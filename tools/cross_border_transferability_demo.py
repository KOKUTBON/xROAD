"""Reproducible cross-border transferability harness.

This driver demonstrates the crash-frequency transferability pipeline running
**end-to-end across two Member States** — Italy (Puglia municipalities) and
France (BAAC) — and produces a cross-border benchmark bundle using
structurally faithful synthetic inputs.

Honesty note
------------
The France extract written here is a **deterministic, structurally-faithful
sample** in the BAAC shape (it exercises the canonical schema and the modeling
feature contract), not the full licensed BAAC corpus. The French national
register is open under Etalab *Licence Ouverte 2.0* and ingests through
``road_risk_modeling.adapters.baac_fr_csv``; bulk ingestion of the real annual
files is the production follow-up. The numbers below therefore validate the
*pipeline and the cross-border degradation behaviour*, not French road-safety
statistics. See ``docs/european-generalisation.md``.

Run::

    PYTHONPATH=src python3 tools/cross_border_transferability_demo.py

It is deterministic, so the published artifacts are reproducible.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.transferability import evaluate_frequency_transferability
from road_risk_modeling.transferability_benchmark import (
    build_transferability_benchmark_bundle,
)

# Paths are repo-relative so the published artifacts and their lineage records
# are reproducible regardless of where the checkout lives. Run from the repo
# root (``PYTHONPATH=src python3 tools/cross_border_transferability_demo.py``).
REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACT_DIR = Path("data/external/cross_border_demo")
METRICS_DIR = Path("data/models/cross_border_transferability")
REPORT_DIR = Path("data/reporting/cross_border_transferability")

HOLDOUT_YEAR = 2022
YEARS = (2020, 2021, 2022)
RF_ESTIMATORS = 50

FIELDNAMES = [
    "segment_id",
    "occurred_year",
    "crash_count",
    "fatal_crash_count",
    "injury_crash_count",
    "fatalities_total",
    "injuries_total",
    "mean_match_distance_m",
    "segment_length_m",
    "highway",
    "oneway",
    "ref",
    "bridge",
    "junction",
    "access",
    "tunnel",
    "bearing_bin",
    "lanes_numeric",
    "maxspeed_numeric",
    "width_numeric",
    "is_roundabout",
    "node_degree_max",
    "road_class_rank",
    "segment_name_present",
]


def _segment_profiles(seed: int, count: int, urban_share: float) -> list[dict]:
    """Build a deterministic set of segment profiles for one jurisdiction.

    ``urban_share`` shifts the road-class mix so the French extract is more
    rural than the Italian municipalities, which is exactly the cross-border
    regime shift HE-05 needs to surface.
    """
    rng = random.Random(seed)
    highways = ["residential", "secondary", "primary", "tertiary", "trunk"]
    profiles: list[dict] = []
    for index in range(count):
        is_urban = rng.random() < urban_share
        highway = rng.choice(highways[:3]) if is_urban else rng.choice(highways[2:])
        base_rate = (3.0 if is_urban else 1.4) + rng.random() * 1.5
        profiles.append(
            {
                "segment_id": f"seg-{index:03d}",
                "highway": highway,
                "base_rate": base_rate,
                "segment_length_m": round(80.0 + rng.random() * 240.0, 1),
                "lanes_numeric": 1 + (2 if not is_urban else 1),
                "maxspeed_numeric": 90 if not is_urban else 50,
                "width_numeric": round(5.5 + rng.random() * 4.0, 1),
                "is_roundabout": "True" if rng.random() < 0.08 else "False",
                "node_degree_max": rng.randint(2, 5),
                "road_class_rank": highways.index(highway) + 1,
                "bearing_bin": rng.choice(["north_south", "east_west", "diagonal"]),
                "mean_match_distance_m": round(2.0 + rng.random() * 6.0, 2),
            }
        )
    return profiles


def _write_jurisdiction(path: Path, seed: int, count: int, urban_share: float) -> None:
    profiles = _segment_profiles(seed, count, urban_share)
    rng = random.Random(seed * 7 + 1)
    rows: list[dict] = []
    for profile in profiles:
        for year in YEARS:
            # A mild upward trend plus a reproducible holdout-year perturbation.
            trend = 0.15 * (year - YEARS[0])
            noise = rng.uniform(-0.5, 0.8)
            crash_count = max(0, round(profile["base_rate"] + trend + noise))
            fatal = 1 if crash_count >= 4 else 0
            injury = max(crash_count - fatal, 0)
            rows.append(
                {
                    "segment_id": profile["segment_id"],
                    "occurred_year": year,
                    "crash_count": crash_count,
                    "fatal_crash_count": fatal,
                    "injury_crash_count": injury,
                    "fatalities_total": fatal,
                    "injuries_total": injury,
                    "mean_match_distance_m": profile["mean_match_distance_m"],
                    "segment_length_m": profile["segment_length_m"],
                    "highway": profile["highway"],
                    "oneway": "False",
                    "ref": "",
                    "bridge": "",
                    "junction": "",
                    "access": "",
                    "tunnel": "",
                    "bearing_bin": profile["bearing_bin"],
                    "lanes_numeric": profile["lanes_numeric"],
                    "maxspeed_numeric": profile["maxspeed_numeric"],
                    "width_numeric": profile["width_numeric"],
                    "is_roundabout": profile["is_roundabout"],
                    "node_degree_max": profile["node_degree_max"],
                    "road_class_rank": profile["road_class_rank"],
                    "segment_name_present": 1,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    # Anchor to the repo root so the relative output paths above resolve the
    # same way no matter where the script is invoked from.
    os.chdir(REPO_ROOT)

    # Two Italian municipalities + one French jurisdiction. France carries a
    # lower urban share (more rural roads) to expose the cross-border regime gap.
    jurisdictions = [
        ("bari", EXTRACT_DIR / "it_bari_segment_year_metrics.csv", 11, 60, 0.85),
        ("foggia_core", EXTRACT_DIR / "it_foggia_segment_year_metrics.csv", 23, 55, 0.80),
        ("fr_baac_sample", EXTRACT_DIR / "fr_baac_segment_year_metrics.csv", 41, 70, 0.45),
    ]
    datasets: list[tuple[str, str]] = []
    for label, path, seed, count, urban_share in jurisdictions:
        _write_jurisdiction(path, seed=seed, count=count, urban_share=urban_share)
        datasets.append((label, str(path)))

    metrics = evaluate_frequency_transferability(
        datasets=datasets,
        output_dir=METRICS_DIR,
        holdout_year=HOLDOUT_YEAR,
        rf_n_estimators=RF_ESTIMATORS,
    )
    metrics_path = metrics["metrics_path"]
    print(f"transferability metrics -> {metrics_path}")

    bundle = build_transferability_benchmark_bundle(
        transferability_metrics_paths=[metrics_path],
        output_dir=REPORT_DIR,
        benchmark_label="Cross-Border Transferability (IT Puglia + FR BAAC) — HE-05",
    )
    print(f"benchmark bundle manifest -> {bundle['manifest_path']}")
    print(f"benchmark stats -> {bundle['stats']}")


if __name__ == "__main__":
    main()
