"""Run the Bari live support-derived signal-phase stack in one pass."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_support_action_queue import build_bari_signal_phase_support_action_queue
from .signal_phase_support_apply_status import (
    build_bari_signal_phase_support_apply_status_bundle,
)
from .signal_phase_support_request_state import (
    build_bari_signal_phase_support_request_state_bundle,
)
from .signal_phase_support_operator_board import (
    build_bari_signal_phase_support_operator_board_bundle,
)
from .signal_phase_support_action_execution import (
    build_bari_signal_phase_support_action_execution_bundle,
)
from .signal_phase_support_action_handoff import (
    build_bari_signal_phase_support_action_handoff_bundle,
)
from .signal_phase_support_runtime_board import (
    build_bari_signal_phase_support_runtime_board_bundle,
)
from .signal_phase_support_runtime_action_queue import (
    build_bari_signal_phase_support_runtime_action_queue,
)
from .signal_phase_support_runtime_action_execution import (
    build_bari_signal_phase_support_runtime_action_execution_bundle,
)
from .signal_phase_support_workbook_completion import (
    build_bari_signal_phase_support_workbook_completion_bundle,
)
from .signal_phase_support_apply_cycle import run_bari_signal_phase_support_apply_cycle
from .signal_phase_support_status import build_bari_signal_phase_support_status_bundle
from .signal_phase_support_writeback import build_bari_signal_phase_support_writeback_bundle


SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_VERSION = "signal_phase_support_runtime_cycle_v1"
SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_CONTRACT_VERSION = (
    "signal_phase_support_runtime_cycle_public_v1"
)


def _cycle_markdown(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    outputs = payload["outputs"]
    lines = [
        "# Bari Signal-Phase Support Runtime Cycle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari live support-derived signal-phase stack has been rebuilt from workbooks through support validation and conditional movement-layer application in one pass.",
        "",
        "## Summary",
        "",
        f"- support requests: `{stats['support_request_count']}`",
        f"- manual workbook rows: `{stats['manual_workbook_row_count']}`",
        f"- pedestrian workbook rows: `{stats['pedestrian_workbook_row_count']}`",
        f"- pending analyst requests: `{stats['requests_pending_manual_resolution_count']}`",
        f"- partially ready requests: `{stats['requests_partially_ready_for_validation_count']}`",
        f"- ready-for-validation requests: `{stats['requests_ready_for_validation_count']}`",
        f"- validation-ready profiles: `{stats['validation_ready_profile_count']}`",
        f"- final pending-manual requests: `{stats['final_pending_manual_resolution_count']}`",
        f"- final partially-ready requests: `{stats['final_partially_ready_for_validation_count']}`",
        f"- final ready-for-validation requests: `{stats['final_ready_for_validation_count']}`",
        f"- final validation-review requests: `{stats['final_validation_review_required_count']}`",
        f"- final accepted-pending-apply requests: `{stats['final_accepted_pending_apply_count']}`",
        f"- final partially applied requests: `{stats['final_partially_applied_count']}`",
        f"- final fully applied requests: `{stats['final_fully_applied_count']}`",
        f"- operator-ready requests: `{stats['operator_ready_request_count']}`",
        f"- operator holds: `{stats['operator_hold_request_count']}`",
        f"- operator workbook-fill requests: `{stats['operator_workbook_fill_request_count']}`",
        f"- operator validation requests: `{stats['operator_validation_request_count']}`",
        f"- operator review requests: `{stats['operator_validation_review_request_count']}`",
        f"- operator repair requests: `{stats['operator_repair_request_count']}`",
        f"- support execution-ready requests: `{stats['support_execution_ready_request_count']}`",
        f"- support execution holds: `{stats['support_execution_hold_request_count']}`",
        f"- support workbook-fill executions: `{stats['support_execution_workbook_fill_request_count']}`",
        f"- support runtime-rerun executions: `{stats['support_execution_runtime_rerun_request_count']}`",
        f"- support validation-review executions: `{stats['support_execution_validation_review_request_count']}`",
        f"- support repair executions: `{stats['support_execution_repair_request_count']}`",
        f"- support apply-pending holds: `{stats['support_execution_apply_pending_hold_count']}`",
        f"- support complete holds: `{stats['support_execution_complete_hold_count']}`",
        f"- support handoff-ready requests: `{stats['support_handoff_ready_request_count']}`",
        f"- support handoff holds: `{stats['support_handoff_hold_request_count']}`",
        f"- support workbook handoffs: `{stats['support_handoff_workbook_request_count']}`",
        f"- support runtime handoffs: `{stats['support_handoff_runtime_rerun_request_count']}`",
        f"- support validation-review handoffs: `{stats['support_handoff_validation_review_request_count']}`",
        f"- support repair handoffs: `{stats['support_handoff_repair_request_count']}`",
        f"- support apply-pending handoff holds: `{stats['support_handoff_apply_pending_hold_count']}`",
        f"- support complete handoff holds: `{stats['support_handoff_complete_hold_count']}`",
        f"- support runtime-board ready requests: `{stats['support_runtime_board_ready_request_count']}`",
        f"- support runtime-board holds: `{stats['support_runtime_board_hold_request_count']}`",
        f"- support runtime-board workbook rows: `{stats['support_runtime_board_workbook_row_count']}`",
        f"- support runtime-board runtime-rerun rows: `{stats['support_runtime_board_runtime_rerun_row_count']}`",
        f"- support runtime-board review rows: `{stats['support_runtime_board_validation_review_row_count']}`",
        f"- support runtime-board repair rows: `{stats['support_runtime_board_repair_row_count']}`",
        f"- support runtime-action ready requests: `{stats['support_runtime_action_queue_ready_count']}`",
        f"- support runtime-action holds: `{stats['support_runtime_action_queue_hold_count']}`",
        f"- support runtime-action workbook requests: `{stats['support_runtime_action_queue_workbook_action_count']}`",
        f"- support runtime-action runtime-rerun requests: `{stats['support_runtime_action_queue_runtime_rerun_action_count']}`",
        f"- support runtime-action review requests: `{stats['support_runtime_action_queue_validation_review_action_count']}`",
        f"- support runtime-action repair requests: `{stats['support_runtime_action_queue_repair_action_count']}`",
        f"- support runtime-execution ready requests: `{stats['support_runtime_execution_ready_request_count']}`",
        f"- support runtime-execution holds: `{stats['support_runtime_execution_hold_request_count']}`",
        f"- support runtime-execution workbook requests: `{stats['support_runtime_execution_workbook_fill_request_count']}`",
        f"- support runtime-execution runtime-rerun requests: `{stats['support_runtime_execution_runtime_rerun_request_count']}`",
        f"- support runtime-execution review requests: `{stats['support_runtime_execution_validation_review_request_count']}`",
        f"- support runtime-execution repair requests: `{stats['support_runtime_execution_repair_request_count']}`",
        f"- support workbook-completion requests: `{stats['support_workbook_completion_request_count']}`",
        f"- support workbook-completion rows: `{stats['support_workbook_completion_row_count']}`",
        f"- support workbook-completion manual rows: `{stats['support_workbook_completion_manual_row_count']}`",
        f"- support workbook-completion pedestrian rows: `{stats['support_workbook_completion_pedestrian_row_count']}`",
        f"- support workbook-completion non-workbook executions: `{stats['support_workbook_completion_non_workbook_execution_count']}`",
        f"- support workbook-completion holds: `{stats['support_workbook_completion_hold_request_count']}`",
        f"- support workbook-completion crash weight: `{stats['support_workbook_completion_total_crash_weight']}`",
        f"- pre-apply workbook-fill actions: `{stats['pre_workbook_fill_action_count']}`",
        f"- pre-apply validation actions: `{stats['pre_validation_action_count']}`",
        f"- executed validations: `{stats['executed_validation_count']}`",
        f"- accepted for ingestion: `{stats['accepted_for_ingestion_count']}`",
        f"- applied profiles: `{stats['applied_profile_count']}`",
        f"- accepted pending apply: `{stats['accepted_pending_apply_count']}`",
        f"- final workbook-fill actions: `{stats['workbook_fill_action_count']}`",
        f"- final validation actions: `{stats['validation_action_count']}`",
        f"- final review actions: `{stats['validation_review_action_count']}`",
        f"- final repair actions: `{stats['repair_action_count']}`",
        f"- final already-applied holds: `{stats['apply_complete_count']}`",
        f"- apply session executed: `{stats['delivery_session_executed']}`",
        f"- movements with phase timing: `{stats['movements_with_phase_timing']}`",
        f"- movements with phase mapping: `{stats['movements_with_phase_mapping']}`",
        "",
        "## Child Outputs",
        "",
        f"- writeback bundle: `{outputs['support_writeback_manifest_path']}`",
        f"- status bundle: `{outputs['support_status_manifest_path']}`",
        f"- pre-apply action queue: `{outputs['support_action_queue_pre_manifest_path']}`",
        f"- apply cycle: `{outputs['support_apply_cycle_manifest_path']}`",
        f"- apply-status bundle: `{outputs['support_apply_status_manifest_path']}`",
        f"- request-state bundle: `{outputs['support_request_state_manifest_path']}`",
        f"- final action queue: `{outputs['support_action_queue_manifest_path']}`",
        f"- operator board: `{outputs['support_operator_board_manifest_path']}`",
        f"- action execution bundle: `{outputs['support_action_execution_manifest_path']}`",
        f"- action handoff bundle: `{outputs['support_action_handoff_manifest_path']}`",
        f"- runtime board: `{outputs['support_runtime_board_manifest_path']}`",
        f"- runtime action queue: `{outputs['support_runtime_action_queue_manifest_path']}`",
        f"- runtime action execution: `{outputs['support_runtime_action_execution_manifest_path']}`",
        f"- workbook completion: `{outputs['support_workbook_completion_manifest_path']}`",
        "",
    ]
    return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def run_bari_signal_phase_support_runtime_cycle(
    *,
    output_dir: str | Path = "data/processed/signal_phase_support_runtime_cycles/bari",
    signal_phase_support_resolution_bundle_path: str | Path = "data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    manual_mapping_stub_path: str | Path = "data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    support_resolution_input = Path(signal_phase_support_resolution_bundle_path)
    manual_mapping_stub_input = Path(manual_mapping_stub_path)
    delivery_checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)

    writeback_output_dir = output_root / "support_writeback"
    status_output_dir = output_root / "support_status"
    pre_action_queue_output_dir = output_root / "support_action_queue_pre"
    apply_cycle_output_dir = output_root / "support_apply_cycle"
    apply_status_output_dir = output_root / "support_apply_status"
    request_state_output_dir = output_root / "support_request_state"
    action_queue_output_dir = output_root / "support_action_queue"
    operator_board_output_dir = output_root / "support_operator_board"
    action_execution_output_dir = output_root / "support_action_execution"
    action_handoff_output_dir = output_root / "support_action_handoff"
    runtime_board_output_dir = output_root / "support_runtime_board"
    runtime_action_queue_output_dir = output_root / "support_runtime_action_queue"
    runtime_action_execution_output_dir = output_root / "support_runtime_action_execution"
    workbook_completion_output_dir = output_root / "support_workbook_completion"

    cycle_json_path = output_root / "signal_phase_support_runtime_cycle.json"
    cycle_md_path = output_root / "signal_phase_support_runtime_cycle.md"
    manifest_path = output_root / "signal_phase_support_runtime_cycle.manifest.json"

    writeback_manifest = build_bari_signal_phase_support_writeback_bundle(
        output_dir=writeback_output_dir,
        signal_phase_support_resolution_bundle_path=support_resolution_input,
        manual_mapping_stub_path=manual_mapping_stub_input,
    )
    writeback_json_path = Path(writeback_manifest["outputs"]["report_json_path"])

    status_manifest = build_bari_signal_phase_support_status_bundle(
        output_dir=status_output_dir,
        signal_phase_support_writeback_bundle_path=writeback_json_path,
    )
    status_json_path = Path(status_manifest["outputs"]["report_json_path"])

    pre_action_queue_manifest = build_bari_signal_phase_support_action_queue(
        output_dir=pre_action_queue_output_dir,
        signal_phase_support_status_bundle_path=status_json_path,
    )
    pre_action_execution_ready_queue_path = Path(
        pre_action_queue_manifest["outputs"]["action_execution_ready_queue_path"]
    )

    apply_cycle_result = run_bari_signal_phase_support_apply_cycle(
        output_dir=apply_cycle_output_dir,
        action_execution_ready_queue_path=pre_action_execution_ready_queue_path,
        delivery_checklist_path=delivery_checklist_input,
        movement_objects_path=movement_objects_input,
        preview_limit=preview_limit,
    )

    apply_cycle_json_path = Path(apply_cycle_result["manifest_path"]).with_suffix("").with_suffix(".json")
    apply_status_manifest = build_bari_signal_phase_support_apply_status_bundle(
        output_dir=apply_status_output_dir,
        signal_phase_support_status_bundle_path=status_json_path,
        signal_phase_support_apply_cycle_path=apply_cycle_json_path,
    )
    apply_status_json_path = Path(apply_status_manifest["outputs"]["report_json_path"])

    request_state_manifest = build_bari_signal_phase_support_request_state_bundle(
        output_dir=request_state_output_dir,
        signal_phase_support_status_bundle_path=status_json_path,
        signal_phase_support_apply_status_bundle_path=apply_status_json_path,
    )
    request_state_json_path = Path(request_state_manifest["outputs"]["report_json_path"])

    action_queue_manifest = build_bari_signal_phase_support_action_queue(
        output_dir=action_queue_output_dir,
        signal_phase_support_status_bundle_path=status_json_path,
        signal_phase_support_apply_status_bundle_path=apply_status_json_path,
    )
    action_queue_json_path = Path(action_queue_manifest["outputs"]["report_json_path"])

    operator_board_manifest = build_bari_signal_phase_support_operator_board_bundle(
        output_dir=operator_board_output_dir,
        signal_phase_support_request_state_bundle_path=request_state_json_path,
        signal_phase_support_action_queue_path=action_queue_json_path,
    )
    operator_board_json_path = Path(operator_board_manifest["outputs"]["report_json_path"])

    action_execution_manifest = build_bari_signal_phase_support_action_execution_bundle(
        output_dir=action_execution_output_dir,
        signal_phase_support_operator_board_bundle_path=operator_board_json_path,
    )
    action_execution_json_path = Path(action_execution_manifest["outputs"]["report_json_path"])

    action_handoff_manifest = build_bari_signal_phase_support_action_handoff_bundle(
        output_dir=action_handoff_output_dir,
        signal_phase_support_action_execution_bundle_path=action_execution_json_path,
        support_runtime_cycle_manifest_path=manifest_path,
    )
    action_handoff_json_path = Path(action_handoff_manifest["outputs"]["bundle_json_path"])

    runtime_board_manifest = build_bari_signal_phase_support_runtime_board_bundle(
        output_dir=runtime_board_output_dir,
        signal_phase_support_action_execution_bundle_path=action_execution_json_path,
        signal_phase_support_action_handoff_bundle_path=action_handoff_json_path,
    )
    runtime_action_queue_manifest = build_bari_signal_phase_support_runtime_action_queue(
        output_dir=runtime_action_queue_output_dir,
        signal_phase_support_runtime_board_bundle_path=Path(
            runtime_board_manifest["outputs"]["bundle_json_path"]
        ),
    )
    runtime_action_execution_manifest = (
        build_bari_signal_phase_support_runtime_action_execution_bundle(
            output_dir=runtime_action_execution_output_dir,
            signal_phase_support_runtime_action_queue_path=Path(
                runtime_action_queue_manifest["outputs"]["report_json_path"]
            ),
        )
    )
    workbook_completion_manifest = (
        build_bari_signal_phase_support_workbook_completion_bundle(
            output_dir=workbook_completion_output_dir,
            signal_phase_support_runtime_action_execution_bundle_path=Path(
                runtime_action_execution_manifest["outputs"]["report_json_path"]
            ),
            signal_phase_support_writeback_bundle_path=writeback_json_path,
        )
    )

    writeback_payload = _load_json(writeback_json_path)
    status_payload = _load_json(status_json_path)
    pre_action_queue_json_path = Path(pre_action_queue_manifest["outputs"]["report_json_path"])
    pre_action_queue_payload = _load_json(pre_action_queue_json_path)
    apply_status_payload = _load_json(apply_status_json_path)
    request_state_payload = _load_json(request_state_json_path)
    action_queue_payload = _load_json(action_queue_json_path)
    operator_board_payload = _load_json(operator_board_json_path)
    action_execution_payload = _load_json(action_execution_json_path)
    action_handoff_payload = _load_json(action_handoff_json_path)
    runtime_board_json_path = Path(runtime_board_manifest["outputs"]["bundle_json_path"])
    runtime_board_payload = _load_json(runtime_board_json_path)
    runtime_action_queue_json_path = Path(
        runtime_action_queue_manifest["outputs"]["report_json_path"]
    )
    runtime_action_queue_payload = _load_json(runtime_action_queue_json_path)
    runtime_action_execution_json_path = Path(
        runtime_action_execution_manifest["outputs"]["report_json_path"]
    )
    runtime_action_execution_payload = _load_json(runtime_action_execution_json_path)
    workbook_completion_json_path = Path(
        workbook_completion_manifest["outputs"]["report_json_path"]
    )
    workbook_completion_payload = _load_json(workbook_completion_json_path)

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "generated_at_utc": generated_at_utc,
        "support_request_count": int(writeback_payload["summary"]["support_request_count"]),
        "manual_workbook_row_count": int(
            writeback_payload["summary"]["manual_workbook_row_count"]
        ),
        "pedestrian_workbook_row_count": int(
            writeback_payload["summary"]["pedestrian_workbook_row_count"]
        ),
        "requests_pending_manual_resolution_count": int(
            status_payload["summary"]["requests_pending_manual_resolution_count"]
        ),
        "requests_partially_ready_for_validation_count": int(
            status_payload["summary"]["requests_partially_ready_for_validation_count"]
        ),
        "requests_ready_for_validation_count": int(
            status_payload["summary"]["requests_ready_for_validation_count"]
        ),
        "validation_ready_profile_count": int(
            status_payload["summary"]["validation_ready_profile_count"]
        ),
        "final_pending_manual_resolution_count": int(
            request_state_payload["summary"]["pending_manual_resolution_count"]
        ),
        "final_partially_ready_for_validation_count": int(
            request_state_payload["summary"]["partially_ready_for_validation_count"]
        ),
        "final_ready_for_validation_count": int(
            request_state_payload["summary"]["ready_for_validation_count"]
        ),
        "final_validation_review_required_count": int(
            request_state_payload["summary"]["validation_review_required_count"]
        ),
        "final_accepted_pending_apply_count": int(
            request_state_payload["summary"]["accepted_pending_apply_count"]
        ),
        "final_partially_applied_count": int(
            request_state_payload["summary"]["partially_applied_count"]
        ),
        "final_fully_applied_count": int(
            request_state_payload["summary"]["fully_applied_count"]
        ),
        "operator_ready_request_count": int(
            operator_board_payload["summary"]["operator_ready_count"]
        ),
        "operator_hold_request_count": int(
            operator_board_payload["summary"]["internal_hold_count"]
        ),
        "operator_workbook_fill_request_count": int(
            operator_board_payload["summary"]["workbook_fill_request_count"]
        ),
        "operator_validation_request_count": int(
            operator_board_payload["summary"]["validation_request_count"]
        ),
        "operator_validation_review_request_count": int(
            operator_board_payload["summary"]["validation_review_request_count"]
        ),
        "operator_repair_request_count": int(
            operator_board_payload["summary"]["repair_request_count"]
        ),
        "support_execution_ready_request_count": int(
            action_execution_payload["summary"]["execution_ready_count"]
        ),
        "support_execution_hold_request_count": int(
            action_execution_payload["summary"]["internal_hold_count"]
        ),
        "support_execution_workbook_fill_request_count": int(
            action_execution_payload["summary"]["workbook_fill_request_count"]
        ),
        "support_execution_runtime_rerun_request_count": int(
            action_execution_payload["summary"]["runtime_rerun_request_count"]
        ),
        "support_execution_validation_review_request_count": int(
            action_execution_payload["summary"]["validation_review_request_count"]
        ),
        "support_execution_repair_request_count": int(
            action_execution_payload["summary"]["repair_request_count"]
        ),
        "support_execution_apply_pending_hold_count": int(
            action_execution_payload["summary"]["apply_pending_hold_count"]
        ),
        "support_execution_complete_hold_count": int(
            action_execution_payload["summary"]["complete_hold_count"]
        ),
        "support_handoff_ready_request_count": int(
            action_handoff_payload["summary"]["handoff_ready_count"]
        ),
        "support_handoff_hold_request_count": int(
            action_handoff_payload["summary"]["internal_hold_count"]
        ),
        "support_handoff_workbook_request_count": int(
            action_handoff_payload["summary"]["workbook_handoff_count"]
        ),
        "support_handoff_runtime_rerun_request_count": int(
            action_handoff_payload["summary"]["runtime_rerun_handoff_count"]
        ),
        "support_handoff_validation_review_request_count": int(
            action_handoff_payload["summary"]["validation_review_handoff_count"]
        ),
        "support_handoff_repair_request_count": int(
            action_handoff_payload["summary"]["repair_handoff_count"]
        ),
        "support_handoff_apply_pending_hold_count": int(
            action_handoff_payload["summary"]["apply_pending_hold_count"]
        ),
        "support_handoff_complete_hold_count": int(
            action_handoff_payload["summary"]["complete_hold_count"]
        ),
        "support_runtime_board_ready_request_count": int(
            runtime_board_payload["summary"]["operator_ready_count"]
        ),
        "support_runtime_board_hold_request_count": int(
            runtime_board_payload["summary"]["internal_hold_count"]
        ),
        "support_runtime_board_workbook_row_count": int(
            runtime_board_payload["summary"]["workbook_row_count"]
        ),
        "support_runtime_board_runtime_rerun_row_count": int(
            runtime_board_payload["summary"]["runtime_rerun_row_count"]
        ),
        "support_runtime_board_validation_review_row_count": int(
            runtime_board_payload["summary"]["validation_review_row_count"]
        ),
        "support_runtime_board_repair_row_count": int(
            runtime_board_payload["summary"]["repair_row_count"]
        ),
        "support_runtime_action_queue_ready_count": int(
            runtime_action_queue_payload["summary"]["immediate_action_count"]
        ),
        "support_runtime_action_queue_hold_count": int(
            runtime_action_queue_payload["summary"]["internal_hold_count"]
        ),
        "support_runtime_action_queue_workbook_action_count": int(
            runtime_action_queue_payload["summary"]["workbook_action_count"]
        ),
        "support_runtime_action_queue_runtime_rerun_action_count": int(
            runtime_action_queue_payload["summary"]["runtime_rerun_action_count"]
        ),
        "support_runtime_action_queue_validation_review_action_count": int(
            runtime_action_queue_payload["summary"]["validation_review_action_count"]
        ),
        "support_runtime_action_queue_repair_action_count": int(
            runtime_action_queue_payload["summary"]["repair_action_count"]
        ),
        "support_runtime_action_queue_apply_pending_hold_count": int(
            runtime_action_queue_payload["summary"]["apply_pending_hold_count"]
        ),
        "support_runtime_action_queue_complete_hold_count": int(
            runtime_action_queue_payload["summary"]["complete_hold_count"]
        ),
        "support_runtime_execution_ready_request_count": int(
            runtime_action_execution_payload["summary"]["execution_ready_count"]
        ),
        "support_runtime_execution_hold_request_count": int(
            runtime_action_execution_payload["summary"]["internal_hold_count"]
        ),
        "support_runtime_execution_workbook_fill_request_count": int(
            runtime_action_execution_payload["summary"]["workbook_fill_request_count"]
        ),
        "support_runtime_execution_runtime_rerun_request_count": int(
            runtime_action_execution_payload["summary"]["runtime_rerun_request_count"]
        ),
        "support_runtime_execution_validation_review_request_count": int(
            runtime_action_execution_payload["summary"][
                "validation_review_request_count"
            ]
        ),
        "support_runtime_execution_repair_request_count": int(
            runtime_action_execution_payload["summary"]["repair_request_count"]
        ),
        "support_runtime_execution_apply_pending_hold_count": int(
            runtime_action_execution_payload["summary"]["apply_pending_hold_count"]
        ),
        "support_runtime_execution_complete_hold_count": int(
            runtime_action_execution_payload["summary"]["complete_hold_count"]
        ),
        "support_workbook_completion_request_count": int(
            workbook_completion_payload["summary"]["workbook_fill_request_count"]
        ),
        "support_workbook_completion_row_count": int(
            workbook_completion_payload["summary"]["completion_row_count"]
        ),
        "support_workbook_completion_manual_row_count": int(
            workbook_completion_payload["summary"]["manual_completion_row_count"]
        ),
        "support_workbook_completion_pedestrian_row_count": int(
            workbook_completion_payload["summary"]["pedestrian_completion_row_count"]
        ),
        "support_workbook_completion_non_workbook_execution_count": int(
            workbook_completion_payload["summary"]["non_workbook_execution_count"]
        ),
        "support_workbook_completion_hold_request_count": int(
            workbook_completion_payload["summary"]["hold_request_count"]
        ),
        "support_workbook_completion_total_crash_weight": int(
            workbook_completion_payload["summary"]["total_crash_weight"]
        ),
        "pre_workbook_fill_action_count": int(
            pre_action_queue_payload["summary"]["workbook_fill_action_count"]
        ),
        "pre_validation_action_count": int(
            pre_action_queue_payload["summary"]["validation_action_count"]
        ),
        "workbook_fill_action_count": int(
            action_queue_payload["summary"]["workbook_fill_action_count"]
        ),
        "validation_action_count": int(
            action_queue_payload["summary"]["validation_action_count"]
        ),
        "validation_review_action_count": int(
            action_queue_payload["summary"]["validation_review_action_count"]
        ),
        "repair_action_count": int(action_queue_payload["summary"]["repair_action_count"]),
        "apply_complete_count": int(action_queue_payload["summary"]["apply_complete_count"]),
        "apply_pending_count": int(action_queue_payload["summary"]["apply_pending_count"]),
        "internal_hold_count": int(action_queue_payload["summary"]["internal_hold_count"]),
        "executed_validation_count": int(
            apply_cycle_result["stats"]["executed_validation_count"]
        ),
        "accepted_for_ingestion_count": int(
            apply_cycle_result["stats"]["accepted_for_ingestion_count"]
        ),
        "accepted_support_artifact_count": int(
            apply_cycle_result["stats"]["accepted_support_artifact_count"]
        ),
        "applied_profile_count": int(apply_status_payload["summary"]["applied_profile_count"]),
        "accepted_pending_apply_count": int(
            apply_status_payload["summary"]["accepted_pending_apply_count"]
        ),
        "delivery_session_executed": bool(
            apply_cycle_result["stats"]["delivery_session_executed"]
        ),
        "movements_with_phase_timing": int(
            apply_cycle_result["stats"]["movements_with_phase_timing"]
        ),
        "movements_with_phase_mapping": int(
            apply_cycle_result["stats"]["movements_with_phase_mapping"]
        ),
    }

    payload = {
        "signal_phase_support_runtime_cycle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_VERSION,
        "signal_phase_support_runtime_cycle_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "bari_signal_phase_support_runtime_cycle_runner",
        },
        "stats": stats,
        "inputs": {
            "signal_phase_support_resolution_bundle_path": str(support_resolution_input),
            "manual_mapping_stub_path": str(manual_mapping_stub_input),
            "delivery_checklist_path": str(delivery_checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "support_writeback_manifest_path": str(writeback_manifest["outputs"]["manifest_path"]),
            "support_status_manifest_path": str(status_manifest["outputs"]["manifest_path"]),
            "support_action_queue_pre_manifest_path": str(
                pre_action_queue_manifest["outputs"]["manifest_path"]
            ),
            "support_apply_status_manifest_path": str(
                apply_status_manifest["outputs"]["manifest_path"]
            ),
            "support_request_state_manifest_path": str(
                request_state_manifest["outputs"]["manifest_path"]
            ),
            "support_action_queue_manifest_path": str(action_queue_manifest["outputs"]["manifest_path"]),
            "support_operator_board_manifest_path": str(
                operator_board_manifest["outputs"]["manifest_path"]
            ),
            "support_action_execution_manifest_path": str(
                action_execution_manifest["outputs"]["manifest_path"]
            ),
            "support_action_handoff_manifest_path": str(
                action_handoff_manifest["outputs"]["manifest_path"]
            ),
            "support_runtime_board_manifest_path": str(
                runtime_board_manifest["outputs"]["manifest_path"]
            ),
            "support_runtime_action_queue_manifest_path": str(
                runtime_action_queue_manifest["outputs"]["manifest_path"]
            ),
            "support_runtime_action_execution_manifest_path": str(
                runtime_action_execution_manifest["outputs"]["manifest_path"]
            ),
            "support_workbook_completion_manifest_path": str(
                workbook_completion_manifest["outputs"]["manifest_path"]
            ),
            "support_apply_cycle_manifest_path": str(apply_cycle_result["manifest_path"]),
            "cycle_json_path": str(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "manifest_path": str(manifest_path),
        },
    }
    cycle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    cycle_md_path.write_text(_cycle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_runtime_cycle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_runtime_cycle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_CONTRACT_VERSION,
            "signal_phase_support_runtime_cycle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_VERSION,
        },
        "source": payload["source"],
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "cycle_json_path": str(cycle_json_path),
            "cycle_json_sha256": _sha256(cycle_json_path),
            "cycle_md_path": str(cycle_md_path),
            "cycle_md_sha256": _sha256(cycle_md_path),
            "support_writeback_manifest_path": payload["outputs"]["support_writeback_manifest_path"],
            "support_status_manifest_path": payload["outputs"]["support_status_manifest_path"],
            "support_action_queue_pre_manifest_path": payload["outputs"]["support_action_queue_pre_manifest_path"],
            "support_apply_status_manifest_path": payload["outputs"]["support_apply_status_manifest_path"],
            "support_request_state_manifest_path": payload["outputs"]["support_request_state_manifest_path"],
            "support_action_queue_manifest_path": payload["outputs"]["support_action_queue_manifest_path"],
            "support_operator_board_manifest_path": payload["outputs"]["support_operator_board_manifest_path"],
            "support_action_execution_manifest_path": payload["outputs"]["support_action_execution_manifest_path"],
            "support_action_handoff_manifest_path": payload["outputs"]["support_action_handoff_manifest_path"],
            "support_runtime_board_manifest_path": payload["outputs"]["support_runtime_board_manifest_path"],
            "support_runtime_action_queue_manifest_path": payload["outputs"]["support_runtime_action_queue_manifest_path"],
            "support_runtime_action_execution_manifest_path": payload["outputs"]["support_runtime_action_execution_manifest_path"],
            "support_workbook_completion_manifest_path": payload["outputs"]["support_workbook_completion_manifest_path"],
            "support_apply_cycle_manifest_path": payload["outputs"]["support_apply_cycle_manifest_path"],
        },
        "stats": stats,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_resolution_bundle",
                    support_resolution_input,
                    _sha256(support_resolution_input),
                ),
                _artifact_reference(
                    "signal_phase_mapping_stub",
                    manual_mapping_stub_input,
                    _sha256(manual_mapping_stub_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_checklist",
                    delivery_checklist_input,
                    _sha256(delivery_checklist_input),
                ),
                _artifact_reference(
                    "movement_objects",
                    movement_objects_input,
                    _sha256(movement_objects_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_cycle_json",
                    cycle_json_path,
                    _sha256(cycle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_cycle_markdown",
                    cycle_md_path,
                    _sha256(cycle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_support_writeback_bundle",
                    Path(payload["outputs"]["support_writeback_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_writeback_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_status_bundle",
                    Path(payload["outputs"]["support_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_queue",
                    Path(payload["outputs"]["support_action_queue_pre_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_action_queue_pre_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_status_bundle",
                    Path(payload["outputs"]["support_apply_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_apply_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_request_state_bundle",
                    Path(payload["outputs"]["support_request_state_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_request_state_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_queue",
                    Path(payload["outputs"]["support_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_operator_board_bundle",
                    Path(payload["outputs"]["support_operator_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_operator_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_execution_bundle",
                    Path(payload["outputs"]["support_action_execution_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_action_execution_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle",
                    Path(payload["outputs"]["support_action_handoff_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_action_handoff_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle",
                    Path(payload["outputs"]["support_runtime_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_runtime_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue",
                    Path(payload["outputs"]["support_runtime_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_runtime_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_execution_bundle",
                    Path(payload["outputs"]["support_runtime_action_execution_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_runtime_action_execution_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_workbook_completion_bundle",
                    Path(payload["outputs"]["support_workbook_completion_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_workbook_completion_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_cycle",
                    Path(payload["outputs"]["support_apply_cycle_manifest_path"]),
                    _sha256(Path(payload["outputs"]["support_apply_cycle_manifest_path"])),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_support_runtime_cycle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
