#!/usr/bin/env python3
"""Run a registered model evaluation suite and persist its gate report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from road_risk_modeling.model_evaluation import evaluate_model, report_markdown
from road_risk_modeling.model_registry import ModelRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite")
    parser.add_argument("--registry-dir", default="data/model_registry")
    parser.add_argument("--output-dir", default="data/model_evaluations")
    parser.add_argument("--version", type=int)
    args = parser.parse_args()
    suite_path = Path(args.suite)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    registry = ModelRegistry(args.registry_dir)
    versions = registry.list_versions(suite["model_name"])
    if not versions:
        parser.error(f"no registered versions for {suite['model_name']!r}")
    version = args.version or max(row["version"] for row in versions)
    record = next((row for row in versions if row["version"] == version), None)
    if record is None:
        parser.error(f"model version {version} is not registered")
    try:
        suite["_production_record"] = registry.resolve(
            suite["model_name"], stage="production"
        )
    except KeyError:
        suite["_production_record"] = None
    report = evaluate_model(record, suite, suite_dir=suite_path.parent)
    registry.record_evaluation(report)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{suite['model_name']}-v{version}"
    json_path = output_dir / f"{stem}.evaluation.json"
    markdown_path = output_dir / f"{stem}.evaluation.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(report_markdown(report), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "json": str(json_path), "markdown": str(markdown_path)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
