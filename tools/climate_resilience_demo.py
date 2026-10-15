"""Climate-resilience demo harness.

Generates a deterministic rural network + an extreme-weather hazard layer
(flood / heat / snow-ice / wind, the shape a Copernicus/EEA hazard-grid join
produces) and runs the climate-resilience assessment, publishing a per-segment
classification CSV, a **map-ready GeoJSON** risk surface, and a summary under
``data/reporting/climate_resilience/``.

Run::

    PYTHONPATH=src python3 tools/climate_resilience_demo.py

Deterministic; the committed extracts are structurally-faithful samples (real
runs ingest licensed Copernicus/EEA hazard layers).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.climate_resilience import HAZARD_KINDS, run_climate_resilience_assessment

REPO_ROOT = Path(__file__).resolve().parents[1]
SEG = Path("data/external/climate_demo/segments.csv")
HAZ = Path("data/external/climate_demo/hazards.csv")
REPORT_DIR = Path("data/reporting/climate_resilience")


def _write_inputs(seg: Path, haz: Path, count: int = 80, seed: int = 23) -> None:
    rng = random.Random(seed)
    seg.parent.mkdir(parents=True, exist_ok=True)
    seg_fields = [
        "segment_id", "maxspeed_numeric", "sinuosity", "bridge", "tunnel",
        "road_class_rank", "latitude", "longitude",
        "crash_count", "adverse_weather_crash_count",
    ]
    haz_fields = ["segment_id", "hazard_kind", "intensity"]
    with seg.open("w", encoding="utf-8", newline="") as sh, haz.open("w", encoding="utf-8", newline="") as hh:
        seg_writer = csv.DictWriter(sh, fieldnames=seg_fields)
        seg_writer.writeheader()
        haz_writer = csv.DictWriter(hh, fieldnames=haz_fields)
        haz_writer.writeheader()
        for index in range(count):
            crash = max(0, int(rng.gauss(1.0, 1.2)))
            adverse = min(crash, int(round(crash * rng.uniform(0.1, 0.9))))
            has_bridge = rng.random() < 0.18
            seg_writer.writerow({
                "segment_id": f"C-{index:04d}",
                "maxspeed_numeric": rng.choice([70, 80, 90, 100]),
                "sinuosity": round(rng.uniform(1.0, 1.3), 3),
                "bridge": "yes" if has_bridge else "",
                "tunnel": "yes" if rng.random() < 0.04 else "",
                "road_class_rank": rng.choice([2, 3, 4, 5]),
                "latitude": round(41.0 + rng.uniform(-0.4, 0.4), 5),
                "longitude": round(16.8 + rng.uniform(-0.4, 0.4), 5),
                "crash_count": crash,
                "adverse_weather_crash_count": adverse,
            })
            # Each segment gets a couple of hazard exposures.
            for hazard in rng.sample(HAZARD_KINDS, k=rng.randint(1, 3)):
                haz_writer.writerow({
                    "segment_id": f"C-{index:04d}",
                    "hazard_kind": hazard,
                    "intensity": round(rng.uniform(0.1, 0.95), 3),
                })


def main() -> None:
    os.chdir(REPO_ROOT)
    _write_inputs(SEG, HAZ)
    result = run_climate_resilience_assessment(
        segments_path=SEG, hazards_path=HAZ, output_dir=REPORT_DIR
    )
    summary = result["summary"]
    print(f"segments scored: {summary['scored_count']}")
    print(f"mean climate risk: {summary['mean_climate_risk']} | high-risk: {summary['high_risk_segments']}")
    print(f"dominant hazards: {summary['dominant_hazard_distribution']}")
    print(f"map-ready GeoJSON -> {result['geojson_path']}")


if __name__ == "__main__":
    main()
