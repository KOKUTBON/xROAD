from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.model_evaluation import evaluate_model, report_markdown
from road_risk_modeling.model_registry import ModelRegistry


class ModelEvaluationTests(unittest.TestCase):
    def _record(self) -> dict:
        return {
            "version": 2,
            "run_id": "run-2",
            "metrics": {"mae": 0.2, "transfer": {"cold_start": 0.7}},
        }

    def test_harness_scores_all_gate_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observations = root / "observations.csv"
            rows = [
                {"actual": 0, "score": 0.1, "district": "low_income"},
                {"actual": 0, "score": 0.2, "district": "high_income"},
                {"actual": 1, "score": 0.8, "district": "low_income"},
                {"actual": 1, "score": 0.9, "district": "high_income"},
            ]
            with observations.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            safe = {
                "countermeasure_id": "cmf-1",
                "countermeasure_name": "lighting",
                "effect_ratio_low": 0.7,
                "effect_ratio_central": 0.8,
                "effect_ratio_high": 0.9,
                "benefit_cost_ratio": 2,
                "evidence_source": "study",
            }
            suite = {
                "suite_name": "fixture",
                "model_name": "frequency",
                "predictive": {
                    "observations_path": observations.name,
                    "target_column": "actual",
                    "score_column": "score",
                    "thresholds": {
                        "roc_auc": {"operator": ">=", "value": 0.8},
                        "average_precision": {"operator": ">=", "value": 0.8},
                        "expected_calibration_error": {"operator": "<=", "value": 0.3},
                    },
                    "registered_metric_checks": [
                        {"metric": "transfer.cold_start", "operator": ">=", "value": 0.6}
                    ],
                },
                "guardrail": {
                    "recommendation_cases": [
                        {"recommendation": safe, "site_features": {}, "should_pass": True}
                    ]
                },
                "fairness": {
                    "group_columns": ["district"],
                    "minimum_group_rows": 2,
                    "maximum_mae_ratio": 1.5,
                },
                "regression": {
                    "metric_checks": [
                        {"metric": "mae", "direction": "lower", "tolerance": 0.05}
                    ]
                },
                "_production_record": {"metrics": {"mae": 0.21}},
            }
            report = evaluate_model(self._record(), suite, suite_dir=root)
            self.assertTrue(report["passed"])
            self.assertEqual(
                set(report["categories"]),
                {"predictive", "guardrail", "fairness", "regression"},
            )
            self.assertIn("**Result: PASS**", report_markdown(report))

    def test_failing_gate_blocks_promotion_and_waiver_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "model.bin"
            data = root / "data.csv"
            model.write_bytes(b"model")
            data.write_text("x\n1\n", encoding="utf-8")
            registry = ModelRegistry(root / "registry")
            registry.register(
                model_name="frequency",
                artifact_path=model,
                data_paths=[data],
                parameters={},
                metrics={"mae": 1},
                model_card={
                    "intended_use": "test",
                    "training_data": "test",
                    "metrics": {"mae": 1},
                    "limitations": "test",
                    "ethics_notes": "test",
                },
                seed=42,
            )
            registry.record_evaluation(
                {
                    "model_name": "frequency",
                    "model_version": 1,
                    "passed": False,
                    "suite_name": "fixture",
                }
            )
            with self.assertRaisesRegex(RuntimeError, "Promotion blocked"):
                registry.set_stage(
                    "frequency", version=1, stage="staging", actor="owner", reason="promote"
                )
            registry.set_stage(
                "frequency",
                version=1,
                stage="staging",
                actor="owner",
                reason="emergency",
                waive_reason="incident response requires controlled deployment",
            )
            payload = json.loads(registry.registry_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["waiver_events"]), 1)
            self.assertIn("incident response", payload["waiver_events"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
