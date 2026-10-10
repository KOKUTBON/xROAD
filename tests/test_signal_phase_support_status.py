from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_status import (
    build_bari_signal_phase_support_status_bundle,
)


class SignalPhaseSupportStatusTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_status_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_status"
            writeback_bundle_path = root / "signal_phase_support_writeback_bundle.json"
            manual_workbook_path = root / "arm_phase_mapping_sheet_workbook.csv"
            pedestrian_workbook_path = root / "pedestrian_stage_mapping_sheet_workbook.csv"
            manual_delivery_path = root / "arm_phase_mapping_sheet_delivery.csv"
            pedestrian_delivery_path = root / "pedestrian_stage_mapping_sheet_delivery.csv"
            request_manual_delivery_path = root / "by_request" / "bari_signal_phase_01" / "arm_phase_mapping_sheet_delivery.csv"
            request_pedestrian_delivery_path = (
                root / "by_request" / "bari_signal_phase_01" / "pedestrian_stage_mapping_sheet_delivery.csv"
            )
            validation_commands_path = root / "validation_commands.csv"

            with manual_workbook_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "incoming_arm_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "incoming_arm_id": "arm_1",
                        "movement_turn": "left",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "protection_state": "protected",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "incoming_arm_id": "arm_2",
                        "movement_turn": "u_turn",
                        "phase_id": "",
                        "stage_id": "",
                        "protection_state": "",
                    }
                )

            with pedestrian_workbook_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "node_object_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "node_object_id": "ped_1",
                        "movement_turn": "cross",
                        "phase_id": "",
                        "stage_id": "",
                        "protection_state": "",
                    }
                )

            with manual_delivery_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "incoming_arm_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                        "outgoing_arm_id",
                        "pedestrian_stage_flag",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "it-bari-signal-93",
                        "incoming_arm_id": "arm_1",
                        "movement_turn": "left",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "protection_state": "protected",
                        "outgoing_arm_id": "",
                        "pedestrian_stage_flag": "",
                        "notes": "",
                    }
                )

            with pedestrian_delivery_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "node_object_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                        "pedestrian_stage_flag",
                        "notes",
                    ],
                )
                writer.writeheader()

            with validation_commands_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "profile_id",
                        "delivery_csv_path",
                        "mapping_stub_path",
                        "validation_command",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "profile_id": "arm_phase_mapping_sheet",
                        "delivery_csv_path": str(request_manual_delivery_path),
                        "mapping_stub_path": str(root / "manual_stub.json"),
                        "validation_command": "validate manual",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "delivery_csv_path": str(request_pedestrian_delivery_path),
                        "mapping_stub_path": str(root / "ped_stub.json"),
                        "validation_command": "validate pedestrian",
                    }
                )

            writeback_bundle_path.write_text(
                json.dumps(
                    {
                        "request_writeback_status": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A",
                                "signalized_movement_count": 3,
                                "matched_crashes_at_junction_total": 8,
                                "unresolved_signalized_movement_count": 1,
                                "unresolved_signalized_crash_total": 4,
                                "recommended_next_action": "Resolve arm mappings first.",
                                "manual_delivery_path": str(request_manual_delivery_path),
                                "pedestrian_delivery_path": str(request_pedestrian_delivery_path),
                            }
                        ],
                        "manual_mapping_workbook_path": str(manual_workbook_path),
                        "pedestrian_mapping_workbook_path": str(pedestrian_workbook_path),
                        "manual_delivery_path": str(manual_delivery_path),
                        "pedestrian_delivery_path": str(pedestrian_delivery_path),
                        "validation_commands_path": str(validation_commands_path),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_status_bundle(
                output_dir=output_dir,
                signal_phase_support_writeback_bundle_path=writeback_bundle_path,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_support_status_bundle_builder")
            self.assertEqual(manifest["stats"]["support_request_count"], 1)
            self.assertEqual(manifest["stats"]["requests_partially_ready_for_validation_count"], 1)
            self.assertEqual(manifest["stats"]["requests_pending_manual_resolution_count"], 0)
            self.assertEqual(
                manifest["stats"]["requests_with_unresolved_signalized_movements_count"],
                1,
            )
            self.assertEqual(manifest["stats"]["unresolved_signalized_movement_count_total"], 1)
            self.assertEqual(manifest["stats"]["unresolved_signalized_crash_total"], 4)
            self.assertEqual(manifest["stats"]["validation_ready_profile_count"], 1)
            self.assertEqual(manifest["stats"]["validation_hold_profile_count"], 1)
            self.assertEqual(manifest["stats"]["analyst_work_queue_count"], 1)

            with (output_dir / "request_support_status.csv").open("r", encoding="utf-8", newline="") as handle:
                request_rows = list(csv.DictReader(handle))
            self.assertEqual(len(request_rows), 1)
            self.assertEqual(request_rows[0]["request_status_category"], "partially_ready_for_validation")
            self.assertEqual(request_rows[0]["manual_ready_count"], "1")
            self.assertEqual(request_rows[0]["manual_pending_count"], "1")
            self.assertEqual(request_rows[0]["pedestrian_pending_count"], "1")
            self.assertEqual(request_rows[0]["unresolved_signalized_movement_count"], "1")
            self.assertEqual(request_rows[0]["unresolved_signalized_crash_total"], "4")

            with (output_dir / "analyst_work_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                analyst_rows = list(csv.DictReader(handle))
            self.assertEqual(len(analyst_rows), 1)
            self.assertEqual(analyst_rows[0]["request_id"], "bari_signal_phase_01")

            with (output_dir / "validation_ready_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 1)
            self.assertEqual(ready_rows[0]["profile_id"], "arm_phase_mapping_sheet")
            self.assertEqual(ready_rows[0]["ready_row_count"], "1")
            self.assertEqual(ready_rows[0]["pending_row_count"], "1")
            self.assertEqual(ready_rows[0]["delivery_csv_path"], str(request_manual_delivery_path))

            with (output_dir / "validation_hold_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(hold_rows), 1)
            self.assertEqual(hold_rows[0]["profile_id"], "pedestrian_stage_mapping_sheet")
            self.assertEqual(hold_rows[0]["validation_state_category"], "waiting_for_analyst_resolution")
            self.assertEqual(hold_rows[0]["delivery_csv_path"], str(request_pedestrian_delivery_path))

            packet_path = output_dir / "request_packets" / "bari_signal_phase_01.md"
            self.assertTrue(packet_path.exists())

            payload = json.loads((output_dir / "signal_phase_support_status_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["validation_ready_profile_count"], 1)
            self.assertEqual(payload["summary"]["unresolved_signalized_crash_total"], 4)
            self.assertEqual(payload["request_support_status"][0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(
                payload["request_support_status"][0]["unresolved_signalized_movement_count"],
                1,
            )

            report_md = (output_dir / "signal_phase_support_status_bundle.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("requests with unresolved signalized movements: `1`", report_md)
            self.assertIn("unresolved signalized crashes: `4`", report_md)


if __name__ == "__main__":
    unittest.main()
