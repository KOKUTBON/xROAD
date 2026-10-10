from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_follow_up_writeback import (
    build_bari_signal_phase_follow_up_writeback_bundle,
)


class SignalPhaseFollowUpWritebackBundleTests(unittest.TestCase):
    def test_build_bari_signal_phase_follow_up_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "follow_up_writeback"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            execution_queue_path = root / "follow_up_execution_queue.csv"
            tracker_updates_path = root / "follow_up_tracker_updates.csv"

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
                        "email_subject": "subject2",
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
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "CAPRUZZI - PETRONI",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
                    }
                )

            with execution_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "request_follow_up_status",
                        "next_follow_up_stage",
                        "due_date",
                        "due_now",
                        "open_delivery_item_count",
                        "open_profile_ids",
                        "recommended_channel",
                        "recommended_action",
                        "primary_channel_value",
                        "secondary_channel_value",
                        "phone_escalation_value",
                        "email_subject",
                        "recommended_time_window",
                        "preferred_focus_hour_ranges",
                        "fallback_pilot_scope",
                        "execution_status",
                        "execution_completed_at",
                        "execution_channel_used",
                        "execution_outcome",
                        "response_received",
                        "response_summary",
                        "protocol_reference",
                        "evidence_path",
                        "execution_notes",
                        "execution_packet_md_path",
                        "execution_packet_json_path",
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
                        "request_follow_up_status": "awaiting_delivery_follow_up",
                        "next_follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "due_now": "True",
                        "open_delivery_item_count": "3",
                        "open_profile_ids": "controller_event_log_export",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "primary_channel_value": "urbanistica@example.com",
                        "secondary_channel_value": "archivio@example.com",
                        "phone_escalation_value": "+39 080 577 1111",
                        "email_subject": "subject",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59",
                        "fallback_pilot_scope": "8 weeks",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-04-05T09:15:00+02:00",
                        "execution_channel_used": "+39 080 577 1111",
                        "execution_outcome": "receipt_confirmed",
                        "response_received": "yes",
                        "response_summary": "Protocol opened and routed to traffic systems team.",
                        "protocol_reference": "PG-2026-001",
                        "evidence_path": "evidence/call_note.txt",
                        "execution_notes": "confirmed by phone",
                        "execution_packet_md_path": "packet1.md",
                        "execution_packet_json_path": "packet1.json",
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
                        "request_follow_up_status": "awaiting_delivery_follow_up",
                        "next_follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "due_now": "False",
                        "open_delivery_item_count": "3",
                        "open_profile_ids": "controller_event_log_export",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "primary_channel_value": "urbanistica@example.com",
                        "secondary_channel_value": "archivio@example.com",
                        "phone_escalation_value": "+39 080 577 1111",
                        "email_subject": "subject2",
                        "recommended_time_window": "weekday evening",
                        "preferred_focus_hour_ranges": "17:00-18:59",
                        "fallback_pilot_scope": "6 weeks",
                        "execution_status": "pending_execution",
                        "execution_completed_at": "",
                        "execution_channel_used": "",
                        "execution_outcome": "",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "execution_notes": "",
                        "execution_packet_md_path": "packet2.md",
                        "execution_packet_json_path": "packet2.json",
                    }
                )

            with tracker_updates_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "follow_up_stage",
                        "due_date",
                        "current_completion_status",
                        "target_completion_status",
                        "completion_date",
                        "completion_notes",
                        "linked_execution_status",
                        "linked_execution_packet_md_path",
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
                        "current_completion_status": "pending",
                        "target_completion_status": "completed_after_execution",
                        "completion_date": "",
                        "completion_notes": "",
                        "linked_execution_status": "pending_execution",
                        "linked_execution_packet_md_path": "packet1.md",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "CAPRUZZI - PETRONI",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "current_completion_status": "pending",
                        "target_completion_status": "completed_after_execution",
                        "completion_date": "",
                        "completion_notes": "",
                        "linked_execution_status": "pending_execution",
                        "linked_execution_packet_md_path": "packet2.md",
                    }
                )

            result = build_bari_signal_phase_follow_up_writeback_bundle(
                output_dir=output_dir,
                dispatch_execution_queue_path=dispatch_queue_path,
                follow_up_tracker_path=follow_up_tracker_path,
                follow_up_execution_queue_path=execution_queue_path,
                follow_up_tracker_updates_path=tracker_updates_path,
            )

            self.assertEqual(result["stats"]["dispatch_row_count"], 2)
            self.assertEqual(result["stats"]["tracker_row_count"], 2)
            self.assertEqual(result["stats"]["execution_queue_row_count"], 2)
            self.assertEqual(result["stats"]["writeback_ready_count"], 1)
            self.assertEqual(result["stats"]["dispatch_rows_updated_count"], 1)
            self.assertEqual(result["stats"]["tracker_rows_completed_count"], 1)
            self.assertEqual(result["stats"]["response_received_count"], 1)

            with (output_dir / "dispatch_execution_queue_synced.csv").open(encoding="utf-8", newline="") as handle:
                dispatch_rows = {row["request_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(
                dispatch_rows["bari_signal_phase_01"]["response_status"],
                "response_received_after_follow_up",
            )
            self.assertEqual(
                dispatch_rows["bari_signal_phase_01"]["response_received_date"],
                "2026-04-05",
            )
            self.assertEqual(
                dispatch_rows["bari_signal_phase_01"]["delivery_evidence_path"],
                "evidence/call_note.txt",
            )
            self.assertEqual(
                dispatch_rows["bari_signal_phase_02"]["response_status"],
                "awaiting_reply",
            )

            with (output_dir / "follow_up_tracker_synced.csv").open(encoding="utf-8", newline="") as handle:
                tracker_rows = {row["request_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(tracker_rows["bari_signal_phase_01"]["completion_status"], "completed")
            self.assertEqual(tracker_rows["bari_signal_phase_01"]["completion_date"], "2026-04-05")
            self.assertEqual(tracker_rows["bari_signal_phase_02"]["completion_status"], "pending")

            with (output_dir / "writeback_ready_queue.csv").open(encoding="utf-8", newline="") as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 1)
            self.assertEqual(ready_rows[0]["request_id"], "bari_signal_phase_01")


if __name__ == "__main__":
    unittest.main()
