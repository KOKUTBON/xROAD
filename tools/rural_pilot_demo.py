"""Rural pilot end-to-end demo.

Runs a rural two-lane network end-to-end: variable-length OSM-style edges →
**200 m sectioning** with rural features (`rural_sectioning`) → **NWRSA**
combined reactive + proactive classification (`nwrsa`), showing how rural
sections feed the network safety assessment.

Run::

    PYTHONPATH=src python3 tools/rural_pilot_demo.py

Deterministic; the committed extract is a structurally-faithful rural sample.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.nwrsa import run_nwrsa_assessment
from road_risk_modeling.rural_sectioning import run_rural_sectioning

REPO_ROOT = Path(__file__).resolve().parents[1]
EDGES = Path("data/external/rural_pilot/rural_edges.csv")
SECTION_DIR = Path("data/reporting/rural_pilot/sections")
NWRSA_DIR = Path("data/reporting/rural_pilot/nwrsa")

EDGE_FIELDS = [
    "segment_id",
    "segment_length_m",
    "maxspeed_numeric",
    "width_numeric",
    "sinuosity",
    "lanes_numeric",
    "oneway",
    "road_class_rank",
    "crash_count",
    "fatal_crash_count",
    "injury_crash_count",
]


def _write_rural_edges(path: Path, count: int = 40, seed: int = 19) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EDGE_FIELDS)
        writer.writeheader()
        for index in range(count):
            # Variable-length rural edges (150 m – 2 km) that 200 m sectioning
            # will split into multiple working sections.
            length = rng.choice([180, 350, 600, 900, 1400, 2000])
            speed = rng.choice([70, 80, 90, 90, 100])
            width = round(rng.uniform(5.0, 7.5), 1)
            sinuosity = round(rng.uniform(1.0, 1.32), 3)
            geometry_risk = (speed - 70) / 30 + (7.5 - width) / 2.5 + (sinuosity - 1.0) / 0.3
            crashes = max(0, int(rng.gauss(geometry_risk, 1.2)))
            fatal = 1 if (crashes >= 2 and rng.random() < 0.35) else 0
            writer.writerow(
                {
                    "segment_id": f"E-{index:04d}",
                    "segment_length_m": length,
                    "maxspeed_numeric": speed,
                    "width_numeric": width,
                    "sinuosity": sinuosity,
                    "lanes_numeric": 2,
                    "oneway": "no",
                    "road_class_rank": rng.choice([3, 4, 4, 5]),
                    "crash_count": crashes,
                    "fatal_crash_count": fatal,
                    "injury_crash_count": max(crashes - fatal, 0),
                }
            )


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_rural_edges(EDGES)

    sectioning = run_rural_sectioning(segments_path=EDGES, output_dir=SECTION_DIR)
    print(f"edges -> sections: {sectioning['summary']['section_count']} sections")
    print(f"sparse-cell share: {sectioning['summary']['sparse_cell_share']}")
    print(f"curvature: {sectioning['summary']['curvature_distribution']}")

    # Feed the 200 m rural sections straight into the NWRSA assessment.
    nwrsa = run_nwrsa_assessment(
        sections_path=sectioning["sections_csv_path"],
        output_dir=NWRSA_DIR,
        categories=3,
    )
    print(f"NWRSA sections classified: {nwrsa['section_count']}")
    print(f"NWRSA category distribution: {nwrsa['category_distribution']}")


if __name__ == "__main__":
    main()
