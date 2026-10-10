from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.node_aggregation import aggregate_node_year_metrics


class NodeAggregationTests(unittest.TestCase):
    def test_aggregate_node_year_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import Point  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            matched_path = root / "matched_node_records.jsonl"
            nodes_path = root / "nodes.geojson"
            output_dir = root / "aggregates"

            with matched_path.open("w", encoding="utf-8") as handle:
                for row in [
                    {
                        "crash_id": "crash-1",
                        "node_object_id": "node-1",
                        "junction_id": "junction-1",
                        "occurred_year": 2025,
                        "severity_level": "injury",
                        "fatalities": 0,
                        "injuries": 1,
                        "node_match_distance_m": 8.0,
                    },
                    {
                        "crash_id": "crash-2",
                        "node_object_id": "node-1",
                        "junction_id": "junction-1",
                        "occurred_year": 2025,
                        "severity_level": "no_injury",
                        "fatalities": 0,
                        "injuries": 0,
                        "node_match_distance_m": 12.0,
                    },
                ]:
                    handle.write(json.dumps(row) + "\n")

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "node-1",
                        "junction_id": "junction-1",
                        "object_type": "traffic_signal",
                        "node_role": "signalized_junction",
                        "name": "VIA A - VIA B",
                        "signal_type": "ITS",
                        "movement_family": "approach",
                        "control_state": "signalized",
                        "movement_resolution_state": "explicit_target",
                        "movement_resolution_method": "single_candidate_turn_match",
                        "movement_target_rank": 1,
                        "movement_target_score": 42.0,
                        "movement_target_heading_delta_deg": 0.0,
                        "movement_target_continuity_flags": "shared_ref | shared_name",
                        "signal_priority_variant": "signal_phase_unknown",
                        "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                        "incoming_arm_id": "seg-1:start",
                        "outgoing_arm_id": "seg-2:end",
                        "segment_id": "seg-1",
                        "nearest_segment_distance_m": 5.0,
                        "geometry": Point(16.87, 41.11),
                    },
                    {
                        "node_object_id": "node-2",
                        "junction_id": "junction-2",
                        "object_type": "traffic_signal",
                        "node_role": "signalized_junction",
                        "name": "VIA C - VIA D",
                        "signal_type": "ITS",
                        "movement_family": "approach",
                        "control_state": "signalized",
                        "movement_resolution_state": "explicit_target",
                        "movement_resolution_method": "single_candidate_turn_match",
                        "movement_target_rank": 1,
                        "movement_target_score": 40.0,
                        "movement_target_heading_delta_deg": 2.0,
                        "movement_target_continuity_flags": "shared_ref",
                        "signal_priority_variant": "signal_phase_unknown",
                        "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                        "incoming_arm_id": "seg-2:start",
                        "outgoing_arm_id": "seg-3:end",
                        "segment_id": "seg-2",
                        "nearest_segment_distance_m": 6.0,
                        "geometry": Point(16.88, 41.12),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(nodes_path, driver="GeoJSON")

            manifest = aggregate_node_year_metrics(matched_path, nodes_path, output_dir)

            self.assertEqual(manifest["stats"]["node_object_count"], 2)
            self.assertEqual(manifest["stats"]["node_year_rows"], 2)
            self.assertEqual(manifest["stats"]["node_year_rows_with_crashes"], 1)
            self.assertEqual(manifest["stats"]["total_crashes"], 2)
            csv_lines = (output_dir / "node_year_metrics.csv").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(csv_lines), 3)
            self.assertIn("movement_family", csv_lines[0])
            self.assertIn("control_state", csv_lines[0])
            self.assertIn("movement_resolution_state", csv_lines[0])
            self.assertIn("movement_resolution_method", csv_lines[0])
            self.assertIn("movement_target_rank", csv_lines[0])
            self.assertIn("movement_target_score", csv_lines[0])
            self.assertIn("signal_priority_variant", csv_lines[0])
            self.assertIn("phase_priority_group", csv_lines[0])
            self.assertIn("approach", csv_lines[1])
            self.assertIn("signalized", csv_lines[1])
            self.assertIn("explicit_target", csv_lines[1])
