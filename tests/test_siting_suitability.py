from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.siting_standards import load_siting_standards
from road_risk_modeling.siting_suitability import (
    export_siting_bundle,
    normalize_weights,
    rank_candidate_sites,
    train_demand_benefit_model,
    weight_sensitivity_analysis,
)


def candidate(identifier: str, *, risk_decile: int = 5, population: float = 0.5) -> dict:
    return {
        "candidate_id": identifier,
        "geometry": {"type": "Point", "coordinates": [16.87, 41.12]},
        "facts": {
            "entrance_segment_risk_decile": risk_decile,
            "protected_crossing_distance_m": 80,
            "safe_route_mean_risk_percentile": 50,
            "entrance_approach_speed_kph": 30,
            "accessible_transit_stop_distance_m": 200,
            "step_free_pedestrian_route": True,
            "minimum_clear_sidewalk_width_m": 1.8,
            "maximum_pedestrian_gradient_percent": 4,
        },
        "population_served_score": population,
        "provision_gap_score": 0.7,
        "access_route_safety_score": 0.8,
        "accessibility_score": 0.75,
        "equity_score": 0.6,
    }


class SitingSuitabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rarm_rules = [
            rule for rule in load_siting_standards() if rule.jurisdiction == "RARM"
        ]
        self.model = train_demand_benefit_model(
            [
                {
                    "population_served_score": 0.9,
                    "provision_gap_score": 0.8,
                    "access_route_safety_score": 0.8,
                    "accessibility_score": 0.7,
                    "equity_score": 0.6,
                    "observed_benefit": 0.9,
                },
                {
                    "population_served_score": 0.2,
                    "provision_gap_score": 0.2,
                    "access_route_safety_score": 0.4,
                    "accessibility_score": 0.3,
                    "equity_score": 0.3,
                    "observed_benefit": 0.2,
                },
            ]
        )

    def test_mandatory_rules_filter_before_ml_ranking(self) -> None:
        result = rank_candidate_sites(
            [
                candidate("eligible", population=0.4),
                candidate("unsafe-high-demand", risk_decile=10, population=1.0),
            ],
            asset_type="school",
            school_grade="primaria",
            rules=self.rarm_rules,
            model=self.model,
        )
        self.assertEqual([row["candidate_id"] for row in result["ranked_candidates"]], ["eligible"])
        excluded = result["excluded_candidates"][0]
        self.assertEqual(excluded["candidate_id"], "unsafe-high-demand")
        self.assertTrue(excluded["companion_interventions"])

    def test_ranking_is_deterministic_and_explainable(self) -> None:
        rows = [candidate("b", population=0.4), candidate("a", population=0.9)]
        first = rank_candidate_sites(
            rows, asset_type="school", school_grade="primaria",
            rules=self.rarm_rules, model=self.model
        )
        second = rank_candidate_sites(
            rows, asset_type="school", school_grade="primaria",
            rules=self.rarm_rules, model=self.model
        )
        self.assertEqual(first["ranked_candidates"], second["ranked_candidates"])
        top = first["ranked_candidates"][0]
        self.assertIn("criteria_scores", top)
        self.assertIn("compliance", top)
        self.assertGreater(top["suitability_score"], 0)

    def test_weights_normalize_and_sensitivity_is_reported(self) -> None:
        weights = normalize_weights({"population_served": 1})
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        analysis = weight_sensitivity_analysis(
            [candidate("a", population=0.9), candidate("b", population=0.5)],
            asset_type="school",
            school_grade="primaria",
            rules=self.rarm_rules,
            model=self.model,
            top_k=2,
        )
        self.assertEqual(len(analysis["scenarios"]), 10)
        self.assertEqual(analysis["minimum_top_k_overlap_share"], 1.0)

    def test_export_contains_geojson_report_and_citations(self) -> None:
        result = rank_candidate_sites(
            [candidate("a")],
            asset_type="school",
            school_grade="primaria",
            rules=self.rarm_rules,
            model=self.model,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export_siting_bundle(
                result, output_dir=temp_dir, name="demo", limit=1
            )
            for path in paths.values():
                self.assertTrue(Path(path).exists())
            self.assertIn(
                "citation", Path(paths["report_path"]).read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
