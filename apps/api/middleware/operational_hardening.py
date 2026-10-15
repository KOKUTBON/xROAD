"""Operational hardening middleware for request logs, metrics, and rate limits."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from apps.api.auth import AuthContext, get_current_auth_context, set_current_auth_context
from apps.api.services import error_tracking


REQUEST_OBSERVABILITY_CONTRACT_VERSION = "request_observability_v1"
RATE_LIMIT_CONTRACT_VERSION = "rate_limit_v1"


def _now() -> float:
    return time.monotonic()


def _subject_hash(subject: str | None) -> str | None:
    if not subject:
        return None
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    return request.url.path


def _job_or_report_id(request: Request) -> str | None:
    path_params = getattr(request, "path_params", {}) or {}
    for key in ("job_id", "report_id", "scenario_draft_id", "scenario_run_id"):
        value = path_params.get(key)
        if value:
            return str(value)
    return None


@dataclass
class RuntimeMetricsRegistry:
    """In-memory per-process request metrics for incident triage."""

    max_latency_samples: int = 1000
    total_requests: int = 0
    total_errors: int = 0
    status_counts: Counter[str] = field(default_factory=Counter)
    method_counts: Counter[str] = field(default_factory=Counter)
    route_counts: Counter[str] = field(default_factory=Counter)
    route_error_counts: Counter[str] = field(default_factory=Counter)
    latency_samples_ms: deque[float] = field(default_factory=deque)
    active_subject_hashes: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self.latency_samples_ms = deque(maxlen=self.max_latency_samples)

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        auth_context: AuthContext | None,
    ) -> None:
        subject_hash = _subject_hash(auth_context.subject if auth_context else None)
        with self._lock:
            self.total_requests += 1
            if status_code >= 500:
                self.total_errors += 1
                self.route_error_counts[route] += 1
            self.status_counts[str(status_code)] += 1
            self.method_counts[method] += 1
            self.route_counts[route] += 1
            self.latency_samples_ms.append(duration_ms)
            if subject_hash:
                self.active_subject_hashes.add(subject_hash)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            samples = sorted(self.latency_samples_ms)
            total = self.total_requests
            if samples:
                p95_index = min(len(samples) - 1, int(round((len(samples) - 1) * 0.95)))
                avg_latency = sum(samples) / len(samples)
                p95_latency = samples[p95_index]
                max_latency = samples[-1]
            else:
                avg_latency = 0.0
                p95_latency = 0.0
                max_latency = 0.0
            return {
                "contract_version": REQUEST_OBSERVABILITY_CONTRACT_VERSION,
                "total_requests": total,
                "total_errors": self.total_errors,
                "error_rate": round((self.total_errors / total), 4) if total else 0.0,
                "by_status": dict(self.status_counts),
                "by_method": dict(self.method_counts),
                "top_routes": dict(self.route_counts.most_common(10)),
                "routes_with_5xx": dict(self.route_error_counts.most_common(10)),
                "latency_ms": {
                    "sample_count": len(samples),
                    "avg": round(avg_latency, 2),
                    "p95": round(p95_latency, 2),
                    "max": round(max_latency, 2),
                },
                "active_user_count": len(self.active_subject_hashes),
            }


RUNTIME_METRICS = RuntimeMetricsRegistry()


def get_runtime_metrics_registry() -> RuntimeMetricsRegistry:
    return RUNTIME_METRICS


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Attach request IDs, emit JSON request logs, and collect metrics."""

    def __init__(
        self,
        app,
        *,
        request_id_header: str = "X-Request-ID",
        logging_enabled: bool = True,
        json_logs: bool = True,
        metrics_registry: RuntimeMetricsRegistry | None = None,
    ) -> None:
        super().__init__(app)
        self.request_id_header = request_id_header
        self.logging_enabled = logging_enabled
        self.json_logs = json_logs
        self.metrics_registry = metrics_registry or RUNTIME_METRICS
        self.logger = logging.getLogger("road_risk.api.requests")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        set_current_auth_context(None)
        request_id = request.headers.get(self.request_id_header) or str(uuid4())
        request.state.request_id = request_id
        started_at = _now()
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_tracking.capture_exception(
                exc,
                context={
                    "request_id": request_id,
                    "route": _route_template(request),
                    "job_or_report_id": _job_or_report_id(request),
                },
            )
            raise
        finally:
            duration_ms = (_now() - started_at) * 1000
            route = _route_template(request)
            auth_context = getattr(request.state, "auth_context", None) or get_current_auth_context()
            self.metrics_registry.record_request(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_ms=duration_ms,
                auth_context=auth_context,
            )
            if response is not None:
                response.headers[self.request_id_header] = request_id
            if self.logging_enabled:
                self._log_request(
                    request=request,
                    request_id=request_id,
                    route=route,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    auth_context=auth_context,
                )

    def _log_request(
        self,
        *,
        request: Request,
        request_id: str,
        route: str,
        status_code: int,
        duration_ms: float,
        auth_context: AuthContext | None,
    ) -> None:
        payload = {
            "event": "api_request",
            "request_id": request_id,
            "method": request.method,
            "route": route,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "job_or_report_id": _job_or_report_id(request),
            "user_subject_hash": _subject_hash(auth_context.subject if auth_context else None),
            "organization_ids": sorted(auth_context.organization_ids) if auth_context else [],
            "municipality_ids": sorted(auth_context.municipality_ids) if auth_context else [],
            "role_count": len(auth_context.roles) if auth_context else 0,
        }
        if self.json_logs:
            self.logger.info(json.dumps(payload, sort_keys=True))
        else:
            self.logger.info(
                "api_request request_id=%s method=%s route=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                route,
                status_code,
                duration_ms,
            )


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple fixed-window rate limiter for public/API routes."""

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        request_limit: int,
        window_seconds: int,
        exempt_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.request_limit = max(1, request_limit)
        self.window_seconds = max(1, window_seconds)
        self.exempt_paths = exempt_paths
        self._lock = Lock()
        self._buckets: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self.enabled or self._is_exempt(request.url.path):
            return await call_next(request)
        key = self._client_key(request)
        allowed, remaining, retry_after = self._consume(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded.",
                    "rate_limit_contract_version": RATE_LIMIT_CONTRACT_VERSION,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.request_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.request_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _is_exempt(self, path: str) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.exempt_paths)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _consume(self, key: str) -> tuple[bool, int, int]:
        now = _now()
        with self._lock:
            window_start, count = self._buckets[key]
            if now - window_start >= self.window_seconds:
                window_start = now
                count = 0
            count += 1
            self._buckets[key] = (window_start, count)
            remaining = max(0, self.request_limit - count)
            retry_after = max(1, int(self.window_seconds - (now - window_start)))
            return count <= self.request_limit, remaining, retry_after


__all__ = [
    "RATE_LIMIT_CONTRACT_VERSION",
    "REQUEST_OBSERVABILITY_CONTRACT_VERSION",
    "InMemoryRateLimitMiddleware",
    "RequestObservabilityMiddleware",
    "RuntimeMetricsRegistry",
    "get_runtime_metrics_registry",
]
