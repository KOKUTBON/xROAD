from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.exposure_connector_ingestion import ingest_exposure_connector_extract
from road_risk_modeling.exposure_provider_adapter import normalize_exposure_provider_extract


class ExposureProviderAdapterTests(unittest.TestCase):
    def test_normalize_motorized_alias_headers_and_ingest_with_bari_stub_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "motorized_provider_export.csv"
            normalized_output_dir = root / "normalized"
            ingestion_output_dir = root / "ingested"
            mapping_stub_path = root / "mapping_stub.json"

            input_csv_path.write_text(
                (
                    "Counter Record ID;Provider;Owner Scope;Segment Ref;Interval Start;Interval End;"
                    "Vehicle Count Total;Sample Count;Aggregation Type;Coverage Share\n"
                    "bari_row_1;municipal_counter_export;municipal;seg-001;"
                    "2025-05-01T00:00:00Z;2025-05-01T23:59:59Z;12458;12458;daily_sensor_aggregate;0,97\n"
                ),
                encoding="utf-8",
            )

            normalized_payload = normalize_exposure_provider_extract(
                input_csv_path,
                provider_profile_id="municipal_counter_export",
                output_dir=normalized_output_dir,
            )
            self.assertEqual(normalized_payload["stats"]["written_rows"], 1)
            self.assertEqual(normalized_payload["stats"]["rejected_rows"], 0)
            self.assertEqual(normalized_payload["stats"]["default_field_counts"]["join_key_type"], 1)

            normalized_csv_path = Path(normalized_payload["normalized_csv_path"])
            with normalized_csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_record_id"], "bari_row_1")
            self.assertEqual(rows[0]["join_key_type"], "segment_id")

            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "work_item_id": "bari_01_motorized_exposure_municipal",
                        "municipality_label": "bari",
                        "capability_code": "motorized_exposure",
                        "recommended_contract": "motorized_exposure_connector_v1",
                        "provider_profile_id": "municipal_counter_export",
                        "provider_profile_label": "Municipal count export",
                        "quality_checks": ["non_negative_vehicle_count"],
                        "governance_gates": [],
                        "publication_policy": {},
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
                            {"target_field": "aggregation_method", "source_field": "aggregation_type", "required": True, "type": "string"},
                            {"target_field": "coverage_pct", "source_field": "coverage_share", "required": False, "type": "optional"},
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            ingested_payload = ingest_exposure_connector_extract(
                normalized_csv_path,
                mapping_stub_path,
                ingestion_output_dir,
            )
            self.assertEqual(ingested_payload["stats"]["written_rows"], 1)
            self.assertEqual(ingested_payload["stats"]["rejected_rows"], 0)

    def test_normalize_speed_extract_rejects_rows_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "speed_provider_export.csv"
            output_dir = root / "normalized"

            input_csv_path.write_text(
                (
                    "Speed Record ID,Provider,Segment Ref,Interval Start,Interval End,Mean Speed KPH,Sample Count\n"
                    "speed_row_1,fixed_speed_counter_export,seg-001,2025-05-01T08:00:00Z,2025-05-01T08:59:59Z,47.2,800\n"
                ),
                encoding="utf-8",
            )

            payload = normalize_exposure_provider_extract(
                input_csv_path,
                provider_profile_id="fixed_speed_counter_export",
                output_dir=output_dir,
            )

            self.assertEqual(payload["stats"]["written_rows"], 0)
            self.assertEqual(payload["stats"]["rejected_rows"], 1)
            self.assertEqual(payload["stats"]["missing_required_field_counts"]["p85_speed_kph"], 1)

            rejected_rows_path = Path(payload["rejected_rows_path"])
            rejected_entries = [
                json.loads(line)
                for line in rejected_rows_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rejected_entries), 1)
            self.assertIn("missing_required_field:p85_speed_kph", rejected_entries[0]["errors"])

    def test_normalize_extract_can_resolve_profile_from_mapping_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "speed_provider_export.csv"
            output_dir = root / "normalized"
            mapping_stub_path = root / "mapping_stub.json"

            input_csv_path.write_text(
                (
                    "Speed Record ID,Provider,Segment Ref,Interval Start,Interval End,Mean Speed KPH,P85 Speed KPH,Sample Count\n"
                    "speed_row_1,fixed_speed_counter_export,seg-001,2025-05-01T08:00:00Z,2025-05-01T08:59:59Z,47.2,58.0,800\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "provider_profile_id": "fixed_speed_counter_export",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = normalize_exposure_provider_extract(
                input_csv_path,
                mapping_stub_path=mapping_stub_path,
                output_dir=output_dir,
            )

            self.assertEqual(payload["provider_profile_id"], "fixed_speed_counter_export")
            self.assertEqual(payload["stats"]["written_rows"], 1)
            manifest_path = Path(payload["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["inputs"]["provider_profile_id"], "fixed_speed_counter_export")
            self.assertEqual(manifest["inputs"]["mapping_stub_path"], str(mapping_stub_path))

    def test_normalize_extract_rejects_profile_mismatch_with_mapping_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "motorized_provider_export.csv"
            output_dir = root / "normalized"
            mapping_stub_path = root / "mapping_stub.json"

            input_csv_path.write_text(
                (
                    "Counter Record ID,Provider,Owner Scope,Segment Ref,Interval Start,Interval End,"
                    "Vehicle Count Total,Sample Count,Aggregation Type\n"
                    "bari_row_1,municipal_counter_export,municipal,seg-001,"
                    "2025-05-01T00:00:00Z,2025-05-01T23:59:59Z,12458,12458,daily_sensor_aggregate\n"
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "provider_profile_id": "fixed_speed_counter_export",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                normalize_exposure_provider_extract(
                    input_csv_path,
                    provider_profile_id="municipal_counter_export",
                    mapping_stub_path=mapping_stub_path,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
