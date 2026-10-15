"""Run the Bari signal-phase receive-side and dispatch-side stacks in one pass."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_action_queue import build_bari_signal_phase_action_queue
from .signal_phase_dispatch_cycle import run_bari_signal_phase_dispatch_cycle
from .signal_phase_dispatch_execution import (
    build_bari_signal_phase_dispatch_execution_bundle,
)
from .signal_phase_dispatch_recording import (
    build_bari_signal_phase_dispatch_recording_bundle,
)
from .signal_phase_dispatch_repair import (
    build_bari_signal_phase_dispatch_repair_bundle,
)
from .signal_phase_dispatch_repair_execution import (
    build_bari_signal_phase_dispatch_repair_execution_bundle,
)
from .signal_phase_dispatch_repair_recording import (
    build_bari_signal_phase_dispatch_repair_recording_bundle,
)
from .signal_phase_dispatch_repair_status import (
    build_bari_signal_phase_dispatch_repair_status_bundle,
)
from .signal_phase_dispatch_validation import (
    build_bari_signal_phase_dispatch_validation_bundle,
)
from .signal_phase_dispatch_writeback import (
    build_bari_signal_phase_dispatch_writeback_bundle,
)
from .signal_phase_operations_cycle import run_bari_signal_phase_operations_cycle


SIGNAL_PHASE_RUNTIME_CYCLE_VERSION = "signal_phase_runtime_cycle_v1"
SIGNAL_PHASE_RUNTIME_CYCLE_CONTRACT_VERSION = "signal_phase_runtime_cycle_public_v1"


def _cycle_markdown(payload: dict[str, object]) -> str:
    stats = payload["stats"]
    outputs = payload["outputs"]
    lines = [
        "# Bari Signal-Phase Runtime Cycle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari receive-side refresh, request-level dispatch refresh, dispatch validation, dispatch writeback, and synced dispatch runtime refresh have been rebuilt in one pass.",
        "",
        "## Summary",
        "",
        f"- receive monitored delivery rows: `{stats['receive_monitored_delivery_count']}`",
        f"- lifecycle delivery items: `{stats['operations_lifecycle_delivery_item_count']}`",
        f"- request-level dispatch actions before writeback: `{stats['dispatch_action_count']}`",
        f"- execution-ready initial sends: `{stats['dispatch_execution_ready_count']}`",
        f"- logged initial sends applied: `{stats['dispatch_recorded_execution_count']}`",
        f"- validated initial sends accepted: `{stats['dispatch_validated_execution_count']}`",
        f"- blocked initial send rows: `{stats['dispatch_blocked_execution_count']}`",
        f"- dispatch-log repair requests: `{stats['dispatch_repair_request_count']}`",
        f"- dispatch-log repair execution-ready rows: `{stats['dispatch_repair_execution_ready_count']}`",
        f"- repair-ready log entries applied: `{stats['dispatch_repair_applied_count']}`",
        f"- repair rows still pending correction: `{stats['dispatch_repair_pending_count']}`",
        f"- repair rows ready for validation: `{stats['dispatch_repair_ready_for_validation_count']}`",
        f"- repair rows still blocked after staged fixes: `{stats['dispatch_repair_still_blocked_count']}`",
        f"- repair rows cleared for writeback: `{stats['dispatch_repair_cleared_count']}`",
        f"- writeback-ready initial sends: `{stats['dispatch_writeback_ready_count']}`",
        f"- recording unresolved signalized movements: `{stats['dispatch_recording_unresolved_signalized_movement_total']}`",
        f"- recording unresolved signalized crashes: `{stats['dispatch_recording_unresolved_signalized_crash_total']}`",
        f"- validation unresolved signalized movements: `{stats['dispatch_validation_unresolved_signalized_movement_total']}`",
        f"- validation unresolved signalized crashes: `{stats['dispatch_validation_unresolved_signalized_crash_total']}`",
        f"- validation accepted unresolved signalized crashes: `{stats['dispatch_validation_accepted_unresolved_signalized_crash_total']}`",
        f"- validation blocked unresolved signalized crashes: `{stats['dispatch_validation_rejected_unresolved_signalized_crash_total']}`",
        f"- writeback unresolved signalized movements: `{stats['dispatch_writeback_unresolved_signalized_movement_total']}`",
        f"- writeback unresolved signalized crashes: `{stats['dispatch_writeback_unresolved_signalized_crash_total']}`",
        f"- writeback-ready unresolved signalized crashes: `{stats['dispatch_writeback_ready_unresolved_signalized_crash_total']}`",
        f"- dispatch-cycle carried unresolved signalized crashes: `{stats['runtime_dispatch_cycle_unresolved_signalized_crash_total']}`",
        f"- runtime action-queue requests after writeback: `{stats['runtime_action_request_count']}`",
        f"- runtime operator execution-ready actions after writeback: `{stats['runtime_action_execution_ready_count']}`",
        f"- runtime operator internal holds after writeback: `{stats['runtime_action_internal_hold_count']}`",
        f"- runtime action handoff-ready rows after writeback: `{stats['runtime_action_handoff_ready_count']}`",
        f"- runtime operator-board rows after writeback: `{stats['runtime_operator_board_ready_count']}`",
        f"- runtime dispatch actions after writeback: `{stats['runtime_dispatch_action_count']}`",
        f"- runtime follow-up actions after writeback: `{stats['runtime_follow_up_action_count']}`",
        "",
        "## Child Outputs",
        "",
        f"- operations cycle: `{outputs['operations_cycle_manifest_path']}`",
        f"- dispatch action queue: `{outputs['dispatch_action_queue_manifest_path']}`",
        f"- dispatch execution bundle: `{outputs['dispatch_execution_manifest_path']}`",
        f"- dispatch recording bundle: `{outputs['dispatch_recording_manifest_path']}`",
        f"- dispatch repair recording bundle: `{outputs['dispatch_repair_recording_manifest_path']}`",
        f"- dispatch validation bundle: `{outputs['dispatch_validation_manifest_path']}`",
        f"- dispatch repair bundle: `{outputs['dispatch_repair_manifest_path']}`",
        f"- dispatch repair execution bundle: `{outputs['dispatch_repair_execution_manifest_path']}`",
        f"- dispatch repair status bundle: `{outputs['dispatch_repair_status_manifest_path']}`",
        f"- dispatch writeback bundle: `{outputs['dispatch_writeback_manifest_path']}`",
        f"- dispatch cycle: `{outputs['dispatch_cycle_manifest_path']}`",
        f"- runtime action execution bundle: `{outputs['runtime_action_execution_manifest_path']}`",
        f"- runtime action handoff bundle: `{outputs['runtime_action_handoff_manifest_path']}`",
        f"- runtime operator board bundle: `{outputs['runtime_operator_board_manifest_path']}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_runtime_cycle(
    *,
    output_dir: str | Path = "data/processed/signal_phase_runtime_cycles/bari",
    signal_phase_delivery_intake_bundle_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    signal_phase_dispatch_bundle_path: str | Path = "data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    dispatch_execution_log_path: str | Path | None = None,
    dispatch_log_repair_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    dispatch_log_repair_log_path: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    preview_limit: int = 10,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    intake_bundle_input = Path(signal_phase_delivery_intake_bundle_path)
    receipt_input = Path(delivery_receipt_register_path)
    checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)
    dispatch_queue_input = Path(dispatch_execution_queue_path)
    follow_up_tracker_input = Path(follow_up_tracker_path)
    dispatch_bundle_input = Path(signal_phase_dispatch_bundle_path)
    dispatch_log_input = (
        Path(dispatch_execution_log_path) if dispatch_execution_log_path is not None else None
    )
    dispatch_repair_queue_input = Path(dispatch_log_repair_queue_path)
    dispatch_repair_log_input = Path(dispatch_log_repair_log_path)
    dispatch_packet_dir = dispatch_bundle_input.parent / "dispatch_packets"

    operations_output_dir = output_root / "operations_cycle"
    dispatch_action_queue_output_dir = output_root / "dispatch_action_queue"
    dispatch_execution_output_dir = output_root / "dispatch_execution"
    dispatch_recording_output_dir = output_root / "dispatch_recording"
    dispatch_repair_recording_output_dir = output_root / "dispatch_repair_recording"
    dispatch_validation_output_dir = output_root / "dispatch_validation"
    dispatch_repair_output_dir = output_root / "dispatch_repair"
    dispatch_repair_execution_output_dir = output_root / "dispatch_repair_execution"
    dispatch_repair_status_output_dir = output_root / "dispatch_repair_status"
    dispatch_writeback_output_dir = output_root / "dispatch_writeback"
    dispatch_cycle_output_dir = output_root / "dispatch_cycle"

    operations_result = run_bari_signal_phase_operations_cycle(
        output_dir=operations_output_dir,
        signal_phase_delivery_intake_bundle_path=intake_bundle_input,
        delivery_receipt_register_path=receipt_input,
        delivery_checklist_path=checklist_input,
        movement_objects_path=movement_objects_input,
        dispatch_execution_queue_path=dispatch_queue_input,
        follow_up_tracker_path=follow_up_tracker_input,
        preview_limit=preview_limit,
    )
    operations_cycle_json_path = operations_output_dir / "signal_phase_operations_cycle.json"

    action_queue_result = build_bari_signal_phase_action_queue(
        output_dir=dispatch_action_queue_output_dir,
        signal_phase_operations_cycle_path=operations_cycle_json_path,
        dispatch_execution_queue_path=dispatch_queue_input,
        signal_phase_dispatch_bundle_path=dispatch_bundle_input,
    )

    dispatch_execution_result = build_bari_signal_phase_dispatch_execution_bundle(
        output_dir=dispatch_execution_output_dir,
        signal_phase_action_queue_path=dispatch_action_queue_output_dir / "action_queue.csv",
        dispatch_execution_queue_path=dispatch_queue_input,
        dispatch_packet_dir=dispatch_packet_dir,
    )

    dispatch_recording_result = build_bari_signal_phase_dispatch_recording_bundle(
        output_dir=dispatch_recording_output_dir,
        dispatch_execution_ready_queue_path=dispatch_execution_output_dir
        / "dispatch_execution_ready_queue.csv",
        dispatch_execution_log_path=dispatch_log_input,
    )

    dispatch_repair_recording_result = (
        build_bari_signal_phase_dispatch_repair_recording_bundle(
            output_dir=dispatch_repair_recording_output_dir,
            dispatch_execution_runtime_queue_path=dispatch_recording_output_dir
            / "dispatch_execution_queue_runtime.csv",
            dispatch_log_repair_queue_path=dispatch_repair_queue_input,
            dispatch_log_repair_log_path=dispatch_repair_log_input,
        )
    )

    dispatch_validation_result = build_bari_signal_phase_dispatch_validation_bundle(
        output_dir=dispatch_validation_output_dir,
        dispatch_execution_runtime_queue_path=dispatch_repair_recording_output_dir
        / "dispatch_execution_queue_runtime_repaired.csv",
    )

    dispatch_repair_result = build_bari_signal_phase_dispatch_repair_bundle(
        output_dir=dispatch_repair_output_dir,
        dispatch_validation_queue_path=dispatch_validation_output_dir
        / "dispatch_execution_queue_validated.csv",
    )

    dispatch_repair_execution_result = (
        build_bari_signal_phase_dispatch_repair_execution_bundle(
            output_dir=dispatch_repair_execution_output_dir,
            dispatch_log_repair_queue_path=dispatch_repair_output_dir
            / "dispatch_log_repair_queue.csv",
            dispatch_log_repair_log_path=dispatch_repair_log_input,
        )
    )

    dispatch_repair_status_result = build_bari_signal_phase_dispatch_repair_status_bundle(
        output_dir=dispatch_repair_status_output_dir,
        dispatch_log_repair_queue_path=dispatch_repair_output_dir / "dispatch_log_repair_queue.csv",
        dispatch_log_repair_log_path=dispatch_repair_log_input,
        dispatch_repair_execution_ready_queue_path=dispatch_repair_execution_output_dir
        / "dispatch_repair_execution_ready_queue.csv",
        dispatch_repair_internal_hold_queue_path=dispatch_repair_execution_output_dir
        / "dispatch_repair_internal_hold_queue.csv",
        dispatch_validation_queue_path=dispatch_validation_output_dir
        / "dispatch_execution_queue_validated.csv",
    )

    dispatch_writeback_result = build_bari_signal_phase_dispatch_writeback_bundle(
        output_dir=dispatch_writeback_output_dir,
        dispatch_execution_queue_path=dispatch_queue_input,
        follow_up_tracker_path=follow_up_tracker_input,
        dispatch_execution_ready_queue_path=dispatch_validation_output_dir
        / "dispatch_execution_queue_validated.csv",
        dispatch_tracker_updates_path=dispatch_execution_output_dir / "dispatch_tracker_updates.csv",
    )

    dispatch_cycle_result = run_bari_signal_phase_dispatch_cycle(
        output_dir=dispatch_cycle_output_dir,
        signal_phase_dispatch_writeback_bundle_path=dispatch_writeback_output_dir
        / "signal_phase_dispatch_writeback_bundle.json",
        delivery_receipt_register_path=receipt_input,
        delivery_monitor_queue_path=operations_output_dir
        / "receive_cycle"
        / "monitor"
        / "delivery_monitor_queue.csv",
        validation_batch_results_path=operations_output_dir
        / "receive_cycle"
        / "validation_batch"
        / "validation_batch_results.csv",
        receive_cycle_path=operations_output_dir / "receive_cycle" / "signal_phase_receive_cycle.json",
        synced_receipt_register_path=operations_output_dir
        / "status_sync"
        / "delivery_receipt_register_synced.csv",
        signal_phase_operations_cycle_path=operations_cycle_json_path,
        signal_phase_dispatch_bundle_path=dispatch_bundle_input,
        dispatch_log_repair_queue_path=dispatch_repair_output_dir / "dispatch_log_repair_queue.csv",
        dispatch_repair_status_path=dispatch_repair_status_output_dir / "dispatch_repair_status.csv",
    )

    cycle_json_path = output_root / "signal_phase_runtime_cycle.json"
    cycle_md_path = output_root / "signal_phase_runtime_cycle.md"
    manifest_path = output_root / "signal_phase_runtime_cycle.manifest.json"

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "generated_at_utc": generated_at_utc,
        "receive_monitored_delivery_count": int(
            operations_result["stats"].get("receive_monitored_delivery_count") or 0
        ),
        "operations_lifecycle_delivery_item_count": int(
            operations_result["stats"].get("lifecycle_delivery_item_count") or 0
        ),
        "dispatch_action_count": int(action_queue_result["stats"].get("dispatch_action_count") or 0),
        "dispatch_execution_ready_count": int(
            dispatch_execution_result["stats"].get("execution_ready_count") or 0
        ),
        "dispatch_recorded_execution_count": int(
            dispatch_recording_result["stats"].get("applied_execution_count") or 0
        ),
        "dispatch_recording_unresolved_signalized_movement_total": int(
            dispatch_recording_result["stats"].get("unresolved_signalized_movement_total") or 0
        ),
        "dispatch_recording_unresolved_signalized_crash_total": int(
            dispatch_recording_result["stats"].get("unresolved_signalized_crash_total") or 0
        ),
        "dispatch_validated_execution_count": int(
            dispatch_validation_result["stats"].get("accepted_for_writeback_count") or 0
        ),
        "dispatch_blocked_execution_count": int(
            dispatch_validation_result["stats"].get("rejected_for_writeback_count") or 0
        ),
        "dispatch_validation_unresolved_signalized_movement_total": int(
            dispatch_validation_result["stats"].get("unresolved_signalized_movement_total") or 0
        ),
        "dispatch_validation_unresolved_signalized_crash_total": int(
            dispatch_validation_result["stats"].get("unresolved_signalized_crash_total") or 0
        ),
        "dispatch_validation_accepted_unresolved_signalized_crash_total": int(
            dispatch_validation_result["stats"].get("accepted_unresolved_signalized_crash_total") or 0
        ),
        "dispatch_validation_rejected_unresolved_signalized_crash_total": int(
            dispatch_validation_result["stats"].get("rejected_unresolved_signalized_crash_total") or 0
        ),
        "dispatch_repair_execution_ready_count": int(
            dispatch_repair_execution_result["stats"].get("execution_ready_count") or 0
        ),
        "dispatch_repair_applied_count": int(
            dispatch_repair_recording_result["stats"].get("applied_repair_count") or 0
        ),
        "dispatch_repair_pending_count": int(
            dispatch_repair_status_result["stats"].get("pending_repair_count") or 0
        ),
        "dispatch_repair_ready_for_validation_count": int(
            dispatch_repair_status_result["stats"].get("ready_for_validation_count") or 0
        ),
        "dispatch_repair_still_blocked_count": int(
            dispatch_repair_status_result["stats"].get("still_blocked_count") or 0
        ),
        "dispatch_repair_cleared_count": int(
            dispatch_repair_status_result["stats"].get("cleared_for_writeback_count") or 0
        ),
        "dispatch_repair_request_count": int(
            dispatch_repair_result["stats"].get("repair_request_count") or 0
        ),
        "dispatch_writeback_ready_count": int(
            dispatch_writeback_result["stats"].get("writeback_ready_count") or 0
        ),
        "dispatch_writeback_unresolved_signalized_movement_total": int(
            dispatch_writeback_result["stats"].get("unresolved_signalized_movement_total") or 0
        ),
        "dispatch_writeback_unresolved_signalized_crash_total": int(
            dispatch_writeback_result["stats"].get("unresolved_signalized_crash_total") or 0
        ),
        "dispatch_writeback_ready_unresolved_signalized_crash_total": int(
            dispatch_writeback_result["stats"].get("writeback_ready_unresolved_signalized_crash_total")
            or 0
        ),
        "runtime_action_request_count": int(
            dispatch_cycle_result["stats"].get("runtime_action_request_count") or 0
        ),
        "runtime_action_execution_ready_count": int(
            dispatch_cycle_result["stats"].get("runtime_action_execution_ready_count") or 0
        ),
        "runtime_action_internal_hold_count": int(
            dispatch_cycle_result["stats"].get("runtime_action_internal_hold_count") or 0
        ),
        "runtime_action_handoff_ready_count": int(
            dispatch_cycle_result["stats"].get("runtime_action_handoff_ready_count") or 0
        ),
        "runtime_operator_board_ready_count": int(
            dispatch_cycle_result["stats"].get("runtime_operator_board_ready_count") or 0
        ),
        "runtime_dispatch_action_count": int(
            dispatch_cycle_result["stats"].get("runtime_dispatch_action_count") or 0
        ),
        "runtime_follow_up_action_count": int(
            dispatch_cycle_result["stats"].get("runtime_follow_up_action_count") or 0
        ),
        "runtime_dispatch_cycle_unresolved_signalized_crash_total": int(
            dispatch_cycle_result["stats"].get("writeback_unresolved_signalized_crash_total") or 0
        ),
    }

    payload = {
        "signal_phase_runtime_cycle_version": SIGNAL_PHASE_RUNTIME_CYCLE_VERSION,
        "signal_phase_runtime_cycle_contract_version": SIGNAL_PHASE_RUNTIME_CYCLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "stats": stats,
        "inputs": {
            "signal_phase_delivery_intake_bundle_path": str(intake_bundle_input),
            "delivery_receipt_register_path": str(receipt_input),
            "delivery_checklist_path": str(checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "dispatch_execution_queue_path": str(dispatch_queue_input),
            "follow_up_tracker_path": str(follow_up_tracker_input),
            "signal_phase_dispatch_bundle_path": str(dispatch_bundle_input),
            "dispatch_execution_log_path": str(dispatch_log_input) if dispatch_log_input else "",
            "dispatch_log_repair_queue_path": str(dispatch_repair_queue_input),
            "dispatch_log_repair_log_path": str(dispatch_repair_log_input),
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "operations_cycle_manifest_path": str(operations_result["manifest_path"]),
            "dispatch_action_queue_manifest_path": str(action_queue_result["manifest_path"]),
            "dispatch_execution_manifest_path": str(dispatch_execution_result["manifest_path"]),
            "dispatch_recording_manifest_path": str(dispatch_recording_result["manifest_path"]),
            "dispatch_repair_recording_manifest_path": str(
                dispatch_repair_recording_result["manifest_path"]
            ),
            "dispatch_validation_manifest_path": str(dispatch_validation_result["manifest_path"]),
            "dispatch_repair_manifest_path": str(dispatch_repair_result["manifest_path"]),
            "dispatch_repair_execution_manifest_path": str(
                dispatch_repair_execution_result["manifest_path"]
            ),
            "dispatch_repair_status_manifest_path": str(
                dispatch_repair_status_result["manifest_path"]
            ),
            "dispatch_writeback_manifest_path": str(dispatch_writeback_result["manifest_path"]),
            "dispatch_cycle_manifest_path": str(dispatch_cycle_result["manifest_path"]),
            "runtime_action_execution_manifest_path": str(
                dispatch_cycle_output_dir
                / "runtime_action_execution"
                / "signal_phase_action_execution_bundle.manifest.json"
            ),
            "runtime_action_handoff_manifest_path": str(
                dispatch_cycle_output_dir
                / "runtime_action_handoff"
                / "signal_phase_action_handoff_bundle.manifest.json"
            ),
            "runtime_operator_board_manifest_path": str(
                dispatch_cycle_output_dir
                / "runtime_operator_board"
                / "signal_phase_operator_board_bundle.manifest.json"
            ),
        },
    }
    cycle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    cycle_md_path.write_text(_cycle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_runtime_cycle_version": SIGNAL_PHASE_RUNTIME_CYCLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_runtime_cycle",
            "public_contract_version": SIGNAL_PHASE_RUNTIME_CYCLE_CONTRACT_VERSION,
            "signal_phase_runtime_cycle_version": SIGNAL_PHASE_RUNTIME_CYCLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_runtime_cycle_runner",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "cycle_json_path": str(cycle_json_path),
            "cycle_json_sha256": _sha256(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "cycle_md_sha256": _sha256(cycle_md_path),
            **payload["outputs"],
        },
        "stats": stats,
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
                            "signal_phase_dispatch_execution_log",
                            dispatch_log_input,
                            _sha256(dispatch_log_input),
                        )
                    ]
                    if dispatch_log_input is not None and dispatch_log_input.exists()
                    else []
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
                    "signal_phase_runtime_cycle_json",
                    cycle_json_path,
                    _sha256(cycle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_runtime_cycle_markdown",
                    cycle_md_path,
                    _sha256(cycle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_operations_cycle_manifest",
                    Path(operations_result["manifest_path"]),
                    _sha256(Path(operations_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_action_queue_manifest",
                    Path(action_queue_result["manifest_path"]),
                    _sha256(Path(action_queue_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_bundle_manifest",
                    Path(dispatch_execution_result["manifest_path"]),
                    _sha256(Path(dispatch_execution_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_recording_bundle_manifest",
                    Path(dispatch_recording_result["manifest_path"]),
                    _sha256(Path(dispatch_recording_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_repair_recording_bundle_manifest",
                    Path(dispatch_repair_recording_result["manifest_path"]),
                    _sha256(Path(dispatch_repair_recording_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_validation_bundle_manifest",
                    Path(dispatch_validation_result["manifest_path"]),
                    _sha256(Path(dispatch_validation_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_repair_bundle_manifest",
                    Path(dispatch_repair_result["manifest_path"]),
                    _sha256(Path(dispatch_repair_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_repair_execution_bundle_manifest",
                    Path(dispatch_repair_execution_result["manifest_path"]),
                    _sha256(Path(dispatch_repair_execution_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_repair_status_bundle_manifest",
                    Path(dispatch_repair_status_result["manifest_path"]),
                    _sha256(Path(dispatch_repair_status_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_writeback_bundle_manifest",
                    Path(dispatch_writeback_result["manifest_path"]),
                    _sha256(Path(dispatch_writeback_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_cycle_manifest",
                    Path(dispatch_cycle_result["manifest_path"]),
                    _sha256(Path(dispatch_cycle_result["manifest_path"])),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_runtime_cycle_version": SIGNAL_PHASE_RUNTIME_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
