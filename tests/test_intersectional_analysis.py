from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.intersectional_analysis import (
    INTERSECTIONAL_DIMENSIONS,
    run_intersectional_analysis,
    stratify,
)


def _casualty(sex: str, age: str, area: str, disability: str, fatal: bool):
    return {
        "sex": sex,
        "age_band": age,
        "area_type": area,
        "disability": disability,
        "severity_level": "fatal" if fatal else "injury",
    }


class StratifyTests(unittest.TestCase):
    def test_suppresses_small_strata(self) -> None:
        rows = [_casualty("F", "65+", "rural", "no", False) for _ in range(4)]
        result = stratify(rows, ["sex"], min_cell=10)
        self.assertEqual(result["strata"], [])
        self.assertEqual(result["strata_suppressed"], 1)
        self.assertEqual(result["suppressed_casualties"], 4)

    def test_surviving_strata_carry_fatal_share(self) -> None:
        rows = [_casualty("M", "25-64", "rural", "no", i < 3) for i in range(12)]
        result = stratify(rows, ["sex"], min_cell=10)
        self.assertEqual(len(result["strata"]), 1)
        stratum = result["strata"][0]
        self.assertEqual(stratum["sex"], "M")
        self.assertEqual(stratum["casualty_count"], 12)
        self.assertEqual(stratum["fatal_count"], 3)
        self.assertAlmostEqual(stratum["fatal_share"], 0.25)

    def test_intersectional_dimensions_combine(self) -> None:
        rows = (
            [_casualty("F", "65+", "rural", "yes", False) for _ in range(11)]
            + [_casualty("M", "25-64", "urban", "no", True) for _ in range(11)]
        )
        result = stratify(rows, list(INTERSECTIONAL_DIMENSIONS), min_cell=10)
        self.assertEqual(len(result["strata"]), 2)
        keys = {(s["sex"], s["age_band"], s["area_type"], s["disability"]) for s in result["strata"]}
        self.assertIn(("F", "65+", "rural", "yes"), keys)

    def test_missing_dimension_values_become_unknown(self) -> None:
        rows = [{"severity_level": "injury"} for _ in range(10)]
        result = stratify(rows, ["sex"], min_cell=10)
        self.assertEqual(result["strata"][0]["sex"], "unknown")


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_suppressed_strata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            casualties = root / "casualties.csv"
            fieldnames = ["sex", "age_band", "area_type", "disability", "severity_level"]
            with casualties.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                # A large F/65+/rural stratum that survives, plus singletons.
                for i in range(20):
                    writer.writerow({
                        "sex": "F", "age_band": "65+", "area_type": "rural",
                        "disability": "no", "severity_level": "fatal" if i < 4 else "injury",
                    })
                writer.writerow({
                    "sex": "M", "age_band": "0-17", "area_type": "urban",
                    "disability": "yes", "severity_level": "injury",
                })

            out = root / "intersectional"
            result = run_intersectional_analysis(casualties_path=casualties, output_dir=out, min_cell=10)

            self.assertTrue(Path(result["strata_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())
            self.assertGreaterEqual(result["intersectional_suppressed"], 1)  # the singleton

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertTrue(payload["privacy"]["aggregate_only"])
            self.assertEqual(payload["privacy"]["k_anonymity_min_cell"], 10)
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            # The surviving sex stratum is present; the singleton is gone.
            sex_strata = payload["sex_disaggregated"]["strata"]
            self.assertTrue(any(s["sex"] == "F" for s in sex_strata))


if __name__ == "__main__":
    unittest.main()
