import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.intervention_feature_store import (
    LABEL_SOURCE_OBSERVED,
    LABEL_SOURCE_SYNTHETIC,
    OUTCOME_COLUMNS,
    SPLIT_STRATEGY,
    assign_temporal_split,
    build_city_records,
    build_intervention_feature_store,
    detect_observed_interventions,
    run_leakage_checks,
)
from road_risk_modeling.countermeasure_knowledge import load_countermeasure_library

_COLUMNS = [
    "segment_id",
    "occurred_year",
    "crash_count",
    "fatal_crash_count",
    "injury_crash_count",
    "fatalities_total",
    "injuries_total",
    "segment_length_m",
    "highway",
    "maxspeed_numeric",
    "lanes_numeric",
    "is_roundabout",
    "crash_density_per_km",
    "fatalities_per_km",
    "injuries_per_km",
]


def _row(segment_id: str, year: int, **overrides) -> dict:
    base = {
        "segment_id": segment_id,
        "occurred_year": year,
        "crash_count": 2,
        "fatal_crash_count": 0,
        "injury_crash_count": 2,
        "fatalities_total": 0,
        "injuries_total": 3,
        "segment_length_m": 500,
        "highway": "residential",
        "maxspeed_numeric": 50,
        "lanes_numeric": 2,
        "is_roundabout": 0,
        "crash_density_per_km": 4.0,
        "fatalities_per_km": 0.0,
        "injuries_per_km": 6.0,
    }
    base.update(overrides)
    return base


class ObservedInterventionTests(unittest.TestCase):
    def test_detects_speed_lane_and_roundabout_changes(self) -> None:
        series = [
            _row("s1", 2019),
            _row("s1", 2020, maxspeed_numeric=30),
            _row("s1", 2021, maxspeed_numeric=30, lanes_numeric=1),
            _row("s1", 2022, maxspeed_numeric=30, lanes_numeric=1, is_roundabout=1),
        ]
        events = detect_observed_interventions(series)
        codes = {(event["intervention_code"], event["intervention_year"]) for event in events}
        self.assertEqual(
            codes,
            {
                ("speed_management", 2020),
                ("lane_reallocation", 2021),
                ("roundabout_conversion", 2022),
            },
        )

    def test_static_attributes_yield_no_events(self) -> None:
        series = [_row("s1", year) for year in (2019, 2020, 2021)]
        self.assertEqual(detect_observed_interventions(series), [])


class CityRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.library = load_countermeasure_library()

    def test_observed_record_has_outcomes_and_baseline_features(self) -> None:
        rows = [
            _row("s1", 2019, crash_density_per_km=6.0),
            _row("s1", 2020, crash_density_per_km=6.0),
            _row("s1", 2021, maxspeed_numeric=30, crash_density_per_km=3.0),
            _row("s1", 2022, maxspeed_numeric=30, crash_density_per_km=3.0),
        ]
        records = build_city_records(city_key="testville", rows=rows, library=self.library)
        observed = [r for r in records if r["label_source"] == LABEL_SOURCE_OBSERVED]
        self.assertEqual(len(observed), 1)
        record = observed[0]
        self.assertEqual(record["intervention_code"], "speed_management")
        self.assertEqual(record["intervention_year"], 2021)
        self.assertFalse(record["is_synthetic"])
        self.assertEqual(record["feature_occurred_year"], 2020)
        self.assertEqual(record["before_crash_density_per_km"], 6.0)
        self.assertEqual(record["outcome_after_crash_density_per_km"], 3.0)
        self.assertEqual(record["outcome_crash_density_ratio"], 0.5)
        self.assertEqual(record["split_strategy"], SPLIT_STRATEGY)

    def test_synthetic_records_are_flagged_and_cite_a_countermeasure(self) -> None:
        rows = []
        for index in range(200):
            for year in (2019, 2020, 2021, 2022):
                rows.append(_row(f"seg-{index}", year))
        records = build_city_records(city_key="testville", rows=rows, library=self.library)
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record["label_source"], LABEL_SOURCE_SYNTHETIC)
            self.assertTrue(record["is_synthetic"])
            self.assertTrue(record["countermeasure_id"])
            self.assertLess(record["feature_occurred_year"], record["intervention_year"])

    def test_temporal_split_assignment(self) -> None:
        self.assertEqual(assign_temporal_split(2022, max_year=2022), "test")
        self.assertEqual(assign_temporal_split(2021, max_year=2022), "validation")
        self.assertEqual(assign_temporal_split(2019, max_year=2022), "train")


