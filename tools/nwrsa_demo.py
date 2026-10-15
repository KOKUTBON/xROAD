"""Reproducible NWRSA demo harness.

Generates a deterministic rural two-lane section sample (200 m sections in the
NWRSA convention) and runs the combined reactive + proactive Network-Wide Road
Safety Assessment, publishing a Directive-compliant ≥3-category classification
under ``data/reporting/nwrsa/``.

Run::

    PYTHONPATH=src python3 tools/nwrsa_demo.py

Deterministic; the committed extract is a structurally-faithful rural sample
(real bulk runs point ``run_nwrsa_assessment`` at production segment tables).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.nwrsa import run_nwrsa_assessment

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACT = Path("data/external/nwrsa_demo/rural_sections.csv")
REPORT_DIR = Path("data/reporting/nwrsa")

FIELDNAMES = [
    "segment_id",
    "maxspeed_numeric",
    "width_numeric",
    "sinuosity",
    "lanes_numeric",
    "node_degree_max",
    "is_intersection_connector",
    "road_class_rank",
    "bridge",
    "tunnel",
    "segment_length_m",
    "crash_count",
    "fatal_crash_count",
    "injury_crash_count",
]


def _write_rural_sections(path: Path, count: int = 120, seed: int = 7) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for index in range(count):
            # Rural two-lane character: mostly 90 km/h, narrow, curvy, single lane.
            speed = rng.choice([70, 80, 90, 90, 100])
            width = round(rng.uniform(5.0, 7.5), 1)
            sinuosity = round(rng.uniform(1.0, 1.3), 3)
            # Crashes are sparse and correlate loosely with poor geometry.
            geometry_risk = (speed - 70) / 30 + (7.5 - width) / 2.5 + (sinuosity - 1.0) / 0.3
            crash_count = max(0, int(rng.gauss(geometry_risk, 1.0)))
            fatal = 1 if (crash_count >= 2 and rng.random() < 0.3) else 0
            writer.writerow(
                {
                    "segment_id": f"R-{index:04d}",
                    "maxspeed_numeric": speed,
                    "width_numeric": width,
                    "sinuosity": sinuosity,
                    "lanes_numeric": 2,
                    "node_degree_max": rng.choice([2, 2, 3, 4]),
                    "is_intersection_connector": 1 if rng.random() < 0.15 else 0,
                    "road_class_rank": rng.choice([3, 4, 4, 5]),
                    "bridge": "yes" if rng.random() < 0.05 else "",
                    "tunnel": "",
                    "segment_length_m": 200,
                    "crash_count": crash_count,
                    "fatal_crash_count": fatal,
                    "injury_crash_count": max(crash_count - fatal, 0),
                }
            )


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_rural_sections(EXTRACT)
    result = run_nwrsa_assessment(
        sections_path=EXTRACT,
        output_dir=REPORT_DIR,
        reactive_weight=0.5,
        proactive_weight=0.5,
        categories=3,
    )
    print(f"sections assessed -> {result['section_count']}")
    print(f"category distribution -> {result['category_distribution']}")
    print(f"classification -> {result['classification_csv_path']}")
    print(f"manifest -> {result['manifest_path']}")


if __name__ == "__main__":
    main()
