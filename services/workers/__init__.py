"""Celery worker runtime for the Road Risk product platform.

The `celery_app` module owns the broker/result-backend configuration and
the task registry. The first real wrapped job is the published refresh
task from #87, exposed on top of the worker foundation that landed
under closed issue #86.
"""

from services.workers.celery_app import celery_app, get_celery_app
from services.workers.settings import WorkerSettings, get_worker_settings

__all__ = [
    "celery_app",
    "get_celery_app",
    "WorkerSettings",
    "get_worker_settings",
]
