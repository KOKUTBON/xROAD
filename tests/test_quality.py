from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.quality import analyze_canonical_jsonl, write_canonical_quality_report


class QualityTests(unittest.TestCase):
    def test_analyze_canonical_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "canonical.jsonl"
            records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "source_system": "legacy",
                                "source_record_id": "1",
                                "province_code": "71",
                                "city_code": "2",
                                "latitude": 41.1,
                                "longitude": 16.8,
                                "roadway_type": "intersection",
                                "intersection_type": "intersection",
                                "severity_level": "injury",
                                "fatalities": 0,
                                "injuries": 1,
                                "quality_flags": ["missing_road_code"],
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "a",
                                "source_system": "legacy",
                                "source_record_id": "1",
                                "province_code": "",
                                "city_code": "3",
                                "latitude": None,
                                "longitude": None,
                                "roadway_type": None,
                                "intersection_type": None,
                                "severity_level": "fatal",
                                "fatalities": 1,
                                "injuries": 0,
                                "quality_flags": ["missing_coordinates"],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = analyze_canonical_jsonl(records_path, top_n=5)

            self.assertEqual(report["stats"]["total_records"], 2)
            self.assertEqual(report["stats"]["coordinate_complete_records"], 1)
            self.assertEqual(report["stats"]["records_with_any_quality_flag"], 2)
            self.assertEqual(report["quality_flag_counts"]["missing_road_code"], 1)
            self.assertEqual(report["quality_flag_counts"]["missing_coordinates"], 1)
            self.assertEqual(report["missing_field_counts"]["province_code"], 1)
            self.assertEqual(report["duplicate_crash_ids"]["duplicate_key_count"], 1)
            self.assertEqual(report["duplicate_source_records"]["duplicate_key_count"], 0)
            self.assertEqual(report["duplicate_raw_source_record_ids"]["duplicate_key_count"], 1)
            self.assertEqual(report["stats"]["unique_crash_ids"], 1)

    def test_write_canonical_quality_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "canonical.jsonl"
            report_path = Path(temp_dir) / "canonical.qa.json"
            records_path.write_text(
                json.dumps(
                    {
                        "crash_id": "x",
                        "source_system": "legacy",
                        "source_record_id": "7",
                        "province_code": "71",
                        "city_code": "2",
                        "latitude": 41.1,
                        "longitude": 16.8,
                        "roadway_type": "intersection",
                        "intersection_type": "intersection",
                        "severity_level": "injury",
                        "fatalities": 0,
                        "injuries": 1,
                        "quality_flags": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = write_canonical_quality_report(records_path, output_path=report_path)

            self.assertTrue(report_path.exists())
            self.assertEqual(result["stats"]["total_records"], 1)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["distinct_provinces"], 1)
