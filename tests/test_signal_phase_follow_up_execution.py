from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_follow_up_execution import (
    build_bari_signal_phase_follow_up_execution_bundle,
)


class SignalPhaseFollowUpExecutionBundleTests(unittest.TestCase):
    def test_build_bari_signal_phase_follow_up_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "follow_up_execution"
            follow_up_ready_queue_path = root / "follow_up_ready_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"

            with follow_up_ready_queue_path.open("w", encoding="utf-8", newline="") as handle:
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
                        "detected_delivery_item_count",
                        "manual_review_item_count",
                        "validated_delivery_item_count",
                        "mapped_delivery_item_count",
                        "stage_delivery_item_count",
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
                        "follow_up_packet_md_path",
                        "follow_up_packet_json_path",
                        "suggested_message",
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
                        "due_now": "False",
                        "open_delivery_item_count": "3",
                        "detected_delivery_item_count": "0",
                        "manual_review_item_count": "0",
                        "validated_delivery_item_count": "0",
                        "mapped_delivery_item_count": "0",
                        "stage_delivery_item_count": "1",
                        "open_profile_ids": "controller_event_log_export | arm_phase_mapping_sheet",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "confirm receipt",
                        "primary_channel_value": "urbanistica@example.com",
                        "secondary_channel_value": "archivio@example.com",
                        "phone_escalation_value": "+39 080 577 1111",
                        "email_subject": "subject",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59",
                        "fallback_pilot_scope": "8 weeks",
                        "follow_up_packet_md_path": "packet.md",
                        "follow_up_packet_json_path": "packet.json",
                        "suggested_message": "follow up now",
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
                        "request_follow_up_status": "validated_pending_application",
                        "next_follow_up_stage": "escalation",
                        "due_date": "2026-04-12",
                        "due_now": "True",
                        "open_delivery_item_count": "1",
                        "detected_delivery_item_count": "1",
                        "manual_review_item_count": "0",
                        "validated_delivery_item_count": "1",
                        "mapped_delivery_item_count": "0",
                        "stage_delivery_item_count": "1",
                        "open_profile_ids": "controller_event_log_export",
                        "recommended_channel": "archivio@example.com",
                        "recommended_action": "escalate",
                        "primary_channel_value": "urbanistica@example.com",
                        "secondary_channel_value": "archivio@example.com",
                        "phone_escalation_value": "+39 080 577 1111",
                        "email_subject": "subject 2",
                        "recommended_time_window": "weekday evening",
                        "preferred_focus_hour_ranges": "17:00-18:59",
                        "fallback_pilot_scope": "6 weeks",
                        "follow_up_packet_md_path": "packet2.md",
                        "follow_up_packet_json_path": "packet2.json",
                        "suggested_message": "hold internal",
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
                        "follow_up_stage": "escalation",
                        "due_date": "2026-04-12",
                        "recommended_channel": "archivio@example.com",
                        "recommended_action": "escalate",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
                    }
                )

            result = build_bari_signal_phase_follow_up_execution_bundle(
                output_dir=output_dir,
                follow_up_ready_queue_path=follow_up_ready_queue_path,
                follow_up_tracker_path=follow_up_tracker_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["execution_ready_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["due_now_count"], 0)
            self.assertEqual(result["stats"]["tracker_update_count"], 1)

            with (output_dir / "follow_up_execution_queue.csv").open(encoding="utf-8", newline="") as handle:
                execution_rows = list(csv.DictReader(handle))
            self.assertEqual(len(execution_rows), 1)
            self.assertEqual(execution_rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(execution_rows[0]["execution_status"], "pending_execution")

            with (output_dir / "internal_hold_queue.csv").open(encoding="utf-8", newline="") as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(hold_rows), 1)
            self.assertEqual(hold_rows[0]["request_id"], "bari_signal_phase_02")

            packet_json = Path(execution_rows[0]["execution_packet_json_path"])
            packet_payload = json.loads(packet_json.read_text(encoding="utf-8"))
            self.assertEqual(packet_payload["request_id"], "bari_signal_phase_01")
            self.assertEqual(packet_payload["execution_status"], "pending_execution")


if __name__ == "__main__":
    unittest.main()
