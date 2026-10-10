from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_action_queue import build_bari_signal_phase_action_queue


class SignalPhaseActionQueueTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_action_queue_prioritizes_dispatch_then_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "action_queue"
            operations_cycle_path = root / "signal_phase_operations_cycle.json"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            lifecycle_items_path = root / "lifecycle_items.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_repair_status_path = root / "dispatch_repair_status.csv"
            dispatch_packet_dir = root / "dispatch_packets"

            operations_cycle_path.write_text("{}", encoding="utf-8")
            dispatch_packet_dir.mkdir(parents=True, exist_ok=True)
            (dispatch_packet_dir / "req_1.md").write_text("dispatch packet", encoding="utf-8")
            dispatch_bundle_path.write_text("{}", encoding="utf-8")

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
                    "response_status",
                    "primary_channel_value",
                    "secondary_channel_value",
                    "phone_escalation_value",
                    "recommended_routing_action",
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
                        "response_status": "awaiting_send",
                        "primary_channel_value": "a@example.com",
                        "secondary_channel_value": "b@example.com",
                        "phone_escalation_value": "+39 1",
                        "recommended_routing_action": "Send now.",
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
                        "response_status": "awaiting_delivery",
                        "primary_channel_value": "a@example.com",
                        "secondary_channel_value": "b@example.com",
                        "phone_escalation_value": "+39 2",
                        "recommended_routing_action": "Sent already.",
                    },
                ],
            )

            self._write_csv(
                lifecycle_items_path,
                [
                    "request_id",
                    "delivery_item_id",
                    "lifecycle_status",
                ],
                [
                    {
                        "request_id": "req_1",
                        "delivery_item_id": "req_1__item",
                        "lifecycle_status": "awaiting_delivery",
                    },
                    {
                        "request_id": "req_2",
                        "delivery_item_id": "req_2__item",
                        "lifecycle_status": "awaiting_delivery",
                    },
                ],
            )

            self._write_csv(
                follow_up_execution_queue_path,
                [
                    "request_id",
                    "next_follow_up_stage",
                    "due_date",
                    "due_now",
                    "recommended_action",
                    "execution_packet_md_path",
                ],
                [
                    {
                        "request_id": "req_1",
                        "next_follow_up_stage": "first_follow_up",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "recommended_action": "Call now.",
                        "execution_packet_md_path": "packets/req_1.md",
                    },
                    {
                        "request_id": "req_2",
                        "next_follow_up_stage": "first_follow_up",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "recommended_action": "Call now.",
                        "execution_packet_md_path": "packets/req_2.md",
                    },
                ],
            )

            self._write_csv(
                dispatch_log_repair_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "action_category",
                    "dispatch_validation_outcome",
                    "dispatch_validation_issue_count",
                    "dispatch_validation_issue_codes",
                    "repair_summary",
                    "repair_packet_md_path",
                    "repair_packet_json_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "action_category": "repair_dispatch_log_now",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_count": 2,
                        "dispatch_validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "repair_summary": "Repair the dispatch log entry.",
                        "repair_packet_md_path": "repair/req_1.md",
                        "repair_packet_json_path": "repair/req_1.json",
                    }
                ],
            )
            self._write_csv(
                dispatch_repair_status_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "repair_status_category",
                    "repair_status",
                    "validation_outcome",
                    "validation_issue_codes",
                    "writeback_eligible",
                    "repair_applied",
                    "execution_queue_state",
                    "due_now",
                    "next_action",
                    "action_summary",
                    "repair_packet_md_path",
                    "repair_packet_json_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "repair_status_category": "ready_for_validation",
                        "repair_status": "ready_for_validation",
                        "validation_outcome": "not_revalidated",
                        "validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "writeback_eligible": "no",
                        "repair_applied": "yes",
                        "execution_queue_state": "internal_hold",
                        "due_now": "yes",
                        "next_action": "rerun_validation_or_runtime_cycle",
                        "action_summary": "The repaired dispatch row is staged and waiting for validation.",
                        "repair_packet_md_path": "repair/req_1_status.md",
                        "repair_packet_json_path": "repair/req_1_status.json",
                    }
                ],
            )

            result = build_bari_signal_phase_action_queue(
                output_dir=output_dir,
                signal_phase_operations_cycle_path=operations_cycle_path,
                dispatch_execution_queue_path=dispatch_queue_path,
                signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                lifecycle_items_path=lifecycle_items_path,
                follow_up_execution_queue_path=follow_up_execution_queue_path,
                dispatch_log_repair_queue_path=dispatch_log_repair_queue_path,
                dispatch_repair_status_path=dispatch_repair_status_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["dispatch_action_count"], 0)
            self.assertEqual(result["stats"]["dispatch_log_fix_action_count"], 1)
            self.assertEqual(result["stats"]["follow_up_action_count"], 1)
            self.assertEqual(result["stats"]["immediate_action_count"], 2)

            with (output_dir / "action_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["request_id"], "req_1")
            self.assertEqual(rows[0]["action_category"], "rerun_dispatch_validation")
            self.assertEqual(rows[0]["repair_status_category"], "ready_for_validation")
            self.assertEqual(rows[0]["packet_md_path"], "repair/req_1_status.md")
            self.assertEqual(rows[1]["request_id"], "req_2")
            self.assertEqual(rows[1]["action_category"], "execute_follow_up_now")

    def test_build_bari_signal_phase_action_queue_suppresses_dispatch_for_cleared_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "action_queue"
            operations_cycle_path = root / "signal_phase_operations_cycle.json"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            lifecycle_items_path = root / "lifecycle_items.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            dispatch_repair_status_path = root / "dispatch_repair_status.csv"
            dispatch_packet_dir = root / "dispatch_packets"

            operations_cycle_path.write_text("{}", encoding="utf-8")
            dispatch_packet_dir.mkdir(parents=True, exist_ok=True)
            (dispatch_packet_dir / "req_1.md").write_text("dispatch packet", encoding="utf-8")
            dispatch_bundle_path.write_text("{}", encoding="utf-8")

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
                    "response_status",
                    "primary_channel_value",
                    "secondary_channel_value",
                    "phone_escalation_value",
                    "recommended_routing_action",
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
                        "response_status": "awaiting_send",
                        "primary_channel_value": "a@example.com",
                        "secondary_channel_value": "b@example.com",
                        "phone_escalation_value": "+39 1",
                        "recommended_routing_action": "Send now.",
                    }
                ],
            )
            self._write_csv(
                lifecycle_items_path,
                ["request_id", "delivery_item_id", "lifecycle_status"],
                [
                    {
                        "request_id": "req_1",
                        "delivery_item_id": "req_1__item",
                        "lifecycle_status": "awaiting_delivery",
                    }
                ],
            )
            self._write_csv(
                follow_up_execution_queue_path,
                [
                    "request_id",
                    "next_follow_up_stage",
                    "due_date",
                    "due_now",
                    "recommended_action",
                    "execution_packet_md_path",
                ],
                [],
            )
            self._write_csv(
                dispatch_repair_status_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "repair_status_category",
                    "repair_status",
                    "validation_outcome",
                    "validation_issue_codes",
                    "writeback_eligible",
                    "repair_applied",
                    "execution_queue_state",
                    "due_now",
                    "next_action",
                    "action_summary",
                    "repair_packet_md_path",
                    "repair_packet_json_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "repair_status_category": "repair_cleared_for_writeback",
                        "repair_status": "ready_for_validation",
                        "validation_outcome": "accepted_for_writeback",
                        "validation_issue_codes": "",
                        "writeback_eligible": "yes",
                        "repair_applied": "yes",
                        "execution_queue_state": "internal_hold",
                        "due_now": "no",
                        "next_action": "wait_for_writeback_refresh",
                        "action_summary": "The repaired dispatch row has already cleared validation and should no longer be re-dispatched.",
                        "repair_packet_md_path": "repair/req_1_status.md",
                        "repair_packet_json_path": "repair/req_1_status.json",
                    }
                ],
            )

            result = build_bari_signal_phase_action_queue(
                output_dir=output_dir,
                signal_phase_operations_cycle_path=operations_cycle_path,
                dispatch_execution_queue_path=dispatch_queue_path,
                signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                lifecycle_items_path=lifecycle_items_path,
                follow_up_execution_queue_path=follow_up_execution_queue_path,
                dispatch_repair_status_path=dispatch_repair_status_path,
            )

            self.assertEqual(result["stats"]["dispatch_action_count"], 0)
            self.assertEqual(result["stats"]["scheduled_action_count"], 1)

            with (output_dir / "action_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["action_category"], "await_dispatch_writeback")
            self.assertEqual(rows[0]["repair_status_category"], "repair_cleared_for_writeback")
            self.assertEqual(rows[0]["due_now"], "False")


if __name__ == "__main__":
    unittest.main()
