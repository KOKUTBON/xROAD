#!/usr/bin/env python3
"""Reference one-command frequency training and registry pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from road_risk_modeling.model_registry import ModelRegistry
from road_risk_modeling.modeling import train_frequency_baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--training-data",
        default="data/processed/aggregates/bari_context_v2/segment_year_metrics.csv",
    )
    parser.add_argument("--output-dir", default="data/models/bari_frequency_registry_reference")
    parser.add_argument("--registry-dir", default="data/model_registry")
    parser.add_argument("--holdout-year", type=int, default=2021)
    args = parser.parse_args()
    result = train_frequency_baseline(
        args.training_data,
        output_dir=args.output_dir,
        holdout_year=args.holdout_year,
    )
    metrics = json.loads(Path(result["metrics_path"]).read_text(encoding="utf-8"))
    model_metrics = metrics["random_forest_poisson_metrics"]
    record = ModelRegistry(args.registry_dir).register(
        model_name="bari_frequency_baseline",
        artifact_path=metrics["outputs"]["model_path"],
        data_paths=[args.training_data],
        parameters={
            "holdout_year": args.holdout_year,
            "seed": 42,
            "pipeline": "train_frequency_baseline",
        },
        metrics=model_metrics,
        model_card={
            "intended_use": "Bari segment-level annual crash-frequency screening.",
            "training_data": str(args.training_data),
            "metrics": model_metrics,
            "limitations": "Historical association; not causal or an individual-event predictor.",
            "ethics_notes": "Municipal decision support with human review; aggregate publication only.",
        },
        seed=42,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
