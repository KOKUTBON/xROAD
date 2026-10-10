from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.prediction_store import RecommendationReviewStore
from road_risk_modeling.recommendation_governance import (
    assert_recommendation_safe,
    benchmark_recommendations,
    calibration_report,
    validate_recommendation_guardrails,
)


def _recommendation(**overrides: object) -> dict:
    payload = {
        "countermeasure_id": "CM-JCT-001",
        "countermeasure_name": "Convert junction to single-lane roundabout",
        "effect_ratio_low": 0.4,
        "effect_ratio_central": 0.55,
        "effect_ratio_high": 0.7,
        "benefit_cost_ratio": 2.1,
        "evidence_source": "iRAP",
    }
    payload.update(overrides)
    return payload


class GuardrailTests(unittest.TestCase):
    def test_roundabout_on_motorway_fails_closed(self) -> None:
        violations = validate_recommendation_guardrails(
            _recommendation(), site_features={"road_class": "motorway"}
        )
        self.assertIn("sanity:roundabout_on_motorway", violations)
        with self.assertRaises(ValueError):
            assert_recommendation_safe(
                _recommendation(), site_features={"road_class": "motorway"}
            )

    def test_invalid_uncertainty_and_economics_are_rejected(self) -> None:
        violations = validate_recommendation_guardrails(
            _recommendation(effect_ratio_low=0.8, effect_ratio_high=0.6, benefit_cost_ratio=-1),
            site_features={"road_class": "residential"},
        )
        self.assertIn("invalid:effect_interval_order", violations)
        self.assertIn("invalid:benefit_cost_ratio", violations)

    def test_valid_treatment_passes(self) -> None:
        self.assertEqual(
            validate_recommendation_guardrails(
                _recommendation(), site_features={"road_class": "residential"}
            ),
            [],
        )


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_and_per_category_calibration(self) -> None:
        result = benchmark_recommendations(
            irap_cases=[
                {"predicted_improvement": 1, "irap_star_improvement": 1},
                {"predicted_improvement": 0, "irap_star_improvement": 0},
            ],
            historical_cases=[
                {
                    "actual_countermeasure_id": "CM-1",
                    "recommended_countermeasure_ids": ["CM-1", "CM-2"],
                }
            ],
        )
        self.assertTrue(result["passed"])
        report = calibration_report(
            [
                {
                    "category": "speed",
                    "predicted_crash_reduction": 0.2,
                    "observed_crash_reduction": 0.25,
                },
                {
                    "category": "junction",
                    "predicted_crash_reduction": 0.5,
                    "observed_crash_reduction": 0.4,
                },
            ]
        )
        self.assertEqual(set(report["by_category"]), {"junction", "speed"})
        self.assertEqual(report["overall"]["case_count"], 2)


class ReviewWorkflowTests(unittest.TestCase):
    def test_approval_requires_recorded_engineer_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with RecommendationReviewStore(Path(temp_dir) / "reviews.sqlite") as store:
                store.propose(
                    recommendation_id="rec-1",
                    payload=_recommendation(),
                    model_version="recommendation_model_v1",
                    data_lineage_hash="abc123",
                )
                with self.assertRaises(ValueError):
                    store.transition("rec-1", to_state="approved", actor="chief-engineer")
                self.assertEqual(store.approved_for_api(), [])
                store.transition(
                    "rec-1",
                    to_state="engineer_reviewed",
                    actor="engineer@example.org",
                    note="Geometry and treatment applicability verified.",
                )
                approved = store.transition(
                    "rec-1", to_state="approved", actor="chief-engineer@example.org"
                )
                self.assertEqual(approved["state"], "approved")
                self.assertEqual(approved["reviewer"], "engineer@example.org")
                self.assertEqual(len(store.approved_for_api()), 1)
                self.assertEqual(
                    [event["to_state"] for event in store.audit_events("rec-1")],
                    ["proposed", "engineer_reviewed", "approved"],
                )

    def test_rejection_requires_reason_and_exports_training_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with RecommendationReviewStore(Path(temp_dir) / "reviews.sqlite") as store:
                store.propose(
                    recommendation_id="rec-2",
                    payload=_recommendation(),
                    model_version="recommendation_model_v1",
                    data_lineage_hash="def456",
                )
                with self.assertRaises(ValueError):
                    store.transition("rec-2", to_state="rejected", actor="engineer")
                store.transition(
                    "rec-2",
                    to_state="rejected",
                    actor="engineer",
                    reason_code="site_constraint",
                    note="Insufficient right of way.",
                )
                signals = store.rejection_training_signals()
                self.assertEqual(signals[0]["accepted_label"], 0)
                self.assertEqual(signals[0]["rejection_reason_code"], "site_constraint")


if __name__ == "__main__":
    unittest.main()
