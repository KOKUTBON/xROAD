"""Run a Bari runtime rehearsal by injecting one synthetic dispatch send."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_runtime_cycle import run_bari_signal_phase_runtime_cycle


SIGNAL_PHASE_RUNTIME_REHEARSAL_VERSION = "signal_phase_runtime_rehearsal_v1"
SIGNAL_PHASE_RUNTIME_REHEARSAL_CONTRACT_VERSION = (
    "signal_phase_runtime_rehearsal_public_v1"
)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _safe_bool_text(value: Any) -> str:
    text = (_clean_text(value) or "").lower()
    return "yes" if text in {"1", "true", "yes", "y"} else "no"


def _request_map(rows: list[dict[str, Any]], key: str = "request_id") -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        request_id = _clean_text(row.get(key))
        if request_id:
            output[request_id] = row
    return output


def _action_state_by_request(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    rows = [
        row
        for row in list(payload.get("action_queue", []) or [])
        if isinstance(row, dict) and _clean_text(row.get("request_id"))
    ]
    return _request_map(rows)


def _operator_state_by_request(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    states: dict[str, dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("operator_ready_queue", []) or []),
        ("hold", payload.get("operator_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            if not request_id:
                continue
            states[request_id] = {
                "operator_queue_type": queue_type,
                "execution_route": _clean_text(row.get("execution_route")) or "",
                "handoff_target_kind": _clean_text(row.get("handoff_target_kind")) or "",
                "handoff_target_path": _clean_text(row.get("handoff_target_path")) or "",
                "hold_reason": _clean_text(row.get("hold_reason")) or "",
                "action_category": _clean_text(row.get("action_category")) or "",
            }
    return states


def _comparison_rows(
    pre_action_states: dict[str, dict[str, Any]],
    post_action_states: dict[str, dict[str, Any]],
    pre_operator_states: dict[str, dict[str, Any]],
    post_operator_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_request_ids = sorted(
        set(pre_action_states)
        | set(post_action_states)
        | set(pre_operator_states)
        | set(post_operator_states)
    )
    for request_id in all_request_ids:
        pre_action = pre_action_states.get(request_id, {})
        post_action = post_action_states.get(request_id, {})
        pre_operator = pre_operator_states.get(request_id, {})
        post_operator = post_operator_states.get(request_id, {})

        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post_action.get("signal_name"))
            or _clean_text(pre_action.get("signal_name"))
            or "",
            "priority_rank": _safe_int(post_action.get("priority_rank"))
            or _safe_int(pre_action.get("priority_rank")),
            "pre_action_category": _clean_text(pre_action.get("action_category")) or "",
            "post_action_category": _clean_text(post_action.get("action_category")) or "",
            "pre_dispatch_status": _clean_text(pre_action.get("dispatch_status")) or "",
            "post_dispatch_status": _clean_text(post_action.get("dispatch_status")) or "",
            "pre_response_status": _clean_text(pre_action.get("response_status")) or "",
            "post_response_status": _clean_text(post_action.get("response_status")) or "",
            "pre_due_now": _safe_bool_text(pre_action.get("due_now")),
            "post_due_now": _safe_bool_text(post_action.get("due_now")),
            "pre_source_stage": _clean_text(pre_action.get("source_stage")) or "",
            "post_source_stage": _clean_text(post_action.get("source_stage")) or "",
            "pre_operator_queue_type": _clean_text(pre_operator.get("operator_queue_type")) or "absent",
            "post_operator_queue_type": _clean_text(post_operator.get("operator_queue_type")) or "absent",
            "pre_operator_execution_route": _clean_text(pre_operator.get("execution_route")) or "",
            "post_operator_execution_route": _clean_text(post_operator.get("execution_route")) or "",
            "pre_handoff_target_kind": _clean_text(pre_operator.get("handoff_target_kind")) or "",
            "post_handoff_target_kind": _clean_text(post_operator.get("handoff_target_kind")) or "",
            "pre_hold_reason": _clean_text(pre_operator.get("hold_reason")) or "",
            "post_hold_reason": _clean_text(post_operator.get("hold_reason")) or "",
        }
        changed = any(
            row[field] != row[f"post_{field[4:]}"]
            for field in (
                "pre_action_category",
                "pre_dispatch_status",
                "pre_response_status",
                "pre_due_now",
                "pre_source_stage",
                "pre_operator_queue_type",
                "pre_operator_execution_route",
                "pre_handoff_target_kind",
                "pre_hold_reason",
            )
        )
        row["state_changed"] = "yes" if changed else "no"
        rows.append(row)
    return rows


def _rehearsal_markdown(payload: dict[str, Any]) -> str:
    selected = payload["selected_request_transition"]
    lines = [
        "# Bari Signal-Phase Runtime Rehearsal",
        "",
        f"As of {payload['generated_at_utc']}, the Bari runtime cycle has been rehearsed by injecting one synthetic dispatch send for `{payload['selected_request_id']}` and rebuilding the full runtime stack.",
        "",
        "## Summary",
        "",
        f"- requests compared: `{payload['summary']['request_count']}`",
        f"- changed requests: `{payload['summary']['changed_request_count']}`",
        f"- selected request changed: `{payload['summary']['selected_request_changed']}`",
        f"- selected request left dispatch action: `{payload['summary']['selected_request_left_dispatch_action']}`",
        f"- selected request left dispatch send: `{payload['summary']['selected_request_left_dispatch_send']}`",
        f"- pre runtime dispatch actions: `{payload['summary']['pre_runtime_dispatch_action_count']}`",
        f"- post runtime dispatch actions: `{payload['summary']['post_runtime_dispatch_action_count']}`",
        f"- pre recording unresolved signalized movements: `{payload['summary']['pre_recording_unresolved_signalized_movement_total']}`",
        f"- post recording unresolved signalized movements: `{payload['summary']['post_recording_unresolved_signalized_movement_total']}`",
        f"- pre validation unresolved signalized crashes: `{payload['summary']['pre_validation_unresolved_signalized_crash_total']}`",
        f"- post validation unresolved signalized crashes: `{payload['summary']['post_validation_unresolved_signalized_crash_total']}`",
        f"- pre validation accepted unresolved signalized crashes: `{payload['summary']['pre_validation_accepted_unresolved_signalized_crash_total']}`",
        f"- post validation accepted unresolved signalized crashes: `{payload['summary']['post_validation_accepted_unresolved_signalized_crash_total']}`",
        f"- pre validation blocked unresolved signalized crashes: `{payload['summary']['pre_validation_rejected_unresolved_signalized_crash_total']}`",
        f"- post validation blocked unresolved signalized crashes: `{payload['summary']['post_validation_rejected_unresolved_signalized_crash_total']}`",
        f"- pre writeback unresolved signalized crashes: `{payload['summary']['pre_writeback_unresolved_signalized_crash_total']}`",
        f"- post writeback unresolved signalized crashes: `{payload['summary']['post_writeback_unresolved_signalized_crash_total']}`",
        f"- pre writeback-ready unresolved signalized crashes: `{payload['summary']['pre_writeback_ready_unresolved_signalized_crash_total']}`",
        f"- post writeback-ready unresolved signalized crashes: `{payload['summary']['post_writeback_ready_unresolved_signalized_crash_total']}`",
        f"- pre dispatch-cycle unresolved signalized crashes: `{payload['summary']['pre_dispatch_cycle_unresolved_signalized_crash_total']}`",
        f"- post dispatch-cycle unresolved signalized crashes: `{payload['summary']['post_dispatch_cycle_unresolved_signalized_crash_total']}`",
        f"- post logged executions: `{payload['summary']['post_recorded_execution_count']}`",
        f"- post validated executions: `{payload['summary']['post_validated_execution_count']}`",
        f"- post writeback-ready executions: `{payload['summary']['post_writeback_ready_count']}`",
        "",
        "## Selected Request",
        "",
        f"- request: `{payload['selected_request_id']}`",
        f"- signal: `{selected['signal_name']}`",
        f"- pre action: `{selected['pre_action_category']}` ({selected['pre_dispatch_status']} / {selected['pre_response_status']})",
        f"- post action: `{selected['post_action_category']}` ({selected['post_dispatch_status']} / {selected['post_response_status']})",
        f"- pre operator state: `{selected['pre_operator_queue_type']}` / `{selected['pre_operator_execution_route'] or 'n/a'}`",
        f"- post operator state: `{selected['post_operator_queue_type']}` / `{selected['post_operator_execution_route'] or 'n/a'}`",
        "",
        "## Outputs",
        "",
        f"- pre runtime cycle: `{payload['outputs']['pre_runtime_cycle_manifest_path']}`",
        f"- post runtime cycle: `{payload['outputs']['post_runtime_cycle_manifest_path']}`",
        f"- injected dispatch log: `{payload['outputs']['rehearsal_dispatch_execution_log_path']}`",
        f"- request comparison: `{payload['outputs']['request_state_comparison_path']}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_runtime_rehearsal(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_runtime_rehearsal/bari",
    request_id: str = "bari_signal_phase_01",
    signal_phase_delivery_intake_bundle_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    signal_phase_dispatch_bundle_path: str | Path = "data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    dispatch_log_repair_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    dispatch_log_repair_log_path: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    execution_status: str = "sent",
    execution_channel_used: str = "pec_email",
    execution_outcome: str = "request_dispatched",
    response_received: str = "no",
    response_summary: str = "",
    protocol_reference: str | None = None,
    evidence_path: str = "",
    execution_notes: str = "rehearsal send",
    execution_completed_at: str | None = None,
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    intake_bundle_input = Path(signal_phase_delivery_intake_bundle_path)
    receipt_input = Path(delivery_receipt_register_path)
    checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)
    dispatch_queue_input = Path(dispatch_execution_queue_path)
    follow_up_tracker_input = Path(follow_up_tracker_path)
    dispatch_bundle_input = Path(signal_phase_dispatch_bundle_path)
    dispatch_repair_queue_input = Path(dispatch_log_repair_queue_path)
    dispatch_repair_log_input = Path(dispatch_log_repair_log_path)

    generated_at = datetime.now(UTC)
    generated_at_utc = generated_at.isoformat()
    execution_completed_at_value = execution_completed_at or generated_at_utc
    protocol_reference_value = protocol_reference or (
        f"REHEARSAL-{request_id}-{generated_at.strftime('%Y%m%dT%H%M%SZ')}"
    )

    pre_runtime_cycle_output_dir = output_root / "pre_runtime_cycle"
    post_runtime_cycle_output_dir = output_root / "post_runtime_cycle"

    common_cycle_kwargs = {
        "signal_phase_delivery_intake_bundle_path": intake_bundle_input,
        "delivery_receipt_register_path": receipt_input,
        "delivery_checklist_path": checklist_input,
        "movement_objects_path": movement_objects_input,
        "dispatch_execution_queue_path": dispatch_queue_input,
        "follow_up_tracker_path": follow_up_tracker_input,
        "signal_phase_dispatch_bundle_path": dispatch_bundle_input,
        "dispatch_log_repair_queue_path": dispatch_repair_queue_input,
        "dispatch_log_repair_log_path": dispatch_repair_log_input,
        "preview_limit": int(preview_limit),
    }

    pre_cycle_result = run_bari_signal_phase_runtime_cycle(
        output_dir=pre_runtime_cycle_output_dir,
        **common_cycle_kwargs,
    )

    pre_dispatch_log_path = (
        pre_runtime_cycle_output_dir / "dispatch_recording" / "dispatch_execution_log.csv"
    )
    pre_dispatch_log_rows = _read_csv_rows(pre_dispatch_log_path)
    if not pre_dispatch_log_rows:
        raise RuntimeError(
            f"Expected dispatch execution log rows at: {pre_dispatch_log_path}"
        )

    selected_row_found = False
    rehearsal_dispatch_log_rows: list[dict[str, Any]] = []
    for row in pre_dispatch_log_rows:
        updated_row = dict(row)
        if _clean_text(row.get("request_id")) == request_id:
            selected_row_found = True
            updated_row["execution_status"] = execution_status
            updated_row["execution_completed_at"] = execution_completed_at_value
            updated_row["execution_channel_used"] = execution_channel_used
            updated_row["execution_outcome"] = execution_outcome
            updated_row["response_received"] = response_received
            updated_row["response_summary"] = response_summary
            updated_row["protocol_reference"] = protocol_reference_value
            updated_row["evidence_path"] = evidence_path
            updated_row["execution_notes"] = execution_notes
        rehearsal_dispatch_log_rows.append(updated_row)

    if not selected_row_found:
        raise RuntimeError(
            f"Could not find request `{request_id}` in {pre_dispatch_log_path}"
        )

    rehearsal_dispatch_log_path = output_root / "rehearsal_dispatch_execution_log.csv"
    _write_csv(
        rehearsal_dispatch_log_path,
        rehearsal_dispatch_log_rows,
        list(rehearsal_dispatch_log_rows[0].keys()),
    )

    post_cycle_result = run_bari_signal_phase_runtime_cycle(
        output_dir=post_runtime_cycle_output_dir,
        dispatch_execution_log_path=rehearsal_dispatch_log_path,
        **common_cycle_kwargs,
    )

    pre_action_states = _action_state_by_request(
        pre_runtime_cycle_output_dir
        / "dispatch_cycle"
        / "runtime_action_queue"
        / "signal_phase_action_queue.json"
    )
    post_action_states = _action_state_by_request(
        post_runtime_cycle_output_dir
        / "dispatch_cycle"
        / "runtime_action_queue"
        / "signal_phase_action_queue.json"
    )
    pre_operator_states = _operator_state_by_request(
        pre_runtime_cycle_output_dir
        / "dispatch_cycle"
        / "runtime_operator_board"
        / "signal_phase_operator_board_bundle.json"
    )
    post_operator_states = _operator_state_by_request(
        post_runtime_cycle_output_dir
        / "dispatch_cycle"
        / "runtime_operator_board"
        / "signal_phase_operator_board_bundle.json"
    )
    comparison_rows = _comparison_rows(
        pre_action_states,
        post_action_states,
        pre_operator_states,
        post_operator_states,
        selected_request_id=request_id,
    )

    selected_request_transition = next(
        (
            row
            for row in comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_transition is None:
        raise RuntimeError(
            f"Could not compare request `{request_id}` in rehearsal outputs."
        )

    request_state_comparison_path = output_root / "request_state_comparison.csv"
    comparison_fieldnames = [
        "request_id",
        "selected_request",
        "signal_name",
        "priority_rank",
        "pre_action_category",
        "post_action_category",
        "pre_dispatch_status",
        "post_dispatch_status",
        "pre_response_status",
        "post_response_status",
        "pre_due_now",
        "post_due_now",
        "pre_source_stage",
        "post_source_stage",
        "pre_operator_queue_type",
        "post_operator_queue_type",
        "pre_operator_execution_route",
        "post_operator_execution_route",
        "pre_handoff_target_kind",
        "post_handoff_target_kind",
        "pre_hold_reason",
        "post_hold_reason",
        "state_changed",
    ]
    _write_csv(request_state_comparison_path, comparison_rows, comparison_fieldnames)

    summary = {
        "generated_at_utc": generated_at_utc,
        "request_count": len(comparison_rows),
        "changed_request_count": sum(
            1 for row in comparison_rows if row.get("state_changed") == "yes"
        ),
        "selected_request_changed": selected_request_transition["state_changed"],
        "selected_request_left_dispatch_action": (
            "yes"
            if selected_request_transition["pre_action_category"] == "dispatch_request_now"
            and selected_request_transition["post_action_category"] != "dispatch_request_now"
            else "no"
        ),
        "selected_request_left_dispatch_send": (
            "yes"
            if selected_request_transition["pre_operator_execution_route"] == "dispatch_send"
            and selected_request_transition["post_operator_execution_route"] != "dispatch_send"
            else "no"
        ),
        "pre_runtime_dispatch_action_count": int(
            pre_cycle_result["stats"].get("runtime_dispatch_action_count") or 0
        ),
        "post_runtime_dispatch_action_count": int(
            post_cycle_result["stats"].get("runtime_dispatch_action_count") or 0
        ),
        "pre_runtime_operator_board_ready_count": int(
            pre_cycle_result["stats"].get("runtime_operator_board_ready_count") or 0
        ),
        "post_runtime_operator_board_ready_count": int(
            post_cycle_result["stats"].get("runtime_operator_board_ready_count") or 0
        ),
        "pre_recording_unresolved_signalized_movement_total": int(
            pre_cycle_result["stats"].get("dispatch_recording_unresolved_signalized_movement_total") or 0
        ),
        "post_recording_unresolved_signalized_movement_total": int(
            post_cycle_result["stats"].get("dispatch_recording_unresolved_signalized_movement_total") or 0
        ),
        "pre_recording_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_recording_unresolved_signalized_crash_total") or 0
        ),
        "post_recording_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_recording_unresolved_signalized_crash_total") or 0
        ),
        "pre_validation_unresolved_signalized_movement_total": int(
            pre_cycle_result["stats"].get("dispatch_validation_unresolved_signalized_movement_total") or 0
        ),
        "post_validation_unresolved_signalized_movement_total": int(
            post_cycle_result["stats"].get("dispatch_validation_unresolved_signalized_movement_total") or 0
        ),
        "pre_validation_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_validation_unresolved_signalized_crash_total") or 0
        ),
        "post_validation_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_validation_unresolved_signalized_crash_total") or 0
        ),
        "pre_validation_accepted_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_validation_accepted_unresolved_signalized_crash_total")
            or 0
        ),
        "post_validation_accepted_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_validation_accepted_unresolved_signalized_crash_total")
            or 0
        ),
        "pre_validation_rejected_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_validation_rejected_unresolved_signalized_crash_total")
            or 0
        ),
        "post_validation_rejected_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_validation_rejected_unresolved_signalized_crash_total")
            or 0
        ),
        "pre_writeback_unresolved_signalized_movement_total": int(
            pre_cycle_result["stats"].get("dispatch_writeback_unresolved_signalized_movement_total") or 0
        ),
        "post_writeback_unresolved_signalized_movement_total": int(
            post_cycle_result["stats"].get("dispatch_writeback_unresolved_signalized_movement_total") or 0
        ),
        "pre_writeback_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_writeback_unresolved_signalized_crash_total") or 0
        ),
        "post_writeback_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_writeback_unresolved_signalized_crash_total") or 0
        ),
        "pre_writeback_ready_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("dispatch_writeback_ready_unresolved_signalized_crash_total")
            or 0
        ),
        "post_writeback_ready_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("dispatch_writeback_ready_unresolved_signalized_crash_total")
            or 0
        ),
        "pre_dispatch_cycle_unresolved_signalized_crash_total": int(
            pre_cycle_result["stats"].get("runtime_dispatch_cycle_unresolved_signalized_crash_total") or 0
        ),
        "post_dispatch_cycle_unresolved_signalized_crash_total": int(
            post_cycle_result["stats"].get("runtime_dispatch_cycle_unresolved_signalized_crash_total") or 0
        ),
        "post_recorded_execution_count": int(
            post_cycle_result["stats"].get("dispatch_recorded_execution_count") or 0
        ),
        "post_validated_execution_count": int(
            post_cycle_result["stats"].get("dispatch_validated_execution_count") or 0
        ),
        "post_writeback_ready_count": int(
            post_cycle_result["stats"].get("dispatch_writeback_ready_count") or 0
        ),
    }

    bundle_json_path = output_root / "signal_phase_runtime_rehearsal.json"
    bundle_md_path = output_root / "signal_phase_runtime_rehearsal.md"
    manifest_path = output_root / "signal_phase_runtime_rehearsal.manifest.json"

    payload = {
        "signal_phase_runtime_rehearsal_version": SIGNAL_PHASE_RUNTIME_REHEARSAL_VERSION,
        "signal_phase_runtime_rehearsal_contract_version": SIGNAL_PHASE_RUNTIME_REHEARSAL_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "selected_request_id": request_id,
        "summary": summary,
        "selected_request_transition": selected_request_transition,
        "inputs": {
            "signal_phase_delivery_intake_bundle_path": str(intake_bundle_input),
            "delivery_receipt_register_path": str(receipt_input),
            "delivery_checklist_path": str(checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "dispatch_execution_queue_path": str(dispatch_queue_input),
            "follow_up_tracker_path": str(follow_up_tracker_input),
            "signal_phase_dispatch_bundle_path": str(dispatch_bundle_input),
            "dispatch_log_repair_queue_path": str(dispatch_repair_queue_input),
            "dispatch_log_repair_log_path": str(dispatch_repair_log_input),
            "request_id": request_id,
            "execution_status": execution_status,
            "execution_completed_at": execution_completed_at_value,
            "execution_channel_used": execution_channel_used,
            "execution_outcome": execution_outcome,
            "response_received": response_received,
            "response_summary": response_summary,
            "protocol_reference": protocol_reference_value,
            "evidence_path": evidence_path,
            "execution_notes": execution_notes,
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "pre_runtime_cycle_manifest_path": str(pre_cycle_result["manifest_path"]),
            "post_runtime_cycle_manifest_path": str(post_cycle_result["manifest_path"]),
            "rehearsal_dispatch_execution_log_path": str(rehearsal_dispatch_log_path),
            "request_state_comparison_path": str(request_state_comparison_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_rehearsal_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_runtime_rehearsal_version": SIGNAL_PHASE_RUNTIME_REHEARSAL_VERSION,
        "contract": {
            "resource_name": "signal_phase_runtime_rehearsal",
            "public_contract_version": SIGNAL_PHASE_RUNTIME_REHEARSAL_CONTRACT_VERSION,
            "signal_phase_runtime_rehearsal_version": SIGNAL_PHASE_RUNTIME_REHEARSAL_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_runtime_rehearsal_runner",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "rehearsal_json_path": str(bundle_json_path),
            "rehearsal_json_sha256": _sha256(bundle_json_path),
            "rehearsal_md_path": str(bundle_md_path),
            "rehearsal_md_sha256": _sha256(bundle_md_path),
            **payload["outputs"],
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_delivery_intake_bundle",
                    intake_bundle_input,
                    _sha256(intake_bundle_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_receipt_register",
                    receipt_input,
                    _sha256(receipt_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_checklist",
                    checklist_input,
                    _sha256(checklist_input),
                ),
                _artifact_reference(
                    "movement_objects",
                    movement_objects_input,
                    _sha256(movement_objects_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue",
                    dispatch_queue_input,
                    _sha256(dispatch_queue_input),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker",
                    follow_up_tracker_input,
                    _sha256(follow_up_tracker_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_bundle",
                    dispatch_bundle_input,
                    _sha256(dispatch_bundle_input),
                ),
                *(
                    [
                        _artifact_reference(
                            "signal_phase_dispatch_repair_queue",
                            dispatch_repair_queue_input,
                            _sha256(dispatch_repair_queue_input),
                        )
                    ]
                    if dispatch_repair_queue_input.exists()
                    else []
                ),
                *(
                    [
                        _artifact_reference(
                            "signal_phase_dispatch_repair_log",
                            dispatch_repair_log_input,
                            _sha256(dispatch_repair_log_input),
                        )
                    ]
                    if dispatch_repair_log_input.exists()
                    else []
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_runtime_rehearsal_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_runtime_rehearsal_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
                _artifact_reference(
                    "signal_phase_runtime_rehearsal_request_comparison",
                    request_state_comparison_path,
                    _sha256(request_state_comparison_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_runtime_cycle_pre_manifest",
                    Path(pre_cycle_result["manifest_path"]),
                    _sha256(Path(pre_cycle_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_runtime_cycle_post_manifest",
                    Path(post_cycle_result["manifest_path"]),
                    _sha256(Path(post_cycle_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_runtime_rehearsal_dispatch_log",
                    rehearsal_dispatch_log_path,
                    _sha256(rehearsal_dispatch_log_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "json_path": str(bundle_json_path),
        "markdown_path": str(bundle_md_path),
        "stats": summary,
        "selected_request_transition": selected_request_transition,
        "outputs": payload["outputs"],
    }
