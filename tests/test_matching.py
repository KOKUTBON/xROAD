from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.matching import match_canonical_records_to_segments


class MatchingTests(unittest.TestCase):
    def test_match_canonical_records_to_segments(self) -> None:
        try:
            import geopandas as gpd  # type: ignore
            from shapely.geometry import LineString, Polygon  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "canonical.jsonl"
            segments_path = root / "segments.geojson"
            boundary_path = root / "boundary.geojson"
            output_dir = root / "matches"

            records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "x",
                                "source_unique_key": "2020:1",
                                "latitude": 41.111,
                                "longitude": 16.871,
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "y",
                                "source_unique_key": "2020:2",
                                "latitude": 41.5,
                                "longitude": 17.5,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            segments = gpd.GeoDataFrame(
                [{"segment_id": "seg-1", "geometry": LineString([(16.87, 41.11), (16.872, 41.112)])}],
                crs="EPSG:4326",
            )
            segments.to_file(segments_path, driver="GeoJSON")
            boundary = gpd.GeoDataFrame(
                [{"geometry": Polygon([(16.869, 41.109), (16.873, 41.109), (16.873, 41.113), (16.869, 41.113)])}],
                crs="EPSG:4326",
            )
            boundary.to_file(boundary_path, driver="GeoJSON")

            manifest = match_canonical_records_to_segments(
                records_path,
                segments_path,
                output_dir=output_dir,
                max_distance_m=100.0,
                boundary_path=boundary_path,
            )

            self.assertEqual(manifest["stats"]["input_records_with_coordinates"], 2)
            self.assertEqual(manifest["stats"]["records_after_boundary_filter"], 1)
            self.assertEqual(manifest["stats"]["records_removed_by_boundary_filter"], 1)
            self.assertEqual(manifest["stats"]["matched_records"], 1)
            self.assertEqual(manifest["stats"]["unmatched_records"], 0)
            self.assertEqual(
                manifest["stats"]["matched_records"] + manifest["stats"]["unmatched_records"],
                manifest["stats"]["records_after_boundary_filter"],
            )
