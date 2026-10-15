"""Intersectional analysis demo harness.

Generates a deterministic casualty sample with sex / age-band / area-type /
disability dimensions and runs the privacy-careful intersectional analysis,
publishing suppressed stratified aggregates under
``data/reporting/intersectional_analysis/``.

Run::

    PYTHONPATH=src python3 tools/intersectional_demo.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.intersectional_analysis import run_intersectional_analysis

REPO_ROOT = Path(__file__).resolve().parents[1]
CASUALTIES = Path("data/external/intersectional_demo/casualties.csv")
REPORT_DIR = Path("data/reporting/intersectional_analysis")

FIELDS = ["sex", "age_band", "area_type", "disability", "severity_level"]
SEXES = ["F", "M"]
AGE_BANDS = ["0-17", "18-24", "25-64", "65+"]
AREAS = ["rural", "urban"]


def _write_casualties(path: Path, count: int = 1200, seed: int = 37) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for _ in range(count):
            sex = rng.choice(SEXES)
            age = rng.choice(AGE_BANDS)
            area = rng.choice(AREAS)
            disability = "yes" if rng.random() < 0.08 else "no"
            # Rural + elderly + male skews more fatal (illustrative).
            fatal_p = 0.05 + (0.05 if area == "rural" else 0) + (0.05 if age == "65+" else 0) + (0.02 if sex == "M" else 0)
            severity = "fatal" if rng.random() < fatal_p else "injury"
            writer.writerow({
                "sex": sex, "age_band": age, "area_type": area,
                "disability": disability, "severity_level": severity,
            })


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_casualties(CASUALTIES)
    result = run_intersectional_analysis(casualties_path=CASUALTIES, output_dir=REPORT_DIR, min_cell=10)
    print(f"sex strata: {result['sex_strata']}")
    print(f"intersectional strata (surviving): {result['intersectional_strata']}")
    print(f"intersectional strata suppressed (below k-anonymity floor): {result['intersectional_suppressed']}")


if __name__ == "__main__":
    main()
