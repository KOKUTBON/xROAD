from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_action_execution import (
    build_bari_signal_phase_support_action_execution_bundle,
)


class SignalPhaseSupportActionExecutionTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_action_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_action_execution"
            operator_board_bundle_path = root / "signal_phase_support_operator_board_bundle.json"

            operator_board_bundle_path.write_text(
                json.dumps(
                    {
                        "operator_ready_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "operator_action_category": "fill_support_workbook_now",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "dominant_workbook_path": "/tmp/arm_phase_mapping_sheet_workbook.csv",
                                "dominant_delivery_csv_path": "/tmp/by_request/bari_signal_phase_01/arm_phase_mapping_sheet_delivery.csv",
                                "dominant_validation_command": "validate arm delivery",
                                "dominant_packet_md_path": "/tmp/arm_packet.md",
                                "request_packet_md_path": "/tmp/bari_signal_phase_01.md",
                                "runtime_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "operator_summary": "Fill the workbook.",
                                "operator_hint": "Complete workbook rows first.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "ready_for_validation",
                                "operator_action_category": "validate_support_delivery_now",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "dominant_workbook_path": "/tmp/pedestrian_stage_mapping_sheet_workbook.csv",
                                "dominant_delivery_csv_path": "/tmp/by_request/bari_signal_phase_02/pedestrian_stage_mapping_sheet_delivery.csv",
                                "dominant_validation_command": "validate ped delivery",
                                "dominant_packet_md_path": "/tmp/ped_packet.md",
                                "request_packet_md_path": "/tmp/bari_signal_phase_02.md",
                                "runtime_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "operator_summary": "Validate the delivery.",
                                "operator_hint": "Rerun the support runtime.",
                            },
                        ],
                        "operator_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "operator_action_category": "support_request_complete",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "request_packet_md_path": "/tmp/bari_signal_phase_03.md",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_action_execution_bundle(
                output_dir=output_dir,
                signal_phase_support_operator_board_bundle_path=operator_board_bundle_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_action_execution_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 3)
            self.assertEqual(manifest["stats"]["execution_ready_count"], 2)
            self.assertEqual(manifest["stats"]["internal_hold_count"], 1)
            self.assertEqual(manifest["stats"]["workbook_fill_request_count"], 1)
            self.assertEqual(manifest["stats"]["runtime_rerun_request_count"], 1)
            self.assertEqual(manifest["stats"]["complete_hold_count"], 1)

            with (output_dir / "action_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 2)
            ready_by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                ready_by_request["bari_signal_phase_01"]["execution_route"],
                "support_workbook_fill",
            )
            self.assertEqual(
                ready_by_request["bari_signal_phase_01"]["execution_target_kind"],
                "support_workbook_csv",
            )
            self.assertEqual(
                ready_by_request["bari_signal_phase_02"]["execution_route"],
                "support_runtime_rerun",
            )
            self.assertEqual(
                ready_by_request["bari_signal_phase_02"]["execution_target_kind"],
                "support_runtime_command",
            )

            with (output_dir / "action_internal_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(hold_rows), 1)
            self.assertEqual(hold_rows[0]["request_id"], "bari_signal_phase_03")
            self.assertIn("fully applied", hold_rows[0]["hold_reason"].lower())

            self.assertTrue(
                (output_dir / "execution_packets" / "bari_signal_phase_01.md").exists()
            )


if __name__ == "__main__":
    unittest.main()
