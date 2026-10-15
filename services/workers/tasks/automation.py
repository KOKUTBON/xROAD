"""Scheduled automation policy tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.workers.celery_app import get_celery_app


def _policy_payload(policy_name: str) -> dict[str, Any]:
    return {
        "contract_version": "automation_scheduled_policy_task_v1",
        "policy_name": policy_name,
        "executed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_published_refresh_policy_logic() -> dict[str, Any]:
    return _policy_payload("published_refresh")


def run_dashboard_refresh_policy_logic() -> dict[str, Any]:
    return _policy_payload("dashboard_refresh")


def run_stale_source_check_policy_logic() -> dict[str, Any]:
    return _policy_payload("stale_source_check")


def run_data_quality_check_policy_logic() -> dict[str, Any]:
    return _policy_payload("data_quality_check")


def run_monthly_report_generation_policy_logic() -> dict[str, Any]:
    return _policy_payload("monthly_report_generation")


try:  # pragma: no branch - import-time switch
    _celery_app = get_celery_app()
except ImportError:  # pragma: no cover - exercised when celery missing
    _celery_app = None


if _celery_app is not None:  # pragma: no cover - covered indirectly
    @_celery_app.task(name="services.workers.tasks.automation.run_published_refresh_policy")
    def run_published_refresh_policy() -> dict[str, Any]:
        return run_published_refresh_policy_logic()

    @_celery_app.task(name="services.workers.tasks.automation.run_dashboard_refresh_policy")
    def run_dashboard_refresh_policy() -> dict[str, Any]:
        return run_dashboard_refresh_policy_logic()

    @_celery_app.task(name="services.workers.tasks.automation.run_stale_source_check_policy")
    def run_stale_source_check_policy() -> dict[str, Any]:
        return run_stale_source_check_policy_logic()

    @_celery_app.task(name="services.workers.tasks.automation.run_data_quality_check_policy")
    def run_data_quality_check_policy() -> dict[str, Any]:
        return run_data_quality_check_policy_logic()

    @_celery_app.task(name="services.workers.tasks.automation.run_monthly_report_generation_policy")
    def run_monthly_report_generation_policy() -> dict[str, Any]:
        return run_monthly_report_generation_policy_logic()
else:  # pragma: no cover - fallback for celery-less envs
    def run_published_refresh_policy() -> dict[str, Any]:
        return run_published_refresh_policy_logic()

    def run_dashboard_refresh_policy() -> dict[str, Any]:
        return run_dashboard_refresh_policy_logic()

    def run_stale_source_check_policy() -> dict[str, Any]:
        return run_stale_source_check_policy_logic()

    def run_data_quality_check_policy() -> dict[str, Any]:
        return run_data_quality_check_policy_logic()

    def run_monthly_report_generation_policy() -> dict[str, Any]:
        return run_monthly_report_generation_policy_logic()


__all__ = [
    "run_dashboard_refresh_policy",
    "run_dashboard_refresh_policy_logic",
    "run_data_quality_check_policy",
    "run_data_quality_check_policy_logic",
    "run_monthly_report_generation_policy",
    "run_monthly_report_generation_policy_logic",
    "run_published_refresh_policy",
    "run_published_refresh_policy_logic",
    "run_stale_source_check_policy",
    "run_stale_source_check_policy_logic",
]
