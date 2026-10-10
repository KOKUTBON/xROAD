from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_targeting import build_bari_signal_phase_target_bundle


class SignalPhaseTargetingTests(unittest.TestCase):
    def test_build_bari_signal_phase_target_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "targets"
            target_coverage_path = root / "target_junction_coverage.csv"
            uncovered_hotspots_path = root / "uncovered_signalized_hotspots.csv"
            target_queue_path = root / "target_request_queue.csv"
            matched_records_path = root / "matched_node_records.jsonl"

            with target_coverage_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "recommended_provider_profile",
                        "required_profiles",
                        "signalized_movement_count",
                        "matched_signalized_crash_count",
                        "movements_with_provider_data",
                        "movements_with_phase_timing",
                        "movements_with_phase_mapping",
                        "unresolved_signalized_movement_count",
                        "unresolved_signalized_crash_count",
                        "unresolved_coverage_pct",
                        "unresolved_crash_coverage_pct",
                        "movements_without_phase_timing",
                        "crashes_without_phase_timing",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_rank": "1",
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                        "signalized_movement_count": "10",
                        "matched_signalized_crash_count": "20",
                        "movements_with_provider_data": "10",
                        "movements_with_phase_timing": "1",
                        "movements_with_phase_mapping": "1",
                        "unresolved_signalized_movement_count": "4",
                        "unresolved_signalized_crash_count": "11",
                        "unresolved_coverage_pct": "40.0",
                        "unresolved_crash_coverage_pct": "55.0",
                        "movements_without_phase_timing": "9",
                        "crashes_without_phase_timing": "20",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_rank": "2",
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                        "signalized_movement_count": "12",
                        "matched_signalized_crash_count": "15",
                        "movements_with_provider_data": "0",
                        "movements_with_phase_timing": "0",
                        "movements_with_phase_mapping": "0",
                        "unresolved_signalized_movement_count": "0",
                        "unresolved_signalized_crash_count": "0",
                        "unresolved_coverage_pct": "0.0",
                        "unresolved_crash_coverage_pct": "0.0",
                        "movements_without_phase_timing": "12",
                        "crashes_without_phase_timing": "15",
                    }
                )

            with uncovered_hotspots_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "node_object_id",
                        "movement_name",
                        "movement_turn",
                        "matched_crash_count",
                        "movement_resolution_state",
                        "phase_priority_group",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "node_object_id": "move_1",
                        "movement_name": "Via A [u_turn]",
                        "movement_turn": "u_turn",
                        "matched_crash_count": "12",
                        "movement_resolution_state": "ambiguous_target_variant",
                        "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "node_object_id": "move_2",
                        "movement_name": "Via B [straight]",
                        "movement_turn": "straight",
                        "matched_crash_count": "9",
                        "movement_resolution_state": "explicit_target",
                        "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                    }
                )

            with target_queue_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_rank",
                        "priority_band",
                        "recommended_provider_profile",
                        "required_profiles",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_rank": "1",
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_rank": "2",
                        "priority_band": "tier_1_immediate",
                        "recommended_provider_profile": "controller_event_log_export",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                    }
                )

            matched_records = [
                {
                    "junction_id": "it-bari-signal-93",
                    "control_state": "signalized",
                    "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                    "occurred_at": "2025-01-06T08:15:00",
                    "occurred_hour": 8,
                    "extra": {"official_bari_open_data": {"time_of_day_bucket": "morning"}},
                },
                {
                    "junction_id": "it-bari-signal-93",
                    "control_state": "signalized",
                    "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                    "occurred_at": "2025-01-07T08:30:00",
                    "occurred_hour": 8,
                    "extra": {"official_bari_open_data": {"time_of_day_bucket": "morning"}},
                },
                {
                    "junction_id": "it-bari-signal-93",
                    "control_state": "signalized",
                    "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                    "occurred_at": "2025-01-11T19:10:00",
                    "occurred_hour": 19,
                    "extra": {"official_bari_open_data": {"time_of_day_bucket": "evening"}},
                },
                {
                    "junction_id": "it-bari-signal-94",
                    "control_state": "signalized",
                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                    "occurred_at": "2025-01-12T15:00:00",
                    "occurred_hour": 15,
                    "extra": {"official_bari_open_data": {"time_of_day_bucket": "afternoon"}},
                },
                {
                    "junction_id": "it-bari-signal-94",
                    "control_state": "signalized",
                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                    "occurred_at": "2025-01-13T16:00:00",
                    "occurred_hour": 16,
                    "extra": {"official_bari_open_data": {"time_of_day_bucket": "afternoon"}},
                },
            ]
            with matched_records_path.open("w", encoding="utf-8") as handle:
                for record in matched_records:
                    handle.write(json.dumps(record) + "\n")

            result = build_bari_signal_phase_target_bundle(
                output_dir=output_dir,
                target_junction_coverage_path=target_coverage_path,
                uncovered_signalized_hotspots_path=uncovered_hotspots_path,
                target_request_queue_path=target_queue_path,
                matched_movement_records_path=matched_records_path,
                top_hotspots_per_target=3,
            )

            self.assertEqual(result["stats"]["target_count"], 2)
            self.assertEqual(result["stats"]["packet_count"], 2)
            self.assertEqual(result["stats"]["targets_with_provider_data"], 1)
            self.assertEqual(result["stats"]["targets_with_phase_timing"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 4)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 11)

            payload = json.loads((output_dir / "signal_phase_target_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["targets"]), 2)
            self.assertEqual(payload["targets"][0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(payload["targets"][0]["coverage_state"], "partial_phase_coverage")
            self.assertEqual(payload["targets"][0]["temporal_profile"]["peak_crash_hour"], 8)
            self.assertEqual(payload["targets"][0]["temporal_profile"]["dominant_day_type"], "weekday")
            self.assertEqual(payload["targets"][0]["unresolved_signalized_movement_count"], 4)
            self.assertEqual(payload["targets"][0]["unresolved_signalized_crash_count"], 11)
            self.assertEqual(payload["targets"][1]["coverage_state"], "no_provider_data")
            self.assertEqual(payload["summary"]["targets_with_time_profiles"], 2)
            self.assertEqual(payload["summary"]["timed_signalized_crash_total"], 5)
            self.assertEqual(payload["summary"]["targets_with_unresolved_movements"], 1)

            packet_path = output_dir / "target_packets" / "bari_signal_phase_01.json"
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["top_uncovered_movements"][0]["movement_name"], "Via A [u_turn]")
            self.assertEqual(packet["temporal_profile"]["peak_time_of_day_bucket"], "morning")
            self.assertIn("08:00-08:59", packet["temporal_profile"]["recommended_time_window"])
            self.assertIn("Prioritize unresolved movement resolution", packet["recommended_next_action"])

            with (output_dir / "target_priority_matrix.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(rows[1]["coverage_state"], "no_provider_data")
            self.assertEqual(rows[0]["peak_crash_hour"], "8")
            self.assertEqual(rows[0]["recommended_time_window"], "weekday morning, especially 08:00-08:59, 19:00-19:59")
            self.assertEqual(rows[0]["unresolved_signalized_movement_count"], "4")
            self.assertEqual(rows[0]["unresolved_signalized_crash_count"], "11")

            with (output_dir / "target_time_profiles.csv").open(encoding="utf-8", newline="") as handle:
                time_rows = list(csv.DictReader(handle))
            self.assertEqual(time_rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(time_rows[0]["peak_time_of_day_bucket"], "morning")
            self.assertEqual(time_rows[1]["dominant_day_type"], "balanced")

            with (output_dir / "target_hourly_profile.csv").open(encoding="utf-8", newline="") as handle:
                hour_rows = list(csv.DictReader(handle))
            self.assertEqual(len(hour_rows), 48)
            peak_hour_rows = [
                row
                for row in hour_rows
                if row["request_id"] == "bari_signal_phase_01" and row["hour"] == "8"
            ]
            self.assertEqual(len(peak_hour_rows), 1)
            self.assertEqual(peak_hour_rows[0]["matched_crash_count"], "2")


if __name__ == "__main__":
    unittest.main()
