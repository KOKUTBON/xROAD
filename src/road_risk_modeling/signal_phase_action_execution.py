"""Build Bari request-level operator execution bundles from the action queue."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_VERSION = "signal_phase_action_execution_bundle_v1"
SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_action_execution_bundle_public_v1"
)

_EXECUTION_ROUTE_BY_ACTION = {
    "dispatch_request_now": "dispatch_send",
    "execute_follow_up_now": "follow_up_send",
    "repair_dispatch_log_now": "dispatch_log_repair",
    "repair_dispatch_log_again": "dispatch_log_repair",
    "rerun_dispatch_validation": "dispatch_validation_rerun",
    "manual_delivery_review": "delivery_manual_review",
    "request_provider_fix": "provider_fix_request",
}


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


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _derive_packet_json_path(packet_md_path: str | None) -> str:
    if not packet_md_path:
        return ""
    path = Path(packet_md_path)
    if path.suffix.lower() != ".md":
        return ""
    packet_json_path = path.with_suffix(".json")
    return str(packet_json_path) if packet_json_path.exists() else ""


def _execution_route(action_category: str, due_now: bool) -> str:
    if action_category == "scheduled_follow_up" and due_now:
        return "follow_up_send"
    return _EXECUTION_ROUTE_BY_ACTION.get(action_category, "")


def _command_hint(action_category: str) -> str:
    if action_category in {"rerun_dispatch_validation", "await_dispatch_writeback"}:
        return "make run-bari-signal-phase-runtime-cycle"
    if action_category == "await_delivery":
        return "make run-bari-signal-phase-receive-cycle"
    return ""


def _hold_reason(action_category: str, due_date: str | None) -> str:
    if action_category == "scheduled_follow_up":
        return (
            f"Follow-up is scheduled for `{due_date}`; do not send it before the due date."
            if due_date
            else "Follow-up is scheduled for a future date."
        )
    if action_category == "await_delivery":
        return "Provider delivery has not arrived yet; wait for intake monitoring to detect a file."
    if action_category == "await_dispatch_writeback":
        return "The repaired dispatch row is cleared and waiting for runtime writeback."
    if action_category == "completed":
        return "All delivery items for this request have already been applied."
    return "No operator execution is required for this request right now."


def _execution_route_summary(route: str) -> str:
    return {
        "dispatch_send": "Send the initial request packet.",
        "follow_up_send": "Execute the prepared follow-up packet.",
        "dispatch_log_repair": "Repair the logged dispatch row before validation.",
        "dispatch_validation_rerun": "Rerun validation for the repaired dispatch row.",
        "delivery_manual_review": "Inspect intake files and select the correct delivery item.",
        "provider_fix_request": "Request a corrected provider extract.",
    }.get(route, "Execute the queued Bari operator action.")


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Action Execution Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari request-level action queue has been split into execution-ready operator work and non-actionable holds.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- execution-ready requests: `{payload['summary']['execution_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- due now: `{payload['summary']['due_now_count']}`",
        f"- dispatch sends: `{payload['summary']['dispatch_send_count']}`",
        f"- follow-up sends: `{payload['summary']['follow_up_send_count']}`",
        f"- repair actions: `{payload['summary']['repair_action_count']}`",
        f"- validation reruns: `{payload['summary']['validation_rerun_count']}`",
        f"- manual reviews: `{payload['summary']['manual_review_count']}`",
        f"- provider-fix requests: `{payload['summary']['provider_fix_count']}`",
        f"- waiting requests: `{payload['summary']['waiting_count']}`",
        f"- completed requests: `{payload['summary']['completed_count']}`",
        "",
        "## Execution Queue",
        "",
    ]
    for row in payload["execution_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['execution_route']}` due `{row['due_date'] or 'n/a'}` "
            f"(packet=`{row['packet_available']}`) -> `{row['action_summary']}`"
        )
    lines.extend(["", "## Internal Holds", ""])
    for row in payload["internal_hold_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['action_category']}` -> `{row['hold_reason']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_action_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_action_execution/bari",
    signal_phase_action_queue_path: str | Path = "data/reporting/signal_phase_action_queue/bari/action_queue.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    action_queue_input = Path(signal_phase_action_queue_path)
    action_rows = _read_csv_rows(action_queue_input)

    execution_ready_queue: list[dict[str, Any]] = []
    internal_hold_queue: list[dict[str, Any]] = []

    for row in sorted(
        action_rows,
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        action_category = _clean_text(row.get("action_category")) or ""
        due_now = _is_true(row.get("due_now"))
        due_date = _clean_text(row.get("due_date"))
        packet_md_path = _clean_text(row.get("packet_md_path")) or ""
        packet_json_path = _derive_packet_json_path(packet_md_path)
        packet_available = "yes" if packet_md_path and Path(packet_md_path).exists() else "no"
        execution_route = _execution_route(action_category, due_now)

        row_payload = {
            "dispatch_reference": _clean_text(row.get("dispatch_reference")),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "priority_rank": _safe_int(row.get("priority_rank")),
            "priority_band": _clean_text(row.get("priority_band")),
            "action_category": action_category,
            "source_stage": _clean_text(row.get("source_stage")),
            "due_date": due_date,
            "due_now": "yes" if due_now else "no",
            "dispatch_status": _clean_text(row.get("dispatch_status")),
            "response_status": _clean_text(row.get("response_status")),
            "lifecycle_statuses": _clean_text(row.get("lifecycle_statuses")),
            "open_delivery_item_count": _safe_int(row.get("open_delivery_item_count")),
            "delivery_item_ids": _clean_text(row.get("delivery_item_ids")),
            "dispatch_validation_outcome": _clean_text(row.get("dispatch_validation_outcome")),
            "dispatch_validation_issue_codes": _clean_text(
                row.get("dispatch_validation_issue_codes")
            ),
            "repair_status_category": _clean_text(row.get("repair_status_category")),
            "repair_status": _clean_text(row.get("repair_status")),
            "repair_next_action": _clean_text(row.get("repair_next_action")),
            "repair_writeback_eligible": _clean_text(row.get("repair_writeback_eligible")),
            "execution_route": execution_route,
            "operator_command": _command_hint(action_category),
            "packet_md_path": packet_md_path,
            "packet_json_path": packet_json_path,
            "packet_available": packet_available,
            "primary_channel_value": _clean_text(row.get("primary_channel_value")),
            "secondary_channel_value": _clean_text(row.get("secondary_channel_value")),
            "phone_escalation_value": _clean_text(row.get("phone_escalation_value")),
            "recommended_action": _clean_text(row.get("recommended_action")),
            "action_summary": _clean_text(row.get("action_summary")),
        }

        if execution_route:
            row_payload["execution_summary"] = _execution_route_summary(execution_route)
            execution_ready_queue.append(row_payload)
        else:
            row_payload["hold_reason"] = _hold_reason(action_category, due_date)
            internal_hold_queue.append(row_payload)

    execution_ready_path = output_root / "action_execution_ready_queue.csv"
    internal_hold_path = output_root / "action_internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_action_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_action_execution_bundle.md"
    manifest_path = output_root / "signal_phase_action_execution_bundle.manifest.json"

    fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "priority_rank",
        "priority_band",
        "action_category",
        "source_stage",
        "due_date",
        "due_now",
        "dispatch_status",
        "response_status",
        "lifecycle_statuses",
        "open_delivery_item_count",
        "delivery_item_ids",
        "dispatch_validation_outcome",
        "dispatch_validation_issue_codes",
        "repair_status_category",
        "repair_status",
        "repair_next_action",
        "repair_writeback_eligible",
        "execution_route",
        "operator_command",
        "packet_md_path",
        "packet_json_path",
        "packet_available",
        "primary_channel_value",
        "secondary_channel_value",
        "phone_escalation_value",
        "recommended_action",
        "action_summary",
    ]
    _write_csv(
        execution_ready_path,
        execution_ready_queue,
        fieldnames + ["execution_summary"],
    )
    _write_csv(
        internal_hold_path,
        internal_hold_queue,
        fieldnames + ["hold_reason"],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(action_rows),
        "execution_ready_count": len(execution_ready_queue),
        "internal_hold_count": len(internal_hold_queue),
        "due_now_count": sum(1 for row in execution_ready_queue if row["due_now"] == "yes"),
        "dispatch_send_count": sum(
            1 for row in execution_ready_queue if row["execution_route"] == "dispatch_send"
        ),
        "follow_up_send_count": sum(
            1 for row in execution_ready_queue if row["execution_route"] == "follow_up_send"
        ),
        "repair_action_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "dispatch_log_repair"
        ),
        "validation_rerun_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "dispatch_validation_rerun"
        ),
        "manual_review_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "delivery_manual_review"
        ),
        "provider_fix_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "provider_fix_request"
        ),
        "waiting_count": sum(
            1
            for row in internal_hold_queue
            if row["action_category"] in {"scheduled_follow_up", "await_delivery", "await_dispatch_writeback"}
        ),
        "completed_count": sum(
            1 for row in internal_hold_queue if row["action_category"] == "completed"
        ),
    }

    payload = {
        "signal_phase_action_execution_bundle_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_VERSION,
        "signal_phase_action_execution_bundle_contract_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "execution_ready_queue": execution_ready_queue,
        "internal_hold_queue": internal_hold_queue,
        "inputs": {
            "signal_phase_action_queue_path": str(action_queue_input),
        },
        "outputs": {
            "action_execution_ready_queue_path": str(execution_ready_path),
            "action_internal_hold_queue_path": str(internal_hold_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_action_execution_bundle_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_action_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_action_execution_bundle_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_action_execution_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "action_execution_ready_queue_path": str(execution_ready_path),
            "action_execution_ready_queue_sha256": _sha256(execution_ready_path),
            "action_internal_hold_queue_path": str(internal_hold_path),
            "action_internal_hold_queue_sha256": _sha256(internal_hold_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_action_queue_csv",
                    action_queue_input,
                    _sha256(action_queue_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_action_execution_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_action_execution_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_action_execution_ready_queue",
                    execution_ready_path,
                    _sha256(execution_ready_path),
                ),
                _artifact_reference(
                    "signal_phase_action_internal_hold_queue",
                    internal_hold_path,
                    _sha256(internal_hold_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_action_execution_bundle_version": SIGNAL_PHASE_ACTION_EXECUTION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
