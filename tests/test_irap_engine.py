"""Unit tests for the International Road Assessment Programme (iRAP) & SRIP engine."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.irap_engine import (
    IRAP_CONTRACT_VERSION,
    IRAP_ENGINE_VERSION,
    SRIP_COUNTERMEASURES,
    SRIP_VERSION,
    IrapSegmentRating,
    IrapUserScores,
    assess_segment_irap,
    calculate_irap_user_scores,
    export_irap_and_srip_artifacts,
    generate_safer_roads_investment_plan,
    srs_to_star_rating,
)


class TestIrapEngine(unittest.TestCase):
    def test_srs_to_star_rating_thresholds(self) -> None:
        # 5 Stars: < 5.0
        self.assertEqual(srs_to_star_rating(0.0), 5)
        self.assertEqual(srs_to_star_rating(4.9), 5)
        # 4 Stars: 5.0 to < 12.5
        self.assertEqual(srs_to_star_rating(5.0), 4)
        self.assertEqual(srs_to_star_rating(12.4), 4)
        # 3 Stars: 12.5 to < 25.0 (UN Minimum Target)
        self.assertEqual(srs_to_star_rating(12.5), 3)
        self.assertEqual(srs_to_star_rating(24.9), 3)
        # 2 Stars: 25.0 to < 50.0
        self.assertEqual(srs_to_star_rating(25.0), 2)
        self.assertEqual(srs_to_star_rating(49.9), 2)
        # 1 Star: >= 50.0
        self.assertEqual(srs_to_star_rating(50.0), 1)
        self.assertEqual(srs_to_star_rating(150.0), 1)

    def test_calculate_user_scores_high_risk_road(self) -> None:
        """High-speed undivided rural road with no pedestrian or bicycle infrastructure."""
        scores = calculate_irap_user_scores(
            operating_speed_kmh=100.0,
            lanes=2,
            is_divided=False,
            has_median_barrier=False,
            carriageway_width_m=6.0,
            sinuosity=1.2,
            has_roadside_barrier=False,
            roadside_hazard_severity=0.8,
            intersection_density_per_km=2.0,
            has_sidewalk=False,
            has_pedestrian_crossing=False,
            has_segregated_cycle_facility=False,
        )
        # In a high speed undivided unprotected corridor, VRUs and vehicles face severe risk
        self.assertLessEqual(scores.vehicle_stars, 2)
        self.assertLessEqual(scores.motorcycle_stars, 2)
        self.assertLessEqual(scores.bicycle_stars, 1)
        self.assertLessEqual(scores.pedestrian_stars, 1)
        self.assertFalse(scores.meets_un_target_4)
        self.assertEqual(scores.minimum_stars, 1)

    def test_calculate_user_scores_safe_modern_corridor(self) -> None:
        """Protected divided corridor with sidewalks, cycle tracks, and barriers."""
        scores = calculate_irap_user_scores(
            operating_speed_kmh=40.0,
            lanes=2,
            is_divided=True,
            has_median_barrier=True,
            carriageway_width_m=7.5,
            sinuosity=1.0,
            has_roadside_barrier=True,
            roadside_hazard_severity=0.1,
            intersection_density_per_km=0.5,
            has_sidewalk=True,
            has_pedestrian_crossing=True,
            has_segregated_cycle_facility=True,
        )
        self.assertGreaterEqual(scores.vehicle_stars, 4)
        self.assertGreaterEqual(scores.motorcycle_stars, 4)
        self.assertGreaterEqual(scores.bicycle_stars, 4)
        self.assertGreaterEqual(scores.pedestrian_stars, 4)
        self.assertTrue(scores.meets_un_target_4)
        self.assertGreaterEqual(scores.minimum_stars, 4)

    def test_assess_segment_irap(self) -> None:
        segment_data = {
            "segment_id": "bari-via-napoli-01",
            "length_km": 0.45,
            "aadt": 8500,
            "operating_speed_kmh": 60,
            "lanes": 2,
            "width": 7.0,
            "is_divided": False,
            "has_sidewalk": False,
            "has_segregated_cycle_facility": False,
        }
        rating = assess_segment_irap(segment_data)
        self.assertEqual(rating.segment_id, "bari-via-napoli-01")
        self.assertEqual(rating.length_km, 0.45)
        self.assertEqual(rating.aadt, 8500.0)
        self.assertIsInstance(rating.scores, IrapUserScores)
        self.assertIn("vehicle_occupant", rating.scores.to_dict())
        self.assertIn("meets_un_target_4", rating.scores.to_dict())

    def test_generate_srip_remedial_actions_and_bcr(self) -> None:
        """Verify SRIP countermeasure selection, FSI reduction, and BCR ranking."""
        high_risk_seg = assess_segment_irap({
            "segment_id": "dangerous-corridor-1",
            "length_km": 2.0,
            "aadt": 12000,
            "operating_speed_kmh": 80,
            "lanes": 2,
            "is_divided": False,
            "has_sidewalk": False,
            "has_segregated_cycle_facility": False,
        })
        safe_seg = assess_segment_irap({
            "segment_id": "safe-corridor-2",
            "length_km": 1.0,
            "aadt": 3000,
            "operating_speed_kmh": 35,
            "lanes": 2,
            "is_divided": True,
            "has_median_barrier": True,
            "has_sidewalk": True,
            "has_pedestrian_crossing": True,
            "has_segregated_cycle_facility": True,
        })

        plan = generate_safer_roads_investment_plan(
            [high_risk_seg, safe_seg],
            value_of_statistical_life_eur=1_500_000.0,
            value_of_serious_injury_eur=250_000.0,
            discount_rate=0.04,
            min_bcr_threshold=1.0,
        )

        # Safe segment should have no recommendations
        segment_ids_in_plan = {item.segment_id for item in plan}
        self.assertIn("dangerous-corridor-1", segment_ids_in_plan)
        self.assertNotIn("safe-corridor-2", segment_ids_in_plan)

        # High risk segment should have recommended investments with positive BCR
        self.assertGreater(len(plan), 0)
        top_item = plan[0]
        self.assertEqual(top_item.priority_rank, 1)
        self.assertGreater(top_item.benefit_cost_ratio, 1.0)
        self.assertGreater(top_item.expected_fsi_prevented_20yr, 0.0)
        self.assertGreater(top_item.present_value_benefits_eur, top_item.present_value_costs_eur)
        self.assertGreater(top_item.post_star_rating, top_item.pre_star_rating)

        # Check ranking order (descending BCR)
        for i in range(len(plan) - 1):
            self.assertGreaterEqual(plan[i].benefit_cost_ratio, plan[i + 1].benefit_cost_ratio)
            self.assertEqual(plan[i].priority_rank, i + 1)

    def test_export_irap_and_srip_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            seg = assess_segment_irap({
                "segment_id": "seg-test-101",
                "length_km": 1.2,
                "aadt": 9000,
                "operating_speed_kmh": 70,
                "lanes": 2,
            })
            plan = generate_safer_roads_investment_plan([seg])

            paths = export_irap_and_srip_artifacts(
                assessed_segments=[seg],
                investment_plan=plan,
                output_dir=out_dir,
                network_label="test_net",
            )

            for key in ["ratings_csv", "srip_csv", "json", "md", "manifest"]:
                self.assertIn(key, paths)
                self.assertTrue(Path(paths[key]).exists())

            # Check JSON content
            with Path(paths["json"]).open("r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["irap_engine_version"], IRAP_ENGINE_VERSION)
                self.assertEqual(data["contract_version"], IRAP_CONTRACT_VERSION)
                self.assertEqual(data["srip_version"], SRIP_VERSION)
                self.assertEqual(data["network_label"], "test_net")
                self.assertIn("un_global_target_4_summary", data)
                self.assertIn("srip_investment_summary", data)

            # Check CSV row count
            with Path(paths["ratings_csv"]).open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["segment_id"], "seg-test-101")


if __name__ == "__main__":
    unittest.main()
