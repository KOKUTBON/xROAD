"""Security-headers middleware.

Adds a small, audited set of security response headers to every API
response. The defaults are aligned with WCAG 2.1 + OWASP secure-header
guidance and the production hardening boundary called out by #96.

The middleware is intentionally additive: it only sets headers that
are not already present, so a downstream reverse proxy (Nginx, Envoy,
the cloud load balancer) can override them when it has stricter
policies.

"""
from __future__ import annotations

from typing import Awaitable, Callable, Iterable, Mapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


SECURITY_HEADERS_CONTRACT_VERSION = "security_headers_v1"


DEFAULT_SECURITY_HEADERS: dict[str, str] = {
    # Tells browsers to keep the response in the inferred content-type;
    # blocks MIME-sniffing-based attacks.
    "X-Content-Type-Options": "nosniff",
    # Disallows the API JSON from being rendered inside a third-party
    # iframe (the API never serves HTML interactively).
    "X-Frame-Options": "DENY",
    # Strict referrer policy: do not leak the API path to cross-origin
    # navigations.
    "Referrer-Policy": "no-referrer",
    # Disable privileged browser features from the JSON surface.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Force HTTPS for one year once we are deployed behind TLS. This is
    # ignored on plain-HTTP local dev.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Lock JSON responses down with a minimal CSP. JSON does not embed
    # scripts; this guards the Swagger UI from being repurposed as an
    # attack surface in production-like deploys.
    "Content-Security-Policy": (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply a fixed set of security headers to every response.

    Existing headers are preserved; the middleware never overwrites a
    header set by a downstream component.
    """

    def __init__(
        self,
        app,
        headers: Mapping[str, str] | None = None,
        *,
        exclude_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._headers = dict(headers or DEFAULT_SECURITY_HEADERS)
        self._exclude_paths = tuple(exclude_paths or ())

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._exclude_paths):
            return response
        for name, value in self._headers.items():
            if name not in response.headers:
                response.headers[name] = value
        return response


__all__ = [
    "DEFAULT_SECURITY_HEADERS",
    "SECURITY_HEADERS_CONTRACT_VERSION",
    "SecurityHeadersMiddleware",
]
