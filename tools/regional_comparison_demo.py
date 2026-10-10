"""Multi-region comparative pilot demo.

Builds three diverse rural region samples (Italy / France / Sweden — illustrative
geography, climate, and safety-culture diversity) and runs the comparative NWRSA,
checking the call's eligibility constraints (>=3 regions, >=2 above EU-average
rural fatality, cross-border). Publishes the comparison under
``data/reporting/regional_comparison/``.

Run::

    PYTHONPATH=src python3 tools/regional_comparison_demo.py

The rural-fatality rates are illustrative placeholders; real submissions must use
CARE statistics (see docs/multi-region-pilots.md).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import random

from road_risk_modeling.regional_comparison import run_regional_comparison

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACT_DIR = Path("data/external/regional_demo")
REPORT_DIR = Path("data/reporting/regional_comparison")

# EU-average rural fatality rate (per million) — illustrative placeholder.
EU_AVG_RURAL_FATALITY = 66.0

# (region_id, country, illustrative rural-fatality rate, geometry-risk bias).
REGIONS = [
    ("puglia", "IT", 84.0, 0.7),       # above EU avg — Mediterranean
    ("occitanie", "FR", 75.0, 0.6),    # above EU avg — varied terrain
    ("vasterbotten", "SE", 41.0, 0.4), # below EU avg — Nordic, winter climate
]

FIELDS = [
    "segment_id", "maxspeed_numeric", "width_numeric", "sinuosity",
    "lanes_numeric", "road_class_rank", "segment_length_m", "crash_count", "fatal_crash_count",
]


def _write_region(path: Path, seed: int, risk_bias: float, count: int = 60) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(count):
            speed = rng.choice([70, 80, 90, 90, 100])
            width = round(rng.uniform(5.0, 7.5), 1)
            sinuosity = round(rng.uniform(1.0, 1.3), 3)
            geometry_risk = risk_bias * ((speed - 70) / 30 + (7.5 - width) / 2.5 + (sinuosity - 1.0) / 0.3)
            crashes = max(0, int(rng.gauss(geometry_risk, 1.0)))
            fatal = 1 if (crashes >= 2 and rng.random() < 0.3) else 0
            writer.writerow({
                "segment_id": f"{path.stem}-{index:04d}",
                "maxspeed_numeric": speed, "width_numeric": width, "sinuosity": sinuosity,
                "lanes_numeric": 2, "road_class_rank": rng.choice([3, 4, 4, 5]),
                "segment_length_m": 200, "crash_count": crashes, "fatal_crash_count": fatal,
            })


def main() -> None:
    os.chdir(REPO_ROOT)
    specs = []
    for seed, (region_id, country, rate, bias) in enumerate(REGIONS, start=51):
        path = EXTRACT_DIR / f"{region_id}.csv"
        _write_region(path, seed=seed, risk_bias=bias)
        specs.append({"region_id": region_id, "country": country, "rural_fatality_rate": rate, "path": str(path)})

    result = run_regional_comparison(
        region_specs=specs,
        output_dir=REPORT_DIR,
        eu_average_rural_fatality_rate=EU_AVG_RURAL_FATALITY,
    )
    elig = result["eligibility"]
    print(f"regions: {elig['region_count']} | countries: {elig['countries']}")
    print(f"high-fatality regions (> EU avg): {elig['high_fatality_regions']}")
    print(f"call-eligible: {elig['eligible']}")


if __name__ == "__main__":
    main()
