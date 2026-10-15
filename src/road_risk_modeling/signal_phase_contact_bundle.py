"""Build Bari signal-phase contact bundles from scoped requests and outreach tracking."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_CONTACT_BUNDLE_VERSION = "signal_phase_contact_bundle_v1"
SIGNAL_PHASE_CONTACT_BUNDLE_CONTRACT_VERSION = "signal_phase_contact_bundle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _send_readiness(contact_name: str | None, contact_email: str | None) -> str:
    if contact_email and contact_name:
        return "ready_to_send"
    if contact_email:
        return "missing_contact_name"
    return "missing_contact_details"


def _email_subject(target: dict[str, Any]) -> str:
    signal_name = _clean_text(target.get("signal_name")) or "Bari signalized junction"
    junction_id = _clean_text(target.get("junction_id")) or "unknown_junction"
    return f"Data request for {signal_name} ({junction_id}) traffic-signal phase records"


def _delivery_scope_by_profile(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scopes = target.get("delivery_scopes") or []
    return {
        str(scope["profile_id"]): scope
        for scope in scopes
        if isinstance(scope, dict) and _clean_text(scope.get("profile_id")) is not None
    }


def _email_markdown(draft: dict[str, Any]) -> str:
    contact_name = draft["contact_name"] or "recipient"
    lines = [
        f"# Bari Signal-Phase Contact Draft: {draft['request_id']}",
        "",
        "## Envelope",
        "",
        f"- To: `{draft['contact_email'] or 'to_be_filled'}`",
        f"- Contact: `{contact_name}`",
        f"- Subject: `{draft['email_subject']}`",
        f"- Send readiness: `{draft['send_readiness']}`",
        "",
        "## Suggested Email Body",
        "",
        f"Dear {contact_name},",
        "",
        "We are requesting traffic-signal operational data for a priority Bari junction as part of the road-safety analysis workflow.",
        "",
        f"Target junction: `{draft['junction_id']}` `{draft['signal_name']}`",
        f"Priority rank: `{draft['priority_rank']}`",
        f"Signalized crashes linked to this junction: `{draft['matched_signalized_crash_count']}`",
        f"Unresolved movement burden: `{draft['unresolved_signalized_movement_count']}` movements / `{draft['unresolved_signalized_crash_count']}` crashes",
        f"Unresolved coverage: `{draft['unresolved_coverage_pct']}`% movements / `{draft['unresolved_crash_coverage_pct']}`% crashes",
        f"Priority movement hotspot: `{draft['top_hotspot_name']}` (`{draft['top_hotspot_crash_count']}` crashes)",
        "",
        "Primary request:",
        "",
        f"- controller event log export: `{draft['controller_window_request']}`",
        "",
        "If a full extract is not immediately available, the following fallback pilot scope is acceptable for the first delivery:",
        "",
        f"- `{draft['fallback_pilot_scope']}`",
        "",
        "Supporting items requested in the same exchange:",
        "",
        f"- arm-to-phase mapping sheet: `{draft['mapping_scope_request']}`",
        f"- junction phase diagram support: `{draft['diagram_scope_request']}`",
        "",
        "Timing rationale:",
        "",
        f"- recommended time window: `{draft['recommended_time_window']}`",
        f"- preferred focus hour ranges: `{draft['preferred_focus_hour_ranges']}`",
        f"- preferred primary channel: `{draft['preferred_primary_channel'] or 'official_default'}`",
        f"- preferred secondary channel: `{draft['preferred_secondary_channel'] or 'official_default'}`",
        f"- routing decision: `{draft['routing_decision'] or 'default_pec_first'}`",
        f"- external blocker: `{draft['external_blocker'] or 'none_reported'}`",
        "",
        "Please reply with the preferred delivery format or indicate any access constraints.",
        "",
        "Best regards,",
        "",
        "[Name / team to be filled]",
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Contact Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the scoped Bari signal-phase requests have been converted into send-ready contact drafts.",
        "",
        "## Summary",
        "",
        f"- targets: `{payload['summary']['target_count']}`",
        f"- contact drafts: `{payload['summary']['draft_count']}`",
        f"- ready to send: `{payload['summary']['ready_to_send_count']}`",
        f"- missing contact details: `{payload['summary']['missing_contact_details_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across targets: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across targets: `{payload['summary']['unresolved_signalized_crash_total']}`",
        f"- timed signalized crashes across targets: `{payload['summary']['timed_signalized_crash_total']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["send_queue"]:
        blocker_suffix = (
            f", blocker `{row['external_blocker']}`" if _clean_text(row.get("external_blocker")) else ""
        )
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: `{row['send_readiness']}`, "
            f"`{row['preferred_focus_hour_ranges']}`, unresolved crashes `{row['unresolved_signalized_crash_count']}`, "
            f"fallback `{row['fallback_pilot_scope']}`{blocker_suffix}"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_contact_bundle(
    *,
    output_dir: str | Path = "data/planning/signal_phase_contact/bari",
    signal_phase_request_scope_bundle_path: str | Path = "data/reporting/signal_phase_request_scope/bari/signal_phase_request_scope_bundle.json",
    outreach_tracker_path: str | Path = "data/planning/signal_phase_acquisition/bari/outreach_tracker.csv",
    follow_up_days: int = 7,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    draft_dir = output_root / "email_drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)

    scope_bundle_input = Path(signal_phase_request_scope_bundle_path)
    outreach_tracker_input = Path(outreach_tracker_path)

    scope_bundle = _load_json(scope_bundle_input)
    target_rows = scope_bundle.get("targets", [])
    if not isinstance(target_rows, list):
        raise RuntimeError("Signal phase request scope bundle must include a top-level 'targets' list.")

    outreach_rows = _read_csv_rows(outreach_tracker_input)
    outreach_by_request = {
        str(row["request_id"]): row
        for row in outreach_rows
    }

    send_queue_rows: list[dict[str, Any]] = []
    draft_payloads: list[dict[str, Any]] = []
    draft_paths: list[str] = []

    for target in sorted(
        [row for row in target_rows if isinstance(row, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("junction_id") or "")),
    ):
        request_id = str(target["request_id"])
        outreach_row = outreach_by_request.get(request_id, {})
        scope_by_profile = _delivery_scope_by_profile(target)
        controller_scope = scope_by_profile.get("controller_event_log_export", {})
        mapping_scope = scope_by_profile.get("arm_phase_mapping_sheet", {})
        diagram_scope = scope_by_profile.get("junction_phase_diagram_support", {})

        contact_name = _clean_text(outreach_row.get("contact_name"))
        contact_email = _clean_text(outreach_row.get("contact_email"))
        send_readiness = _send_readiness(contact_name, contact_email)
        email_subject = _email_subject(target)
        fallback_pilot_scope = _clean_text(target.get("recommended_pilot_scope"))
        preferred_focus_hour_ranges = _clean_text(target.get("preferred_focus_hour_ranges"))
        recommended_time_window = _clean_text(target.get("recommended_time_window"))
        preferred_primary_channel = _clean_text(outreach_row.get("preferred_primary_channel"))
        preferred_secondary_channel = _clean_text(outreach_row.get("preferred_secondary_channel"))
        routing_decision = _clean_text(outreach_row.get("routing_decision"))
        external_blocker = _clean_text(outreach_row.get("external_blocker"))

        queue_row = {
            "request_id": request_id,
            "junction_id": _clean_text(target.get("junction_id")),
            "signal_name": _clean_text(target.get("signal_name")),
            "priority_rank": _safe_int(target.get("priority_rank")),
            "priority_band": _clean_text(target.get("priority_band")),
            "contact_name": contact_name,
            "contact_email": contact_email,
            "owner_team": _clean_text(outreach_row.get("owner_team")),
            "preferred_primary_channel": preferred_primary_channel,
            "preferred_secondary_channel": preferred_secondary_channel,
            "routing_decision": routing_decision,
            "external_blocker": external_blocker,
            "send_readiness": send_readiness,
            "follow_up_days": int(follow_up_days),
            "email_subject": email_subject,
            "matched_signalized_crash_count": _safe_int(target.get("matched_signalized_crash_count")),
            "timed_signalized_crash_count": _safe_int(target.get("timed_signalized_crash_count")),
            "unresolved_signalized_movement_count": _safe_int(target.get("unresolved_signalized_movement_count")),
            "unresolved_signalized_crash_count": _safe_int(target.get("unresolved_signalized_crash_count")),
            "unresolved_coverage_pct": round(_safe_float(target.get("unresolved_coverage_pct")), 2),
            "unresolved_crash_coverage_pct": round(_safe_float(target.get("unresolved_crash_coverage_pct")), 2),
            "top_hotspot_name": _clean_text(target.get("top_hotspot_name")),
            "top_hotspot_crash_count": _safe_int(target.get("top_hotspot_crash_count")),
            "recommended_time_window": recommended_time_window,
            "preferred_focus_hour_ranges": preferred_focus_hour_ranges,
            "fallback_pilot_scope": fallback_pilot_scope,
            "controller_window_request": _clean_text(controller_scope.get("scoped_requested_window")),
            "mapping_scope_request": _clean_text(mapping_scope.get("scoped_requested_window")),
            "diagram_scope_request": _clean_text(diagram_scope.get("scoped_requested_window")),
        }
        send_queue_rows.append(queue_row)

        draft_payload = dict(queue_row)
        draft_payloads.append(draft_payload)
        draft_md_path = draft_dir / f"{_slugify(request_id)}.md"
        draft_json_path = draft_dir / f"{_slugify(request_id)}.json"
        draft_md_path.write_text(_email_markdown(draft_payload), encoding="utf-8")
        draft_json_path.write_text(json.dumps(draft_payload, indent=2, sort_keys=True), encoding="utf-8")
        draft_paths.extend([str(draft_md_path), str(draft_json_path)])

    send_queue_path = output_root / "contact_send_queue.csv"
    bundle_json_path = output_root / "signal_phase_contact_bundle.json"
    bundle_md_path = output_root / "signal_phase_contact_bundle.md"
    manifest_path = output_root / "signal_phase_contact_bundle.manifest.json"

    _write_csv(
        send_queue_path,
        send_queue_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "contact_name",
            "contact_email",
            "owner_team",
            "preferred_primary_channel",
            "preferred_secondary_channel",
            "routing_decision",
            "external_blocker",
            "send_readiness",
            "follow_up_days",
            "email_subject",
            "matched_signalized_crash_count",
            "timed_signalized_crash_count",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "top_hotspot_name",
            "top_hotspot_crash_count",
            "recommended_time_window",
            "preferred_focus_hour_ranges",
            "fallback_pilot_scope",
            "controller_window_request",
            "mapping_scope_request",
            "diagram_scope_request",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_count": len(send_queue_rows),
        "draft_count": len(draft_payloads),
        "ready_to_send_count": sum(1 for row in send_queue_rows if row["send_readiness"] == "ready_to_send"),
        "missing_contact_details_count": sum(
            1 for row in send_queue_rows if row["send_readiness"] == "missing_contact_details"
        ),
        "external_blocker_count": sum(1 for row in send_queue_rows if _clean_text(row.get("external_blocker"))),
        "targets_with_unresolved_movements": sum(
            1 for row in send_queue_rows if _safe_int(row["unresolved_signalized_movement_count"]) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row["unresolved_signalized_movement_count"]) for row in send_queue_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row["unresolved_signalized_crash_count"]) for row in send_queue_rows
        ),
        "timed_signalized_crash_total": sum(_safe_int(row["timed_signalized_crash_count"]) for row in send_queue_rows),
    }

    bundle_payload = {
        "signal_phase_contact_bundle_version": SIGNAL_PHASE_CONTACT_BUNDLE_VERSION,
        "signal_phase_contact_bundle_contract_version": SIGNAL_PHASE_CONTACT_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "send_queue": send_queue_rows,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_contact_bundle_version": SIGNAL_PHASE_CONTACT_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_contact_bundle",
            "public_contract_version": SIGNAL_PHASE_CONTACT_BUNDLE_CONTRACT_VERSION,
            "signal_phase_contact_bundle_version": SIGNAL_PHASE_CONTACT_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_contact_bundle_builder",
        },
        "inputs": {
            "signal_phase_request_scope_bundle_path": str(scope_bundle_input),
            "outreach_tracker_path": str(outreach_tracker_input),
            "follow_up_days": int(follow_up_days),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "contact_send_queue_path": str(send_queue_path),
            "contact_send_queue_sha256": _sha256(send_queue_path),
            "draft_dir": str(draft_dir),
            "draft_paths": draft_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_request_scope_bundle", scope_bundle_input, _sha256(scope_bundle_input)),
            _artifact_reference("signal_phase_outreach_tracker", outreach_tracker_input, _sha256(outreach_tracker_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_contact_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_contact_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_contact_send_queue", send_queue_path, _sha256(send_queue_path)),
        ]
        + [
            _artifact_reference("signal_phase_contact_draft", Path(path), _sha256(Path(path)))
            for path in draft_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_contact_bundle_version": SIGNAL_PHASE_CONTACT_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
