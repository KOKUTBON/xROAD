"""Quality and geospatial QA for canonical crash records."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


MISSING_VALUES = (None, "", [])
KEY_FIELD_NAMES = (
    "source_unique_key",
    "source_record_id",
    "province_code",
    "city_code",
    "latitude",
    "longitude",
    "roadway_type",
    "intersection_type",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _derive_expected_severity(fatalities: int, injuries: int) -> str:
    if fatalities > 0:
        return "fatal"
    if injuries > 0:
        return "injury"
    return "no_injury"


def _top_counts(counter: Counter[str], top_n: int) -> dict[str, int]:
    return dict(counter.most_common(top_n))


def _duplicate_summary(counter: Counter[str], top_n: int) -> dict[str, Any]:
    duplicates = [(key, count) for key, count in counter.items() if count > 1]
    duplicates.sort(key=lambda item: (-item[1], item[0]))
    return {
        "duplicate_key_count": len(duplicates),
        "duplicate_record_count": sum(count for _, count in duplicates),
        "sample": [{ "key": key, "count": count } for key, count in duplicates[:top_n]],
    }


def analyze_canonical_jsonl(records_path: str | Path, top_n: int = 20) -> dict[str, Any]:
    path = Path(records_path)

    severity_counts: Counter[str] = Counter()
    roadway_type_counts: Counter[str] = Counter()
    intersection_type_counts: Counter[str] = Counter()
    quality_flag_counts: Counter[str] = Counter()
    province_counts: Counter[str] = Counter()
    city_counts: Counter[str] = Counter()
    missing_field_counts: Counter[str] = Counter()
    crash_id_counts: Counter[str] = Counter()
    source_key_counts: Counter[str] = Counter()
    raw_source_record_id_counts: Counter[str] = Counter()

    total_records = 0
    coordinate_complete_records = 0
    records_with_any_quality_flag = 0
    severity_mismatch_count = 0
    negative_outcome_count = 0
    coordinates_outside_country_bounds = 0
    coordinates_outside_jurisdiction_bounds = 0

    total_fatalities = 0
    total_injuries = 0

    min_latitude: float | None = None
    max_latitude: float | None = None
    min_longitude: float | None = None
    max_longitude: float | None = None
    outside_jurisdiction_samples: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            total_records += 1

            crash_id = record.get("crash_id")
            if crash_id:
                crash_id_counts[str(crash_id)] += 1

            raw_source_record_id = record.get("source_record_id")
            if raw_source_record_id:
                raw_source_record_id_counts[str(raw_source_record_id)] += 1

            source_system = record.get("source_system")
            source_unique_key = record.get("source_unique_key")
            if source_system and source_unique_key:
                source_key_counts[f"{source_system}:{source_unique_key}"] += 1

            severity_counts[str(record.get("severity_level") or "unknown")] += 1
            roadway_type_counts[str(record.get("roadway_type") or "unknown")] += 1
            intersection_type_counts[str(record.get("intersection_type") or "unknown")] += 1

            province_value = record.get("province_code")
            if province_value not in MISSING_VALUES:
                province_counts[str(province_value)] += 1

            city_value = record.get("city_code")
            if city_value not in MISSING_VALUES:
                city_counts[str(city_value)] += 1

            for field_name in KEY_FIELD_NAMES:
                if record.get(field_name) in MISSING_VALUES:
                    missing_field_counts[field_name] += 1

            quality_flags = [str(flag) for flag in (record.get("quality_flags") or [])]
            if quality_flags:
                records_with_any_quality_flag += 1
            for flag in quality_flags:
                quality_flag_counts[flag] += 1
            if "coordinates_outside_expected_country_bounds" in quality_flags:
                coordinates_outside_country_bounds += 1
            if "coordinates_outside_expected_jurisdiction_bounds" in quality_flags:
                coordinates_outside_jurisdiction_bounds += 1
                if len(outside_jurisdiction_samples) < top_n:
                    outside_jurisdiction_samples.append(
                        {
                            "crash_id": record.get("crash_id"),
                            "source_record_id": record.get("source_record_id"),
                            "latitude": record.get("latitude"),
                            "longitude": record.get("longitude"),
                        }
                    )

            fatalities = int(record.get("fatalities") or 0)
            injuries = int(record.get("injuries") or 0)
            total_fatalities += fatalities
            total_injuries += injuries

            if fatalities < 0 or injuries < 0:
                negative_outcome_count += 1

            expected_severity = _derive_expected_severity(fatalities, injuries)
            if record.get("severity_level") != expected_severity:
                severity_mismatch_count += 1

            latitude = record.get("latitude")
            longitude = record.get("longitude")
            if latitude is not None and longitude is not None:
                coordinate_complete_records += 1
                lat = float(latitude)
                lon = float(longitude)
                min_latitude = lat if min_latitude is None else min(min_latitude, lat)
                max_latitude = lat if max_latitude is None else max(max_latitude, lat)
                min_longitude = lon if min_longitude is None else min(min_longitude, lon)
                max_longitude = lon if max_longitude is None else max(max_longitude, lon)

    return {
        "records_path": str(path),
        "records_sha256": _sha256(path),
        "stats": {
            "total_records": total_records,
            "coordinate_complete_records": coordinate_complete_records,
            "records_with_any_quality_flag": records_with_any_quality_flag,
            "severity_mismatch_count": severity_mismatch_count,
            "negative_outcome_count": negative_outcome_count,
            "coordinates_outside_country_bounds": coordinates_outside_country_bounds,
            "coordinates_outside_jurisdiction_bounds": coordinates_outside_jurisdiction_bounds,
            "total_fatalities": total_fatalities,
            "total_injuries": total_injuries,
            "distinct_provinces": len(province_counts),
            "distinct_cities": len(city_counts),
            "unique_crash_ids": len(crash_id_counts),
            "unique_source_records": len(source_key_counts),
            "unique_raw_source_record_ids": len(raw_source_record_id_counts),
        },
        "missing_field_counts": dict(sorted(missing_field_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "roadway_type_counts": dict(sorted(roadway_type_counts.items())),
        "intersection_type_counts": dict(sorted(intersection_type_counts.items())),
        "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        "coordinate_bounds": {
            "min_latitude": min_latitude,
            "max_latitude": max_latitude,
            "min_longitude": min_longitude,
            "max_longitude": max_longitude,
        },
        "outside_jurisdiction_samples": outside_jurisdiction_samples,
        "top_provinces": _top_counts(province_counts, top_n),
        "top_cities": _top_counts(city_counts, top_n),
        "duplicate_crash_ids": _duplicate_summary(crash_id_counts, top_n),
        "duplicate_source_records": _duplicate_summary(source_key_counts, top_n),
        "duplicate_raw_source_record_ids": _duplicate_summary(raw_source_record_id_counts, top_n),
    }


def write_canonical_quality_report(
    records_path: str | Path,
    output_path: str | Path | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    report = analyze_canonical_jsonl(records_path, top_n=top_n)
    destination = Path(output_path) if output_path else Path(records_path).with_suffix(".qa.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "records_path": str(Path(records_path)),
        "report_path": str(destination),
        "report_sha256": _sha256(destination),
        "stats": report["stats"],
    }