class LeakageCheckTests(unittest.TestCase):
    def _valid_record(self) -> dict:
        return {
            "object_id": "s1",
            "city_key": "testville",
            "intervention_year": 2021,
            "temporal_split": "train",
            "feature_occurred_year": 2020,
            "feature_maxspeed_numeric": 50,
        }

    def test_passes_on_clean_records(self) -> None:
        report = run_leakage_checks([self._valid_record()])
        self.assertEqual(report["violations"], 0)
        self.assertEqual(report["checked_records"], 1)

    def test_rejects_outcome_column_in_feature_block(self) -> None:
        record = self._valid_record()
        record[f"feature_{OUTCOME_COLUMNS[0]}"] = 1.0
        with self.assertRaises(RuntimeError) as ctx:
            run_leakage_checks([record])
        self.assertIn("leaked into features", str(ctx.exception))

    def test_rejects_baseline_year_at_or_after_intervention(self) -> None:
        record = self._valid_record()
        record["feature_occurred_year"] = 2021
        with self.assertRaises(RuntimeError) as ctx:
            run_leakage_checks([record])
        self.assertIn("strictly before intervention year", str(ctx.exception))

    def test_rejects_train_years_overlapping_test_period(self) -> None:
        train = self._valid_record()
        train["intervention_year"] = 2022
        train["feature_occurred_year"] = 2021
        test = self._valid_record()
        test["temporal_split"] = "test"
        with self.assertRaises(RuntimeError) as ctx:
            run_leakage_checks([train, test])
        self.assertIn("overlap the test period", str(ctx.exception))


class BuildTests(unittest.TestCase):
    def test_end_to_end_build_with_fixture_cities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            city_paths = {}
            for city in ("alpha", "beta"):
                rows = []
                for index in range(120):
                    for year in (2019, 2020, 2021, 2022):
                        overrides = {}
                        # Give a handful of alpha segments an observed change.
                        if city == "alpha" and index < 3 and year >= 2021:
                            overrides["maxspeed_numeric"] = 30
                        rows.append(_row(f"{city}-seg-{index}", year, **overrides))
                path = tmp_path / f"{city}.csv"
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
                    writer.writeheader()
                    writer.writerows(rows)
                city_paths[city] = path

            output_dir = tmp_path / "store"
            result = build_intervention_feature_store(
                city_datasets=city_paths, output_dir=output_dir
            )
            self.assertIn(result["matrix_format"], {"parquet", "csv"})
            self.assertTrue(Path(result["matrix_path"]).exists())
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["contract"]["split_strategy"], SPLIT_STRATEGY)
            self.assertIn("lineage", manifest)
            card = json.loads(Path(result["dataset_card_path"]).read_text(encoding="utf-8"))
            self.assertEqual(card["leakage_checks"]["violations"], 0)
            self.assertIn(LABEL_SOURCE_OBSERVED, card["stats"]["label_source_counts"])
            self.assertIn(LABEL_SOURCE_SYNTHETIC, card["stats"]["label_source_counts"])
            self.assertLess(card["stats"]["synthetic_share"], 1.0)
            self.assertTrue(card["known_biases"])
            self.assertEqual(set(card["stats"]["city_counts"]), {"alpha", "beta"})


if __name__ == "__main__":
    unittest.main()
