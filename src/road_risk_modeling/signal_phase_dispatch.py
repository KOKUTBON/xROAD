"""Build Bari signal-phase dispatch bundles from contact-resolution artifacts."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_BUNDLE_VERSION = "signal_phase_dispatch_bundle_v1"
SIGNAL_PHASE_DISPATCH_BUNDLE_CONTRACT_VERSION = "signal_phase_dispatch_bundle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _parse_planned_date(value: str | None) -> date:
    if value is None:
        return datetime.now().date()
    return date.fromisoformat(value)


def _channel_by_role(official_channels: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
    for channel in official_channels:
        if _clean_text(channel.get("channel_role")) == role:
            return channel
    return None


def _dispatch_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Dispatch Packet: {packet['request_id']}",
        "",
        "## Envelope",
        "",
        f"- Dispatch reference: `{packet['dispatch_reference']}`",
        f"- Planned dispatch date: `{packet['planned_dispatch_date']}`",
        f"- To: `{packet['primary_channel_value']}`",
        f"- CC: `{packet['secondary_channel_value']}`",
        f"- General email fallback: `{packet['general_email_value']}`",
        f"- Phone escalation: `{packet['phone_escalation_value']}`",
        f"- Subject: `{packet['email_subject']}`",
        "",
        "## Request Context",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Priority rank: `{packet['priority_rank']}`",
        f"- Recommended time window: `{packet['recommended_time_window']}`",
        f"- Preferred focus hours: `{packet['preferred_focus_hour_ranges']}`",
        f"- Fallback pilot scope: `{packet['fallback_pilot_scope']}`",
        f"- Routing decision: `{packet['routing_decision'] or 'default_pec_first'}`",
        f"- External blocker: `{packet['external_blocker'] or 'none_reported'}`",
        f"- Unresolved movement burden: `{packet['unresolved_signalized_movement_count']}` movements / `{packet['unresolved_signalized_crash_count']}` crashes",
        f"- Unresolved coverage: `{packet['unresolved_coverage_pct']}`% movements / `{packet['unresolved_crash_coverage_pct']}`% crashes",
        "",
        "## Recommended Message",
        "",
        f"Please provide the requested signal-phase material for `{packet['signal_name']}` (`{packet['junction_id']}`).",
        f"The highest-yield crash window is `{packet['recommended_time_window']}`, with focus hours `{packet['preferred_focus_hour_ranges']}`.",
        f"If a full extract is not immediately available, the fallback pilot scope is `{packet['fallback_pilot_scope']}`.",
        f"This request currently carries unresolved burden of `{packet['unresolved_signalized_movement_count']}` movements and `{packet['unresolved_signalized_crash_count']}` crashes.",
        "",
        "## Follow-up Plan",
        "",
        f"- First follow-up due: `{packet['first_follow_up_date']}`",
        f"- Escalation due: `{packet['escalation_date']}`",
        f"- Follow-up action: `{packet['follow_up_action']}`",
        "",
        "## Evidence To Record After Send",
        "",
        "- sent timestamp",
        "- sent message copy or PEC receipt",
        "- any acknowledgement or routing reply",
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari contact-resolution queue has been converted into a dispatch tracker.",
        "",
        "## Summary",
        "",
        f"- targets: `{payload['summary']['target_count']}`",
        f"- dispatch queue rows: `{payload['summary']['dispatch_queue_count']}`",
        f"- follow-up items: `{payload['summary']['follow_up_item_count']}`",
        f"- primary PEC rows: `{payload['summary']['primary_pec_count']}`",
        f"- direct named contacts: `{payload['summary']['direct_contact_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across targets: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across targets: `{payload['summary']['unresolved_signalized_crash_total']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["dispatch_queue"]:
        blocker_suffix = (
            f", blocker `{row['external_blocker']}`" if _clean_text(row.get("external_blocker")) else ""
        )
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: send `{row['planned_dispatch_date']}`, "
            f"follow up `{row['first_follow_up_date']}`, escalate `{row['escalation_date']}`, "
            f"unresolved crashes `{row['unresolved_signalized_crash_count']}`{blocker_suffix}"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_bundle(
    *,
    output_dir: str | Path = "data/planning/signal_phase_dispatch/bari",
    signal_phase_contact_resolution_bundle_path: str | Path = "data/planning/signal_phase_contact_resolution/bari/signal_phase_contact_resolution_bundle.json",
    planned_dispatch_date: str | None = None,
    follow_up_days: int = 7,
    escalation_days: int = 14,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "dispatch_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    resolution_bundle_input = Path(signal_phase_contact_resolution_bundle_path)
    resolution_payload = _load_json(resolution_bundle_input)
    resolution_queue = resolution_payload.get("resolution_queue", [])
    official_channels = resolution_payload.get("official_channels", [])
    if not isinstance(resolution_queue, list):
        raise RuntimeError("Signal phase contact-resolution bundle must include a top-level 'resolution_queue' list.")
    if not isinstance(official_channels, list):
        raise RuntimeError("Signal phase contact-resolution bundle must include a top-level 'official_channels' list.")

    planned_date = _parse_planned_date(planned_dispatch_date)
    first_follow_up_date = planned_date + timedelta(days=int(follow_up_days))
    escalation_date = planned_date + timedelta(days=int(escalation_days))

    general_email = _channel_by_role(official_channels, "general_email")
    public_relations = _channel_by_role(official_channels, "public_relations")

    dispatch_rows: list[dict[str, Any]] = []
    follow_up_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for index, row in enumerate(
        sorted(
            [item for item in resolution_queue if isinstance(item, dict)],
            key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("junction_id") or "")),
        ),
        start=1,
    ):
        request_id = str(row["request_id"])
        dispatch_reference = f"BARI-SPD-{planned_date.strftime('%Y%m%d')}-{index:02d}"
        dispatch_row = {
            "dispatch_reference": dispatch_reference,
            "request_id": request_id,
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "priority_rank": _safe_int(row.get("priority_rank")),
            "priority_band": _clean_text(row.get("priority_band")),
            "dispatch_status": "pending_dispatch",
            "planned_dispatch_date": planned_date.isoformat(),
            "first_follow_up_date": first_follow_up_date.isoformat(),
            "escalation_date": escalation_date.isoformat(),
            "send_channel_strategy": "primary_pec_with_secondary_pec_cc",
            "primary_channel_type": _clean_text(row.get("primary_channel_type")),
            "primary_channel_value": _clean_text(row.get("primary_channel_value")),
            "secondary_channel_type": _clean_text(row.get("secondary_channel_type")),
            "secondary_channel_value": _clean_text(row.get("secondary_channel_value")),
            "general_email_value": _clean_text(general_email.get("channel_value")) if general_email else None,
            "phone_escalation_type": _clean_text(row.get("phone_escalation_type")),
            "phone_escalation_value": _clean_text(row.get("phone_escalation_value")),
            "public_relations_value": _clean_text(public_relations.get("channel_value")) if public_relations else None,
            "contact_name": _clean_text(row.get("contact_name")),
            "contact_email": _clean_text(row.get("contact_email")),
            "email_subject": _clean_text(row.get("email_subject")),
            "recommended_time_window": _clean_text(row.get("recommended_time_window")),
            "preferred_focus_hour_ranges": _clean_text(row.get("preferred_focus_hour_ranges")),
            "fallback_pilot_scope": _clean_text(row.get("fallback_pilot_scope")),
            "routing_decision": _clean_text(row.get("routing_decision")),
            "external_blocker": _clean_text(row.get("external_blocker")),
            "unresolved_signalized_movement_count": _safe_int(row.get("unresolved_signalized_movement_count")),
            "unresolved_signalized_crash_count": _safe_int(row.get("unresolved_signalized_crash_count")),
            "unresolved_coverage_pct": round(_safe_float(row.get("unresolved_coverage_pct")), 2),
            "unresolved_crash_coverage_pct": round(_safe_float(row.get("unresolved_crash_coverage_pct")), 2),
            "recommended_routing_action": _clean_text(row.get("recommended_routing_action")),
            "follow_up_action": (
                "If no acknowledgement is received, call the centralino or URP to confirm routing, then escalate through archivio generale PEC."
            ),
            "delivery_evidence_path": "",
            "response_status": "awaiting_send",
            "response_received_date": "",
            "notes": "",
        }
        dispatch_rows.append(dispatch_row)

        follow_up_rows.append(
            {
                "dispatch_reference": dispatch_reference,
                "request_id": request_id,
                "junction_id": dispatch_row["junction_id"],
                "signal_name": dispatch_row["signal_name"],
                "follow_up_stage": "first_follow_up",
                "due_date": first_follow_up_date.isoformat(),
                "recommended_channel": dispatch_row["phone_escalation_value"],
                "recommended_action": "Confirm receipt or routing and request acknowledgement of the PEC/email submission.",
                "completion_status": "pending",
                "completion_date": "",
                "notes": "",
            }
        )
        follow_up_rows.append(
            {
                "dispatch_reference": dispatch_reference,
                "request_id": request_id,
                "junction_id": dispatch_row["junction_id"],
                "signal_name": dispatch_row["signal_name"],
                "follow_up_stage": "escalation",
                "due_date": escalation_date.isoformat(),
                "recommended_channel": dispatch_row["secondary_channel_value"],
                "recommended_action": "Escalate through archivio generale PEC and record any protocol or routing feedback.",
                "completion_status": "pending",
                "completion_date": "",
                "notes": "",
            }
        )

        packet_md_path = packet_dir / f"{_slugify(request_id)}.md"
        packet_json_path = packet_dir / f"{_slugify(request_id)}.json"
        packet_md_path.write_text(_dispatch_packet_markdown(dispatch_row), encoding="utf-8")
        packet_json_path.write_text(json.dumps(dispatch_row, indent=2, sort_keys=True), encoding="utf-8")
        packet_paths.extend([str(packet_md_path), str(packet_json_path)])

    dispatch_queue_path = output_root / "dispatch_execution_queue.csv"
    follow_up_tracker_path = output_root / "follow_up_tracker.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_bundle.manifest.json"

    _write_csv(
        dispatch_queue_path,
        dispatch_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "dispatch_status",
            "planned_dispatch_date",
            "first_follow_up_date",
            "escalation_date",
            "send_channel_strategy",
            "primary_channel_type",
            "primary_channel_value",
            "secondary_channel_type",
            "secondary_channel_value",
            "general_email_value",
            "phone_escalation_type",
            "phone_escalation_value",
            "public_relations_value",
            "contact_name",
            "contact_email",
            "email_subject",
            "recommended_time_window",
            "preferred_focus_hour_ranges",
            "fallback_pilot_scope",
            "routing_decision",
            "external_blocker",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "recommended_routing_action",
            "follow_up_action",
            "delivery_evidence_path",
            "response_status",
            "response_received_date",
            "notes",
        ],
    )
    _write_csv(
        follow_up_tracker_path,
        follow_up_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "follow_up_stage",
            "due_date",
            "recommended_channel",
            "recommended_action",
            "completion_status",
            "completion_date",
            "notes",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_count": len(dispatch_rows),
        "dispatch_queue_count": len(dispatch_rows),
        "follow_up_item_count": len(follow_up_rows),
        "primary_pec_count": sum(1 for row in dispatch_rows if row["primary_channel_type"] == "pec_email"),
        "direct_contact_count": sum(1 for row in dispatch_rows if row["contact_email"]),
        "external_blocker_count": sum(1 for row in dispatch_rows if _clean_text(row.get("external_blocker"))),
        "targets_with_unresolved_movements": sum(
            1 for row in dispatch_rows if _safe_int(row["unresolved_signalized_movement_count"]) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row["unresolved_signalized_movement_count"]) for row in dispatch_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row["unresolved_signalized_crash_count"]) for row in dispatch_rows
        ),
    }

    bundle_payload = {
        "signal_phase_dispatch_bundle_version": SIGNAL_PHASE_DISPATCH_BUNDLE_VERSION,
        "signal_phase_dispatch_bundle_contract_version": SIGNAL_PHASE_DISPATCH_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "dispatch_queue": dispatch_rows,
        "follow_up_tracker": follow_up_rows,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_bundle_version": SIGNAL_PHASE_DISPATCH_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_bundle_version": SIGNAL_PHASE_DISPATCH_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_bundle_builder",
        },
        "inputs": {
            "signal_phase_contact_resolution_bundle_path": str(resolution_bundle_input),
            "planned_dispatch_date": planned_date.isoformat(),
            "follow_up_days": int(follow_up_days),
            "escalation_days": int(escalation_days),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "dispatch_queue_path": str(dispatch_queue_path),
            "dispatch_queue_sha256": _sha256(dispatch_queue_path),
            "follow_up_tracker_path": str(follow_up_tracker_path),
            "follow_up_tracker_sha256": _sha256(follow_up_tracker_path),
            "packet_dir": str(packet_dir),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_contact_resolution_bundle",
                resolution_bundle_input,
                _sha256(resolution_bundle_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_dispatch_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_dispatch_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_dispatch_queue", dispatch_queue_path, _sha256(dispatch_queue_path)),
            _artifact_reference("signal_phase_follow_up_tracker", follow_up_tracker_path, _sha256(follow_up_tracker_path)),
        ]
        + [
            _artifact_reference("signal_phase_dispatch_packet", Path(path), _sha256(Path(path)))
            for path in packet_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_bundle_version": SIGNAL_PHASE_DISPATCH_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
