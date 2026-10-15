from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.transferability_benchmark import build_transferability_benchmark_bundle


def _write_metrics(
    path: Path,
    *,
    dataset_labels: list[str],
    rf_n_estimators: int,
    runtime_seconds: float,
    within: dict[str, tuple[float, float]],
    temporal: dict[str, tuple[float, float]],
    cold_start: dict[str, tuple[float, float]],
    history_free: dict[str, tuple[float, float]],
    requested_modes: list[str] | None = None,
) -> None:
    def build_mode(entries: dict[str, tuple[float, float]]) -> dict[str, object]:
        payload: dict[str, object] = {}
        for label, (deviance, top_share) in entries.items():
            train_labels = [item for item in dataset_labels if item != label]
            if not train_labels:
                train_labels = [label]
            payload[label] = {
                "train_jurisdictions": train_labels,
                "test_rows": 12,
                "test_crash_total": 5,
                "random_forest_poisson_metrics": {
                    "mean_poisson_deviance": deviance,
                    "top_5pct_crash_share": top_share,
                },
            }
        return payload

    requested_modes = requested_modes or [
        "within_jurisdiction_temporal",
        "cross_jurisdiction_temporal",
        "cross_jurisdiction_cold_start",
        "cross_jurisdiction_history_free",
    ]

    path.write_text(
        json.dumps(
            {
                "holdout_year": 2021,
                "random_forest_n_estimators": rf_n_estimators,
                "requested_modes": requested_modes,
                "profiling": {
                    "runtime_seconds": runtime_seconds,
                },
                "dataset_inputs": [
                    {
                        "label": label,
                        "path": f"data/processed/aggregates/{label}/segment_year_metrics.csv",
                        "sha256": f"sha-{label}",
                        "rows": 100,
                        "crash_total": 10,
                    }
                    for label in dataset_labels
                ],
                "within_jurisdiction_temporal": build_mode(within),
                "cross_jurisdiction_temporal": build_mode(temporal),
                "cross_jurisdiction_cold_start": build_mode(cold_start),
                "cross_jurisdiction_history_free": build_mode(history_free),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


class TransferabilityBenchmarkTests(unittest.TestCase):
    def test_build_transferability_benchmark_bundle_compares_stacks_and_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "benchmark"

            four_city_path = root / "four_city_rf25.metrics.json"
            five_city_rf25_path = root / "five_city_rf25.metrics.json"
            five_city_rf100_path = root / "five_city_rf100.metrics.json"

            four_city_labels = [
                "bari",
                "foggia_municipality",
                "taranto_municipality",
                "lecce_municipality",
            ]
            five_city_labels = [
                *four_city_labels,
                "brindisi_municipality",
            ]

            _write_metrics(
                four_city_path,
                dataset_labels=four_city_labels,
                rf_n_estimators=25,
                runtime_seconds=8.0,
                within={label: (0.20, 0.40) for label in four_city_labels},
                temporal={label: (0.30, 0.32) for label in four_city_labels},
                cold_start={label: (0.38, 0.23) for label in four_city_labels},
                history_free={label: (0.40, 0.21) for label in four_city_labels},
            )
            _write_metrics(
                five_city_rf25_path,
                dataset_labels=five_city_labels,
                rf_n_estimators=25,
                runtime_seconds=10.0,
                within={label: (0.22, 0.39) for label in five_city_labels},
                temporal={label: (0.32, 0.30) for label in five_city_labels},
                cold_start={label: (0.41, 0.22) for label in five_city_labels},
                history_free={label: (0.43, 0.20) for label in five_city_labels},
            )
            _write_metrics(
                five_city_rf100_path,
                dataset_labels=five_city_labels,
                rf_n_estimators=100,
                runtime_seconds=18.0,
                within={label: (0.21, 0.40) for label in five_city_labels},
                temporal={label: (0.30, 0.34) for label in five_city_labels},
                cold_start={label: (0.36, 0.25) for label in five_city_labels},
                history_free={label: (0.38, 0.24) for label in five_city_labels},
            )

            manifest = build_transferability_benchmark_bundle(
                transferability_metrics_paths=[
                    four_city_path,
                    five_city_rf25_path,
                    five_city_rf100_path,
                ],
                benchmark_label="Expanded Municipality Transferability Benchmark",
                output_dir=output_dir,
            )

            self.assertEqual(
                manifest["transferability_benchmark_version"],
                "transferability_benchmark_v1",
            )
            self.assertEqual(manifest["stats"]["input_run_count"], 3)

            bundle_payload = json.loads(
                (output_dir / "transferability_benchmark.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                bundle_payload["benchmark_label"],
                "Expanded Municipality Transferability Benchmark",
            )
            self.assertEqual(bundle_payload["stats"]["stack_count"], 2)
            self.assertEqual(bundle_payload["stats"]["budget_count"], 2)

            comparison = bundle_payload["stack_comparisons"][0]
            self.assertEqual(comparison["from_dataset_count"], 4)
            self.assertEqual(comparison["to_dataset_count"], 5)
            self.assertEqual(comparison["added_targets"], ["brindisi_municipality"])

            five_city_profile = next(
                profile
                for profile in bundle_payload["budget_profiles"]
                if profile["stack_key"] == "__".join(five_city_labels)
            )
            self.assertEqual(five_city_profile["recommended_budget"], 100)
            self.assertIn("rf100", five_city_profile["rationale"])

            markdown = (output_dir / "transferability_benchmark.md").read_text(encoding="utf-8")
            self.assertIn("Expanded Municipality Transferability Benchmark", markdown)
            self.assertIn("Brindisi Municipality", markdown)

    def test_build_transferability_benchmark_bundle_ignores_duplicate_mode_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "benchmark"

            all_modes_path = root / "five_city_rf50_all_modes.metrics.json"
            temporal_only_path = root / "five_city_rf50_temporal.metrics.json"

            dataset_labels = [
                "bari",
                "foggia_municipality",
                "taranto_municipality",
                "lecce_municipality",
                "brindisi_municipality",
            ]

            _write_metrics(
                all_modes_path,
                dataset_labels=dataset_labels,
                rf_n_estimators=50,
                runtime_seconds=18.0,
                within={label: (0.21, 0.40) for label in dataset_labels},
                temporal={label: (0.30, 0.34) for label in dataset_labels},
                cold_start={label: (0.36, 0.25) for label in dataset_labels},
                history_free={label: (0.38, 0.24) for label in dataset_labels},
            )
            _write_metrics(
                temporal_only_path,
                dataset_labels=dataset_labels,
                rf_n_estimators=50,
                runtime_seconds=7.0,
                within={label: (0.99, 0.01) for label in dataset_labels},
                temporal={label: (0.45, 0.12) for label in dataset_labels},
                cold_start={label: (0.99, 0.01) for label in dataset_labels},
                history_free={label: (0.99, 0.01) for label in dataset_labels},
                requested_modes=["cross_jurisdiction_temporal"],
            )

            build_transferability_benchmark_bundle(
                transferability_metrics_paths=[
                    all_modes_path,
                    temporal_only_path,
                ],
                benchmark_label="Duplicate Mode Coverage Benchmark",
                output_dir=output_dir,
            )

            bundle_payload = json.loads(
                (output_dir / "transferability_benchmark.json").read_text(encoding="utf-8")
            )
            self.assertEqual(bundle_payload["stats"]["input_run_count"], 1)

            run = bundle_payload["runs"][0]
            self.assertEqual(run["runtime_seconds"], 18.0)
            self.assertEqual(
                run["requested_modes"],
                [
                    "within_jurisdiction_temporal",
                    "cross_jurisdiction_temporal",
                    "cross_jurisdiction_cold_start",
                    "cross_jurisdiction_history_free",
                ],
            )
            self.assertEqual(
                run["mode_summaries"]["cross_jurisdiction_temporal"][
                    "average_mean_poisson_deviance"
                ],
                0.30,
            )
            self.assertEqual(run["metrics_paths"], [str(all_modes_path)])
