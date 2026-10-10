import unittest

from road_risk_modeling.countermeasure_knowledge import load_countermeasure_library
from road_risk_modeling.recommendation_model import (
    SOCIAL_COST_PER_CRASH_EUR,
    evaluate_against_cmf_prior,
    recommend_for_site,
    train_recommendation_model,
)


def _record(
    *,
    object_id: str,
    city: str,
    split: str,
    maxspeed: float,
    ratio: float,
    code: str = "speed_management",
    countermeasure_id: str | None = "CM-SPD-001",
) -> dict:
    return {
        "object_id": object_id,
        "object_type": "segment",
        "city_key": city,
        "intervention_code": code,
        "label_source": "observed_attribute_change",
        "is_synthetic": False,
        "countermeasure_id": countermeasure_id,
        "intervention_year": 2021,
        "temporal_split": split,
        "city_fold": city,
        "outcome_crash_density_ratio": ratio,
        "before_crash_density_per_km": 5.0,
        "before_severity_density_per_km": 6.0,
        "feature_maxspeed_numeric": maxspeed,
        "feature_lanes_numeric": 2,
        "feature_segment_length_m": 400,
        "feature_road_class_rank": 3,
        "feature_sinuosity": 1.05,
        "feature_node_degree_sum": 6,
        "feature_exposure_proxy_index": 40,
        "feature_exposure_policy_index": 30,
        "feature_poi_any_count": 5,
        "feature_building_any_count": 20,
    }


def _fixture_records() -> list[dict]:
    """Observed before/after cases whose true effect depends on site speed.

    True ratio = 0.45 on fast (70 km/h) sites and 0.80 on slow (30 km/h)
    sites; the CMF prior for CM-SPD-001 is a single 0.62 for both, so a model
    that learns the speed interaction must beat the prior-only baseline.
    """
    records = []
    for index in range(120):
        fast = index % 2 == 0
        split = "train" if index < 80 else ("validation" if index < 100 else "test")
        records.append(
            _record(
                object_id=f"seg-{index}",
                city="alpha" if index % 3 else "beta",
                split=split,
                maxspeed=70 if fast else 30,
                ratio=0.45 if fast else 0.80,
            )
        )
    return records


class TrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.library = load_countermeasure_library()
        self.records = _fixture_records()

    def test_beats_cmf_prior_baseline_on_held_out_observed_cases(self) -> None:
        model = train_recommendation_model(self.records, library=self.library, seed=42)
        evaluation = evaluate_against_cmf_prior(model, self.records)
        self.assertGreater(evaluation["evaluated_records"], 0)
        self.assertLess(evaluation["model_mae"], evaluation["cmf_prior_baseline_mae"])
        self.assertTrue(evaluation["beats_prior_baseline"])

    def test_training_is_deterministic_for_a_seed(self) -> None:
        model_a = train_recommendation_model(self.records, library=self.library, seed=7)
        model_b = train_recommendation_model(self.records, library=self.library, seed=7)
        features = {name: 50 for name in model_a.feature_names}
        prediction_a = model_a.predict_effect(
            features=features,
            intervention_code="speed_management",
            prior_cmf=0.62,
            prior_ci=(0.50, 0.77),
            city_key="alpha",
        )
        prediction_b = model_b.predict_effect(
            features=features,
            intervention_code="speed_management",
            prior_cmf=0.62,
            prior_ci=(0.50, 0.77),
            city_key="alpha",
        )
        self.assertEqual(prediction_a, prediction_b)

    def test_cold_start_widens_interval_and_shrinks_toward_prior(self) -> None:
        model = train_recommendation_model(self.records, library=self.library, seed=42)
        features = {name: 50 for name in model.feature_names}
        known = model.predict_effect(
            features=features,
            intervention_code="speed_management",
            prior_cmf=0.62,
            prior_ci=(0.50, 0.77),
            city_key="alpha",
        )
        cold = model.predict_effect(
            features=features,
            intervention_code="speed_management",
            prior_cmf=0.62,
            prior_ci=(0.50, 0.77),
            city_key="never-seen-city",
        )
        self.assertFalse(known["cold_start"])
        self.assertTrue(cold["cold_start"])
        known_width = known["effect_ratio_high"] - known["effect_ratio_low"]
        cold_width = cold["effect_ratio_high"] - cold["effect_ratio_low"]
        self.assertGreater(cold_width, known_width)
        self.assertLess(cold["shrinkage_weight"], known["shrinkage_weight"])
        # The estimate never leaves the (relaxed) prior confidence envelope.
        for prediction in (known, cold):
            self.assertGreaterEqual(prediction["effect_ratio_central"], 0.50 * 0.8)
            self.assertLessEqual(prediction["effect_ratio_central"], 0.77 * 1.2)


class RecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.library = load_countermeasure_library()
        self.model = train_recommendation_model(
            _fixture_records(), library=self.library, seed=42
        )

    def test_recommendations_never_violate_preconditions(self) -> None:
        site_features = {
            "object_type": "segment",
            "area_type": "urban",
            "maxspeed": 50,
            "lane_count": 2,
            "road_class": "residential",
            "segment_length_m": 400,
        }
        model_features = {name: 40 for name in self.model.feature_names}
        recommendations = recommend_for_site(
            self.model,
            site_features=site_features,
            model_features=model_features,
            baseline_annual_crashes=2.0,
            city_key="alpha",
        )
        self.assertTrue(recommendations)
        by_id = {c.countermeasure_id: c for c in self.library}
        from road_risk_modeling.countermeasure_knowledge import countermeasure_is_applicable

        for recommendation in recommendations:
            countermeasure = by_id[recommendation["countermeasure_id"]]
            self.assertTrue(countermeasure_is_applicable(countermeasure, site_features))
        # CM-SPD-001 requires maxspeed=50: a 30 km/h site must not receive it.
        slow_site = dict(site_features, maxspeed=30)
        slow_recommendations = recommend_for_site(
            self.model,
            site_features=slow_site,
            model_features=model_features,
            baseline_annual_crashes=2.0,
            city_key="alpha",
        )
        self.assertNotIn(
            "CM-SPD-001",
            {recommendation["countermeasure_id"] for recommendation in slow_recommendations},
        )

    def test_ranking_output_carries_economics_and_why(self) -> None:
        recommendations = recommend_for_site(
            self.model,
            site_features={
                "object_type": "segment",
                "area_type": "urban",
                "maxspeed": 50,
                "lane_count": 2,
                "road_class": "residential",
            },
            model_features={name: 40 for name in self.model.feature_names},
            baseline_annual_crashes=3.0,
            city_key="alpha",
        )
        top = recommendations[0]
        self.assertGreater(top["expected_annual_crashes_prevented"], 0)
        self.assertLessEqual(
            top["expected_annual_crashes_prevented_low"],
            top["expected_annual_crashes_prevented"],
        )
        self.assertGreaterEqual(
            top["expected_annual_crashes_prevented_high"],
            top["expected_annual_crashes_prevented"],
        )
        self.assertAlmostEqual(
            top["annual_social_benefit_eur"],
            top["expected_annual_crashes_prevented"] * SOCIAL_COST_PER_CRASH_EUR,
            delta=1.0,
        )
        self.assertGreater(top["benefit_cost_ratio"], 0)
        self.assertTrue(top["evidence_source"])
        self.assertTrue(top["top_risk_factors"])
        self.assertIn("label", top["top_risk_factors"][0])
        # Ranked by expected crashes prevented, descending.
        prevented = [r["expected_annual_crashes_prevented"] for r in recommendations]
        self.assertEqual(prevented, sorted(prevented, reverse=True))


if __name__ == "__main__":
    unittest.main()
