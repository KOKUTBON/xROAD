"""Admin control-center service.

This service composes a single read-only "control-center" snapshot for
an organization. It is the backing layer for the admin product surfaces
delivered under issue #91:

- governance matrix (data sources and their publication / governance
  posture)
- ingestion job rollup (counts per status, latest activity)
- automations roster (scheduler beat schedule entries the operations
  team relies on)
- user roster (organization memberships and municipality access scope)
- recent audit-log digest
- governed data-source lifecycle writes with audit trails

"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from apps.api.auth import ALL_ROLES, ROLE_ADMIN, ROLE_PUBLIC, ROLE_SUPER_ADMIN
from apps.api.db import repositories


ADMIN_CONTROL_CENTER_CONTRACT_VERSION = "admin_control_center_v1"
ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION = "admin_governance_matrix_v1"
ADMIN_AUTOMATIONS_CONTRACT_VERSION = "admin_automations_v1"
ADMIN_USER_ROSTER_CONTRACT_VERSION = "admin_user_roster_v1"
ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION = "admin_data_source_write_v1"
ADMIN_ACCESS_WRITE_CONTRACT_VERSION = "admin_access_write_v1"

GOVERNANCE_STATUSES = (
    "draft",
    "needs_review",
    "approved",
    "blocked",
    "revoked",
)
PUBLICATION_TIERS = (
    "public",
    "internal",
    "restricted",
)
SOURCE_STATUSES = (
    "active",
    "archived",
)
REFRESH_FREQUENCIES = (
    "manual",
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "event_driven",
)
MEMBERSHIP_ROLES = tuple(role for role in ALL_ROLES if role != ROLE_PUBLIC)
MEMBERSHIP_STATUSES = (
    "active",
    "inactive",
    "suspended",
)
MUNICIPALITY_ACCESS_LEVELS = (
    "restricted",
    "internal",
    "full",
)
MUNICIPALITY_LINK_STATUSES = (
    "active",
    "inactive",
)


class AdminControlError(RuntimeError):
    """Raised when an admin write request cannot be applied safely."""


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _data_source_row(record: Any) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "name": record.name,
        "source_type": record.source_type,
        "provider_name": getattr(record, "provider_name", None),
        "governance_status": record.governance_status,
        "publication_tier": record.publication_tier,
        "refresh_frequency": getattr(record, "refresh_frequency", None),
        "municipality_id": str(record.municipality_id) if getattr(record, "municipality_id", None) else None,
        "status": getattr(record, "status", "active"),
        "created_at": _iso(getattr(record, "created_at", None)),
        "updated_at": _iso(getattr(record, "updated_at", None)),
    }


def _ingestion_job_row(record: Any) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "job_type": record.job_type,
        "status": record.status,
        "source_id": str(record.source_id) if getattr(record, "source_id", None) else None,
        "municipality_id": str(record.municipality_id) if getattr(record, "municipality_id", None) else None,
        "created_at": _iso(getattr(record, "created_at", None)),
        "started_at": _iso(getattr(record, "started_at", None)),
        "finished_at": _iso(getattr(record, "finished_at", None)),
    }


def _audit_row(record: Any) -> dict[str, Any]:
    metadata = getattr(record, "metadata_json", None) or {}
    return {
        "id": str(record.id),
        "event_type": getattr(record, "event_type", None) or getattr(record, "action", None),
        "actor_subject": (
            getattr(record, "actor_subject", None)
            or metadata.get("actor_subject")
            or getattr(record, "user_id", None)
        ),
        "resource_kind": getattr(record, "resource_kind", None) or getattr(record, "target_type", None),
        "resource_id": getattr(record, "resource_id", None) or getattr(record, "target_id", None),
        "created_at": _iso(getattr(record, "created_at", None)),
    }


def _user_row(record: Any) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "subject": getattr(record, "external_subject", None) or getattr(record, "subject", None),
        "email": getattr(record, "email", None),
        "display_name": getattr(record, "display_name", None),
        "status": getattr(record, "status", None),
    }


def _membership_row(record: Any) -> dict[str, Any]:
    user = getattr(record, "user", None)
    return {
        "membership_id": str(record.id),
        "role": record.role,
        "status": record.status,
        "user": _user_row(user) if user else {
            "id": None,
            "subject": None,
            "email": None,
            "display_name": None,
            "status": None,
        },
        "created_at": _iso(getattr(record, "created_at", None)),
    }


def _municipality_link_row(record: Any) -> dict[str, Any]:
    return {
        "link_id": str(record.id),
        "municipality_id": str(record.municipality_id),
        "access_level": record.access_level,
        "status": record.status,
        "created_at": _iso(getattr(record, "created_at", None)),
        "updated_at": _iso(getattr(record, "updated_at", None)),
    }


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AdminControlError(f"{field_name} is required.")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validated_choice(value: Any, field_name: str, allowed: tuple[str, ...]) -> str:
    text = _required_text(value, field_name)
    if text not in allowed:
        raise AdminControlError(
            f"{field_name} must be one of: {', '.join(allowed)}."
        )
    return text


def _validated_optional_choice(
    value: Any,
    field_name: str,
    allowed: tuple[str, ...],
) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if text not in allowed:
        raise AdminControlError(
            f"{field_name} must be one of: {', '.join(allowed)}."
        )
    return text


def _policy_evaluation(row: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    blocks_ingestion = row.get("status") == "archived" or row.get("governance_status") in {
        "blocked",
        "revoked",
    }
    public_review_required = row.get("publication_tier") == "public"

    if row.get("publication_tier") == "public" and row.get("governance_status") != "approved":
        warnings.append(
            "Public publication tier is selected before the source is approved."
        )
    if blocks_ingestion:
        warnings.append(
            "This source is blocked for new ingestion jobs until it is active and governance-approved."
        )
    if row.get("governance_status") == "approved" and row.get("publication_tier") == "public":
        warnings.append(
            "Public artifacts may be refreshed from this source; verify provider rights before publishing."
        )

    return {
        "warnings": warnings,
        "blocks_ingestion": blocks_ingestion,
        "public_artifact_review_required": public_review_required,
    }


def _write_response(
    *,
    operation: str,
    source: Any,
    audit_log: Any,
) -> dict[str, Any]:
    row = _data_source_row(source)
    return {
        "contract_version": ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION,
        "operation": operation,
        "data_source": row,
        "policy_evaluation": _policy_evaluation(row),
        "audit_log_id": str(getattr(audit_log, "id", "")),
    }


def _record_data_source_audit(
    session: Session,
    *,
    organization_id: str,
    source: Any,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    actor_subject: str | None,
    decision_note: str | None = None,
) -> Any:
    changed_fields = sorted(
        key for key in after.keys()
        if before is None or before.get(key) != after.get(key)
    )
    return repositories.record_audit_log(
        session,
        organization_id=organization_id,
        municipality_id=after.get("municipality_id"),
        user_id=None,
        action=action,
        target_type="data_source",
        target_id=str(source.id),
        metadata={
            "actor_subject": actor_subject,
            "before": before,
            "after": after,
            "changed_fields": changed_fields,
            "decision_note": decision_note,
            "policy_evaluation": _policy_evaluation(after),
        },
    )


def _ensure_unique_source_name(
    session: Session,
    *,
    organization_id: str,
    name: str,
    current_source_id: str | None = None,
) -> None:
    existing = repositories.get_data_source_by_name(session, organization_id, name)
    if existing is None:
        return
    if current_source_id is not None and str(existing.id) == str(current_source_id):
        return
    raise AdminControlError(f"Data source name '{name}' already exists for this organization.")


def _is_active_admin_membership(row: dict[str, Any]) -> bool:
    return row.get("status") == "active" and row.get("role") in {ROLE_ADMIN, ROLE_SUPER_ADMIN}


def _active_admin_count(session: Session, organization_id: str) -> int:
    memberships = repositories.list_memberships_for_organization(session, organization_id)
    return sum(1 for membership in memberships if _is_active_admin_membership(_membership_row(membership)))


def _guard_last_admin(
    session: Session,
    *,
    organization_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    if not _is_active_admin_membership(before):
        return
    if _is_active_admin_membership(after):
        return
    if _active_admin_count(session, organization_id) <= 1:
        raise AdminControlError(
            "Cannot remove or deactivate the last active admin membership for this organization."
        )


def _record_access_audit(
    session: Session,
    *,
    organization_id: str,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    actor_subject: str | None,
    decision_note: str | None = None,
    municipality_id: str | None = None,
) -> Any:
    changed_fields = sorted(
        key for key in after.keys()
        if before is None or before.get(key) != after.get(key)
    )
    return repositories.record_audit_log(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        user_id=None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata={
            "actor_subject": actor_subject,
            "before": before,
            "after": after,
            "changed_fields": changed_fields,
            "decision_note": decision_note,
        },
    )


def _access_response(
    *,
    operation: str,
    payload_key: str,
    payload: dict[str, Any],
    audit_log: Any,
) -> dict[str, Any]:
    return {
        "contract_version": ADMIN_ACCESS_WRITE_CONTRACT_VERSION,
        "operation": operation,
        payload_key: payload,
        "audit_log_id": str(getattr(audit_log, "id", "")),
    }


def link_organization_user(
    session: Session,
    *,
    organization_id: str,
    subject: str,
    email: str | None = None,
    display_name: str | None = None,
    role: str = "analyst",
    status: str = "active",
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Link an OIDC user subject to an organization membership."""
    clean_subject = _required_text(subject, "subject")
    clean_role = _validated_choice(role, "role", MEMBERSHIP_ROLES)
    clean_status = _validated_choice(status, "status", MEMBERSHIP_STATUSES)
    user = repositories.upsert_user_by_subject(
        session,
        subject=clean_subject,
        email=_optional_text(email),
        display_name=_optional_text(display_name),
    )
    membership = repositories.get_membership_for_user(
        session,
        organization_id=organization_id,
        user_id=str(user.id),
    )
    before = _membership_row(membership) if membership is not None else None
    if membership is None:
        membership = repositories.add_membership(
            session,
            organization_id=organization_id,
            user_id=str(user.id),
            role=clean_role,
            status=clean_status,
        )
        operation = "linked"
        action = "membership.linked"
    else:
        after_preview = {**before, "role": clean_role, "status": clean_status}
        _guard_last_admin(
            session,
            organization_id=organization_id,
            before=before,
            after=after_preview,
        )
        membership.role = clean_role
        membership.status = clean_status
        session.flush()
        operation = "updated"
        action = "membership.updated"

    after = _membership_row(membership)
    audit = _record_access_audit(
        session,
        organization_id=organization_id,
        action=action,
        target_type="organization_membership",
        target_id=str(membership.id),
        before=before,
        after=after,
        actor_subject=actor_subject,
        decision_note=decision_note,
    )
    return _access_response(
        operation=operation,
        payload_key="membership",
        payload=after,
        audit_log=audit,
    )


