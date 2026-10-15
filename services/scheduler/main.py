"""Entrypoint module for `celery -A services.scheduler.main beat`.

This module is what the scheduler container's `CMD` points at. It
registers the canonical beat schedule on the shared Celery app before
celery-beat starts consuming it.

"""
from __future__ import annotations

from services.scheduler.beat_schedule import register_beat_schedule
from services.workers.celery_app import get_celery_app


def _bootstrap() -> object:
    app = get_celery_app()
    register_beat_schedule(app)
    return app


# Celery looks for a module-level `app` attribute when invoked as
# `celery -A services.scheduler.main beat`.
app = _bootstrap()


__all__ = ["app"]
