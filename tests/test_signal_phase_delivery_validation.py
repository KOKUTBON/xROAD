from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_delivery_validation import validate_signal_phase_delivery


class SignalPhaseDeliveryValidationTests(unittest.TestCase):
    def test_validate_signal_phase_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "validation"
            input_csv_path = root / "controller_event_log.csv"
            mapping_stub_path = root / "mapping_stub.json"
            checklist_path = root / "delivery_checklist.csv"

            with input_csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "device_id",
                        "event_start_utc",
                        "event_end_utc",
                        "phase_id",
                        "stage_id",
                        "event_type",
                        "control_mode",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "it-bari-signal-93",
                        "device_id": "bari_ctrl_001",
                        "event_start_utc": "2025-05-06T07:00:00Z",
                        "event_end_utc": "2025-05-06T07:01:30Z",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "event_type": "stage_active",
                        "control_mode": "controller_runtime",
                    }
                )

            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "profile_id": "controller_event_log_export",
                        "profile_label": "Controller event log export",
                        "profile_type": "provider_feed",
                        "field_mappings": [
                            {"required": True, "source_field": "TODO_controller_event_log_export__junction_id", "target_field": "junction_id", "type": "string"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__device_id", "target_field": "device_id", "type": "string"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__event_start_utc", "target_field": "event_start_utc", "type": "datetime"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__event_end_utc", "target_field": "event_end_utc", "type": "datetime"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__phase_id", "target_field": "phase_id", "type": "string"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__stage_id", "target_field": "stage_id", "type": "string"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__event_type", "target_field": "event_type", "type": "string"},
                            {"required": True, "source_field": "TODO_controller_event_log_export__control_mode", "target_field": "control_mode", "type": "string"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with checklist_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
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
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "controller_event_log_export",
                        "owner_team": "traffic control center",
                        "delivery_format": "CSV export",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "valid events",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "primary",
                    }
                )

            result = validate_signal_phase_delivery(
                input_csv_path,
                mapping_stub_path,
                output_dir,
                delivery_checklist_path=checklist_path,
                junction_id="it-bari-signal-93",
            )

            self.assertEqual(result["stats"]["validation_outcome"], "accepted_for_ingestion")
            self.assertEqual(result["stats"]["matched_checklist_rows"], 1)
            self.assertEqual(result["stats"]["accepted_rows"], 1)
            self.assertEqual(result["stats"]["rejected_rows"], 0)

            report_payload = json.loads((output_dir / "signal_phase_delivery_validation.json").read_text(encoding="utf-8"))
            self.assertEqual(report_payload["stats"]["suggested_delivery_status"], "validated_ready_for_ingestion")
            self.assertEqual(report_payload["profile"]["profile_id"], "controller_event_log_export")

            with (output_dir / "checklist_recommendations.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["suggested_delivery_status"], "validated_ready_for_ingestion")

    def test_validate_signal_phase_support_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "validation"
            input_file_path = root / "junction_phase_diagram_support.pdf"
            mapping_stub_path = root / "mapping_stub.json"
            checklist_path = root / "delivery_checklist.csv"

            input_file_path.write_text("%PDF-1.4\nBari signal-phase support sample\n", encoding="utf-8")
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "profile_id": "junction_phase_diagram_support",
                        "profile_label": "Junction phase diagram support",
                        "profile_type": "support_artifact",
                        "field_mappings": [],
                        "support_validation": {
                            "validation_mode": "file_presence_and_extension",
                            "allowed_extensions": [".pdf", ".png"],
                            "minimum_file_size_bytes": 16,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with checklist_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
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
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "junction_phase_diagram_support",
                        "owner_team": "traffic control center",
                        "delivery_format": "PDF support diagram",
                        "requested_window": "current_layout",
                        "acceptance_gate": "diagram identifies stages",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "support",
                    }
                )

            result = validate_signal_phase_delivery(
                input_file_path,
                mapping_stub_path,
                output_dir,
                delivery_checklist_path=checklist_path,
                request_id="bari_signal_phase_01",
                junction_id="it-bari-signal-93",
            )

            self.assertEqual(result["stats"]["validation_outcome"], "accepted_support_artifact")
            self.assertEqual(result["stats"]["accepted_rows"], 1)
            self.assertEqual(result["stats"]["support_file_size_bytes"], input_file_path.stat().st_size)

            report_payload = json.loads((output_dir / "signal_phase_delivery_validation.json").read_text(encoding="utf-8"))
            self.assertEqual(report_payload["stats"]["suggested_delivery_status"], "validated_support_artifact")
            self.assertEqual(report_payload["schema"]["detected_support_extension"], ".pdf")

            with (output_dir / "checklist_recommendations.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["suggested_delivery_status"], "validated_support_artifact")


if __name__ == "__main__":
    unittest.main()
