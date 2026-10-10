from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.model_registry import (
    ModelRegistry,
    validate_model_card,
    version_data_artifacts,
)


CARD = {
    "intended_use": "Network screening.",
    "training_data": "fixture.csv",
    "metrics": {"mae": 0.2},
    "limitations": "Fixture only.",
    "ethics_notes": "Human review required.",
}


class ModelRegistryTests(unittest.TestCase):
    @staticmethod
    def _pass(registry: ModelRegistry, model_name: str, version: int) -> None:
        registry.record_evaluation(
            {
                "model_name": model_name,
                "model_version": version,
                "passed": True,
                "suite_name": "fixture",
            }
        )

    def test_registration_versions_data_environment_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "model.joblib"
            data = root / "training.csv"
            model.write_bytes(b"model-v1")
            data.write_text("x,y\n1,2\n", encoding="utf-8")
            registry = ModelRegistry(root / "registry")
            record = registry.register(
                model_name="frequency",
                artifact_path=model,
                data_paths=[data],
                parameters={"seed": 42},
                metrics={"mae": 0.2},
                model_card=CARD,
                seed=42,
                git_sha="abc123",
            )
            self.assertEqual(record["stage"], "candidate")
            self.assertEqual(record["version"], 1)
            self.assertTrue(Path(record["artifact"]["path"]).exists())
            self.assertEqual(record["git_sha"], "abc123")
            self.assertTrue(record["data_version"]["data_lineage_hash"])
            self.assertIn("python", record["environment"])
            duplicate = registry.register(
                model_name="frequency",
                artifact_path=model,
                data_paths=[data],
                parameters={"seed": 42},
                metrics={"mae": 0.2},
                model_card=CARD,
                seed=42,
                git_sha="abc123",
            )
            self.assertEqual(duplicate["run_id"], record["run_id"])
            self.assertEqual(len(registry.list_versions("frequency")), 1)

    def test_model_card_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            validate_model_card({"intended_use": "missing the rest"})

    def test_content_addressed_data_version_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.csv"
            path.write_text("a\n1\n", encoding="utf-8")
            first = version_data_artifacts([path])["data_lineage_hash"]
            path.write_text("a\n2\n", encoding="utf-8")
            second = version_data_artifacts([path])["data_lineage_hash"]
            self.assertNotEqual(first, second)

    def test_promotion_serving_resolution_and_rollback_are_stage_flips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = root / "data.csv"
            data.write_text("x\n1\n", encoding="utf-8")
            registry = ModelRegistry(root / "registry")
            records = []
            for index in (1, 2):
                model = root / f"model-{index}.joblib"
                model.write_bytes(f"model-{index}".encode())
                records.append(
                    registry.register(
                        model_name="weather",
                        artifact_path=model,
                        data_paths=[data],
                        parameters={"iteration": index},
                        metrics={"mae": 1 / index},
                        model_card=CARD,
                        seed=42,
                        git_sha="abc",
                    )
                )
            self._pass(registry, "weather", 1)
            self._pass(registry, "weather", 2)
            registry.set_stage(
                "weather", version=1, stage="staging", actor="ml-owner", reason="validated"
            )
            registry.set_stage(
                "weather", version=1, stage="production", actor="ml-owner", reason="promote"
            )
            self.assertEqual(registry.resolve("weather")["version"], 1)
            registry.set_stage(
                "weather", version=2, stage="staging", actor="ml-owner", reason="validated"
            )
            registry.set_stage(
                "weather", version=2, stage="production", actor="ml-owner", reason="replace"
            )
            self.assertEqual(registry.resolve("weather")["version"], 2)
            registry.set_stage(
                "weather", version=1, stage="production", actor="ml-owner", reason="rollback"
            )
            self.assertEqual(registry.resolve("weather")["version"], 1)
            events = json.loads(registry.registry_path.read_text())["stage_events"]
            self.assertEqual(events[-1]["reason"], "rollback")

    def test_candidate_cannot_skip_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "model.joblib"
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
                model_card=CARD,
                seed=42,
            )
            with self.assertRaisesRegex(ValueError, "candidate -> production"):
                registry.set_stage(
                    "frequency",
                    version=1,
                    stage="production",
                    actor="owner",
                    reason="skip validation",
                )

    def test_resolver_rejects_tampered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "model.joblib"
            data = root / "data.csv"
            model.write_bytes(b"safe")
            data.write_text("x\n1\n", encoding="utf-8")
            registry = ModelRegistry(root / "registry")
            record = registry.register(
                model_name="frequency",
                artifact_path=model,
                data_paths=[data],
                parameters={},
                metrics={"mae": 1},
                model_card=CARD,
                seed=42,
            )
            self._pass(registry, "frequency", 1)
            registry.set_stage(
                "frequency", version=1, stage="staging", actor="owner", reason="validate"
            )
            registry.set_stage(
                "frequency", version=1, stage="production", actor="owner", reason="test"
            )
            Path(record["artifact"]["path"]).write_bytes(b"tampered")
            with self.assertRaises(RuntimeError):
                registry.resolve("frequency")


if __name__ == "__main__":
    unittest.main()
