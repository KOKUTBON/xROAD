from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_operator_board import (
    build_bari_signal_phase_support_operator_board_bundle,
)


class SignalPhaseSupportOperatorBoardTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_operator_board_bundle_merges_request_and_profile_actions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_operator_board"
            request_state_bundle_path = root / "signal_phase_support_request_state_bundle.json"
            support_action_queue_path = root / "signal_phase_support_action_queue.json"

            request_state_bundle_path.write_text(
                json.dumps(
                    {
                        "request_support_runtime_state": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "request_runtime_summary": "pending_manual_resolution: 0/2 applied, 0 ready, 2 waiting",
                                "next_action": "Complete workbook rows.",
                                "recommended_next_action": "Resolve arm-phase and pedestrian-stage mappings.",
                                "profile_count": 2,
                                "applied_profile_count": 0,
                                "accepted_pending_apply_count": 0,
                                "ready_for_validation_count": 0,
                                "waiting_for_analyst_resolution_count": 2,
                                "signalized_movement_count": 3,
                                "matched_crashes_at_junction_total": 8,
                                "unresolved_signalized_movement_count": 1,
                                "unresolved_signalized_crash_total": 4,
                                "manual_workbook_path": "/tmp/arm.csv",
                                "pedestrian_workbook_path": "/tmp/ped.csv",
                                "manual_delivery_path": "/tmp/arm_delivery.csv",
                                "pedestrian_delivery_path": "/tmp/ped_delivery.csv",
                                "packet_md_path": "/tmp/bari_signal_phase_01.md",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "request_runtime_summary": "fully_applied_to_movement_layer: 2/2 applied, 0 ready, 0 waiting",
                                "next_action": "No action required.",
                                "recommended_next_action": "None.",
                                "profile_count": 2,
                                "applied_profile_count": 2,
                                "accepted_pending_apply_count": 0,
                                "ready_for_validation_count": 0,
                                "waiting_for_analyst_resolution_count": 0,
                                "signalized_movement_count": 2,
                                "matched_crashes_at_junction_total": 3,
                                "unresolved_signalized_movement_count": 0,
                                "unresolved_signalized_crash_total": 0,
                                "manual_workbook_path": "/tmp/arm2.csv",
                                "pedestrian_workbook_path": "/tmp/ped2.csv",
                                "manual_delivery_path": "/tmp/arm2_delivery.csv",
                                "pedestrian_delivery_path": "/tmp/ped2_delivery.csv",
                                "packet_md_path": "/tmp/bari_signal_phase_02.md",
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            support_action_queue_path.write_text(
                json.dumps(
                    {
                        "action_execution_ready_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "profile_id": "arm_phase_mapping_sheet",
                                "action_category": "fill_support_workbook_now",
                                "execution_route": "analyst_workbook_fill",
                                "pending_row_count": 18,
                                "ready_row_count": 0,
                                "workbook_path": "/tmp/arm.csv",
                                "delivery_csv_path": "/tmp/arm_delivery.csv",
                                "validation_command": "validate arm",
                                "packet_md_path": "/tmp/arm_packet.md",
                            },
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "profile_id": "pedestrian_stage_mapping_sheet",
                                "action_category": "fill_support_workbook_now",
                                "execution_route": "analyst_workbook_fill",
                                "pending_row_count": 8,
                                "ready_row_count": 0,
                                "workbook_path": "/tmp/ped.csv",
                                "delivery_csv_path": "/tmp/ped_delivery.csv",
                                "validation_command": "validate ped",
                                "packet_md_path": "/tmp/ped_packet.md",
                            },
                        ],
                        "action_internal_hold_queue": [
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "profile_id": "arm_phase_mapping_sheet",
                                "action_category": "support_apply_complete",
                                "execution_route": "",
                                "pending_row_count": 0,
                                "ready_row_count": 0,
                                "workbook_path": "/tmp/arm2.csv",
                                "delivery_csv_path": "/tmp/arm2_delivery.csv",
                                "validation_command": "",
                                "packet_md_path": "/tmp/arm2_packet.md",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "profile_id": "pedestrian_stage_mapping_sheet",
                                "action_category": "support_apply_complete",
                                "execution_route": "",
                                "pending_row_count": 0,
                                "ready_row_count": 0,
                                "workbook_path": "/tmp/ped2.csv",
                                "delivery_csv_path": "/tmp/ped2_delivery.csv",
                                "validation_command": "",
                                "packet_md_path": "/tmp/ped2_packet.md",
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_support_operator_board_bundle(
                output_dir=output_dir,
                signal_phase_support_request_state_bundle_path=request_state_bundle_path,
                signal_phase_support_action_queue_path=support_action_queue_path,
                support_runtime_command="make run-bari-signal-phase-support-runtime-cycle",
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["operator_ready_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["workbook_fill_request_count"], 1)
            self.assertEqual(result["stats"]["complete_request_count"], 1)
            self.assertEqual(
                result["stats"]["requests_with_unresolved_signalized_movements_count"],
                1,
            )
            self.assertEqual(result["stats"]["unresolved_signalized_movement_count_total"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 4)

            with (output_dir / "operator_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(ready_rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(ready_rows[0]["operator_action_category"], "fill_support_workbook_now")
            self.assertEqual(ready_rows[0]["dominant_profile_id"], "arm_phase_mapping_sheet")
            self.assertEqual(ready_rows[0]["unresolved_signalized_movement_count"], "1")
            self.assertEqual(ready_rows[0]["unresolved_signalized_crash_total"], "4")
            self.assertEqual(
                ready_rows[0]["runtime_command"],
                "make run-bari-signal-phase-support-runtime-cycle",
            )

            with (output_dir / "operator_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(hold_rows[0]["request_id"], "bari_signal_phase_02")
            self.assertEqual(hold_rows[0]["operator_action_category"], "support_request_complete")
            self.assertEqual(hold_rows[0]["unresolved_signalized_movement_count"], "0")

            payload = json.loads(
                (output_dir / "signal_phase_support_operator_board_bundle.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["summary"]["unresolved_signalized_crash_total"], 4)

            report_md = (output_dir / "signal_phase_support_operator_board_bundle.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("requests with unresolved signalized movements: `1`", report_md)
            self.assertIn("unresolved signalized crashes: `4`", report_md)

            packet_md = (output_dir / "request_packets" / "bari_signal_phase_01.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("unresolved signalized movements: `1`", packet_md)
            self.assertIn("unresolved signalized crashes: `4`", packet_md)


if __name__ == "__main__":
    unittest.main()
