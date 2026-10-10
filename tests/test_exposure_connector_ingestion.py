from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_connector_ingestion import ingest_exposure_connector_extract
from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle


class ExposureConnectorIngestionTests(unittest.TestCase):
    def test_ingest_exposure_connector_extract_writes_normalized_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "connector.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "processed"
            governance_dir = root / "governance"

            input_csv_path.write_text(
                (
                    "source_record_id,provider_name,road_owner_scope,join_key_type,join_key_value,"
                    "observed_start_utc,observed_end_utc,vehicle_count,sample_size,aggregation_method,aadt\n"
                    "demo_1,municipal_counter_export,municipal,segment_id,seg-001,"
                    "2025-05-01T00:00:00Z,2025-05-01T23:59:59Z,1234,1234,daily_sensor_aggregate,1400\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "municipality_label": "bari",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "publication_policy": {
                            "publication_tier": "restricted_aggregates_with_public_summary",
                        },
                        "quality_checks": ["non_negative_vehicle_count"],
                        "governance_gates": ["provider_license_registered"],
                        "field_mappings": [
                            {"target_field": "source_record_id", "source_field": "TODO_demo__source_record_id", "required": True, "type": "string"},
                            {"target_field": "provider_name", "source_field": "TODO_demo__provider_name", "required": True, "type": "string"},
                            {"target_field": "road_owner_scope", "source_field": "TODO_demo__road_owner_scope", "required": True, "type": "enum"},
                            {"target_field": "join_key_type", "source_field": "TODO_demo__join_key_type", "required": True, "type": "enum"},
                            {"target_field": "join_key_value", "source_field": "TODO_demo__join_key_value", "required": True, "type": "string"},
                            {"target_field": "observed_start_utc", "source_field": "TODO_demo__observed_start_utc", "required": True, "type": "datetime"},
                            {"target_field": "observed_end_utc", "source_field": "TODO_demo__observed_end_utc", "required": True, "type": "datetime"},
                            {"target_field": "vehicle_count", "source_field": "TODO_demo__vehicle_count", "required": True, "type": "number"},
                            {"target_field": "sample_size", "source_field": "TODO_demo__sample_size", "required": True, "type": "integer"},
                            {"target_field": "aggregation_method", "source_field": "TODO_demo__aggregation_method", "required": True, "type": "string"},
                            {"target_field": "aadt", "source_field": "TODO_demo__aadt", "required": False, "type": "optional"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            build_governance_interoperability_bundle(governance_dir)

            payload = ingest_exposure_connector_extract(
                input_csv_path,
                mapping_stub_path,
                output_dir,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            self.assertEqual(payload["exposure_connector_observations_version"], "exposure_connector_observations_v1")
            self.assertEqual(payload["stats"]["written_rows"], 1)
            self.assertEqual(payload["stats"]["rejected_rows"], 0)

            observations_path = output_dir / "connector_observations.jsonl"
            manifest_path = output_dir / "connector_observations.manifest.json"
            rejected_rows_path = output_dir / "connector_rejected_rows.jsonl"
            self.assertTrue(observations_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(rejected_rows_path.exists())

            record = json.loads(observations_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["municipality_label"], "bari")
            self.assertEqual(record["capability_code"], "motorized_exposure")
            self.assertEqual(record["join_key_type"], "segment_id")
            self.assertEqual(record["attributes"]["vehicle_count"], 1234.0)
            self.assertEqual(record["attributes"]["sample_size"], 1234)
            self.assertEqual(record["attributes"]["aadt"], 1400)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "exposure_connector_observations")
            self.assertEqual(manifest["stats"]["written_rows"], 1)
            self.assertEqual(
                manifest["governance"]["source_family_ids"],
                ["exposure_motorized_aggregate"],
            )

    def test_ingest_exposure_connector_extract_rejects_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "connector.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "processed"

            input_csv_path.write_text(
                (
                    "source_record_id,provider_name,road_owner_scope,join_key_type,join_key_value,"
                    "observed_start_utc,observed_end_utc,vehicle_count,sample_size,aggregation_method\n"
                    "demo_1,municipal_counter_export,municipal,segment_id,seg-001,"
                    "2025-05-01T00:00:00Z,2025-05-01T23:59:59Z,,1234,daily_sensor_aggregate\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "municipality_label": "bari",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "field_mappings": [
                            {"target_field": "source_record_id", "source_field": "source_record_id", "required": True, "type": "string"},
                            {"target_field": "provider_name", "source_field": "provider_name", "required": True, "type": "string"},
                            {"target_field": "road_owner_scope", "source_field": "road_owner_scope", "required": True, "type": "enum"},
                            {"target_field": "join_key_type", "source_field": "join_key_type", "required": True, "type": "enum"},
                            {"target_field": "join_key_value", "source_field": "join_key_value", "required": True, "type": "string"},
                            {"target_field": "observed_start_utc", "source_field": "observed_start_utc", "required": True, "type": "datetime"},
                            {"target_field": "observed_end_utc", "source_field": "observed_end_utc", "required": True, "type": "datetime"},
                            {"target_field": "vehicle_count", "source_field": "vehicle_count", "required": True, "type": "number"},
                            {"target_field": "sample_size", "source_field": "sample_size", "required": True, "type": "integer"},
                            {"target_field": "aggregation_method", "source_field": "aggregation_method", "required": True, "type": "string"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = ingest_exposure_connector_extract(
                input_csv_path,
                mapping_stub_path,
                output_dir,
            )

            self.assertEqual(payload["stats"]["written_rows"], 0)
            self.assertEqual(payload["stats"]["rejected_rows"], 1)
            rejected = (output_dir / "connector_rejected_rows.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rejected), 1)

    def test_ingest_exposure_connector_extract_handles_dirty_numeric_formats_and_quality_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "dirty_connector.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "processed"

            input_csv_path.write_text(
                (
                    "counter_record_id,provider_name,owner_scope,network_join_type,segment_ref,"
                    "observation_start_utc,observation_end_utc,vehicle_count_total,sample_count,aggregation_method,coverage_share\n"
                    "bari_001,municipal_counter_export,municipal,segment_id,seg-001,"
                    "2025-05-01T00:00:00+02:00,2025-05-01T23:59:59+02:00,12 458,12 458,daily_sensor_aggregate,\"0,97\"\n"
                    "bari_002,municipal_counter_export,municipal,segment_id,seg-002,"
                    "2025-05-02T00:00:00+02:00,2025-05-02T23:59:59+02:00,-10,10,daily_sensor_aggregate,\"1,20\"\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "municipality_label": "bari",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "quality_checks": [
                            "non_negative_vehicle_count",
                            "observed_start_before_end",
                            "coverage_threshold_documented",
                        ],
                        "field_mappings": [
                            {"target_field": "source_record_id", "source_field": "counter_record_id", "required": True, "type": "string"},
                            {"target_field": "provider_name", "source_field": "provider_name", "required": True, "type": "string"},
                            {"target_field": "road_owner_scope", "source_field": "owner_scope", "required": True, "type": "enum"},
                            {"target_field": "join_key_type", "source_field": "network_join_type", "required": True, "type": "enum"},
                            {"target_field": "join_key_value", "source_field": "segment_ref", "required": True, "type": "string"},
                            {"target_field": "observed_start_utc", "source_field": "observation_start_utc", "required": True, "type": "datetime"},
                            {"target_field": "observed_end_utc", "source_field": "observation_end_utc", "required": True, "type": "datetime"},
                            {"target_field": "vehicle_count", "source_field": "vehicle_count_total", "required": True, "type": "number"},
                            {"target_field": "sample_size", "source_field": "sample_count", "required": True, "type": "integer"},
                            {"target_field": "aggregation_method", "source_field": "aggregation_method", "required": True, "type": "string"},
                            {"target_field": "coverage_pct", "source_field": "coverage_share", "required": False, "type": "optional"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = ingest_exposure_connector_extract(
                input_csv_path,
                mapping_stub_path,
                output_dir,
            )

            self.assertEqual(payload["stats"]["total_rows"], 2)
            self.assertEqual(payload["stats"]["written_rows"], 1)
            self.assertEqual(payload["stats"]["rejected_rows"], 1)
            self.assertGreaterEqual(
                payload["stats"]["quality_flag_counts"].get(
                    "quality_check_failed:non_negative_vehicle_count:vehicle_count",
                    0,
                ),
                1,
            )

            observations_path = output_dir / "connector_observations.jsonl"
            record = json.loads(observations_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["attributes"]["vehicle_count"], 12458.0)
            self.assertEqual(record["attributes"]["sample_size"], 12458)
            self.assertEqual(record["attributes"]["coverage_pct"], 0.97)
            self.assertEqual(record["attributes"]["observed_start_utc"], "2025-04-30T22:00:00Z")

    def test_ingest_exposure_connector_extract_validates_speed_quality_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "speed_connector.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "processed"

            input_csv_path.write_text(
                (
                    "speed_record_id,provider_name,owner_scope,network_join_type,segment_ref,"
                    "observation_start_utc,observation_end_utc,mean_speed_kph,p85_speed_kph,sample_count,speed_std_kph,speed_variance_kph2\n"
                    "speed_001,fixed_speed_counter_export,municipal,segment_id,seg-001,"
                    "2025-05-01T08:00:00+02:00,2025-05-01T08:59:59+02:00,\"43,8\",\"55,7\",921,\"8,7\",\"75,69\"\n"
                    "speed_002,fixed_speed_counter_export,municipal,segment_id,seg-002,"
                    "2025-05-01T09:00:00+02:00,2025-05-01T09:59:59+02:00,60,55,1200,6.1,37.21\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "work_item_id": "bari_02_speed_observation_municipal",
                        "municipality_label": "bari",
                        "capability_code": "speed_observation",
                        "recommended_contract": "observed_speed_connector_v1",
                        "provider_profile_id": "fixed_speed_counter_export",
                        "provider_profile_label": "Fixed speed counter export",
                        "quality_checks": [
                            "non_negative_speed_values",
                            "p85_not_below_mean",
                            "observed_start_before_end",
                            "sample_size_threshold_documented",
                        ],
                        "field_mappings": [
                            {"target_field": "source_record_id", "source_field": "speed_record_id", "required": True, "type": "string"},
                            {"target_field": "provider_name", "source_field": "provider_name", "required": True, "type": "string"},
                            {"target_field": "road_owner_scope", "source_field": "owner_scope", "required": True, "type": "enum"},
                            {"target_field": "join_key_type", "source_field": "network_join_type", "required": True, "type": "enum"},
                            {"target_field": "join_key_value", "source_field": "segment_ref", "required": True, "type": "string"},
                            {"target_field": "observed_start_utc", "source_field": "observation_start_utc", "required": True, "type": "datetime"},
                            {"target_field": "observed_end_utc", "source_field": "observation_end_utc", "required": True, "type": "datetime"},
                            {"target_field": "mean_speed_kph", "source_field": "mean_speed_kph", "required": True, "type": "number"},
                            {"target_field": "p85_speed_kph", "source_field": "p85_speed_kph", "required": True, "type": "number"},
                            {"target_field": "sample_size", "source_field": "sample_count", "required": True, "type": "integer"},
                            {"target_field": "speed_std_kph", "source_field": "speed_std_kph", "required": False, "type": "optional"},
                            {"target_field": "speed_variance", "source_field": "speed_variance_kph2", "required": False, "type": "optional"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = ingest_exposure_connector_extract(
                input_csv_path,
                mapping_stub_path,
                output_dir,
            )

            self.assertEqual(payload["stats"]["total_rows"], 2)
            self.assertEqual(payload["stats"]["written_rows"], 1)
            self.assertEqual(payload["stats"]["rejected_rows"], 1)
            self.assertGreaterEqual(
                payload["stats"]["quality_flag_counts"].get(
                    "quality_check_failed:p85_not_below_mean:p85_below_mean",
                    0,
                ),
                1,
            )

            observations_path = output_dir / "connector_observations.jsonl"
            record = json.loads(observations_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["attributes"]["mean_speed_kph"], 43.8)
            self.assertEqual(record["attributes"]["p85_speed_kph"], 55.7)
            self.assertEqual(record["attributes"]["speed_std_kph"], 8.7)
            self.assertEqual(record["attributes"]["speed_variance"], 75.69)
