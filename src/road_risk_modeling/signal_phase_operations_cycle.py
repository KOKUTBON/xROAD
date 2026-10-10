"""Run the Bari signal-phase operational stack in one pass."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_follow_up import build_bari_signal_phase_follow_up_bundle
from .signal_phase_follow_up_cycle import run_bari_signal_phase_follow_up_cycle
from .signal_phase_follow_up_execution import build_bari_signal_phase_follow_up_execution_bundle
from .signal_phase_follow_up_writeback import build_bari_signal_phase_follow_up_writeback_bundle
from .signal_phase_lifecycle import build_bari_signal_phase_lifecycle_report
from .signal_phase_receive_cycle import run_bari_signal_phase_receive_cycle
from .signal_phase_status_sync import build_bari_signal_phase_status_sync_bundle


SIGNAL_PHASE_OPERATIONS_CYCLE_VERSION = "signal_phase_operations_cycle_v1"
SIGNAL_PHASE_OPERATIONS_CYCLE_CONTRACT_VERSION = "signal_phase_operations_cycle_public_v1"


def _cycle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Operations Cycle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari receive-side and follow-up-side signal-phase stacks have been refreshed in one pass.",
        "",
        "## Summary",
        "",
        f"- monitored delivery rows: `{payload['stats']['receive_monitored_delivery_count']}`",
        f"- validation-ready rows: `{payload['stats']['receive_validation_ready_count']}`",
        f"- accepted-for-ingestion deliveries: `{payload['stats']['receive_accepted_for_ingestion_count']}`",
        f"- synced validated delivery rows: `{payload['stats']['status_sync_validated_count']}`",
        f"- lifecycle delivery items: `{payload['stats']['lifecycle_delivery_item_count']}`",
        f"- lifecycle pending follow-ups: `{payload['stats']['lifecycle_pending_follow_up_count']}`",
        f"- request-level follow-up packets: `{payload['stats']['follow_up_request_count']}`",
        f"- execution-ready follow-up packets: `{payload['stats']['follow_up_execution_ready_count']}`",
        f"- writeback-ready rows: `{payload['stats']['writeback_ready_count']}`",
        f"- runtime execution-ready rows after cycle: `{payload['stats']['runtime_execution_ready_count']}`",
        "",
        "## Child Outputs",
        "",
        f"- receive cycle: `{payload['outputs']['receive_cycle_manifest_path']}`",
        f"- status sync: `{payload['outputs']['status_sync_manifest_path']}`",
        f"- lifecycle report: `{payload['outputs']['lifecycle_manifest_path']}`",
        f"- follow-up bundle: `{payload['outputs']['follow_up_manifest_path']}`",
        f"- follow-up execution bundle: `{payload['outputs']['follow_up_execution_manifest_path']}`",
        f"- follow-up writeback bundle: `{payload['outputs']['follow_up_writeback_manifest_path']}`",
        f"- follow-up cycle: `{payload['outputs']['follow_up_cycle_manifest_path']}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_operations_cycle(
    *,
    output_dir: str | Path = "data/processed/signal_phase_operations_cycles/bari",
    signal_phase_delivery_intake_bundle_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    intake_bundle_input = Path(signal_phase_delivery_intake_bundle_path)
    receipt_register_input = Path(delivery_receipt_register_path)
    checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)
    dispatch_queue_input = Path(dispatch_execution_queue_path)
    follow_up_tracker_input = Path(follow_up_tracker_path)

    receive_output_dir = output_root / "receive_cycle"
    status_sync_output_dir = output_root / "status_sync"
    lifecycle_output_dir = output_root / "lifecycle"
    follow_up_output_dir = output_root / "follow_up"
    follow_up_execution_output_dir = output_root / "follow_up_execution"
    follow_up_writeback_output_dir = output_root / "follow_up_writeback"
    follow_up_cycle_output_dir = output_root / "follow_up_cycle"

    receive_result = run_bari_signal_phase_receive_cycle(
        output_dir=receive_output_dir,
        signal_phase_delivery_intake_bundle_path=intake_bundle_input,
        delivery_receipt_register_path=receipt_register_input,
        delivery_checklist_path=checklist_input,
        movement_objects_path=movement_objects_input,
        preview_limit=preview_limit,
    )
    receive_cycle_json_path = receive_output_dir / "signal_phase_receive_cycle.json"
    delivery_monitor_queue_path = receive_output_dir / "monitor" / "delivery_monitor_queue.csv"
    validation_batch_results_path = receive_output_dir / "validation_batch" / "validation_batch_results.csv"

    status_sync_result = build_bari_signal_phase_status_sync_bundle(
        output_dir=status_sync_output_dir,
        delivery_receipt_register_path=receipt_register_input,
        delivery_monitor_queue_path=delivery_monitor_queue_path,
        validation_batch_results_path=validation_batch_results_path,
        delivery_checklist_path=checklist_input,
        receive_cycle_path=receive_cycle_json_path,
    )
    synced_receipt_register_path = status_sync_output_dir / "delivery_receipt_register_synced.csv"

    lifecycle_result = build_bari_signal_phase_lifecycle_report(
        output_dir=lifecycle_output_dir,
        dispatch_execution_queue_path=dispatch_queue_input,
        follow_up_tracker_path=follow_up_tracker_input,
        delivery_receipt_register_path=receipt_register_input,
        delivery_monitor_queue_path=delivery_monitor_queue_path,
        validation_batch_results_path=validation_batch_results_path,
        receive_cycle_path=receive_cycle_json_path,
    )
    follow_up_agenda_path = lifecycle_output_dir / "follow_up_agenda.csv"

    follow_up_result = build_bari_signal_phase_follow_up_bundle(
        output_dir=follow_up_output_dir,
        dispatch_execution_queue_path=dispatch_queue_input,
        follow_up_agenda_path=follow_up_agenda_path,
        synced_receipt_register_path=synced_receipt_register_path,
    )
    follow_up_ready_queue_path = follow_up_output_dir / "follow_up_ready_queue.csv"

    follow_up_execution_result = build_bari_signal_phase_follow_up_execution_bundle(
        output_dir=follow_up_execution_output_dir,
        follow_up_ready_queue_path=follow_up_ready_queue_path,
        follow_up_tracker_path=follow_up_tracker_input,
    )

    follow_up_writeback_result = build_bari_signal_phase_follow_up_writeback_bundle(
        output_dir=follow_up_writeback_output_dir,
        dispatch_execution_queue_path=dispatch_queue_input,
        follow_up_tracker_path=follow_up_tracker_input,
        follow_up_execution_queue_path=follow_up_execution_output_dir / "follow_up_execution_queue.csv",
        follow_up_tracker_updates_path=follow_up_execution_output_dir / "follow_up_tracker_updates.csv",
    )

    follow_up_cycle_result = run_bari_signal_phase_follow_up_cycle(
        output_dir=follow_up_cycle_output_dir,
        follow_up_writeback_bundle_path=follow_up_writeback_output_dir
        / "signal_phase_follow_up_writeback_bundle.json",
        delivery_receipt_register_path=receipt_register_input,
        delivery_monitor_queue_path=delivery_monitor_queue_path,
        validation_batch_results_path=validation_batch_results_path,
        receive_cycle_path=receive_cycle_json_path,
        synced_receipt_register_path=synced_receipt_register_path,
    )

    cycle_json_path = output_root / "signal_phase_operations_cycle.json"
    cycle_md_path = output_root / "signal_phase_operations_cycle.md"
    manifest_path = output_root / "signal_phase_operations_cycle.manifest.json"

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "generated_at_utc": generated_at_utc,
        "receive_monitored_delivery_count": int(
            receive_result["stats"].get("monitored_delivery_count") or 0
        ),
        "receive_validation_ready_count": int(receive_result["stats"].get("validation_ready_count") or 0),
        "receive_accepted_for_ingestion_count": int(
            receive_result["stats"].get("accepted_for_ingestion_count") or 0
        ),
        "status_sync_validated_count": int(status_sync_result["stats"].get("validated_count") or 0),
        "lifecycle_delivery_item_count": int(lifecycle_result["stats"].get("delivery_item_count") or 0),
        "lifecycle_pending_follow_up_count": int(
            lifecycle_result["stats"].get("pending_follow_up_count") or 0
        ),
        "follow_up_request_count": int(follow_up_result["stats"].get("request_count") or 0),
        "follow_up_execution_ready_count": int(
            follow_up_execution_result["stats"].get("execution_ready_count") or 0
        ),
        "writeback_ready_count": int(follow_up_writeback_result["stats"].get("writeback_ready_count") or 0),
        "runtime_execution_ready_count": int(
            follow_up_cycle_result["stats"].get("runtime_execution_ready_count") or 0
        ),
    }

    payload = {
        "signal_phase_operations_cycle_version": SIGNAL_PHASE_OPERATIONS_CYCLE_VERSION,
        "signal_phase_operations_cycle_contract_version": SIGNAL_PHASE_OPERATIONS_CYCLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "stats": stats,
        "inputs": {
            "signal_phase_delivery_intake_bundle_path": str(intake_bundle_input),
            "delivery_receipt_register_path": str(receipt_register_input),
            "delivery_checklist_path": str(checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "dispatch_execution_queue_path": str(dispatch_queue_input),
            "follow_up_tracker_path": str(follow_up_tracker_input),
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "receive_cycle_manifest_path": str(receive_result["manifest_path"]),
            "status_sync_manifest_path": str(status_sync_result["manifest_path"]),
            "lifecycle_manifest_path": str(lifecycle_result["manifest_path"]),
            "follow_up_manifest_path": str(follow_up_result["manifest_path"]),
            "follow_up_execution_manifest_path": str(follow_up_execution_result["manifest_path"]),
            "follow_up_writeback_manifest_path": str(follow_up_writeback_result["manifest_path"]),
            "follow_up_cycle_manifest_path": str(follow_up_cycle_result["manifest_path"]),
        },
    }
    cycle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    cycle_md_path.write_text(_cycle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_operations_cycle_version": SIGNAL_PHASE_OPERATIONS_CYCLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_operations_cycle",
            "public_contract_version": SIGNAL_PHASE_OPERATIONS_CYCLE_CONTRACT_VERSION,
            "signal_phase_operations_cycle_version": SIGNAL_PHASE_OPERATIONS_CYCLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_operations_cycle_runner",
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
                    receipt_register_input,
                    _sha256(receipt_register_input),
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
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_operations_cycle_json",
                    cycle_json_path,
                    _sha256(cycle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_operations_cycle_markdown",
                    cycle_md_path,
                    _sha256(cycle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_receive_cycle",
                    Path(receive_result["manifest_path"]),
                    _sha256(Path(receive_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_status_sync_bundle",
                    Path(status_sync_result["manifest_path"]),
                    _sha256(Path(status_sync_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_lifecycle_report",
                    Path(lifecycle_result["manifest_path"]),
                    _sha256(Path(lifecycle_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_bundle",
                    Path(follow_up_result["manifest_path"]),
                    _sha256(Path(follow_up_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_execution_bundle",
                    Path(follow_up_execution_result["manifest_path"]),
                    _sha256(Path(follow_up_execution_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_writeback_bundle",
                    Path(follow_up_writeback_result["manifest_path"]),
                    _sha256(Path(follow_up_writeback_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_cycle",
                    Path(follow_up_cycle_result["manifest_path"]),
                    _sha256(Path(follow_up_cycle_result["manifest_path"])),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_operations_cycle_version": SIGNAL_PHASE_OPERATIONS_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
