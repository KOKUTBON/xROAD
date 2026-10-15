"""Run the Bari support-derived validation and apply path in one pass."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_delivery_session import apply_validated_signal_phase_deliveries
from .signal_phase_support_validation_batch import run_bari_signal_phase_support_validation_batch


SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_VERSION = "signal_phase_support_apply_cycle_v1"
SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_CONTRACT_VERSION = "signal_phase_support_apply_cycle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _accepted_validation_manifest_paths(batch_payload: dict[str, Any]) -> list[str]:
    accepted_paths: list[str] = []
    for row in batch_payload.get("validation_results", []):
        if row.get("validation_outcome") != "accepted_for_ingestion":
            continue
        manifest_path = str(row.get("manifest_path") or "").strip()
        if manifest_path:
            accepted_paths.append(manifest_path)
    return accepted_paths


def _cycle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Apply Cycle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support-derived signal-phase path has run validation and conditional movement-layer application in sequence.",
        "",
        "## Summary",
        "",
        f"- action queue rows: `{payload['stats']['action_queue_count']}`",
        f"- validation candidates: `{payload['stats']['validation_candidate_count']}`",
        f"- executed validations: `{payload['stats']['executed_validation_count']}`",
        f"- accepted for ingestion: `{payload['stats']['accepted_for_ingestion_count']}`",
        f"- skipped non-validation actions: `{payload['stats']['skipped_non_validation_action_count']}`",
        f"- apply session executed: `{payload['stats']['delivery_session_executed']}`",
        f"- movements with phase timing: `{payload['stats']['movements_with_phase_timing']}`",
        f"- movements with phase mapping: `{payload['stats']['movements_with_phase_mapping']}`",
        "",
        "## Output Paths",
        "",
        f"- support validation manifest: `{payload['outputs']['support_validation_batch_manifest_path']}`",
        f"- apply session manifest: `{payload['outputs']['delivery_session_manifest_path'] or 'not_run'}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_support_apply_cycle(
    *,
    output_dir: str | Path = "data/processed/signal_phase_support_apply_cycles/bari",
    action_execution_ready_queue_path: str | Path = "data/reporting/signal_phase_support_action_queue/bari/action_execution_ready_queue.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    matched_records_path: str | Path | None = "data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    target_request_queue_path: str | Path | None = "data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    action_queue_input = Path(action_execution_ready_queue_path)
    checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)

    validation_output_dir = output_root / "support_validation_batch"
    session_output_dir = output_root / "delivery_session"

    validation_result = run_bari_signal_phase_support_validation_batch(
        output_dir=validation_output_dir,
        action_execution_ready_queue_path=action_queue_input,
        delivery_checklist_path=checklist_input,
        preview_limit=preview_limit,
    )

    validation_manifest = _load_json(Path(validation_result["manifest_path"]))
    batch_json_path = Path(validation_manifest["outputs"]["batch_json_path"])
    batch_payload = _load_json(batch_json_path)
    accepted_manifest_paths = _accepted_validation_manifest_paths(batch_payload)

    session_result: dict[str, Any] | None = None
    if accepted_manifest_paths:
        session_result = apply_validated_signal_phase_deliveries(
            movement_objects_input,
            accepted_manifest_paths,
            session_output_dir,
            matched_records_path=matched_records_path,
            target_request_queue_path=target_request_queue_path,
            baseline_movement_objects_path=movement_objects_input,
        )

    cycle_json_path = output_root / "signal_phase_support_apply_cycle.json"
    cycle_md_path = output_root / "signal_phase_support_apply_cycle.md"
    manifest_path = output_root / "signal_phase_support_apply_cycle.manifest.json"

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "generated_at_utc": generated_at_utc,
        "action_queue_count": int(validation_result["stats"]["action_queue_count"]),
        "validation_candidate_count": int(validation_result["stats"]["validation_candidate_count"]),
        "executed_validation_count": int(validation_result["stats"]["executed_validation_count"]),
        "accepted_for_ingestion_count": int(validation_result["stats"]["accepted_for_ingestion_count"]),
        "accepted_support_artifact_count": int(validation_result["stats"]["accepted_support_artifact_count"]),
        "partial_review_count": int(validation_result["stats"]["partial_review_count"]),
        "provider_fix_required_count": int(validation_result["stats"]["provider_fix_required_count"]),
        "skipped_non_validation_action_count": int(validation_result["stats"]["skipped_non_validation_action_count"]),
        "skipped_missing_validation_inputs_count": int(
            validation_result["stats"]["skipped_missing_validation_inputs_count"]
        ),
        "delivery_session_executed": session_result is not None,
        "delivery_session_manifest_count": len(accepted_manifest_paths),
        "movement_count": session_result["stats"]["movement_count"] if session_result else 0,
        "movements_with_phase_timing": session_result["stats"]["movements_with_phase_timing"] if session_result else 0,
        "movements_with_phase_mapping": session_result["stats"]["movements_with_phase_mapping"] if session_result else 0,
    }
    payload = {
        "signal_phase_support_apply_cycle_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_VERSION,
        "signal_phase_support_apply_cycle_contract_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "bari_signal_phase_support_apply_cycle_runner",
        },
        "stats": stats,
        "inputs": {
            "action_execution_ready_queue_path": str(action_queue_input),
            "delivery_checklist_path": str(checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "matched_records_path": str(matched_records_path) if matched_records_path is not None else None,
            "target_request_queue_path": (
                str(target_request_queue_path) if target_request_queue_path is not None else None
            ),
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "support_validation_batch_manifest_path": str(Path(validation_result["manifest_path"])),
            "delivery_session_manifest_path": (str(Path(session_result["manifest_path"])) if session_result else None),
            "cycle_json_path": str(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "manifest_path": str(manifest_path),
            "accepted_validation_manifest_paths": accepted_manifest_paths,
        },
    }
    cycle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    cycle_md_path.write_text(_cycle_markdown(payload), encoding="utf-8")

    supporting_outputs = [
        _artifact_reference(
            "signal_phase_support_validation_batch",
            Path(payload["outputs"]["support_validation_batch_manifest_path"]),
            _sha256(Path(payload["outputs"]["support_validation_batch_manifest_path"])),
        )
    ] + [
        _artifact_reference("signal_phase_delivery_validation", Path(path), _sha256(Path(path)))
        for path in accepted_manifest_paths
    ]
    if payload["outputs"]["delivery_session_manifest_path"]:
        supporting_outputs.append(
            _artifact_reference(
                "signal_phase_delivery_session",
                Path(payload["outputs"]["delivery_session_manifest_path"]),
                _sha256(Path(payload["outputs"]["delivery_session_manifest_path"])),
            )
        )

    manifest = {
        "signal_phase_support_apply_cycle_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_apply_cycle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_CONTRACT_VERSION,
            "signal_phase_support_apply_cycle_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_VERSION,
        },
        "source": payload["source"],
        "stats": stats,
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "cycle_json_path": str(cycle_json_path),
            "cycle_json_sha256": _sha256(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "cycle_md_sha256": _sha256(cycle_md_path),
            "support_validation_batch_manifest_path": payload["outputs"]["support_validation_batch_manifest_path"],
            "delivery_session_manifest_path": payload["outputs"]["delivery_session_manifest_path"],
            "accepted_validation_manifest_paths": accepted_manifest_paths,
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_action_execution_ready_queue",
                    action_queue_input,
                    _sha256(action_queue_input),
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
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_support_apply_cycle_json", cycle_json_path, _sha256(cycle_json_path)),
                _artifact_reference("signal_phase_support_apply_cycle_markdown", cycle_md_path, _sha256(cycle_md_path)),
            ],
            supporting_outputs=supporting_outputs,
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_support_apply_cycle_version": SIGNAL_PHASE_SUPPORT_APPLY_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
