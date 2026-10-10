"""Scheduled refresh, notifications, and automation controls.

This service is the product-side reader for the automation surface
that grew out of #87 (published refresh job) and #86 (scheduler beat
schedule). It composes:

- the live, environment-backed beat schedule from `services.scheduler.beat_schedule`
- the automation-run history (org-scoped) from the `ingestion_jobs`
  table - the same table that #87 uses to track wrapped refresh runs
- persisted schedule controls stored as audit-log events
- stale-source detection derived from `data_sources.refresh_frequency`
- a notifications feed derived from `audit_logs` filtered to the
  events ops cares about (refresh completion, refresh failure, manual
  trigger, governance change)
- a manual-trigger path that creates a queued `ingestion_job` row
  (the worker registered in #86 + #87 picks it up)

"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import html
import json
from typing import Any, Iterable
from urllib import request as urllib_request
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from apps.api.db import repositories


AUTOMATION_OVERVIEW_CONTRACT_VERSION = "automation_overview_v1"
AUTOMATION_SCHEDULES_CONTRACT_VERSION = "automation_schedules_v1"
AUTOMATION_RUNS_CONTRACT_VERSION = "automation_runs_v1"
AUTOMATION_NOTIFICATIONS_CONTRACT_VERSION = "automation_notifications_v1"
AUTOMATION_MANUAL_TRIGGER_CONTRACT_VERSION = "automation_manual_trigger_v1"
AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION = "automation_schedule_control_v1"
AUTOMATION_STALE_SOURCES_CONTRACT_VERSION = "automation_stale_sources_v1"
AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION = "automation_notification_delivery_v1"
AUTOMATION_NOTIFICATION_DIGEST_CONTRACT_VERSION = "automation_notification_digest_v1"

AUTOMATION_RUN_JOB_TYPES: tuple[str, ...] = (
    "published_refresh",
    "dashboard_refresh",
    "manual_refresh",
    "scheduled_refresh",
)

NOTIFICATION_AUDIT_ACTIONS: tuple[str, ...] = (
    "published_refresh.completed",
    "published_refresh.failed",
    "published_refresh.triggered",
    "scheduled_refresh.completed",
    "scheduled_refresh.failed",
    "scheduled_refresh.triggered",
    "manual_refresh.triggered",
    "ingestion_job.failed",
    "data_source.stale",
    "data_source.approved",
    "data_source.blocked",
    "automation.notification.delivered",
    "automation.schedule.paused",
    "automation.schedule.resumed",
    "automation.schedule.updated",
)

SCHEDULE_CONTROL_ACTIONS = frozenset({"pause", "resume", "update"})
SCHEDULE_AUDIT_ACTIONS = frozenset(
    {
        "automation.schedule.paused",
        "automation.schedule.resumed",
        "automation.schedule.updated",
    }
)
DEFAULT_NOTIFICATION_CHANNELS = ("email_outbox", "webhook")
REFRESH_FREQUENCY_SECONDS = {
    "hourly": 3_600,
    "daily": 86_400,
    "weekly": 604_800,
    "monthly": 2_592_000,
    "quarterly": 7_776_000,
}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _render_schedule_value(value: Any) -> dict[str, Any]:
    if isinstance(value, (int, float)):
        return {"kind": "interval_seconds", "value": float(value)}
    return {"kind": "celery_schedule", "value": repr(value)}


def _automation_policy_for_name(name: str) -> dict[str, Any]:
    if "stale-source" in name:
        return {
            "policy_kind": "stale_source_detection",
            "notification_triggers": ["data_source.stale"],
            "description": "Detect sources beyond their refresh policy and notify admins.",
        }
    if "data-quality" in name:
        return {
            "policy_kind": "data_quality_check",
            "notification_triggers": ["ingestion_job.failed", "data_source.blocked"],
            "description": "Run data-quality readiness checks after source changes.",
        }
    if "monthly-report" in name:
        return {
            "policy_kind": "monthly_report_generation",
            "notification_triggers": ["scheduled_refresh.failed"],
            "description": "Generate monthly executive and public transparency report requests.",
        }
    if "published-refresh" in name or "dashboard-refresh" in name:
        return {
            "policy_kind": "published_refresh",
            "notification_triggers": ["published_refresh.failed", "scheduled_refresh.failed"],
            "description": "Refresh published resources and dashboard artifacts.",
        }
    return {
        "policy_kind": "health",
        "notification_triggers": ["scheduled_refresh.failed"],
        "description": "Scheduler health and worker availability checks.",
    }


def _schedule_control_state(session: Session | None, organization_id: str | None) -> dict[str, dict[str, Any]]:
    if session is None or not organization_id:
        return {}
    try:
        logs = repositories.list_audit_logs_for_organization(session, organization_id)
    except Exception:
        return {}
    state: dict[str, dict[str, Any]] = {}
    for record in reversed(logs):
        action = getattr(record, "action", None)
        if action not in SCHEDULE_AUDIT_ACTIONS:
            continue
        metadata = dict(getattr(record, "metadata_json", None) or {})
        name = str(metadata.get("schedule_name") or "")
        if not name:
            continue
        entry = state.setdefault(name, {})
        if action == "automation.schedule.paused":
            entry["paused"] = True
        elif action == "automation.schedule.resumed":
            entry["paused"] = False
        elif action == "automation.schedule.updated":
            if metadata.get("schedule_seconds") is not None:
                entry["schedule_override"] = float(metadata["schedule_seconds"])
            if metadata.get("notification_channels") is not None:
                entry["notification_channels"] = list(metadata["notification_channels"] or [])
    return state


def list_automation_schedules(
    *,
    session: Session | None = None,
    organization_id: str | None = None,
    beat_schedule: dict[str, Any] | None = None,
    paused_entries: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the schedule roster annotated with pause-state metadata.

    `paused_entries` is the set of beat-schedule entry names that the
    operator has paused. Until a write path exists this is always an
    empty set; the parameter keeps the contract stable for the
    pause/resume/update APIs persist overrides as audit-log events. The
    scheduler cadence itself remains environment-backed for v1.
    """
    if beat_schedule is None:
        try:
            from services.scheduler.beat_schedule import build_beat_schedule

            beat_schedule = build_beat_schedule()
        except ImportError:
            beat_schedule = None

    persisted_state = _schedule_control_state(session, organization_id)
    paused_set = set(paused_entries or [])
    entries: list[dict[str, Any]] = []
    if beat_schedule:
        for name, entry in beat_schedule.items():
            state = persisted_state.get(name, {})
            schedule_value = state.get("schedule_override", entry.get("schedule"))
            paused = bool(state.get("paused", name in paused_set))
            entries.append(
                {
                    "name": name,
                    "task": entry.get("task"),
                    "schedule": _render_schedule_value(schedule_value),
                    "base_schedule": _render_schedule_value(entry.get("schedule")),
                    "options": dict(entry.get("options") or {}),
                    "paused": paused,
                    "policy": _automation_policy_for_name(name),
                    "notification_channels": list(state.get("notification_channels") or DEFAULT_NOTIFICATION_CHANNELS),
                    "configuration_source": "audit_override" if state else "environment",
                }
            )
    return {
        "contract_version": AUTOMATION_SCHEDULES_CONTRACT_VERSION,
        "scheduler_available": beat_schedule is not None,
        "entry_count": len(entries),
        "paused_count": sum(1 for e in entries if e["paused"]),
        "entries": entries,
    }


