from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from road_risk_modeling.enrichment import (
    apply_exposure_policy_to_segments,
    enrich_segments,
    enrich_segments_with_context,
)


class EnrichmentTests(unittest.TestCase):
    def test_enrich_segments_adds_topology_features(self) -> None:
        try:
            import geopandas as gpd  # type: ignore
            from shapely.geometry import LineString  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            output_dir = root / "enriched"

            segments = gpd.GeoDataFrame(
                [
                    {
                        "segment_id": "seg-1",
                        "u": 1,
                        "v": 2,
                        "highway": "residential",
                        "name": "Via Uno",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.80, 41.10), (16.81, 41.10)]),
                    },
                    {
                        "segment_id": "seg-2",
                        "u": 2,
                        "v": 3,
                        "highway": "residential",
                        "name": "Via Due",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.81, 41.10), (16.82, 41.10)]),
                    },
                    {
                        "segment_id": "seg-3",
                        "u": 2,
                        "v": 4,
                        "highway": "primary",
                        "name": None,
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.81, 41.10), (16.81, 41.11)]),
                    },
                ],
                crs="EPSG:4326",
            )
            segments.to_file(segments_path, driver="GeoJSON")

            manifest = enrich_segments(segments_path, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["segment_count"], 3)
            enriched_path = output_dir / "road_segments_enriched.geojson"
            self.assertTrue(enriched_path.exists())

            enriched = gpd.read_file(enriched_path).set_index("segment_id")
            self.assertEqual(int(enriched.loc["seg-1", "node_degree_u"]), 1)
            self.assertEqual(int(enriched.loc["seg-1", "node_degree_v"]), 3)
            self.assertEqual(int(enriched.loc["seg-1", "is_dead_end"]), 1)
            self.assertEqual(int(enriched.loc["seg-3", "is_intersection_connector"]), 1)
            self.assertGreaterEqual(float(enriched.loc["seg-1", "sinuosity"]), 1.0)
            self.assertIn(enriched.loc["seg-1", "bearing_bin"], {"E", "W"})

    def test_enrich_segments_with_context_adds_poi_counts_and_exposure_policy(self) -> None:
        try:
            import geopandas as gpd  # type: ignore
            from shapely.geometry import LineString, Point, Polygon  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            boundary_path = root / "boundary.geojson"
            output_dir = root / "context"

            segments = gpd.GeoDataFrame(
                [
                    {
                        "segment_id": "seg-1",
                        "u": 1,
                        "v": 2,
                        "highway": "residential",
                        "lanes": "1",
                        "maxspeed": "30",
                        "node_degree_max": 3,
                        "road_class_rank": 2,
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.80, 41.10), (16.801, 41.10)]),
                    },
                    {
                        "segment_id": "seg-2",
                        "u": 2,
                        "v": 3,
                        "highway": "primary",
                        "lanes": "2",
                        "maxspeed": "70",
                        "node_degree_max": 4,
                        "road_class_rank": 6,
                        "segment_length_m": 150.0,
                        "geometry": LineString([(16.805, 41.10), (16.806, 41.10)]),
                    },
                ],
                crs="EPSG:4326",
            )
            boundary = gpd.GeoDataFrame(
                [{"geometry": Polygon([(16.79, 41.09), (16.81, 41.09), (16.81, 41.11), (16.79, 41.11)])}],
                crs="EPSG:4326",
            )
            poi_features = gpd.GeoDataFrame(
                [
                    {"amenity": "school", "shop": None, "public_transport": None, "highway": None, "railway": None, "tourism": None, "leisure": None, "geometry": Point(16.8005, 41.1001)},
                    {"amenity": "hospital", "shop": None, "public_transport": None, "highway": None, "railway": None, "tourism": None, "leisure": None, "landuse": "residential", "building": "apartments", "office": None, "geometry": Point(16.8006, 41.1002)},
                    {"amenity": None, "shop": "supermarket", "public_transport": None, "highway": None, "railway": None, "tourism": None, "leisure": None, "landuse": "commercial", "building": "retail", "office": None, "geometry": Point(16.8055, 41.1001)},
                    {"amenity": None, "shop": None, "public_transport": "platform", "highway": None, "railway": None, "tourism": None, "leisure": None, "landuse": None, "building": None, "office": "company", "geometry": Point(16.8057, 41.1002)},
                ],
                crs="EPSG:4326",
            )

            segments.to_file(segments_path, driver="GeoJSON")
            boundary.to_file(boundary_path, driver="GeoJSON")

            with patch("road_risk_modeling.enrichment._fetch_osm_context_features", return_value=poi_features):
                manifest = enrich_segments_with_context(
                    segments_path,
                    boundary_path,
                    output_dir=output_dir,
                    poi_buffer_m=150.0,
                )

            self.assertEqual(manifest["stats"]["segment_count"], 2)
            context_path = output_dir / "road_segments_context.geojson"
            self.assertTrue(context_path.exists())

            context = gpd.read_file(context_path).set_index("segment_id")
            self.assertGreaterEqual(int(context.loc["seg-1", "poi_any_count"]), 2)
            self.assertGreaterEqual(int(context.loc["seg-1", "poi_education_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-1", "poi_healthcare_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-2", "poi_retail_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-2", "poi_transit_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-1", "building_any_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-1", "landuse_residential_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-2", "building_commercial_count"]), 1)
            self.assertGreaterEqual(int(context.loc["seg-2", "landuse_commercial_count"]), 1)
            self.assertGreater(float(context.loc["seg-1", "exposure_proxy_index"]), 0.0)
            self.assertEqual(
                context.loc["seg-1", "exposure_policy_version"],
                "segment_exposure_v2_static_context_built_env",
            )
            self.assertGreater(float(context.loc["seg-1", "exposure_policy_index"]), 0.0)
            self.assertGreater(float(context.loc["seg-1", "exposure_movement_index"]), 0.0)
            self.assertGreater(float(context.loc["seg-1", "exposure_built_environment_index"]), 0.0)
            self.assertGreater(float(context.loc["seg-1", "exposure_population_proxy_index"]), 0.0)
            self.assertGreaterEqual(float(context.loc["seg-1", "exposure_data_completeness"]), 0.0)
            self.assertGreater(float(context.loc["seg-2", "exposure_proxy_index"]), float(context.loc["seg-1", "exposure_proxy_index"]))

    def test_apply_exposure_policy_to_segments_writes_policy_output(self) -> None:
        try:
            import geopandas as gpd  # type: ignore
            from shapely.geometry import LineString  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            output_dir = root / "policy"

            segments = gpd.GeoDataFrame(
                [
                    {
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "lanes": "2",
                        "maxspeed": "70",
                        "width": "7",
                        "segment_length_m": 120.0,
                        "node_degree_max": 4,
                        "is_dead_end": 0,
                        "is_intersection_connector": 1,
                        "segment_name_present": 1,
                        "poi_any_count": 3,
                        "poi_transit_count": 1,
                        "building_any_count": 2,
                        "building_residential_count": 1,
                        "building_commercial_count": 1,
                        "landuse_residential_count": 1,
                        "landuse_commercial_count": 1,
                        "geometry": LineString([(16.80, 41.10), (16.81, 41.10)]),
                    }
                ],
                crs="EPSG:4326",
            )
            segments.to_file(segments_path, driver="GeoJSON")

            manifest = apply_exposure_policy_to_segments(segments_path, output_dir=output_dir)

            self.assertEqual(manifest["policy"]["exposure_policy_version"], "segment_exposure_v2_static_context_built_env")
            exposure_path = output_dir / "road_segments_exposure.geojson"
            self.assertTrue(exposure_path.exists())

            enriched = gpd.read_file(exposure_path)
            self.assertGreater(float(enriched.loc[0, "exposure_policy_index"]), 0.0)
            self.assertGreater(float(enriched.loc[0, "exposure_activity_index"]), 1.0)
            self.assertGreater(float(enriched.loc[0, "exposure_built_environment_index"]), 1.0)
            self.assertGreater(float(enriched.loc[0, "exposure_population_proxy_index"]), 1.0)
