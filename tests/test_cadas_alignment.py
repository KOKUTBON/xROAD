"""Tests for the CADaS / CARE alignment."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.cadas_alignment import (
    CADAS_ALIGNMENT_VERSION,
    CADAS_VARIABLE_MAP,
    LEVEL_MANDATORY,
    STATUS_GAP,
    build_cadas_alignment_bundle,
    cadas_coverage_gaps,
    export_canonical_to_cadas,
    to_cadas_record,
)
from road_risk_modeling.canonical_schema import CanonicalCrashRecord


def _record(**overrides) -> CanonicalCrashRecord:
    base = dict(
        crash_id="c-1",
        source_system="test",
        source_record_id=None,
        source_unique_key=None,
        source_member=None,
        source_row_number=None,
        occurred_at=None,
        occurred_year=2023,
        occurred_month=6,
        occurred_day=15,
        occurred_hour=14,
        occurred_minute=None,
        timestamp_precision="day",
        country_code="IT",
        region_code="ITF4",
        province_code=None,
        city_code=None,
        city_name="Bari",
        latitude=41.12,
        longitude=16.87,
        road_segment_id=None,
        roadway_type="urban",
        intersection_type="junction",
        weather_code="clear",
        light_condition="daylight",
        fatalities=1,
        injuries=2,
        severity_level="fatal",
    )
    base.update(overrides)
    return CanonicalCrashRecord(**base)


class ToCadasRecordTests(unittest.TestCase):
    def test_maps_core_accident_variables(self):
        cadas = to_cadas_record(_record())
        self.assertEqual(cadas["A.1"], "IT")
        self.assertEqual(cadas["A.2"], "c-1")
        self.assertEqual(cadas["A.3"], "2023-06-15")
        self.assertEqual(cadas["A.4"], 14)
        self.assertEqual(cadas["A.10"], 1)
        self.assertEqual(cadas["A.11"], 2)

    def test_date_derived_from_occurred_at_when_present(self):
        cadas = to_cadas_record(_record(occurred_at=__import__("datetime").datetime(2022, 1, 2, 9)))
        self.assertEqual(cadas["A.3"], "2022-01-02")

    def test_accepts_plain_dict(self):
        cadas = to_cadas_record(_record().to_dict())
        self.assertEqual(cadas["A.1"], "IT")

    def test_missing_date_parts_yield_none(self):
        cadas = to_cadas_record(_record(occurred_year=None, occurred_month=None, occurred_day=None))
        self.assertIsNone(cadas["A.3"])


class CoverageTests(unittest.TestCase):
    def test_every_mandatory_variable_is_covered(self):
        mandatory_gaps = [
            m for m in CADAS_VARIABLE_MAP
            if m.level == LEVEL_MANDATORY and m.status == STATUS_GAP
        ]
        self.assertEqual(mandatory_gaps, [], "No mandatory CADaS variable should be an uncovered gap")

    def test_gap_list_is_non_empty_and_well_formed(self):
        gaps = cadas_coverage_gaps()
        self.assertTrue(gaps)
        for gap in gaps:
            self.assertEqual(gap["status"], STATUS_GAP)
            self.assertIsNone(gap["canonical_field"])


class BundleTests(unittest.TestCase):
    def test_bundle_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_cadas_alignment_bundle(output_dir=tmp)
            self.assertEqual(payload["cadas_alignment_version"], CADAS_ALIGNMENT_VERSION)

            root = Path(tmp)
            for name in (
                "cadas_variable_map.csv",
                "cadas_alignment_bundle.json",
                "cadas_coverage_gaps.json",
                "cadas_alignment.md",
                "cadas_alignment_bundle.manifest.json",
            ):
                self.assertTrue((root / name).exists(), f"missing {name}")

            with (root / "cadas_variable_map.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), len(CADAS_VARIABLE_MAP))

            manifest = json.loads((root / "cadas_alignment_bundle.manifest.json").read_text())
            self.assertEqual(len(manifest["outputs"]), 4)
            self.assertEqual(
                payload["coverage"]["mandatory_covered"],
                payload["coverage"]["mandatory_total"],
            )


class ExportTests(unittest.TestCase):
    def test_export_round_trips_canonical_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "canonical.jsonl"
            with canonical.open("w", encoding="utf-8") as fh:
                fh.write(json.dumps(_record(crash_id="a").to_dict()) + "\n")
                fh.write("\n")  # blank line should be skipped
                fh.write(json.dumps(_record(crash_id="b", fatalities=0).to_dict()) + "\n")

            payload = export_canonical_to_cadas(canonical_path=canonical, output_dir=root / "out")
            self.assertEqual(payload["records_exported"], 2)

            out = root / "out"
            with (out / "crashes_cadas.jsonl").open(encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual([row["A.2"] for row in lines], ["a", "b"])

            with (out / "crashes_cadas.csv").open(encoding="utf-8") as fh:
                csv_rows = list(csv.DictReader(fh))
            self.assertEqual(len(csv_rows), 2)
            self.assertIn("A.1", csv_rows[0])


if __name__ == "__main__":
    unittest.main()
