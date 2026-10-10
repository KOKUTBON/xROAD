from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.regional_comparison import (
    RegionPilot,
    assess_region,
    compare_regions,
    run_regional_comparison,
)


def _section(speed: int, width: float, sinuosity: float, crashes: int, fatal: int):
    return {
        "segment_id": f"s-{speed}-{width}",
        "maxspeed_numeric": speed,
        "width_numeric": width,
        "sinuosity": sinuosity,
        "lanes_numeric": 2,
        "road_class_rank": 4,
        "segment_length_m": 200,
        "crash_count": crashes,
        "fatal_crash_count": fatal,
    }


def _region(region_id: str, country: str, rate: float, n: int = 12) -> RegionPilot:
    sections = [_section(70 + (i % 4) * 10, 7.0 - (i % 4) * 0.5, 1.0 + (i % 4) * 0.08, i % 5, 1 if i % 6 == 0 else 0) for i in range(n)]
    return RegionPilot(region_id=region_id, country=country, rural_fatality_rate=rate, sections=sections)


class AssessRegionTests(unittest.TestCase):
    def test_region_summary_has_distribution_and_score(self) -> None:
        summary = assess_region(_region("puglia", "IT", 80.0))
        self.assertEqual(summary["region_id"], "puglia")
        self.assertEqual(summary["section_count"], 12)
        self.assertIn("category_distribution", summary)
        self.assertIsNotNone(summary["mean_nwrsa_score"])


class CompareRegionsTests(unittest.TestCase):
    def test_eligible_when_three_regions_two_high_fatality_cross_border(self) -> None:
        regions = [
            _region("puglia", "IT", 85.0),     # above EU avg
            _region("occitanie", "FR", 78.0),  # above EU avg
            _region("uppsala", "SE", 40.0),    # below EU avg
        ]
        result = compare_regions(regions, eu_average_rural_fatality_rate=66.0)
        elig = result["eligibility"]
        self.assertTrue(elig["meets_min_regions"])
        self.assertEqual(elig["high_fatality_region_count"], 2)
        self.assertTrue(elig["meets_min_high_fatality"])
        self.assertTrue(elig["is_cross_border"])
        self.assertTrue(elig["eligible"])

    def test_ineligible_with_too_few_high_fatality_regions(self) -> None:
        regions = [
            _region("a", "IT", 85.0),
            _region("b", "FR", 40.0),
            _region("c", "SE", 38.0),
        ]
        result = compare_regions(regions, eu_average_rural_fatality_rate=66.0)
        self.assertFalse(result["eligibility"]["meets_min_high_fatality"])
        self.assertFalse(result["eligibility"]["eligible"])

    def test_ineligible_single_country(self) -> None:
        regions = [
            _region("a", "IT", 85.0),
            _region("b", "IT", 78.0),
            _region("c", "IT", 70.0),
        ]
        result = compare_regions(regions, eu_average_rural_fatality_rate=66.0)
        self.assertFalse(result["eligibility"]["is_cross_border"])
        self.assertFalse(result["eligibility"]["eligible"])


class PipelineTests(unittest.TestCase):
    def test_run_regional_comparison_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fieldnames = [
                "segment_id", "maxspeed_numeric", "width_numeric", "sinuosity",
                "lanes_numeric", "road_class_rank", "segment_length_m", "crash_count", "fatal_crash_count",
            ]
            specs = []
            for region_id, country, rate in [("puglia", "IT", 85.0), ("occitanie", "FR", 78.0), ("uppsala", "SE", 40.0)]:
                path = root / f"{region_id}.csv"
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    for i in range(12):
                        writer.writerow(_section(70 + (i % 4) * 10, 7.0 - (i % 4) * 0.5, 1.0 + (i % 4) * 0.08, i % 5, 1 if i % 6 == 0 else 0))
                specs.append({"region_id": region_id, "country": country, "rural_fatality_rate": rate, "path": str(path)})

            out = root / "comparison"
            result = run_regional_comparison(
                region_specs=specs, output_dir=out, eu_average_rural_fatality_rate=66.0
            )

            self.assertTrue(result["eligibility"]["eligible"])
            self.assertTrue(Path(result["comparison_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(payload["regions"]), 3)
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(len(payload["lineage"]["upstream_inputs"]), 3)


if __name__ == "__main__":
    unittest.main()
