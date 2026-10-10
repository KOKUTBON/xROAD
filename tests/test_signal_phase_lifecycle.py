from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_lifecycle import build_bari_signal_phase_lifecycle_report


class SignalPhaseLifecycleReportTests(unittest.TestCase):
    def test_build_bari_signal_phase_lifecycle_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "lifecycle"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            receipt_register_path = root / "delivery_receipt_register.csv"
            monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"
            session_manifest_path = root / "signal_phase_delivery_session.manifest.json"
            session_json_path = root / "signal_phase_delivery_session.json"
            validation_manifest_path = root / "accepted_validation.manifest.json"

            with dispatch_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "dispatch_status",
                        "planned_dispatch_date",
                        "first_follow_up_date",
                        "escalation_date",
                        "send_channel_strategy",
                        "primary_channel_type",
                        "primary_channel_value",
                        "secondary_channel_type",
                        "secondary_channel_value",
                        "general_email_value",
                        "phone_escalation_type",
                        "phone_escalation_value",
                        "public_relations_value",
                        "contact_name",
                        "contact_email",
                        "email_subject",
                        "recommended_time_window",
                        "preferred_focus_hour_ranges",
                        "fallback_pilot_scope",
                        "recommended_routing_action",
                        "follow_up_action",
                        "delivery_evidence_path",
                        "response_status",
                        "response_received_date",
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
                        "priority_rank": "1",
                        "priority_band": "tier_1_immediate",
                        "dispatch_status": "sent",
                        "planned_dispatch_date": "2026-03-29",
                        "first_follow_up_date": "2026-04-05",
                        "escalation_date": "2026-04-12",
                        "send_channel_strategy": "pec",
                        "primary_channel_type": "pec_email",
                        "primary_channel_value": "urbanistica@example.com",
                        "secondary_channel_type": "pec_email",
                        "secondary_channel_value": "archivio@example.com",
                        "general_email_value": "urp@example.com",
                        "phone_escalation_type": "phone",
                        "phone_escalation_value": "+39 080 577 1111",
                        "public_relations_value": "080/5772390",
                        "contact_name": "",
                        "contact_email": "",
                        "email_subject": "subject",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59",
                        "fallback_pilot_scope": "8 weeks",
                        "recommended_routing_action": "send",
                        "follow_up_action": "call",
                        "delivery_evidence_path": "",
                        "response_status": "awaiting_reply",
                        "response_received_date": "",
                        "notes": "",
                    }
                )
            with follow_up_tracker_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "follow_up_stage",
                        "due_date",
                        "recommended_channel",
                        "recommended_action",
                        "completion_status",
                        "completion_date",
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
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
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
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "expected_filename_hint": "controller_event_log_*.csv",
                        "incoming_dropzone_path": "incoming/controller",
                        "mapping_stub_path": "mapping.json",
                        "validation_output_dir": "validation/controller",
                        "validation_command": "validate",
                        "receipt_status": "delivery_detected",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "accepted_for_ingestion",
                        "validation_manifest_path": str(validation_manifest_path),
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
                        "receipt_status": "delivery_detected",
                        "received_date": "",
                        "received_file_path": "support.pdf",
                        "validation_status": "accepted_support_artifact",
                        "validation_manifest_path": "support_validation.manifest.json",
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
                        "validation_command_ready": "validate controller.csv",
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
                        "validation_command_ready": "validate support.pdf",
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
                        "manifest_path": str(validation_manifest_path),
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

            validation_manifest_path.write_text("{}", encoding="utf-8")
            session_json_path.write_text(
                json.dumps(
                    {
                        "accepted_deliveries": [
                            {"validation_manifest_path": str(validation_manifest_path)}
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

            result = build_bari_signal_phase_lifecycle_report(
                output_dir=output_dir,
                dispatch_execution_queue_path=dispatch_queue_path,
                follow_up_tracker_path=follow_up_tracker_path,
                delivery_receipt_register_path=receipt_register_path,
                delivery_monitor_queue_path=monitor_queue_path,
                validation_batch_results_path=validation_batch_results_path,
                receive_cycle_path=receive_cycle_path,
            )

            self.assertEqual(result["stats"]["delivery_item_count"], 3)
            self.assertEqual(result["stats"]["request_count"], 1)
            self.assertEqual(result["stats"]["manual_review_count"], 1)
            self.assertEqual(result["stats"]["applied_count"], 1)
            self.assertEqual(result["stats"]["support_artifact_validated_count"], 1)
            self.assertEqual(result["stats"]["pending_follow_up_count"], 3)

            payload = json.loads((output_dir / "signal_phase_lifecycle_report.json").read_text(encoding="utf-8"))
            rows_by_item = {row["delivery_item_id"]: row for row in payload["lifecycle_items"]}
            self.assertEqual(
                rows_by_item["bari_signal_phase_01__controller_event_log_export"]["lifecycle_status"],
                "applied_to_movement_layer",
            )
            self.assertEqual(
                rows_by_item["bari_signal_phase_01__arm_phase_mapping_sheet"]["lifecycle_status"],
                "manual_review_required",
            )
            self.assertEqual(
                rows_by_item["bari_signal_phase_01__junction_phase_diagram_support"]["lifecycle_status"],
                "support_artifact_validated",
            )


if __name__ == "__main__":
    unittest.main()
