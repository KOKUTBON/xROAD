from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_acquisition import build_bari_signal_phase_acquisition_plan


class SignalPhaseAcquisitionTests(unittest.TestCase):
    def test_build_bari_signal_phase_acquisition_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_acquisition"
            request_pack_path = root / "signal_phase_request_pack.json"
            request_pack_path.write_text(
                json.dumps(
                    {
                        "priority_request_rows": [
                            {
                                "request_id": "bari_phase_request_001",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "recommended_provider_profile": "controller_event_log_export",
                                "required_profiles": (
                                    "controller_event_log_export | arm_phase_mapping_sheet | "
                                    "junction_phase_diagram_support"
                                ),
                                "signalized_crash_total": 59,
                                "ambiguous_movement_count": 36,
                            },
                            {
                                "request_id": "bari_phase_request_002",
                                "junction_id": "it-bari-signal-10",
                                "signal_name": "TEST SIGNAL",
                                "priority_rank": 2,
                                "priority_band": "tier_2_next_wave",
                                "recommended_provider_profile": "signal_stage_plan_export",
                                "required_profiles": "signal_stage_plan_export | arm_phase_mapping_sheet",
                                "signalized_crash_total": 8,
                                "ambiguous_movement_count": 4,
                            },
                        ],
                        "stats": {
                            "recommended_profile_counts": {
                                "controller_event_log_export": 1,
                                "signal_stage_plan_export": 1,
                            }
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_acquisition_plan(
                output_dir=output_dir,
                signal_phase_request_pack_path=request_pack_path,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_acquisition_plan_builder")
            self.assertEqual(manifest["stats"]["request_row_count"], 2)
            self.assertEqual(manifest["stats"]["tier_1_signal_count"], 1)
            self.assertEqual(manifest["stats"]["tier_2_signal_count"], 1)
            self.assertEqual(manifest["stats"]["delivery_item_count"], 5)

            payload = json.loads((output_dir / "signal_phase_acquisition_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["delivery_item_count"], 5)
            self.assertEqual(len(payload["tier_1_requests"]), 1)
            self.assertEqual(
                payload["tier_1_requests"][0]["junction_id"],
                "it-bari-signal-93",
            )

            with (output_dir / "outreach_tracker.csv").open(encoding="utf-8", newline="") as handle:
                outreach_rows = list(csv.DictReader(handle))
            self.assertEqual(len(outreach_rows), 2)
            self.assertEqual(outreach_rows[0]["acquisition_status"], "pending_outreach")

            with (output_dir / "delivery_checklist.csv").open(encoding="utf-8", newline="") as handle:
                delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(delivery_rows), 5)
            self.assertEqual(delivery_rows[0]["delivery_status"], "awaiting_request")

    def test_build_bari_signal_phase_acquisition_plan_preserves_existing_live_tracker_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_acquisition"
            output_dir.mkdir(parents=True, exist_ok=True)
            request_pack_path = root / "signal_phase_request_pack.json"
            outreach_tracker_path = output_dir / "outreach_tracker.csv"

            request_pack_path.write_text(
                json.dumps(
                    {
                        "priority_request_rows": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Live Signal",
                                "priority_rank": 1,
                                "priority_band": "tier_1_immediate",
                                "recommended_provider_profile": "controller_event_log_export",
                                "required_profiles": (
                                    "controller_event_log_export | arm_phase_mapping_sheet | "
                                    "junction_phase_diagram_support"
                                ),
                                "signalized_crash_total": 59,
                                "ambiguous_movement_count": 36,
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Fresh Signal",
                                "priority_rank": 2,
                                "priority_band": "tier_1_immediate",
                                "recommended_provider_profile": "controller_event_log_export",
                                "required_profiles": "controller_event_log_export",
                                "signalized_crash_total": 54,
                                "ambiguous_movement_count": 18,
                            },
                        ],
                        "stats": {
                            "recommended_profile_counts": {
                                "controller_event_log_export": 2,
                            }
                        },
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
                        "last_contact_date",
                        "next_follow_up_date",
                        "request_window",
                        "required_profiles",
                        "delivery_note",
                        "signalized_crash_total",
                        "ambiguous_movement_count",
                        "preferred_primary_channel",
                        "preferred_secondary_channel",
                        "routing_decision",
                        "external_blocker",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Live Signal",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "acquisition_status": "initial_dispatch_sent",
                        "owner_team": "Comune di Bari mobility and viability service",
                        "contact_name": "Servizio Mobilita e Viabilita - Protocollo",
                        "contact_email": "planning@pec.example.test",
                        "last_contact_date": "2026-04-21",
                        "next_follow_up_date": "2026-04-28",
                        "request_window": "last_12_months_plus_current_control_state",
                        "required_profiles": (
                            "controller_event_log_export | arm_phase_mapping_sheet | "
                            "junction_phase_diagram_support"
                        ),
                        "delivery_note": "Use first for the busiest and most ambiguous signalized junctions.",
                        "signalized_crash_total": 59,
                        "ambiguous_movement_count": 36,
                        "preferred_primary_channel": "planning@pec.example.test",
                        "preferred_secondary_channel": "archives@pec.example.test",
                        "routing_decision": "Send via primary PEC and CC archivio generale PEC.",
                        "external_blocker": "awaiting_owner_reply_after_initial_dispatch",
                    }
                )

            manifest = build_bari_signal_phase_acquisition_plan(
                output_dir=output_dir,
                signal_phase_request_pack_path=request_pack_path,
            )

            with outreach_tracker_path.open(encoding="utf-8", newline="") as handle:
                outreach_rows = list(csv.DictReader(handle))

            self.assertEqual(len(outreach_rows), 2)
            self.assertEqual(outreach_rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(outreach_rows[0]["acquisition_status"], "initial_dispatch_sent")
            self.assertEqual(
                outreach_rows[0]["preferred_secondary_channel"],
                "archives@pec.example.test",
            )
            self.assertEqual(outreach_rows[0]["external_blocker"], "awaiting_owner_reply_after_initial_dispatch")
            self.assertEqual(outreach_rows[1]["request_id"], "bari_signal_phase_02")
            self.assertEqual(outreach_rows[1]["acquisition_status"], "pending_outreach")
            self.assertEqual(outreach_rows[1]["contact_email"], "")

            self.assertEqual(manifest["stats"]["outreach_status_counts"]["initial_dispatch_sent"], 1)
            self.assertEqual(manifest["stats"]["outreach_status_counts"]["pending_outreach"], 1)
            self.assertEqual(manifest["stats"]["contact_ready_row_count"], 1)
            self.assertEqual(manifest["stats"]["contacted_row_count"], 1)

            payload = json.loads((output_dir / "signal_phase_acquisition_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["outreach_status_counts"]["initial_dispatch_sent"], 1)
            plan_md = (output_dir / "signal_phase_acquisition_plan.md").read_text(encoding="utf-8")
            self.assertIn("Outreach status counts", plan_md)
            self.assertIn("Preserve the live outreach tracker as the source of truth", plan_md)


if __name__ == "__main__":
    unittest.main()