def update_membership_access(
    session: Session,
    *,
    organization_id: str,
    membership_id: str,
    role: str | None = None,
    status: str | None = None,
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Update an organization membership role/status with last-admin guardrails."""
    membership = repositories.get_membership(session, membership_id)
    if membership is None or str(membership.organization_id) != str(organization_id):
        raise AdminControlError("Membership not found for this organization.")
    if role is None and status is None:
        raise AdminControlError("At least one membership field must be updated.")

    before = _membership_row(membership)
    next_role = before["role"] if role is None else _validated_choice(role, "role", MEMBERSHIP_ROLES)
    next_status = before["status"] if status is None else _validated_choice(
        status, "status", MEMBERSHIP_STATUSES,
    )
    after_preview = {**before, "role": next_role, "status": next_status}
    _guard_last_admin(
        session,
        organization_id=organization_id,
        before=before,
        after=after_preview,
    )

    membership.role = next_role
    membership.status = next_status
    session.flush()
    after = _membership_row(membership)
    if before == after:
        raise AdminControlError("Membership update did not change role or status.")

    audit = _record_access_audit(
        session,
        organization_id=organization_id,
        action="membership.access_updated",
        target_type="organization_membership",
        target_id=str(membership.id),
        before=before,
        after=after,
        actor_subject=actor_subject,
        decision_note=decision_note,
    )
    return _access_response(
        operation="membership_updated",
        payload_key="membership",
        payload=after,
        audit_log=audit,
    )


def assign_municipality_access(
    session: Session,
    *,
    organization_id: str,
    municipality_id: str,
    access_level: str = "restricted",
    status: str = "active",
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Create or update an organization-to-municipality access link."""
    clean_municipality_id = _required_text(municipality_id, "municipality_id")
    clean_access_level = _validated_choice(
        access_level, "access_level", MUNICIPALITY_ACCESS_LEVELS,
    )
    clean_status = _validated_choice(status, "status", MUNICIPALITY_LINK_STATUSES)
    link = repositories.get_organization_municipality_link(
        session,
        organization_id=organization_id,
        municipality_id=clean_municipality_id,
    )
    before = _municipality_link_row(link) if link is not None else None
    if link is None:
        link = repositories.link_organization_municipality(
            session,
            organization_id=organization_id,
            municipality_id=clean_municipality_id,
            access_level=clean_access_level,
            status=clean_status,
        )
        action = "municipality_access.assigned"
        operation = "municipality_access_assigned"
    else:
        link.access_level = clean_access_level
        link.status = clean_status
        session.flush()
        action = "municipality_access.updated"
        operation = "municipality_access_updated"

    after = _municipality_link_row(link)
    if before == after:
        raise AdminControlError("Municipality access update did not change any field.")
    audit = _record_access_audit(
        session,
        organization_id=organization_id,
        municipality_id=clean_municipality_id,
        action=action,
        target_type="organization_municipality",
        target_id=str(link.id),
        before=before,
        after=after,
        actor_subject=actor_subject,
        decision_note=decision_note,
    )
    return _access_response(
        operation=operation,
        payload_key="municipality_link",
        payload=after,
        audit_log=audit,
    )


def create_governed_data_source(
    session: Session,
    *,
    organization_id: str,
    name: str,
    source_type: str,
    municipality_id: str | None = None,
    provider_name: str | None = None,
    governance_status: str = "draft",
    publication_tier: str = "restricted",
    refresh_frequency: str | None = None,
    configuration: dict[str, Any] | None = None,
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Create a governed data source and record an audit event."""
    clean_name = _required_text(name, "name")
    clean_source_type = _required_text(source_type, "source_type")
    clean_governance = _validated_choice(
        governance_status, "governance_status", GOVERNANCE_STATUSES,
    )
    clean_publication = _validated_choice(
        publication_tier, "publication_tier", PUBLICATION_TIERS,
    )
    clean_refresh = _validated_optional_choice(
        refresh_frequency, "refresh_frequency", REFRESH_FREQUENCIES,
    )
    _ensure_unique_source_name(session, organization_id=organization_id, name=clean_name)

    source = repositories.create_data_source(
        session,
        organization_id=organization_id,
        municipality_id=_optional_text(municipality_id),
        name=clean_name,
        source_type=clean_source_type,
        provider_name=_optional_text(provider_name),
        governance_status=clean_governance,
        publication_tier=clean_publication,
        refresh_frequency=clean_refresh,
        configuration=dict(configuration or {}),
        status="active",
    )
    after = _data_source_row(source)
    audit = _record_data_source_audit(
        session,
        organization_id=organization_id,
        source=source,
        action="data_source.created",
        before=None,
        after=after,
        actor_subject=actor_subject,
        decision_note=decision_note,
    )
    return _write_response(operation="created", source=source, audit_log=audit)


def update_governed_data_source(
    session: Session,
    *,
    organization_id: str,
    source_id: str,
    updates: dict[str, Any],
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Update governance/publication fields for a data source and audit the delta."""
    source = repositories.get_data_source(session, source_id)
    if source is None or str(source.organization_id) != str(organization_id):
        raise AdminControlError("Data source not found for this organization.")
    if not updates:
        raise AdminControlError("At least one data-source field must be updated.")

    allowed_fields = {
        "name",
        "source_type",
        "provider_name",
        "municipality_id",
        "governance_status",
        "publication_tier",
        "refresh_frequency",
        "configuration",
        "status",
    }
    unknown = sorted(set(updates) - allowed_fields)
    if unknown:
        raise AdminControlError(f"Unsupported data-source update fields: {', '.join(unknown)}.")

    before = _data_source_row(source)

    if "name" in updates:
        clean_name = _required_text(updates["name"], "name")
        _ensure_unique_source_name(
            session,
            organization_id=organization_id,
            name=clean_name,
            current_source_id=str(source.id),
        )
        source.name = clean_name
    if "source_type" in updates:
        source.source_type = _required_text(updates["source_type"], "source_type")
    if "provider_name" in updates:
        source.provider_name = _optional_text(updates["provider_name"])
    if "municipality_id" in updates:
        source.municipality_id = _optional_text(updates["municipality_id"])
    if "governance_status" in updates:
        source.governance_status = _validated_choice(
            updates["governance_status"], "governance_status", GOVERNANCE_STATUSES,
        )
    if "publication_tier" in updates:
        source.publication_tier = _validated_choice(
            updates["publication_tier"], "publication_tier", PUBLICATION_TIERS,
        )
    if "refresh_frequency" in updates:
        source.refresh_frequency = _validated_optional_choice(
            updates["refresh_frequency"], "refresh_frequency", REFRESH_FREQUENCIES,
        )
    if "configuration" in updates:
        configuration = updates["configuration"]
        if configuration is not None and not isinstance(configuration, dict):
            raise AdminControlError("configuration must be an object when provided.")
        source.configuration_json = dict(configuration or {})
    if "status" in updates:
        source.status = _validated_choice(updates["status"], "status", SOURCE_STATUSES)

    session.flush()
    after = _data_source_row(source)
    if before == after:
        raise AdminControlError("Data-source update did not change any governed field.")

    action = "data_source.updated"
    if before.get("status") != "archived" and after.get("status") == "archived":
        action = "data_source.archived"
    elif (
        before.get("governance_status") != after.get("governance_status")
        or before.get("publication_tier") != after.get("publication_tier")
        or before.get("refresh_frequency") != after.get("refresh_frequency")
    ):
        action = "data_source.policy_updated"

    audit = _record_data_source_audit(
        session,
        organization_id=organization_id,
        source=source,
        action=action,
        before=before,
        after=after,
        actor_subject=actor_subject,
        decision_note=decision_note,
    )
    operation = action.replace("data_source.", "")
    return _write_response(operation=operation, source=source, audit_log=audit)


def archive_governed_data_source(
    session: Session,
    *,
    organization_id: str,
    source_id: str,
    actor_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Archive a data source through the same audited write path."""
    return update_governed_data_source(
        session,
        organization_id=organization_id,
        source_id=source_id,
        updates={"status": "archived"},
        actor_subject=actor_subject,
        decision_note=decision_note,
    )


def build_governance_matrix(
    session: Session,
    *,
    organization_id: str,
) -> dict[str, Any]:
    """Compose the governance matrix for an organization.

    The matrix groups every operational data source by governance status
    and publication tier so the admin surface can render a single table
    of "what is approved, what is restricted, what is still draft".
    """
    sources = repositories.list_data_sources_for_organization(session, organization_id)
    rows = [_data_source_row(s) for s in sources]
    status_counts: Counter[str] = Counter(r["governance_status"] for r in rows)
    tier_counts: Counter[str] = Counter(r["publication_tier"] for r in rows)
    return {
        "contract_version": ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION,
        "organization_id": organization_id,
        "totals": {
            "data_source_count": len(rows),
            "by_governance_status": dict(status_counts),
            "by_publication_tier": dict(tier_counts),
        },
        "rows": rows,
    }


def build_user_roster(
    session: Session,
    *,
    organization_id: str,
) -> dict[str, Any]:
    """Compose the user roster for an organization.

    Returns the active organization memberships joined with the user
    record. Municipality access scope is included as a separate
    `municipality_links` block because the admin surface needs to render
    them side by side.
    """
    memberships = repositories.list_memberships_for_organization(session, organization_id)
    rows = [_membership_row(m) for m in memberships]
    role_counts: Counter[str] = Counter(r["role"] for r in rows)
    status_counts: Counter[str] = Counter(r["status"] for r in rows)
    links = repositories.list_municipality_links_for_organization(session, organization_id)
    municipality_links = [_municipality_link_row(link) for link in links]
    return {
        "contract_version": ADMIN_USER_ROSTER_CONTRACT_VERSION,
        "organization_id": organization_id,
        "totals": {
            "membership_count": len(rows),
            "by_role": dict(role_counts),
            "by_status": dict(status_counts),
            "municipality_link_count": len(municipality_links),
        },
        "memberships": rows,
        "municipality_links": municipality_links,
    }


def build_automations_roster(
    *,
    organization_id: str,
    beat_schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the automations roster.

    The schedule snapshot is rendered from the live beat schedule when
    available (services.scheduler.beat_schedule.build_beat_schedule()).
    When the scheduler package is not installed (for example, in the
    API-only image), an empty roster is returned with an explicit note.
    """
    if beat_schedule is None:
        try:
            from services.scheduler.beat_schedule import build_beat_schedule

            beat_schedule = build_beat_schedule()
        except ImportError:
            beat_schedule = None

    entries: list[dict[str, Any]] = []
    if beat_schedule:
        for name, entry in beat_schedule.items():
            schedule_value = entry.get("schedule")
            schedule_repr: Any
            if isinstance(schedule_value, (int, float)):
                schedule_repr = {"kind": "interval_seconds", "value": float(schedule_value)}
            else:
                schedule_repr = {"kind": "celery_schedule", "value": repr(schedule_value)}
            entries.append(
                {
                    "name": name,
                    "task": entry.get("task"),
                    "schedule": schedule_repr,
                    "options": dict(entry.get("options") or {}),
                }
            )
    return {
        "contract_version": ADMIN_AUTOMATIONS_CONTRACT_VERSION,
        "organization_id": organization_id,
        "scheduler_available": beat_schedule is not None,
        "entries": entries,
        "entry_count": len(entries),
    }


def build_admin_control_center(
    session: Session,
    *,
    organization_id: str,
    recent_audit_limit: int = 25,
    recent_jobs_limit: int = 25,
    beat_schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the full admin control-center bundle.

    Returns the four sub-bundles plus an `ingestion_overview` rollup so
    the admin surface can render headline counts without paging through
    every ingestion job.
    """
    governance = build_governance_matrix(session, organization_id=organization_id)
    users = build_user_roster(session, organization_id=organization_id)
    automations = build_automations_roster(
        organization_id=organization_id,
        beat_schedule=beat_schedule,
    )

    jobs = repositories.list_ingestion_jobs_for_organization(session, organization_id)
    job_rows = [_ingestion_job_row(job) for job in jobs]
    job_status_counts: Counter[str] = Counter(row["status"] for row in job_rows)
    recent_jobs = sorted(
        job_rows,
        key=lambda row: row.get("created_at") or "",
        reverse=True,
    )[:recent_jobs_limit]

    audit = repositories.list_audit_logs_for_organization(session, organization_id)
    audit_rows = sorted(
        (_audit_row(entry) for entry in audit),
        key=lambda row: row.get("created_at") or "",
        reverse=True,
    )[:recent_audit_limit]

    artifacts = repositories.list_artifact_references_for_organization(session, organization_id)
    artifact_counts: Counter[str] = Counter(
        getattr(item, "publication_tier", None) or "unspecified" for item in artifacts
    )
    artifact_overview = {
        "total": len(artifacts),
        "by_publication_tier": dict(artifact_counts),
    }

    return {
        "contract_version": ADMIN_CONTROL_CENTER_CONTRACT_VERSION,
        "organization_id": organization_id,
        "generated_at": _iso(datetime.now(tz=timezone.utc)),
        "ingestion_overview": {
            "total": len(job_rows),
            "by_status": dict(job_status_counts),
            "recent_jobs": recent_jobs,
        },
        "artifact_overview": artifact_overview,
        "governance_matrix": governance,
        "automations": automations,
        "user_roster": users,
        "recent_audit": {
            "limit": recent_audit_limit,
            "entries": audit_rows,
        },
    }


__all__ = [
    "ADMIN_ACCESS_WRITE_CONTRACT_VERSION",
    "ADMIN_AUTOMATIONS_CONTRACT_VERSION",
    "ADMIN_CONTROL_CENTER_CONTRACT_VERSION",
    "ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION",
    "ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION",
    "ADMIN_USER_ROSTER_CONTRACT_VERSION",
    "AdminControlError",
    "GOVERNANCE_STATUSES",
    "MEMBERSHIP_ROLES",
    "MEMBERSHIP_STATUSES",
    "MUNICIPALITY_ACCESS_LEVELS",
    "MUNICIPALITY_LINK_STATUSES",
    "PUBLICATION_TIERS",
    "REFRESH_FREQUENCIES",
    "SOURCE_STATUSES",
    "archive_governed_data_source",
    "assign_municipality_access",
    "build_admin_control_center",
    "build_automations_roster",
    "build_governance_matrix",
    "build_user_roster",
    "create_governed_data_source",
    "link_organization_user",
    "update_membership_access",
    "update_governed_data_source",
]
