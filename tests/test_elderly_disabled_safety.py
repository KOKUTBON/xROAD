from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.elderly_disabled_safety import (
    accessibility_provision,
    elderly_exposure,
    recommend_countermeasures,
    run_elderly_disabled_assessment,
    score_segment,
)


class ElderlyExposureTests(unittest.TestCase):
    def test_recorded_age_used_when_available(self) -> None:
        result = elderly_exposure({"elderly_casualty_count": 3, "casualty_count": 4})
        self.assertEqual(result["elderly_exposure"], 0.75)
        self.assertEqual(result["basis"], "recorded_casualty_age")

    def test_area_proxy_when_age_absent(self) -> None:
        result = elderly_exposure({"area_elderly_population_share": 0.28})
        self.assertEqual(result["elderly_exposure"], 0.28)
        self.assertEqual(result["basis"], "ageing_area_proxy")

    def test_unavailable_when_no_signal(self) -> None:
        result = elderly_exposure({"segment_id": "x"})
        self.assertIsNone(result["elderly_exposure"])
        self.assertEqual(result["basis"], "unavailable")


class AccessibilityTests(unittest.TestCase):
    def test_full_provision_scores_high(self) -> None:
        result = accessibility_provision(
            {"pedestrian_crossing": "yes", "refuge_island": "yes", "dropped_kerb": "yes", "lit": "yes"}
        )
        self.assertEqual(result["provision_score"], 100.0)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["missing_provisions"], [])

    def test_missing_provisions_listed(self) -> None:
        result = accessibility_provision(
            {"pedestrian_crossing": "yes", "refuge_island": "no", "dropped_kerb": "no", "lit": "yes"}
        )
        self.assertLess(result["provision_score"], 100.0)
        self.assertIn("refuge_island", result["missing_provisions"])
        self.assertIn("dropped_kerb", result["missing_provisions"])

    def test_unknown_provisions_reduce_coverage(self) -> None:
        result = accessibility_provision({"pedestrian_crossing": "yes"})
        self.assertLess(result["coverage"], 1.0)

    def test_no_known_provisions_yields_none(self) -> None:
        result = accessibility_provision({"segment_id": "x"})
        self.assertIsNone(result["provision_score"])


class CountermeasureTests(unittest.TestCase):
    def test_missing_provisions_map_to_measures(self) -> None:
        measures = recommend_countermeasures(["refuge_island", "dropped_kerb"])
        codes = {m["code"] for m in measures}
        self.assertIn("central_refuge_island", codes)
        self.assertIn("dropped_kerb_tactile", codes)


class ScoringTests(unittest.TestCase):
    def test_high_exposure_low_provision_is_high_priority(self) -> None:
        scored = score_segment(
            {
                "segment_id": "s1",
                "elderly_casualty_count": 4,
                "casualty_count": 5,
                "pedestrian_crossing": "no",
                "refuge_island": "no",
                "dropped_kerb": "no",
                "lit": "no",
                "involves_vru": "yes",
            }
        )
        self.assertIsNotNone(scored["elderly_disabled_priority"])
        self.assertGreater(scored["elderly_disabled_priority"], 50.0)
        self.assertTrue(scored["countermeasures"])

    def test_well_provisioned_segment_is_low_priority(self) -> None:
        scored = score_segment(
            {
                "segment_id": "s2",
                "area_elderly_population_share": 0.2,
                "pedestrian_crossing": "yes",
                "refuge_island": "yes",
                "dropped_kerb": "yes",
                "lit": "yes",
            }
        )
        self.assertEqual(scored["elderly_disabled_priority"], 0.0)
        self.assertEqual(scored["countermeasures"], [])


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_distinct_elderly_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments = root / "segments.csv"
            fieldnames = [
                "segment_id", "elderly_casualty_count", "casualty_count",
                "pedestrian_crossing", "refuge_island", "dropped_kerb", "lit", "involves_vru",
            ]
            with segments.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for i in range(8):
                    writer.writerow({
                        "segment_id": f"s{i}",
                        "elderly_casualty_count": i % 4,
                        "casualty_count": 4,
                        "pedestrian_crossing": "yes" if i % 2 else "no",
                        "refuge_island": "no",
                        "dropped_kerb": "yes" if i % 3 else "no",
                        "lit": "yes",
                        "involves_vru": "yes" if i % 2 else "no",
                    })

            out = root / "elderly"
            result = run_elderly_disabled_assessment(segments_path=segments, output_dir=out)

            self.assertEqual(result["summary"]["segment_count"], 8)
            self.assertTrue(Path(result["priority_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertIn("countermeasure_demand", payload["summary"])
            # Countermeasure library is surfaced for the intervention briefs.
            self.assertIn("central_refuge_island", payload["countermeasure_library"]["refuge_island"]["code"])


if __name__ == "__main__":
    unittest.main()
