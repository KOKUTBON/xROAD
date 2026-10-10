"""Content-addressed model registry and reproducible run metadata (ML-01)."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess  # nosec B404 # fixed git command, no shell or user arguments
import sys
from typing import Any, Iterable, Mapping


MODEL_REGISTRY_VERSION = "model_registry_v1"
MODEL_STAGES = ("candidate", "staging", "production")
ALLOWED_STAGE_TRANSITIONS = {
    "candidate": {"staging"},
    "staging": {"candidate", "production"},
    "production": {"staging"},
}
REQUIRED_MODEL_CARD_FIELDS = (
    "intended_use",
    "training_data",
    "metrics",
    "limitations",
    "ethics_notes",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha(cwd: Path) -> str:
    try:
        return subprocess.run(  # nosec B607, B603 # fixed git command resolved from the deployment PATH
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def environment_snapshot() -> dict[str, Any]:
    packages = {}
    for name in ("numpy", "pandas", "scikit-learn", "joblib"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
    }


def version_data_artifacts(paths: Iterable[str | Path]) -> dict[str, Any]:
    artifacts = []
    aggregate = hashlib.sha256()
    for raw_path in sorted((Path(path) for path in paths), key=lambda path: str(path)):
        checksum = sha256_file(raw_path)
        aggregate.update(str(raw_path).encode())
        aggregate.update(checksum.encode())
        artifacts.append(
            {"path": str(raw_path), "sha256": checksum, "size_bytes": raw_path.stat().st_size}
        )
    return {
        "data_lineage_hash": aggregate.hexdigest(),
        "artifacts": artifacts,
    }


def validate_model_card(card: Mapping[str, Any]) -> None:
    missing = [
        field for field in REQUIRED_MODEL_CARD_FIELDS
        if card.get(field) in (None, "", [], {})
    ]
    if missing:
        raise ValueError(f"Model card is incomplete; missing: {', '.join(missing)}")


class ModelRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "artifacts").mkdir(exist_ok=True)
        self.registry_path = self.root / "registry.json"

    def _load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {
                "model_registry_version": MODEL_REGISTRY_VERSION,
                "models": {},
                "stage_events": [],
                "evaluations": [],
                "waiver_events": [],
            }
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if payload.get("model_registry_version") != MODEL_REGISTRY_VERSION:
            raise RuntimeError("Unsupported model registry version.")
        payload.setdefault("evaluations", [])
        payload.setdefault("waiver_events", [])
        return payload

    def record_evaluation(self, report: Mapping[str, Any]) -> None:
        payload = self._load()
        payload["evaluations"].append(dict(report))
        self._write(payload)

    def _write(self, payload: dict[str, Any]) -> None:
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.registry_path)

    def register(
        self,
        *,
        model_name: str,
        artifact_path: str | Path,
        data_paths: Iterable[str | Path],
        parameters: Mapping[str, Any],
        metrics: Mapping[str, Any],
        model_card: Mapping[str, Any],
        seed: int,
        git_sha: str | None = None,
    ) -> dict[str, Any]:
        validate_model_card(model_card)
        source = Path(artifact_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        artifact_hash = sha256_file(source)
        data_version = version_data_artifacts(data_paths)
        run_payload = {
            "model_name": model_name,
            "artifact_sha256": artifact_hash,
            "data_lineage_hash": data_version["data_lineage_hash"],
            "parameters": dict(parameters),
            "metrics": dict(metrics),
            "seed": int(seed),
        }
        run_id = hashlib.sha256(
            json.dumps(run_payload, sort_keys=True).encode()
        ).hexdigest()[:20]
        destination = self.root / "artifacts" / artifact_hash[:2] / f"{artifact_hash}{source.suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        payload = self._load()
        versions = payload["models"].setdefault(model_name, [])
        existing = next((row for row in versions if row["run_id"] == run_id), None)
        if existing:
            return existing
        record = {
            "run_id": run_id,
            "version": len(versions) + 1,
            "stage": "candidate",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "artifact": {
                "path": str(destination),
                "sha256": artifact_hash,
                "source_path": str(source),
            },
            "data_version": data_version,
            "parameters": dict(parameters),
            "metrics": dict(metrics),
            "model_card": dict(model_card),
            "seed": int(seed),
            "git_sha": git_sha or _git_sha(Path.cwd()),
            "environment": environment_snapshot(),
        }
        versions.append(record)
        self._write(payload)
        return record

    def set_stage(
        self,
        model_name: str,
        *,
        version: int,
        stage: str,
        actor: str,
        reason: str,
        waive_reason: str | None = None,
    ) -> dict[str, Any]:
        if stage not in MODEL_STAGES:
            raise ValueError(f"Unknown model stage: {stage}")
        if not actor or not reason:
            raise ValueError("Stage changes require actor and reason.")
        payload = self._load()
        versions = payload["models"].get(model_name, [])
        target = next((row for row in versions if row["version"] == version), None)
        if target is None:
            raise KeyError(f"{model_name} v{version}")
        previous_stage = target["stage"]
        if stage == previous_stage:
            return target
        if stage not in ALLOWED_STAGE_TRANSITIONS[previous_stage]:
            raise ValueError(
                f"Invalid model stage transition: {previous_stage} -> {stage}"
            )
        if stage in {"staging", "production"}:
            evaluations = [
                row
                for row in payload["evaluations"]
                if row.get("model_name") == model_name
                and row.get("model_version") == version
            ]
            latest = evaluations[-1] if evaluations else None
            if not latest or not latest.get("passed"):
                if not waive_reason:
                    raise RuntimeError(
                        "Promotion blocked: no passing evaluation report; "
                        "use an explicit waiver with reason."
                    )
                payload["waiver_events"].append(
                    {
                        "model_name": model_name,
                        "version": version,
                        "target_stage": stage,
                        "actor": actor,
                        "reason": waive_reason,
                        "occurred_at_utc": datetime.now(UTC).isoformat(),
                    }
                )
        for row in versions:
            if row["stage"] == stage and row is not target:
                row["stage"] = "staging" if stage == "production" else "candidate"
        target["stage"] = stage
        payload["stage_events"].append(
            {
                "model_name": model_name,
                "version": version,
                "from_stage": previous_stage,
                "to_stage": stage,
                "actor": actor,
                "reason": reason,
                "occurred_at_utc": datetime.now(UTC).isoformat(),
            }
        )
        self._write(payload)
        return target

    def resolve(self, model_name: str, *, stage: str = "production") -> dict[str, Any]:
        if stage not in MODEL_STAGES:
            raise ValueError(f"Unknown model stage: {stage}")
        versions = self._load()["models"].get(model_name, [])
        matches = [row for row in versions if row["stage"] == stage]
        if len(matches) != 1:
            raise KeyError(f"No unique {stage} model for {model_name!r}.")
        record = matches[0]
        if sha256_file(record["artifact"]["path"]) != record["artifact"]["sha256"]:
            raise RuntimeError("Registered model artifact failed checksum verification.")
        return record

    def list_versions(self, model_name: str) -> list[dict[str, Any]]:
        return list(self._load()["models"].get(model_name, []))
