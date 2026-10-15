from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_action_handoff import (
    build_bari_signal_phase_action_handoff_bundle,
)


class SignalPhaseActionHandoffTest(unittest.TestCase):
    def test_build_bari_signal_phase_action_handoff_bundle_routes_ready_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "action_handoff"
            action_execution_bundle_path = root / "signal_phase_action_execution_bundle.json"
            dispatch_execution_log_path = root / "dispatch_execution_log.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"
            delivery_monitor_queue_path = root / "delivery_monitor_queue.csv"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            runtime_cycle_manifest_path = root / "signal_phase_runtime_cycle.manifest.json"

            for path in (
                dispatch_execution_log_path,
                follow_up_execution_queue_path,
                dispatch_log_repair_log_path,
                delivery_monitor_queue_path,
                delivery_receipt_register_path,
                runtime_cycle_manifest_path,
            ):
                path.write_text("{}" if path.suffix == ".json" else "request_id\n", encoding="utf-8")

            action_execution_bundle_path.write_text(
                json.dumps(
                    {
                        "execution_ready_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "action_category": "dispatch_request_now",
                                "execution_route": "dispatch_send",
                                "due_date": "2026-03-29",
                                "due_now": "yes",
                                "packet_md_path": "/tmp/dispatch_01.md",
                                "packet_json_path": "/tmp/dispatch_01.json",
                                "packet_available": "yes",
                                "action_summary": "Send the first PEC request.",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "action_category": "execute_follow_up_now",
                                "execution_route": "follow_up_send",
                                "due_date": "2026-04-05",
                                "due_now": "yes",
                                "packet_available": "yes",
                                "action_summary": "Execute the prepared follow-up packet.",
                            },
                            {
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "priority_rank": 3,
                                "priority_band": "tier_1_immediate",
                                "action_category": "repair_dispatch_log_again",
                                "execution_route": "dispatch_log_repair",
                                "due_now": "yes",
                                "packet_available": "yes",
                                "action_summary": "Repair the send log.",
                            },
                            {
                                "request_id": "bari_signal_phase_04",
                                "junction_id": "it-bari-signal-67",
                                "signal_name": "Signal 67",
                                "priority_rank": 4,
                                "priority_band": "tier_1_immediate",
                                "action_category": "rerun_dispatch_validation",
                                "execution_route": "dispatch_validation_rerun",
                                "due_now": "yes",
                                "operator_command": "make run-bari-signal-phase-runtime-cycle",
                                "action_summary": "Rerun validation.",
                            },
                            {
                                "request_id": "bari_signal_phase_05",
                                "junction_id": "it-bari-signal-57",
                                "signal_name": "Signal 57",
                                "priority_rank": 5,
                                "priority_band": "tier_1_immediate",
                                "action_category": "manual_delivery_review",
                                "execution_route": "delivery_manual_review",
                                "due_now": "yes",
                                "action_summary": "Manual review required.",
                            },
                            {
                                "request_id": "bari_signal_phase_06",
                                "junction_id": "it-bari-signal-27",
                                "signal_name": "Signal 27",
                                "priority_rank": 6,
                                "priority_band": "tier_1_immediate",
                                "action_category": "request_provider_fix",
                                "execution_route": "provider_fix_request",
                                "due_now": "yes",
                                "action_summary": "Provider fix is required.",
                            },
                        ],
                        "internal_hold_queue": [
                            {
                                "request_id": "bari_signal_phase_07",
                                "junction_id": "it-bari-signal-11",
                                "signal_name": "Signal 11",
                                "priority_rank": 7,
                                "priority_band": "tier_2_next_wave",
                                "action_category": "await_delivery",
                                "execution_route": "",
                                "due_now": "no",
                                "hold_reason": "Wait for delivery.",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_action_handoff_bundle(
                output_dir=output_dir,
                signal_phase_action_execution_bundle_path=action_execution_bundle_path,
                dispatch_execution_log_path=dispatch_execution_log_path,
                follow_up_execution_queue_path=follow_up_execution_queue_path,
                dispatch_log_repair_log_path=dispatch_log_repair_log_path,
                delivery_monitor_queue_path=delivery_monitor_queue_path,
                delivery_receipt_register_path=delivery_receipt_register_path,
                runtime_cycle_manifest_path=runtime_cycle_manifest_path,
            )

            self.assertEqual(result["stats"]["request_count"], 7)
            self.assertEqual(result["stats"]["handoff_ready_count"], 6)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["dispatch_recording_count"], 1)
            self.assertEqual(result["stats"]["follow_up_recording_count"], 1)
            self.assertEqual(result["stats"]["repair_log_count"], 1)
            self.assertEqual(result["stats"]["runtime_command_count"], 1)
            self.assertEqual(result["stats"]["delivery_review_count"], 1)
            self.assertEqual(result["stats"]["provider_fix_count"], 1)

            with (output_dir / "action_handoff_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                by_request["bari_signal_phase_01"]["handoff_target_kind"],
                "dispatch_execution_log",
            )
            self.assertEqual(
                Path(by_request["bari_signal_phase_01"]["handoff_target_path"]),
                dispatch_execution_log_path,
            )
            self.assertEqual(
                by_request["bari_signal_phase_04"]["handoff_target_kind"],
                "runtime_cycle_command",
            )
            self.assertIn(
                "run-bari-signal-phase-runtime-cycle",
                by_request["bari_signal_phase_04"]["handoff_instructions"].lower(),
            )

            with (output_dir / "action_handoff_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(hold_rows[0]["action_category"], "await_delivery")


if __name__ == "__main__":
    unittest.main()
