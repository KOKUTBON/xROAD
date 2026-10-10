"""Reproducible scientific benchmark harness.

Runs the platform crash-frequency model against the recognised road-safety
baselines — a **Safety Performance Function (SPF)** Poisson GLM and the
**Highway Safety Manual Empirical Bayes (EB)** estimator — on a temporal
holdout, with bootstrap confidence intervals, calibration, and spatial
cross-validation, then publishes the result under
``data/reporting/scientific_benchmark/``.

It reuses the deterministic Italy + France extract generator from the
cross-border harness, so the same committed sample drives both benchmarks.

Run::

    PYTHONPATH=src python3 tools/scientific_benchmark_demo.py

Deterministic — the published artifacts regenerate byte-for-byte. The committed
extracts are structurally-faithful samples (see
``docs/european-generalisation.md``); the protocol and baselines are what carry
over to bulk data.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cross_border_transferability_demo import _write_jurisdiction  # noqa: E402

from road_risk_modeling.scientific_benchmark import run_scientific_benchmark  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACT_DIR = Path("data/external/scientific_benchmark_demo")
REPORT_DIR = Path("data/reporting/scientific_benchmark")
HOLDOUT_YEAR = 2022


def main() -> None:
    os.chdir(REPO_ROOT)
    jurisdictions = [
        ("bari", EXTRACT_DIR / "it_bari_segment_year_metrics.csv", 11, 60, 0.85),
        ("foggia_core", EXTRACT_DIR / "it_foggia_segment_year_metrics.csv", 23, 55, 0.80),
        ("fr_baac_sample", EXTRACT_DIR / "fr_baac_segment_year_metrics.csv", 41, 70, 0.45),
    ]
    datasets: list[tuple[str, str]] = []
    for label, path, seed, count, urban_share in jurisdictions:
        _write_jurisdiction(path, seed=seed, count=count, urban_share=urban_share)
        datasets.append((label, str(path)))

    result = run_scientific_benchmark(
        datasets=datasets,
        output_dir=REPORT_DIR,
        holdout_year=HOLDOUT_YEAR,
        rf_n_estimators=200,
        bootstrap_iterations=500,
        spatial_folds=5,
    )
    print(f"metrics -> {result['metrics_path']}")
    print(f"report  -> {result['report_path']}")
    print(f"ranking by holdout deviance -> {result['holdout_ranking_by_deviance']}")


if __name__ == "__main__":
    main()
