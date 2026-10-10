from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.rural_sectioning import (
    derive_rural_features,
    run_rural_sectioning,
    section_network,
    section_road_segment,
)


class SectioningTests(unittest.TestCase):
    def test_long_segment_splits_into_200m_sections(self) -> None:
        sections = section_road_segment(
            {"segment_id": "edge-1", "segment_length_m": 1000, "crash_count": 4, "fatal_crash_count": 2},
            section_length_m=200,
        )
        self.assertEqual(len(sections), 5)
        self.assertEqual(sections[0]["section_id"], "edge-1#s00")
        self.assertEqual(sections[0]["section_count"], 5)
        # Length and crashes are apportioned evenly across the 5 sections.
        self.assertAlmostEqual(sections[0]["segment_length_m"], 200.0)
        self.assertAlmostEqual(sum(s["crash_count"] for s in sections), 4.0, places=3)
        self.assertAlmostEqual(sum(s["fatal_crash_count"] for s in sections), 2.0, places=3)

    def test_short_segment_stays_single_section(self) -> None:
        sections = section_road_segment(
            {"segment_id": "short", "segment_length_m": 120, "crash_count": 1},
            section_length_m=200,
        )
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["crash_count"], 1.0)

    def test_missing_length_defaults_to_one_section(self) -> None:
        sections = section_road_segment({"segment_id": "x"}, section_length_m=200)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["segment_length_m"], 200.0)


class RuralFeatureTests(unittest.TestCase):
    def test_sharp_fast_single_carriageway_has_high_mechanism_exposure(self) -> None:
        features = derive_rural_features(
            {
                "maxspeed_numeric": 100,
                "width_numeric": 5.5,
                "sinuosity": 1.35,
                "lanes_numeric": 2,
                "road_class_rank": 4,
                "crash_count": 0,
            }
        )
        self.assertEqual(features["curvature_class"], "sharp")
        self.assertTrue(features["is_single_carriageway"])
        self.assertTrue(features["narrow_carriageway"])
        self.assertGreater(features["run_off_road_exposure"], 0.7)
        self.assertGreater(features["head_on_exposure"], 0.6)
        self.assertTrue(features["sparse_cell"])

    def test_straight_wide_divided_road_has_low_head_on_exposure(self) -> None:
        features = derive_rural_features(
            {
                "maxspeed_numeric": 90,
                "width_numeric": 9.0,
                "sinuosity": 1.0,
                "lanes_numeric": 4,
                "oneway": "yes",
                "road_class_rank": 1,
                "crash_count": 3,
            }
        )
        self.assertEqual(features["curvature_class"], "straight")
        self.assertFalse(features["is_single_carriageway"])
        self.assertFalse(features["narrow_carriageway"])
        self.assertLess(features["head_on_exposure"], 0.3)
        self.assertFalse(features["sparse_cell"])

    def test_rural_exposure_index_tracks_road_class(self) -> None:
        high = derive_rural_features({"road_class_rank": 1})["rural_exposure_index"]
        low = derive_rural_features({"road_class_rank": 5})["rural_exposure_index"]
        self.assertGreater(high, low)


class PipelineTests(unittest.TestCase):
    def test_run_rural_sectioning_writes_sections_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments = root / "segments.csv"
            fieldnames = [
                "segment_id", "segment_length_m", "maxspeed_numeric", "width_numeric",
                "sinuosity", "lanes_numeric", "road_class_rank", "crash_count", "fatal_crash_count",
            ]
            with segments.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow({
                    "segment_id": "e1", "segment_length_m": 600, "maxspeed_numeric": 90,
                    "width_numeric": 6.0, "sinuosity": 1.2, "lanes_numeric": 2,
                    "road_class_rank": 4, "crash_count": 3, "fatal_crash_count": 1,
                })
                writer.writerow({
                    "segment_id": "e2", "segment_length_m": 150, "maxspeed_numeric": 70,
                    "width_numeric": 7.0, "sinuosity": 1.0, "lanes_numeric": 2,
                    "road_class_rank": 3, "crash_count": 0, "fatal_crash_count": 0,
                })

            out = root / "rural"
            result = run_rural_sectioning(segments_path=segments, output_dir=out)

            # e1 (600m) -> 3 sections, e2 (150m) -> 1 section = 4 total.
            self.assertEqual(result["summary"]["section_count"], 4)
            self.assertTrue(Path(result["sections_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["section_length_m"], 200.0)
            self.assertEqual(payload["input_segment_count"], 2)
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertIn("curvature_distribution", payload["summary"])

            with Path(result["sections_csv_path"]).open() as handle:
                section_rows = list(csv.DictReader(handle))
            self.assertEqual(len(section_rows), 4)
            # Crash apportionment preserved across e1's three sections.
            e1_crashes = sum(
                float(r["crash_count"]) for r in section_rows if r["parent_segment_id"] == "e1"
            )
            self.assertAlmostEqual(e1_crashes, 3.0, places=2)


if __name__ == "__main__":
    unittest.main()
