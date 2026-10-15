"""Automated Quality Gate Tests for Segment-Time Panel & Baseline Engines.

Directly verifies the test requirements mandated in the Research Audit:
- test_weather_join_never_uses_future_observation
- test_no_negative_exposure
- test_crash_road_match_within_threshold
- test_test_period_after_training_period
- test_spatial_group_kfold_zero_leakage
- test_leakage_blacklist_rejection
- test_baselines_and_gbdt_convergence
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.segment_panel_engine import (
    LEAKAGE_BLACKLIST,
    CrashPointRecord,
    RoadSegmentRecord,
    WeatherRecord,
    backward_join_weather,
    build_segment_week_panel,
    export_panel_artifacts,
    filter_leakage_features,
    snap_crashes_to_segments,
)
from road_risk_modeling.panel_baselines_engine import (
    HistoricalExposureRateModel,
    NegativeBinomialExposureModel,
    PoissonGlmExposureModel,
    PoissonGradientBoostedModel,
    RegularizedLogisticModel,
    _poisson_deviance,
    _top_k_capture_curve,
    evaluate_model_suite,
)
from road_risk_modeling.spatial_temporal_validation import (
    forward_temporal_split,
    space_time_blocked_split,
    spatial_group_kfold_split,
)


class TestSegmentPanelEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_segments = [
            RoadSegmentRecord(
                segment_id="seg-1",
                name="Via Cavour",
                latitude=41.1180,
                longitude=16.8690,
                length_km=1.20,
                aadt=15000.0,
                road_class="urban_arterial",
                speed_limit_kmh=50.0,
                lanes=4,
                spatial_group="group_north",
            ),
            RoadSegmentRecord(
                segment_id="seg-2",
                name="Via Sparano",
                latitude=41.1215,
                longitude=16.8710,
                length_km=0.80,
                aadt=3500.0,
                road_class="pedestrian_shared",
                speed_limit_kmh=30.0,
                lanes=2,
                spatial_group="group_north",
            ),
            RoadSegmentRecord(
                segment_id="seg-3",
                name="Via Caldarola",
                latitude=41.1090,
                longitude=16.8850,
                length_km=1.50,
                aadt=18000.0,
                road_class="suburban_arterial",
                speed_limit_kmh=60.0,
                lanes=4,
                spatial_group="group_south",
            ),
        ]

        self.sample_crashes = [
            # Exactly at seg-1
            CrashPointRecord("cr-1", "2026-01-08T10:00:00Z", 41.1180, 16.8690, "slight"),
            # ~20m from seg-2 (within 50m)
            CrashPointRecord("cr-2", "2026-01-15T14:30:00Z", 41.1216, 16.8711, "serious"),
            # ~1km away from everything (unmatched)
            CrashPointRecord("cr-far", "2026-01-20T08:00:00Z", 41.1500, 16.9200, "slight"),
        ]

        self.sample_weather = [
            WeatherRecord("METEO-1", "2026-01-08T08:00:00Z", 2.5, 9.0),
            WeatherRecord("METEO-1", "2026-01-08T09:30:00Z", 4.0, 8.5),
            WeatherRecord("METEO-1", "2026-01-08T11:00:00Z", 15.0, 5.0), # Future relative to 10:00!
            WeatherRecord("METEO-1", "2026-01-15T12:00:00Z", 0.0, 12.0),
        ]

    def test_weather_join_never_uses_future_observation(self) -> None:
        """Verify weather join strictly selects observations at or before prediction time (no future leakage)."""
        target_time = datetime.fromisoformat("2026-01-08T10:00:00+00:00")
        w_joined = backward_join_weather(target_time, self.sample_weather, tolerance_hours=2.0)

        # Must pick 09:30:00Z (precip 4.0 mm), NOT 11:00:00Z (precip 15.0 mm)!
        self.assertEqual(w_joined["precipitation_mm"], 4.0)
        self.assertEqual(w_joined["temperature_c"], 8.5)
        self.assertEqual(w_joined["weather_joined_lag_minutes"], 30.0)

    def test_no_negative_exposure(self) -> None:
        """Verify that traffic exposure vehicle_km and log_exposure are strictly non-negative."""
        panel = build_segment_week_panel(
            segments=self.sample_segments,
            crashes=self.sample_crashes,
            weather=self.sample_weather,
            weeks_count=4,
            base_start_iso="2026-01-05T00:00:00Z",
        )
        for obs in panel.observations:
            self.assertGreater(obs.exposure_vehicle_km, 0.0)
            self.assertGreaterEqual(obs.log_exposure, 0.0)
            self.assertGreaterEqual(obs.crash_count, 0)
            self.assertIn(obs.any_crash, {0, 1})

    def test_crash_road_match_within_threshold(self) -> None:
        """Verify nearest-neighbor snapping respects the 50m threshold and excludes far crashes."""
        matched, unmatched = snap_crashes_to_segments(self.sample_crashes, self.sample_segments, max_distance_m=50.0)

        # cr-1 snapped to seg-1
        self.assertEqual(len(matched["seg-1"]), 1)
        self.assertEqual(matched["seg-1"][0]["crash_id"], "cr-1")
        self.assertLessEqual(matched["seg-1"][0]["road_distance_m"], 5.0)

        # cr-2 snapped to seg-2
        self.assertEqual(len(matched["seg-2"]), 1)
        self.assertEqual(matched["seg-2"][0]["crash_id"], "cr-2")
        self.assertLessEqual(matched["seg-2"][0]["road_distance_m"], 50.0)

        # cr-far is in unmatched
        unmatched_ids = [c["crash_id"] for c in unmatched]
        self.assertIn("cr-far", unmatched_ids)

    def test_test_period_after_training_period(self) -> None:
        """Verify forward temporal split guarantees train.period_start.max() < test.period_start.min()."""
        panel = build_segment_week_panel(
            segments=self.sample_segments,
            crashes=self.sample_crashes,
            weeks_count=6,
            base_start_iso="2026-01-05T00:00:00Z",
        )
        obs_dicts = [o.to_dict() for o in panel.observations]
        split = forward_temporal_split(obs_dicts, test_fraction=0.33)

        self.assertGreater(len(split.train_indices), 0)
        self.assertGreater(len(split.test_indices), 0)
        self.assertLess(split.train_end, split.test_start)

    def test_spatial_group_kfold_zero_leakage(self) -> None:
        """Verify spatial GroupKFold guarantees zero geographic group overlap between train and test."""
        panel = build_segment_week_panel(
            segments=self.sample_segments,
            crashes=self.sample_crashes,
            weeks_count=4,
        )
        obs_dicts = [o.to_dict() for o in panel.observations]
        split = spatial_group_kfold_split(obs_dicts, n_splits=2, fold_idx=0)

        train_groups = {obs_dicts[i]["spatial_group"] for i in split.train_indices}
        test_groups = {obs_dicts[i]["spatial_group"] for i in split.test_indices}

        overlap = train_groups.intersection(test_groups)
        self.assertEqual(len(overlap), 0, f"Geographic leakage detected across folds: {overlap}")

    def test_leakage_blacklist_rejection(self) -> None:
        """Verify feature blacklist strictly filters out post-crash variables."""
        polluted_features = {
            "speed_limit_kmh": 50.0,
            "lanes": 2,
            "fatality_count": 1,
            "serious_injuries": 2,
            "ambulance_response_min": 8.5,
            "police_citation": "excessive_speed",
            "vehicle_damage": "total_loss",
            "crash_severity": "fatal",
            "precipitation_mm": 5.0,
        }
        cleaned = filter_leakage_features(polluted_features)

        for blacklisted in LEAKAGE_BLACKLIST:
            self.assertNotIn(blacklisted, cleaned)

        self.assertIn("speed_limit_kmh", cleaned)
        self.assertIn("lanes", cleaned)
        self.assertIn("precipitation_mm", cleaned)

    def test_baselines_and_gbdt_convergence(self) -> None:
        """Verify Historical Rate, Poisson GLM, NegBin, Logistic, and Poisson GBDT train and evaluate."""
        panel = build_segment_week_panel(
            segments=self.sample_segments,
            crashes=self.sample_crashes,
            weeks_count=6,
        )
        obs_dicts = [o.to_dict() for o in panel.observations]
        split = forward_temporal_split(obs_dicts, test_fraction=0.33)

        feature_cols = ["speed_limit_kmh", "lanes", "precipitation_mm"]
        X_train = [[obs_dicts[i][c] for c in feature_cols] for i in split.train_indices]
        y_train = [obs_dicts[i]["crash_count"] for i in split.train_indices]
        exp_train = [obs_dicts[i]["exposure_vehicle_km"] for i in split.train_indices]

        X_test = [[obs_dicts[i][c] for c in feature_cols] for i in split.test_indices]
        y_test = [obs_dicts[i]["crash_count"] for i in split.test_indices]
        exp_test = [obs_dicts[i]["exposure_vehicle_km"] for i in split.test_indices]

        report = evaluate_model_suite(
            X_train=X_train, y_train=y_train, exp_train=exp_train,
            X_test=X_test, y_test=y_test, exp_test=exp_test,
            feature_names=feature_cols,
        )

        self.assertEqual(len(report.model_benchmarks), 5)
        for m in report.model_benchmarks:
            self.assertGreaterEqual(m.poisson_deviance, 0.0)
            self.assertGreaterEqual(m.mae, 0.0)
            self.assertGreaterEqual(m.roc_auc, 0.0)
            self.assertLessEqual(m.roc_auc, 1.0)


if __name__ == "__main__":
    unittest.main()
