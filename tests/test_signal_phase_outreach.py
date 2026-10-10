from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_outreach import build_bari_signal_phase_outreach_bundle


class SignalPhaseOutreachTests(unittest.TestCase):
    def test_build_bari_signal_phase_outreach_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_outreach"
            request_pack_path = root / "signal_phase_request_pack.json"
            acquisition_plan_path = root / "signal_phase_acquisition_plan.json"
            request_template_dir = root / "request_templates"
            request_template_dir.mkdir(parents=True, exist_ok=True)

            template_path = request_template_dir / "controller_event_log_export_request.md"
            template_path.write_text("# Controller Event Log Request\n\nBase template body.", encoding="utf-8")

            request_pack_path.write_text(
                json.dumps(
                    {
                        "priority_request_rows": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "CAPRUZZI - B. CROCE",
                                "priority_band": "tier_1_immediate",
                                "recommended_provider_profile": "controller_event_log_export",
                                "signalized_crash_total": 59,
                                "ambiguous_movement_count": 36,
                                "sample_incoming_arm_id": "arm_in_01",
                                "sample_movement_turn": "left",
                                "sample_outgoing_arm_id": "arm_out_01",
                                "sample_resolution_state": "ambiguous_target_variant",
                                "movement_turn_catalog": "left | straight | right",
                                "phase_groups_present": "signalized_pedestrian_stage",
                            },
                            {
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-10",
                                "signal_name": "TEST SIGNAL",
                                "priority_band": "tier_2_next_wave",
                                "recommended_provider_profile": "controller_event_log_export",
                                "signalized_crash_total": 8,
                                "ambiguous_movement_count": 4,
                                "sample_incoming_arm_id": "arm_in_02",
                                "sample_movement_turn": "straight",
                                "sample_outgoing_arm_id": "arm_out_02",
                                "sample_resolution_state": "explicit_target",
                                "movement_turn_catalog": "straight",
                                "phase_groups_present": "signalized_aligned_turn_phase_unknown",
                            },
                        ],
                        "outputs": {
                            "template_paths": [str(template_path)],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            outreach_tracker_path = root / "outreach_tracker.csv"
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
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "it-bari-signal-93",
                            "signal_name": "CAPRUZZI - B. CROCE",
                            "priority_rank": 1,
                            "priority_band": "tier_1_immediate",
                            "recommended_provider_profile": "controller_event_log_export",
                            "acquisition_status": "pending_outreach",
                            "owner_team": "traffic control center",
                            "contact_name": "",
                            "contact_email": "",
                            "last_contact_date": "",
                            "next_follow_up_date": "",
                            "request_window": "last_12_months_plus_current_control_state",
                            "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet | junction_phase_diagram_support",
                            "delivery_note": "Use first for the busiest and most ambiguous signalized junctions.",
                            "signalized_crash_total": 59,
                            "ambiguous_movement_count": 36,
                        },
                        {
                            "request_id": "bari_signal_phase_02",
                            "junction_id": "it-bari-signal-10",
                            "signal_name": "TEST SIGNAL",
                            "priority_rank": 2,
                            "priority_band": "tier_2_next_wave",
                            "recommended_provider_profile": "controller_event_log_export",
                            "acquisition_status": "pending_outreach",
                            "owner_team": "traffic control center",
                            "contact_name": "",
                            "contact_email": "",
                            "last_contact_date": "",
                            "next_follow_up_date": "",
                            "request_window": "last_12_months_plus_current_control_state",
                            "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                            "delivery_note": "Use first for the busiest and most ambiguous signalized junctions.",
                            "signalized_crash_total": 8,
                            "ambiguous_movement_count": 4,
                        },
                    ]
                )

            delivery_checklist_path = root / "delivery_checklist.csv"
            with delivery_checklist_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "delivery_item_id",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_band",
                        "profile_id",
                        "owner_team",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "delivery_status",
                        "received_date",
                        "validated_date",
                        "mapped_to_movements",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "it-bari-signal-93",
                            "signal_name": "CAPRUZZI - B. CROCE",
                            "priority_band": "tier_1_immediate",
                            "profile_id": "controller_event_log_export",
                            "owner_team": "traffic control center",
                            "delivery_format": "CSV export",
                            "requested_window": "last_12_months_plus_current_control_state",
                            "acceptance_gate": "valid events",
                            "delivery_status": "awaiting_request",
                            "received_date": "",
                            "validated_date": "",
                            "mapped_to_movements": "no",
                            "notes": "primary",
                        },
                        {
                            "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "it-bari-signal-93",
                            "signal_name": "CAPRUZZI - B. CROCE",
                            "priority_band": "tier_1_immediate",
                            "profile_id": "arm_phase_mapping_sheet",
                            "owner_team": "internal analyst",
                            "delivery_format": "CSV mapping",
                            "requested_window": "current_junction_geometry_revision",
                            "acceptance_gate": "mapped movements",
                            "delivery_status": "awaiting_request",
                            "received_date": "",
                            "validated_date": "",
                            "mapped_to_movements": "no",
                            "notes": "mapping",
                        },
                        {
                            "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "it-bari-signal-93",
                            "signal_name": "CAPRUZZI - B. CROCE",
                            "priority_band": "tier_1_immediate",
                            "profile_id": "junction_phase_diagram_support",
                            "owner_team": "signal maintenance contractor",
                            "delivery_format": "PDF",
                            "requested_window": "current_operational_layout",
                            "acceptance_gate": "diagram present",
                            "delivery_status": "awaiting_request",
                            "received_date": "",
                            "validated_date": "",
                            "mapped_to_movements": "no",
                            "notes": "diagram",
                        },
                    ]
                )

            acquisition_plan_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "outreach_tracker_csv_path": str(outreach_tracker_path),
                            "delivery_checklist_csv_path": str(delivery_checklist_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_outreach_bundle(
                output_dir=output_dir,
                acquisition_plan_path=acquisition_plan_path,
                signal_phase_request_pack_path=request_pack_path,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_outreach_bundle_builder")
            self.assertEqual(manifest["stats"]["target_request_count"], 1)
            self.assertEqual(manifest["stats"]["target_delivery_item_count"], 3)
            self.assertEqual(manifest["stats"]["request_packet_count"], 1)
            self.assertEqual(manifest["stats"]["profile_packet_count"], 3)

            bundle_payload = json.loads((output_dir / "signal_phase_outreach_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle_payload["inputs"]["priority_band"], "tier_1_immediate")
            self.assertEqual(len(bundle_payload["target_requests"]), 1)
            self.assertEqual(bundle_payload["target_requests"][0]["junction_id"], "it-bari-signal-93")

            with (output_dir / "target_request_queue.csv").open(encoding="utf-8", newline="") as handle:
                request_rows = list(csv.DictReader(handle))
            self.assertEqual(len(request_rows), 1)

            with (output_dir / "target_delivery_queue.csv").open(encoding="utf-8", newline="") as handle:
                delivery_rows = list(csv.DictReader(handle))
            self.assertEqual(len(delivery_rows), 3)

            packet_paths = list((output_dir / "request_packets").glob("*.md"))
            self.assertEqual(len(packet_paths), 1)
            self.assertIn("Controller Event Log Request", packet_paths[0].read_text(encoding="utf-8"))

            profile_packet_paths = sorted((output_dir / "profile_packets").glob("*.md"))
            self.assertEqual(len(profile_packet_paths), 3)


if __name__ == "__main__":
    unittest.main()
