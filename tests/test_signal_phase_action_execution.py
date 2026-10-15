from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_action_execution import (
    build_bari_signal_phase_action_execution_bundle,
)


class SignalPhaseActionExecutionTest(unittest.TestCase):
    def test_build_bari_signal_phase_action_execution_bundle_splits_ready_and_hold_rows(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "action_execution"
            action_queue_path = root / "action_queue.csv"
            packet_dir = root / "packets"
            packet_dir.mkdir(parents=True, exist_ok=True)

            for packet_name in ("dispatch_01", "follow_up_02", "repair_03"):
                (packet_dir / f"{packet_name}.md").write_text("# packet\n", encoding="utf-8")
                (packet_dir / f"{packet_name}.json").write_text("{}", encoding="utf-8")

            with action_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
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
                        "dispatch_validation_outcome",
                        "dispatch_validation_issue_codes",
                        "repair_status_category",
                        "repair_status",
                        "repair_next_action",
                        "repair_writeback_eligible",
                        "packet_md_path",
                        "primary_channel_value",
                        "secondary_channel_value",
                        "phone_escalation_value",
                        "recommended_action",
                        "action_summary",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "dispatch_reference": "dispatch-01",
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "it-bari-signal-93",
                            "signal_name": "Signal 93",
                            "priority_rank": "1",
                            "priority_band": "tier_1_immediate",
                            "action_category": "dispatch_request_now",
                            "source_stage": "dispatch",
                            "due_date": "2026-03-29",
                            "due_now": "True",
                            "packet_md_path": str(packet_dir / "dispatch_01.md"),
                            "primary_channel_value": "planning@pec.example.test",
                            "secondary_channel_value": "archives@pec.example.test",
                            "recommended_action": "Send the initial request.",
                            "action_summary": "Send the first PEC request.",
                        },
                        {
                            "dispatch_reference": "dispatch-02",
                            "request_id": "bari_signal_phase_02",
                            "junction_id": "it-bari-signal-94",
                            "signal_name": "Signal 94",
                            "priority_rank": "2",
                            "priority_band": "tier_1_immediate",
                            "action_category": "execute_follow_up_now",
                            "source_stage": "follow_up",
                            "due_date": "2026-04-05",
                            "due_now": "True",
                            "packet_md_path": str(packet_dir / "follow_up_02.md"),
                            "recommended_action": "Send the first follow-up.",
                            "action_summary": "Execute the prepared follow-up packet.",
                        },
                        {
                            "dispatch_reference": "dispatch-03",
                            "request_id": "bari_signal_phase_03",
                            "junction_id": "it-bari-signal-84",
                            "signal_name": "Signal 84",
                            "priority_rank": "3",
                            "priority_band": "tier_1_immediate",
                            "action_category": "repair_dispatch_log_again",
                            "source_stage": "dispatch_repair_status",
                            "due_date": "2026-03-29",
                            "due_now": "True",
                            "packet_md_path": str(packet_dir / "repair_03.md"),
                            "dispatch_validation_issue_codes": "missing_protocol_or_evidence",
                            "recommended_action": "Repair the log.",
                            "action_summary": "Repair the send log before writeback.",
                        },
                        {
                            "dispatch_reference": "dispatch-04",
                            "request_id": "bari_signal_phase_04",
                            "junction_id": "it-bari-signal-67",
                            "signal_name": "Signal 67",
                            "priority_rank": "4",
                            "priority_band": "tier_1_immediate",
                            "action_category": "rerun_dispatch_validation",
                            "source_stage": "dispatch_repair_status",
                            "due_date": "2026-03-29",
                            "due_now": "True",
                            "recommended_action": "Rerun validation.",
                            "action_summary": "The repaired row is staged and waiting for validation.",
                        },
                        {
                            "dispatch_reference": "dispatch-05",
                            "request_id": "bari_signal_phase_05",
                            "junction_id": "it-bari-signal-57",
                            "signal_name": "Signal 57",
                            "priority_rank": "5",
                            "priority_band": "tier_1_immediate",
                            "action_category": "scheduled_follow_up",
                            "source_stage": "follow_up",
                            "due_date": "2026-04-05",
                            "due_now": "False",
                            "recommended_action": "Prepare the follow-up.",
                            "action_summary": "Prepare the reminder for next week.",
                        },
                        {
                            "dispatch_reference": "dispatch-06",
                            "request_id": "bari_signal_phase_06",
                            "junction_id": "it-bari-signal-27",
                            "signal_name": "Signal 27",
                            "priority_rank": "6",
                            "priority_band": "tier_1_immediate",
                            "action_category": "await_dispatch_writeback",
                            "source_stage": "dispatch_repair_status",
                            "due_now": "False",
                            "recommended_action": "Wait for writeback.",
                            "action_summary": "The cleared row should move through writeback.",
                        },
                        {
                            "dispatch_reference": "dispatch-07",
                            "request_id": "bari_signal_phase_07",
                            "junction_id": "it-bari-signal-11",
                            "signal_name": "Signal 11",
                            "priority_rank": "7",
                            "priority_band": "tier_2_next_wave",
                            "action_category": "completed",
                            "source_stage": "completed",
                            "due_now": "False",
                            "recommended_action": "No action.",
                            "action_summary": "Already applied.",
                        },
                        {
                            "dispatch_reference": "dispatch-08",
                            "request_id": "bari_signal_phase_08",
                            "junction_id": "it-bari-signal-12",
                            "signal_name": "Signal 12",
                            "priority_rank": "8",
                            "priority_band": "tier_2_next_wave",
                            "action_category": "manual_delivery_review",
                            "source_stage": "delivery_review",
                            "due_now": "True",
                            "recommended_action": "Inspect the delivery folder.",
                            "action_summary": "Manual file review is required.",
                        },
                        {
                            "dispatch_reference": "dispatch-09",
                            "request_id": "bari_signal_phase_09",
                            "junction_id": "it-bari-signal-13",
                            "signal_name": "Signal 13",
                            "priority_rank": "9",
                            "priority_band": "tier_2_next_wave",
                            "action_category": "request_provider_fix",
                            "source_stage": "provider_fix",
                            "due_now": "True",
                            "recommended_action": "Ask for a corrected extract.",
                            "action_summary": "Provider fix is required.",
                        },
                    ]
                )

            result = build_bari_signal_phase_action_execution_bundle(
                output_dir=output_dir,
                signal_phase_action_queue_path=action_queue_path,
            )

            self.assertEqual(result["stats"]["request_count"], 9)
            self.assertEqual(result["stats"]["execution_ready_count"], 6)
            self.assertEqual(result["stats"]["internal_hold_count"], 3)
            self.assertEqual(result["stats"]["dispatch_send_count"], 1)
            self.assertEqual(result["stats"]["follow_up_send_count"], 1)
            self.assertEqual(result["stats"]["repair_action_count"], 1)
            self.assertEqual(result["stats"]["validation_rerun_count"], 1)
            self.assertEqual(result["stats"]["manual_review_count"], 1)
            self.assertEqual(result["stats"]["provider_fix_count"], 1)
            self.assertEqual(result["stats"]["waiting_count"], 2)
            self.assertEqual(result["stats"]["completed_count"], 1)

            with (output_dir / "action_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(ready_rows[0]["execution_route"], "dispatch_send")
            self.assertEqual(ready_rows[0]["packet_available"], "yes")
            self.assertTrue(ready_rows[0]["packet_json_path"].endswith("dispatch_01.json"))
            validation_row = next(
                row for row in ready_rows if row["action_category"] == "rerun_dispatch_validation"
            )
            self.assertEqual(
                validation_row["operator_command"], "make run-bari-signal-phase-runtime-cycle"
            )

            with (output_dir / "action_internal_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            hold_by_action = {row["action_category"]: row for row in hold_rows}
            self.assertIn("await_dispatch_writeback", hold_by_action)
            self.assertIn("writeback", hold_by_action["await_dispatch_writeback"]["hold_reason"])

    def test_build_bari_signal_phase_action_execution_bundle_promotes_due_scheduled_follow_up(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "action_execution"
            action_queue_path = root / "action_queue.csv"
            packet_md_path = root / "scheduled_follow_up.md"
            packet_json_path = root / "scheduled_follow_up.json"
            packet_md_path.write_text("# packet\n", encoding="utf-8")
            packet_json_path.write_text("{}", encoding="utf-8")

            with action_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "action_category",
                        "source_stage",
                        "due_date",
                        "due_now",
                        "packet_md_path",
                        "recommended_action",
                        "action_summary",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_10",
                        "junction_id": "it-bari-signal-15",
                        "signal_name": "Signal 15",
                        "priority_rank": "1",
                        "priority_band": "tier_1_immediate",
                        "action_category": "scheduled_follow_up",
                        "source_stage": "follow_up",
                        "due_date": "2026-04-05",
                        "due_now": "True",
                        "packet_md_path": str(packet_md_path),
                        "recommended_action": "Send the scheduled follow-up.",
                        "action_summary": "This scheduled follow-up is now due.",
                    }
                )

            result = build_bari_signal_phase_action_execution_bundle(
                output_dir=output_dir,
                signal_phase_action_queue_path=action_queue_path,
            )

            self.assertEqual(result["stats"]["execution_ready_count"], 1)
            self.assertEqual(result["stats"]["follow_up_send_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 0)

            with (output_dir / "action_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["execution_route"], "follow_up_send")
            self.assertEqual(rows[0]["packet_available"], "yes")


if __name__ == "__main__":
    unittest.main()
