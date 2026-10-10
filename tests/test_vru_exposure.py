from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.vru_exposure import build_vru_exposure_bundle


class VruExposureTests(unittest.TestCase):
    def test_build_vru_exposure_bundle_writes_segment_and_crossing_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            output_dir = root / "vru_exposure"
            prediction_store_dir = root / "prediction_store" / "demo_bari_run"
            prediction_store_dir.mkdir(parents=True, exist_ok=True)

            analyst_csv_path = prediction_store_dir / "segment_scores_analyst.csv"
            with analyst_csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "segment_score_id",
                        "segment_id",
                        "name",
                        "highway",
                        "road_class_rank",
                        "maxspeed",
                        "lanes",
                        "length",
                        "segment_length_m",
                        "public_score_band",
                        "public_score_index",
                        "predicted_crash_count",
                        "observed_crash_count",
                        "score_rank_desc",
                        "poi_education_count",
                        "poi_retail_count",
                        "poi_transit_count",
                        "poi_healthcare_count",
                        "poi_hospitality_count",
                        "poi_leisure_count",
                        "poi_any_count",
                        "building_residential_count",
                        "building_commercial_count",
                        "landuse_residential_count",
                        "landuse_commercial_count",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-1",
                            "segment_id": "drive:1:2:0",
                            "name": "['Corso Demo']",
                            "highway": "['secondary']",
                            "road_class_rank": "5",
                            "maxspeed": "['50']",
                            "lanes": "['2']",
                            "length": "120",
                            "segment_length_m": "120",
                            "public_score_band": "very_high",
                            "public_score_index": "96",
                            "predicted_crash_count": "3.4",
                            "observed_crash_count": "4",
                            "score_rank_desc": "1",
                            "poi_education_count": "2",
                            "poi_retail_count": "1",
                            "poi_transit_count": "1",
                            "poi_healthcare_count": "0",
                            "poi_hospitality_count": "0",
                            "poi_leisure_count": "0",
                            "poi_any_count": "5",
                            "building_residential_count": "2",
                            "building_commercial_count": "1",
                            "landuse_residential_count": "1",
                            "landuse_commercial_count": "1",
                        },
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-2",
                            "segment_id": "drive:2:3:0",
                            "name": "['Corso Demo']",
                            "highway": "['secondary']",
                            "road_class_rank": "5",
                            "maxspeed": "['60']",
                            "lanes": "['2']",
                            "length": "140",
                            "segment_length_m": "140",
                            "public_score_band": "high",
                            "public_score_index": "90",
                            "predicted_crash_count": "2.8",
                            "observed_crash_count": "3",
                            "score_rank_desc": "2",
                            "poi_education_count": "0",
                            "poi_retail_count": "3",
                            "poi_transit_count": "2",
                            "poi_healthcare_count": "1",
                            "poi_hospitality_count": "1",
                            "poi_leisure_count": "0",
                            "poi_any_count": "7",
                            "building_residential_count": "1",
                            "building_commercial_count": "2",
                            "landuse_residential_count": "0",
                            "landuse_commercial_count": "2",
                        },
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-3",
                            "segment_id": "drive:3:4:0",
                            "name": "['Corso Demo']",
                            "highway": "['secondary']",
                            "road_class_rank": "5",
                            "maxspeed": "['50']",
                            "lanes": "['3']",
                            "length": "160",
                            "segment_length_m": "160",
                            "public_score_band": "high",
                            "public_score_index": "88",
                            "predicted_crash_count": "2.5",
                            "observed_crash_count": "2",
                            "score_rank_desc": "3",
                            "poi_education_count": "0",
                            "poi_retail_count": "1",
                            "poi_transit_count": "2",
                            "poi_healthcare_count": "1",
                            "poi_hospitality_count": "0",
                            "poi_leisure_count": "1",
                            "poi_any_count": "5",
                            "building_residential_count": "1",
                            "building_commercial_count": "1",
                            "landuse_residential_count": "0",
                            "landuse_commercial_count": "1",
                        },
                    ]
                )

            analyst_geojson_path = prediction_store_dir / "segment_scores_analyst.geojson"
            analyst_geojson_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0, 0], [1, 0]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-1",
                                    "segment_id": "drive:1:2:0",
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[1, 0], [2, 0]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-2",
                                    "segment_id": "drive:2:3:0",
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[2, 0], [3, 0]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-3",
                                    "segment_id": "drive:3:4:0",
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            segment_manifest_path = prediction_store_dir / "segment_scores.manifest.json"
            segment_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "analyst_csv_path": str(analyst_csv_path),
                            "analyst_geojson_path": str(analyst_geojson_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            movement_objects_path = root / "road_movement_objects.geojson"
            movement_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [0, 0]},
                                "properties": {
                                    "node_object_id": "crossing-1",
                                    "junction_id": "crossing-1",
                                    "movement_role": "pedestrian_crossing",
                                    "name": "Crossing Demo 1",
                                    "control_state": "uncontrolled",
                                    "crossing_protection_state": "uncontrolled",
                                    "priority_rule": "driver_priority_or_ambiguous",
                                    "phase_priority_group": "uncontrolled_crossing_gap_acceptance",
                                    "segment_id": "drive:1:2:0",
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [1, 0]},
                                "properties": {
                                    "node_object_id": "crossing-2",
                                    "junction_id": "crossing-2",
                                    "movement_role": "pedestrian_crossing",
                                    "name": "Crossing Demo 2",
                                    "control_state": "signalized",
                                    "crossing_protection_state": "signalized",
                                    "priority_rule": "controlled",
                                    "phase_priority_group": "signalized_pedestrian_stage",
                                    "segment_id": "drive:2:3:0",
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            dashboard_summary_path.write_text(
                json.dumps(
                    {
                        "published_runs": [
                            {
                                "city_key": "bari",
                                "display_name": "Demo Bari",
                                "prediction_run_label": "demo_bari_run",
                                "segment_scores": {
                                    "manifest_path": str(segment_manifest_path),
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_vru_exposure_bundle(
                dashboard_summary_path=dashboard_summary_path,
                output_dir=output_dir,
                prediction_run_labels=["demo_bari_run"],
                movement_objects_path=movement_objects_path,
            )

            self.assertEqual(payload["vru_exposure_bundle_version"], "vru_exposure_bundle_v1")
            self.assertEqual(payload["bundle_count"], 1)

            bundle_dir = output_dir / "demo_bari_run"
            bundle_path = bundle_dir / "vru_exposure_bundle.json"
            markdown_path = bundle_dir / "vru_exposure_bundle.md"
            segment_geojson_path = bundle_dir / "segment_vru_exposure.geojson"
            crossing_geojson_path = bundle_dir / "crossing_vru_exposure.geojson"
            corridor_csv_path = bundle_dir / "corridor_vru_exposure.csv"
            manifest_path = bundle_dir / "vru_exposure_bundle.manifest.json"
            self.assertTrue(bundle_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(segment_geojson_path.exists())
            self.assertTrue(crossing_geojson_path.exists())
            self.assertTrue(corridor_csv_path.exists())
            self.assertTrue(manifest_path.exists())

            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle["layer_status"], "proxy_backed")
            self.assertEqual(bundle["stats"]["segment_feature_count"], 3)
            self.assertEqual(bundle["stats"]["crossing_feature_count"], 2)
            self.assertEqual(bundle["planning_summary"]["top_crossing_candidate"]["crossing_name"], "Crossing Demo 1")
            self.assertEqual(bundle["planning_summary"]["top_walkability_corridor"]["corridor_label"], "Corso Demo")

            segment_geojson = json.loads(segment_geojson_path.read_text(encoding="utf-8"))
            self.assertEqual(segment_geojson["type"], "FeatureCollection")
            first_segment = segment_geojson["features"][0]["properties"]
            self.assertEqual(first_segment["vru_exposure_layer_kind"], "segment")
            self.assertEqual(first_segment["vru_exposure_source"], "proxy_backed")
            self.assertIn("pedestrian_priority_score", first_segment)

            crossing_geojson = json.loads(crossing_geojson_path.read_text(encoding="utf-8"))
            self.assertEqual(crossing_geojson["type"], "FeatureCollection")
            first_crossing = crossing_geojson["features"][0]["properties"]
            self.assertEqual(first_crossing["vru_exposure_layer_kind"], "crossing")
            self.assertIn("pedestrian_crossing_priority_score", first_crossing)

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Demo Bari VRU Exposure Layer", markdown)
            self.assertIn("proxy-backed VRU exposure layers", markdown)
