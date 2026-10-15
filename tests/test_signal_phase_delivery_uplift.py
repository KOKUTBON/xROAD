from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_delivery_uplift import (
    build_bari_signal_phase_delivery_uplift_report,
)


class SignalPhaseDeliveryUpliftTests(unittest.TestCase):
    def test_build_bari_signal_phase_delivery_uplift_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "uplift"
            baseline_path = root / "baseline.geojson"
            updated_path = root / "updated.geojson"
            matched_path = root / "matched.jsonl"
            target_queue_path = root / "target_request_queue.csv"

            baseline_path.write_text(
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
                                    "junction_phase_provider_available": 0.0,
                                    "movement_phase_timing_available": 0.0,
                                    "movement_phase_mapping_available": 0.0,
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
                                    "junction_phase_provider_available": 0.0,
                                    "movement_phase_timing_available": 0.0,
                                    "movement_phase_mapping_available": 0.0,
                                },
                                "geometry": {"type": "Point", "coordinates": [16.861, 41.121]},
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            updated_path.write_text(
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
                                    "movement_resolution_state": "explicit_target",
                                    "junction_phase_provider_available": 1.0,
                                    "movement_phase_timing_available": 1.0,
                                    "movement_phase_mapping_available": 1.0,
                                },
                                "geometry": {"type": "Point", "coordinates": [16.861, 41.121]},
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            matched_path.write_text(
                "\n".join(
                    [
                        json.dumps({"node_object_id": "m1"}, sort_keys=True),
                        json.dumps({"node_object_id": "m2"}, sort_keys=True),
                    ]
                )
                + "\n",
                encoding="utf-8",
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
                        "acquisition_status": "awaiting_delivery",
                        "required_profiles": "controller_event_log_export | arm_phase_mapping_sheet",
                    }
                )

            result = build_bari_signal_phase_delivery_uplift_report(
                output_dir=output_dir,
                baseline_movement_objects_path=baseline_path,
                updated_movement_objects_path=updated_path,
                matched_records_path=matched_path,
                target_request_queue_path=target_queue_path,
            )

            self.assertEqual(result["stats"]["movements_with_phase_timing_before"], 0)
            self.assertEqual(result["stats"]["movements_with_phase_timing_after"], 2)
            self.assertEqual(result["stats"]["movements_with_phase_mapping_before"], 0)
            self.assertEqual(result["stats"]["movements_with_phase_mapping_after"], 2)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_count_before"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_count_after"], 0)
            self.assertEqual(result["stats"]["improved_target_junction_count"], 1)

            payload = json.loads((output_dir / "signal_phase_delivery_uplift.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["metric_comparison"][1]["before_value"], 0)
            self.assertEqual(payload["metric_comparison"][1]["after_value"], 2)
            self.assertEqual(payload["target_junction_uplift"][0]["movements_with_phase_mapping_delta"], 2)

            with (output_dir / "coverage_metric_comparison.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            metric_lookup = {row["metric_key"]: row for row in rows}
            self.assertEqual(metric_lookup["movements_with_phase_mapping"]["absolute_delta"], "2")

            with (output_dir / "target_junction_uplift.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                target_rows = list(csv.DictReader(handle))
            self.assertEqual(len(target_rows), 1)
            self.assertEqual(target_rows[0]["junction_id"], "it-bari-signal-93")
            self.assertEqual(target_rows[0]["movements_with_phase_timing_delta"], "2")


if __name__ == "__main__":
    unittest.main()
