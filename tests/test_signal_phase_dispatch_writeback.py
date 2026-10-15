from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_writeback import (
    build_bari_signal_phase_dispatch_writeback_bundle,
)


class SignalPhaseDispatchWritebackBundleTests(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_writeback"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            execution_ready_queue_path = root / "dispatch_execution_ready_queue.csv"
            tracker_updates_path = root / "dispatch_tracker_updates.csv"

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
                        "recommended_routing_action": "Send now.",
                        "follow_up_action": "Call later.",
                        "delivery_evidence_path": "",
                        "response_status": "awaiting_send",
                        "response_received_date": "",
                        "notes": "",
                    }
                ],
            )

            self._write_csv(
                follow_up_tracker_path,
                [
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
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 1",
                        "recommended_action": "confirm receipt",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
                    },
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "follow_up_stage": "escalation",
                        "due_date": "2026-04-12",
                        "recommended_channel": "secondary@example.com",
                        "recommended_action": "escalate",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
                    },
                ],
            )

            self._write_csv(
                execution_ready_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "priority_rank",
                    "priority_band",
                    "action_category",
                    "due_date",
                    "due_now",
                    "dispatch_status",
                    "response_status",
                    "send_channel_strategy",
                    "primary_channel_type",
                    "primary_channel_value",
                    "secondary_channel_type",
                    "secondary_channel_value",
                    "general_email_value",
                    "phone_escalation_type",
                    "phone_escalation_value",
                    "public_relations_value",
                    "email_subject",
                    "recommended_time_window",
                    "preferred_focus_hour_ranges",
                    "fallback_pilot_scope",
                    "unresolved_signalized_movement_count",
                    "unresolved_signalized_crash_count",
                    "unresolved_coverage_pct",
                    "unresolved_crash_coverage_pct",
                    "recommended_action",
                    "action_summary",
                    "dispatch_packet_md_path",
                    "dispatch_packet_json_path",
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
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "action_category": "dispatch_request_now",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "dispatch_status": "pending_dispatch",
                        "response_status": "awaiting_send",
                        "send_channel_strategy": "primary_pec_with_secondary_pec_cc",
                        "primary_channel_type": "pec_email",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_type": "pec_email",
                        "secondary_channel_value": "secondary@example.com",
                        "general_email_value": "general@example.com",
                        "phone_escalation_type": "phone",
                        "phone_escalation_value": "+39 1",
                        "public_relations_value": "pr@example.com",
                        "email_subject": "Subject",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59",
                        "fallback_pilot_scope": "8 weeks",
                        "unresolved_signalized_movement_count": 6,
                        "unresolved_signalized_crash_count": 13,
                        "unresolved_coverage_pct": 30.0,
                        "unresolved_crash_coverage_pct": 65.0,
                        "recommended_action": "Send now.",
                        "action_summary": "Dispatch now.",
                        "dispatch_packet_md_path": "dispatch.md",
                        "dispatch_packet_json_path": "dispatch.json",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-31T09:15:00+02:00",
                        "execution_channel_used": "urbanistica@pec.example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "yes",
                        "response_summary": "PEC accepted",
                        "protocol_reference": "PG-2026-001",
                        "evidence_path": "evidence/pec_receipt.eml",
                        "execution_notes": "sent",
                        "execution_packet_md_path": "runtime.md",
                        "execution_packet_json_path": "runtime.json",
                    }
                ],
            )

            self._write_csv(
                tracker_updates_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "current_dispatch_status",
                    "target_dispatch_status",
                    "current_response_status",
                    "target_response_status",
                    "execution_status",
                    "execution_completed_at",
                    "execution_channel_used",
                    "protocol_reference",
                    "evidence_path",
                    "response_received",
                    "response_summary",
                    "update_notes",
                    "linked_execution_packet_md_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "current_dispatch_status": "pending_dispatch",
                        "target_dispatch_status": "sent_via_pec",
                        "current_response_status": "awaiting_send",
                        "target_response_status": "awaiting_delivery",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-31T09:15:00+02:00",
                        "execution_channel_used": "urbanistica@pec.example.com",
                        "protocol_reference": "PG-2026-001",
                        "evidence_path": "evidence/pec_receipt.eml",
                        "response_received": "yes",
                        "response_summary": "PEC accepted",
                        "update_notes": "sent",
                        "linked_execution_packet_md_path": "runtime.md",
                    }
                ],
            )

            result = build_bari_signal_phase_dispatch_writeback_bundle(
                output_dir=output_dir,
                dispatch_execution_queue_path=dispatch_queue_path,
                follow_up_tracker_path=follow_up_tracker_path,
                dispatch_execution_ready_queue_path=execution_ready_queue_path,
                dispatch_tracker_updates_path=tracker_updates_path,
            )

            self.assertEqual(result["stats"]["dispatch_row_count"], 1)
            self.assertEqual(result["stats"]["writeback_ready_count"], 1)
            self.assertEqual(result["stats"]["dispatch_rows_updated_count"], 1)
            self.assertEqual(result["stats"]["tracker_rows_retimed_count"], 2)
            self.assertEqual(result["stats"]["response_received_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["writeback_ready_unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["writeback_ready_unresolved_signalized_crash_total"], 13)

            with (output_dir / "dispatch_execution_queue_synced.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                synced_dispatch_rows = list(csv.DictReader(handle))
            self.assertEqual(synced_dispatch_rows[0]["dispatch_status"], "sent_via_pec")
            self.assertEqual(synced_dispatch_rows[0]["response_status"], "response_received_after_dispatch")
            self.assertEqual(synced_dispatch_rows[0]["delivery_evidence_path"], "evidence/pec_receipt.eml")

            with (output_dir / "follow_up_tracker_synced.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                synced_tracker_rows = list(csv.DictReader(handle))
            self.assertEqual(synced_tracker_rows[0]["due_date"], "2026-04-07")
            self.assertEqual(synced_tracker_rows[1]["due_date"], "2026-04-14")

            with (output_dir / "writeback_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(ready_rows[0]["unresolved_signalized_movement_count"], "6")

            bundle_md = (output_dir / "signal_phase_dispatch_writeback_bundle.md").read_text(encoding="utf-8")
            self.assertIn("writeback-ready unresolved signalized crashes: `13`", bundle_md)


if __name__ == "__main__":
    unittest.main()
