from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.nwrsa import (
    assess_network,
    classify_sections,
    run_nwrsa_assessment,
    score_in_built_safety,
)


class InBuiltSafetyScoringTests(unittest.TestCase):
    def test_safe_section_scores_low(self) -> None:
        safe = {
            "maxspeed_numeric": 50,
            "width_numeric": 8.0,
            "sinuosity": 1.0,
            "lanes_numeric": 4,
            "node_degree_max": 2,
            "road_class_rank": 1,
        }
        result = score_in_built_safety(safe)
        self.assertIsNotNone(result["score"])
        self.assertLess(result["score"], 15.0)
        # All criteria except roadside_structures are present here.
        self.assertGreater(result["coverage"], 0.9)

    def test_unsafe_rural_section_scores_high(self) -> None:
        unsafe = {
            "maxspeed_numeric": 100,
            "width_numeric": 5.0,
            "sinuosity": 1.3,
            "lanes_numeric": 2,
            "node_degree_max": 5,
            "road_class_rank": 5,
            "bridge": "yes",
        }
        result = score_in_built_safety(unsafe)
        self.assertGreater(result["score"], 85.0)
        self.assertEqual(result["coverage"], 1.0)

    def test_missing_inputs_renormalise_with_coverage(self) -> None:
        partial = {"maxspeed_numeric": 90}  # only one criterion present
        result = score_in_built_safety(partial)
        self.assertIsNotNone(result["score"])
        self.assertLess(result["coverage"], 1.0)
        self.assertIn("speed_environment", result["contributions"])

    def test_no_inputs_yields_no_score(self) -> None:
        result = score_in_built_safety({"segment_id": "x"})
        self.assertIsNone(result["score"])
        self.assertEqual(result["coverage"], 0.0)


class ClassificationTests(unittest.TestCase):
    def test_requires_at_least_three_categories(self) -> None:
        with self.assertRaises(ValueError):
            classify_sections([10.0, 50.0, 90.0], categories=2)

    def test_three_category_split_orders_low_to_high(self) -> None:
        scores = [5.0, 10.0, 50.0, 60.0, 95.0, 99.0]
        bands = classify_sections(scores, categories=3)
        # Lowest scores -> category 1, highest -> category 3.
        self.assertEqual(bands[0], 1)
        self.assertEqual(bands[-1], 3)
        self.assertTrue(all(1 <= b <= 3 for b in bands))

    def test_none_scores_pass_through(self) -> None:
        bands = classify_sections([None, 10.0, 90.0], categories=3)
        self.assertIsNone(bands[0])


class NetworkAssessmentTests(unittest.TestCase):
    def test_combined_score_blends_reactive_and_proactive(self) -> None:
        rows = [
            {  # safe geometry, no crashes
                "segment_id": "s-safe",
                "maxspeed_numeric": 50, "width_numeric": 8.0, "sinuosity": 1.0,
                "lanes_numeric": 4, "node_degree_max": 2, "road_class_rank": 1,
                "segment_length_m": 200, "crash_count": 0, "fatal_crash_count": 0,
            },
            {  # unsafe geometry + fatal crash
                "segment_id": "s-danger",
                "maxspeed_numeric": 100, "width_numeric": 5.0, "sinuosity": 1.3,
                "lanes_numeric": 2, "node_degree_max": 5, "road_class_rank": 5,
                "segment_length_m": 200, "crash_count": 3, "fatal_crash_count": 1,
            },
        ]
        results = assess_network(rows, categories=3)
        safe = next(r for r in results if r["section_id"] == "s-safe")
        danger = next(r for r in results if r["section_id"] == "s-danger")
        # The dangerous section must score worse on every axis and never rank
        # safer than the safe one. (Full category-distribution coverage with a
        # spread network is asserted in PipelineTests.)
        self.assertLess(safe["combined_nwrsa_score"], danger["combined_nwrsa_score"])
        self.assertGreater(danger["proactive_score"], safe["proactive_score"])
        self.assertGreaterEqual(danger["safety_category"], safe["safety_category"])


class PipelineTests(unittest.TestCase):
    def test_run_nwrsa_assessment_writes_directive_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sections = root / "sections.csv"
            fieldnames = [
                "segment_id", "maxspeed_numeric", "width_numeric", "sinuosity",
                "lanes_numeric", "node_degree_max", "road_class_rank",
                "segment_length_m", "crash_count", "fatal_crash_count",
            ]
            with sections.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for i in range(9):
                    writer.writerow({
                        "segment_id": f"sec-{i}",
                        "maxspeed_numeric": 50 + i * 6,
                        "width_numeric": 8.0 - i * 0.3,
                        "sinuosity": 1.0 + i * 0.03,
                        "lanes_numeric": 4 if i < 3 else 2,
                        "node_degree_max": 2 + (i % 4),
                        "road_class_rank": 1 + (i % 5),
                        "segment_length_m": 200,
                        "crash_count": i,
                        "fatal_crash_count": 1 if i >= 7 else 0,
                    })

            out = root / "nwrsa"
            result = run_nwrsa_assessment(sections_path=sections, output_dir=out, categories=3)

            self.assertEqual(result["section_count"], 9)
            self.assertTrue(Path(result["classification_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            payload = json.loads(Path(result["assessment_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["categories"], 3)
            self.assertIn("(EU) 2019/1936", payload["directive"])
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            # All three mandated categories are populated for a spread network.
            distribution = result["category_distribution"]
            self.assertEqual(set(distribution.keys()), {"1", "2", "3"})
            self.assertEqual(sum(distribution.values()), 9)


if __name__ == "__main__":
    unittest.main()
