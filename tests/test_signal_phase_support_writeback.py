from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_writeback import (
    build_bari_signal_phase_support_writeback_bundle,
)


class SignalPhaseSupportWritebackTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_writeback"
            support_resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"

            support_resolution_bundle_path.write_text(
                json.dumps(
                    {
                        "summary": {"support_request_count": 1},
                        "support_resolution_requests": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "signalized_movement_count": 3,
                                "matched_crashes_at_junction_total": 8,
                                "unresolved_signalized_movement_count": 1,
                                "unresolved_signalized_crash_total": 4,
                                "recommended_next_action": "arm_phase_and_pedestrian_stage_resolution",
                            }
                        ],
                        "manual_arm_phase_review": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "signal_type": "traffic_signal",
                                "incoming_arm_id": "arm_capruzzi_in",
                                "movement_turn": "u_turn",
                                "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                "crash_total": 50,
                                "injury_total": 12,
                                "peak_year": "2024",
                                "peak_year_crash_count": 18,
                                "candidate_target_arm_catalog": "arm_capruzzi_out | arm_b_croce_out",
                                "outgoing_arm_catalog": "arm_capruzzi_out | arm_b_croce_out",
                                "movement_variant_count": 2,
                                "movement_ids": "move_1 | move_2",
                                "support_artifact_path": "data/support/bari_signal_phase_01.pdf",
                                "validation_manifest_path": "data/quality/support_validation.manifest.json",
                                "manual_mapping_hint": "Use support diagram to disambiguate u-turn stage.",
                            }
                        ],
                        "pedestrian_stage_review": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "signal_type": "traffic_signal",
                                "node_object_id": "ped_cross_1",
                                "movement_turn": "cross",
                                "crash_total": 1,
                                "injury_total": 0,
                                "peak_year": "2024",
                                "peak_year_crash_count": 1,
                                "support_artifact_path": "data/support/bari_signal_phase_01.pdf",
                                "validation_manifest_path": "data/quality/support_validation.manifest.json",
                                "manual_mapping_hint": "Match crossing stage from the support diagram.",
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
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            workbooks_dir = output_dir / "workbooks"
            workbooks_dir.mkdir(parents=True, exist_ok=True)
            with (workbooks_dir / "arm_phase_mapping_sheet_workbook.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "signal_type",
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
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "legacy",
                        "signal_type": "legacy",
                        "incoming_arm_id": "arm_capruzzi_in",
                        "movement_turn": "u_turn",
                        "phase_id": "phase_09",
                        "stage_id": "stage_04",
                        "protection_state": "protected",
                        "outgoing_arm_id": "arm_capruzzi_out",
                        "pedestrian_stage_flag": "false",
                        "notes": "validated manually",
                    }
                )
            with (workbooks_dir / "pedestrian_stage_mapping_sheet_workbook.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "signal_type",
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
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "legacy",
                        "signal_type": "legacy",
                        "node_object_id": "ped_cross_1",
                        "movement_turn": "cross",
                        "phase_id": "phase_11",
                        "stage_id": "stage_07",
                        "protection_state": "protected",
                        "pedestrian_stage_flag": "true",
                        "notes": "crossing stage confirmed",
                    }
                )

            manifest = build_bari_signal_phase_support_writeback_bundle(
                output_dir=output_dir,
                signal_phase_support_resolution_bundle_path=support_resolution_bundle_path,
                manual_mapping_stub_path=manual_mapping_stub_path,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_support_writeback_bundle_builder")
            self.assertEqual(manifest["stats"]["support_request_count"], 1)
            self.assertEqual(manifest["stats"]["manual_workbook_row_count"], 1)
            self.assertEqual(manifest["stats"]["pedestrian_workbook_row_count"], 1)
            self.assertEqual(
                manifest["stats"]["requests_with_unresolved_signalized_movements_count"],
                1,
            )
            self.assertEqual(manifest["stats"]["unresolved_signalized_movement_count_total"], 1)
            self.assertEqual(manifest["stats"]["unresolved_signalized_crash_total"], 4)
            self.assertEqual(manifest["stats"]["manual_delivery_ready_count"], 1)
            self.assertEqual(manifest["stats"]["pedestrian_delivery_ready_count"], 1)
            self.assertEqual(manifest["stats"]["validation_command_count"], 2)

            with (output_dir / "workbooks" / "arm_phase_mapping_sheet_workbook.csv").open("r", encoding="utf-8", newline="") as handle:
                manual_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manual_rows), 1)
            self.assertEqual(manual_rows[0]["phase_id"], "phase_09")
            self.assertEqual(manual_rows[0]["stage_id"], "stage_04")
            self.assertEqual(manual_rows[0]["outgoing_arm_id"], "arm_capruzzi_out")
            self.assertEqual(manual_rows[0]["notes"], "validated manually")

            with (output_dir / "workbooks" / "pedestrian_stage_mapping_sheet_workbook.csv").open("r", encoding="utf-8", newline="") as handle:
                pedestrian_rows = list(csv.DictReader(handle))
            self.assertEqual(len(pedestrian_rows), 1)
            self.assertEqual(pedestrian_rows[0]["node_object_id"], "ped_cross_1")
            self.assertEqual(pedestrian_rows[0]["phase_id"], "phase_11")
            self.assertEqual(pedestrian_rows[0]["pedestrian_stage_flag"], "true")

            with (output_dir / "deliveries" / "arm_phase_mapping_sheet_delivery.csv").open("r", encoding="utf-8", newline="") as handle:
                manual_delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manual_delivery_rows), 1)
            self.assertEqual(manual_delivery_rows[0]["incoming_arm_id"], "arm_capruzzi_in")

            request_manual_delivery_path = (
                output_dir / "deliveries" / "by_request" / "bari_signal_phase_01" / "arm_phase_mapping_sheet_delivery.csv"
            )
            with request_manual_delivery_path.open("r", encoding="utf-8", newline="") as handle:
                request_manual_delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(request_manual_delivery_rows), 1)

            with (output_dir / "deliveries" / "pedestrian_stage_mapping_sheet_delivery.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                pedestrian_delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(pedestrian_delivery_rows), 1)
            self.assertEqual(pedestrian_delivery_rows[0]["node_object_id"], "ped_cross_1")

            request_pedestrian_delivery_path = (
                output_dir / "deliveries" / "by_request" / "bari_signal_phase_01" / "pedestrian_stage_mapping_sheet_delivery.csv"
            )
            with request_pedestrian_delivery_path.open("r", encoding="utf-8", newline="") as handle:
                request_pedestrian_delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(request_pedestrian_delivery_rows), 1)

            pedestrian_stub = json.loads(
                (output_dir / "mapping_stubs" / "pedestrian_stage_mapping_sheet_mapping_stub.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(pedestrian_stub["profile_id"], "pedestrian_stage_mapping_sheet")
            self.assertEqual(
                pedestrian_stub["target_join_strategy"]["movement_mapping_level"],
                "direct_node_object_to_phase",
            )

            with (output_dir / "validation_commands" / "validation_commands.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                validation_rows = list(csv.DictReader(handle))
            self.assertEqual(len(validation_rows), 2)
            self.assertEqual({row["profile_id"] for row in validation_rows}, {"arm_phase_mapping_sheet", "pedestrian_stage_mapping_sheet"})
            self.assertEqual(
                {row["delivery_csv_path"] for row in validation_rows},
                {str(request_manual_delivery_path), str(request_pedestrian_delivery_path)},
            )

            payload = json.loads((output_dir / "signal_phase_support_writeback_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["manual_delivery_ready_count"], 1)
            self.assertEqual(payload["summary"]["unresolved_signalized_crash_total"], 4)
            self.assertEqual(payload["request_writeback_status"][0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(payload["request_writeback_status"][0]["manual_delivery_path"], str(request_manual_delivery_path))
            self.assertEqual(
                payload["request_writeback_status"][0]["unresolved_signalized_movement_count"],
                1,
            )
            self.assertEqual(
                payload["request_writeback_status"][0]["unresolved_signalized_crash_total"],
                4,
            )

            report_md = (output_dir / "signal_phase_support_writeback_bundle.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("requests with unresolved signalized movements: `1`", report_md)
            self.assertIn("unresolved signalized crashes: `4`", report_md)


if __name__ == "__main__":
    unittest.main()
