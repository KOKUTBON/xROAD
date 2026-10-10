from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.aggregation import aggregate_segment_year_metrics


class AggregationTests(unittest.TestCase):
    def test_aggregate_segment_year_metrics(self) -> None:
        try:
            import geopandas as gpd  # type: ignore
            from shapely.geometry import LineString  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched_path = root / "matched.jsonl"
            segments_path = root / "segments.geojson"
            output_dir = root / "aggregates"

            matched_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "segment_id": "seg-1",
                                "occurred_year": 2020,
                                "severity_level": "injury",
                                "fatalities": 0,
                                "injuries": 1,
                                "match_distance_m": 2.0,
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "b",
                                "segment_id": "seg-1",
                                "occurred_year": 2020,
                                "severity_level": "fatal",
                                "fatalities": 1,
                                "injuries": 0,
                                "match_distance_m": 4.0,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            segments = gpd.GeoDataFrame(
                [
                    {"segment_id": "seg-1", "segment_length_m": 100.0, "geometry": LineString([(16.87, 41.11), (16.872, 41.112)])},
                    {"segment_id": "seg-2", "segment_length_m": 200.0, "geometry": LineString([(16.88, 41.12), (16.882, 41.122)])},
                ],
                crs="EPSG:4326",
            )
            segments.to_file(segments_path, driver="GeoJSON")

            manifest = aggregate_segment_year_metrics(matched_path, segments_path, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["segment_count"], 2)
            self.assertEqual(manifest["stats"]["segment_year_rows"], 2)
            self.assertEqual(manifest["stats"]["segment_year_rows_with_crashes"], 1)
            self.assertEqual(manifest["stats"]["segment_year_rows_without_crashes"], 1)
            self.assertEqual(manifest["stats"]["total_crashes"], 2)
