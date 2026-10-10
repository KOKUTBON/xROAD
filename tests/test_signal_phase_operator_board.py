from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_operator_board import (
    build_bari_signal_phase_operator_board_bundle,
)


class SignalPhaseOperatorBoardTest(unittest.TestCase):
    def test_build_bari_signal_phase_operator_board_bundle_merges_execution_and_handoff(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "operator_board"
            action_execution_bundle_path = root / "signal_phase_action_execution_bundle.json"
            action_handoff_bundle_path = root / "signal_phase_action_handoff_bundle.json"

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
                                "packet_md_path": "/tmp/bari_signal_phase_01.md",
                                "packet_json_path": "/tmp/bari_signal_phase_01.json",
                                "packet_available": "yes",
                                "primary_channel_value": "urbanistica@example.com",
                                "secondary_channel_value": "archivio@example.com",
                                "phone_escalation_value": "+39 080 577 1111",
                                "recommended_action": "Send the PEC request.",
                                "action_summary": "Send the initial request.",
                                "execution_summary": "Send the initial request packet.",
                            }
                        ],
                        "internal_hold_queue": [
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "action_category": "await_delivery",
                                "execution_route": "",
                                "due_now": "no",
                                "packet_available": "no",
                                "hold_reason": "Wait for delivery.",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            action_handoff_bundle_path.write_text(
                json.dumps(
                    {
                        "handoff_ready_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "handoff_target_kind": "dispatch_execution_log",
                                "handoff_target_path": "/tmp/dispatch_execution_log.csv",
                                "handoff_status": "ready_for_operator",
                                "handoff_instructions": "Update the dispatch log after the send.",
                                "handoff_reference_key": "request_id",
                                "handoff_reference_value": "bari_signal_phase_01",
                            }
                        ],
                        "internal_hold_queue": [],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_operator_board_bundle(
                output_dir=output_dir,
                signal_phase_action_execution_bundle_path=action_execution_bundle_path,
                signal_phase_action_handoff_bundle_path=action_handoff_bundle_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["operator_ready_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["dispatch_row_count"], 1)
            self.assertEqual(result["stats"]["follow_up_row_count"], 0)

            with (output_dir / "operator_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(ready_rows[0]["handoff_target_kind"], "dispatch_execution_log")
            self.assertEqual(ready_rows[0]["handoff_target_path"], "/tmp/dispatch_execution_log.csv")

            with (output_dir / "operator_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(hold_rows[0]["request_id"], "bari_signal_phase_02")
            self.assertEqual(hold_rows[0]["hold_reason"], "Wait for delivery.")


if __name__ == "__main__":
    unittest.main()
