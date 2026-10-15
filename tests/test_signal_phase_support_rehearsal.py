from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_support_rehearsal import (
    run_bari_signal_phase_support_rehearsal,
)
from road_risk_modeling.signal_phase_support_writeback import (
    build_bari_signal_phase_support_writeback_bundle,
)


class SignalPhaseSupportRehearsalTests(unittest.TestCase):
    def test_run_bari_signal_phase_support_rehearsal_injects_rows_and_compares_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            support_resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"
            live_writeback_dir = root / "live_support_writeback"
            output_dir = root / "support_rehearsal"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            support_resolution_bundle_path.write_text(
                json.dumps(
                    {
                        "support_resolution_requests": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "recommended_next_action": "Resolve support mappings.",
                            }
                        ],
                        "manual_arm_phase_review": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "signal_type": "IMP. SEMAF",
                                "incoming_arm_id": "arm_a",
                                "movement_turn": "u_turn",
                                "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                                "crash_total": 50,
                                "injury_total": 24,
                                "peak_year": "2024",
                                "peak_year_crash_count": 18,
                                "candidate_target_arm_catalog": "arm_b@W | arm_c@E",
                                "movement_variant_count": 2,
                                "movement_ids": "movement_a",
                                "support_artifact_path": "diagram.pdf",
                                "validation_manifest_path": "support.manifest.json",
                                "manual_mapping_hint": "Fill the phase mapping from the diagram.",
                            }
                        ],
                        "pedestrian_stage_review": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "signal_type": "IMP. SEMAF",
                                "node_object_id": "crossing_1",
                                "movement_turn": "cross",
                                "crash_total": 1,
                                "injury_total": 0,
                                "peak_year": "2023",
                                "peak_year_crash_count": 1,
                                "support_artifact_path": "diagram.pdf",
                                "validation_manifest_path": "support.manifest.json",
                                "manual_mapping_hint": "Fill the pedestrian stage from the diagram.",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            manual_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "mapping_stub_version": "signal_phase_mapping_stub_v1",
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [
                            {
                                "target_field": "junction_id",
                                "source_field": "TODO_arm_phase_mapping_sheet__junction_id",
                                "required": True,
                                "type": "string",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            delivery_checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text(
                '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
            )

            live_writeback_manifest = build_bari_signal_phase_support_writeback_bundle(
                output_dir=live_writeback_dir,
                signal_phase_support_resolution_bundle_path=support_resolution_bundle_path,
                manual_mapping_stub_path=manual_mapping_stub_path,
            )
            live_writeback_bundle_path = Path(
                live_writeback_manifest["outputs"]["report_json_path"]
            )

            call_index = {"count": 0}

            def _apply_cycle_side_effect(**kwargs):
                call_index["count"] += 1
                apply_output_dir = Path(kwargs["output_dir"])
                apply_output_dir.mkdir(parents=True, exist_ok=True)
                manifest_path = (
                    apply_output_dir / "signal_phase_support_apply_cycle.manifest.json"
                )
                manifest_path.write_text("{}", encoding="utf-8")
                if call_index["count"] == 1:
                    return {
                        "manifest_path": str(manifest_path),
                        "stats": {
                            "action_queue_count": 2,
                            "validation_candidate_count": 0,
                            "executed_validation_count": 0,
                            "accepted_for_ingestion_count": 0,
                            "skipped_non_validation_action_count": 2,
                            "delivery_session_executed": False,
                            "movements_with_phase_timing": 0,
                            "movements_with_phase_mapping": 0,
                        },
                    }
                return {
                    "manifest_path": str(manifest_path),
                    "stats": {
                        "action_queue_count": 2,
                        "validation_candidate_count": 2,
                        "executed_validation_count": 2,
                        "accepted_for_ingestion_count": 2,
                        "skipped_non_validation_action_count": 0,
                        "delivery_session_executed": True,
                        "movements_with_phase_timing": 2,
                        "movements_with_phase_mapping": 2,
                    },
                }

            def _write_manifest(path: Path) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"manifest_path": str(path)}, indent=2), encoding="utf-8")
                return str(path)

            def _write_json(path: Path, payload: dict[str, object]) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
                return str(path)

            with patch(
                "road_risk_modeling.signal_phase_support_rehearsal.run_bari_signal_phase_support_apply_cycle",
                side_effect=_apply_cycle_side_effect,
            ) as apply_cycle_mock, patch(
                "road_risk_modeling.signal_phase_support_rehearsal.build_bari_signal_phase_support_apply_status_bundle",
                side_effect=lambda **kwargs: {
                    "outputs": {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_support_apply_status_bundle.manifest.json"
                        ),
                        "report_json_path": _write_json(
                            Path(kwargs["output_dir"]) / "signal_phase_support_apply_status_bundle.json",
                            {
                                "summary": (
                                    {
                                        "profile_count": 2,
                                        "applied_profile_count": 0,
                                        "accepted_pending_apply_count": 0,
                                    }
                                    if "pre_support_apply_status" in str(kwargs["output_dir"])
                                    else {
                                        "profile_count": 2,
                                        "applied_profile_count": 2,
                                        "accepted_pending_apply_count": 0,
                                    }
                                )
                            },
                        ),
                    }
                },
            ) as apply_status_mock, patch(
                "road_risk_modeling.signal_phase_support_rehearsal.build_bari_signal_phase_support_request_state_bundle",
                side_effect=lambda **kwargs: {
                    "outputs": {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_support_request_state_bundle.manifest.json"
                        ),
                        "report_json_path": _write_json(
                            Path(kwargs["output_dir"]) / "signal_phase_support_request_state_bundle.json",
                            {
                                "summary": (
                                    {
                                        "pending_manual_resolution_count": 1,
                                        "partially_ready_for_validation_count": 0,
                                        "ready_for_validation_count": 0,
                                        "validation_review_required_count": 0,
                                        "accepted_pending_apply_count": 0,
                                        "partially_applied_count": 0,
                                        "fully_applied_count": 0,
                                    }
                                    if "pre_support_request_state" in str(kwargs["output_dir"])
                                    else {
                                        "pending_manual_resolution_count": 0,
                                        "partially_ready_for_validation_count": 0,
                                        "ready_for_validation_count": 0,
                                        "validation_review_required_count": 0,
                                        "accepted_pending_apply_count": 0,
                                        "partially_applied_count": 0,
                                        "fully_applied_count": 1,
                                    }
                                ),
                                "request_support_runtime_state": [
                                    (
                                        {
                                            "request_id": "bari_signal_phase_01",
                                            "signal_name": "Signal 93",
                                            "request_runtime_category": "pending_manual_resolution",
                                            "applied_profile_count": 0,
                                            "ready_for_validation_count": 0,
                                            "waiting_for_analyst_resolution_count": 2,
                                            "request_runtime_summary": "pending_manual_resolution: 0/2 applied, 0 ready, 2 waiting",
                                            "next_action": "Complete workbook rows.",
                                        }
                                        if "pre_support_request_state" in str(kwargs["output_dir"])
                                        else {
                                            "request_id": "bari_signal_phase_01",
                                            "signal_name": "Signal 93",
                                            "request_runtime_category": "fully_applied_to_movement_layer",
                                            "applied_profile_count": 2,
                                            "ready_for_validation_count": 0,
                                            "waiting_for_analyst_resolution_count": 0,
                                            "request_runtime_summary": "fully_applied_to_movement_layer: 2/2 applied, 0 ready, 0 waiting",
                                            "next_action": "No action required.",
                                        }
                                    )
                                ],
                            },
                        ),
                    }
                },
            ) as request_state_mock, patch(
                "road_risk_modeling.signal_phase_support_rehearsal.build_bari_signal_phase_support_operator_board_bundle",
                side_effect=lambda **kwargs: {
                    "outputs": {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_support_operator_board_bundle.manifest.json"
                        ),
                        "report_json_path": _write_json(
                            Path(kwargs["output_dir"]) / "signal_phase_support_operator_board_bundle.json",
                            {
                                "summary": (
                                    {
                                        "request_count": 1,
                                        "operator_ready_count": 1,
                                        "internal_hold_count": 0,
                                        "workbook_fill_request_count": 1,
                                        "validation_request_count": 0,
                                        "validation_review_request_count": 0,
                                        "repair_request_count": 0,
                                        "apply_pending_request_count": 0,
                                        "complete_request_count": 0,
                                    }
                                    if "pre_support_operator_board" in str(kwargs["output_dir"])
                                    else {
                                        "request_count": 1,
                                        "operator_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_fill_request_count": 0,
                                        "validation_request_count": 0,
                                        "validation_review_request_count": 0,
                                        "repair_request_count": 0,
                                        "apply_pending_request_count": 0,
                                        "complete_request_count": 0,
                                    }
                                ),
                                "operator_ready_queue": (
                                    [
                                        {
                                            "support_request_reference": "bari_signal_phase_01",
                                            "request_id": "bari_signal_phase_01",
                                            "junction_id": "it-bari-signal-93",
                                            "signal_name": "Signal 93",
                                            "request_runtime_category": "pending_manual_resolution",
                                            "operator_action_category": "fill_support_workbook_now",
                                            "due_now": "yes",
                                            "dominant_workbook_path": "/tmp/arm_phase_mapping_sheet_workbook.csv",
                                            "dominant_delivery_csv_path": "/tmp/arm_phase_mapping_sheet_delivery.csv",
                                            "dominant_validation_command": "validate arm phase delivery",
                                            "dominant_packet_md_path": "/tmp/arm_phase_mapping_sheet_packet.md",
                                            "request_packet_md_path": "/tmp/request_01.md",
                                            "runtime_command": "run support runtime cycle",
                                            "operator_hint": "Fill the workbook rows before rerun.",
                                            "operator_summary": "Fill workbook rows.",
                                            "dominant_profile_id": "arm_phase_mapping_sheet",
                                        }
                                    ]
                                    if "pre_support_operator_board" in str(kwargs["output_dir"])
                                    else []
                                ),
                                "operator_hold_queue": (
                                    []
                                    if "pre_support_operator_board" in str(kwargs["output_dir"])
                                    else [
                                        {
                                            "support_request_reference": "bari_signal_phase_01",
                                            "request_id": "bari_signal_phase_01",
                                            "junction_id": "it-bari-signal-93",
                                            "signal_name": "Signal 93",
                                            "request_runtime_category": "fully_applied_to_movement_layer",
                                            "operator_action_category": "support_request_complete",
                                            "due_now": "no",
                                            "operator_summary": "Already applied.",
                                            "dominant_profile_id": "arm_phase_mapping_sheet",
                                        }
                                    ]
                                ),
                            },
                        ),
                    }
                },
            ) as operator_board_mock:
                result = run_bari_signal_phase_support_rehearsal(
                    output_dir=output_dir,
                    request_id="bari_signal_phase_01",
                    signal_phase_support_writeback_bundle_path=live_writeback_bundle_path,
                    signal_phase_support_resolution_bundle_path=support_resolution_bundle_path,
                    manual_mapping_stub_path=manual_mapping_stub_path,
                    delivery_checklist_path=delivery_checklist_path,
                    movement_objects_path=movement_objects_path,
                )

            self.assertEqual(apply_cycle_mock.call_count, 2)
            self.assertEqual(apply_status_mock.call_count, 2)
            self.assertEqual(request_state_mock.call_count, 2)
            self.assertEqual(operator_board_mock.call_count, 2)
            self.assertEqual(result["stats"]["pre_validation_action_count"], 0)
            self.assertEqual(result["stats"]["post_validation_action_count"], 2)
            self.assertEqual(result["stats"]["pre_operator_ready_count"], 1)
            self.assertEqual(result["stats"]["post_operator_ready_count"], 0)
            self.assertEqual(result["stats"]["pre_runtime_board_ready_count"], 1)
            self.assertEqual(result["stats"]["post_runtime_board_ready_count"], 0)
            self.assertEqual(result["stats"]["pre_runtime_action_ready_count"], 1)
            self.assertEqual(result["stats"]["post_runtime_action_ready_count"], 0)
            self.assertEqual(result["stats"]["pre_runtime_execution_ready_count"], 1)
            self.assertEqual(result["stats"]["post_runtime_execution_ready_count"], 0)
            self.assertEqual(result["stats"]["post_executed_validation_count"], 2)
            self.assertEqual(result["stats"]["post_accepted_for_ingestion_count"], 2)
            self.assertTrue(result["stats"]["post_delivery_session_executed"])
            self.assertEqual(result["stats"]["post_movements_with_phase_mapping"], 2)

            with (output_dir / "request_state_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                request_rows = list(csv.DictReader(handle))
            selected_request = next(
                row for row in request_rows if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_request["pre_request_status_category"],
                "pending_manual_resolution",
            )
            self.assertEqual(
                selected_request["post_request_status_category"],
                "ready_for_validation",
            )
            self.assertEqual(
                selected_request["post_validation_ready_profile_count"],
                "2",
            )

            with (output_dir / "request_runtime_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                request_runtime_rows = list(csv.DictReader(handle))
            selected_runtime = next(
                row for row in request_runtime_rows if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_runtime["pre_request_runtime_category"],
                "pending_manual_resolution",
            )
            self.assertEqual(
                selected_runtime["post_request_runtime_category"],
                "fully_applied_to_movement_layer",
            )

            with (output_dir / "operator_board_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                operator_rows = list(csv.DictReader(handle))
            selected_operator = next(
                row for row in operator_rows if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_operator["pre_operator_action_category"],
                "fill_support_workbook_now",
            )
            self.assertEqual(
                selected_operator["post_operator_action_category"],
                "support_request_complete",
            )

            with (output_dir / "runtime_board_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                runtime_board_rows = list(csv.DictReader(handle))
            selected_runtime_board = next(
                row
                for row in runtime_board_rows
                if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_runtime_board["pre_action_category"],
                "fill_support_workbook_now",
            )
            self.assertEqual(
                selected_runtime_board["post_action_category"],
                "support_request_complete",
            )

            with (output_dir / "runtime_action_queue_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                runtime_action_rows = list(csv.DictReader(handle))
            selected_runtime_action = next(
                row
                for row in runtime_action_rows
                if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_runtime_action["pre_final_action_category"],
                "support_fill_workbook_now",
            )
            self.assertEqual(
                selected_runtime_action["post_final_action_category"],
                "support_request_complete",
            )

            with (output_dir / "runtime_action_execution_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                runtime_execution_rows = list(csv.DictReader(handle))
            selected_runtime_execution = next(
                row
                for row in runtime_execution_rows
                if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(
                selected_runtime_execution["pre_final_action_category"],
                "support_fill_workbook_now",
            )
            self.assertEqual(
                selected_runtime_execution["post_final_action_category"],
                "support_request_complete",
            )
            self.assertEqual(
                selected_runtime_execution["pre_execution_route"],
                "support_workbook_fill",
            )
            self.assertEqual(
                selected_runtime_execution["post_queue_type"],
                "hold",
            )

            with (output_dir / "profile_state_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                profile_rows = list(csv.DictReader(handle))
            manual_profile = next(
                row
                for row in profile_rows
                if row["request_id"] == "bari_signal_phase_01"
                and row["profile_id"] == "arm_phase_mapping_sheet"
            )
            pedestrian_profile = next(
                row
                for row in profile_rows
                if row["request_id"] == "bari_signal_phase_01"
                and row["profile_id"] == "pedestrian_stage_mapping_sheet"
            )
            self.assertEqual(
                manual_profile["pre_action_category"], "fill_support_workbook_now"
            )
            self.assertEqual(
                manual_profile["post_action_category"], "validate_support_delivery_now"
            )
            self.assertEqual(
                pedestrian_profile["pre_action_category"],
                "fill_support_workbook_now",
            )
            self.assertEqual(
                pedestrian_profile["post_action_category"],
                "validate_support_delivery_now",
            )

            rehearsal_manual_workbook = (
                output_dir
                / "rehearsal_writeback"
                / "workbooks"
                / "arm_phase_mapping_sheet_workbook.csv"
            )
            with rehearsal_manual_workbook.open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                manual_rows = list(csv.DictReader(handle))
            self.assertEqual(manual_rows[0]["phase_id"], "phase_a")
            self.assertEqual(manual_rows[0]["stage_id"], "stage_1")
            self.assertEqual(manual_rows[0]["protection_state"], "protected")
            self.assertEqual(manual_rows[0]["outgoing_arm_id"], "arm_b")


if __name__ == "__main__":
    unittest.main()
