from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_contact_resolution import (
    build_bari_signal_phase_contact_resolution_bundle,
)


class SignalPhaseContactResolutionTests(unittest.TestCase):
    def test_missing_private_contacts_does_not_use_embedded_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = root / "contacts.json"
            bundle.write_text(json.dumps({"send_queue": []}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "verified official_channels"):
                build_bari_signal_phase_contact_resolution_bundle(
                    output_dir=root / "output", signal_phase_contact_bundle_path=bundle
                )

    def test_build_bari_signal_phase_contact_resolution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_contact_resolution"
            contact_bundle_path = root / "signal_phase_contact_bundle.json"

            contact_bundle_path.write_text(
                json.dumps(
                    {
                        "source_observed_as_of": "2000-01-01",
                        "official_channels": [
                            {
                                "channel_id": str(i),
                                "channel_role": "example",
                                "channel_type": kind,
                                "channel_value": value,
                                "owner_team": "Example authority",
                                "recommended_use": "Synthetic routing fixture",
                                "source_title": "Synthetic fixture",
                                "source_url": "https://example.test",
                                "source_observed_as_of": "2000-01-01",
                            }
                            for i, (kind, value) in enumerate(
                                [
                                    ("pec_email", "planning@pec.example.test"),
                                    ("pec_email", "archives@pec.example.test"),
                                    ("email", "administration@example.test"),
                                    ("phone", "+1 202 555 0100"),
                                    ("phone", "+1 202 555 0101"),
                                ]
                            )
                        ],
                        "send_queue": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A Junction",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "send_readiness": "missing_contact_details",
                                "contact_name": "",
                                "contact_email": "",
                                "preferred_primary_channel": "administration@example.test",
                                "preferred_secondary_channel": "planning@pec.example.test",
                                "routing_decision": "Start with general municipal email, then escalate to PEC if not acknowledged.",
                                "external_blocker": "owner_team_confirmation_pending",
                                "email_subject": "Data request for Via A Junction",
                                "recommended_time_window": "weekday afternoon, especially 12:00-12:59",
                                "preferred_focus_hour_ranges": "12:00-12:59 | 14:00-14:59",
                                "fallback_pilot_scope": "8 weeks of weekday coverage around 12:00-12:59 | 14:00-14:59",
                                "unresolved_signalized_movement_count": 6,
                                "unresolved_signalized_crash_count": 13,
                                "unresolved_coverage_pct": 30.0,
                                "unresolved_crash_coverage_pct": 65.0,
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Via B Junction",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "send_readiness": "ready_to_send",
                                "contact_name": "Mario Rossi",
                                "contact_email": "mario.rossi@example.com",
                                "preferred_primary_channel": "",
                                "preferred_secondary_channel": "",
                                "routing_decision": "",
                                "external_blocker": "",
                                "email_subject": "Data request for Via B Junction",
                                "recommended_time_window": "weekday overnight, especially 00:00-00:59",
                                "preferred_focus_hour_ranges": "00:00-00:59",
                                "fallback_pilot_scope": "8 weeks of weekday coverage around 00:00-00:59",
                                "unresolved_signalized_movement_count": 0,
                                "unresolved_signalized_crash_count": 0,
                                "unresolved_coverage_pct": 0.0,
                                "unresolved_crash_coverage_pct": 0.0,
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_contact_resolution_bundle(
                output_dir=output_dir,
                signal_phase_contact_bundle_path=contact_bundle_path,
            )

            self.assertEqual(result["stats"]["target_count"], 2)
            self.assertEqual(result["stats"]["direct_contact_count"], 1)
            self.assertEqual(result["stats"]["routable_via_official_channels_count"], 2)
            self.assertEqual(result["stats"]["official_channel_count"], 5)
            self.assertEqual(result["stats"]["external_blocker_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            payload = json.loads(
                (output_dir / "signal_phase_contact_resolution_bundle.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(payload["resolution_queue"]), 2)
            self.assertEqual(len(payload["official_channels"]), 5)
            self.assertEqual(
                payload["resolution_queue"][0]["primary_channel_value"],
                "administration@example.test",
            )
            self.assertEqual(
                payload["resolution_queue"][0]["primary_channel_type"], "email"
            )
            self.assertEqual(
                payload["resolution_queue"][0]["secondary_channel_value"],
                "planning@pec.example.test",
            )
            self.assertEqual(
                payload["resolution_queue"][0]["secondary_channel_type"], "pec_email"
            )
            self.assertEqual(
                payload["resolution_queue"][0]["unresolved_signalized_movement_count"],
                6,
            )
            self.assertEqual(
                payload["resolution_queue"][0]["unresolved_signalized_crash_count"], 13
            )
            self.assertEqual(
                payload["resolution_queue"][1]["contact_email"],
                "mario.rossi@example.com",
            )
            self.assertEqual(
                payload["resolution_queue"][0]["recommended_routing_action"],
                "Start with general municipal email, then escalate to PEC if not acknowledged.",
            )
            self.assertEqual(
                payload["resolution_queue"][0]["external_blocker"],
                "owner_team_confirmation_pending",
            )
            self.assertEqual(payload["summary"]["targets_with_unresolved_movements"], 1)

            with (output_dir / "official_contact_channels.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                official_rows = list(csv.DictReader(handle))
            self.assertEqual(len(official_rows), 5)
            self.assertEqual(official_rows[0]["channel_id"], "0")

            with (output_dir / "contact_resolution_queue.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(len(queue_rows), 2)
            self.assertEqual(queue_rows[0]["phone_escalation_value"], "+1 202 555 0100")
            self.assertEqual(
                queue_rows[0]["external_blocker"], "owner_team_confirmation_pending"
            )
            self.assertEqual(queue_rows[0]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(queue_rows[0]["unresolved_signalized_crash_count"], "13")

            packet_md = (
                output_dir / "resolution_packets" / "bari_signal_phase_01.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Primary channel", packet_md)
            self.assertIn("administration@example.test", packet_md)
            self.assertIn(
                "Unresolved movement burden: `6` movements / `13` crashes", packet_md
            )


if __name__ == "__main__":
    unittest.main()
