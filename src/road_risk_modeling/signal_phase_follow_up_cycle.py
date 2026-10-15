"""Run Bari signal-phase follow-up writeback outputs through the downstream follow-up stack."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_follow_up import build_bari_signal_phase_follow_up_bundle
from .signal_phase_follow_up_execution import build_bari_signal_phase_follow_up_execution_bundle
from .signal_phase_lifecycle import build_bari_signal_phase_lifecycle_report


SIGNAL_PHASE_FOLLOW_UP_CYCLE_VERSION = "signal_phase_follow_up_cycle_v1"
SIGNAL_PHASE_FOLLOW_UP_CYCLE_CONTRACT_VERSION = "signal_phase_follow_up_cycle_public_v1"


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


def _cycle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Follow-up Cycle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari follow-up writeback outputs have been propagated through a refreshed lifecycle board, request-level follow-up queue, and execution queue.",
        "",
        "## Summary",
        "",
        f"- writeback-ready rows: `{payload['stats']['writeback_ready_count']}`",
        f"- dispatch rows updated in writeback: `{payload['stats']['dispatch_rows_updated_count']}`",
        f"- tracker rows completed in writeback: `{payload['stats']['tracker_rows_completed_count']}`",
        f"- runtime lifecycle delivery items: `{payload['stats']['runtime_lifecycle_delivery_item_count']}`",
        f"- runtime pending follow-ups: `{payload['stats']['runtime_lifecycle_pending_follow_up_count']}`",
        f"- runtime due follow-ups: `{payload['stats']['runtime_lifecycle_due_follow_up_count']}`",
        f"- runtime request packets: `{payload['stats']['runtime_follow_up_request_count']}`",
        f"- runtime follow-ups due now: `{payload['stats']['runtime_follow_up_due_now_count']}`",
        f"- runtime execution-ready requests: `{payload['stats']['runtime_execution_ready_count']}`",
        f"- runtime internal holds: `{payload['stats']['runtime_internal_hold_count']}`",
        "",
        "## Output Manifests",
        "",
        f"- Lifecycle: `{payload['outputs']['runtime_lifecycle_manifest_path']}`",
        f"- Follow-up bundle: `{payload['outputs']['runtime_follow_up_manifest_path']}`",
        f"- Follow-up execution bundle: `{payload['outputs']['runtime_follow_up_execution_manifest_path']}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_follow_up_cycle(
    *,
    output_dir: str | Path = "data/processed/signal_phase_follow_up_cycles/bari",
    follow_up_writeback_bundle_path: str | Path = "data/reporting/signal_phase_follow_up_writeback/bari/signal_phase_follow_up_writeback_bundle.json",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_monitor_queue_path: str | Path = "data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    validation_batch_results_path: str | Path = "data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    receive_cycle_path: str | Path = "data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
    synced_receipt_register_path: str | Path = "data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    writeback_bundle_input = Path(follow_up_writeback_bundle_path)
    receipt_input = Path(delivery_receipt_register_path)
    monitor_input = Path(delivery_monitor_queue_path)
    validation_input = Path(validation_batch_results_path)
    receive_cycle_input = Path(receive_cycle_path)
    synced_receipt_input = Path(synced_receipt_register_path)

    writeback_bundle = _load_json(writeback_bundle_input)
    writeback_outputs = writeback_bundle.get("outputs", {})
    synced_dispatch_value = _clean_text(writeback_outputs.get("synced_dispatch_execution_queue_path"))
    synced_tracker_value = _clean_text(writeback_outputs.get("synced_follow_up_tracker_path"))
    if not synced_dispatch_value or not synced_tracker_value:
        raise RuntimeError(
            "Follow-up writeback bundle must include synced dispatch and synced tracker paths."
        )

    synced_dispatch_input = Path(synced_dispatch_value)
    synced_tracker_input = Path(synced_tracker_value)
    if not synced_dispatch_input.exists():
        raise RuntimeError(f"Synced dispatch queue not found: {synced_dispatch_input}")
    if not synced_tracker_input.exists():
        raise RuntimeError(f"Synced follow-up tracker not found: {synced_tracker_input}")

    lifecycle_output_dir = output_root / "runtime_lifecycle"
    follow_up_output_dir = output_root / "runtime_follow_up"
    follow_up_execution_output_dir = output_root / "runtime_follow_up_execution"

    lifecycle_result = build_bari_signal_phase_lifecycle_report(
        output_dir=lifecycle_output_dir,
        dispatch_execution_queue_path=synced_dispatch_input,
        follow_up_tracker_path=synced_tracker_input,
        delivery_receipt_register_path=receipt_input,
        delivery_monitor_queue_path=monitor_input,
        validation_batch_results_path=validation_input,
        receive_cycle_path=receive_cycle_input,
    )
    runtime_follow_up_agenda_path = lifecycle_output_dir / "follow_up_agenda.csv"

    follow_up_result = build_bari_signal_phase_follow_up_bundle(
        output_dir=follow_up_output_dir,
        dispatch_execution_queue_path=synced_dispatch_input,
        follow_up_agenda_path=runtime_follow_up_agenda_path,
        synced_receipt_register_path=synced_receipt_input,
    )
    runtime_follow_up_ready_queue_path = follow_up_output_dir / "follow_up_ready_queue.csv"

    follow_up_execution_result = build_bari_signal_phase_follow_up_execution_bundle(
        output_dir=follow_up_execution_output_dir,
        follow_up_ready_queue_path=runtime_follow_up_ready_queue_path,
        follow_up_tracker_path=synced_tracker_input,
    )

    cycle_json_path = output_root / "signal_phase_follow_up_cycle.json"
    cycle_md_path = output_root / "signal_phase_follow_up_cycle.md"
    manifest_path = output_root / "signal_phase_follow_up_cycle.manifest.json"

    writeback_summary = writeback_bundle.get("summary", {})
    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "generated_at_utc": generated_at_utc,
        "writeback_ready_count": int(writeback_summary.get("writeback_ready_count") or 0),
        "dispatch_rows_updated_count": int(writeback_summary.get("dispatch_rows_updated_count") or 0),
        "tracker_rows_completed_count": int(writeback_summary.get("tracker_rows_completed_count") or 0),
        "runtime_lifecycle_delivery_item_count": int(
            lifecycle_result["stats"].get("delivery_item_count") or 0
        ),
        "runtime_lifecycle_pending_follow_up_count": int(
            lifecycle_result["stats"].get("pending_follow_up_count") or 0
        ),
        "runtime_lifecycle_due_follow_up_count": int(
            lifecycle_result["stats"].get("due_follow_up_count") or 0
        ),
        "runtime_follow_up_request_count": int(follow_up_result["stats"].get("request_count") or 0),
        "runtime_follow_up_due_now_count": int(follow_up_result["stats"].get("due_now_count") or 0),
        "runtime_execution_ready_count": int(
            follow_up_execution_result["stats"].get("execution_ready_count") or 0
        ),
        "runtime_internal_hold_count": int(
            follow_up_execution_result["stats"].get("internal_hold_count") or 0
        ),
    }

    payload = {
        "signal_phase_follow_up_cycle_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_VERSION,
        "signal_phase_follow_up_cycle_contract_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "stats": stats,
        "inputs": {
            "follow_up_writeback_bundle_path": str(writeback_bundle_input),
            "synced_dispatch_execution_queue_path": str(synced_dispatch_input),
            "synced_follow_up_tracker_path": str(synced_tracker_input),
            "delivery_receipt_register_path": str(receipt_input),
            "delivery_monitor_queue_path": str(monitor_input),
            "validation_batch_results_path": str(validation_input),
            "receive_cycle_path": str(receive_cycle_input),
            "synced_receipt_register_path": str(synced_receipt_input),
        },
        "outputs": {
            "runtime_lifecycle_manifest_path": str(lifecycle_result["manifest_path"]),
            "runtime_follow_up_manifest_path": str(follow_up_result["manifest_path"]),
            "runtime_follow_up_execution_manifest_path": str(
                follow_up_execution_result["manifest_path"]
            ),
        },
    }
    cycle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    cycle_md_path.write_text(_cycle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_follow_up_cycle_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_follow_up_cycle",
            "public_contract_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_CONTRACT_VERSION,
            "signal_phase_follow_up_cycle_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_follow_up_cycle_runner",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "cycle_json_path": str(cycle_json_path),
            "cycle_json_sha256": _sha256(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "cycle_md_sha256": _sha256(cycle_md_path),
            "runtime_lifecycle_manifest_path": str(lifecycle_result["manifest_path"]),
            "runtime_follow_up_manifest_path": str(follow_up_result["manifest_path"]),
            "runtime_follow_up_execution_manifest_path": str(
                follow_up_execution_result["manifest_path"]
            ),
        },
        "stats": stats,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_follow_up_writeback_bundle",
                    writeback_bundle_input,
                    _sha256(writeback_bundle_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue_synced",
                    synced_dispatch_input,
                    _sha256(synced_dispatch_input),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker_synced",
                    synced_tracker_input,
                    _sha256(synced_tracker_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_receipt_register",
                    receipt_input,
                    _sha256(receipt_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_monitor_queue",
                    monitor_input,
                    _sha256(monitor_input),
                ),
                _artifact_reference(
                    "signal_phase_validation_batch_results",
                    validation_input,
                    _sha256(validation_input),
                ),
                _artifact_reference(
                    "signal_phase_receive_cycle_json",
                    receive_cycle_input,
                    _sha256(receive_cycle_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_receipt_register_synced",
                    synced_receipt_input,
                    _sha256(synced_receipt_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_follow_up_cycle_json",
                    cycle_json_path,
                    _sha256(cycle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_cycle_markdown",
                    cycle_md_path,
                    _sha256(cycle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_lifecycle_report_manifest",
                    Path(lifecycle_result["manifest_path"]),
                    _sha256(Path(lifecycle_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_bundle_manifest",
                    Path(follow_up_result["manifest_path"]),
                    _sha256(Path(follow_up_result["manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_execution_bundle_manifest",
                    Path(follow_up_execution_result["manifest_path"]),
                    _sha256(Path(follow_up_execution_result["manifest_path"])),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_follow_up_cycle_version": SIGNAL_PHASE_FOLLOW_UP_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
