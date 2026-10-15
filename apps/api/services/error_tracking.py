"""Optional error tracking integration with safe PII defaults."""

from __future__ import annotations

from typing import Any

from apps.api.settings import ApiSettings


ERROR_TRACKING_CONTRACT_VERSION = "error_tracking_v1"

_SENTRY_CLIENT: Any | None = None
_INITIALIZED = False
_DEPENDENCY_AVAILABLE = False


def configure_error_tracking(settings: ApiSettings) -> dict[str, Any]:
    """Initialize Sentry when configured.

    The dependency is optional so self-hosted deployments can enable it
    without making local development or CI depend on Sentry.
    """
    global _SENTRY_CLIENT, _INITIALIZED, _DEPENDENCY_AVAILABLE
    enabled = bool(settings.error_tracking_enabled and settings.sentry_dsn)
    if not enabled:
        _SENTRY_CLIENT = None
        _INITIALIZED = False
        _DEPENDENCY_AVAILABLE = False
        return build_error_tracking_status(settings)

    try:
        import sentry_sdk  # type: ignore
    except Exception:
        _SENTRY_CLIENT = None
        _INITIALIZED = False
        _DEPENDENCY_AVAILABLE = False
        return build_error_tracking_status(settings)

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    _SENTRY_CLIENT = sentry_sdk
    _INITIALIZED = True
    _DEPENDENCY_AVAILABLE = True
    return build_error_tracking_status(settings)


def capture_exception(exc: BaseException, *, context: dict[str, Any] | None = None) -> None:
    """Capture an exception if the optional tracking client is active."""
    if not _INITIALIZED or _SENTRY_CLIENT is None:
        return
    safe_context = dict(context or {})
    with _SENTRY_CLIENT.push_scope() as scope:
        for key, value in safe_context.items():
            if value is not None:
                scope.set_tag(str(key), str(value))
        _SENTRY_CLIENT.capture_exception(exc)


def build_error_tracking_status(settings: ApiSettings) -> dict[str, Any]:
    return {
        "contract_version": ERROR_TRACKING_CONTRACT_VERSION,
        "enabled": bool(settings.error_tracking_enabled and settings.sentry_dsn),
        "provider": "sentry",
        "initialized": _INITIALIZED,
        "dependency_available": _DEPENDENCY_AVAILABLE,
        "environment": settings.sentry_environment or settings.env,
        "pii_policy": "send_default_pii=false; only request_id, route, status, job/report ids, and aggregate scope counts are tagged",
    }


__all__ = [
    "ERROR_TRACKING_CONTRACT_VERSION",
    "build_error_tracking_status",
    "capture_exception",
    "configure_error_tracking",
]
