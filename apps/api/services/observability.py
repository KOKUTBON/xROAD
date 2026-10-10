"""Observability surfaces: info, readiness, lightweight metrics.

This service is the API-side reader for production observability. It
exposes:

- a stable `info` payload (app, API version, auth provider, optional
  build metadata from `ROAD_RISK_BUILD_*` env vars)
- a structured `readiness` check (does the published index exist, does
  the dashboard summary exist, does the scenario index exist, is the
  scheduler module importable, are the operational tables reachable
  via a cheap session-level probe)
- a minimal `metrics` snapshot (counts that ops cares about during an
  incident: ingestion job statuses, recent automation runs, total
  audit-log entries)

"""
from __future__ import annotations

import os
import platform
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.db import repositories
from apps.api.middleware.operational_hardening import get_runtime_metrics_registry
from apps.api.services import error_tracking
from apps.api.settings import ApiSettings


OBSERVABILITY_INFO_CONTRACT_VERSION = "observability_info_v1"
OBSERVABILITY_READINESS_CONTRACT_VERSION = "observability_readiness_v1"
OBSERVABILITY_METRICS_CONTRACT_VERSION = "observability_metrics_v2"

PROCESS_START_AT = time.monotonic()


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_path(path_value: Path, *, root_dir: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return (root_dir / path_value).resolve()


def build_info_payload(settings: ApiSettings) -> dict[str, Any]:
    """Stable identity payload for ops dashboards and load balancers."""
    return {
        "contract_version": OBSERVABILITY_INFO_CONTRACT_VERSION,
        "app_name": "road-risk-api",
        "app_environment": os.environ.get("ROAD_RISK_API_ENV", "local"),
        "build_sha": os.environ.get("ROAD_RISK_BUILD_SHA"),
        "build_ref": os.environ.get("ROAD_RISK_BUILD_REF"),
        "build_timestamp": os.environ.get("ROAD_RISK_BUILD_TIMESTAMP"),
        "auth_provider": settings.auth_provider if settings.auth_enabled else "disabled",
        "auth_enabled": bool(settings.auth_enabled),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "process_uptime_seconds": int(time.monotonic() - PROCESS_START_AT),
        "generated_at": _iso_now(),
    }


def _check_artifact(path: Path) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "path": str(path),
        "status": "ready" if exists else "missing",
        "exists": exists,
    }


def _check_scheduler_module() -> dict[str, Any]:
    try:
        from services.scheduler.beat_schedule import build_beat_schedule

        schedule = build_beat_schedule()
        return {
            "status": "ready",
            "entry_count": len(schedule or {}),
            "module": "services.scheduler.beat_schedule",
        }
    except Exception as exc:  # pragma: no cover - imported in CI
        return {
            "status": "unavailable",
            "module": "services.scheduler.beat_schedule",
            "error": str(exc),
        }


def _check_database_session(session: Session | None) -> dict[str, Any]:
    if session is None:
        return {"status": "not_attempted"}
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # pragma: no cover - exercised in integration
        return {"status": "unavailable", "error": str(exc)}


