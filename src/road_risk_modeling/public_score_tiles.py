"""Public tile aggregation for published segment-score artifacts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    governance_contract_reference,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .prediction_store import _public_score_band


PUBLIC_SCORE_TILES_VERSION = "segment_score_tiles_v1"
PUBLIC_SCORE_TILES_CONTRACT_VERSION = "segment_score_tiles_public_v1"

PUBLIC_TILE_FIELDS = [
    "tile_score_id",
    "occurred_year",
    "prediction_run_label",
    "prediction_task",
    "tile_size_m",
    "tile_segment_count",
    "tile_mean_public_score_index",
    "tile_max_public_score_index",
    "tile_public_score_band",
    "tile_score_decile",
]


def _load_geo_stack() -> tuple[Any, Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
        from shapely.geometry import box  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and Shapely are required for public tile aggregation. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd, box


def _tile_contract(prediction_run_label: str, tile_size_m: float) -> dict[str, Any]:
    return {
        "resource_name": "segment_score_tiles",
        "public_contract_version": PUBLIC_SCORE_TILES_CONTRACT_VERSION,
        "prediction_store_version": PUBLIC_SCORE_TILES_VERSION,
        "prediction_run_label": prediction_run_label,
        "tile_size_m": tile_size_m,
        "public_fields": PUBLIC_TILE_FIELDS,
        "public_response_shape": {
            "type": "FeatureCollection",
            "feature_id": "tile_score_id",
            "properties": PUBLIC_TILE_FIELDS,
        },
    }


def aggregate_public_score_tiles(
    public_scores_path: str | Path,
    prediction_store_manifest_path: str | Path,
    output_dir: str | Path,
    tile_size_m: float = 500.0,
    *,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    if tile_size_m <= 0:
        raise RuntimeError("tile_size_m must be greater than 0.")

    gpd, pd, box = _load_geo_stack()

    public_scores_input = Path(public_scores_path)
    store_manifest_input = Path(prediction_store_manifest_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    public_geojson_path = output_root / "score_tiles_public.geojson"
    summary_csv_path = output_root / "score_tiles_summary.csv"
    manifest_path = output_root / "score_tiles.manifest.json"

    store_manifest = json.loads(store_manifest_input.read_text(encoding="utf-8"))
    public_scores = gpd.read_file(public_scores_input)
    if public_scores.empty:
        raise RuntimeError("Public segment-score GeoJSON is empty.")

    required_columns = {
        "segment_score_id",
        "occurred_year",
        "prediction_run_label",
        "prediction_task",
        "public_score_index",
        "public_score_band",
        "score_decile",
    }
    missing_columns = sorted(required_columns - set(public_scores.columns))
    if missing_columns:
        raise RuntimeError(
            "Public segment-score GeoJSON is missing required columns: " + ", ".join(missing_columns)
        )

    local_crs = public_scores.estimate_utm_crs() or "EPSG:3857"
    projected = public_scores.to_crs(local_crs).copy()
    projected["centroid_x"] = projected.geometry.centroid.x
    projected["centroid_y"] = projected.geometry.centroid.y
    min_x, min_y, _max_x, _max_y = projected.total_bounds
    projected["tile_col"] = ((projected["centroid_x"] - float(min_x)) / tile_size_m).apply(math.floor).astype(int)
    projected["tile_row"] = ((projected["centroid_y"] - float(min_y)) / tile_size_m).apply(math.floor).astype(int)
    projected["public_score_index"] = pd.to_numeric(projected["public_score_index"], errors="coerce")
    projected["score_decile"] = pd.to_numeric(projected["score_decile"], errors="coerce")
    if projected["public_score_index"].isna().any() or projected["score_decile"].isna().any():
        raise RuntimeError("Public segment-score GeoJSON contains invalid score fields.")

    tile_records: list[dict[str, Any]] = []
    tile_geometries: list[Any] = []
    group_fields = ["occurred_year", "prediction_run_label", "prediction_task", "tile_col", "tile_row"]
    grouped = projected.groupby(group_fields, dropna=False, sort=True)
    for (occurred_year, run_label, task, tile_col, tile_row), group in grouped:
        tile_min_x = float(min_x) + int(tile_col) * tile_size_m
        tile_min_y = float(min_y) + int(tile_row) * tile_size_m
        tile_max_x = tile_min_x + tile_size_m
        tile_max_y = tile_min_y + tile_size_m
        max_score = float(group["public_score_index"].max())
        mean_score = float(group["public_score_index"].mean())
        tile_records.append(
            {
                "tile_score_id": f"{run_label}:{int(float(occurred_year))}:{int(tile_col)}:{int(tile_row)}:{int(tile_size_m)}m",
                "occurred_year": int(float(occurred_year)),
                "prediction_run_label": str(run_label),
                "prediction_task": str(task),
                "tile_size_m": float(tile_size_m),
                "tile_segment_count": int(len(group)),
                "tile_mean_public_score_index": round(mean_score, 6),
                "tile_max_public_score_index": round(max_score, 6),
                "tile_public_score_band": _public_score_band(max_score / 100.0),
                "tile_score_decile": int(group["score_decile"].min()),
                "tile_high_band_segment_count": int(group["public_score_band"].isin(["high", "very_high"]).sum()),
                "tile_very_high_band_segment_count": int((group["public_score_band"] == "very_high").sum()),
                "tile_col": int(tile_col),
                "tile_row": int(tile_row),
            }
        )
        tile_geometries.append(box(tile_min_x, tile_min_y, tile_max_x, tile_max_y))

    tiles = gpd.GeoDataFrame(tile_records, geometry=tile_geometries, crs=local_crs).to_crs(epsg=4326)
    public_tiles = tiles[PUBLIC_TILE_FIELDS + ["geometry"]].copy()
    public_tiles.to_file(public_geojson_path, driver="GeoJSON")

    summary_rows = tiles.drop(columns="geometry").sort_values(
        by=["occurred_year", "tile_max_public_score_index", "tile_segment_count"],
        ascending=[True, False, False],
    )
    with summary_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows.columns))
        writer.writeheader()
        writer.writerows(summary_rows.to_dict(orient="records"))

    contract = _tile_contract(
        prediction_run_label=str(tiles["prediction_run_label"].iloc[0]),
        tile_size_m=float(tile_size_m),
    )
    manifest = {
        "prediction_store_version": PUBLIC_SCORE_TILES_VERSION,
        "inputs": {
            "public_scores_path": str(public_scores_input),
            "public_scores_sha256": _sha256(public_scores_input),
            "prediction_store_manifest_path": str(store_manifest_input),
            "prediction_store_manifest_sha256": _sha256(store_manifest_input),
        },
        "outputs": {
            "public_geojson_path": str(public_geojson_path),
            "public_geojson_sha256": _sha256(public_geojson_path),
            "summary_csv_path": str(summary_csv_path),
            "summary_csv_sha256": _sha256(summary_csv_path),
            "manifest_path": str(manifest_path),
        },
        "contract": contract,
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY],
            role_policy_ids=artifact_role_policy_ids(SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY),
        ),
        "stats": {
            "tile_rows": int(len(tiles)),
            "holdout_years": sorted({int(value) for value in tiles["occurred_year"].unique().tolist()}),
            "prediction_run_label": str(tiles["prediction_run_label"].iloc[0]),
            "prediction_task": str(tiles["prediction_task"].iloc[0]),
            "tile_size_m": float(tile_size_m),
            "max_tile_public_score_index": float(tiles["tile_max_public_score_index"].max()),
            "mean_tile_public_score_index": float(tiles["tile_mean_public_score_index"].mean()),
            "tiles_high_or_very_high": int(tiles["tile_public_score_band"].isin(["high", "very_high"]).sum()),
            "tiles_very_high": int((tiles["tile_public_score_band"] == "very_high").sum()),
            "covered_segment_rows": int(int(store_manifest.get("stats", {}).get("segment_score_rows", 0))),
        },
        "source_prediction_store": {
            "manifest_path": str(store_manifest_input),
            "contract": store_manifest.get("contract", {}),
            "stats": store_manifest.get("stats", {}),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "segment_scores_public_geojson",
                    public_scores_input,
                    _sha256(public_scores_input),
                ),
                _artifact_reference(
                    "segment_scores_manifest",
                    store_manifest_input,
                    _sha256(store_manifest_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "score_tiles_public_geojson",
                    public_geojson_path,
                    _sha256(public_geojson_path),
                ),
                _artifact_reference(
                    "score_tiles_summary_csv",
                    summary_csv_path,
                    _sha256(summary_csv_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "prediction_store_version": PUBLIC_SCORE_TILES_VERSION,
        "contract": {
            "public_contract_version": contract["public_contract_version"],
        },
        "stats": manifest["stats"],
    }
