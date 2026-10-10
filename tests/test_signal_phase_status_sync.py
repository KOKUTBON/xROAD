from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_status_sync import build_bari_signal_phase_status_sync_bundle


class SignalPhaseStatusSyncBundleTests(unittest.TestCase):
    def test_build_bari_signal_phase_status_sync_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "status_sync"
            receipt_register_path = root / "delivery_receipt_register.csv"
            monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            checklist_path = root / "delivery_checklist.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"
            session_manifest_path = root / "signal_phase_delivery_session.manifest.json"
            session_json_path = root / "signal_phase_delivery_session.json"
            accepted_manifest_path = root / "accepted_validation.manifest.json"

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
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "expected_filename_hint": "controller_event_log_*.csv",
                        "incoming_dropzone_path": "incoming/controller",
                        "mapping_stub_path": "mapping.json",
                        "validation_output_dir": "validation/controller",
                        "validation_command": "validate",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "junction_phase_diagram_support",
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "delivery_format": "PDF",
                        "requested_window": "current_layout",
                        "acceptance_gate": "support diagram present",
                        "expected_filename_hint": "junction_phase_diagram_*",
                        "incoming_dropzone_path": "incoming/support",
                        "mapping_stub_path": "support_mapping.json",
                        "validation_output_dir": "validation/support",
                        "validation_command": "validate",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "arm_phase_mapping_sheet",
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "delivery_format": "CSV",
                        "requested_window": "current_layout",
                        "acceptance_gate": "mapping complete",
                        "expected_filename_hint": "arm_phase_mapping_*.csv",
                        "incoming_dropzone_path": "incoming/mapping",
                        "mapping_stub_path": "mapping_sheet.json",
                        "validation_output_dir": "validation/mapping",
                        "validation_command": "validate",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )

            with monitor_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "incoming_dropzone_path",
                        "detected_file_count",
                        "detected_file_paths",
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
                        "incoming_dropzone_path": "incoming/controller",
                        "detected_file_count": "1",
                        "detected_file_paths": "controller.csv",
                        "selected_received_file_path": "controller.csv",
                        "monitor_status": "ready_for_validation",
                        "validation_command_ready": "validate",
                        "validation_output_dir": "validation/controller",
                        "validation_status": "accepted_for_ingestion",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "arm_phase_mapping_sheet",
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "incoming_dropzone_path": "incoming/mapping",
                        "detected_file_count": "2",
                        "detected_file_paths": "a.csv | b.csv",
                        "selected_received_file_path": "",
                        "monitor_status": "multiple_files_manual_review",
                        "validation_command_ready": "",
                        "validation_output_dir": "validation/mapping",
                        "validation_status": "not_started",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "junction_phase_diagram_support",
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "incoming_dropzone_path": "incoming/support",
                        "detected_file_count": "1",
                        "detected_file_paths": "support.pdf",
                        "selected_received_file_path": "support.pdf",
                        "monitor_status": "ready_for_validation",
                        "validation_command_ready": "validate",
                        "validation_output_dir": "validation/support",
                        "validation_status": "accepted_support_artifact",
                    }
                )

            with validation_batch_results_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "delivery_item_id",
                        "request_id",
                        "junction_id",
                        "profile_id",
                        "validation_outcome",
                        "manifest_path",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "profile_id": "controller_event_log_export",
                        "validation_outcome": "accepted_for_ingestion",
                        "manifest_path": str(accepted_manifest_path),
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "profile_id": "junction_phase_diagram_support",
                        "validation_outcome": "accepted_support_artifact",
                        "manifest_path": "support_validation.manifest.json",
                    }
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
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "arm_phase_mapping_sheet",
                        "owner_team": "traffic control center",
                        "delivery_format": "CSV export",
                        "requested_window": "current_layout",
                        "acceptance_gate": "mapping complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
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
                        "acceptance_gate": "support diagram present",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )

            accepted_manifest_path.write_text("{}", encoding="utf-8")
            session_json_path.write_text(
                json.dumps(
                    {
                        "accepted_deliveries": [
                            {"validation_manifest_path": str(accepted_manifest_path)}
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            session_manifest_path.write_text(
                json.dumps(
                    {"outputs": {"session_json_path": str(session_json_path)}},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            receive_cycle_path.write_text(
                json.dumps(
                    {"outputs": {"delivery_session_manifest_path": str(session_manifest_path)}},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_status_sync_bundle(
                output_dir=output_dir,
                delivery_receipt_register_path=receipt_register_path,
                delivery_monitor_queue_path=monitor_queue_path,
                validation_batch_results_path=validation_batch_results_path,
                delivery_checklist_path=checklist_path,
                receive_cycle_path=receive_cycle_path,
            )

            self.assertEqual(result["stats"]["receipt_row_count"], 3)
            self.assertEqual(result["stats"]["checklist_row_count"], 3)
            self.assertEqual(result["stats"]["detected_delivery_count"], 3)
            self.assertEqual(result["stats"]["manual_review_count"], 1)
            self.assertEqual(result["stats"]["validated_count"], 2)
            self.assertEqual(result["stats"]["validated_support_artifact_count"], 1)
            self.assertEqual(result["stats"]["mapped_count"], 1)

            with (output_dir / "delivery_receipt_register_synced.csv").open(encoding="utf-8", newline="") as handle:
                synced_receipts = {row["delivery_item_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(
                synced_receipts["bari_signal_phase_01__controller_event_log_export"]["receipt_status"],
                "delivery_detected",
            )
            self.assertEqual(
                synced_receipts["bari_signal_phase_01__controller_event_log_export"]["validation_status"],
                "accepted_for_ingestion",
            )
            self.assertEqual(
                synced_receipts["bari_signal_phase_01__controller_event_log_export"]["synced_applied_to_movement_layer"],
                "yes",
            )
            self.assertEqual(
                synced_receipts["bari_signal_phase_01__arm_phase_mapping_sheet"]["receipt_status"],
                "multiple_files_manual_review",
            )
            self.assertEqual(
                synced_receipts["bari_signal_phase_01__junction_phase_diagram_support"]["validation_status"],
                "accepted_support_artifact",
            )

            with (output_dir / "delivery_checklist_synced.csv").open(encoding="utf-8", newline="") as handle:
                synced_checklist = {row["delivery_item_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(
                synced_checklist["bari_signal_phase_01__controller_event_log_export"]["delivery_status"],
                "mapped_to_movements",
            )
            self.assertEqual(
                synced_checklist["bari_signal_phase_01__arm_phase_mapping_sheet"]["delivery_status"],
                "manual_delivery_review",
            )
            self.assertEqual(
                synced_checklist["bari_signal_phase_01__junction_phase_diagram_support"]["delivery_status"],
                "validated_support_artifact",
            )


if __name__ == "__main__":
    unittest.main()
