"""Build Bari request-level action handoff bundles from the action-execution surface."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_VERSION = "signal_phase_action_handoff_bundle_v1"
SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_action_handoff_bundle_public_v1"
)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _handoff_mapping(
    execution_route: str,
    *,
    dispatch_execution_log_path: Path,
    follow_up_execution_queue_path: Path,
    dispatch_log_repair_log_path: Path,
    delivery_monitor_queue_path: Path,
    delivery_receipt_register_path: Path,
    runtime_cycle_manifest_path: Path,
) -> tuple[str, str, str]:
    if execution_route == "dispatch_send":
        return (
            "dispatch_execution_log",
            str(dispatch_execution_log_path),
            "After the send, fill the matching row in the dispatch execution log and rerun `make run-bari-signal-phase-runtime-cycle`.",
        )
    if execution_route == "follow_up_send":
        return (
            "follow_up_execution_queue",
            str(follow_up_execution_queue_path),
            "After the reminder, update the matching follow-up execution row and rerun `make run-bari-signal-phase-runtime-cycle`.",
        )
    if execution_route == "dispatch_log_repair":
        return (
            "dispatch_log_repair_log",
            str(dispatch_log_repair_log_path),
            "Complete the repair row, mark it ready for validation, and rerun `make run-bari-signal-phase-runtime-cycle`.",
        )
    if execution_route == "dispatch_validation_rerun":
        return (
            "runtime_cycle_command",
            str(runtime_cycle_manifest_path),
            "Rerun `make run-bari-signal-phase-runtime-cycle` so the repaired row can clear validation and writeback.",
        )
    if execution_route == "delivery_manual_review":
        return (
            "delivery_monitor_queue",
            str(delivery_monitor_queue_path),
            "Review the delivery-monitor queue and receipt register together before the next validation batch.",
        )
    if execution_route == "provider_fix_request":
        return (
            "provider_fix_request",
            str(delivery_receipt_register_path),
            "Use the linked delivery items to request a corrected provider extract, then rerun `make run-bari-signal-phase-receive-cycle` when it lands.",
        )
    return (
        "unknown_handoff",
        "",
        "No downstream handoff target is defined for this execution route.",
    )


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Action Handoff Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari request-level operator queue has been translated into exact downstream handoff targets.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- handoff-ready requests: `{payload['summary']['handoff_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- dispatch-log handoffs: `{payload['summary']['dispatch_recording_count']}`",
        f"- follow-up handoffs: `{payload['summary']['follow_up_recording_count']}`",
        f"- repair-log handoffs: `{payload['summary']['repair_log_count']}`",
        f"- runtime-cycle reruns: `{payload['summary']['runtime_command_count']}`",
        f"- delivery-review handoffs: `{payload['summary']['delivery_review_count']}`",
        f"- provider-fix handoffs: `{payload['summary']['provider_fix_count']}`",
        "",
        "## Ready Queue",
        "",
    ]
    for row in payload["handoff_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['handoff_target_kind']}` at `{row['handoff_target_path'] or 'n/a'}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_action_handoff_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_action_handoff/bari",
    signal_phase_action_execution_bundle_path: str | Path = "data/reporting/signal_phase_action_execution/bari/signal_phase_action_execution_bundle.json",
    dispatch_execution_log_path: str | Path = "data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_log.csv",
    follow_up_execution_queue_path: str | Path = "data/reporting/signal_phase_follow_up_execution/bari/follow_up_execution_queue.csv",
    dispatch_log_repair_log_path: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    delivery_monitor_queue_path: str | Path = "data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    runtime_cycle_manifest_path: str | Path = "data/processed/signal_phase_runtime_cycles/bari/signal_phase_runtime_cycle.manifest.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    action_execution_bundle_input = Path(signal_phase_action_execution_bundle_path)
    dispatch_execution_log_input = Path(dispatch_execution_log_path)
    follow_up_execution_queue_input = Path(follow_up_execution_queue_path)
    dispatch_log_repair_log_input = Path(dispatch_log_repair_log_path)
    delivery_monitor_queue_input = Path(delivery_monitor_queue_path)
    delivery_receipt_register_input = Path(delivery_receipt_register_path)
    runtime_cycle_manifest_input = Path(runtime_cycle_manifest_path)

    action_execution_bundle = _load_json(action_execution_bundle_input)
    execution_ready_rows = list(action_execution_bundle.get("execution_ready_queue", []) or [])
    internal_hold_rows = list(action_execution_bundle.get("internal_hold_queue", []) or [])

    handoff_ready_queue: list[dict[str, Any]] = []
    hold_queue: list[dict[str, Any]] = []

    for row in sorted(
        [item for item in execution_ready_rows if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        handoff_target_kind, handoff_target_path, handoff_instructions = _handoff_mapping(
            _clean_text(row.get("execution_route")) or "",
            dispatch_execution_log_path=dispatch_execution_log_input,
            follow_up_execution_queue_path=follow_up_execution_queue_input,
            dispatch_log_repair_log_path=dispatch_log_repair_log_input,
            delivery_monitor_queue_path=delivery_monitor_queue_input,
            delivery_receipt_register_path=delivery_receipt_register_input,
            runtime_cycle_manifest_path=runtime_cycle_manifest_input,
        )
        handoff_ready_queue.append(
            {
                "dispatch_reference": _clean_text(row.get("dispatch_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "priority_rank": _safe_int(row.get("priority_rank")),
                "priority_band": _clean_text(row.get("priority_band")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_date": _clean_text(row.get("due_date")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "packet_json_path": _clean_text(row.get("packet_json_path")),
                "packet_available": _clean_text(row.get("packet_available")) or "no",
                "operator_command": _clean_text(row.get("operator_command")),
                "recommended_action": _clean_text(row.get("recommended_action")),
                "action_summary": _clean_text(row.get("action_summary")),
                "handoff_target_kind": handoff_target_kind,
                "handoff_target_path": handoff_target_path,
                "handoff_reference_key": "request_id",
                "handoff_reference_value": _clean_text(row.get("request_id")),
                "handoff_status": "ready_for_operator",
                "handoff_instructions": handoff_instructions,
            }
        )

    for row in sorted(
        [item for item in internal_hold_rows if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        hold_queue.append(
            {
                "dispatch_reference": _clean_text(row.get("dispatch_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "priority_rank": _safe_int(row.get("priority_rank")),
                "priority_band": _clean_text(row.get("priority_band")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_date": _clean_text(row.get("due_date")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "hold_reason": _clean_text(row.get("hold_reason")),
                "operator_command": _clean_text(row.get("operator_command")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "packet_json_path": _clean_text(row.get("packet_json_path")),
            }
        )

    ready_queue_path = output_root / "action_handoff_queue.csv"
    hold_queue_path = output_root / "action_handoff_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_action_handoff_bundle.json"
    bundle_md_path = output_root / "signal_phase_action_handoff_bundle.md"
    manifest_path = output_root / "signal_phase_action_handoff_bundle.manifest.json"

    ready_fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "priority_rank",
        "priority_band",
        "action_category",
        "execution_route",
        "due_date",
        "due_now",
        "packet_md_path",
        "packet_json_path",
        "packet_available",
        "operator_command",
        "recommended_action",
        "action_summary",
        "handoff_target_kind",
        "handoff_target_path",
        "handoff_reference_key",
        "handoff_reference_value",
        "handoff_status",
        "handoff_instructions",
    ]
    hold_fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "priority_rank",
        "priority_band",
        "action_category",
        "execution_route",
        "due_date",
        "due_now",
        "hold_reason",
        "operator_command",
        "packet_md_path",
        "packet_json_path",
    ]
    _write_csv(ready_queue_path, handoff_ready_queue, ready_fieldnames)
    _write_csv(hold_queue_path, hold_queue, hold_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(handoff_ready_queue) + len(hold_queue),
        "handoff_ready_count": len(handoff_ready_queue),
        "internal_hold_count": len(hold_queue),
        "dispatch_recording_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "dispatch_execution_log"
        ),
        "follow_up_recording_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "follow_up_execution_queue"
        ),
        "repair_log_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "dispatch_log_repair_log"
        ),
        "runtime_command_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "runtime_cycle_command"
        ),
        "delivery_review_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "delivery_monitor_queue"
        ),
        "provider_fix_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "provider_fix_request"
        ),
    }

    payload = {
        "signal_phase_action_handoff_bundle_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_VERSION,
        "signal_phase_action_handoff_bundle_contract_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "handoff_ready_queue": handoff_ready_queue,
        "internal_hold_queue": hold_queue,
        "inputs": {
            "signal_phase_action_execution_bundle_path": str(action_execution_bundle_input),
            "dispatch_execution_log_path": str(dispatch_execution_log_input),
            "follow_up_execution_queue_path": str(follow_up_execution_queue_input),
            "dispatch_log_repair_log_path": str(dispatch_log_repair_log_input),
            "delivery_monitor_queue_path": str(delivery_monitor_queue_input),
            "delivery_receipt_register_path": str(delivery_receipt_register_input),
            "runtime_cycle_manifest_path": str(runtime_cycle_manifest_input),
        },
        "outputs": {
            "action_handoff_queue_path": str(ready_queue_path),
            "action_handoff_hold_queue_path": str(hold_queue_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_action_handoff_bundle_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_action_handoff_bundle",
            "public_contract_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION,
            "signal_phase_action_handoff_bundle_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_action_handoff_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "action_handoff_queue_path": str(ready_queue_path),
            "action_handoff_queue_sha256": _sha256(ready_queue_path),
            "action_handoff_hold_queue_path": str(hold_queue_path),
            "action_handoff_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_action_execution_bundle_json",
                    action_execution_bundle_input,
                    _sha256(action_execution_bundle_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_action_handoff_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_action_handoff_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_action_handoff_queue",
                    ready_queue_path,
                    _sha256(ready_queue_path),
                ),
                _artifact_reference(
                    "signal_phase_action_handoff_hold_queue",
                    hold_queue_path,
                    _sha256(hold_queue_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_action_handoff_bundle_version": SIGNAL_PHASE_ACTION_HANDOFF_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
