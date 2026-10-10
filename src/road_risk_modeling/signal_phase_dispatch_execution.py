"""Build Bari signal-phase initial-dispatch execution bundles."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_VERSION = "signal_phase_dispatch_execution_bundle_v1"
SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_CONTRACT_VERSION = "signal_phase_dispatch_execution_bundle_public_v1"


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


def _target_dispatch_status(channel_type: Any) -> str:
    channel = (_clean_text(channel_type) or "").lower()
    if channel == "pec_email":
        return "sent_via_pec"
    if channel == "email":
        return "sent_via_email"
    if channel == "phone":
        return "sent_via_phone"
    return "dispatch_executed"


def _execution_message(row: dict[str, Any]) -> str:
    return (
        f"Please send the Bari signal-phase request for `{row['signal_name']}` (`{row['junction_id']}`) "
        f"using `{row['primary_channel_value'] or 'the primary route'}` and CC "
        f"`{row['secondary_channel_value'] or 'the secondary route'}`. The requested focus window is "
        f"`{row['preferred_focus_hour_ranges'] or row['recommended_time_window'] or 'the scoped crash-heavy period'}`. "
        f"If a full export is not available, the fallback pilot scope is `{row['fallback_pilot_scope'] or 'the scoped pilot window'}`. "
        f"Current unresolved burden is `{row['unresolved_signalized_movement_count']}` movements and "
        f"`{row['unresolved_signalized_crash_count']}` crashes."
    )


def _execution_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Dispatch Execution: {packet['request_id']}",
        "",
        "## Execution Summary",
        "",
        f"- Dispatch reference: `{packet['dispatch_reference']}`",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Due date: `{packet['due_date']}`",
        f"- Due now: `{packet['due_now']}`",
        f"- Unresolved movement burden: `{packet['unresolved_signalized_movement_count']}` movements / `{packet['unresolved_signalized_crash_count']}` crashes",
        f"- Unresolved coverage: `{packet['unresolved_coverage_pct']}`% movements / `{packet['unresolved_crash_coverage_pct']}`% crashes",
        "",
        "## Send Route",
        "",
        f"- Primary channel: `{packet['primary_channel_value']}`",
        f"- Secondary channel: `{packet['secondary_channel_value']}`",
        f"- General email fallback: `{packet['general_email_value']}`",
        f"- Phone escalation: `{packet['phone_escalation_value']}`",
        f"- Subject: `{packet['email_subject']}`",
        "",
        "## Suggested Message",
        "",
        str(packet["suggested_message"]),
        "",
        "## After Send",
        "",
        "- record the actual channel used",
        "- record the send timestamp",
        "- save PEC receipt or sent-message evidence",
        "- record any protocol or acknowledgement",
        "- populate the staged dispatch-tracker update row",
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Execution Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari request-level action queue has been filtered into initial dispatch actions and non-dispatch holds.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- execution-ready dispatches: `{payload['summary']['execution_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- due now: `{payload['summary']['due_now_count']}`",
        f"- PEC-first dispatches: `{payload['summary']['pec_ready_count']}`",
        f"- staged tracker updates: `{payload['summary']['tracker_update_count']}`",
        f"- execution-ready targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across execution-ready targets: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across execution-ready targets: `{payload['summary']['unresolved_signalized_crash_total']}`",
        "",
        "## Execution Queue",
        "",
    ]
    for row in payload["execution_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: send `{row['due_date']}` via `{row['primary_channel_value']}`, "
            f"unresolved crashes `{row['unresolved_signalized_crash_count']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_execution/bari",
    signal_phase_action_queue_path: str | Path = "data/reporting/signal_phase_action_queue/bari/action_queue.csv",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    dispatch_packet_dir: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_packets",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "execution_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    action_queue_input = Path(signal_phase_action_queue_path)
    dispatch_queue_input = Path(dispatch_execution_queue_path)
    dispatch_packet_dir_input = Path(dispatch_packet_dir)

    action_rows = _read_csv_rows(action_queue_input)
    dispatch_rows = _read_csv_rows(dispatch_queue_input)
    dispatch_by_request = {str(row.get("request_id") or ""): row for row in dispatch_rows if row.get("request_id")}

    execution_ready_rows: list[dict[str, Any]] = []
    internal_hold_rows: list[dict[str, Any]] = []
    tracker_update_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for action_row in sorted(
        [item for item in action_rows if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        request_id = str(action_row.get("request_id") or "")
        dispatch_row = dispatch_by_request.get(request_id, {})
        action_category = _clean_text(action_row.get("action_category")) or ""

        if action_category == "dispatch_request_now":
            execution_row = {
                "dispatch_reference": _clean_text(action_row.get("dispatch_reference")),
                "request_id": request_id,
                "junction_id": _clean_text(action_row.get("junction_id")),
                "signal_name": _clean_text(action_row.get("signal_name")),
                "priority_rank": _safe_int(action_row.get("priority_rank")),
                "priority_band": _clean_text(action_row.get("priority_band")),
                "action_category": action_category,
                "due_date": _clean_text(action_row.get("due_date")),
                "due_now": _clean_text(action_row.get("due_now")) or "False",
                "dispatch_status": _clean_text(dispatch_row.get("dispatch_status")),
                "response_status": _clean_text(dispatch_row.get("response_status")),
                "send_channel_strategy": _clean_text(dispatch_row.get("send_channel_strategy")),
                "primary_channel_type": _clean_text(dispatch_row.get("primary_channel_type")),
                "primary_channel_value": _clean_text(dispatch_row.get("primary_channel_value")),
                "secondary_channel_type": _clean_text(dispatch_row.get("secondary_channel_type")),
                "secondary_channel_value": _clean_text(dispatch_row.get("secondary_channel_value")),
                "general_email_value": _clean_text(dispatch_row.get("general_email_value")),
                "phone_escalation_type": _clean_text(dispatch_row.get("phone_escalation_type")),
                "phone_escalation_value": _clean_text(dispatch_row.get("phone_escalation_value")),
                "public_relations_value": _clean_text(dispatch_row.get("public_relations_value")),
                "email_subject": _clean_text(dispatch_row.get("email_subject")),
                "recommended_time_window": _clean_text(dispatch_row.get("recommended_time_window")),
                "preferred_focus_hour_ranges": _clean_text(dispatch_row.get("preferred_focus_hour_ranges")),
                "fallback_pilot_scope": _clean_text(dispatch_row.get("fallback_pilot_scope")),
                "unresolved_signalized_movement_count": _safe_int(dispatch_row.get("unresolved_signalized_movement_count")),
                "unresolved_signalized_crash_count": _safe_int(dispatch_row.get("unresolved_signalized_crash_count")),
                "unresolved_coverage_pct": round(_safe_float(dispatch_row.get("unresolved_coverage_pct")), 2),
                "unresolved_crash_coverage_pct": round(
                    _safe_float(dispatch_row.get("unresolved_crash_coverage_pct")), 2
                ),
                "recommended_action": _clean_text(action_row.get("recommended_action")),
                "action_summary": _clean_text(action_row.get("action_summary")),
                "dispatch_packet_md_path": _clean_text(action_row.get("packet_md_path")),
                "dispatch_packet_json_path": str(dispatch_packet_dir_input / f"{_slugify(request_id)}.json"),
                "execution_status": "pending_execution",
                "execution_completed_at": "",
                "execution_channel_used": "",
                "execution_outcome": "",
                "response_received": "no",
                "response_summary": "",
                "protocol_reference": "",
                "evidence_path": "",
                "execution_notes": "",
            }
            execution_row["suggested_message"] = _execution_message(execution_row)
            packet_base = _slugify(request_id)
            packet_md_path = packet_dir / f"{packet_base}.md"
            packet_json_path = packet_dir / f"{packet_base}.json"
            packet_md_path.write_text(_execution_packet_markdown(execution_row), encoding="utf-8")
            packet_json_path.write_text(json.dumps(execution_row, indent=2, sort_keys=True), encoding="utf-8")
            execution_row["execution_packet_md_path"] = str(packet_md_path)
            execution_row["execution_packet_json_path"] = str(packet_json_path)
            packet_paths.extend([str(packet_md_path), str(packet_json_path)])
            execution_ready_rows.append(execution_row)

            tracker_update_rows.append(
                {
                    "dispatch_reference": execution_row["dispatch_reference"],
                    "request_id": request_id,
                    "junction_id": execution_row["junction_id"],
                    "signal_name": execution_row["signal_name"],
                    "current_dispatch_status": execution_row["dispatch_status"],
                    "target_dispatch_status": _target_dispatch_status(execution_row["primary_channel_type"]),
                    "current_response_status": execution_row["response_status"],
                    "target_response_status": "awaiting_delivery",
                    "execution_status": "pending_execution",
                    "execution_completed_at": "",
                    "execution_channel_used": "",
                    "protocol_reference": "",
                    "evidence_path": "",
                    "response_received": "no",
                    "response_summary": "",
                    "update_notes": "",
                    "linked_execution_packet_md_path": str(packet_md_path),
                    "unresolved_signalized_movement_count": execution_row["unresolved_signalized_movement_count"],
                    "unresolved_signalized_crash_count": execution_row["unresolved_signalized_crash_count"],
                    "unresolved_coverage_pct": execution_row["unresolved_coverage_pct"],
                    "unresolved_crash_coverage_pct": execution_row["unresolved_crash_coverage_pct"],
                }
            )
        else:
            internal_hold_rows.append(
                {
                    "request_id": request_id,
                    "junction_id": _clean_text(action_row.get("junction_id")),
                    "signal_name": _clean_text(action_row.get("signal_name")),
                    "action_category": action_category,
                    "due_date": _clean_text(action_row.get("due_date")),
                    "hold_reason": "This request is not in the initial dispatch state; use the request-level action queue instead of the dispatch execution bundle.",
                }
            )

    execution_ready_path = output_root / "dispatch_execution_ready_queue.csv"
    tracker_updates_path = output_root / "dispatch_tracker_updates.csv"
    internal_hold_path = output_root / "internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_execution_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_execution_bundle.manifest.json"

    _write_csv(
        execution_ready_path,
        execution_ready_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "action_category",
            "due_date",
            "due_now",
            "dispatch_status",
            "response_status",
            "send_channel_strategy",
            "primary_channel_type",
            "primary_channel_value",
            "secondary_channel_type",
            "secondary_channel_value",
            "general_email_value",
            "phone_escalation_type",
            "phone_escalation_value",
            "public_relations_value",
            "email_subject",
            "recommended_time_window",
            "preferred_focus_hour_ranges",
            "fallback_pilot_scope",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "recommended_action",
            "action_summary",
            "dispatch_packet_md_path",
            "dispatch_packet_json_path",
            "execution_status",
            "execution_completed_at",
            "execution_channel_used",
            "execution_outcome",
            "response_received",
            "response_summary",
            "protocol_reference",
            "evidence_path",
            "execution_notes",
            "execution_packet_md_path",
            "execution_packet_json_path",
        ],
    )
    _write_csv(
        tracker_updates_path,
        tracker_update_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "current_dispatch_status",
            "target_dispatch_status",
            "current_response_status",
            "target_response_status",
            "execution_status",
            "execution_completed_at",
            "execution_channel_used",
            "protocol_reference",
            "evidence_path",
            "response_received",
            "response_summary",
            "update_notes",
            "linked_execution_packet_md_path",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
        ],
    )
    _write_csv(
        internal_hold_path,
        internal_hold_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "action_category",
            "due_date",
            "hold_reason",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(action_rows),
        "execution_ready_count": len(execution_ready_rows),
        "internal_hold_count": len(internal_hold_rows),
        "due_now_count": sum(1 for row in execution_ready_rows if (_clean_text(row.get("due_now")) or "").lower() == "true"),
        "pec_ready_count": sum(1 for row in execution_ready_rows if row.get("primary_channel_type") == "pec_email"),
        "tracker_update_count": len(tracker_update_rows),
        "targets_with_unresolved_movements": sum(
            1 for row in execution_ready_rows if _safe_int(row.get("unresolved_signalized_movement_count")) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in execution_ready_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in execution_ready_rows
        ),
    }

    payload = {
        "signal_phase_dispatch_execution_bundle_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_VERSION,
        "signal_phase_dispatch_execution_bundle_contract_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "execution_ready_queue": execution_ready_rows,
        "internal_hold_queue": internal_hold_rows,
        "tracker_updates": tracker_update_rows,
        "inputs": {
            "signal_phase_action_queue_path": str(action_queue_input),
            "dispatch_execution_queue_path": str(dispatch_queue_input),
            "dispatch_packet_dir": str(dispatch_packet_dir_input),
        },
        "outputs": {
            "dispatch_execution_ready_queue_path": str(execution_ready_path),
            "dispatch_tracker_updates_path": str(tracker_updates_path),
            "internal_hold_queue_path": str(internal_hold_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_execution_bundle_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_execution_bundle_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_execution_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "dispatch_execution_ready_queue_path": str(execution_ready_path),
            "dispatch_execution_ready_queue_sha256": _sha256(execution_ready_path),
            "dispatch_tracker_updates_path": str(tracker_updates_path),
            "dispatch_tracker_updates_sha256": _sha256(tracker_updates_path),
            "internal_hold_queue_path": str(internal_hold_path),
            "internal_hold_queue_sha256": _sha256(internal_hold_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_action_queue_csv",
                    action_queue_input,
                    _sha256(action_queue_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue",
                    dispatch_queue_input,
                    _sha256(dispatch_queue_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_ready_queue_csv",
                    execution_ready_path,
                    _sha256(execution_ready_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_tracker_updates_csv",
                    tracker_updates_path,
                    _sha256(tracker_updates_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_internal_hold_queue_csv",
                    internal_hold_path,
                    _sha256(internal_hold_path),
                ),
                *[
                    _artifact_reference(
                        "signal_phase_dispatch_execution_packet",
                        Path(path),
                        _sha256(Path(path)),
                    )
                    for path in packet_paths
                ],
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_dispatch_execution_bundle_version": SIGNAL_PHASE_DISPATCH_EXECUTION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
