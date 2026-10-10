from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.modeling import train_frequency_baseline, train_severity_baseline


class ModelingTests(unittest.TestCase):
    def test_train_frequency_baseline_writes_metrics_and_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            aggregate_path = root / "segment_year_metrics.csv"
            output_dir = root / "models"

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
                "lanes_numeric",
                "maxspeed_numeric",
                "width_numeric",
                "is_roundabout",
            ]

            rows = []
            for segment_id, base_crashes, highway in [
                ("seg-1", 0, "residential"),
                ("seg-2", 2, "primary"),
                ("seg-3", 1, "secondary"),
                ("seg-4", 3, "tertiary"),
            ]:
                for year in [2019, 2020, 2021]:
                    year_offset = 1 if year == 2020 else 0
                    holdout_spike = 1 if year == 2021 and segment_id in {"seg-2", "seg-4"} else 0
                    crash_count = base_crashes + year_offset + holdout_spike
                    rows.append(
                        {
                            "segment_id": segment_id,
                            "occurred_year": year,
                            "crash_count": crash_count,
                            "fatal_crash_count": 1 if crash_count >= 3 else 0,
                            "injury_crash_count": max(crash_count - 1, 0),
                            "fatalities_total": 1 if crash_count >= 3 else 0,
                            "injuries_total": max(crash_count - 1, 0),
                            "mean_match_distance_m": 4.0 + base_crashes,
                            "segment_length_m": 100.0 + base_crashes * 25,
                            "highway": highway,
                            "oneway": "False",
                            "ref": "",
                            "bridge": "",
                            "junction": "",
                            "access": "",
                            "tunnel": "",
                            "lanes_numeric": 1 + base_crashes,
                            "maxspeed_numeric": 30 + base_crashes * 10,
                            "width_numeric": 5 + base_crashes,
                            "is_roundabout": "False",
                        }
                    )

            with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            try:
                result = train_frequency_baseline(aggregate_path, output_dir=output_dir, holdout_year=2021)
            except RuntimeError as exc:
                if "Modeling dependencies are required" in str(exc):
                    self.skipTest("ML stack not installed")
                raise

            metrics_path = Path(result["metrics_path"])
            predictions_path = output_dir / "holdout_predictions.csv"

            self.assertTrue(metrics_path.exists())
            self.assertTrue(predictions_path.exists())

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["holdout_year"], 2021)
            self.assertEqual(metrics["test_rows"], 4)
            self.assertIn("prior_year_crash_count", metrics["temporal_history_features"])
            self.assertIn("random_forest_poisson_metrics", metrics)
            self.assertIn("last_year_baseline_metrics", metrics)
            self.assertEqual(metrics["training_config"]["task"], "segment_frequency_baseline")
            self.assertEqual(metrics["training_config"]["split_strategy"], "temporal_holdout_year")
            self.assertEqual(metrics["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(metrics["lineage"]["publishable_outputs"][0]["role"], "holdout_segment_predictions")

            with predictions_path.open(encoding="utf-8", newline="") as handle:
                prediction_rows = list(csv.DictReader(handle))

            self.assertEqual(len(prediction_rows), 4)
            self.assertIn("linear_poisson_prediction", prediction_rows[0])
            self.assertIn("random_forest_poisson_prediction", prediction_rows[0])
            self.assertIn("last_year_baseline_prediction", prediction_rows[0])
            self.assertIn("naive_mean_prediction", prediction_rows[0])

    def test_train_frequency_baseline_drops_all_null_numeric_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            aggregate_path = root / "segment_year_metrics.csv"
            output_dir = root / "models"

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
                "lanes_numeric",
                "maxspeed_numeric",
                "width_numeric",
                "is_roundabout",
            ]

            rows = []
            for segment_id, base_crashes, highway in [
                ("seg-1", 0, "residential"),
                ("seg-2", 2, "primary"),
            ]:
                for year in [2019, 2020, 2021]:
                    crash_count = base_crashes + (1 if year >= 2020 else 0)
                    rows.append(
                        {
                            "segment_id": segment_id,
                            "occurred_year": year,
                            "crash_count": crash_count,
                            "fatal_crash_count": 1 if crash_count >= 3 else 0,
                            "injury_crash_count": max(crash_count - 1, 0),
                            "fatalities_total": 1 if crash_count >= 3 else 0,
                            "injuries_total": max(crash_count - 1, 0),
                            "mean_match_distance_m": 2.0 + base_crashes,
                            "segment_length_m": 100.0 + base_crashes * 10,
                            "highway": highway,
                            "oneway": "False",
                            "ref": "",
                            "bridge": "",
                            "junction": "",
                            "access": "",
                            "tunnel": "",
                            "lanes_numeric": 1 + base_crashes,
                            "maxspeed_numeric": 30 + base_crashes * 10,
                            "width_numeric": "",
                            "is_roundabout": "False",
                        }
                    )

            with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            try:
                result = train_frequency_baseline(aggregate_path, output_dir=output_dir, holdout_year=2021)
            except RuntimeError as exc:
                if "Modeling dependencies are required" in str(exc):
                    self.skipTest("ML stack not installed")
                raise

            metrics = json.loads(Path(result["metrics_path"]).read_text(encoding="utf-8"))
            self.assertIn("width_numeric", metrics["dropped_numeric_features"])
            self.assertNotIn("width_numeric", metrics["feature_columns"])
            self.assertEqual(metrics["training_config"]["feature_inventory"]["dropped_numeric_features"], ["width_numeric"])

    def test_train_severity_baseline_writes_metrics_and_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            aggregate_path = root / "segment_year_metrics.csv"
            matched_path = root / "matched_records.jsonl"
            output_dir = root / "severity"

            aggregate_fieldnames = [
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
                "node_degree_max",
                "poi_any_count",
                "exposure_proxy_index",
                "lanes_numeric",
                "maxspeed_numeric",
                "width_numeric",
                "is_roundabout",
            ]
            aggregate_rows = [
                {
                    "segment_id": "seg-1",
                    "occurred_year": 2019,
                    "crash_count": 1,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 1,
                    "fatalities_total": 0,
                    "injuries_total": 1,
                    "mean_match_distance_m": 3.0,
                    "segment_length_m": 90.0,
                    "highway": "residential",
                    "oneway": "False",
                    "ref": "",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "north_south",
                    "node_degree_max": 2,
                    "poi_any_count": 1,
                    "exposure_proxy_index": 0.2,
                    "lanes_numeric": 1,
                    "maxspeed_numeric": 30,
                    "width_numeric": 5,
                    "is_roundabout": "False",
                },
                {
                    "segment_id": "seg-1",
                    "occurred_year": 2020,
                    "crash_count": 2,
                    "fatal_crash_count": 1,
                    "injury_crash_count": 1,
                    "fatalities_total": 1,
                    "injuries_total": 2,
                    "mean_match_distance_m": 3.5,
                    "segment_length_m": 90.0,
                    "highway": "residential",
                    "oneway": "False",
                    "ref": "",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "north_south",
                    "node_degree_max": 2,
                    "poi_any_count": 2,
                    "exposure_proxy_index": 0.3,
                    "lanes_numeric": 1,
                    "maxspeed_numeric": 30,
                    "width_numeric": 5,
                    "is_roundabout": "False",
                },
                {
                    "segment_id": "seg-1",
                    "occurred_year": 2021,
                    "crash_count": 1,
                    "fatal_crash_count": 1,
                    "injury_crash_count": 0,
                    "fatalities_total": 1,
                    "injuries_total": 0,
                    "mean_match_distance_m": 2.0,
                    "segment_length_m": 90.0,
                    "highway": "residential",
                    "oneway": "False",
                    "ref": "",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "north_south",
                    "node_degree_max": 2,
                    "poi_any_count": 2,
                    "exposure_proxy_index": 0.35,
                    "lanes_numeric": 1,
                    "maxspeed_numeric": 30,
                    "width_numeric": 5,
                    "is_roundabout": "False",
                },
                {
                    "segment_id": "seg-2",
                    "occurred_year": 2019,
                    "crash_count": 2,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 2,
                    "fatalities_total": 0,
                    "injuries_total": 3,
                    "mean_match_distance_m": 4.0,
                    "segment_length_m": 140.0,
                    "highway": "primary",
                    "oneway": "True",
                    "ref": "SS16",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "east_west",
                    "node_degree_max": 4,
                    "poi_any_count": 5,
                    "exposure_proxy_index": 0.8,
                    "lanes_numeric": 2,
                    "maxspeed_numeric": 70,
                    "width_numeric": 7,
                    "is_roundabout": "False",
                },
                {
                    "segment_id": "seg-2",
                    "occurred_year": 2020,
                    "crash_count": 2,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 2,
                    "fatalities_total": 0,
                    "injuries_total": 2,
                    "mean_match_distance_m": 5.0,
                    "segment_length_m": 140.0,
                    "highway": "primary",
                    "oneway": "True",
                    "ref": "SS16",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "east_west",
                    "node_degree_max": 4,
                    "poi_any_count": 6,
                    "exposure_proxy_index": 0.85,
                    "lanes_numeric": 2,
                    "maxspeed_numeric": 70,
                    "width_numeric": 7,
                    "is_roundabout": "False",
                },
                {
                    "segment_id": "seg-2",
                    "occurred_year": 2021,
                    "crash_count": 1,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 1,
                    "fatalities_total": 0,
                    "injuries_total": 1,
                    "mean_match_distance_m": 4.0,
                    "segment_length_m": 140.0,
                    "highway": "primary",
                    "oneway": "True",
                    "ref": "SS16",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": "east_west",
                    "node_degree_max": 4,
                    "poi_any_count": 6,
                    "exposure_proxy_index": 0.9,
                    "lanes_numeric": 2,
                    "maxspeed_numeric": 70,
                    "width_numeric": 7,
                    "is_roundabout": "False",
                },
            ]
            with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=aggregate_fieldnames)
                writer.writeheader()
                writer.writerows(aggregate_rows)

            matched_rows = [
                {
                    "crash_id": "a",
                    "segment_id": "seg-1",
                    "occurred_year": 2019,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 1,
                    "match_distance_m": 2.0,
                    "weather_code": "1",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
                {
                    "crash_id": "b",
                    "segment_id": "seg-1",
                    "occurred_year": 2020,
                    "severity_level": "fatal",
                    "fatalities": 1,
                    "injuries": 0,
                    "match_distance_m": 1.5,
                    "weather_code": "2",
                    "roadway_type": "intersection",
                    "intersection_type": "intersection",
                },
                {
                    "crash_id": "c",
                    "segment_id": "seg-1",
                    "occurred_year": 2020,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 2,
                    "match_distance_m": 1.8,
                    "weather_code": "2",
                    "roadway_type": "intersection",
                    "intersection_type": "intersection",
                },
                {
                    "crash_id": "d",
                    "segment_id": "seg-1",
                    "occurred_year": 2021,
                    "severity_level": "fatal",
                    "fatalities": 1,
                    "injuries": 0,
                    "match_distance_m": 1.1,
                    "weather_code": "3",
                    "roadway_type": "intersection",
                    "intersection_type": "intersection",
                },
                {
                    "crash_id": "e",
                    "segment_id": "seg-2",
                    "occurred_year": 2019,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 1,
                    "match_distance_m": 3.0,
                    "weather_code": "1",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
                {
                    "crash_id": "f",
                    "segment_id": "seg-2",
                    "occurred_year": 2019,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 2,
                    "match_distance_m": 3.2,
                    "weather_code": "1",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
                {
                    "crash_id": "g",
                    "segment_id": "seg-2",
                    "occurred_year": 2020,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 1,
                    "match_distance_m": 4.1,
                    "weather_code": "1",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
                {
                    "crash_id": "h",
                    "segment_id": "seg-2",
                    "occurred_year": 2020,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 1,
                    "match_distance_m": 4.0,
                    "weather_code": "2",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
                {
                    "crash_id": "i",
                    "segment_id": "seg-2",
                    "occurred_year": 2021,
                    "severity_level": "injury",
                    "fatalities": 0,
                    "injuries": 1,
                    "match_distance_m": 3.8,
                    "weather_code": "1",
                    "roadway_type": "road_segment",
                    "intersection_type": "non_intersection",
                },
            ]
            matched_path.write_text(
                "\n".join(json.dumps(row) for row in matched_rows) + "\n",
                encoding="utf-8",
            )

            try:
                result = train_severity_baseline(
                    matched_path,
                    aggregate_path,
                    output_dir=output_dir,
                    holdout_year=2021,
                )
            except RuntimeError as exc:
                if "Modeling dependencies are required" in str(exc):
                    self.skipTest("ML stack not installed")
                raise

            metrics_path = Path(result["metrics_path"])
            predictions_path = output_dir / "holdout_severity_predictions.csv"

            self.assertTrue(metrics_path.exists())
            self.assertTrue(predictions_path.exists())

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["holdout_year"], 2021)
            self.assertEqual(metrics["test_rows"], 2)
            self.assertEqual(metrics["training_config"]["task"], "crash_severity_baseline")
            self.assertEqual(metrics["training_config"]["label_column"], "is_fatal_crash")
            self.assertEqual(len(metrics["lineage"]["upstream_inputs"]), 2)
            self.assertEqual(metrics["test_fatal_count"], 1)
            self.assertIn("poi_any_count", metrics["feature_columns"])
            self.assertIn("exposure_proxy_index", metrics["feature_columns"])
            self.assertIn("bearing_bin", metrics["feature_columns"])
            self.assertIn("random_forest_classifier_metrics", metrics)
            self.assertIn("prior_segment_fatality_metrics", metrics)

            with predictions_path.open(encoding="utf-8", newline="") as handle:
                prediction_rows = list(csv.DictReader(handle))

            self.assertEqual(len(prediction_rows), 2)
            self.assertIn("logistic_fatal_probability", prediction_rows[0])
            self.assertIn("random_forest_fatal_probability", prediction_rows[0])
            self.assertIn("prior_segment_fatality_probability", prediction_rows[0])
            self.assertIn("naive_fatal_probability", prediction_rows[0])
