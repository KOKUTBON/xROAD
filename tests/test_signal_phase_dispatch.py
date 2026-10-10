from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch import build_bari_signal_phase_dispatch_bundle


class SignalPhaseDispatchTests(unittest.TestCase):
    def test_build_bari_signal_phase_dispatch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch"
            resolution_bundle_path = root / "signal_phase_contact_resolution_bundle.json"

            resolution_bundle_path.write_text(
                json.dumps(
                    {
                        "resolution_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A Junction",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "contact_name": "",
                                "contact_email": "",
                                "email_subject": "Data request for Via A Junction",
                                "recommended_time_window": "weekday afternoon, especially 12:00-12:59",
                                "preferred_focus_hour_ranges": "12:00-12:59 | 14:00-14:59",
                                "fallback_pilot_scope": "8 weeks of weekday coverage around 12:00-12:59 | 14:00-14:59",
                                "routing_decision": "Use PEC-first routing with archivio generale in CC.",
                                "external_blocker": "awaiting_reply_after_first_send",
                                "primary_channel_type": "pec_email",
                                "primary_channel_value": "planning@pec.example.test",
                                "secondary_channel_type": "pec_email",
                                "secondary_channel_value": "archives@pec.example.test",
                                "phone_escalation_type": "phone",
                                "phone_escalation_value": "+39 080 577 1111",
                                "unresolved_signalized_movement_count": 6,
                                "unresolved_signalized_crash_count": 13,
                                "unresolved_coverage_pct": 30.0,
                                "unresolved_crash_coverage_pct": 65.0,
                                "recommended_routing_action": "Send by PEC and call if needed.",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Via B Junction",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "contact_name": "Mario Rossi",
                                "contact_email": "mario.rossi@example.com",
                                "email_subject": "Data request for Via B Junction",
                                "recommended_time_window": "weekday overnight, especially 00:00-00:59",
                                "preferred_focus_hour_ranges": "00:00-00:59",
                                "fallback_pilot_scope": "8 weeks of weekday coverage around 00:00-00:59",
                                "routing_decision": "",
                                "external_blocker": "",
                                "primary_channel_type": "pec_email",
                                "primary_channel_value": "planning@pec.example.test",
                                "secondary_channel_type": "pec_email",
                                "secondary_channel_value": "archives@pec.example.test",
                                "phone_escalation_type": "phone",
                                "phone_escalation_value": "+39 080 577 1111",
                                "unresolved_signalized_movement_count": 0,
                                "unresolved_signalized_crash_count": 0,
                                "unresolved_coverage_pct": 0.0,
                                "unresolved_crash_coverage_pct": 0.0,
                                "recommended_routing_action": "Send by PEC and call if needed.",
                            },
                        ],
                        "official_channels": [
                            {
                                "channel_role": "service_pec",
                                "channel_type": "pec_email",
                                "channel_value": "planning@pec.example.test",
                            },
                            {
                                "channel_role": "general_protocol_pec",
                                "channel_type": "pec_email",
                                "channel_value": "archives@pec.example.test",
                            },
                            {
                                "channel_role": "general_email",
                                "channel_type": "email",
                                "channel_value": "administration@example.test",
                            },
                            {
                                "channel_role": "phone_switchboard",
                                "channel_type": "phone",
                                "channel_value": "+39 080 577 1111",
                            },
                            {
                                "channel_role": "public_relations",
                                "channel_type": "phone",
                                "channel_value": "080/5772390 ; 800/018291",
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_dispatch_bundle(
                output_dir=output_dir,
                signal_phase_contact_resolution_bundle_path=resolution_bundle_path,
                planned_dispatch_date="2026-03-29",
                follow_up_days=7,
                escalation_days=14,
            )

            self.assertEqual(result["stats"]["target_count"], 2)
            self.assertEqual(result["stats"]["dispatch_queue_count"], 2)
            self.assertEqual(result["stats"]["follow_up_item_count"], 4)
            self.assertEqual(result["stats"]["primary_pec_count"], 2)
            self.assertEqual(result["stats"]["direct_contact_count"], 1)
            self.assertEqual(result["stats"]["external_blocker_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            payload = json.loads((output_dir / "signal_phase_dispatch_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["dispatch_queue"]), 2)
            self.assertEqual(payload["dispatch_queue"][0]["dispatch_reference"], "BARI-SPD-20260329-01")
            self.assertEqual(payload["dispatch_queue"][0]["first_follow_up_date"], "2026-04-05")
            self.assertEqual(payload["dispatch_queue"][0]["escalation_date"], "2026-04-12")
            self.assertEqual(payload["dispatch_queue"][0]["general_email_value"], "administration@example.test")
            self.assertEqual(payload["dispatch_queue"][0]["unresolved_signalized_movement_count"], 6)
            self.assertEqual(payload["dispatch_queue"][0]["unresolved_signalized_crash_count"], 13)
            self.assertEqual(payload["dispatch_queue"][0]["unresolved_coverage_pct"], 30.0)
            self.assertEqual(
                payload["dispatch_queue"][0]["routing_decision"],
                "Use PEC-first routing with archivio generale in CC.",
            )
            self.assertEqual(
                payload["dispatch_queue"][0]["external_blocker"],
                "awaiting_reply_after_first_send",
            )
            self.assertEqual(payload["summary"]["targets_with_unresolved_movements"], 1)

            with (output_dir / "dispatch_execution_queue.csv").open(encoding="utf-8", newline="") as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(len(queue_rows), 2)
            self.assertEqual(queue_rows[0]["dispatch_status"], "pending_dispatch")
            self.assertEqual(queue_rows[0]["external_blocker"], "awaiting_reply_after_first_send")
            self.assertEqual(queue_rows[0]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(queue_rows[0]["unresolved_signalized_crash_count"], "13")

            with (output_dir / "follow_up_tracker.csv").open(encoding="utf-8", newline="") as handle:
                follow_up_rows = list(csv.DictReader(handle))
            self.assertEqual(len(follow_up_rows), 4)
            self.assertEqual(follow_up_rows[0]["follow_up_stage"], "first_follow_up")
            self.assertEqual(follow_up_rows[1]["follow_up_stage"], "escalation")

            packet_md = (output_dir / "dispatch_packets" / "bari_signal_phase_01.md").read_text(encoding="utf-8")
            self.assertIn("To: `planning@pec.example.test`", packet_md)
            self.assertIn("First follow-up due: `2026-04-05`", packet_md)
            self.assertIn("External blocker: `awaiting_reply_after_first_send`", packet_md)
            self.assertIn("Unresolved movement burden: `6` movements / `13` crashes", packet_md)


if __name__ == "__main__":
    unittest.main()
