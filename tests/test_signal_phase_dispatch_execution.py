from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_execution import (
    build_bari_signal_phase_dispatch_execution_bundle,
)


class SignalPhaseDispatchExecutionTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_execution"
            action_queue_path = root / "action_queue.csv"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            dispatch_packet_dir = root / "dispatch_packets"
            dispatch_packet_dir.mkdir(parents=True, exist_ok=True)
            (dispatch_packet_dir / "req_1.md").write_text("dispatch packet", encoding="utf-8")
            (dispatch_packet_dir / "req_1.json").write_text("{}", encoding="utf-8")

            self._write_csv(
                action_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "priority_rank",
                    "priority_band",
                    "action_category",
                    "source_stage",
                    "due_date",
                    "due_now",
                    "dispatch_status",
                    "response_status",
                    "lifecycle_statuses",
                    "open_delivery_item_count",
                    "delivery_item_ids",
                    "packet_md_path",
                    "primary_channel_value",
                    "secondary_channel_value",
                    "phone_escalation_value",
                    "recommended_action",
                    "action_summary",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "action_category": "dispatch_request_now",
                        "source_stage": "dispatch",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "dispatch_status": "pending_dispatch",
                        "response_status": "awaiting_send",
                        "lifecycle_statuses": "awaiting_delivery",
                        "open_delivery_item_count": 3,
                        "delivery_item_ids": "req_1__a | req_1__b",
                        "packet_md_path": str(dispatch_packet_dir / "req_1.md"),
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_value": "secondary@example.com",
                        "phone_escalation_value": "+39 1",
                        "recommended_action": "Send now.",
                        "action_summary": "Dispatch now.",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "priority_rank": 2,
                        "priority_band": "tier_1_immediate",
                        "action_category": "await_delivery",
                        "source_stage": "delivery_wait",
                        "due_date": "2026-04-05",
                        "due_now": "False",
                        "dispatch_status": "sent_via_pec",
                        "response_status": "awaiting_delivery",
                        "lifecycle_statuses": "awaiting_delivery",
                        "open_delivery_item_count": 3,
                        "delivery_item_ids": "req_2__a | req_2__b",
                        "packet_md_path": "",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_value": "secondary@example.com",
                        "phone_escalation_value": "+39 2",
                        "recommended_action": "Wait.",
                        "action_summary": "Wait.",
                    },
                ],
            )

            self._write_csv(
                dispatch_queue_path,
                [
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
                    "unresolved_signalized_movement_count",
                    "unresolved_signalized_crash_count",
                    "unresolved_coverage_pct",
                    "unresolved_crash_coverage_pct",
                    "recommended_routing_action",
                    "follow_up_action",
                    "delivery_evidence_path",
                    "response_status",
                    "response_received_date",
                    "notes",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "dispatch_status": "pending_dispatch",
                        "planned_dispatch_date": "2026-03-29",
                        "first_follow_up_date": "2026-04-05",
                        "escalation_date": "2026-04-12",
                        "send_channel_strategy": "primary_pec_with_secondary_pec_cc",
                        "primary_channel_type": "pec_email",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_type": "pec_email",
                        "secondary_channel_value": "secondary@example.com",
                        "general_email_value": "general@example.com",
                        "phone_escalation_type": "phone",
                        "phone_escalation_value": "+39 1",
                        "public_relations_value": "pr@example.com",
                        "contact_name": "",
                        "contact_email": "",
                        "email_subject": "Subject",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59",
                        "fallback_pilot_scope": "8 weeks",
                        "unresolved_signalized_movement_count": 6,
                        "unresolved_signalized_crash_count": 13,
                        "unresolved_coverage_pct": 30.0,
                        "unresolved_crash_coverage_pct": 65.0,
                        "recommended_routing_action": "Send now.",
                        "follow_up_action": "Follow up later.",
                        "delivery_evidence_path": "",
                        "response_status": "awaiting_send",
                        "response_received_date": "",
                        "notes": "",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "priority_rank": 2,
                        "priority_band": "tier_1_immediate",
                        "dispatch_status": "sent_via_pec",
                        "planned_dispatch_date": "2026-03-29",
                        "first_follow_up_date": "2026-04-05",
                        "escalation_date": "2026-04-12",
                        "send_channel_strategy": "primary_pec_with_secondary_pec_cc",
                        "primary_channel_type": "pec_email",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_type": "pec_email",
                        "secondary_channel_value": "secondary@example.com",
                        "general_email_value": "general@example.com",
                        "phone_escalation_type": "phone",
                        "phone_escalation_value": "+39 2",
                        "public_relations_value": "pr@example.com",
                        "contact_name": "",
                        "contact_email": "",
                        "email_subject": "Subject Two",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "17:00-18:59",
                        "fallback_pilot_scope": "8 weeks",
                        "unresolved_signalized_movement_count": 0,
                        "unresolved_signalized_crash_count": 0,
                        "unresolved_coverage_pct": 0.0,
                        "unresolved_crash_coverage_pct": 0.0,
                        "recommended_routing_action": "Wait.",
                        "follow_up_action": "Follow up later.",
                        "delivery_evidence_path": "",
                        "response_status": "awaiting_delivery",
                        "response_received_date": "",
                        "notes": "",
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_execution_bundle(
                output_dir=output_dir,
                signal_phase_action_queue_path=action_queue_path,
                dispatch_execution_queue_path=dispatch_queue_path,
                dispatch_packet_dir=dispatch_packet_dir,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["execution_ready_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["tracker_update_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            with (output_dir / "dispatch_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["request_id"], "req_1")
            self.assertEqual(rows[0]["dispatch_packet_md_path"], str(dispatch_packet_dir / "req_1.md"))
            self.assertEqual(rows[0]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(rows[0]["unresolved_signalized_crash_count"], "13")

            with (output_dir / "dispatch_tracker_updates.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                tracker_rows = list(csv.DictReader(handle))
            self.assertEqual(len(tracker_rows), 1)
            self.assertEqual(tracker_rows[0]["target_dispatch_status"], "sent_via_pec")
            self.assertEqual(tracker_rows[0]["unresolved_signalized_movement_count"], "6")

            packet_md = (output_dir / "execution_packets" / "req_1.md").read_text(encoding="utf-8")
            self.assertIn("Unresolved movement burden: `6` movements / `13` crashes", packet_md)


if __name__ == "__main__":
    unittest.main()
