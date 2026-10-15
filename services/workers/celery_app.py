"""Celery app factory for the Road Risk worker runtime.

The factory returns a configured `Celery` instance with:

- Redis broker + result backend (configurable via `WorkerSettings`)
- JSON-only task / result serialization
- Per-pipeline queue routes (ingestion, published refresh, reports)
- Auto-discovery of `services.workers.tasks` modules

Importing this module is safe even when the `celery` package is not
installed (the import simply raises a clear ImportError when the app is
actually used). That keeps the API container's slim install path -
which does not need celery - from breaking.

"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from services.workers.settings import WorkerSettings, get_worker_settings

if TYPE_CHECKING:
    from celery import Celery


def _require_celery() -> Any:
    try:
        from celery import Celery
    except ImportError as exc:  # pragma: no cover - exercised when celery missing
        raise ImportError(
            "Celery is not installed. Install the worker extras with "
            "`pip install -e '.[worker]'` to use services.workers.celery_app."
        ) from exc
    return Celery


def build_celery_app(settings: WorkerSettings | None = None) -> "Celery":
    """Build a freshly-configured Celery app.

    This function is the dependency-injection seam used by tests and by
    the cached `get_celery_app()` accessor. Callers that need to swap
    settings (for example, an integration test that points at a
    throwaway broker) should call `build_celery_app(custom_settings)`.
    """
    celery_settings = settings or get_worker_settings()
    Celery = _require_celery()

    app = Celery(
        "road_risk",
        broker=celery_settings.broker_url,
        backend=celery_settings.result_backend,
        include=[
            "services.workers.tasks",
            "services.workers.tasks.automation",
            "services.workers.tasks.health",
            "services.workers.tasks.ingestion",
            "services.workers.tasks.published_refresh",
            "services.workers.tasks.reports",
        ],
    )
    app.conf.update(celery_settings.to_celery_config())
    return app


@lru_cache(maxsize=1)
def get_celery_app() -> "Celery":
    """Return the process-cached Celery app."""
    return build_celery_app()


# Module-level alias kept so `-A services.workers.celery_app` resolves
# without needing the `app:` suffix when celery is available. When
# celery is not installed we expose a `None` placeholder so importing
# the module from the API container still succeeds.
try:  # pragma: no branch - import-time switch
    celery_app: "Celery | None" = build_celery_app()
except ImportError:  # pragma: no cover - exercised when celery missing
    celery_app = None


__all__ = [
    "build_celery_app",
    "celery_app",
    "get_celery_app",
]
