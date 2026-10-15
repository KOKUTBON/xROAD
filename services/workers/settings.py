"""Worker runtime settings.

The worker runtime is configured exclusively through `ROAD_RISK_*`
environment variables so the same image works under docker compose
locally and against a managed Redis broker in production.

"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class WorkerSettings:
    """Immutable Celery worker configuration snapshot.

    Defaults match the local docker compose stack
    (`infra/docker/docker-compose.yml`). Production deployments should
    override `broker_url` and `result_backend` only.
    """

    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    task_default_queue: str = "road_risk_default"
    task_ingestion_queue: str = "road_risk_ingestion"
    task_published_refresh_queue: str = "road_risk_published_refresh"
    task_reports_queue: str = "road_risk_reports"
    task_automation_queue: str = "road_risk_automation"
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: tuple[str, ...] = field(default_factory=lambda: ("json",))
    timezone: str = "UTC"
    enable_utc: bool = True
    worker_concurrency: int = 4
    worker_prefetch_multiplier: int = 1
    task_acks_late: bool = True
    broker_connection_retry_on_startup: bool = True
    result_expires_seconds: int = 3600
    published_refresh_interval_seconds: int = 86_400
    dashboard_refresh_interval_seconds: int = 86_400
    stale_source_check_interval_seconds: int = 86_400
    data_quality_check_interval_seconds: int = 86_400
    monthly_report_interval_seconds: int = 2_592_000

    @property
    def queue_names(self) -> tuple[str, ...]:
        return (
            self.task_default_queue,
            self.task_ingestion_queue,
            self.task_published_refresh_queue,
            self.task_reports_queue,
            self.task_automation_queue,
        )

    def to_celery_config(self) -> dict[str, object]:
        """Render a dict that can be passed to `celery_app.conf.update`."""
        return {
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            "task_default_queue": self.task_default_queue,
            "task_serializer": self.task_serializer,
            "result_serializer": self.result_serializer,
            "accept_content": list(self.accept_content),
            "timezone": self.timezone,
            "enable_utc": self.enable_utc,
            "worker_concurrency": self.worker_concurrency,
            "worker_prefetch_multiplier": self.worker_prefetch_multiplier,
            "task_acks_late": self.task_acks_late,
            "broker_connection_retry_on_startup": self.broker_connection_retry_on_startup,
            "result_expires": self.result_expires_seconds,
            "task_routes": {
                "services.workers.tasks.ingestion.*": {"queue": self.task_ingestion_queue},
                "services.workers.tasks.published_refresh.*": {
                    "queue": self.task_published_refresh_queue,
                },
                "services.workers.tasks.reports.*": {"queue": self.task_reports_queue},
                "services.workers.tasks.automation.*": {"queue": self.task_automation_queue},
            },
        }


@lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    """Build a `WorkerSettings` from the live environment, cached per process."""
    return WorkerSettings(
        broker_url=_env_str("ROAD_RISK_WORKER_BROKER_URL", _env_str("ROAD_RISK_REDIS_URL", "redis://localhost:6379/0")),
        result_backend=_env_str(
            "ROAD_RISK_WORKER_RESULT_BACKEND",
            _env_str("ROAD_RISK_REDIS_RESULT_URL", "redis://localhost:6379/1"),
        ),
        task_default_queue=_env_str("ROAD_RISK_WORKER_DEFAULT_QUEUE", "road_risk_default"),
        task_ingestion_queue=_env_str("ROAD_RISK_WORKER_INGESTION_QUEUE", "road_risk_ingestion"),
        task_published_refresh_queue=_env_str(
            "ROAD_RISK_WORKER_PUBLISHED_REFRESH_QUEUE",
            "road_risk_published_refresh",
        ),
        task_reports_queue=_env_str("ROAD_RISK_WORKER_REPORTS_QUEUE", "road_risk_reports"),
        task_automation_queue=_env_str("ROAD_RISK_WORKER_AUTOMATION_QUEUE", "road_risk_automation"),
        timezone=_env_str("ROAD_RISK_WORKER_TIMEZONE", "UTC"),
        worker_concurrency=_env_int("ROAD_RISK_WORKER_CONCURRENCY", 4),
        worker_prefetch_multiplier=_env_int("ROAD_RISK_WORKER_PREFETCH_MULTIPLIER", 1),
        task_acks_late=_env_bool("ROAD_RISK_WORKER_ACKS_LATE", True),
        broker_connection_retry_on_startup=_env_bool(
            "ROAD_RISK_WORKER_BROKER_RETRY_ON_STARTUP", True
        ),
        result_expires_seconds=_env_int("ROAD_RISK_WORKER_RESULT_EXPIRES_S", 3600),
        published_refresh_interval_seconds=_env_int("ROAD_RISK_AUTOMATION_PUBLISHED_REFRESH_INTERVAL_S", 86_400),
        dashboard_refresh_interval_seconds=_env_int("ROAD_RISK_AUTOMATION_DASHBOARD_REFRESH_INTERVAL_S", 86_400),
        stale_source_check_interval_seconds=_env_int("ROAD_RISK_AUTOMATION_STALE_SOURCE_CHECK_INTERVAL_S", 86_400),
        data_quality_check_interval_seconds=_env_int("ROAD_RISK_AUTOMATION_DATA_QUALITY_CHECK_INTERVAL_S", 86_400),
        monthly_report_interval_seconds=_env_int("ROAD_RISK_AUTOMATION_MONTHLY_REPORT_INTERVAL_S", 2_592_000),
    )


def reset_worker_settings_cache() -> None:
    """Reset the cached settings (used by tests)."""
    get_worker_settings.cache_clear()


__all__ = [
    "WorkerSettings",
    "get_worker_settings",
    "reset_worker_settings_cache",
]
