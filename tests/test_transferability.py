from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.transferability import evaluate_frequency_transferability


class TransferabilityTests(unittest.TestCase):
    def test_evaluate_frequency_transferability_writes_metrics(self) -> None:
        try:
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("ML stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bari_path = root / "bari.csv"
            foggia_path = root / "foggia.csv"
            output_dir = root / "transfer"

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
                "highway",
                "oneway",
                "ref",
                "bridge",
                "junction",
                "access",
                "tunnel",
                "bearing_bin",
                "lanes_numeric",
                "maxspeed_numeric",
                "width_numeric",
                "is_roundabout",
                "node_degree_max",
                "road_class_rank",
                "segment_name_present",
            ]

            def write_dataset(path: Path, label_offset: int) -> None:
                rows = []
                for segment_id, base, highway in [
                    ("seg-1", 0 + label_offset, "residential"),
                    ("seg-2", 2 + label_offset, "primary"),
                    ("seg-3", 1 + label_offset, "secondary"),
                ]:
                    for year in [2019, 2020, 2021]:
                        holdout_spike = 1 if year == 2021 and segment_id == "seg-2" else 0
                        crash_count = max(0, base + (1 if year == 2020 else 0) + holdout_spike)
                        rows.append(
                            {
                                "segment_id": segment_id,
                                "occurred_year": year,
                                "crash_count": crash_count,
                                "fatal_crash_count": 1 if crash_count >= 3 else 0,
                                "injury_crash_count": max(crash_count - 1, 0),
                                "fatalities_total": 1 if crash_count >= 3 else 0,
                                "injuries_total": max(crash_count - 1, 0),
                                "mean_match_distance_m": 3.0 + base,
                                "segment_length_m": 100.0 + base * 10,
                                "highway": highway,
                                "oneway": "False",
                                "ref": "",
                                "bridge": "",
                                "junction": "",
                                "access": "",
                                "tunnel": "",
                                "bearing_bin": "north_south" if segment_id != "seg-2" else "east_west",
                                "lanes_numeric": 1 + min(base, 2),
                                "maxspeed_numeric": 30 + base * 10,
                                "width_numeric": 5 + base,
                                "is_roundabout": "False",
                                "node_degree_max": 2 + base,
                                "road_class_rank": 1 + min(base, 3),
                                "segment_name_present": 1,
                            }
                        )
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            write_dataset(bari_path, label_offset=0)
            write_dataset(foggia_path, label_offset=1)

            result = evaluate_frequency_transferability(
                datasets=[("bari", bari_path), ("foggia_core", foggia_path)],
                output_dir=output_dir,
                holdout_year=2021,
                rf_n_estimators=25,
            )

            metrics_path = Path(result["metrics_path"])
            predictions_path = output_dir / "frequency_transferability_predictions.csv"
            self.assertTrue(metrics_path.exists())
            self.assertTrue(predictions_path.exists())

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["holdout_year"], 2021)
            self.assertEqual(metrics["random_forest_n_estimators"], 25)
            self.assertEqual(metrics["profiling"]["dataset_count"], 2)
            self.assertEqual(metrics["profiling"]["requested_mode_count"], 4)
            self.assertGreater(metrics["profiling"]["runtime_seconds"], 0.0)
            self.assertEqual(metrics["training_config"]["task"], "frequency_transferability_evaluation")
            self.assertEqual(
                metrics["training_config"]["split_strategy"],
                "leave_one_jurisdiction_out_temporal_holdout",
            )
            self.assertEqual(metrics["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(len(metrics["lineage"]["upstream_inputs"]), 2)
            self.assertIn("bari", metrics["within_jurisdiction_temporal"])
            self.assertIn("foggia_core", metrics["cross_jurisdiction_temporal"])
            self.assertIn("bari", metrics["cross_jurisdiction_cold_start"])
            self.assertIn("foggia_core", metrics["cross_jurisdiction_history_free"])
            self.assertIn("random_forest_poisson_metrics", metrics["within_jurisdiction_temporal"]["bari"])
            self.assertEqual(
                metrics["within_jurisdiction_temporal"]["bari"]["random_forest_config"]["n_estimators"],
                25,
            )
            self.assertEqual(
                metrics["cross_jurisdiction_temporal"]["foggia_core"]["train_jurisdictions"],
                ["bari"],
            )
            self.assertGreater(
                len(metrics["cross_jurisdiction_cold_start"]["bari"]["zeroed_temporal_history_features"]),
                0,
            )
            self.assertNotIn(
                "prior_year_crash_count",
                metrics["cross_jurisdiction_history_free"]["foggia_core"]["model_feature_columns"],
            )

    def test_evaluate_frequency_transferability_respects_requested_modes(self) -> None:
        try:
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("ML stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bari_path = root / "bari.csv"
            foggia_path = root / "foggia.csv"
            output_dir = root / "transfer"

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
                "highway",
                "oneway",
            ]

            def write_dataset(path: Path, offset: int) -> None:
                rows = []
                for segment_id, base in [("seg-1", 0 + offset), ("seg-2", 1 + offset)]:
                    for year in [2020, 2021]:
                        crash_count = base + (1 if year == 2021 and segment_id == "seg-2" else 0)
                        rows.append(
                            {
                                "segment_id": segment_id,
                                "occurred_year": year,
                                "crash_count": crash_count,
                                "fatal_crash_count": 1 if crash_count >= 2 else 0,
                                "injury_crash_count": max(crash_count - 1, 0),
                                "fatalities_total": 1 if crash_count >= 2 else 0,
                                "injuries_total": max(crash_count - 1, 0),
                                "mean_match_distance_m": 2.0 + base,
                                "segment_length_m": 100.0 + base * 10,
                                "highway": "residential",
                                "oneway": "False",
                            }
                        )
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            write_dataset(bari_path, offset=0)
            write_dataset(foggia_path, offset=1)

            result = evaluate_frequency_transferability(
                datasets=[("bari", bari_path), ("foggia", foggia_path)],
                output_dir=output_dir,
                holdout_year=2021,
                rf_n_estimators=10,
                modes=["cross_jurisdiction_temporal"],
            )

            self.assertEqual(result["requested_modes"], ["cross_jurisdiction_temporal"])
            self.assertEqual(result["within_jurisdiction_temporal"], {})
            self.assertEqual(result["cross_jurisdiction_cold_start"], {})
            self.assertEqual(result["cross_jurisdiction_history_free"], {})
            self.assertIn("bari", result["cross_jurisdiction_temporal"])

            metrics = json.loads(Path(result["metrics_path"]).read_text(encoding="utf-8"))
            self.assertEqual(metrics["requested_modes"], ["cross_jurisdiction_temporal"])
            self.assertEqual(metrics["within_jurisdiction_temporal"], {})
