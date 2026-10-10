from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_validation_batch import run_bari_signal_phase_validation_batch


class SignalPhaseValidationBatchTests(unittest.TestCase):
    def test_run_bari_signal_phase_validation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "validation_batch"
            ready_queue_path = root / "validation_ready_queue.csv"
            receipt_register_path = root / "delivery_receipt_register.csv"
            checklist_path = root / "delivery_checklist.csv"
            mapping_stub_path = root / "mapping_stub.json"
            input_csv_path = root / "controller_event_log.csv"

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

            with ready_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "selected_received_file_path",
                        "monitor_status",
                        "validation_command_ready",
                        "validation_output_dir",
                        "validation_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "selected_received_file_path": str(input_csv_path),
                        "monitor_status": "ready_for_validation",
                        "validation_command_ready": "ready",
                        "validation_output_dir": str(root / "validated" / "controller"),
                        "validation_status": "not_started",
                    }
                )

            with receipt_register_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "expected_filename_hint",
                        "incoming_dropzone_path",
                        "mapping_stub_path",
                        "validation_output_dir",
                        "validation_command",
                        "receipt_status",
                        "received_date",
                        "received_file_path",
                        "validation_status",
                        "validation_manifest_path",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "delivery_format": "CSV export",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "valid events",
                        "expected_filename_hint": "controller_event_log_*.csv",
                        "incoming_dropzone_path": str(root / "incoming"),
                        "mapping_stub_path": str(mapping_stub_path),
                        "validation_output_dir": str(root / "validated" / "controller"),
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping.json",
                        "receipt_status": "delivery_detected",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )

            result = run_bari_signal_phase_validation_batch(
                output_dir=output_dir,
                validation_ready_queue_path=ready_queue_path,
                delivery_receipt_register_path=receipt_register_path,
                delivery_checklist_path=checklist_path,
                preview_limit=5,
            )

            self.assertEqual(result["stats"]["ready_queue_count"], 1)
            self.assertEqual(result["stats"]["executed_validation_count"], 1)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 1)
            self.assertEqual(result["stats"]["skipped_count"], 0)

            payload = json.loads((output_dir / "signal_phase_validation_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["validation_results"]), 1)
            self.assertEqual(payload["validation_results"][0]["validation_outcome"], "accepted_for_ingestion")

            with (output_dir / "validation_batch_results.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["validation_outcome"], "accepted_for_ingestion")

    def test_run_bari_signal_phase_validation_batch_with_support_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "validation_batch"
            ready_queue_path = root / "validation_ready_queue.csv"
            receipt_register_path = root / "delivery_receipt_register.csv"
            checklist_path = root / "delivery_checklist.csv"
            mapping_stub_path = root / "mapping_stub.json"
            input_file_path = root / "junction_phase_diagram_support.pdf"

            input_file_path.write_text("%PDF-1.4\nsupport sample\n", encoding="utf-8")
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
                        "delivery_format": "PDF export",
                        "requested_window": "current_layout",
                        "acceptance_gate": "diagram identifies stages",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "support",
                    }
                )

            with ready_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "selected_received_file_path",
                        "monitor_status",
                        "validation_command_ready",
                        "validation_output_dir",
                        "validation_status",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "junction_phase_diagram_support",
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "selected_received_file_path": str(input_file_path),
                        "monitor_status": "ready_for_validation",
                        "validation_command_ready": "ready",
                        "validation_output_dir": str(root / "validated" / "support"),
                        "validation_status": "not_started",
                    }
                )

            with receipt_register_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "expected_filename_hint",
                        "incoming_dropzone_path",
                        "mapping_stub_path",
                        "validation_output_dir",
                        "validation_command",
                        "receipt_status",
                        "received_date",
                        "received_file_path",
                        "validation_status",
                        "validation_manifest_path",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "junction_phase_diagram_support",
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "delivery_format": "PDF export",
                        "requested_window": "current_layout",
                        "acceptance_gate": "diagram identifies stages",
                        "expected_filename_hint": "junction_phase_diagram_*",
                        "incoming_dropzone_path": str(root / "incoming"),
                        "mapping_stub_path": str(mapping_stub_path),
                        "validation_output_dir": str(root / "validated" / "support"),
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping.json",
                        "receipt_status": "delivery_detected",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )

            result = run_bari_signal_phase_validation_batch(
                output_dir=output_dir,
                validation_ready_queue_path=ready_queue_path,
                delivery_receipt_register_path=receipt_register_path,
                delivery_checklist_path=checklist_path,
                preview_limit=5,
            )

            self.assertEqual(result["stats"]["ready_queue_count"], 1)
            self.assertEqual(result["stats"]["executed_validation_count"], 1)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 0)
            self.assertEqual(result["stats"]["accepted_support_artifact_count"], 1)

            payload = json.loads((output_dir / "signal_phase_validation_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["validation_results"][0]["validation_outcome"], "accepted_support_artifact")


if __name__ == "__main__":
    unittest.main()
