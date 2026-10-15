from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.connector_observation_join import apply_connector_observations_to_segments
from road_risk_modeling.exposure_readiness import build_exposure_readiness_report


class ConnectorObservationJoinTests(unittest.TestCase):
    def test_apply_connector_observations_to_segments_joins_matched_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            observation_manifest_path = root / "connector_observations.manifest.json"
            observations_path = root / "connector_observations.jsonl"
            output_dir = root / "joined"

            segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "segment_length_m": 100.0,
                                },
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [1.0, 1.0]],
                                },
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-2",
                                    "segment_length_m": 120.0,
                                },
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[1.0, 1.0], [2.0, 2.0]],
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            observations_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "municipality_label": "bari",
                                "capability_code": "motorized_exposure",
                                "provider_profile_id": "municipal_counter_export",
                                "join_key_type": "segment_id",
                                "join_key_value": "seg-1",
                                "observed_end_utc": "2025-05-01T23:59:59Z",
                                "attributes": {
                                    "vehicle_count": 1000.0,
                                    "sample_size": 1000,
                                    "aadt": 1200.0,
                                },
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "municipality_label": "bari",
                                "capability_code": "speed_observation",
                                "provider_profile_id": "probe_speed_aggregate",
                                "join_key_type": "segment_id",
                                "join_key_value": "seg-1",
                                "observed_end_utc": "2025-05-01T08:59:59Z",
                                "attributes": {
                                    "mean_speed_kph": 43.8,
                                    "p85_speed_kph": 55.7,
                                    "sample_size": 500,
                                },
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "municipality_label": "bari",
                                "capability_code": "vru_exposure",
                                "provider_profile_id": "vru_counter_program",
                                "join_key_type": "segment_id",
                                "join_key_value": "seg-1",
                                "observed_end_utc": "2025-05-01T18:00:00Z",
                                "attributes": {
                                    "pedestrian_count": 250.0,
                                    "cyclist_count": 40.0,
                                    "vru_exposure_index": 0.73,
                                    "crossing_flow": 290.0,
                                },
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "municipality_label": "bari",
                                "capability_code": "speed_observation",
                                "provider_profile_id": "probe_speed_aggregate",
                                "join_key_type": "segment_id",
                                "join_key_value": "missing-seg",
                                "observed_end_utc": "2025-05-01T08:59:59Z",
                                "attributes": {
                                    "mean_speed_kph": 50.0,
                                    "p85_speed_kph": 61.0,
                                    "sample_size": 100,
                                },
                            },
                            sort_keys=True,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            observation_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "observations_path": str(observations_path),
                            "manifest_path": str(observation_manifest_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = apply_connector_observations_to_segments(
                segments_path,
                [observation_manifest_path],
                output_dir,
            )

            self.assertEqual(payload["segment_connector_observations_version"], "segment_connector_observations_v1")
            self.assertEqual(payload["stats"]["matched_observations"], 3)
            self.assertEqual(payload["stats"]["unmatched_observations"], 1)
            self.assertEqual(payload["stats"]["matched_segment_count"], 1)
            self.assertEqual(payload["stats"]["motorized_available_segment_count"], 1)
            self.assertEqual(payload["stats"]["speed_available_segment_count"], 1)
            self.assertEqual(payload["stats"]["vru_available_segment_count"], 1)
            self.assertEqual(payload["stats"]["dual_capability_segment_count"], 1)
            self.assertEqual(payload["stats"]["all_three_capability_segment_count"], 1)
            self.assertEqual(payload["stats"]["motorized_available_segment_share"], 0.5)
            self.assertEqual(payload["stats"]["speed_available_segment_share"], 0.5)
            self.assertEqual(payload["stats"]["vru_available_segment_share"], 0.5)
            self.assertEqual(payload["stats"]["dual_capability_segment_share"], 0.5)
            self.assertEqual(payload["stats"]["all_three_capability_segment_share"], 0.5)

            joined_path = output_dir / "road_segments_connector_observations.geojson"
            manifest_path = output_dir / "road_segments_connector_observations.manifest.json"
            self.assertTrue(joined_path.exists())
            self.assertTrue(manifest_path.exists())

            joined = json.loads(joined_path.read_text(encoding="utf-8"))
            seg1 = next(feature for feature in joined["features"] if feature["properties"]["segment_id"] == "seg-1")
            seg2 = next(feature for feature in joined["features"] if feature["properties"]["segment_id"] == "seg-2")
            self.assertEqual(seg1["properties"]["observed_vehicle_count_mean"], 1000.0)
            self.assertEqual(seg1["properties"]["observed_mean_speed_kph_mean"], 43.8)
            self.assertEqual(seg1["properties"]["observed_connector_capability_count"], 3.0)
            self.assertEqual(seg1["properties"]["aadt"], 1200.0)
            self.assertEqual(seg1["properties"]["traffic_volume"], 1000.0)
            self.assertEqual(seg1["properties"]["traffic_count_daily"], 1000.0)
            self.assertEqual(seg1["properties"]["mean_speed_kph"], 43.8)
            self.assertEqual(seg1["properties"]["p85_speed_kph"], 55.7)
            self.assertEqual(seg1["properties"]["pedestrian_count"], 250.0)
            self.assertEqual(seg1["properties"]["cyclist_count"], 40.0)
            self.assertEqual(seg1["properties"]["vru_exposure_index"], 0.73)
            self.assertEqual(seg1["properties"]["crossing_flow"], 290.0)
            self.assertEqual(seg2["properties"]["observed_connector_capability_count"], 0.0)

            readiness_output = root / "readiness"
            build_exposure_readiness_report(
                datasets=[("bari_connector_pilot", str(joined_path))],
                output_dir=readiness_output,
            )
            readiness_payload = json.loads((readiness_output / "exposure_readiness.json").read_text(encoding="utf-8"))
            capabilities = {
                item["code"]: item
                for item in readiness_payload["datasets"][0]["capabilities"]
            }
            self.assertEqual(capabilities["motorized_exposure"]["status"], "available")
            self.assertEqual(capabilities["speed_observation"]["status"], "available")
            self.assertEqual(capabilities["vru_exposure"]["status"], "available")
            self.assertEqual(capabilities["speed_observation"]["required_feature_share"], 0.5)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "segment_connector_observations")
            self.assertEqual(manifest["stats"]["capability_summaries"]["motorized_exposure"]["matched_segments"], 1)
            self.assertEqual(
                manifest["stats"]["municipality_coverage"]["bari"]["motorized_available_segment_count"],
                1,
            )
            self.assertEqual(
                manifest["stats"]["municipality_coverage"]["bari"]["motorized_available_segment_share"],
                0.5,
            )
            self.assertEqual(
                manifest["stats"]["municipality_coverage"]["bari"]["speed_available_segment_count"],
                1,
            )
            self.assertEqual(
                manifest["stats"]["municipality_coverage"]["bari"]["speed_available_segment_share"],
                0.5,
            )
