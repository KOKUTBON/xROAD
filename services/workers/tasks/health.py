"""Health-check Celery tasks.

These tasks are the only ones registered at the #86 foundation step.
They exist so the broker contract can be exercised by ops tooling and
by the test suite without depending on any of the real analytics
pipelines (which land under #87, #88, and #95).

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.workers.celery_app import get_celery_app


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _ping_payload() -> dict[str, Any]:
    return {
        "task": "services.workers.tasks.health.ping",
        "status": "ok",
        "completed_at": _now_iso(),
    }


def _summary_payload() -> dict[str, Any]:
    """Lightweight worker self-description for ops dashboards.

    Importing `WorkerSettings` here (rather than at module top) keeps the
    function callable without forcing eager environment resolution at
    import time.
    """
    from services.workers.settings import get_worker_settings

    settings = get_worker_settings()
    return {
        "task": "services.workers.tasks.health.worker_summary",
        "status": "ok",
        "completed_at": _now_iso(),
        "queues": list(settings.queue_names),
        "broker_url_scheme": settings.broker_url.split("://", 1)[0],
        "result_backend_scheme": settings.result_backend.split("://", 1)[0],
        "timezone": settings.timezone,
        "worker_concurrency": settings.worker_concurrency,
    }


# Plain functions are kept as a stable testing seam: tests exercise the
# logic without spinning up a Celery worker. The Celery decorators below
# turn them into registered tasks when celery is available.
ping_logic = _ping_payload
worker_summary_logic = _summary_payload


try:  # pragma: no branch - import-time switch
    _celery_app = get_celery_app()
except ImportError:  # pragma: no cover - exercised when celery missing
    _celery_app = None


if _celery_app is not None:  # pragma: no cover - covered indirectly
    @_celery_app.task(name="services.workers.tasks.health.ping")
    def ping() -> dict[str, Any]:
        """Return a static OK payload, used by ops to confirm the broker contract."""
        return _ping_payload()

    @_celery_app.task(name="services.workers.tasks.health.worker_summary")
    def worker_summary() -> dict[str, Any]:
        """Return the worker's effective queue/broker shape for ops dashboards."""
        return _summary_payload()
else:  # pragma: no cover - fallback for celery-less envs
    def ping() -> dict[str, Any]:
        return _ping_payload()

    def worker_summary() -> dict[str, Any]:
        return _summary_payload()


__all__ = [
    "ping",
    "worker_summary",
    "ping_logic",
    "worker_summary_logic",
]
