from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_coverage import build_bari_signal_phase_coverage_report


class SignalPhaseCoverageTests(unittest.TestCase):
    def test_build_bari_signal_phase_coverage_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "coverage"
            movement_path = root / "road_movement_objects_signal_phase.geojson"
            matched_path = root / "matched_node_records.jsonl"
            target_queue_path = root / "target_request_queue.csv"
            delivery_session_manifest_path = root / "signal_phase_delivery_session.manifest.json"

            movement_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m1",
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "signalized_turn_movement",
                                    "movement_turn": "straight",
                                    "name": "Via A [straight]",
                                    "control_state": "signalized",
                                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                    "signal_priority_variant": "signal_phase_unknown",
                                    "movement_resolution_state": "explicit_target",
                                    "junction_phase_provider_available": 1.0,
                                    "movement_phase_timing_available": 1.0,
                                    "movement_phase_mapping_available": 1.0,
                                },
                                "geometry": {"type": "Point", "coordinates": [16.86, 41.12]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m2",
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "signalized_turn_movement",
                                    "movement_turn": "left",
                                    "name": "Via A [left]",
                                    "control_state": "signalized",
                                    "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                                    "signal_priority_variant": "signal_phase_unknown",
                                    "movement_resolution_state": "ambiguous_target_variant",
                                    "junction_phase_provider_available": 1.0,
                                    "movement_phase_timing_available": 0.0,
                                    "movement_phase_mapping_available": 0.0,
                                },
                                "geometry": {"type": "Point", "coordinates": [16.861, 41.121]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m3",
                                    "junction_id": "it-bari-junction-1",
                                    "movement_role": "unsignalized_turn_movement",
                                    "movement_turn": "straight",
                                    "name": "Via B [straight]",
                                    "control_state": "unsignalized_multi_arm",
                                    "phase_priority_group": None,
                                    "signal_priority_variant": None,
                                    "movement_resolution_state": "turn_only_fallback",
                                    "junction_phase_provider_available": 0.0,
                                    "movement_phase_timing_available": 0.0,
                                    "movement_phase_mapping_available": 0.0,
                                },
                                "geometry": {"type": "Point", "coordinates": [16.862, 41.122]},
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            matched_rows = [
                {"node_object_id": "m2", "junction_id": "it-bari-signal-93"},
                {"node_object_id": "m2", "junction_id": "it-bari-signal-93"},
                {"node_object_id": "m3", "junction_id": "it-bari-junction-1"},
            ]
            with matched_path.open("w", encoding="utf-8") as handle:
                for row in matched_rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")

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
                        "acquisition_status",
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
                        "acquisition_status": "pending_outreach",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                    }
                )

            delivery_session_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "movement_signal_phase_manifest_path": "data/processed/signal_phase_delivery_sessions/bari_sample/movement_layer/road_movement_objects_signal_phase.manifest.json"
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_coverage_report(
                output_dir=output_dir,
                movement_objects_path=movement_path,
                matched_records_path=matched_path,
                target_request_queue_path=target_queue_path,
                delivery_session_manifest_path=delivery_session_manifest_path,
                top_n=5,
            )

            self.assertEqual(result["stats"]["movement_count"], 3)
            self.assertEqual(result["stats"]["signalized_movement_count"], 2)
            self.assertEqual(result["stats"]["movements_with_provider_data"], 2)
            self.assertEqual(result["stats"]["movements_with_phase_timing"], 1)
            self.assertEqual(result["stats"]["movements_with_phase_mapping"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_count"], 1)
            self.assertEqual(result["stats"]["matched_crash_count"], 3)
            self.assertEqual(result["stats"]["matched_signalized_crash_count"], 2)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_count"], 2)
            self.assertEqual(result["stats"]["target_junction_count"], 1)
            self.assertEqual(result["stats"]["target_junctions_with_phase_timing"], 1)
            self.assertEqual(result["stats"]["uncovered_signalized_hotspot_count"], 1)

            payload = json.loads((output_dir / "signal_phase_coverage.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["matched_crashes_on_provider_movements"], 2)
            self.assertEqual(payload["top_uncovered_signalized_hotspots"][0]["node_object_id"], "m2")
            self.assertEqual(payload["top_uncovered_signalized_hotspots"][0]["is_unresolved_movement"], 1)

            with (output_dir / "target_junction_coverage.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["junction_id"], "it-bari-signal-93")
            self.assertEqual(rows[0]["signalized_movement_count"], "2")
            self.assertEqual(rows[0]["matched_signalized_crash_count"], "2")
            self.assertEqual(rows[0]["movements_with_phase_timing"], "1")
            self.assertEqual(rows[0]["unresolved_signalized_movement_count"], "1")
            self.assertEqual(rows[0]["unresolved_signalized_crash_count"], "2")

            manifest = json.loads((output_dir / "signal_phase_coverage.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "signal_phase_coverage_report")


if __name__ == "__main__":
    unittest.main()
