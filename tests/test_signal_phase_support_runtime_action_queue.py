from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_runtime_action_queue import (
    build_bari_signal_phase_support_runtime_action_queue,
)


class SignalPhaseSupportRuntimeActionQueueTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_runtime_action_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_runtime_action_queue"
            runtime_board_bundle_path = root / "signal_phase_support_runtime_board_bundle.json"

            runtime_board_bundle_path.write_text(
                json.dumps(
                    {
                        "operator_ready_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "action_category": "fill_support_workbook_now",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_workbook_fill",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/arm.csv",
                                "request_packet_md_path": "/tmp/request_01.md",
                                "packet_md_path": "/tmp/packet_01.md",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/arm.csv",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Fill workbook rows.",
                                "due_now": "yes",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "ready_for_validation",
                                "action_category": "validate_support_delivery_now",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "execution_route": "support_runtime_rerun",
                                "execution_target_kind": "support_runtime_command",
                                "execution_target": "make run-bari-signal-phase-support-runtime-cycle",
                                "request_packet_md_path": "/tmp/request_02.md",
                                "packet_md_path": "/tmp/packet_02.md",
                                "handoff_target_kind": "support_runtime_cycle_command",
                                "handoff_target_path": "/tmp/runtime.manifest.json",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "handoff_instructions": "Rerun support runtime.",
                                "due_now": "yes",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "review_support_validation_results",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_validation_review",
                                "execution_target_kind": "support_request_packet",
                                "execution_target": "/tmp/request_03.md",
                                "request_packet_md_path": "/tmp/request_03.md",
                                "packet_md_path": "/tmp/packet_03.md",
                                "handoff_target_kind": "support_request_packet",
                                "handoff_target_path": "/tmp/request_03.md",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Review packet.",
                                "due_now": "yes",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_04",
                                "request_id": "bari_signal_phase_04",
                                "junction_id": "it-bari-signal-67",
                                "signal_name": "Signal 67",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "repair_support_delivery",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_workbook_repair",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/repair.csv",
                                "request_packet_md_path": "/tmp/request_04.md",
                                "packet_md_path": "/tmp/packet_04.md",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/repair.csv",
                                "handoff_status": "handoff_ready",
                                "handoff_command": "",
                                "handoff_instructions": "Repair workbook.",
                                "due_now": "yes",
                            },
                        ],
                        "operator_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_05",
                                "request_id": "bari_signal_phase_05",
                                "junction_id": "it-bari-signal-57",
                                "signal_name": "Signal 57",
                                "request_runtime_category": "accepted_pending_apply",
                                "action_category": "support_apply_pending_refresh",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_05.md",
                                "packet_md_path": "/tmp/packet_05.md",
                                "hold_reason": "Accepted rows are waiting for apply refresh.",
                                "due_now": "no",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_06",
                                "request_id": "bari_signal_phase_06",
                                "junction_id": "it-bari-signal-27",
                                "signal_name": "Signal 27",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "action_category": "support_request_complete",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_06.md",
                                "packet_md_path": "/tmp/packet_06.md",
                                "hold_reason": "Already complete.",
                                "due_now": "no",
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_runtime_action_queue(
                output_dir=output_dir,
                signal_phase_support_runtime_board_bundle_path=runtime_board_bundle_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_runtime_action_queue_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 6)
            self.assertEqual(manifest["stats"]["immediate_action_count"], 4)
            self.assertEqual(manifest["stats"]["internal_hold_count"], 2)
            self.assertEqual(manifest["stats"]["workbook_action_count"], 1)
            self.assertEqual(manifest["stats"]["runtime_rerun_action_count"], 1)
            self.assertEqual(manifest["stats"]["validation_review_action_count"], 1)
            self.assertEqual(manifest["stats"]["repair_action_count"], 1)
            self.assertEqual(manifest["stats"]["apply_pending_hold_count"], 1)
            self.assertEqual(manifest["stats"]["complete_hold_count"], 1)

            with (output_dir / "action_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 4)
            self.assertEqual(ready_rows[0]["request_id"], "bari_signal_phase_04")
            by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                by_request["bari_signal_phase_01"]["final_action_category"],
                "support_fill_workbook_now",
            )
            self.assertEqual(
                by_request["bari_signal_phase_02"]["final_action_category"],
                "support_runtime_rerun_now",
            )
            self.assertEqual(
                by_request["bari_signal_phase_03"]["final_action_category"],
                "support_validation_review_now",
            )
            self.assertEqual(
                by_request["bari_signal_phase_04"]["final_action_category"],
                "support_repair_workbook_now",
            )

            with (output_dir / "action_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            hold_by_request = {row["request_id"]: row for row in hold_rows}
            self.assertEqual(
                hold_by_request["bari_signal_phase_05"]["final_action_category"],
                "support_apply_pending_refresh",
            )
            self.assertEqual(
                hold_by_request["bari_signal_phase_06"]["final_action_category"],
                "support_request_complete",
            )


if __name__ == "__main__":
    unittest.main()
