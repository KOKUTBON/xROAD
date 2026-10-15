from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.remediation import analyze_match_results


class RemediationTests(unittest.TestCase):
    def test_analyze_match_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched_path = root / "matched.jsonl"
            unmatched_path = root / "unmatched.jsonl"

            matched_path.write_text(
                "\n".join(
                    [
                        json.dumps({"crash_id": "a", "match_distance_m": 2.0, "city_code": "6", "province_code": "72"}),
                        json.dumps({"crash_id": "b", "match_distance_m": 8.0, "city_code": "6", "province_code": "72"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            unmatched_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "c",
                                "source_unique_key": "2020:3",
                                "match_distance_m": 55.0,
                                "city_code": "6",
                                "province_code": "72",
                                "quality_flags": ["missing_road_code"],
                                "segment_id": "seg-x",
                                "extra": {"legacy_location": {"road_code": None, "road_description": "Via Roma"}},
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "d",
                                "source_unique_key": "2020:4",
                                "match_distance_m": 180.0,
                                "city_code": "27",
                                "province_code": "72",
                                "quality_flags": [],
                                "segment_id": "seg-y",
                                "extra": {"legacy_location": {"road_code": "SP11001BA", "road_description": "SP110"}},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = analyze_match_results(matched_path, unmatched_path, output_dir=root, review_limit=10)

            self.assertEqual(result["stats"]["matched_records"], 2)
            self.assertEqual(result["stats"]["unmatched_records"], 2)
            self.assertTrue((root / "remediation_report.json").exists())
            self.assertTrue((root / "review_candidates.jsonl").exists())

            report = json.loads((root / "remediation_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["threshold_sweep_records_within_distance"]["60"], 3)
            self.assertEqual(report["top_unmatched_road_codes"]["<missing>"], 1)
