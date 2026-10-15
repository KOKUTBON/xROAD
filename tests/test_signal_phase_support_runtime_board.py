from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_runtime_board import (
    build_bari_signal_phase_support_runtime_board_bundle,
)


class SignalPhaseSupportRuntimeBoardTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_runtime_board_bundle_merges_execution_and_handoff(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_runtime_board"
            action_execution_bundle_path = root / "signal_phase_support_action_execution_bundle.json"
            action_handoff_bundle_path = root / "signal_phase_support_action_handoff_bundle.json"

            action_execution_bundle_path.write_text(
                json.dumps(
                    {
                        "execution_ready_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "action_category": "fill_support_workbook_now",
                                "execution_route": "support_workbook_fill",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/arm_workbook.csv",
                                "execution_summary": "Complete workbook rows.",
                                "request_packet_md_path": "/tmp/request_01.md",
                                "packet_md_path": "/tmp/packet_01.md",
                                "priority_rank": 4,
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "ready_for_validation",
                                "action_category": "validate_support_delivery_now",
                                "execution_route": "support_runtime_rerun",
                                "due_now": "yes",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "execution_target_kind": "support_runtime_command",
                                "execution_target": "make run-bari-signal-phase-support-runtime-cycle",
                                "execution_summary": "Rerun the support runtime.",
                                "request_packet_md_path": "/tmp/request_02.md",
                                "packet_md_path": "/tmp/packet_02.md",
                                "priority_rank": 3,
                            },
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "review_support_validation_results",
                                "execution_route": "support_validation_review",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_target_kind": "support_request_packet",
                                "execution_target": "/tmp/request_03.md",
                                "execution_summary": "Review validation results.",
                                "request_packet_md_path": "/tmp/request_03.md",
                                "packet_md_path": "/tmp/packet_03.md",
                                "priority_rank": 2,
                            },
                            {
                                "support_request_reference": "bari_signal_phase_04",
                                "request_id": "bari_signal_phase_04",
                                "junction_id": "it-bari-signal-67",
                                "signal_name": "Signal 67",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "repair_support_delivery",
                                "execution_route": "support_workbook_repair",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/repair_workbook.csv",
                                "execution_summary": "Repair workbook rows.",
                                "request_packet_md_path": "/tmp/request_04.md",
                                "packet_md_path": "/tmp/packet_04.md",
                                "priority_rank": 1,
                            },
                        ],
                        "internal_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_05",
                                "request_id": "bari_signal_phase_05",
                                "junction_id": "it-bari-signal-57",
                                "signal_name": "Signal 57",
                                "request_runtime_category": "accepted_pending_apply",
                                "action_category": "support_apply_pending_refresh",
                                "execution_route": "",
                                "due_now": "no",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_05.md",
                                "packet_md_path": "/tmp/packet_05.md",
                                "hold_reason": "Accepted rows are waiting for apply refresh.",
                                "priority_rank": 5,
                            },
                            {
                                "support_request_reference": "bari_signal_phase_06",
                                "request_id": "bari_signal_phase_06",
                                "junction_id": "it-bari-signal-27",
                                "signal_name": "Signal 27",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "action_category": "support_request_complete",
                                "execution_route": "",
                                "due_now": "no",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_06.md",
                                "packet_md_path": "/tmp/packet_06.md",
                                "hold_reason": "Request is already complete.",
                                "priority_rank": 6,
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            action_handoff_bundle_path.write_text(
                json.dumps(
                    {
                        "handoff_ready_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/arm_workbook.csv",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Fill workbook rows.",
                                "handoff_reference_key": "workbook_path",
                                "handoff_reference_value": "/tmp/arm_workbook.csv",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "handoff_target_kind": "support_runtime_cycle_command",
                                "handoff_target_path": "/tmp/runtime_cycle.manifest.json",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "handoff_instructions": "Rerun support runtime.",
                                "handoff_reference_key": "runtime_cycle_manifest_path",
                                "handoff_reference_value": "/tmp/runtime_cycle.manifest.json",
                            },
                            {
                                "request_id": "bari_signal_phase_03",
                                "handoff_target_kind": "support_request_packet",
                                "handoff_target_path": "/tmp/request_03.md",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Review request packet.",
                                "handoff_reference_key": "request_packet_md_path",
                                "handoff_reference_value": "/tmp/request_03.md",
                            },
                            {
                                "request_id": "bari_signal_phase_04",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/repair_workbook.csv",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Repair workbook rows.",
                                "handoff_reference_key": "workbook_path",
                                "handoff_reference_value": "/tmp/repair_workbook.csv",
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_runtime_board_bundle(
                output_dir=output_dir,
                signal_phase_support_action_execution_bundle_path=action_execution_bundle_path,
                signal_phase_support_action_handoff_bundle_path=action_handoff_bundle_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_runtime_board_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 6)
            self.assertEqual(manifest["stats"]["operator_ready_count"], 4)
            self.assertEqual(manifest["stats"]["internal_hold_count"], 2)
            self.assertEqual(manifest["stats"]["workbook_row_count"], 2)
            self.assertEqual(manifest["stats"]["runtime_rerun_row_count"], 1)
            self.assertEqual(manifest["stats"]["validation_review_row_count"], 1)
            self.assertEqual(manifest["stats"]["repair_row_count"], 1)
            self.assertEqual(manifest["stats"]["apply_pending_hold_count"], 1)
            self.assertEqual(manifest["stats"]["complete_hold_count"], 1)

            with (output_dir / "operator_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 4)
            self.assertEqual(ready_rows[0]["request_id"], "bari_signal_phase_04")
            ready_by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                ready_by_request["bari_signal_phase_01"]["handoff_target_kind"],
                "support_workbook_csv",
            )
            self.assertEqual(
                ready_by_request["bari_signal_phase_02"]["handoff_target_kind"],
                "support_runtime_cycle_command",
            )
            self.assertEqual(
                ready_by_request["bari_signal_phase_03"]["handoff_target_kind"],
                "support_request_packet",
            )

            with (output_dir / "operator_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(hold_rows), 2)
            hold_by_request = {row["request_id"]: row for row in hold_rows}
            self.assertEqual(
                hold_by_request["bari_signal_phase_05"]["action_category"],
                "support_apply_pending_refresh",
            )
            self.assertEqual(
                hold_by_request["bari_signal_phase_06"]["action_category"],
                "support_request_complete",
            )


if __name__ == "__main__":
    unittest.main()
