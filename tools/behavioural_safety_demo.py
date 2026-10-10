"""Behavioural-safety analytics demo harness.

Generates a deterministic crash sample with behavioural signals (observed speed
vs limit, time-of-day, VRU involvement) across a few rural corridors and runs
the aggregate, privacy-safe enforcement-prioritisation analysis, publishing the
result under ``data/reporting/behavioural_safety/``.

Run::

    PYTHONPATH=src python3 tools/behavioural_safety_demo.py

Deterministic; aggregate-only (corridor x time-of-day), small cells suppressed.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.behavioural_safety import run_behavioural_analysis

REPO_ROOT = Path(__file__).resolve().parents[1]
CRASHES = Path("data/external/behavioural_demo/crashes.csv")
REPORT_DIR = Path("data/reporting/behavioural_safety")

FIELDS = ["corridor_id", "occurred_hour", "observed_p85_speed_kph", "observed_speed_limit_kph", "involves_vru"]

# A few rural corridors with different behavioural profiles.
CORRIDORS = [
    ("SS16", 50, 0.7),   # high speeding pressure
    ("SP231", 70, 0.3),
    ("SS96", 90, 0.2),
    ("SP1", 50, 0.5),
]


def _write_crashes(path: Path, count: int = 400, seed: int = 29) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for _ in range(count):
            corridor, limit, speed_bias = rng.choice(CORRIDORS)
            # p85 speed around the limit, biased upward on speeding corridors.
            p85 = limit + rng.gauss(speed_bias * 20.0, 6.0)
            hour = rng.randint(0, 23)
            writer.writerow({
                "corridor_id": corridor,
                "occurred_hour": hour,
                "observed_p85_speed_kph": round(max(0.0, p85), 1),
                "observed_speed_limit_kph": limit,
                "involves_vru": "yes" if rng.random() < 0.12 else "no",
            })


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_crashes(CRASHES)
    result = run_behavioural_analysis(crashes_path=CRASHES, output_dir=REPORT_DIR, min_cell=5)
    print(f"priority cells (corridor x time-of-day): {result['priority_count']}")
    print(f"cells suppressed (below anonymity floor): {result['cells_suppressed']}")
    print(f"priorities CSV -> {result['enforcement_priorities_csv_path']}")


if __name__ == "__main__":
    main()
