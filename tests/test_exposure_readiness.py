from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_readiness import build_exposure_readiness_report


class ExposureReadinessTests(unittest.TestCase):
    def test_build_exposure_readiness_report_classifies_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "planning"
            dataset_path = root / "demo_segments.geojson"
            dataset_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "lanes": "2",
                                    "maxspeed": "50",
                                    "road_class_rank": 4,
                                    "is_intersection_connector": 1,
                                    "segment_length_m": 120.0,
                                    "exposure_proxy_index": 0.8,
                                    "exposure_movement_index": 0.9,
                                    "poi_education_count": 2,
                                },
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [1.0, 1.0]],
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_exposure_readiness_report(
                datasets=[("demo_city", str(dataset_path))],
                output_dir=output_dir,
            )

            self.assertEqual(payload["exposure_readiness_version"], "exposure_readiness_v1")
            self.assertEqual(payload["stats"]["dataset_count"], 1)

            report_json_path = output_dir / "exposure_readiness.json"
            report_markdown_path = output_dir / "exposure_readiness.md"
            manifest_path = output_dir / "exposure_readiness.manifest.json"
            self.assertTrue(report_json_path.exists())
            self.assertTrue(report_markdown_path.exists())
            self.assertTrue(manifest_path.exists())

            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            self.assertEqual(report["datasets"][0]["label"], "demo_city")
            capabilities = {
                item["code"]: item
                for item in report["datasets"][0]["capabilities"]
            }
            self.assertEqual(capabilities["motorized_exposure"]["status"], "proxy_only")
            self.assertEqual(capabilities["motorized_exposure"]["required_feature_share"], 0.0)
            self.assertEqual(capabilities["motorized_exposure"]["proxy_feature_share"], 1.0)
            self.assertEqual(capabilities["speed_observation"]["required_feature_share"], 0.0)
            self.assertEqual(capabilities["speed_observation"]["proxy_feature_share"], 1.0)
            self.assertEqual(capabilities["road_geometry_design"]["status"], "available")
            self.assertEqual(capabilities["weather_visibility"]["status"], "missing")

            markdown = report_markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Exposure Backbone Readiness Report", markdown)
            self.assertIn("Motor traffic exposure", markdown)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "exposure_readiness")
            self.assertEqual(manifest["stats"]["highest_priority_missing_count"], 3)

    def test_build_exposure_readiness_report_marks_contract_ready_when_bari_mappings_are_non_todo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "planning"
            mapping_stub_root = root / "mapping_stubs"
            mapping_stub_root.mkdir(parents=True, exist_ok=True)
            dataset_path = root / "bari_segments.geojson"

            dataset_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "maxspeed": "50",
                                    "exposure_proxy_index": 0.8,
                                },
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [1.0, 1.0]],
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            (mapping_stub_root / "bari_01_motorized_exposure_municipal__municipal_counter_export.json").write_text(
                json.dumps(
                    {
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "counter_record_id",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "required": True,
                            },
                        ],
                        "provider_profile_id": "municipal_counter_export",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_exposure_readiness_report(
                datasets=[("bari", str(dataset_path))],
                output_dir=output_dir,
                mapping_stub_root=mapping_stub_root,
            )

            self.assertEqual(payload["stats"]["dataset_count"], 1)
            report = json.loads((output_dir / "exposure_readiness.json").read_text(encoding="utf-8"))
            capabilities = {
                item["code"]: item
                for item in report["datasets"][0]["capabilities"]
            }
            self.assertEqual(capabilities["motorized_exposure"]["status"], "proxy_only")
            self.assertEqual(capabilities["motorized_exposure"]["connector_contract_state"], "contract_ready")
            self.assertEqual(capabilities["motorized_exposure"]["connector_mapping_stub_count"], 1)
            self.assertEqual(
                capabilities["motorized_exposure"]["ready_connector_profiles"],
                ["municipal_counter_export"],
            )
            self.assertIn("Connector contract is ready", capabilities["motorized_exposure"]["next_step"])

    def test_build_exposure_readiness_report_marks_contract_ready_when_bari_mappings_are_non_todo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "planning"
            mapping_stub_root = root / "mapping_stubs"
            mapping_stub_root.mkdir(parents=True, exist_ok=True)
            dataset_path = root / "bari_segments.geojson"

            dataset_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "maxspeed": "50",
                                    "exposure_proxy_index": 0.8,
                                },
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [1.0, 1.0]],
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            (mapping_stub_root / "bari_01_motorized_exposure_municipal__municipal_counter_export.json").write_text(
                json.dumps(
                    {
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "counter_record_id",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "required": True,
                            },
                        ],
                        "provider_profile_id": "municipal_counter_export",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_exposure_readiness_report(
                datasets=[("bari", str(dataset_path))],
                output_dir=output_dir,
                mapping_stub_root=mapping_stub_root,
            )

            self.assertEqual(payload["stats"]["dataset_count"], 1)
            report = json.loads((output_dir / "exposure_readiness.json").read_text(encoding="utf-8"))
            capabilities = {
                item["code"]: item
                for item in report["datasets"][0]["capabilities"]
            }
            self.assertEqual(capabilities["motorized_exposure"]["status"], "proxy_only")
            self.assertEqual(capabilities["motorized_exposure"]["connector_contract_state"], "contract_ready")
            self.assertEqual(capabilities["motorized_exposure"]["connector_mapping_stub_count"], 1)
            self.assertEqual(
                capabilities["motorized_exposure"]["ready_connector_profiles"],
                ["municipal_counter_export"],
            )
            self.assertIn("Connector contract is ready", capabilities["motorized_exposure"]["next_step"])
