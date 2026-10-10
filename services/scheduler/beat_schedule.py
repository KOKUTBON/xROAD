"""Celery-beat schedule definitions.

The schedule is kept as a plain dict so it can be inspected, asserted
on, and rendered as ops documentation without instantiating Celery.
`register_beat_schedule(app)` is the helper that the scheduler
entrypoint calls at boot.

"""
from __future__ import annotations

from typing import Any

from services.workers.settings import WorkerSettings, get_worker_settings


def build_beat_schedule(settings: WorkerSettings | None = None) -> dict[str, dict[str, Any]]:
    """Build the recurring schedule for the worker fleet.

    Returns a Celery-beat-compatible dict. Each entry must include:

    - `task` - fully qualified Celery task name
    - `schedule` - interval in seconds (int) or a `crontab` instance
    - `options` - optional Celery routing options (queue, expires, etc.)

    Production schedules are environment-backed through
    `ROAD_RISK_AUTOMATION_*_INTERVAL_S` and rendered here so Celery beat,
    the API automation dashboard, and ops documentation share one source
    of truth.
    """
    s = settings or get_worker_settings()
    return {
        "health-worker-summary-every-5-minutes": {
            "task": "services.workers.tasks.health.worker_summary",
            "schedule": 300.0,
            "options": {
                "queue": s.task_default_queue,
                "expires": 60,
            },
        },
        "health-ping-every-1-minute": {
            "task": "services.workers.tasks.health.ping",
            "schedule": 60.0,
            "options": {
                "queue": s.task_default_queue,
                "expires": 30,
            },
        },
        "published-refresh-daily": {
            "task": "services.workers.tasks.automation.run_published_refresh_policy",
            "schedule": float(s.published_refresh_interval_seconds),
            "options": {
                "queue": s.task_automation_queue,
                "expires": 600,
            },
        },
        "dashboard-refresh-daily": {
            "task": "services.workers.tasks.automation.run_dashboard_refresh_policy",
            "schedule": float(s.dashboard_refresh_interval_seconds),
            "options": {
                "queue": s.task_automation_queue,
                "expires": 600,
            },
        },
        "stale-source-check-daily": {
            "task": "services.workers.tasks.automation.run_stale_source_check_policy",
            "schedule": float(s.stale_source_check_interval_seconds),
            "options": {
                "queue": s.task_automation_queue,
                "expires": 600,
            },
        },
        "data-quality-check-daily": {
            "task": "services.workers.tasks.automation.run_data_quality_check_policy",
            "schedule": float(s.data_quality_check_interval_seconds),
            "options": {
                "queue": s.task_automation_queue,
                "expires": 600,
            },
        },
        "monthly-report-generation": {
            "task": "services.workers.tasks.automation.run_monthly_report_generation_policy",
            "schedule": float(s.monthly_report_interval_seconds),
            "options": {
                "queue": s.task_automation_queue,
                "expires": 3600,
            },
        },
    }


# Module-level constant kept for ops tooling that just needs to read the
# schedule (for example, to render the operator dashboard).
BEAT_SCHEDULE: dict[str, dict[str, Any]] = build_beat_schedule()


def register_beat_schedule(celery_app: Any, settings: WorkerSettings | None = None) -> dict[str, dict[str, Any]]:
    """Attach the beat schedule onto a Celery app instance.

    Returns the schedule that was applied so the scheduler entrypoint
    can log the contract at boot.
    """
    schedule = build_beat_schedule(settings)
    celery_app.conf.beat_schedule = schedule
    return schedule


__all__ = [
    "BEAT_SCHEDULE",
    "build_beat_schedule",
    "register_beat_schedule",
]
