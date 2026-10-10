from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_source_catalog import build_exposure_source_catalog


class ExposureSourceCatalogTests(unittest.TestCase):
    def test_build_exposure_source_catalog_writes_catalog_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            readiness_report_path = root / "exposure_readiness.json"
            output_dir = root / "exposure_sources"

            readiness_report_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "label": "demo_city",
                                "dataset_path": "data/processed/segments/demo/road_segments_context.geojson",
                                "feature_count": 42,
                                "capabilities": [
                                    {
                                        "code": "motorized_exposure",
                                        "label": "Motor traffic exposure",
                                        "priority": 1,
                                        "status": "proxy_only",
                                        "next_step": "Acquire AADT, traffic counts, or floating-car traffic volume aggregates per segment.",
                                    },
                                    {
                                        "code": "speed_observation",
                                        "label": "Observed speed and variability",
                                        "priority": 1,
                                        "status": "proxy_only",
                                        "next_step": "Replace static speed-limit fields with observed speed distributions or aggregated probe-speed feeds.",
                                    },
                                    {
                                        "code": "vru_exposure",
                                        "label": "Pedestrian and cyclist exposure",
                                        "priority": 1,
                                        "status": "proxy_only",
                                        "next_step": "Add pedestrian and cyclist counters or defensible VRU exposure proxies at crossings and corridors.",
                                    },
                                    {
                                        "code": "road_geometry_design",
                                        "label": "Road geometry and design controls",
                                        "priority": 1,
                                        "status": "available",
                                        "next_step": "Keep extending geometry coverage toward crossings, lighting, signals, and continuity attributes.",
                                    },
                                ],
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_exposure_source_catalog(
                readiness_report_path=readiness_report_path,
                output_dir=output_dir,
            )

            self.assertEqual(payload["exposure_source_catalog_version"], "exposure_source_catalog_v1")
            self.assertEqual(payload["stats"]["dataset_count"], 1)
            self.assertEqual(payload["stats"]["connector_contract_count"], 3)

            catalog_json_path = output_dir / "exposure_source_catalog.json"
            catalog_markdown_path = output_dir / "exposure_source_catalog.md"
            connector_contracts_path = output_dir / "connector_contracts.json"
            manifest_path = output_dir / "exposure_source_catalog.manifest.json"
            self.assertTrue(catalog_json_path.exists())
            self.assertTrue(catalog_markdown_path.exists())
            self.assertTrue(connector_contracts_path.exists())
            self.assertTrue(manifest_path.exists())

            catalog = json.loads(catalog_json_path.read_text(encoding="utf-8"))
            self.assertEqual(catalog["datasets"][0]["label"], "demo_city")
            self.assertEqual(len(catalog["datasets"][0]["priority_connector_backlog"]), 3)
            self.assertEqual(
                catalog["datasets"][0]["priority_connector_backlog"][0]["recommended_contract"],
                "motorized_exposure_connector_v1",
            )

            contracts = json.loads(connector_contracts_path.read_text(encoding="utf-8"))
            self.assertIn("motorized_exposure", contracts)
            self.assertIn("vru_exposure", contracts)

            markdown = catalog_markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Exposure Source Catalog", markdown)
            self.assertIn("motorized_exposure_connector_v1", markdown)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "exposure_source_catalog")
            self.assertEqual(manifest["stats"]["priority_connector_gap_count"], 3)

    def test_build_exposure_source_catalog_marks_contract_ready_proxy_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            readiness_report_path = root / "exposure_readiness.json"
            output_dir = root / "exposure_sources"

            readiness_report_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "label": "bari",
                                "dataset_path": "data/processed/segments/bari_context_v2/road_segments_context.geojson",
                                "feature_count": 100,
                                "capabilities": [
                                    {
                                        "code": "motorized_exposure",
                                        "label": "Motor traffic exposure",
                                        "priority": 1,
                                        "status": "proxy_only",
                                        "connector_contract_state": "contract_ready",
                                        "connector_mapping_stub_count": 1,
                                        "ready_connector_profiles": ["municipal_counter_export"],
                                        "next_step": "Connector contract is ready; ingest an approved provider extract and publish refreshed join/readiness coverage outputs.",
                                    }
                                ],
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            build_exposure_source_catalog(
                readiness_report_path=readiness_report_path,
                output_dir=output_dir,
            )

            catalog = json.loads((output_dir / "exposure_source_catalog.json").read_text(encoding="utf-8"))
            backlog_item = catalog["datasets"][0]["priority_connector_backlog"][0]
            self.assertEqual(backlog_item["current_status"], "proxy_only_contract_ready")
            self.assertEqual(backlog_item["connector_contract_state"], "contract_ready")
            self.assertEqual(backlog_item["connector_mapping_stub_count"], 1)
            self.assertEqual(backlog_item["ready_connector_profiles"], ["municipal_counter_export"])
