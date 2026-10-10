from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_connector_intake import build_exposure_connector_intake_pack
from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle


class ExposureConnectorIntakePackTests(unittest.TestCase):
    def test_build_exposure_connector_intake_pack_writes_templates_and_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            onboarding_plan_path = root / "exposure_onboarding_plan.json"
            output_dir = root / "exposure_connector_intake"
            governance_dir = root / "governance"

            source_catalog_path.write_text(
                json.dumps(
                    {
                        "connector_contracts": {
                            "motorized_exposure": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {"name": "join_key_type", "type": "enum"},
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "vehicle_count", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                    {"name": "aggregation_method", "type": "string"},
                                ],
                                "optional_fields": ["aadt", "coverage_pct"],
                            },
                            "speed_observation": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {
                                        "name": "join_key_type",
                                        "type": "enum",
                                        "allowed": ["segment_id", "junction_approach_id"],
                                    },
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "mean_speed_kph", "type": "number"},
                                    {"name": "p85_speed_kph", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                ],
                                "optional_fields": ["speed_std_kph", "speed_limit_kph"],
                            },
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            onboarding_plan_path.write_text(
                json.dumps(
                    {
                        "municipality_plans": [
                            {
                                "label": "demo_city",
                                "work_items": [
                                    {
                                        "work_item_id": "demo_01_motorized_exposure_municipal",
                                        "municipality_label": "demo_city",
                                        "capability_code": "motorized_exposure",
                                        "capability_label": "Motor traffic exposure",
                                        "owner_scope": "municipal",
                                        "recommended_contract": "motorized_exposure_connector_v1",
                                        "quality_checks": ["non_negative_vehicle_count"],
                                        "governance_gates": ["provider_license_registered"],
                                    },
                                    {
                                        "work_item_id": "demo_02_speed_observation_municipal",
                                        "municipality_label": "demo_city",
                                        "capability_code": "speed_observation",
                                        "capability_label": "Observed speed and variability",
                                        "owner_scope": "municipal",
                                        "recommended_contract": "observed_speed_connector_v1",
                                        "quality_checks": ["p85_not_below_mean"],
                                        "governance_gates": ["retention_policy_defined"],
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
            build_governance_interoperability_bundle(governance_dir)

            payload = build_exposure_connector_intake_pack(
                source_catalog_path=source_catalog_path,
                onboarding_plan_path=onboarding_plan_path,
                output_dir=output_dir,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            self.assertEqual(payload["exposure_connector_intake_version"], "exposure_connector_intake_v1")
            self.assertEqual(payload["stats"]["municipality_count"], 1)
            self.assertEqual(payload["stats"]["phase_1_work_item_count"], 2)
            self.assertEqual(payload["stats"]["template_count"], 4)
            self.assertEqual(payload["stats"]["mapping_stub_count"], 4)

            pack_json_path = output_dir / "connector_intake_pack.json"
            pack_markdown_path = output_dir / "connector_intake_pack.md"
            rights_matrix_path = output_dir / "source_rights_matrix.csv"
            manifest_path = output_dir / "connector_intake_pack.manifest.json"
            self.assertTrue(pack_json_path.exists())
            self.assertTrue(pack_markdown_path.exists())
            self.assertTrue(rights_matrix_path.exists())
            self.assertTrue(manifest_path.exists())

            pack = json.loads(pack_json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(pack["connector_intakes"]), 2)
            motorized_intake = next(item for item in pack["connector_intakes"] if item["capability_code"] == "motorized_exposure")
            self.assertEqual(len(motorized_intake["provider_profiles"]), 2)
            template_path = Path(motorized_intake["provider_profiles"][0]["template_path"])
            mapping_path = Path(motorized_intake["provider_profiles"][0]["mapping_stub_path"])
            self.assertTrue(template_path.exists())
            self.assertTrue(mapping_path.exists())
            mapping_stub = json.loads(mapping_path.read_text(encoding="utf-8"))
            self.assertEqual(
                mapping_stub["governance"]["source_family_ids"],
                ["exposure_motorized_aggregate"],
            )

            with rights_matrix_path.open(encoding="utf-8", newline="") as handle:
                rights_rows = list(csv.DictReader(handle))
            self.assertEqual(len(rights_rows), 4)
            self.assertEqual(rights_rows[0]["municipality_label"], "demo_city")

            markdown = pack_markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Exposure Connector Intake Pack", markdown)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "exposure_connector_intake_pack")
            self.assertEqual(manifest["stats"]["rights_matrix_row_count"], 4)
            self.assertIn("exposure_connector_intake_pack", manifest["governance"]["artifact_family_ids"])

    def test_build_exposure_connector_intake_pack_applies_bari_motorized_contract_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            onboarding_plan_path = root / "exposure_onboarding_plan.json"
            output_dir = root / "exposure_connector_intake"

            source_catalog_path.write_text(
                json.dumps(
                    {
                        "connector_contracts": {
                            "motorized_exposure": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {"name": "join_key_type", "type": "enum"},
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "vehicle_count", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                    {"name": "aggregation_method", "type": "string"},
                                ],
                                "optional_fields": [
                                    "aadt",
                                    "heavy_vehicle_share",
                                    "vehicle_km_estimate",
                                    "coverage_pct",
                                    "flow_quality_flag",
                                ],
                            },
                            "speed_observation": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {"name": "join_key_type", "type": "enum"},
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "mean_speed_kph", "type": "number"},
                                    {"name": "p85_speed_kph", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                ],
                                "optional_fields": ["speed_std_kph"],
                            },
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            onboarding_plan_path.write_text(
                json.dumps(
                    {
                        "municipality_plans": [
                            {
                                "label": "bari",
                                "work_items": [
                                    {
                                        "work_item_id": "bari_01_motorized_exposure_municipal",
                                        "municipality_label": "bari",
                                        "capability_code": "motorized_exposure",
                                        "capability_label": "Motor traffic exposure",
                                        "owner_scope": "municipal",
                                        "recommended_contract": "motorized_exposure_connector_v1",
                                        "quality_checks": ["non_negative_vehicle_count"],
                                        "governance_gates": ["provider_license_registered"],
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

            build_exposure_connector_intake_pack(
                source_catalog_path=source_catalog_path,
                onboarding_plan_path=onboarding_plan_path,
                output_dir=output_dir,
            )

            mapping_stub_path = (
                output_dir
                / "mapping_stubs"
                / "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
            )
            mapping_stub = json.loads(mapping_stub_path.read_text(encoding="utf-8"))
            source_by_target = {
                row["target_field"]: row["source_field"]
                for row in mapping_stub["field_mappings"]
            }
            self.assertEqual(source_by_target["source_record_id"], "counter_record_id")
            self.assertEqual(source_by_target["join_key_value"], "segment_ref")
            self.assertEqual(source_by_target["vehicle_count"], "vehicle_count_total")
            self.assertEqual(source_by_target["coverage_pct"], "coverage_share")
            self.assertIn(
                "bari_context_v2/road_segments_context.geojson",
                mapping_stub["target_join_strategy"]["join_lookup_note"],
            )

    def test_build_exposure_connector_intake_pack_applies_bari_speed_contract_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            onboarding_plan_path = root / "exposure_onboarding_plan.json"
            output_dir = root / "exposure_connector_intake"

            source_catalog_path.write_text(
                json.dumps(
                    {
                        "connector_contracts": {
                            "motorized_exposure": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {"name": "join_key_type", "type": "enum"},
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "vehicle_count", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                    {"name": "aggregation_method", "type": "string"},
                                ],
                                "optional_fields": ["aadt"],
                            },
                            "speed_observation": {
                                "required_fields": [
                                    {"name": "source_record_id", "type": "string"},
                                    {"name": "provider_name", "type": "string"},
                                    {"name": "road_owner_scope", "type": "enum"},
                                    {
                                        "name": "join_key_type",
                                        "type": "enum",
                                        "allowed": [
                                            "segment_id",
                                            "junction_approach_id",
                                        ],
                                    },
                                    {"name": "join_key_value", "type": "string"},
                                    {"name": "observed_start_utc", "type": "datetime"},
                                    {"name": "observed_end_utc", "type": "datetime"},
                                    {"name": "mean_speed_kph", "type": "number"},
                                    {"name": "p85_speed_kph", "type": "number"},
                                    {"name": "sample_size", "type": "integer"},
                                ],
                                "optional_fields": [
                                    "speed_std_kph",
                                    "speed_variance",
                                    "speed_limit_kph",
                                    "probe_penetration_rate",
                                    "speed_quality_flag",
                                ],
                            },
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            onboarding_plan_path.write_text(
                json.dumps(
                    {
                        "municipality_plans": [
                            {
                                "label": "bari",
                                "work_items": [
                                    {
                                        "work_item_id": "bari_02_speed_observation_municipal",
                                        "municipality_label": "bari",
                                        "capability_code": "speed_observation",
                                        "capability_label": "Observed speed and variability",
                                        "owner_scope": "municipal",
                                        "recommended_contract": "observed_speed_connector_v1",
                                        "quality_checks": ["non_negative_speed_values"],
                                        "governance_gates": ["retention_policy_defined"],
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

            build_exposure_connector_intake_pack(
                source_catalog_path=source_catalog_path,
                onboarding_plan_path=onboarding_plan_path,
                output_dir=output_dir,
            )

            mapping_stub_path = (
                output_dir
                / "mapping_stubs"
                / "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
            )
            mapping_stub = json.loads(mapping_stub_path.read_text(encoding="utf-8"))
            source_by_target = {
                row["target_field"]: row["source_field"]
                for row in mapping_stub["field_mappings"]
            }
            self.assertEqual(source_by_target["source_record_id"], "speed_record_id")
            self.assertEqual(source_by_target["join_key_value"], "segment_ref")
            self.assertEqual(source_by_target["sample_size"], "sample_count")
            self.assertEqual(source_by_target["speed_variance"], "speed_variance_kph2")
            self.assertEqual(mapping_stub["target_join_strategy"]["join_key_type"], "segment_id")
