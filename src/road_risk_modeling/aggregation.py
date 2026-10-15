"""Aggregate matched crash records into segment-level modeling tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .connector_observation_schema import OBSERVED_CONNECTOR_NUMERIC_COLUMNS
from .exposure_policy import BUILT_ENV_COUNT_COLUMNS, EXPOSURE_NUMERIC_COLUMNS, POI_COUNT_COLUMNS


SEGMENT_METADATA_COLUMNS = [
    "highway",
    "lanes",
    "maxspeed",
    "oneway",
    "ref",
    "bridge",
    "junction",
    "width",
    "access",
    "tunnel",
    "bearing_bin",
]

SEGMENT_ENRICHMENT_NUMERIC_COLUMNS = [
    "node_degree_u",
    "node_degree_v",
    "node_degree_min",
    "node_degree_max",
    "node_degree_sum",
    "is_dead_end",
    "is_intersection_connector",
    "straight_distance_m",
    "sinuosity",
    "road_class_rank",
    "segment_name_present",
    *POI_COUNT_COLUMNS,
    *BUILT_ENV_COUNT_COLUMNS,
    "exposure_proxy_index",
    *OBSERVED_CONNECTOR_NUMERIC_COLUMNS,
    *EXPOSURE_NUMERIC_COLUMNS,
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_tabular_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for aggregation. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd


def _normalize_list_like(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("[") and text.endswith("]"):
        parts = [part.strip().strip("'").strip('"') for part in text[1:-1].split(",") if part.strip()]
        return "|".join(parts) if parts else None
    return text


def _extract_numeric(value: Any) -> float | None:
    text = _normalize_list_like(value)
    if text is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def aggregate_segment_year_metrics(
    matched_path: str | Path,
    segments_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    gpd, pd = _load_tabular_stack()
    matched_input = Path(matched_path)
    segments_input = Path(segments_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    geojson_path = output_root / "segment_year_metrics.geojson"
    csv_path = output_root / "segment_year_metrics.csv"
    manifest_path = output_root / "segment_year_metrics.manifest.json"

    segments = gpd.read_file(segments_input)
    required_segment_columns = {"segment_id", "segment_length_m", "geometry"}
    missing_segment_columns = required_segment_columns.difference(segments.columns)
    if missing_segment_columns:
        raise RuntimeError(f"Segments file is missing required columns: {sorted(missing_segment_columns)}")

    with matched_input.open("r", encoding="utf-8") as handle:
        matched_rows = [json.loads(line) for line in handle]
    if not matched_rows:
        raise RuntimeError(f"Matched input is empty: {matched_input}")

    frame = pd.DataFrame(matched_rows)
    if "segment_id" not in frame.columns or "occurred_year" not in frame.columns:
        raise RuntimeError("Matched records must contain 'segment_id' and 'occurred_year'.")

    frame["fatal_crash_count"] = (frame["severity_level"] == "fatal").astype(int)
    frame["injury_crash_count"] = (frame["severity_level"] == "injury").astype(int)
    frame["match_distance_m"] = frame["match_distance_m"].astype(float)
    frame["fatalities"] = frame["fatalities"].astype(int)
    frame["injuries"] = frame["injuries"].astype(int)

    observed_years = sorted(int(year) for year in frame["occurred_year"].dropna().unique())
    segment_year_index = pd.MultiIndex.from_product(
        [segments["segment_id"].astype(str).tolist(), observed_years],
        names=["segment_id", "occurred_year"],
    ).to_frame(index=False)

    aggregated = (
        frame.groupby(["segment_id", "occurred_year"], as_index=False)
        .agg(
            crash_count=("crash_id", "count"),
            fatal_crash_count=("fatal_crash_count", "sum"),
            injury_crash_count=("injury_crash_count", "sum"),
            fatalities_total=("fatalities", "sum"),
            injuries_total=("injuries", "sum"),
            mean_match_distance_m=("match_distance_m", "mean"),
        )
    )

    base_columns = ["segment_id", "segment_length_m", "geometry"] + [
        column for column in SEGMENT_METADATA_COLUMNS if column in segments.columns
    ] + [
        column for column in SEGMENT_ENRICHMENT_NUMERIC_COLUMNS if column in segments.columns
    ]
    base_segments = segments[base_columns].copy()
    for column in SEGMENT_METADATA_COLUMNS:
        if column in base_segments.columns:
            base_segments[column] = base_segments[column].map(_normalize_list_like)
    for column in SEGMENT_ENRICHMENT_NUMERIC_COLUMNS:
        if column in base_segments.columns:
            base_segments[column] = pd.to_numeric(base_segments[column], errors="coerce")

    base_segments["lanes_numeric"] = base_segments["lanes"].map(_extract_numeric) if "lanes" in base_segments.columns else None
    base_segments["maxspeed_numeric"] = base_segments["maxspeed"].map(_extract_numeric) if "maxspeed" in base_segments.columns else None
    base_segments["width_numeric"] = base_segments["width"].map(_extract_numeric) if "width" in base_segments.columns else None
    base_segments["is_roundabout"] = (
        base_segments["junction"].fillna("").astype(str).str.contains("roundabout", case=False)
        if "junction" in base_segments.columns
        else False
    )
    model_frame = segment_year_index.merge(aggregated, on=["segment_id", "occurred_year"], how="left")
    model_frame = model_frame.merge(base_segments, on="segment_id", how="left")

    zero_fill_columns = [
        "crash_count",
        "fatal_crash_count",
        "injury_crash_count",
        "fatalities_total",
        "injuries_total",
    ]
    for column in zero_fill_columns:
        model_frame[column] = model_frame[column].fillna(0).astype(int)

    model_frame["mean_match_distance_m"] = model_frame["mean_match_distance_m"].fillna(0.0)
    model_frame["crash_density_per_km"] = model_frame.apply(
        lambda row: (row["crash_count"] / (row["segment_length_m"] / 1000.0)) if row["segment_length_m"] else 0.0,
        axis=1,
    )
    model_frame["fatalities_per_km"] = model_frame.apply(
        lambda row: (row["fatalities_total"] / (row["segment_length_m"] / 1000.0)) if row["segment_length_m"] else 0.0,
        axis=1,
    )
    model_frame["injuries_per_km"] = model_frame.apply(
        lambda row: (row["injuries_total"] / (row["segment_length_m"] / 1000.0)) if row["segment_length_m"] else 0.0,
        axis=1,
    )
    if "exposure_proxy_index" in model_frame.columns:
        model_frame["crashes_per_exposure_proxy"] = model_frame.apply(
            lambda row: (row["crash_count"] / row["exposure_proxy_index"]) if row["exposure_proxy_index"] else 0.0,
            axis=1,
        )
        model_frame["fatalities_per_exposure_proxy"] = model_frame.apply(
            lambda row: (row["fatalities_total"] / row["exposure_proxy_index"]) if row["exposure_proxy_index"] else 0.0,
            axis=1,
        )
        model_frame["injuries_per_exposure_proxy"] = model_frame.apply(
            lambda row: (row["injuries_total"] / row["exposure_proxy_index"]) if row["exposure_proxy_index"] else 0.0,
            axis=1,
        )
    if "exposure_policy_index" in model_frame.columns:
        model_frame["crashes_per_exposure_policy"] = model_frame.apply(
            lambda row: (row["crash_count"] / row["exposure_policy_index"]) if row["exposure_policy_index"] else 0.0,
            axis=1,
        )
        model_frame["fatalities_per_exposure_policy"] = model_frame.apply(
            lambda row: (row["fatalities_total"] / row["exposure_policy_index"]) if row["exposure_policy_index"] else 0.0,
            axis=1,
        )
        model_frame["injuries_per_exposure_policy"] = model_frame.apply(
            lambda row: (row["injuries_total"] / row["exposure_policy_index"]) if row["exposure_policy_index"] else 0.0,
            axis=1,
        )

    metric_gdf = gpd.GeoDataFrame(model_frame, geometry="geometry", crs=segments.crs)
    metric_gdf.to_file(geojson_path, driver="GeoJSON")
    metric_gdf.drop(columns=["geometry"]).to_csv(csv_path, index=False)

    manifest = {
        "inputs": {
            "matched_path": str(matched_input),
            "matched_sha256": _sha256(matched_input),
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
        },
        "outputs": {
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "csv_path": str(csv_path),
            "csv_sha256": _sha256(csv_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "observed_years": observed_years,
            "segment_count": int(segments["segment_id"].nunique()),
            "segment_year_rows": int(len(metric_gdf)),
            "segment_year_rows_with_crashes": int((metric_gdf["crash_count"] > 0).sum()),
            "segment_year_rows_without_crashes": int((metric_gdf["crash_count"] == 0).sum()),
            "total_crashes": int(metric_gdf["crash_count"].sum()),
            "total_fatalities": int(metric_gdf["fatalities_total"].sum()),
            "total_injuries": int(metric_gdf["injuries_total"].sum()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
