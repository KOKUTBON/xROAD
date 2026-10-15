from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.scientific_benchmark import (
    ESTIMATOR_LABELS,
    run_scientific_benchmark,
)


def _write_dataset(path: Path, offset: int) -> None:
    fieldnames = [
        "segment_id",
        "occurred_year",
        "crash_count",
        "fatal_crash_count",
        "injury_crash_count",
        "fatalities_total",
        "injuries_total",
        "mean_match_distance_m",
        "segment_length_m",
        "exposure_proxy_index",
        "road_class_rank",
        "maxspeed_numeric",
        "lanes_numeric",
        "width_numeric",
        "node_degree_max",
        "highway",
    ]
    rows = []
    for segment in range(12):
        base = (segment % 4) + offset
        for year in (2020, 2021, 2022):
            crash_count = max(0, base + (1 if year == 2022 and segment % 3 == 0 else 0))
            rows.append(
                {
                    "segment_id": f"seg-{segment:02d}",
                    "occurred_year": year,
                    "crash_count": crash_count,
                    "fatal_crash_count": 1 if crash_count >= 4 else 0,
                    "injury_crash_count": max(crash_count - 1, 0),
                    "fatalities_total": 1 if crash_count >= 4 else 0,
                    "injuries_total": max(crash_count - 1, 0),
                    "mean_match_distance_m": 3.0 + base,
                    "segment_length_m": 100.0 + base * 12,
                    "exposure_proxy_index": 0.5 + base * 0.3,
                    "road_class_rank": 1 + (segment % 4),
                    "maxspeed_numeric": 50 + base * 10,
                    "lanes_numeric": 1 + (segment % 2),
                    "width_numeric": 5.0 + base,
                    "node_degree_max": 2 + (segment % 3),
                    "highway": "residential",
                }
            )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ScientificBenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_all_baselines_with_uncertainty(self) -> None:
        try:
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("ML stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ds_a = root / "a.csv"
            ds_b = root / "b.csv"
            _write_dataset(ds_a, offset=0)
            _write_dataset(ds_b, offset=1)
            output_dir = root / "bench"

            result = run_scientific_benchmark(
                datasets=[("city_a", ds_a), ("city_b", ds_b)],
                output_dir=output_dir,
                holdout_year=2022,
                rf_n_estimators=25,
                bootstrap_iterations=50,
                spatial_folds=3,
            )

            metrics_path = Path(result["metrics_path"])
            self.assertTrue(metrics_path.exists())
            self.assertTrue(Path(result["report_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            payload = json.loads(metrics_path.read_text(encoding="utf-8"))

            # All four recognised estimators are evaluated.
            for label in ESTIMATOR_LABELS:
                self.assertIn(label, payload["estimators"])
                estimator = payload["estimators"][label]
                self.assertIn("mean_poisson_deviance", estimator["metrics"])
                # Bootstrap CI is present and ordered.
                ci = estimator["deviance_ci"]
                self.assertLessEqual(ci["ci95_low"], ci["ci95_high"])
                # Calibration deciles present.
                self.assertGreater(len(estimator["calibration"]), 0)
                # Spatial CV present.
                self.assertIn(label, payload["spatial_cross_validation"])

            # SPF and EB are the named road-safety baselines.
            self.assertIn("spf_poisson", ESTIMATOR_LABELS)
            self.assertIn("empirical_bayes", ESTIMATOR_LABELS)
            self.assertEqual(payload["holdout_year"], 2022)
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(len(payload["holdout_ranking_by_deviance"]), len(ESTIMATOR_LABELS))

    def test_requires_exposure_features(self) -> None:
        try:
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("ML stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "bad.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["segment_id", "occurred_year", "crash_count"]
                )
                writer.writeheader()
                writer.writerow({"segment_id": "s1", "occurred_year": 2020, "crash_count": 1})
                writer.writerow({"segment_id": "s1", "occurred_year": 2022, "crash_count": 2})

            with self.assertRaises(RuntimeError):
                run_scientific_benchmark(
                    datasets=[("x", path)],
                    output_dir=root / "out",
                    holdout_year=2022,
                )


if __name__ == "__main__":
    unittest.main()
