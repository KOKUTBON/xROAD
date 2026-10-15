#!/usr/bin/env python3
"""One-command Bari historical-weather ingestion and crash join."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from road_risk_modeling.weather_ingestion import (
    build_weather_join_bundle,
    fetch_open_meteo,
    parse_open_meteo_payload,
)


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--crashes",
        default="data/processed/matches/bari_open_data/matched_records.jsonl",
    )
    parser.add_argument("--output-dir", default="data/processed/weather/bari")
    parser.add_argument("--cache-dir", default="cache/weather/open_meteo")
    parser.add_argument("--weather-json")
    args = parser.parse_args()
    crash_path = Path(args.crashes)
    crashes = _jsonl(crash_path)
    timestamps = [str(row["occurred_at"]) for row in crashes if row.get("occurred_at")]
    if not timestamps:
        raise RuntimeError("Crash input has no timestamps.")
    coordinates = [
        (float(row["latitude"]), float(row["longitude"]))
        for row in crashes
        if row.get("latitude") is not None and row.get("longitude") is not None
    ]
    latitude = sum(value[0] for value in coordinates) / len(coordinates)
    longitude = sum(value[1] for value in coordinates) / len(coordinates)
    if args.weather_json:
        weather_path = Path(args.weather_json)
        payload = json.loads(weather_path.read_text(encoding="utf-8"))
    else:
        payload, weather_path = fetch_open_meteo(
            latitude=latitude,
            longitude=longitude,
            start_date=min(timestamps)[:10],
            end_date=max(timestamps)[:10],
            cache_dir=args.cache_dir,
        )
    observations = parse_open_meteo_payload(payload)
    result = build_weather_join_bundle(
        crashes=crashes,
        observations=observations,
        output_dir=args.output_dir,
        crash_source_path=crash_path,
        weather_source_path=weather_path,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
