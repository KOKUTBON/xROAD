"""Elderly & disabled road-user safety demo harness.

Generates a deterministic segment sample with age-band and accessibility-
infrastructure attributes and runs the elderly/disabled assessment, publishing
priority + tailored-countermeasure outputs under
``data/reporting/elderly_disabled_safety/``.

Run::

    PYTHONPATH=src python3 tools/elderly_disabled_demo.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.elderly_disabled_safety import run_elderly_disabled_assessment

REPO_ROOT = Path(__file__).resolve().parents[1]
SEG = Path("data/external/elderly_disabled_demo/segments.csv")
REPORT_DIR = Path("data/reporting/elderly_disabled_safety")

FIELDS = [
    "segment_id", "elderly_casualty_count", "casualty_count", "area_elderly_population_share",
    "pedestrian_crossing", "refuge_island", "dropped_kerb", "lit", "involves_vru",
]


def _write_segments(path: Path, count: int = 90, seed: int = 31) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(count):
            casualties = rng.randint(0, 5)
            has_age = rng.random() < 0.6  # 60% of segments have recorded age
            elderly = rng.randint(0, casualties) if (has_age and casualties) else ""
            writer.writerow({
                "segment_id": f"E-{index:04d}",
                "elderly_casualty_count": elderly if has_age else "",
                "casualty_count": casualties,
                "area_elderly_population_share": round(rng.uniform(0.12, 0.34), 3) if not has_age else "",
                "pedestrian_crossing": "yes" if rng.random() < 0.45 else "no",
                "refuge_island": "yes" if rng.random() < 0.25 else "no",
                "dropped_kerb": "yes" if rng.random() < 0.5 else "no",
                "lit": "yes" if rng.random() < 0.7 else "no",
                "involves_vru": "yes" if rng.random() < 0.3 else "no",
            })


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_segments(SEG)
    result = run_elderly_disabled_assessment(segments_path=SEG, output_dir=REPORT_DIR)
    summary = result["summary"]
    print(f"segments: {summary['segment_count']} | scored: {summary['scored_count']}")
    print(f"mean priority: {summary['mean_priority']} | high-priority: {summary['high_priority_segments']}")
    print(f"countermeasure demand: {summary['countermeasure_demand']}")


if __name__ == "__main__":
    main()
