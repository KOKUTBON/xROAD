"""Match canonical crash points to extracted road segments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        from shapely.geometry import Point  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and Shapely are required for matching. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, Point


def match_canonical_records_to_segments(
    records_path: str | Path,
    segments_path: str | Path,
    output_dir: str | Path,
    max_distance_m: float = 50.0,
    boundary_path: str | Path | None = None,
) -> dict[str, Any]:
    gpd, Point = _load_geo_stack()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_input_path = Path(records_path)
    segments_input_path = Path(segments_path)
    boundary_input_path = Path(boundary_path) if boundary_path else None
    matched_path = output_root / "matched_records.jsonl"
    unmatched_path = output_root / "unmatched_records.jsonl"
    manifest_path = output_root / "matched_records.manifest.json"

    segments = gpd.read_file(segments_input_path)
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segments file does not contain required 'segment_id' column: {segments_input_path}")

    records: list[dict[str, Any]] = []
    with records_input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    point_records = [
        record
        for record in records
        if record.get("latitude") is not None and record.get("longitude") is not None
    ]
    for index, record in enumerate(point_records):
        record["_match_row_id"] = index
    points = gpd.GeoDataFrame(
        point_records,
        geometry=[
            Point(float(record["longitude"]), float(record["latitude"]))
            for record in point_records
        ],
        crs="EPSG:4326",
    )

    records_before_boundary_filter = len(points)
    if boundary_input_path:
        boundary = gpd.read_file(boundary_input_path).to_crs(points.crs)
        boundary_union = boundary.union_all()
        points = points.loc[points.geometry.within(boundary_union)].copy()

    local_crs = segments.estimate_utm_crs() or "EPSG:3857"
    projected_segments = segments.to_crs(local_crs)
    projected_points = points.to_crs(local_crs)

    joined = gpd.sjoin_nearest(
        projected_points,
        projected_segments[["segment_id", "geometry"]],
        how="left",
        distance_col="match_distance_m",
    )
    joined = joined.sort_values(by=["_match_row_id", "match_distance_m", "segment_id"], kind="stable")
    joined = joined.drop_duplicates(subset="_match_row_id", keep="first")

    matched_count = 0
    unmatched_count = 0

    with (
        matched_path.open("w", encoding="utf-8") as matched_handle,
        unmatched_path.open("w", encoding="utf-8") as unmatched_handle,
    ):
        for _, row in joined.iterrows():
            record = {
                key: value
                for key, value in row.drop(labels=["geometry"]).items()
                if key not in {"index_right", "_match_row_id"}
            }
            distance = row.get("match_distance_m")
            segment_id = row.get("segment_id")
            if segment_id is not None and distance is not None and float(distance) <= max_distance_m:
                record["road_segment_id"] = str(segment_id)
                record["match_distance_m"] = float(distance)
                matched_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                matched_count += 1
            else:
                record["match_distance_m"] = float(distance) if distance is not None else None
                unmatched_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                unmatched_count += 1

    manifest = {
        "inputs": {
            "records_path": str(records_input_path),
            "records_sha256": _sha256(records_input_path),
            "segments_path": str(segments_input_path),
            "segments_sha256": _sha256(segments_input_path),
            "boundary_path": str(boundary_input_path) if boundary_input_path else None,
            "boundary_sha256": _sha256(boundary_input_path) if boundary_input_path else None,
        },
        "outputs": {
            "matched_path": str(matched_path),
            "matched_sha256": _sha256(matched_path),
            "unmatched_path": str(unmatched_path),
            "unmatched_sha256": _sha256(unmatched_path),
            "manifest_path": str(manifest_path),
        },
        "policy": {
            "max_distance_m": max_distance_m,
        },
        "stats": {
            "input_records_with_coordinates": len(point_records),
            "records_after_boundary_filter": len(points),
            "records_removed_by_boundary_filter": records_before_boundary_filter - len(points),
            "matched_records": matched_count,
            "unmatched_records": unmatched_count,
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
