from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

import pandas as pd

from road_risk_modeling.segmentation import (
    compare_boundaries,
    extract_boundary_from_place,
    extract_segments_from_boundary,
    extract_segments_from_records_bbox,
    load_geospatial_stack,
)


class SegmentationTests(unittest.TestCase):
    def test_load_geospatial_stack_reports_missing_dependency(self) -> None:
        with patch("builtins.__import__", side_effect=ModuleNotFoundError("No module named 'osmnx'")):
            with self.assertRaises(RuntimeError) as context:
                load_geospatial_stack()

        self.assertIn("OSMnx is not installed", str(context.exception))

    def test_extract_segments_from_records_bbox_writes_manifest(self) -> None:
        try:
            import geopandas as gpd
            from shapely.geometry import LineString
        except ModuleNotFoundError:
            self.skipTest("Geospatial stack not installed")

        class FakeOx:
            last_bbox = None

            @staticmethod
            def graph_from_bbox(bbox, network_type="drive"):
                FakeOx.last_bbox = bbox
                return {"bbox": bbox, "network_type": network_type}

            @staticmethod
            def graph_to_gdfs(_graph, nodes=False):
                if nodes:
                    raise AssertionError("Expected edge GeoDataFrame extraction.")
                return gpd.GeoDataFrame(
                    pd.DataFrame(
                        {
                            "u": [1],
                            "v": [2],
                            "key": [0],
                            "highway": ["residential"],
                        }
                    ),
                    geometry=[LineString([(16.80, 41.10), (16.81, 41.11)])],
                    crs="EPSG:4326",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "records.jsonl"
            output_dir = root / "segments"
            records_path.write_text(
                '{"crash_id":"a","latitude":41.10,"longitude":16.80}\n'
                '{"crash_id":"b","latitude":41.11,"longitude":16.81}\n',
                encoding="utf-8",
            )

            with patch(
                "road_risk_modeling.segmentation.load_geospatial_stack",
                return_value=(FakeOx(), gpd, __import__("shapely.geometry", fromlist=["box"]).box),
            ):
                manifest = extract_segments_from_records_bbox(
                    records_path,
                    output_dir=output_dir,
                    network_type="drive",
                    pad_m=500.0,
                )

            self.assertEqual(manifest["inputs"]["boundary_source"], "records_bbox")
            self.assertEqual(manifest["stats"]["input_records_with_coordinates"], 2)
            self.assertIsNotNone(FakeOx.last_bbox)
            west, south, east, north = FakeOx.last_bbox
            self.assertLess(west, east)
            self.assertLess(south, north)
            self.assertTrue((output_dir / "road_segments.geojson").exists())
            self.assertTrue((output_dir / "boundary.geojson").exists())

    def test_extract_boundary_from_place_writes_manifest(self) -> None:
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon
        except ModuleNotFoundError:
            self.skipTest("Geospatial stack not installed")

        class FakeOx:
            @staticmethod
            def geocode_to_gdf(_place_query):
                return gpd.GeoDataFrame(
                    pd.DataFrame({"display_name": ["Example City"]}),
                    geometry=[
                        Polygon(
                            [
                                (16.8, 41.0),
                                (16.9, 41.0),
                                (16.9, 41.1),
                                (16.8, 41.1),
                            ]
                        )
                    ],
                    crs="EPSG:4326",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "boundary"
            with patch(
                "road_risk_modeling.segmentation.load_geospatial_stack",
                return_value=(FakeOx(), gpd, __import__("shapely.geometry", fromlist=["box"]).box),
            ):
                manifest = extract_boundary_from_place("Example City", output_dir=output_dir)

            self.assertEqual(manifest["inputs"]["boundary_source"], "place_query")
            self.assertGreater(manifest["stats"]["area_km2"], 0.0)
            self.assertTrue((output_dir / "boundary.geojson").exists())
            self.assertTrue((output_dir / "boundary.manifest.json").exists())

    def test_extract_segments_from_boundary_writes_manifest(self) -> None:
        try:
            import geopandas as gpd
            from shapely.geometry import LineString, Polygon
        except ModuleNotFoundError:
            self.skipTest("Geospatial stack not installed")

        class FakeOx:
            last_polygon = None

            @staticmethod
            def graph_from_polygon(polygon, network_type="drive"):
                FakeOx.last_polygon = polygon
                return {"polygon": polygon, "network_type": network_type}

            @staticmethod
            def graph_to_gdfs(_graph, nodes=False):
                if nodes:
                    raise AssertionError("Expected edge GeoDataFrame extraction.")
                return gpd.GeoDataFrame(
                    pd.DataFrame(
                        {
                            "u": [1],
                            "v": [2],
                            "key": [0],
                            "highway": ["residential"],
                        }
                    ),
                    geometry=[LineString([(16.80, 41.10), (16.81, 41.11)])],
                    crs="EPSG:4326",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            boundary_path = root / "boundary.geojson"
            output_dir = root / "segments"
            boundary = gpd.GeoDataFrame(
                pd.DataFrame({"name": ["boundary"]}),
                geometry=[
                    Polygon(
                        [
                            (16.8, 41.0),
                            (16.9, 41.0),
                            (16.9, 41.1),
                            (16.8, 41.1),
                        ]
                    )
                ],
                crs="EPSG:4326",
            )
            boundary.to_file(boundary_path, driver="GeoJSON")

            with patch(
                "road_risk_modeling.segmentation.load_geospatial_stack",
                return_value=(FakeOx(), gpd, __import__("shapely.geometry", fromlist=["box"]).box),
            ):
                manifest = extract_segments_from_boundary(
                    boundary_path,
                    output_dir=output_dir,
                    network_type="drive",
                )

            self.assertEqual(manifest["inputs"]["boundary_source"], "boundary_geojson")
            self.assertGreater(manifest["stats"]["boundary_area_km2"], 0.0)
            self.assertIsNotNone(FakeOx.last_polygon)
            self.assertTrue((output_dir / "road_segments.geojson").exists())
            self.assertTrue((output_dir / "boundary.geojson").exists())

    def test_compare_boundaries_reports_overlap(self) -> None:
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon
        except ModuleNotFoundError:
            self.skipTest("Geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference_path = root / "reference.geojson"
            candidate_path = root / "candidate.geojson"
            output_path = root / "report.json"

            reference = gpd.GeoDataFrame(
                pd.DataFrame({"name": ["reference"]}),
                geometry=[
                    Polygon(
                        [
                            (16.8, 41.0),
                            (16.9, 41.0),
                            (16.9, 41.1),
                            (16.8, 41.1),
                        ]
                    )
                ],
                crs="EPSG:4326",
            )
            candidate = gpd.GeoDataFrame(
                pd.DataFrame({"name": ["candidate"]}),
                geometry=[
                    Polygon(
                        [
                            (16.85, 41.02),
                            (16.89, 41.02),
                            (16.89, 41.08),
                            (16.85, 41.08),
                        ]
                    )
                ],
                crs="EPSG:4326",
            )
            reference.to_file(reference_path, driver="GeoJSON")
            candidate.to_file(candidate_path, driver="GeoJSON")

            report = compare_boundaries(reference_path, candidate_path, output_path=output_path)

            self.assertGreater(report["stats"]["intersection_over_union"], 0.0)
            self.assertGreater(report["stats"]["candidate_within_reference_ratio"], 0.99)
            self.assertTrue(output_path.exists())
