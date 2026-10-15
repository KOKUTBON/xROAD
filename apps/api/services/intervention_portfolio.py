"""Managed municipal intervention portfolio service."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.db import repositories
from apps.api.services import scenario_planner
from apps.api.settings import ApiSettings


INTERVENTION_PORTFOLIO_CONTRACT_VERSION = "intervention_portfolio_v1"
INTERVENTION_PORTFOLIO_WRITE_CONTRACT_VERSION = "intervention_portfolio_write_v1"
INTERVENTION_PORTFOLIO_EXPORT_CONTRACT_VERSION = "intervention_portfolio_export_v1"

PORTFOLIO_STATUSES = (
    "candidate",
    "shortlisted",
    "planned",
    "in_progress",
    "completed",
    "deferred",
    "rejected",
    "removed",
)
COST_CLASSES = ("low", "medium", "high", "capital")
COST_CLASS_WEIGHTS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 4.0,
    "capital": 8.0,
}


class InterventionPortfolioError(RuntimeError):
    """Raised when intervention portfolio state cannot be applied."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise InterventionPortfolioError(f"{field_name} is required.")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validated_choice(value: Any, field_name: str, allowed: tuple[str, ...]) -> str:
    text = _required_text(value, field_name)
    if text not in allowed:
        raise InterventionPortfolioError(f"{field_name} must be one of: {', '.join(allowed)}.")
    return text


def _validated_optional_choice(value: Any, field_name: str, allowed: tuple[str, ...]) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if text not in allowed:
        raise InterventionPortfolioError(f"{field_name} must be one of: {', '.join(allowed)}.")
    return text


def _coerce_float(value: Any, *, field_name: str, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InterventionPortfolioError(f"{field_name} must be numeric.") from exc


def _parse_date(value: Any, field_name: str) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise InterventionPortfolioError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _priority_score(expected_benefit: float | None, cost_class: str | None) -> float | None:
    if expected_benefit is None:
        return None
    weight = COST_CLASS_WEIGHTS.get(cost_class or "medium", COST_CLASS_WEIGHTS["medium"])
    return round(float(expected_benefit) / weight, 4)


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row.get("status") or "unknown" for row in rows))


def _monitoring_placeholder(record: Any) -> dict[str, Any]:
    properties = dict(getattr(record, "properties_json", None) or {})
    before_after = dict(properties.get("before_after") or {})
    monitoring = dict(properties.get("monitoring") or {})
    completed_at = getattr(record, "completed_at", None)
    return {
        "status": "awaiting_after_data" if completed_at and not monitoring.get("after_observed_crashes") else "not_started",
        "baseline_predicted_crashes": before_after.get("baseline_predicted_crash_total"),
        "expected_crash_reduction": before_after.get("expected_crash_reduction"),
        "after_observed_crashes": monitoring.get("after_observed_crashes"),
        "monitoring_period": monitoring.get("monitoring_period"),
        "completed_at": _iso(completed_at),
    }


def _row(record: Any) -> dict[str, Any]:
    properties = dict(getattr(record, "properties_json", None) or {})
    return {
        "intervention_id": str(getattr(record, "id", "")),
        "organization_id": str(getattr(record, "organization_id", "")),
        "municipality_id": str(getattr(record, "municipality_id", "")) if getattr(record, "municipality_id", None) else None,
        "city_key": properties.get("city_key"),
        "scenario_run_id": properties.get("scenario_workspace_run_id")
        or (str(getattr(record, "scenario_run_id")) if getattr(record, "scenario_run_id", None) else None),
        "target_object_type": getattr(record, "target_object_type", None),
        "target_object_id": getattr(record, "target_object_id", None),
        "target_label": properties.get("target_label"),
        "intervention_type": getattr(record, "intervention_type", None),
        "cost_class": getattr(record, "cost_class", None),
        "expected_benefit": float(getattr(record, "expected_benefit")) if getattr(record, "expected_benefit", None) is not None else None,
        "priority_score": float(getattr(record, "priority_score")) if getattr(record, "priority_score", None) is not None else None,
        "status": getattr(record, "status", None),
        "owner_subject": getattr(record, "owner_subject", None),
        "planned_start_date": _iso(getattr(record, "planned_start_date", None)),
        "planned_completion_date": _iso(getattr(record, "planned_completion_date", None)),
        "completed_at": _iso(getattr(record, "completed_at", None)),
        "notes": getattr(record, "notes", None),
        "source_kind": getattr(record, "source_kind", None),
        "properties": properties,
        "monitoring": _monitoring_placeholder(record),
        "created_at": _iso(getattr(record, "created_at", None)),
        "updated_at": _iso(getattr(record, "updated_at", None)),
    }


