from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_follow_up import build_bari_signal_phase_follow_up_bundle


class SignalPhaseFollowUpBundleTests(unittest.TestCase):
    def test_build_bari_signal_phase_follow_up_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "follow_up"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_agenda_path = root / "follow_up_agenda.csv"
            synced_receipt_path = root / "delivery_receipt_register_synced.csv"

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
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "CAPRUZZI - PETRONI",
                        "priority_rank": "2",
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
                        "email_subject": "subject 2",
                        "recommended_time_window": "weekday evening",
                        "preferred_focus_hour_ranges": "17:00-18:59",
                        "fallback_pilot_scope": "6 weeks",
                        "recommended_routing_action": "send",
                        "follow_up_action": "call",
                        "delivery_evidence_path": "",
                        "response_status": "awaiting_reply",
                        "response_received_date": "",
                        "notes": "",
                    }
                )

            with follow_up_agenda_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "delivery_item_id",
                        "profile_id",
                        "follow_up_stage",
                        "due_date",
                        "recommended_channel",
                        "recommended_action",
                        "lifecycle_status",
                        "due_now",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "profile_id": "controller_event_log_export",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "lifecycle_status": "awaiting_delivery",
                        "due_now": "False",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "profile_id": "arm_phase_mapping_sheet",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "lifecycle_status": "awaiting_delivery",
                        "due_now": "False",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "CAPRUZZI - PETRONI",
                        "delivery_item_id": "bari_signal_phase_02__controller_event_log_export",
                        "profile_id": "controller_event_log_export",
                        "follow_up_stage": "escalation",
                        "due_date": "2026-04-12",
                        "recommended_channel": "archivio@example.com",
                        "recommended_action": "escalate",
                        "lifecycle_status": "awaiting_delivery",
                        "due_now": "True",
                    }
                )

            with synced_receipt_path.open("w", encoding="utf-8", newline="") as handle:
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
                        "synced_applied_to_movement_layer",
                        "synced_detected_file_count",
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
                        "expected_filename_hint": "controller.csv",
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
                        "synced_applied_to_movement_layer": "no",
                        "synced_detected_file_count": "0",
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
                        "requested_window": "layout",
                        "acceptance_gate": "mapping complete",
                        "expected_filename_hint": "mapping.csv",
                        "incoming_dropzone_path": "incoming/mapping",
                        "mapping_stub_path": "mapping_sheet.json",
                        "validation_output_dir": "validation/mapping",
                        "validation_command": "validate",
                        "receipt_status": "multiple_files_manual_review",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                        "synced_applied_to_movement_layer": "no",
                        "synced_detected_file_count": "2",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "CAPRUZZI - PETRONI",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_02__controller_event_log_export",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "expected_filename_hint": "controller.csv",
                        "incoming_dropzone_path": "incoming/controller2",
                        "mapping_stub_path": "mapping2.json",
                        "validation_output_dir": "validation/controller2",
                        "validation_command": "validate",
                        "receipt_status": "delivery_detected",
                        "received_date": "",
                        "received_file_path": "controller.csv",
                        "validation_status": "accepted_for_ingestion",
                        "validation_manifest_path": "accepted.manifest.json",
                        "notes": "",
                        "synced_applied_to_movement_layer": "no",
                        "synced_detected_file_count": "1",
                    }
                )

            result = build_bari_signal_phase_follow_up_bundle(
                output_dir=output_dir,
                dispatch_execution_queue_path=dispatch_queue_path,
                follow_up_agenda_path=follow_up_agenda_path,
                synced_receipt_register_path=synced_receipt_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["due_now_count"], 1)
            self.assertEqual(result["stats"]["first_follow_up_count"], 1)
            self.assertEqual(result["stats"]["escalation_count"], 1)
            self.assertEqual(result["stats"]["manual_review_request_count"], 1)
            self.assertEqual(result["stats"]["validated_pending_application_count"], 1)
            self.assertEqual(result["stats"]["open_delivery_item_count"], 3)

            with (output_dir / "follow_up_ready_queue.csv").open(encoding="utf-8", newline="") as handle:
                queue_rows = {row["request_id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(queue_rows["bari_signal_phase_01"]["request_follow_up_status"], "manual_review_required")
            self.assertEqual(queue_rows["bari_signal_phase_01"]["next_follow_up_stage"], "first_follow_up")
            self.assertEqual(queue_rows["bari_signal_phase_02"]["request_follow_up_status"], "validated_pending_application")
            self.assertEqual(queue_rows["bari_signal_phase_02"]["next_follow_up_stage"], "escalation")
            self.assertEqual(queue_rows["bari_signal_phase_02"]["due_now"], "True")

            packet_json_path = Path(queue_rows["bari_signal_phase_01"]["follow_up_packet_json_path"])
            packet_payload = json.loads(packet_json_path.read_text(encoding="utf-8"))
            self.assertEqual(packet_payload["request_id"], "bari_signal_phase_01")
            self.assertIn("controller_event_log_export", packet_payload["open_profile_ids"])


if __name__ == "__main__":
    unittest.main()
