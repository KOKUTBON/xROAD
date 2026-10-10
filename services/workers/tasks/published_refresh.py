"""Published refresh backend job task."""

from __future__ import annotations

from typing import Any

from apps.api.db import SessionLocal, get_ingestion_job
from apps.api.services.published_refresh_jobs import execute_published_refresh_job
from services.workers.celery_app import get_celery_app


def run_job_logic(job_id: str) -> dict[str, Any]:
    """Run the first production backend job against an existing DB record."""
    session = SessionLocal()
    try:
        job = get_ingestion_job(session, job_id)
        if job is None:
            raise ValueError(f"Unknown ingestion job id: {job_id}")
        result = execute_published_refresh_job(session, job)
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
    @_celery_app.task(name="services.workers.tasks.published_refresh.run_job")
    def run_job(job_id: str) -> dict[str, Any]:
        return run_job_logic(job_id)
else:  # pragma: no cover - fallback for celery-less envs
    def run_job(job_id: str) -> dict[str, Any]:
        return run_job_logic(job_id)


__all__ = [
    "run_job",
    "run_job_logic",
]
