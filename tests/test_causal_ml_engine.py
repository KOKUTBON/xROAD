"""Tests for Causal Machine Learning (Double Machine Learning) Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.causal_ml_engine import (
    CAUSAL_CONTRACT_VERSION,
    CAUSAL_ENGINE_VERSION,
    CausalTreatmentEffect,
    ObservationalUnit,
    SegmentCateEstimate,
    _fit_logistic_regression,
    _fit_ridge_regression,
    _predict_propensity,
    _predict_ridge,
    estimate_double_ml_treatment_effect,
    estimate_segment_cate_heterogeneity,
    export_causal_ml_artifacts,
    parse_observational_units,
)


class TestCausalMLEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_units_data = [
            # Treated units (SPEED_CAMERA)
            {
                "segment_id": f"seg-tr-{i}",
                "countermeasure_id": "SPEED_CAMERA",
                "treated": True,
                "baseline_crashes_pre": 7.0 + (i % 3) * 0.5,
                "outcome_crashes_post": 3.0 + (i % 3) * 0.4,
                "aadt": 18000.0 + i * 500,
                "operating_speed_kmh": 68.0,
                "speed_limit_kmh": 50.0,
                "lanes_numeric": 4,
                "width_m": 14.0,
                "is_urban": True,
                "intersection_density": 3.0,
            }
            for i in range(10)
        ] + [
            # Control units (Untreated)
            {
                "segment_id": f"seg-ctrl-{i}",
                "countermeasure_id": "SPEED_CAMERA",
                "treated": False,
                "baseline_crashes_pre": 6.8 + (i % 3) * 0.5,
                "outcome_crashes_post": 6.7 + (i % 3) * 0.4,
                "aadt": 17500.0 + i * 450,
                "operating_speed_kmh": 66.0,
                "speed_limit_kmh": 50.0,
                "lanes_numeric": 4,
                "width_m": 13.5,
                "is_urban": True,
                "intersection_density": 3.1,
            }
            for i in range(10)
        ]

    def test_parse_observational_units(self) -> None:
        units = parse_observational_units(self.sample_units_data)
        self.assertEqual(len(units), 20)
        self.assertEqual(units[0].segment_id, "seg-tr-0")
        self.assertTrue(units[0].treated)
        self.assertEqual(units[0].countermeasure_id, "SPEED_CAMERA")
        self.assertAlmostEqual(units[0].baseline_crashes_pre, 7.0)
        self.assertAlmostEqual(units[0].outcome_crashes_post, 3.0)

        # Test feature vector dimensions
        fv = units[0].feature_vector
        self.assertEqual(len(fv), 8)
        self.assertAlmostEqual(fv[0], 7.0)

    def test_ridge_regression_solver(self) -> None:
        # y = 1.0 + 2.0 * x1 + 3.0 * x2
        X = [
            [1.0, 2.0],
            [2.0, 1.0],
            [3.0, 4.0],
            [4.0, 3.0],
            [5.0, 5.0],
            [6.0, 2.0],
        ]
        Y = [1.0 + 2.0 * x[0] + 3.0 * x[1] for x in X]
        weights = _fit_ridge_regression(X, Y, alpha=0.01)
        self.assertEqual(len(weights), 3)

        preds = _predict_ridge(X, weights)
        for actual, pred in zip(Y, preds):
            self.assertAlmostEqual(actual, pred, delta=0.5)

    def test_logistic_regression_solver(self) -> None:
        # Simple separable binary data
        X = [[1.0], [2.0], [8.0], [9.0]]
        D = [0, 0, 1, 1]
        weights = _fit_logistic_regression(X, D, learning_rate=0.1, iterations=100)
        self.assertEqual(len(weights), 2)

        preds = _predict_propensity(X, weights)
        self.assertLess(preds[0], preds[-1])
        self.assertTrue(0.0 <= preds[0] <= 1.0)
        self.assertTrue(0.0 <= preds[-1] <= 1.0)

    def test_double_ml_treatment_effect_estimation(self) -> None:
        units = parse_observational_units(self.sample_units_data)
        effect, residuals = estimate_double_ml_treatment_effect(units, "SPEED_CAMERA", n_folds=3)

        self.assertIsInstance(effect, CausalTreatmentEffect)
        self.assertEqual(effect.countermeasure_id, "SPEED_CAMERA")
        self.assertEqual(effect.sample_size_total, 20)
        self.assertEqual(effect.sample_size_treated, 10)
        self.assertEqual(effect.sample_size_control, 10)

        # Expected causal reduction should be strongly negative (drop from ~7 to ~3.4)
        self.assertLess(effect.ate_crashes, -2.5)
        self.assertGreater(effect.standard_error, 0.0)
        self.assertTrue(effect.is_statistically_significant)
        self.assertLess(effect.p_value, 0.05)
        self.assertLess(effect.empirical_cmf, 0.70)
        self.assertGreater(effect.percent_reduction, 30.0)

        self.assertEqual(len(residuals), 20)

    def test_double_ml_insufficient_sample(self) -> None:
        small_data = self.sample_units_data[:5]
        units = parse_observational_units(small_data)
        with self.assertRaises(RuntimeError):
            estimate_double_ml_treatment_effect(units, "SPEED_CAMERA")

    def test_segment_cate_heterogeneity(self) -> None:
        units = parse_observational_units(self.sample_units_data)
        cate_list = estimate_segment_cate_heterogeneity(units, "SPEED_CAMERA", base_ate=-3.0)

        self.assertEqual(len(cate_list), 20)
        self.assertIsInstance(cate_list[0], SegmentCateEstimate)
        # Check sorted descending
        for i in range(len(cate_list) - 1):
            self.assertGreaterEqual(
                cate_list[i].predicted_annual_crash_reduction,
                cate_list[i + 1].predicted_annual_crash_reduction,
            )
        self.assertIn(cate_list[0].priority_tier, {"top_priority", "high_priority"})

    def test_export_causal_ml_artifacts(self) -> None:
        units = parse_observational_units(self.sample_units_data)
        effect, _ = estimate_double_ml_treatment_effect(units, "SPEED_CAMERA")
        cate = estimate_segment_cate_heterogeneity(units, "SPEED_CAMERA", effect.ate_crashes)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_files = export_causal_ml_artifacts(
                treatment_effects=[effect],
                cate_estimates=cate,
                output_dir=tmp_dir,
                network_label="test_network",
            )

            self.assertTrue(Path(out_files["treatment_effects_csv"]).exists())
            self.assertTrue(Path(out_files["cate_csv"]).exists())
            self.assertTrue(Path(out_files["bundle_json"]).exists())
            self.assertTrue(Path(out_files["briefing_md"]).exists())
            self.assertTrue(Path(out_files["manifest"]).exists())

            # Verify bundle content
            bundle = json.loads(Path(out_files["bundle_json"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["causal_engine_version"], CAUSAL_ENGINE_VERSION)
            self.assertEqual(bundle["contract_version"], CAUSAL_CONTRACT_VERSION)
            self.assertEqual(bundle["network_label"], "test_network")
            self.assertEqual(bundle["summary"]["total_countermeasures_evaluated"], 1)
            self.assertEqual(bundle["summary"]["statistically_significant_countermeasures"], 1)

            # Verify manifest
            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "causal_machine_learning_evaluation")
            self.assertIn("treatment_effects_csv", manifest["files"])
            self.assertIn("sha256", manifest["files"]["treatment_effects_csv"])


if __name__ == "__main__":
    unittest.main()
