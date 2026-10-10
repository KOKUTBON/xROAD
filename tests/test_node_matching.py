from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.node_matching import match_canonical_records_to_node_objects


class NodeMatchingTests(unittest.TestCase):
    def test_match_canonical_records_to_node_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import Point  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            records_path = root / "records.jsonl"
            nodes_path = root / "nodes.geojson"
            output_dir = root / "matches"

            with records_path.open("w", encoding="utf-8") as handle:
                for row in [
                    {
                        "crash_id": "crash-1",
                        "occurred_year": 2025,
                        "severity_level": "injury",
                        "fatalities": 0,
                        "injuries": 1,
                        "latitude": 41.11001,
                        "longitude": 16.87001,
                    },
                    {
                        "crash_id": "crash-2",
                        "occurred_year": 2025,
                        "severity_level": "no_injury",
                        "fatalities": 0,
                        "injuries": 0,
                        "latitude": 41.15,
                        "longitude": 16.95,
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
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(nodes_path, driver="GeoJSON")

            manifest = match_canonical_records_to_node_objects(
                records_path,
                nodes_path,
                output_dir,
                max_distance_m=35.0,
            )

            self.assertEqual(manifest["stats"]["matched_records"], 1)
            self.assertEqual(manifest["stats"]["unmatched_records"], 1)
            matched_lines = (output_dir / "matched_node_records.jsonl").read_text(encoding="utf-8").strip().splitlines()
            matched_record = json.loads(matched_lines[0])
            self.assertEqual(matched_record["node_object_id"], "node-1")
            self.assertEqual(matched_record["junction_id"], "junction-1")
            self.assertEqual(matched_record["movement_family"], "approach")
            self.assertEqual(matched_record["control_state"], "signalized")
            self.assertEqual(matched_record["movement_resolution_state"], "explicit_target")
            self.assertEqual(matched_record["movement_resolution_method"], "single_candidate_turn_match")
            self.assertEqual(matched_record["movement_target_rank"], 1)
            self.assertEqual(matched_record["movement_target_score"], 42.0)
            self.assertEqual(matched_record["movement_target_heading_delta_deg"], 0.0)
            self.assertEqual(matched_record["signal_priority_variant"], "signal_phase_unknown")
            self.assertEqual(matched_record["phase_priority_group"], "signalized_aligned_turn_phase_unknown")
            self.assertEqual(matched_record["incoming_arm_id"], "seg-1:start")
            self.assertEqual(matched_record["outgoing_arm_id"], "seg-2:end")
