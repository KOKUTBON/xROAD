from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_validation_batch import (
    run_bari_signal_phase_support_validation_batch,
)


class SignalPhaseSupportValidationBatchTests(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_run_bari_signal_phase_support_validation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_validation_batch"
            action_queue_path = root / "action_execution_ready_queue.csv"
            delivery_csv_path = root / "arm_phase_mapping_sheet_delivery.csv"
            mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"
            checklist_path = root / "delivery_checklist.csv"

            self._write_csv(
                delivery_csv_path,
                [
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
                [
                    {
                        "junction_id": "it-bari-signal-93",
                        "incoming_arm_id": "arm_capruzzi_in",
                        "movement_turn": "u_turn",
                        "phase_id": "phase_09",
                        "stage_id": "stage_04",
                        "protection_state": "protected",
                        "outgoing_arm_id": "arm_capruzzi_out",
                        "pedestrian_stage_flag": "false",
                        "notes": "validated manually",
                    }
                ],
            )

            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_label": "Arm-to-phase mapping sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [
                            {"target_field": "junction_id", "source_field": "junction_id", "required": True, "type": "string"},
                            {"target_field": "incoming_arm_id", "source_field": "incoming_arm_id", "required": True, "type": "string"},
                            {"target_field": "movement_turn", "source_field": "movement_turn", "required": True, "type": "string"},
                            {"target_field": "phase_id", "source_field": "phase_id", "required": True, "type": "string"},
                            {"target_field": "stage_id", "source_field": "stage_id", "required": True, "type": "string"},
                            {"target_field": "protection_state", "source_field": "protection_state", "required": True, "type": "string"},
                            {"target_field": "outgoing_arm_id", "source_field": "outgoing_arm_id", "required": False, "type": "string"},
                            {"target_field": "pedestrian_stage_flag", "source_field": "pedestrian_stage_flag", "required": False, "type": "boolean"},
                        ],
                        "publication_policy": {},
                        "quality_gates": [],
                        "target_join_strategy": {"junction_key": "junction_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            self._write_csv(
                checklist_path,
                [
                    "delivery_item_id",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "priority_band",
                    "profile_id",
                    "owner_team",
                    "delivery_format",
                    "requested_window",
                    "acceptance_gate",
                    "delivery_status",
                    "received_date",
                    "validated_date",
                    "mapped_to_movements",
                    "notes",
                ],
                [
                    {
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "arm_phase_mapping_sheet",
                        "owner_team": "analyst",
                        "delivery_format": "CSV export",
                        "requested_window": "support_derived",
                        "acceptance_gate": "valid mappings",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "support derived",
                    }
                ],
            )

            self._write_csv(
                action_queue_path,
                [
                    "support_action_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "profile_id",
                    "action_category",
                    "execution_route",
                    "delivery_csv_path",
                    "mapping_stub_path",
                ],
                [
                    {
                        "support_action_reference": "bari_signal_phase_01:arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "arm_phase_mapping_sheet",
                        "action_category": "validate_support_delivery_now",
                        "execution_route": "validate_delivery",
                        "delivery_csv_path": str(delivery_csv_path),
                        "mapping_stub_path": str(mapping_stub_path),
                    },
                    {
                        "support_action_reference": "bari_signal_phase_01:pedestrian_stage_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "action_category": "fill_support_workbook_now",
                        "execution_route": "analyst_workbook_fill",
                        "delivery_csv_path": str(root / "pedestrian_delivery.csv"),
                        "mapping_stub_path": str(root / "pedestrian_mapping_stub.json"),
                    },
                ],
            )

            result = run_bari_signal_phase_support_validation_batch(
                output_dir=output_dir,
                action_execution_ready_queue_path=action_queue_path,
                delivery_checklist_path=checklist_path,
            )

            self.assertEqual(result["stats"]["action_queue_count"], 2)
            self.assertEqual(result["stats"]["validation_candidate_count"], 1)
            self.assertEqual(result["stats"]["executed_validation_count"], 1)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 1)
            self.assertEqual(result["stats"]["skipped_non_validation_action_count"], 1)

            with (output_dir / "support_validation_batch_results.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            executed = [row for row in rows if row["batch_outcome"] == "executed_validation"]
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0]["validation_outcome"], "accepted_for_ingestion")
            skipped = [row for row in rows if row["batch_outcome"] == "skipped_non_validation_action"]
            self.assertEqual(len(skipped), 1)

            payload = json.loads((output_dir / "signal_phase_support_validation_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["executed_validation_count"], 1)


if __name__ == "__main__":
    unittest.main()