def _filter_rows(rows: list[dict[str, Any]], *, city_key: str | None = None) -> list[dict[str, Any]]:
    if city_key:
        rows = [row for row in rows if row.get("city_key") in {None, city_key}]
    return rows


def build_portfolio(
    session: Session,
    *,
    organization_id: str,
    city_key: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return ranked organization-scoped intervention portfolio rows."""
    if status is not None:
        status = _validated_choice(status, "status", PORTFOLIO_STATUSES)
    try:
        records = repositories.list_interventions_for_organization(
            session,
            organization_id,
            status=status,
            limit=limit,
        )
        availability = "available"
        unavailable_reason = None
    except (SQLAlchemyError, AttributeError):
        records = []
        availability = "degraded"
        unavailable_reason = "database_unavailable"
    rows = _filter_rows([_row(record) for record in records], city_key=city_key)
    rows = sorted(
        rows,
        key=lambda row: (
            float(row.get("priority_score") or 0.0),
            float(row.get("expected_benefit") or 0.0),
        ),
        reverse=True,
    )[:limit]
    total_expected_benefit = round(sum(float(row.get("expected_benefit") or 0.0) for row in rows), 4)
    return {
        "contract_version": INTERVENTION_PORTFOLIO_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "availability": availability,
        "unavailable_reason": unavailable_reason,
        "totals": {
            "portfolio_count": len(rows),
            "expected_benefit": total_expected_benefit,
            "by_status": _status_counts(rows),
        },
        "rows": rows,
    }


def _scenario_run_candidate(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_run_id: str,
) -> dict[str, Any]:
    run = scenario_planner.get_scenario_run(
        settings,
        organization_id=organization_id,
        scenario_run_id=scenario_run_id,
    )["run"]
    target = dict(run.get("target") or {})
    before_after = dict(run.get("before_after") or {})
    target_label = target.get("target_context_label") or run.get("name") or scenario_run_id
    target_object_id = target.get("target_context_key") or target_label or scenario_run_id
    expected_benefit = _coerce_float(
        before_after.get("expected_crash_reduction"),
        field_name="scenario_run.expected_crash_reduction",
        default=0.0,
    )
    cost_class = _optional_text(run.get("cost_class")) or "medium"
    return {
        "city_key": run.get("city_key"),
        "target_object_type": "scenario_target",
        "target_object_id": target_object_id,
        "target_label": target_label,
        "intervention_type": run.get("intervention_code"),
        "cost_class": cost_class,
        "expected_benefit": expected_benefit,
        "priority_score": _priority_score(expected_benefit, cost_class),
        "source_kind": "scenario_run",
        "properties": {
            "scenario_workspace_run_id": scenario_run_id,
            "scenario_name": run.get("name"),
            "city_key": run.get("city_key"),
            "target_label": target_label,
            "before_after": before_after,
            "confidence": run.get("confidence"),
            "assumptions": list(run.get("assumptions") or []),
        },
    }


def create_portfolio_item(
    session: Session,
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str | None = None,
    target_object_type: str | None = None,
    target_object_id: str | None = None,
    intervention_type: str | None = None,
    cost_class: str | None = None,
    expected_benefit: float | None = None,
    priority_score: float | None = None,
    status: str = "candidate",
    owner_subject: str | None = None,
    planned_start_date: str | None = None,
    planned_completion_date: str | None = None,
    notes: str | None = None,
    scenario_run_id: str | None = None,
    actor_subject: str | None = None,
) -> dict[str, Any]:
    """Create a portfolio item manually or from a scenario run."""
    candidate: dict[str, Any] = {}
    if scenario_run_id:
        candidate.update(
            _scenario_run_candidate(
                settings,
                organization_id=organization_id,
                scenario_run_id=scenario_run_id,
            )
        )
    candidate_city_key = _optional_text(city_key) or candidate.get("city_key")
    resolved_target_object_type = _required_text(target_object_type or candidate.get("target_object_type"), "target_object_type")
    resolved_target_object_id = _required_text(target_object_id or candidate.get("target_object_id"), "target_object_id")
    resolved_intervention_type = _required_text(intervention_type or candidate.get("intervention_type"), "intervention_type")
    resolved_cost_class = _validated_optional_choice(cost_class or candidate.get("cost_class"), "cost_class", COST_CLASSES) or "medium"
    resolved_expected_benefit = _coerce_float(
        expected_benefit if expected_benefit is not None else candidate.get("expected_benefit"),
        field_name="expected_benefit",
        default=0.0,
    )
    resolved_priority_score = _coerce_float(
        priority_score if priority_score is not None else candidate.get("priority_score"),
        field_name="priority_score",
        default=_priority_score(resolved_expected_benefit, resolved_cost_class),
    )
    resolved_status = _validated_choice(status, "status", PORTFOLIO_STATUSES)
    properties = dict(candidate.get("properties") or {})
    properties.update(
        {
            "city_key": candidate_city_key,
            "target_label": properties.get("target_label") or resolved_target_object_id,
            "portfolio_contract_version": INTERVENTION_PORTFOLIO_CONTRACT_VERSION,
        }
    )
    if notes:
        properties["initial_note"] = notes

    record = repositories.create_intervention(
        session,
        organization_id=organization_id,
        target_object_type=resolved_target_object_type,
        target_object_id=resolved_target_object_id,
        intervention_type=resolved_intervention_type,
        cost_class=resolved_cost_class,
        expected_benefit=resolved_expected_benefit,
        priority_score=resolved_priority_score,
        status=resolved_status,
        owner_subject=_optional_text(owner_subject),
        planned_start_date=_parse_date(planned_start_date, "planned_start_date"),
        planned_completion_date=_parse_date(planned_completion_date, "planned_completion_date"),
        notes=_optional_text(notes),
        source_kind="scenario_run" if scenario_run_id else "manual",
        properties=properties,
    )
    repositories.record_audit_log(
        session,
        organization_id=organization_id,
        action="intervention_portfolio.created",
        target_type="intervention",
        target_id=str(record.id),
        status=resolved_status,
        metadata={
            "actor_subject": actor_subject,
            "city_key": candidate_city_key,
            "scenario_run_id": scenario_run_id,
            "expected_benefit": resolved_expected_benefit,
            "priority_score": resolved_priority_score,
        },
    )
    return {
        "contract_version": INTERVENTION_PORTFOLIO_WRITE_CONTRACT_VERSION,
        "operation": "created",
        "portfolio_item": _row(record),
    }


def update_portfolio_item(
    session: Session,
    *,
    organization_id: str,
    intervention_id: str,
    updates: dict[str, Any],
    actor_subject: str | None = None,
) -> dict[str, Any]:
    """Update portfolio status, owner, dates, cost, benefit, or notes."""
    record = repositories.get_intervention(session, intervention_id)
    if record is None or str(getattr(record, "organization_id", "")) != organization_id:
        raise InterventionPortfolioError("Intervention portfolio item not found.")

    before = _row(record)
    status = _validated_optional_choice(updates.get("status"), "status", PORTFOLIO_STATUSES)
    cost_class = _validated_optional_choice(updates.get("cost_class"), "cost_class", COST_CLASSES)
    expected_benefit = _coerce_float(updates.get("expected_benefit"), field_name="expected_benefit") if "expected_benefit" in updates else None
    priority_score = _coerce_float(updates.get("priority_score"), field_name="priority_score") if "priority_score" in updates else None
    if priority_score is None and (expected_benefit is not None or cost_class is not None):
        priority_score = _priority_score(
            expected_benefit if expected_benefit is not None else before.get("expected_benefit"),
            cost_class if cost_class is not None else before.get("cost_class"),
        )
    completed_at = _utc_now() if status == "completed" and getattr(record, "completed_at", None) is None else None
    monitoring: dict[str, Any] = {}
    if "after_observed_crashes" in updates:
        monitoring["after_observed_crashes"] = _coerce_float(updates.get("after_observed_crashes"), field_name="after_observed_crashes")
    if "monitoring_period" in updates:
        monitoring["monitoring_period"] = _optional_text(updates.get("monitoring_period"))

    repositories.update_intervention(
        session,
        record,
        status=status,
        owner_subject=_optional_text(updates.get("owner_subject")) if "owner_subject" in updates else None,
        planned_start_date=_parse_date(updates.get("planned_start_date"), "planned_start_date") if "planned_start_date" in updates else None,
        planned_completion_date=_parse_date(updates.get("planned_completion_date"), "planned_completion_date") if "planned_completion_date" in updates else None,
        completed_at=completed_at,
        notes=_optional_text(updates.get("notes")) if "notes" in updates else None,
        cost_class=cost_class,
        expected_benefit=expected_benefit,
        priority_score=priority_score,
        properties={"monitoring": monitoring} if monitoring else None,
    )
    after = _row(record)
    changed_fields = sorted(
        key for key in after
        if key in before and before.get(key) != after.get(key)
    )
    repositories.record_audit_log(
        session,
        organization_id=organization_id,
        action="intervention_portfolio.updated",
        target_type="intervention",
        target_id=str(record.id),
        status=str(after.get("status") or "updated"),
        metadata={
            "actor_subject": actor_subject,
            "changed_fields": changed_fields,
            "before": {key: before.get(key) for key in changed_fields},
            "after": {key: after.get(key) for key in changed_fields},
        },
    )
    return {
        "contract_version": INTERVENTION_PORTFOLIO_WRITE_CONTRACT_VERSION,
        "operation": "updated",
        "portfolio_item": after,
    }


def remove_portfolio_item(
    session: Session,
    *,
    organization_id: str,
    intervention_id: str,
    actor_subject: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result = update_portfolio_item(
        session,
        organization_id=organization_id,
        intervention_id=intervention_id,
        updates={"status": "removed", "notes": reason},
        actor_subject=actor_subject,
    )
    repositories.record_audit_log(
        session,
        organization_id=organization_id,
        action="intervention_portfolio.removed",
        target_type="intervention",
        target_id=intervention_id,
        status="removed",
        metadata={"actor_subject": actor_subject, "reason": reason},
    )
    result["operation"] = "removed"
    return result


def build_portfolio_export(
    session: Session,
    *,
    organization_id: str,
    city_key: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    portfolio = build_portfolio(
        session,
        organization_id=organization_id,
        city_key=city_key,
        status=status,
        limit=limit,
    )
    export_rows = [
        {
            "priority_rank": index,
            "intervention_id": row["intervention_id"],
            "city_key": row.get("city_key"),
            "target": row.get("target_label") or row.get("target_object_id"),
            "intervention_type": row.get("intervention_type"),
            "status": row.get("status"),
            "owner_subject": row.get("owner_subject"),
            "cost_class": row.get("cost_class"),
            "expected_benefit": row.get("expected_benefit"),
            "priority_score": row.get("priority_score"),
            "planned_completion_date": row.get("planned_completion_date"),
            "completed_at": row.get("completed_at"),
            "notes": row.get("notes"),
        }
        for index, row in enumerate(portfolio["rows"], start=1)
    ]
    return {
        "contract_version": INTERVENTION_PORTFOLIO_EXPORT_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "availability": portfolio["availability"],
        "unavailable_reason": portfolio["unavailable_reason"],
        "summary": portfolio["totals"],
        "rows": export_rows,
    }


__all__ = [
    "COST_CLASSES",
    "INTERVENTION_PORTFOLIO_CONTRACT_VERSION",
    "INTERVENTION_PORTFOLIO_EXPORT_CONTRACT_VERSION",
    "INTERVENTION_PORTFOLIO_WRITE_CONTRACT_VERSION",
    "InterventionPortfolioError",
    "PORTFOLIO_STATUSES",
    "build_portfolio",
    "build_portfolio_export",
    "create_portfolio_item",
    "remove_portfolio_item",
    "update_portfolio_item",
]