def build_readiness_payload(
    settings: ApiSettings,
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    """Structured readiness probe for liveness + readiness load balancing."""
    checks = {
        "published_index": _check_artifact(
            _resolve_path(settings.published_index_path, root_dir=settings.root_dir),
        ),
        "dashboard_summary": _check_artifact(
            _resolve_path(settings.dashboard_summary_path, root_dir=settings.root_dir),
        ),
        "scenario_index": _check_artifact(
            _resolve_path(
                Path("data/planning/scenario_countermeasures/scenario_countermeasure_index.json"),
                root_dir=settings.root_dir,
            ),
        ),
        "scheduler_module": _check_scheduler_module(),
        "database_session": _check_database_session(session),
    }
    failing = [name for name, value in checks.items() if value.get("status") not in {"ready", "not_attempted"}]
    overall = "ready" if not failing else "degraded"
    return {
        "contract_version": OBSERVABILITY_READINESS_CONTRACT_VERSION,
        "status": overall,
        "failing": failing,
        "checks": checks,
        "generated_at": _iso_now(),
    }


def build_metrics_payload(
    session: Session,
    *,
    organization_id: str,
    recent_runs_limit: int = 100,
    settings: ApiSettings | None = None,
) -> dict[str, Any]:
    """Minimal metrics snapshot for one organization.

    This is intentionally a thin wrapper over the existing repository
    helpers; the long-term plan is to swap in Prometheus / OpenTelemetry
    once the relevant infra lands. The shape is contracted so that swap
    is additive rather than breaking.
    """
    jobs = repositories.list_ingestion_jobs_for_organization(session, organization_id)
    job_status_counts: Counter[str] = Counter(j.status for j in jobs)
    job_type_counts: Counter[str] = Counter(j.job_type for j in jobs)
    completed_jobs = job_status_counts.get("completed", 0)
    failed_jobs = job_status_counts.get("failed", 0)
    terminal_jobs = completed_jobs + failed_jobs

    audit_logs = repositories.list_audit_logs_for_organization(session, organization_id)
    audit_action_counts: Counter[str] = Counter(
        getattr(record, "action", None) or "unknown" for record in audit_logs
    )

    data_sources = repositories.list_data_sources_for_organization(session, organization_id)
    governance_counts: Counter[str] = Counter(s.governance_status for s in data_sources)
    now = datetime.now(tz=timezone.utc)
    stale_sources = [
        source
        for source in data_sources
        if source.status == "active"
        and source.refresh_frequency not in {None, "", "manual", "on_demand"}
        and (
            source.last_refresh_at is None
            or _as_utc(source.last_refresh_at)
            < now - timedelta(days=2 if source.refresh_frequency == "daily" else 14)
        )
    ]

    reports = repositories.list_reports_for_organization(session, organization_id)
    report_status_counts: Counter[str] = Counter(report.status for report in reports)
    report_type_counts: Counter[str] = Counter(report.report_type for report in reports)

    artifacts = repositories.list_artifact_references_for_organization(session, organization_id)
    artifact_kind_counts: Counter[str] = Counter(artifact.artifact_kind for artifact in artifacts)
    publication_tier_counts: Counter[str] = Counter(artifact.publication_tier for artifact in artifacts)
    total_storage_bytes = 0
    for artifact in artifacts:
        lineage = dict(artifact.lineage_json or {})
        total_storage_bytes += _as_int(lineage.get("size_bytes") or lineage.get("content_length"))

    memberships = repositories.list_memberships_for_organization(session, organization_id)
    active_memberships = [membership for membership in memberships if membership.status == "active"]

    total_rows = 0
    rejected_rows = 0
    accepted_rows = 0
    for job in jobs:
        stats = dict(job.job_stats_json or {})
        total_rows += _as_int(stats.get("total_rows") or stats.get("preview_row_count"))
        rejected_rows += _as_int(stats.get("rejected_rows") or stats.get("rejected_preview_rows"))
        accepted_rows += _as_int(
            stats.get("written_rows")
            or stats.get("accepted_rows")
            or stats.get("accepted_preview_rows")
        )

    recent_runs = jobs[:recent_runs_limit]
    return {
        "contract_version": OBSERVABILITY_METRICS_CONTRACT_VERSION,
        "organization_id": organization_id,
        "generated_at": _iso_now(),
        "ingestion_jobs": {
            "total": len(jobs),
            "by_status": dict(job_status_counts),
            "by_job_type": dict(job_type_counts),
            "recent_window": len(recent_runs),
            "success_rate": round((completed_jobs / terminal_jobs), 4) if terminal_jobs else 0.0,
            "failure_rate": round((failed_jobs / terminal_jobs), 4) if terminal_jobs else 0.0,
            "row_quality": {
                "total_rows": total_rows,
                "accepted_rows": accepted_rows,
                "rejected_rows": rejected_rows,
                "rejection_rate": round((rejected_rows / total_rows), 4) if total_rows else 0.0,
            },
        },
        "audit_log": {
            "total": len(audit_logs),
            "by_action": dict(audit_action_counts),
        },
        "data_sources": {
            "total": len(data_sources),
            "by_governance_status": dict(governance_counts),
            "stale_count": len(stale_sources),
            "stale_source_ids": [str(source.id) for source in stale_sources[:25]],
        },
        "reports": {
            "total": len(reports),
            "by_status": dict(report_status_counts),
            "by_report_type": dict(report_type_counts),
            "generated_total": report_status_counts.get("generated", 0),
            "failed_total": report_status_counts.get("failed", 0),
        },
        "storage": {
            "artifact_references": len(artifacts),
            "by_artifact_kind": dict(artifact_kind_counts),
            "by_publication_tier": dict(publication_tier_counts),
            "known_total_bytes": total_storage_bytes,
        },
        "active_users": {
            "active_memberships": len(active_memberships),
            "recent_request_subjects": get_runtime_metrics_registry().snapshot()["active_user_count"],
        },
        "api_runtime": get_runtime_metrics_registry().snapshot(),
        "error_tracking": error_tracking.build_error_tracking_status(settings or ApiSettings()),
        "security_controls": {
            "rate_limiting": {
                "enabled": bool(settings.rate_limit_enabled) if settings else False,
                "requests": settings.rate_limit_requests if settings else None,
                "window_seconds": settings.rate_limit_window_seconds if settings else None,
            },
            "cors_allowed_origins": [
                origin.strip()
                for origin in (settings.cors_allowed_origins if settings else "").split(",")
                if origin.strip()
            ],
        },
    }


__all__ = [
    "OBSERVABILITY_INFO_CONTRACT_VERSION",
    "OBSERVABILITY_METRICS_CONTRACT_VERSION",
    "OBSERVABILITY_READINESS_CONTRACT_VERSION",
    "build_info_payload",
    "build_metrics_payload",
    "build_readiness_payload",
]
