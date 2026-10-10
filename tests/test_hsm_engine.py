"""Unit tests for the AASHTO Highway Safety Manual (HSM) Empirical Bayes engine."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.hsm_engine import (
    CALIBRATED_HSM_SPFS,
    SpfCoefficients,
    compute_empirical_bayes_segment,
    export_hsm_screening_artifacts,
    screen_road_network_hsm,
)


class TestHsmEngine(unittest.TestCase):
    def test_calibrated_spfs_catalog(self) -> None:
        self.assertIn("rural_two_lane_two_way", CALIBRATED_HSM_SPFS)
        self.assertIn("urban_arterial_divided", CALIBRATED_HSM_SPFS)
        self.assertIn("motorway_freeway", CALIBRATED_HSM_SPFS)

        r2u = CALIBRATED_HSM_SPFS["rural_two_lane_two_way"]
        self.assertEqual(r2u.facility_class, "rural_two_lane_two_way")
        self.assertLess(r2u.beta_0, 0.0)
        self.assertGreater(r2u.beta_1, 0.5)
        self.assertGreater(r2u.overdispersion_k, 0.0)

    def test_spf_prediction_properties(self) -> None:
        spf = CALIBRATED_HSM_SPFS["rural_two_lane_two_way"]

        # Longer segment has proportionally higher predicted crashes
        pred_1km = spf.predict_annual_crashes(aadt=5000, length_km=1.0)
        pred_2km = spf.predict_annual_crashes(aadt=5000, length_km=2.0)
        self.assertAlmostEqual(pred_2km, pred_1km * 2.0, places=4)

        # Higher AADT produces higher predicted crashes
        pred_low_aadt = spf.predict_annual_crashes(aadt=2000, length_km=1.0)
        pred_high_aadt = spf.predict_annual_crashes(aadt=8000, length_km=1.0)
        self.assertGreater(pred_high_aadt, pred_low_aadt)

        # Calibration factor C scales linearly
        pred_calibrated = spf.predict_annual_crashes(aadt=5000, length_km=1.0, calibration_factor_c=1.2)
        self.assertAlmostEqual(pred_calibrated, pred_1km * 1.2, places=4)

        # Zero length or zero AADT returns zero
        self.assertEqual(spf.predict_annual_crashes(aadt=0, length_km=1.0), 0.0)
        self.assertEqual(spf.predict_annual_crashes(aadt=5000, length_km=0.0), 0.0)

    def test_empirical_bayes_weight_and_psi(self) -> None:
        # High crash site: observed is much greater than predicted
        res_high = compute_empirical_bayes_segment(
            segment_id="seg-hazardous",
            observed_crashes=[8, 10, 9],  # avg 9 crashes/yr
            aadt=3000,
            length_km=1.0,
            facility_class="rural_two_lane_two_way",
        )

        # EB Weight w must be between 0 and 1
        self.assertGreater(res_high.eb_weight_w, 0.0)
        self.assertLess(res_high.eb_weight_w, 1.0)

        # Expected crashes must be between predicted and observed
        self.assertGreater(res_high.eb_expected_annual, res_high.spf_predicted_annual)
        self.assertLess(res_high.eb_expected_annual, res_high.observed_crashes_annual)

        # PSI must be positive for hazardous site
        self.assertGreater(res_high.psi_excess_crashes_annual, 0.0)
        self.assertEqual(res_high.screening_band, "high_priority")

        # Low crash site: observed is 0
        res_safe = compute_empirical_bayes_segment(
            segment_id="seg-safe",
            observed_crashes=[0, 0, 0],
            aadt=3000,
            length_km=1.0,
            facility_class="rural_two_lane_two_way",
        )
        self.assertLessEqual(res_safe.observed_crashes_annual, 0.0)
        # Even with 0 observed crashes, EB expected is slightly above 0 due to structural risk (SPF)
        self.assertGreater(res_safe.eb_expected_annual, 0.0)
        # PSI should be negative (performing better than expectation)
        self.assertLess(res_safe.psi_excess_crashes_annual, 0.0)

    def test_network_screening_ranking(self) -> None:
        segments = [
            {"segment_id": "seg-nominal", "observed_crashes": 2, "length_km": 1.0, "aadt": 3000},
            {"segment_id": "seg-worst", "observed_crashes": 15, "length_km": 1.0, "aadt": 3000},
            {"segment_id": "seg-best", "observed_crashes": 0, "length_km": 1.0, "aadt": 3000},
        ]

        ranked = screen_road_network_hsm(segments, default_facility_class="rural_two_lane_two_way")

        self.assertEqual(len(ranked), 3)
        # Rank 1 must be seg-worst because it has highest excess crashes (PSI)
        self.assertEqual(ranked[0].segment_id, "seg-worst")
        self.assertEqual(ranked[0].priority_rank, 1)

        # Rank 3 must be seg-best
        self.assertEqual(ranked[2].segment_id, "seg-best")
        self.assertEqual(ranked[2].priority_rank, 3)

    def test_export_hsm_artifacts(self) -> None:
        segments = [
            {"segment_id": "seg-1", "observed_crashes": 6, "length_km": 1.2, "aadt": 4500},
            {"segment_id": "seg-2", "observed_crashes": 1, "length_km": 0.8, "aadt": 2000},
        ]
        results = screen_road_network_hsm(segments)

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = export_hsm_screening_artifacts(results, output_dir=tmp_dir, network_label="pilot_test")
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue(Path(paths["csv"]).exists())
            self.assertTrue(Path(paths["md"]).exists())
            self.assertTrue(Path(paths["manifest"]).exists())

            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_segments_screened"], 2)
            self.assertIn("results", payload)


if __name__ == "__main__":
    unittest.main()
