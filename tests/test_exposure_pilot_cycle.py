from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_pilot_cycle import run_bari_phase1_exposure_pilot


class ExposurePilotCycleTests(unittest.TestCase):
    def test_run_bari_phase1_exposure_pilot_builds_join_and_readiness_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            mapping_stub_root = root / "mapping_stubs"
            motorized_mapping_stub_path = (
                mapping_stub_root
                / "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
            )
            speed_mapping_stub_path = (
                mapping_stub_root
                / "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
            )
            motorized_csv_path = root / "motorized.csv"
            speed_csv_path = root / "speed.csv"
            output_dir = root / "pilot_output"

            mapping_stub_root.mkdir(parents=True, exist_ok=True)

            segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "municipality_label": "bari",
                                    "maxspeed": "50",
                                    "exposure_proxy_index": 0.72,
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

            motorized_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "quality_checks": [
                            "non_negative_vehicle_count",
                            "observed_start_before_end",
                            "join_key_resolves_to_current_network_object",
                        ],
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "counter_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "vehicle_count",
                                "source_field": "vehicle_count_total",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                            {
                                "target_field": "aggregation_method",
                                "source_field": "aggregation_method",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "aadt",
                                "source_field": "aadt_estimate",
                                "type": "optional",
                                "required": False,
                            },
                            {
                                "target_field": "vehicle_km_estimate",
                                "source_field": "vehicle_km_travelled_estimate",
                                "type": "optional",
                                "required": False,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            speed_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_02_speed_observation_municipal",
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
                            {
                                "target_field": "source_record_id",
                                "source_field": "speed_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "mean_speed_kph",
                                "source_field": "mean_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "p85_speed_kph",
                                "source_field": "p85_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                            {
                                "target_field": "speed_std_kph",
                                "source_field": "speed_std_kph",
                                "type": "optional",
                                "required": False,
                            },
                            {
                                "target_field": "speed_variance",
                                "source_field": "speed_variance_kph2",
                                "type": "optional",
                                "required": False,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            motorized_csv_path.write_text(
                "source_record_id,provider_name,road_owner_scope,join_key_type,join_key_value,observed_start_utc,observed_end_utc,vehicle_count,sample_size,aggregation_method,aadt,vehicle_km_estimate\n"
                "m1,municipal_counter_export,municipal,segment_id,seg-1,2025-05-01T00:00:00Z,2025-05-01T23:59:59Z,1200,1200,daily_sensor_aggregate,1210,340.2\n",
                encoding="utf-8",
            )
            speed_csv_path.write_text(
                "source_record_id,provider_name,road_owner_scope,join_key_type,join_key_value,observed_start_utc,observed_end_utc,mean_speed_kph,p85_speed_kph,sample_size,speed_std_kph,speed_variance\n"
                "s1,fixed_speed_counter_export,municipal,segment_id,seg-1,2025-05-01T08:00:00Z,2025-05-01T08:59:59Z,45.1,56.2,890,8.2,67.24\n",
                encoding="utf-8",
            )

            payload = run_bari_phase1_exposure_pilot(
                segments_path=segments_path,
                motorized_extract_path=motorized_csv_path,
                motorized_mapping_stub_path=motorized_mapping_stub_path,
                speed_extract_path=speed_csv_path,
                speed_mapping_stub_path=speed_mapping_stub_path,
                mapping_stub_root=mapping_stub_root,
                readiness_dataset_label="bari",
                output_dir=output_dir,
            )

            self.assertEqual(payload["stats"]["motorized_rows_written"], 1)
            self.assertEqual(payload["stats"]["speed_rows_written"], 1)
            self.assertEqual(payload["stats"]["joined_matched_segment_count"], 1)
            self.assertEqual(
                payload["stats"]["readiness_status_by_capability"]["motorized_exposure"],
                "available",
            )
            self.assertEqual(
                payload["stats"]["readiness_status_by_capability"]["speed_observation"],
                "available",
            )

            summary_path = output_dir / "bari_phase1_exposure_pilot.json"
            manifest_path = output_dir / "bari_phase1_exposure_pilot.manifest.json"
            markdown_path = output_dir / "bari_phase1_exposure_pilot.md"
            self.assertTrue(summary_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(markdown_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["pilot_label"], "bari_phase1")
            self.assertGreater(summary["stats"]["motorized_required_feature_share"], 0.0)
            self.assertGreater(summary["stats"]["speed_required_feature_share"], 0.0)

            readiness_report = json.loads(
                (output_dir / "readiness" / "exposure_readiness.json").read_text(encoding="utf-8")
            )
            self.assertEqual(readiness_report["datasets"][0]["label"], "bari")

            joined_segments = json.loads(
                (output_dir / "connector_join" / "road_segments_connector_observations.geojson").read_text(
                    encoding="utf-8"
                )
            )
            properties = joined_segments["features"][0]["properties"]
            self.assertEqual(properties["observed_motorized_available"], 1.0)
            self.assertEqual(properties["observed_speed_available"], 1.0)

    def test_run_bari_phase1_exposure_pilot_can_normalize_raw_provider_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            mapping_stub_root = root / "mapping_stubs"
            motorized_mapping_stub_path = (
                mapping_stub_root
                / "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
            )
            speed_mapping_stub_path = (
                mapping_stub_root
                / "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
            )
            motorized_csv_path = root / "motorized_provider_raw.csv"
            speed_csv_path = root / "speed_provider_raw.csv"
            output_dir = root / "pilot_output"

            mapping_stub_root.mkdir(parents=True, exist_ok=True)

            segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "municipality_label": "bari",
                                    "maxspeed": "50",
                                    "exposure_proxy_index": 0.72,
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

            motorized_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "quality_checks": ["non_negative_vehicle_count"],
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "counter_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "vehicle_count",
                                "source_field": "vehicle_count_total",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                            {
                                "target_field": "aggregation_method",
                                "source_field": "aggregation_type",
                                "type": "string",
                                "required": True,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            speed_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_02_speed_observation_municipal",
                        "capability_code": "speed_observation",
                        "recommended_contract": "observed_speed_connector_v1",
                        "provider_profile_id": "fixed_speed_counter_export",
                        "provider_profile_label": "Fixed speed counter export",
                        "quality_checks": ["p85_not_below_mean"],
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "speed_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "mean_speed_kph",
                                "source_field": "mean_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "p85_speed_kph",
                                "source_field": "p85_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            motorized_csv_path.write_text(
                (
                    "Counter Record ID;Provider;Owner Scope;Segment Ref;Interval Start;Interval End;"
                    "Vehicle Count Total;Sample Count;Aggregation Type\n"
                    "m1;municipal_counter_export;municipal;seg-1;"
                    "2025-05-01T00:00:00Z;2025-05-01T23:59:59Z;1200;1200;daily_sensor_aggregate\n"
                ),
                encoding="utf-8",
            )
            speed_csv_path.write_text(
                (
                    "Speed Record ID,Provider,Segment Ref,Interval Start,Interval End,Mean Speed KPH,P85 Speed KPH,Sample Count\n"
                    "s1,fixed_speed_counter_export,seg-1,2025-05-01T08:00:00Z,2025-05-01T08:59:59Z,45.1,56.2,890\n"
                ),
                encoding="utf-8",
            )

            payload = run_bari_phase1_exposure_pilot(
                segments_path=segments_path,
                motorized_extract_path=motorized_csv_path,
                motorized_mapping_stub_path=motorized_mapping_stub_path,
                speed_extract_path=speed_csv_path,
                speed_mapping_stub_path=speed_mapping_stub_path,
                motorized_provider_profile_id="municipal_counter_export",
                speed_provider_profile_id="fixed_speed_counter_export",
                mapping_stub_root=mapping_stub_root,
                readiness_dataset_label="bari",
                output_dir=output_dir,
            )

            self.assertEqual(payload["stats"]["motorized_normalization_rows_written"], 1)
            self.assertEqual(payload["stats"]["speed_normalization_rows_written"], 1)
            self.assertEqual(payload["stats"]["motorized_rows_written"], 1)
            self.assertEqual(payload["stats"]["speed_rows_written"], 1)
            self.assertEqual(payload["stats"]["joined_matched_segment_count"], 1)

            self.assertTrue(
                (output_dir / "motorized_normalization" / "municipal_counter_export__normalized_extract.csv").exists()
            )
            self.assertTrue(
                (output_dir / "speed_normalization" / "fixed_speed_counter_export__normalized_extract.csv").exists()
            )

    def test_run_bari_phase1_exposure_pilot_can_normalize_from_mapping_stub_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            mapping_stub_root = root / "mapping_stubs"
            motorized_mapping_stub_path = (
                mapping_stub_root
                / "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
            )
            speed_mapping_stub_path = (
                mapping_stub_root
                / "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
            )
            motorized_csv_path = root / "motorized_provider_raw.csv"
            speed_csv_path = root / "speed_provider_raw.csv"
            output_dir = root / "pilot_output"

            mapping_stub_root.mkdir(parents=True, exist_ok=True)

            segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "segment_id": "seg-1",
                                    "municipality_label": "bari",
                                    "maxspeed": "50",
                                    "exposure_proxy_index": 0.72,
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

            motorized_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "quality_checks": ["non_negative_vehicle_count"],
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "counter_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "vehicle_count",
                                "source_field": "vehicle_count_total",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                            {
                                "target_field": "aggregation_method",
                                "source_field": "aggregation_type",
                                "type": "string",
                                "required": True,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            speed_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "municipality_label": "bari",
                        "work_item_id": "bari_02_speed_observation_municipal",
                        "capability_code": "speed_observation",
                        "recommended_contract": "observed_speed_connector_v1",
                        "provider_profile_id": "fixed_speed_counter_export",
                        "provider_profile_label": "Fixed speed counter export",
                        "quality_checks": ["p85_not_below_mean"],
                        "field_mappings": [
                            {
                                "target_field": "source_record_id",
                                "source_field": "speed_record_id",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "provider_name",
                                "source_field": "provider_name",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "road_owner_scope",
                                "source_field": "owner_scope",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_type",
                                "source_field": "network_join_type",
                                "type": "enum",
                                "required": True,
                            },
                            {
                                "target_field": "join_key_value",
                                "source_field": "segment_ref",
                                "type": "string",
                                "required": True,
                            },
                            {
                                "target_field": "observed_start_utc",
                                "source_field": "observation_start_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "observed_end_utc",
                                "source_field": "observation_end_utc",
                                "type": "datetime",
                                "required": True,
                            },
                            {
                                "target_field": "mean_speed_kph",
                                "source_field": "mean_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "p85_speed_kph",
                                "source_field": "p85_speed_kph",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "target_field": "sample_size",
                                "source_field": "sample_count",
                                "type": "integer",
                                "required": True,
                            },
                        ],
                        "target_join_strategy": {"join_key_type": "segment_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            motorized_csv_path.write_text(
                (
                    "Counter Record ID;Provider;Owner Scope;Segment Ref;Interval Start;Interval End;"
                    "Vehicle Count Total;Sample Count;Aggregation Type\n"
                    "m1;municipal_counter_export;municipal;seg-1;"
                    "2025-05-01T00:00:00Z;2025-05-01T23:59:59Z;1200;1200;daily_sensor_aggregate\n"
                ),
                encoding="utf-8",
            )
            speed_csv_path.write_text(
                (
                    "Speed Record ID,Provider,Segment Ref,Interval Start,Interval End,Mean Speed KPH,P85 Speed KPH,Sample Count\n"
                    "s1,fixed_speed_counter_export,seg-1,2025-05-01T08:00:00Z,2025-05-01T08:59:59Z,45.1,56.2,890\n"
                ),
                encoding="utf-8",
            )

            payload = run_bari_phase1_exposure_pilot(
                segments_path=segments_path,
                motorized_extract_path=motorized_csv_path,
                motorized_mapping_stub_path=motorized_mapping_stub_path,
                speed_extract_path=speed_csv_path,
                speed_mapping_stub_path=speed_mapping_stub_path,
                normalize_motorized_provider_extract=True,
                normalize_speed_provider_extract=True,
                mapping_stub_root=mapping_stub_root,
                readiness_dataset_label="bari",
                output_dir=output_dir,
            )

            self.assertEqual(payload["stats"]["motorized_normalization_rows_written"], 1)
            self.assertEqual(payload["stats"]["speed_normalization_rows_written"], 1)
            self.assertEqual(payload["stats"]["motorized_rows_written"], 1)
            self.assertEqual(payload["stats"]["speed_rows_written"], 1)
            self.assertEqual(payload["stats"]["joined_matched_segment_count"], 1)

            summary = json.loads((output_dir / "bari_phase1_exposure_pilot.json").read_text(encoding="utf-8"))
            self.assertIsNone(summary["inputs"]["motorized_provider_profile_id"])
            self.assertIsNone(summary["inputs"]["speed_provider_profile_id"])
            self.assertTrue(summary["inputs"]["normalize_motorized_provider_extract"])
            self.assertTrue(summary["inputs"]["normalize_speed_provider_extract"])
            self.assertEqual(
                summary["inputs"]["motorized_resolved_provider_profile_id"],
                "municipal_counter_export",
            )
            self.assertEqual(
                summary["inputs"]["speed_resolved_provider_profile_id"],
                "fixed_speed_counter_export",
            )


if __name__ == "__main__":
    unittest.main()
