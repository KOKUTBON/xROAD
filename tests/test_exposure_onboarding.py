from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_onboarding import build_exposure_onboarding_plan


class ExposureOnboardingPlanTests(unittest.TestCase):
    def test_build_exposure_onboarding_plan_writes_plan_and_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            output_dir = root / "exposure_onboarding"

            source_catalog_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "label": "demo_city",
                                "dataset_path": "data/processed/segments/demo/road_segments_context.geojson",
                                "road_owner_scopes": ["municipal"],
                                "priority_connector_backlog": [
                                    {
                                        "capability_code": "motorized_exposure",
                                        "capability_label": "Motor traffic exposure",
                                        "priority": 1,
                                        "current_status": "proxy_only",
                                        "recommended_contract": "motorized_exposure_connector_v1",
                                        "target_objects": ["segment", "junction"],
                                        "preferred_time_grain": "daily_or_hourly_aggregate",
                                        "horizon_alignment": ["D6-14", "PHOEBE"],
                                        "next_action": "Acquire AADT or floating-car volume aggregates per segment.",
                                    },
                                    {
                                        "capability_code": "speed_observation",
                                        "capability_label": "Observed speed and variability",
                                        "priority": 1,
                                        "current_status": "proxy_only",
                                        "recommended_contract": "observed_speed_connector_v1",
                                        "target_objects": ["segment", "junction_approach"],
                                        "preferred_time_grain": "hourly_or_15min_aggregate",
                                        "horizon_alignment": ["D6-14", "iDriving"],
                                        "next_action": "Acquire aggregated probe-speed or counter outputs.",
                                    },
                                    {
                                        "capability_code": "vru_exposure",
                                        "capability_label": "Pedestrian and cyclist exposure",
                                        "priority": 1,
                                        "current_status": "proxy_only",
                                        "recommended_contract": "vru_exposure_connector_v1",
                                        "target_objects": ["crossing", "segment", "junction"],
                                        "preferred_time_grain": "daily_or_hourly_aggregate",
                                        "horizon_alignment": ["D6-13", "SOTERIA"],
                                        "next_action": "Acquire counts at crossings and school corridors.",
                                    },
                                ],
                            }
                        ],
                        "owner_profiles": [
                            {
                                "scope": "municipal",
                                "description": "Municipal operators.",
                                "likely_partners": ["municipal mobility department", "local police"],
                            }
                        ],
                        "connector_contracts": {
                            "motorized_exposure": {
                                "governance_requirements": ["provider_license_registered"],
                                "quality_checks": ["non_negative_vehicle_count"],
                            },
                            "speed_observation": {
                                "governance_requirements": ["retention_policy_defined"],
                                "quality_checks": ["p85_not_below_mean"],
                            },
                            "vru_exposure": {
                                "governance_requirements": ["privacy_review_for_mobile_or_video_sources"],
                                "quality_checks": ["count_method_documented"],
                            },
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_exposure_onboarding_plan(
                source_catalog_path=source_catalog_path,
                output_dir=output_dir,
            )

            self.assertEqual(payload["exposure_onboarding_plan_version"], "exposure_onboarding_plan_v1")
            self.assertEqual(payload["stats"]["dataset_count"], 1)
            self.assertEqual(payload["stats"]["work_item_count"], 3)
            self.assertEqual(payload["stats"]["active_phase_count"], 2)

            plan_json_path = output_dir / "exposure_onboarding_plan.json"
            plan_markdown_path = output_dir / "exposure_onboarding_plan.md"
            matrix_csv_path = output_dir / "connector_onboarding_matrix.csv"
            manifest_path = output_dir / "exposure_onboarding_plan.manifest.json"
            self.assertTrue(plan_json_path.exists())
            self.assertTrue(plan_markdown_path.exists())
            self.assertTrue(matrix_csv_path.exists())
            self.assertTrue(manifest_path.exists())

            plan = json.loads(plan_json_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["municipality_plans"][0]["label"], "demo_city")
            first_work_item = plan["municipality_plans"][0]["work_items"][0]
            self.assertEqual(first_work_item["capability_code"], "motorized_exposure")
            self.assertEqual(first_work_item["phase_code"], "phase_1_foundational_flow_and_speed")
            self.assertIn("provider_license_registered", first_work_item["governance_gates"])

            markdown = plan_markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Exposure Connector Onboarding Plan", markdown)
            self.assertIn("Phase 1 - Foundational flow and speed coverage", markdown)

            with matrix_csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["municipality_label"], "demo_city")
            self.assertEqual(rows[0]["capability_code"], "motorized_exposure")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "exposure_onboarding_plan")
            self.assertEqual(manifest["stats"]["work_item_count"], 3)

    def test_build_exposure_onboarding_plan_keeps_connector_contract_state_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            output_dir = root / "exposure_onboarding"

            source_catalog_path.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "label": "bari",
                                "dataset_path": "data/processed/segments/bari_context_v2/road_segments_context.geojson",
                                "road_owner_scopes": ["municipal"],
                                "priority_connector_backlog": [
                                    {
                                        "capability_code": "motorized_exposure",
                                        "capability_label": "Motor traffic exposure",
                                        "priority": 1,
                                        "current_status": "proxy_only_contract_ready",
                                        "connector_contract_state": "contract_ready",
                                        "connector_mapping_stub_count": 1,
                                        "ready_connector_profiles": ["municipal_counter_export"],
                                        "recommended_contract": "motorized_exposure_connector_v1",
                                        "target_objects": ["segment", "junction"],
                                        "preferred_time_grain": "daily_or_hourly_aggregate",
                                        "horizon_alignment": ["D6-14", "PHOEBE"],
                                        "next_action": "Connector contract is ready; ingest approved extracts.",
                                    }
                                ],
                            }
                        ],
                        "owner_profiles": [
                            {
                                "scope": "municipal",
                                "description": "Municipal operators.",
                                "likely_partners": ["municipal mobility department"],
                            }
                        ],
                        "connector_contracts": {
                            "motorized_exposure": {
                                "governance_requirements": ["provider_license_registered"],
                                "quality_checks": ["non_negative_vehicle_count"],
                            }
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            build_exposure_onboarding_plan(
                source_catalog_path=source_catalog_path,
                output_dir=output_dir,
            )

            plan = json.loads((output_dir / "exposure_onboarding_plan.json").read_text(encoding="utf-8"))
            work_item = plan["municipality_plans"][0]["work_items"][0]
            self.assertEqual(work_item["connector_contract_state"], "contract_ready")
            self.assertEqual(work_item["connector_mapping_stub_count"], 1)
            self.assertEqual(work_item["ready_connector_profiles"], ["municipal_counter_export"])

            with (output_dir / "connector_onboarding_matrix.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["connector_contract_state"], "contract_ready")
            self.assertEqual(rows[0]["connector_mapping_stub_count"], "1")
