"""Report generation backend job task."""

from __future__ import annotations

from typing import Any

from apps.api.db import SessionLocal, get_report
from apps.api.services.reporting_hub import execute_report_generation
from apps.api.settings import get_settings
from services.workers.celery_app import get_celery_app


def run_report_logic(report_id: str) -> dict[str, Any]:
    session = SessionLocal()
    try:
        report = get_report(session, report_id)
        if report is None:
            raise ValueError(f"Unknown report id: {report_id}")
        result = execute_report_generation(session, get_settings(), report)
        session.commit()
        return result
    except Exception:
        session.commit()
        raise
    finally:
        session.close()


try:  # pragma: no branch - import-time switch
    _celery_app = get_celery_app()
except ImportError:  # pragma: no cover - exercised when celery missing
    _celery_app = None


if _celery_app is not None:  # pragma: no cover - covered indirectly
    @_celery_app.task(name="services.workers.tasks.reports.run_report")
    def run_report(report_id: str) -> dict[str, Any]:
        return run_report_logic(report_id)
else:  # pragma: no cover - fallback for celery-less envs
    def run_report(report_id: str) -> dict[str, Any]:
        return run_report_logic(report_id)


__all__ = [
    "run_report",
    "run_report_logic",
]
