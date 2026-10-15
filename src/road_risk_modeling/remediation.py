"""Reports and review exports for post-match remediation workflows."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _distance_bin(distance_m: float) -> str:
    if distance_m <= 60:
        return "0-60"
    if distance_m <= 75:
        return "60-75"
    if distance_m <= 100:
        return "75-100"
    if distance_m <= 150:
        return "100-150"
    if distance_m <= 250:
        return "150-250"
    return "250+"


def _distance_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "min": None,
            "mean": None,
            "p50": None,
            "p90": None,
            "p99": None,
            "max": None,
        }
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "mean": mean(ordered),
        "p50": ordered[len(ordered) // 2],
        "p90": ordered[int(len(ordered) * 0.9)],
        "p99": ordered[min(int(len(ordered) * 0.99), len(ordered) - 1)],
        "max": ordered[-1],
    }


def analyze_match_results(
    matched_path: str | Path,
    unmatched_path: str | Path,
    output_dir: str | Path | None = None,
    thresholds_m: tuple[int, ...] = (50, 60, 75, 100, 150, 250, 500, 1000),
    review_limit: int = 200,
) -> dict[str, Any]:
    matched_input = Path(matched_path)
    unmatched_input = Path(unmatched_path)
    output_root = Path(output_dir) if output_dir else matched_input.parent
    output_root.mkdir(parents=True, exist_ok=True)

    report_path = output_root / "remediation_report.json"
    review_path = output_root / "review_candidates.jsonl"

    with matched_input.open("r", encoding="utf-8") as matched_handle:
        matched_rows = [json.loads(line) for line in matched_handle]
    with unmatched_input.open("r", encoding="utf-8") as unmatched_handle:
        unmatched_rows = [json.loads(line) for line in unmatched_handle]

    matched_distances = [float(row["match_distance_m"]) for row in matched_rows if row.get("match_distance_m") is not None]
    unmatched_distances = [float(row["match_distance_m"]) for row in unmatched_rows if row.get("match_distance_m") is not None]

    unmatched_distance_bins = Counter(_distance_bin(distance) for distance in unmatched_distances)
    unmatched_city_counts = Counter(str(row.get("city_code")) for row in unmatched_rows)
    unmatched_province_counts = Counter(str(row.get("province_code")) for row in unmatched_rows)
    unmatched_quality_flag_counts = Counter(flag for row in unmatched_rows for flag in row.get("quality_flags", []))
    unmatched_road_code_counts = Counter(
        (row.get("extra", {}).get("legacy_location", {}).get("road_code") or "<missing>")
        for row in unmatched_rows
    )
    unmatched_road_description_counts = Counter(
        (row.get("extra", {}).get("legacy_location", {}).get("road_description") or "<missing>")
        for row in unmatched_rows
    )

    threshold_sweep = {
        str(threshold): len(matched_rows)
        + sum(1 for row in unmatched_rows if row.get("match_distance_m") is not None and float(row["match_distance_m"]) <= threshold)
        for threshold in thresholds_m
    }

    review_candidates = sorted(
        unmatched_rows,
        key=lambda row: float(row.get("match_distance_m") or 10**18),
    )[:review_limit]
    review_export_rows = []
    with review_path.open("w", encoding="utf-8") as review_handle:
        for row in review_candidates:
            export_row = {
                "crash_id": row.get("crash_id"),
                "source_unique_key": row.get("source_unique_key"),
                "city_code": row.get("city_code"),
                "province_code": row.get("province_code"),
                "match_distance_m": row.get("match_distance_m"),
                "road_code": row.get("extra", {}).get("legacy_location", {}).get("road_code"),
                "road_description": row.get("extra", {}).get("legacy_location", {}).get("road_description"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "quality_flags": row.get("quality_flags", []),
                "segment_id": row.get("segment_id"),
            }
            review_export_rows.append(export_row)
            review_handle.write(json.dumps(export_row, ensure_ascii=True, sort_keys=True) + "\n")

    report = {
        "inputs": {
            "matched_path": str(matched_input),
            "matched_sha256": _sha256(matched_input),
            "unmatched_path": str(unmatched_input),
            "unmatched_sha256": _sha256(unmatched_input),
        },
        "outputs": {
            "report_path": str(report_path),
            "review_path": str(review_path),
        },
        "stats": {
            "matched_records": len(matched_rows),
            "unmatched_records": len(unmatched_rows),
            "match_rate": len(matched_rows) / (len(matched_rows) + len(unmatched_rows)) if (matched_rows or unmatched_rows) else None,
        },
        "matched_distance_stats_m": _distance_stats(matched_distances),
        "unmatched_distance_stats_m": _distance_stats(unmatched_distances),
        "unmatched_distance_bins": dict(sorted(unmatched_distance_bins.items())),
        "threshold_sweep_records_within_distance": threshold_sweep,
        "unmatched_quality_flag_counts": dict(sorted(unmatched_quality_flag_counts.items())),
        "top_unmatched_cities": dict(unmatched_city_counts.most_common(20)),
        "top_unmatched_provinces": dict(unmatched_province_counts.most_common(20)),
        "top_unmatched_road_codes": dict(unmatched_road_code_counts.most_common(20)),
        "top_unmatched_road_descriptions": dict(unmatched_road_description_counts.most_common(20)),
        "review_candidates_preview": review_export_rows[:20],
    }

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "report_path": str(report_path),
        "report_sha256": _sha256(report_path),
        "review_path": str(review_path),
        "review_sha256": _sha256(review_path),
        "stats": report["stats"],
    }
