from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_contact_bundle import build_bari_signal_phase_contact_bundle


class SignalPhaseContactBundleTests(unittest.TestCase):
    def test_build_bari_signal_phase_contact_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_contact"
            scope_bundle_path = root / "signal_phase_request_scope_bundle.json"
            outreach_tracker_path = root / "outreach_tracker.csv"

            scope_bundle_path.write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A Junction",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "matched_signalized_crash_count": 20,
                                "timed_signalized_crash_count": 20,
                                "unresolved_signalized_movement_count": 6,
                                "unresolved_signalized_crash_count": 13,
                                "unresolved_coverage_pct": 30.0,
                                "unresolved_crash_coverage_pct": 65.0,
                                "top_hotspot_name": "Via A [u_turn]",
                                "top_hotspot_crash_count": 12,
                                "recommended_time_window": "weekday afternoon, especially 12:00-12:59, 14:00-14:59",
                                "preferred_focus_hour_ranges": "12:00-12:59 | 14:00-14:59",
                                "recommended_pilot_scope": "8 weeks of weekday coverage around 12:00-12:59 | 14:00-14:59",
                                "delivery_scopes": [
                                    {
                                        "profile_id": "controller_event_log_export",
                                        "scoped_requested_window": "last_12_months_plus_current_control_state; fallback pilot scope: 8 weeks of weekday coverage around 12:00-12:59 | 14:00-14:59",
                                    },
                                    {
                                        "profile_id": "arm_phase_mapping_sheet",
                                        "scoped_requested_window": "current_junction_geometry_revision; focus mapping on Via A [u_turn]",
                                    },
                                    {
                                        "profile_id": "junction_phase_diagram_support",
                                        "scoped_requested_window": "current_operational_layout; highlight protected turns affecting Via A [u_turn]",
                                    },
                                ],
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Via B Junction",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "matched_signalized_crash_count": 15,
                                "timed_signalized_crash_count": 15,
                                "unresolved_signalized_movement_count": 0,
                                "unresolved_signalized_crash_count": 0,
                                "unresolved_coverage_pct": 0.0,
                                "unresolved_crash_coverage_pct": 0.0,
                                "top_hotspot_name": "Via B [straight]",
                                "top_hotspot_crash_count": 9,
                                "recommended_time_window": "weekday overnight, especially 00:00-00:59",
                                "preferred_focus_hour_ranges": "00:00-00:59",
                                "recommended_pilot_scope": "8 weeks of weekday coverage around 00:00-00:59",
                                "delivery_scopes": [
                                    {
                                        "profile_id": "controller_event_log_export",
                                        "scoped_requested_window": "last_12_months_plus_current_control_state; fallback pilot scope: 8 weeks of weekday coverage around 00:00-00:59",
                                    }
                                ],
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with outreach_tracker_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "recommended_provider_profile",
                        "acquisition_status",
                        "owner_team",
                        "contact_name",
                        "contact_email",
                        "preferred_primary_channel",
                        "preferred_secondary_channel",
                        "routing_decision",
                        "external_blocker",
                        "last_contact_date",
                        "next_follow_up_date",
                        "request_window",
                        "required_profiles",
                        "delivery_note",
                        "signalized_crash_total",
                        "ambiguous_movement_count",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "acquisition_status": "pending_outreach",
                        "owner_team": "ITS",
                        "contact_name": "Mario Rossi",
                        "contact_email": "mario.rossi@example.com",
                        "preferred_primary_channel": "planning@pec.example.test",
                        "preferred_secondary_channel": "archives@pec.example.test",
                        "routing_decision": "Send PEC to mobility office and CC archivio generale.",
                        "external_blocker": "awaiting_official_reply",
                        "last_contact_date": "",
                        "next_follow_up_date": "",
                        "request_window": "last_12_months_plus_current_control_state",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet | junction_phase_diagram_support",
                        "delivery_note": "Use first for the busiest and most ambiguous signalized junctions.",
                        "signalized_crash_total": 20,
                        "ambiguous_movement_count": 10,
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_rank": 2,
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "acquisition_status": "pending_outreach",
                        "owner_team": "ITS",
                        "contact_name": "",
                        "contact_email": "",
                        "preferred_primary_channel": "",
                        "preferred_secondary_channel": "",
                        "routing_decision": "",
                        "external_blocker": "",
                        "last_contact_date": "",
                        "next_follow_up_date": "",
                        "request_window": "last_12_months_plus_current_control_state",
                        "required_profiles": "controller_event_log_export",
                        "delivery_note": "Use first for the busiest and most ambiguous signalized junctions.",
                        "signalized_crash_total": 15,
                        "ambiguous_movement_count": 4,
                    }
                )

            result = build_bari_signal_phase_contact_bundle(
                output_dir=output_dir,
                signal_phase_request_scope_bundle_path=scope_bundle_path,
                outreach_tracker_path=outreach_tracker_path,
                follow_up_days=10,
            )

            self.assertEqual(result["stats"]["target_count"], 2)
            self.assertEqual(result["stats"]["draft_count"], 2)
            self.assertEqual(result["stats"]["ready_to_send_count"], 1)
            self.assertEqual(result["stats"]["missing_contact_details_count"], 1)
            self.assertEqual(result["stats"]["external_blocker_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            payload = json.loads((output_dir / "signal_phase_contact_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["send_queue"]), 2)
            self.assertEqual(payload["send_queue"][0]["send_readiness"], "ready_to_send")
            self.assertEqual(payload["send_queue"][0]["follow_up_days"], 10)
            self.assertIn("fallback pilot scope", payload["send_queue"][0]["controller_window_request"])
            self.assertEqual(payload["send_queue"][0]["unresolved_signalized_movement_count"], 6)
            self.assertEqual(payload["send_queue"][0]["unresolved_signalized_crash_count"], 13)
            self.assertEqual(
                payload["send_queue"][0]["preferred_primary_channel"],
                "planning@pec.example.test",
            )
            self.assertEqual(
                payload["send_queue"][0]["preferred_secondary_channel"],
                "archives@pec.example.test",
            )
            self.assertEqual(
                payload["send_queue"][0]["routing_decision"],
                "Send PEC to mobility office and CC archivio generale.",
            )
            self.assertEqual(payload["send_queue"][0]["external_blocker"], "awaiting_official_reply")
            self.assertEqual(payload["send_queue"][1]["send_readiness"], "missing_contact_details")
            self.assertEqual(payload["summary"]["targets_with_unresolved_movements"], 1)

            with (output_dir / "contact_send_queue.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["contact_email"], "mario.rossi@example.com")
            self.assertEqual(rows[0]["external_blocker"], "awaiting_official_reply")
            self.assertEqual(rows[1]["send_readiness"], "missing_contact_details")
            self.assertEqual(rows[0]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(rows[0]["unresolved_signalized_crash_count"], "13")

            draft_md = (output_dir / "email_drafts" / "bari_signal_phase_01.md").read_text(encoding="utf-8")
            self.assertIn("Dear Mario Rossi", draft_md)
            self.assertIn("8 weeks of weekday coverage around 12:00-12:59 | 14:00-14:59", draft_md)
            self.assertIn("Unresolved movement burden: `6` movements / `13` crashes", draft_md)


if __name__ == "__main__":
    unittest.main()