def _automation_run_row(record: Any) -> dict[str, Any]:
    return {
        "job_id": str(record.id),
        "job_type": record.job_type,
        "status": record.status,
        "municipality_id": str(record.municipality_id) if getattr(record, "municipality_id", None) else None,
        "source_id": str(record.source_id) if getattr(record, "source_id", None) else None,
        "submitted_by_user_id": str(record.submitted_by_user_id) if getattr(record, "submitted_by_user_id", None) else None,
        "created_at": _iso(getattr(record, "created_at", None)),
        "started_at": _iso(getattr(record, "started_at", None)),
        "finished_at": _iso(getattr(record, "finished_at", None)),
    }


def list_automation_runs(
    session: Session,
    *,
    organization_id: str,
    job_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return the automation-run history for one organization."""
    all_jobs = repositories.list_ingestion_jobs_for_organization(
        session, organization_id,
    )
    filtered: list[Any] = []
    for job in all_jobs:
        if job.job_type not in AUTOMATION_RUN_JOB_TYPES:
            continue
        if job_type is not None and job.job_type != job_type:
            continue
        filtered.append(job)
    rows = [_automation_run_row(j) for j in filtered[: max(limit, 0)]]
    status_counts: Counter[str] = Counter(r["status"] for r in rows)
    type_counts: Counter[str] = Counter(r["job_type"] for r in rows)
    return {
        "contract_version": AUTOMATION_RUNS_CONTRACT_VERSION,
        "organization_id": organization_id,
        "filters": {"job_type": job_type, "limit": limit},
        "totals": {
            "total": len(rows),
            "by_status": dict(status_counts),
            "by_job_type": dict(type_counts),
        },
        "runs": rows,
    }


def _notification_row(record: Any) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "action": getattr(record, "action", None) or getattr(record, "event_type", None),
        "target_type": getattr(record, "target_type", None),
        "target_id": getattr(record, "target_id", None),
        "status": getattr(record, "status", None),
        "actor_user_id": str(record.user_id) if getattr(record, "user_id", None) else None,
        "created_at": _iso(getattr(record, "created_at", None)),
        "metadata": dict(getattr(record, "metadata_json", None) or {}),
    }


def list_notifications(
    session: Session,
    *,
    organization_id: str,
    actions: Iterable[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return audit-log-derived notifications for one organization."""
    allowed_actions = set(actions or NOTIFICATION_AUDIT_ACTIONS)
    raw_logs = repositories.list_audit_logs_for_organization(session, organization_id)
    rows: list[dict[str, Any]] = []
    for record in raw_logs:
        action = getattr(record, "action", None) or getattr(record, "event_type", None)
        if action not in allowed_actions:
            continue
        rows.append(_notification_row(record))
        if len(rows) >= max(limit, 0):
            break
    action_counts: Counter[str] = Counter(r["action"] for r in rows)
    return {
        "contract_version": AUTOMATION_NOTIFICATIONS_CONTRACT_VERSION,
        "organization_id": organization_id,
        "filters": {
            "actions": sorted(allowed_actions),
            "limit": limit,
        },
        "totals": {
            "total": len(rows),
            "by_action": dict(action_counts),
        },
        "notifications": rows,
    }


def trigger_manual_refresh(
    session: Session,
    *,
    organization_id: str,
    municipality_id: str | None = None,
    submitted_by_user_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue a manual refresh as a queued ingestion_job row.

    Returns the new job's id + the audit-log id created alongside it.
    The Celery worker added in #86 picks the job up; the actual refresh
    body is the published-refresh task from #87.
    """
    request_metadata = dict(parameters or {})
    job = repositories.create_ingestion_job(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        submitted_by_user_id=submitted_by_user_id,
        job_type="manual_refresh",
        status="queued",
        parameters={
            "trigger_kind": "manual_refresh",
            "triggered_at": _iso(datetime.now(tz=timezone.utc)),
            **request_metadata,
        },
    )
    audit = repositories.record_audit_log(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        user_id=submitted_by_user_id,
        action="manual_refresh.triggered",
        target_type="ingestion_job",
        target_id=str(job.id),
        status="recorded",
        metadata={
            "job_type": job.job_type,
            "parameters": request_metadata,
        },
    )
    return {
        "contract_version": AUTOMATION_MANUAL_TRIGGER_CONTRACT_VERSION,
        "organization_id": organization_id,
        "job": _automation_run_row(job),
        "audit_log_id": str(audit.id),
    }


def control_schedule(
    session: Session,
    *,
    organization_id: str,
    schedule_name: str,
    action: str,
    schedule_seconds: float | None = None,
    notification_channels: Iterable[str] | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    action = action.strip().lower()
    if action not in SCHEDULE_CONTROL_ACTIONS:
        raise ValueError(f"Unsupported schedule control action: {action}")
    schedules = list_automation_schedules(session=session, organization_id=organization_id)
    known_names = {entry["name"] for entry in schedules["entries"]}
    if schedule_name not in known_names:
        raise ValueError(f"Unknown automation schedule: {schedule_name}")
    if action == "update" and schedule_seconds is not None and schedule_seconds <= 0:
        raise ValueError("schedule_seconds must be greater than zero.")

    audit_action = {
        "pause": "automation.schedule.paused",
        "resume": "automation.schedule.resumed",
        "update": "automation.schedule.updated",
    }[action]
    metadata = {
        "schedule_name": schedule_name,
        "schedule_seconds": schedule_seconds,
        "notification_channels": list(notification_channels or []),
    }
    audit = repositories.record_audit_log(
        session,
        organization_id=organization_id,
        user_id=actor_user_id,
        action=audit_action,
        target_type="automation_schedule",
        target_id=schedule_name,
        status="recorded",
        metadata=metadata,
    )
    return {
        "contract_version": AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION,
        "organization_id": organization_id,
        "action": action,
        "schedule_name": schedule_name,
        "audit_log_id": str(audit.id),
        "schedules": list_automation_schedules(session=session, organization_id=organization_id),
    }


def _frequency_threshold_seconds(refresh_frequency: str | None) -> int | None:
    if not refresh_frequency:
        return None
    normalized = refresh_frequency.strip().lower()
    if normalized in REFRESH_FREQUENCY_SECONDS:
        return REFRESH_FREQUENCY_SECONDS[normalized]
    if normalized.endswith("h") and normalized[:-1].isdigit():
        return int(normalized[:-1]) * 3_600
    if normalized.endswith("d") and normalized[:-1].isdigit():
        return int(normalized[:-1]) * 86_400
    return None


def _stale_source_row(source: Any, *, now: datetime) -> dict[str, Any] | None:
    threshold = _frequency_threshold_seconds(getattr(source, "refresh_frequency", None))
    if threshold is None:
        return None
    last_refresh_at = getattr(source, "last_refresh_at", None)
    if last_refresh_at is None:
        stale_for_seconds = None
        is_stale = True
    else:
        if last_refresh_at.tzinfo is None:
            last_refresh_at = last_refresh_at.replace(tzinfo=timezone.utc)
        stale_for_seconds = max((now - last_refresh_at.astimezone(timezone.utc)).total_seconds(), 0.0)
        is_stale = stale_for_seconds > threshold
    if not is_stale:
        return None
    return {
        "source_id": str(getattr(source, "id", "")),
        "name": getattr(source, "name", None),
        "source_type": getattr(source, "source_type", None),
        "municipality_id": str(getattr(source, "municipality_id")) if getattr(source, "municipality_id", None) else None,
        "refresh_frequency": getattr(source, "refresh_frequency", None),
        "last_refresh_at": _iso(last_refresh_at),
        "threshold_seconds": threshold,
        "stale_for_seconds": stale_for_seconds,
        "severity": "missing_refresh" if last_refresh_at is None else "stale",
    }


def detect_stale_sources(
    session: Session,
    *,
    organization_id: str,
    now: datetime | None = None,
    record_notifications: bool = True,
) -> dict[str, Any]:
    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    sources = repositories.list_data_sources_for_organization(session, organization_id)
    stale_rows = [
        row
        for source in sources
        if (row := _stale_source_row(source, now=resolved_now)) is not None
    ]
    audit_log_ids: list[str] = []
    if record_notifications:
        for row in stale_rows:
            audit = repositories.record_audit_log(
                session,
                organization_id=organization_id,
                municipality_id=row.get("municipality_id"),
                action="data_source.stale",
                target_type="data_source",
                target_id=row["source_id"],
                status="stale",
                metadata=row,
            )
            audit_log_ids.append(str(audit.id))
    return {
        "contract_version": AUTOMATION_STALE_SOURCES_CONTRACT_VERSION,
        "organization_id": organization_id,
        "generated_at": _iso(resolved_now),
        "totals": {
            "source_count": len(sources),
            "stale_count": len(stale_rows),
        },
        "stale_sources": stale_rows,
        "audit_log_ids": audit_log_ids,
    }


# Application email palette, inlined for the
# HTML notification digest. Kept dependency-free: inline styles + inline SVG,
# with the xROAD wordmark carrying the identity where email clients strip SVG.
_BRAND_ASPHALT = "#101317"
_BRAND_RED_600 = "#FF4B3E"
_BRAND_AMBER = "#FFB400"
_BRAND_IVORY_100 = "#F8F3E9"
_BRAND_IVORY_200 = "#F2E9D8"
_BRAND_INK = "#0B0B0B"
_BRAND_NEUTRAL_500 = "#6F6F6A"
_BRAND_NEUTRAL_200 = "#D9D9D7"
_BRAND_SERIF = "'Libre Baskerville', Baskerville, Georgia, 'Times New Roman', serif"
_BRAND_SANS = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)

# Canonical Signal mark from the active web application.
_BRAND_MARK_SVG = """<svg width="26" height="26" role="img" aria-label="xROAD" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <title>xROAD</title>
  <defs>
    <clipPath id="xroad-plate"><path d="M32 8.5 55.5 32 32 55.5 8.5 32Z"/></clipPath>
    <linearGradient id="xroad-amber" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFC43D"/>
      <stop offset="1" stop-color="#FFA800"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="15" fill="#101317"/>
  <path d="M32 8.5 55.5 32 32 55.5 8.5 32Z" fill="url(#xroad-amber)" stroke="url(#xroad-amber)" stroke-width="5" stroke-linejoin="round"/>
  <g clip-path="url(#xroad-plate)">
    <path d="M16.5 60 29.6 21h4.8L47.5 60Z" fill="#101317"/>
    <path d="M32 52.5v-5.2M32 43.2v-4.1M32 35.5v-3.1M32 29.1v-2.2" stroke="#FFB400" stroke-width="1.9" stroke-linecap="round"/>
  </g>
  <circle cx="32" cy="18.4" r="3.1" fill="#101317"/>
  <circle cx="32" cy="18.4" r="1.2" fill="#FF4B3E"/>
</svg>
"""

_DIGEST_ACTION_LABELS = {
    "published_refresh.completed": "Published refresh completed",
    "published_refresh.failed": "Published refresh failed",
    "published_refresh.triggered": "Published refresh triggered",
    "scheduled_refresh.completed": "Scheduled refresh completed",
    "scheduled_refresh.failed": "Scheduled refresh failed",
    "scheduled_refresh.triggered": "Scheduled refresh triggered",
    "manual_refresh.triggered": "Manual refresh triggered",
    "ingestion_job.failed": "Ingestion job failed",
    "data_source.stale": "Data source stale",
    "data_source.approved": "Data source approved",
    "data_source.blocked": "Data source blocked",
    "automation.schedule.paused": "Schedule paused",
    "automation.schedule.resumed": "Schedule resumed",
    "automation.schedule.updated": "Schedule updated",
    "automation.notification.delivered": "Notification batch delivered",
}


def _digest_action_label(action: str | None) -> str:
    if not action:
        return "Automation event"
    return _DIGEST_ACTION_LABELS.get(action) or action.replace("_", " ").replace(".", " · ").title()


def _digest_accent(action: str | None, status: str | None) -> str:
    text = f"{action or ''} {status or ''}".lower()
    if any(keyword in text for keyword in ("fail", "stale", "block", "error")):
        return _BRAND_RED_600
    if any(keyword in text for keyword in ("approve", "complete", "resume", "deliver")):
        return _BRAND_ASPHALT
    return _BRAND_AMBER


def _digest_subject(rows: list[dict[str, Any]]) -> str:
    count = len(rows)
    if count == 0:
        return "xROAD automation digest — all monitored feeds steady"
    failures = sum(1 for row in rows if _digest_accent(row.get("action"), row.get("status")) == _BRAND_RED_600)
    noun = "notification" if count == 1 else "notifications"
    if failures:
        return f"xROAD automation digest — {count} {noun}, {failures} needing attention"
    return f"xROAD automation digest — {count} {noun}"


def _render_digest_text(organization_id: str, rows: list[dict[str, Any]], generated_at: str | None) -> str:
    lines = [
        "xROAD — Road Accident Risk Modeling",
        "Automation Digest",
        "=" * 34,
        f"Organization: {organization_id}",
        f"Generated:    {generated_at or '—'}",
        "",
    ]
    if not rows:
        lines.append("No automation notifications in this window. All monitored feeds are steady.")
    else:
        for row in rows:
            label = _digest_action_label(row.get("action"))
            detail = " · ".join(
                part
                for part in (row.get("status"), row.get("target_type"), row.get("created_at"))
                if part
            )
            lines.append(f"• {label}" + (f" ({detail})" if detail else ""))
    lines += [
        "",
        "-" * 34,
        "Sent by xROAD automation from your organisation's audit feed.",
    ]
    return "\n".join(lines)


def _render_digest_html(organization_id: str, rows: list[dict[str, Any]], generated_at: str | None) -> str:
    esc = html.escape
    cell = f"padding:12px 16px;border-bottom:1px solid {_BRAND_NEUTRAL_200};font-family:{_BRAND_SANS};"
    meta = f"{cell}font-size:13px;color:{_BRAND_NEUTRAL_500};"
    head = (
        f"padding:8px 16px;font-family:{_BRAND_SANS};font-size:11px;letter-spacing:.06em;"
        f"text-transform:uppercase;color:{_BRAND_NEUTRAL_500};"
    )
    if rows:
        items = []
        for row in rows:
            accent = _digest_accent(row.get("action"), row.get("status"))
            label = esc(_digest_action_label(row.get("action")))
            status = esc(str(row.get("status") or "—"))
            target = esc(" ".join(str(p) for p in (row.get("target_type"), row.get("target_id")) if p) or "—")
            timestamp = esc(str(row.get("created_at") or "—"))
            items.append(
                "<tr>"
                f'<td style="{cell}border-left:3px solid {accent};font-size:14px;color:{_BRAND_INK};">{label}</td>'
                f'<td style="{meta}">{status}</td>'
                f'<td style="{meta}">{target}</td>'
                f'<td style="{meta}white-space:nowrap;">{timestamp}</td>'
                "</tr>"
            )
        body = (
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-collapse:collapse;margin-top:8px;"><thead><tr>'
            f'<th align="left" style="{head}">Event</th>'
            f'<th align="left" style="{head}">Status</th>'
            f'<th align="left" style="{head}">Target</th>'
            f'<th align="left" style="{head}">Time (UTC)</th>'
            f'</tr></thead><tbody>{"".join(items)}</tbody></table>'
        )
    else:
        body = (
            f'<p style="margin:16px 0 0;font-family:{_BRAND_SANS};font-size:14px;color:{_BRAND_NEUTRAL_500};">'
            "No automation notifications in this window. All monitored feeds are steady.</p>"
        )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background:{_BRAND_IVORY_100};">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
        f'style="background:{_BRAND_IVORY_100};padding:24px 0;"><tr><td align="center">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="600" '
        f'style="width:600px;max-width:600px;background:#ffffff;border:1px solid {_BRAND_NEUTRAL_200};">'
        # Letterhead: Signal mark + xROAD wordmark.
        '<tr><td style="padding:24px 24px 16px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="vertical-align:middle;padding-right:12px;">{_BRAND_MARK_SVG}</td>'
        '<td style="vertical-align:middle;">'
        f'<div style="font-family:{_BRAND_SERIF};font-size:20px;font-weight:700;'
        f'color:{_BRAND_ASPHALT};letter-spacing:.02em;">xROAD</div>'
        f'<div style="font-family:{_BRAND_SANS};font-size:11px;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{_BRAND_NEUTRAL_500};">Road Accident Risk Modeling</div>'
        "</td></tr></table></td></tr>"
        # Purple + gold letterhead rule.
        f'<tr><td style="padding:0 24px;"><div style="height:2px;background:{_BRAND_ASPHALT};"></div>'
        f'<div style="height:2px;width:64px;background:{_BRAND_AMBER};"></div></td></tr>'
        # Title + provenance line.
        '<tr><td style="padding:16px 24px 0;">'
        f'<div style="font-family:{_BRAND_SERIF};font-size:18px;color:{_BRAND_INK};">Automation Digest</div>'
        f'<div style="font-family:{_BRAND_SANS};font-size:12px;color:{_BRAND_NEUTRAL_500};margin-top:2px;">'
        f"{esc(organization_id)} · generated {esc(generated_at or '—')}</div></td></tr>"
        f'<tr><td style="padding:8px 24px 24px;">{body}</td></tr>'
        # Footer.
        f'<tr><td style="padding:16px 24px;background:{_BRAND_IVORY_200};'
        f'border-top:1px solid {_BRAND_NEUTRAL_200};font-family:{_BRAND_SANS};'
        f'font-size:11px;color:{_BRAND_NEUTRAL_500};">'
        "Sent by xROAD automation from your organisation's audit feed.</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def render_notification_digest(
    organization_id: str,
    notifications: Iterable[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Render a branded automation digest (subject + HTML + plain text).

    Reuses the Signal mark, application letterhead, and serif
    wordmark from the brand standard so email and webhook deliveries carry the
    same corporate identity as the PDF reports.
    """
    rows = list(notifications)
    generated_iso = _iso(generated_at or datetime.now(timezone.utc))
    return {
        "contract_version": AUTOMATION_NOTIFICATION_DIGEST_CONTRACT_VERSION,
        "subject": _digest_subject(rows),
        "text": _render_digest_text(organization_id, rows, generated_iso),
        "html": _render_digest_html(organization_id, rows, generated_iso),
        "notification_count": len(rows),
        "generated_at": generated_iso,
    }


def deliver_notifications(
    session: Session,
    *,
    organization_id: str,
    actions: Iterable[str] | None = None,
    limit: int = 50,
    email_recipients: Iterable[str] | None = None,
    webhook_url: str | None = None,
    dry_run: bool = True,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    notifications = list_notifications(
        session,
        organization_id=organization_id,
        actions=actions,
        limit=limit,
    )
    rows = notifications["notifications"]
    digest = render_notification_digest(organization_id, rows, generated_at=generated_at)
    channels: list[dict[str, Any]] = []
    recipients = [recipient for recipient in (email_recipients or []) if recipient]
    if recipients:
        channels.append({
            "channel": "email_outbox",
            "recipient_count": len(recipients),
            "subject": digest["subject"],
            "message_formats": ["html", "text"],
            "delivered": not dry_run,
        })
    if webhook_url:
        delivered = False
        if not dry_run:
            if urlparse(webhook_url).scheme not in {"http", "https"}:
                raise ValueError("Webhook URL must use HTTP or HTTPS.")
            payload = json.dumps({
                "organization_id": organization_id,
                "digest": {
                    "subject": digest["subject"],
                    "text": digest["text"],
                    "html": digest["html"],
                },
                "notifications": rows,
            }).encode("utf-8")
            request = urllib_request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib_request.urlopen(request, timeout=10):  # nosec B310 # HTTP(S) scheme checked above
                delivered = True
        channels.append({"channel": "webhook", "configured": True, "delivered": delivered})
    if not channels:
        channels.append({"channel": "audit_feed", "delivered": True})

    audit = repositories.record_audit_log(
        session,
        organization_id=organization_id,
        action="automation.notification.delivered",
        target_type="automation_notification_batch",
        status="dry_run" if dry_run else "delivered",
        metadata={
            "notification_count": len(rows),
            "channels": channels,
            "actions": notifications["filters"]["actions"],
            "digest_subject": digest["subject"],
        },
    )
    return {
        "contract_version": AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION,
        "organization_id": organization_id,
        "dry_run": dry_run,
        "notification_count": len(rows),
        "channels": channels,
        "digest": digest,
        "audit_log_id": str(audit.id),
    }


def build_automation_overview(
    session: Session,
    *,
    organization_id: str,
    paused_entries: Iterable[str] | None = None,
    runs_limit: int = 10,
    notifications_limit: int = 10,
    beat_schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the read-only automation overview for the admin surface."""
    schedules = list_automation_schedules(
        session=session,
        organization_id=organization_id,
        beat_schedule=beat_schedule,
        paused_entries=paused_entries,
    )
    runs = list_automation_runs(
        session, organization_id=organization_id, limit=runs_limit,
    )
    notifications = list_notifications(
        session, organization_id=organization_id, limit=notifications_limit,
    )
    stale_sources = detect_stale_sources(
        session,
        organization_id=organization_id,
        record_notifications=False,
    )
    return {
        "contract_version": AUTOMATION_OVERVIEW_CONTRACT_VERSION,
        "organization_id": organization_id,
        "generated_at": _iso(datetime.now(tz=timezone.utc)),
        "schedules": schedules,
        "runs": {
            "limit": runs_limit,
            "totals": runs["totals"],
            "rows": runs["runs"],
        },
        "notifications": {
            "limit": notifications_limit,
            "totals": notifications["totals"],
            "rows": notifications["notifications"],
        },
        "stale_sources": stale_sources,
    }


__all__ = [
    "AUTOMATION_MANUAL_TRIGGER_CONTRACT_VERSION",
    "AUTOMATION_NOTIFICATIONS_CONTRACT_VERSION",
    "AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION",
    "AUTOMATION_OVERVIEW_CONTRACT_VERSION",
    "AUTOMATION_RUNS_CONTRACT_VERSION",
    "AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION",
    "AUTOMATION_RUN_JOB_TYPES",
    "AUTOMATION_SCHEDULES_CONTRACT_VERSION",
    "AUTOMATION_STALE_SOURCES_CONTRACT_VERSION",
    "NOTIFICATION_AUDIT_ACTIONS",
    "build_automation_overview",
    "control_schedule",
    "deliver_notifications",
    "detect_stale_sources",
    "list_automation_runs",
    "list_automation_schedules",
    "list_notifications",
    "trigger_manual_refresh",
]
