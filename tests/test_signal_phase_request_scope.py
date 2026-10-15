from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_request_scope import build_bari_signal_phase_request_scope_bundle


class SignalPhaseRequestScopeTests(unittest.TestCase):
    def test_build_bari_signal_phase_request_scope_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_request_scope"
            target_bundle_path = root / "signal_phase_target_bundle.json"
            delivery_checklist_path = root / "delivery_checklist.csv"

            target_bundle = {
                "targets": [
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "coverage_state": "partial_phase_coverage",
                        "matched_signalized_crash_count": 20,
                        "unresolved_signalized_movement_count": 6,
                        "unresolved_signalized_crash_count": 13,
                        "unresolved_coverage_pct": 30.0,
                        "unresolved_crash_coverage_pct": 65.0,
                        "recommended_time_window": "weekday afternoon, especially 12:00-12:59, 14:00-14:59",
                        "top_hotspot_name": "Via A [u_turn]",
                        "top_hotspot_crash_count": 12,
                        "temporal_profile": {
                            "timed_signalized_crash_count": 20,
                            "dominant_day_type": "weekday",
                            "peak_time_of_day_bucket": "afternoon",
                            "peak_crash_hour_label": "12:00-12:59",
                            "recommended_time_window": "weekday afternoon, especially 12:00-12:59, 14:00-14:59",
                            "top_hours": [
                                {"hour": 12, "hour_label": "12:00-12:59", "crash_count": 7},
                                {"hour": 14, "hour_label": "14:00-14:59", "crash_count": 5},
                            ],
                        },
                        "top_uncovered_movements": [
                            {
                                "movement_name": "Via A [u_turn]",
                                "movement_turn": "u_turn",
                                "matched_crash_count": 12,
                            }
                        ],
                    },
                    {
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_rank": 2,
                        "priority_band": "tier_1_immediate",
                        "coverage_state": "no_provider_data",
                        "matched_signalized_crash_count": 15,
                        "unresolved_signalized_movement_count": 0,
                        "unresolved_signalized_crash_count": 0,
                        "unresolved_coverage_pct": 0.0,
                        "unresolved_crash_coverage_pct": 0.0,
                        "recommended_time_window": "weekend overnight, especially 00:00-01:59",
                        "top_hotspot_name": "Via B [straight]",
                        "top_hotspot_crash_count": 9,
                        "temporal_profile": {
                            "timed_signalized_crash_count": 15,
                            "dominant_day_type": "weekend",
                            "peak_time_of_day_bucket": "overnight",
                            "peak_crash_hour_label": "00:00-00:59",
                            "recommended_time_window": "weekend overnight, especially 00:00-01:59",
                            "top_hours": [
                                {"hour": 0, "hour_label": "00:00-00:59", "crash_count": 5},
                                {"hour": 1, "hour_label": "01:00-01:59", "crash_count": 4},
                            ],
                        },
                        "top_uncovered_movements": [
                            {
                                "movement_name": "Via B [straight]",
                                "movement_turn": "straight",
                                "matched_crash_count": 9,
                            }
                        ],
                    },
                ]
            }
            target_bundle_path.write_text(json.dumps(target_bundle), encoding="utf-8")

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
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "controller_event_log_export",
                        "owner_team": "ITS",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "coverage",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "arm_phase_mapping_sheet",
                        "owner_team": "Analyst",
                        "delivery_format": "CSV",
                        "requested_window": "current_junction_geometry_revision",
                        "acceptance_gate": "mapping",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_02__controller_event_log_export",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "controller_event_log_export",
                        "owner_team": "ITS",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "coverage",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )

            result = build_bari_signal_phase_request_scope_bundle(
                output_dir=output_dir,
                signal_phase_target_bundle_path=target_bundle_path,
                delivery_checklist_path=delivery_checklist_path,
            )

            self.assertEqual(result["stats"]["target_count"], 2)
            self.assertEqual(result["stats"]["delivery_scope_count"], 3)
            self.assertEqual(result["stats"]["controller_event_scope_count"], 2)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["targets_with_pilot_scopes"], 2)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            payload = json.loads((output_dir / "signal_phase_request_scope_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["targets"]), 2)
            self.assertEqual(payload["targets"][0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(payload["targets"][0]["preferred_focus_hour_ranges"], "12:00-12:59 | 14:00-14:59")
            self.assertEqual(payload["targets"][0]["unresolved_signalized_movement_count"], 6)
            self.assertEqual(payload["targets"][0]["unresolved_signalized_crash_count"], 13)
            self.assertIn("8 weeks of weekday coverage", payload["targets"][0]["recommended_pilot_scope"])
            self.assertEqual(payload["summary"]["targets_with_unresolved_movements"], 1)

            packet = json.loads((output_dir / "scope_packets" / "bari_signal_phase_01.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["delivery_scopes"][0]["profile_id"], "arm_phase_mapping_sheet")
            controller_scope = [row for row in packet["delivery_scopes"] if row["profile_id"] == "controller_event_log_export"][0]
            self.assertIn("last_12_months_plus_current_control_state", controller_scope["scoped_requested_window"])
            self.assertIn("8 weeks of weekday coverage", controller_scope["scoped_requested_window"])
            self.assertIn("Unresolved burden is 6 movements and 13 crashes", controller_scope["scope_rationale"])

            with (output_dir / "target_collection_windows.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(rows[0]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(rows[0]["unresolved_signalized_crash_count"], "13")
            self.assertEqual(rows[1]["preferred_focus_hour_ranges"], "00:00-01:59")

            with (output_dir / "delivery_scope_matrix.csv").open(encoding="utf-8", newline="") as handle:
                scope_rows = list(csv.DictReader(handle))
            self.assertEqual(len(scope_rows), 3)
            self.assertIn("controller_event_log_export", {row["profile_id"] for row in scope_rows})
            request_one_rows = [row for row in scope_rows if row["request_id"] == "bari_signal_phase_01"]
            self.assertTrue(request_one_rows)
            self.assertEqual({row["unresolved_signalized_movement_count"] for row in request_one_rows}, {"6"})
            self.assertEqual({row["unresolved_signalized_crash_count"] for row in request_one_rows}, {"13"})


if __name__ == "__main__":
    unittest.main()
