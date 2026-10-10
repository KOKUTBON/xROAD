"""Join normalized connector observations onto a segment layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .connector_observation_schema import OBSERVED_CONNECTOR_NUMERIC_COLUMNS
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SEGMENT_CONNECTOR_OBSERVATIONS_VERSION = "segment_connector_observations_v1"
SEGMENT_CONNECTOR_OBSERVATIONS_CONTRACT_VERSION = "segment_connector_observations_public_v1"

CAPABILITY_AGGREGATION = {
    "motorized_exposure": {
        "count_field": "observed_motorized_observation_count",
        "provider_count_field": "observed_motorized_provider_count",
        "available_field": "observed_motorized_available",
        "latest_end_field": "observed_motorized_latest_end_utc",
        "provider_profiles_field": "observed_motorized_provider_profiles",
        "numeric_fields": {
            "vehicle_count": "observed_vehicle_count_mean",
            "sample_size": "observed_motorized_sample_size_mean",
            "aadt": "observed_aadt_mean",
            "heavy_vehicle_share": "observed_heavy_vehicle_share_mean",
            "vehicle_km_estimate": "observed_vehicle_km_estimate_mean",
            "coverage_pct": "observed_flow_coverage_pct_mean",
        },
    },
    "speed_observation": {
        "count_field": "observed_speed_observation_count",
        "provider_count_field": "observed_speed_provider_count",
        "available_field": "observed_speed_available",
        "latest_end_field": "observed_speed_latest_end_utc",
        "provider_profiles_field": "observed_speed_provider_profiles",
        "numeric_fields": {
            "mean_speed_kph": "observed_mean_speed_kph_mean",
            "p85_speed_kph": "observed_p85_speed_kph_mean",
            "sample_size": "observed_speed_sample_size_mean",
            "speed_std_kph": "observed_speed_std_kph_mean",
            "speed_variance": "observed_speed_variance_mean",
            "speed_limit_kph": "observed_speed_limit_kph_mean",
            "probe_penetration_rate": "observed_probe_penetration_rate_mean",
        },
    },
    "vru_exposure": {
        "count_field": "observed_vru_observation_count",
        "provider_count_field": "observed_vru_provider_count",
        "available_field": "observed_vru_available",
        "latest_end_field": "observed_vru_latest_end_utc",
        "provider_profiles_field": "observed_vru_provider_profiles",
        "numeric_fields": {
            "pedestrian_count": "observed_pedestrian_count_mean",
            "cyclist_count": "observed_cyclist_count_mean",
            "vru_exposure_index": "observed_vru_exposure_index_mean",
            "crossing_flow": "observed_crossing_flow_mean",
            "micromobility_trip_count": "observed_micromobility_trip_count_mean",
        },
    },
}


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for connector observation joins. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object at: {path}")
    return payload


def _resolve_manifest_output(manifest_path: Path, field_name: str) -> Path:
    manifest = _load_json(manifest_path)
    output_value = manifest.get("outputs", {}).get(field_name)
    if not isinstance(output_value, str) or not output_value.strip():
        raise RuntimeError(f"Manifest does not contain outputs.{field_name}: {manifest_path}")
    candidate = Path(output_value)
    if candidate.is_absolute():
        return candidate
    return candidate


def _load_observation_rows(observation_manifest_paths: list[str | Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_manifests: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for manifest_path_value in observation_manifest_paths:
        manifest_path = Path(manifest_path_value)
        manifest = _load_json(manifest_path)
        observations_path = _resolve_manifest_output(manifest_path, "observations_path")
        source_manifests.append(
            {
                "manifest_path": str(manifest_path),
                "observations_path": str(observations_path),
                "municipality_label": manifest.get("connector", {}).get("municipality_label"),
                "capability_code": manifest.get("connector", {}).get("capability_code"),
                "provider_profile_id": manifest.get("connector", {}).get("provider_profile_id"),
            }
        )
        with observations_path.open("r", encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows, source_manifests


def _flatten_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        attributes = dict(row.get("attributes", {}))
        flattened.append(
            {
                "municipality_label": row.get("municipality_label"),
                "capability_code": row.get("capability_code"),
                "provider_profile_id": row.get("provider_profile_id"),
                "join_key_type": row.get("join_key_type"),
                "join_key_value": row.get("join_key_value"),
                "observed_end_utc": row.get("observed_end_utc"),
                **attributes,
            }
        )
    return flattened


def _aggregate_capability(frame: Any, pd: Any, capability_code: str) -> Any:
    config = CAPABILITY_AGGREGATION[capability_code]
    subset = frame[frame["capability_code"] == capability_code].copy()
    if subset.empty:
        columns = ["segment_id", config["count_field"], config["provider_count_field"], config["available_field"]]
        return pd.DataFrame(columns=columns)

    grouped = subset.groupby("join_key_value", as_index=False)
    aggregated = grouped.size().rename(columns={"join_key_value": "segment_id", "size": config["count_field"]})
    provider_counts = (
        subset.groupby("join_key_value")["provider_profile_id"]
        .nunique()
        .rename(config["provider_count_field"])
        .reset_index()
        .rename(columns={"join_key_value": "segment_id"})
    )
    provider_profiles = (
        subset.groupby("join_key_value")["provider_profile_id"]
        .agg(lambda values: "|".join(sorted({str(value) for value in values if value})))
        .rename(config["provider_profiles_field"])
        .reset_index()
        .rename(columns={"join_key_value": "segment_id"})
    )
    latest_end = (
        subset.groupby("join_key_value")["observed_end_utc"]
        .max()
        .rename(config["latest_end_field"])
        .reset_index()
        .rename(columns={"join_key_value": "segment_id"})
    )
    aggregated = aggregated.merge(provider_counts, on="segment_id", how="left")
    aggregated = aggregated.merge(provider_profiles, on="segment_id", how="left")
    aggregated = aggregated.merge(latest_end, on="segment_id", how="left")
    aggregated[config["available_field"]] = 1.0

    for source_field, target_field in config["numeric_fields"].items():
        if source_field not in subset.columns:
            continue
        subset[source_field] = pd.to_numeric(subset[source_field], errors="coerce")
        numeric = (
            subset.groupby("join_key_value")[source_field]
            .mean()
            .rename(target_field)
            .reset_index()
            .rename(columns={"join_key_value": "segment_id"})
        )
        aggregated = aggregated.merge(numeric, on="segment_id", how="left")

    return aggregated


def _coalesce_numeric_column(frame: Any, pd: Any, target_field: str, source_fields: list[str]) -> None:
    if target_field in frame.columns:
        resolved = pd.to_numeric(frame[target_field], errors="coerce")
    else:
        resolved = pd.Series([None] * len(frame), index=frame.index, dtype="float64")
    for source_field in source_fields:
        if source_field not in frame.columns:
            continue
        source_values = pd.to_numeric(frame[source_field], errors="coerce")
        resolved = resolved.where(resolved.notna(), source_values)
    frame[target_field] = resolved


def _materialize_canonical_exposure_fields(frame: Any, pd: Any) -> None:
    # Preserve any pre-existing canonical values and only fill missing values from connector observations.
    _coalesce_numeric_column(frame, pd, "aadt", ["observed_aadt_mean", "observed_vehicle_count_mean"])
    _coalesce_numeric_column(frame, pd, "traffic_volume", ["observed_vehicle_count_mean", "observed_aadt_mean"])
    _coalesce_numeric_column(frame, pd, "traffic_count_daily", ["observed_vehicle_count_mean", "observed_aadt_mean"])
    _coalesce_numeric_column(frame, pd, "vehicle_km_travelled", ["observed_vehicle_km_estimate_mean"])
    _coalesce_numeric_column(frame, pd, "mean_speed_kph", ["observed_mean_speed_kph_mean"])
    _coalesce_numeric_column(frame, pd, "p85_speed_kph", ["observed_p85_speed_kph_mean"])
    _coalesce_numeric_column(frame, pd, "speed_std_kph", ["observed_speed_std_kph_mean"])
    _coalesce_numeric_column(frame, pd, "speed_variance", ["observed_speed_variance_mean"])
    _coalesce_numeric_column(frame, pd, "pedestrian_count", ["observed_pedestrian_count_mean"])
    _coalesce_numeric_column(frame, pd, "cyclist_count", ["observed_cyclist_count_mean"])
    _coalesce_numeric_column(frame, pd, "vru_exposure_index", ["observed_vru_exposure_index_mean"])
    _coalesce_numeric_column(frame, pd, "crossing_flow", ["observed_crossing_flow_mean"])
    _coalesce_numeric_column(frame, pd, "micromobility_trip_count", ["observed_micromobility_trip_count_mean"])


def _coerce_connector_numeric_columns(frame: Any, pd: Any) -> None:
    for column in OBSERVED_CONNECTOR_NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _municipality_coverage_stats(
    *,
    pd: Any,
    segments: Any,
    segment_rows: Any,
    matched_rows: Any,
    source_manifests: list[dict[str, Any]],
    total_segment_count: int,
) -> dict[str, dict[str, Any]]:
    municipality_labels: set[str] = set()
    if "municipality_label" in segment_rows.columns:
        municipality_labels.update(
            str(value)
            for value in segment_rows["municipality_label"].dropna().tolist()
            if str(value).strip()
        )
    municipality_labels.update(
        str(item.get("municipality_label") or "").strip()
        for item in source_manifests
        if str(item.get("municipality_label") or "").strip()
    )

    if not municipality_labels:
        return {}

    segment_counts_by_municipality: dict[str, int] = {}
    if "municipality_label" in segments.columns:
        segment_counts_by_municipality = {
            str(label): int(count)
            for label, count in segments.groupby("municipality_label")["segment_id"].nunique().items()
            if str(label).strip()
        }

    stats: dict[str, dict[str, Any]] = {}
    for municipality_label in sorted(municipality_labels):
        label_segment_rows = (
            segment_rows[segment_rows["municipality_label"] == municipality_label]
            if "municipality_label" in segment_rows.columns
            else segment_rows.iloc[0:0]
        )
        label_matched_rows = (
            matched_rows[matched_rows["municipality_label"] == municipality_label]
            if "municipality_label" in matched_rows.columns
            else matched_rows.iloc[0:0]
        )
        label_motorized_rows = label_matched_rows[
            label_matched_rows["capability_code"] == "motorized_exposure"
        ]
        label_speed_rows = label_matched_rows[
            label_matched_rows["capability_code"] == "speed_observation"
        ]

        segment_count = segment_counts_by_municipality.get(municipality_label)
        if segment_count is None and len(municipality_labels) == 1:
            segment_count = total_segment_count

        matched_segment_count = int(label_matched_rows["join_key_value"].astype(str).nunique())
        motorized_available_segment_count = int(
            label_motorized_rows["join_key_value"].astype(str).nunique()
        )
        speed_available_segment_count = int(
            label_speed_rows["join_key_value"].astype(str).nunique()
        )

        denominator = float(segment_count) if segment_count and segment_count > 0 else 0.0
        stats[municipality_label] = {
            "segment_count": int(segment_count) if segment_count is not None else None,
            "input_observation_count": int(len(label_segment_rows)),
            "matched_observation_count": int(len(label_matched_rows)),
            "matched_segment_count": matched_segment_count,
            "motorized_available_segment_count": motorized_available_segment_count,
            "speed_available_segment_count": speed_available_segment_count,
            "matched_segment_share": round(matched_segment_count / denominator, 4)
            if denominator > 0.0
            else None,
            "motorized_available_segment_share": round(
                motorized_available_segment_count / denominator,
                4,
            )
            if denominator > 0.0
            else None,
            "speed_available_segment_share": round(
                speed_available_segment_count / denominator,
                4,
            )
            if denominator > 0.0
            else None,
        }

    return stats


def apply_connector_observations_to_segments(
    segments_path: str | Path,
    observation_manifest_paths: list[str | Path],
    output_dir: str | Path,
) -> dict[str, Any]:
    if not observation_manifest_paths:
        raise RuntimeError("At least one observation manifest path is required.")

    gpd, pd = _load_geo_stack()
    segments_input = Path(segments_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    enriched_path = output_root / "road_segments_connector_observations.geojson"
    manifest_path = output_root / "road_segments_connector_observations.manifest.json"

    segments = gpd.read_file(segments_input)
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segments file does not contain required 'segment_id' column: {segments_input}")
    segments["segment_id"] = segments["segment_id"].astype(str)

    observation_rows, source_manifests = _load_observation_rows(observation_manifest_paths)
    flattened_rows = _flatten_observations(observation_rows)
    frame = pd.DataFrame(flattened_rows)
    total_observations = len(frame)
    if frame.empty:
        raise RuntimeError("Observation manifests did not contain any rows.")

    skipped_join_type_counts = (
        frame[frame["join_key_type"] != "segment_id"]["join_key_type"].value_counts(dropna=False).to_dict()
        if "join_key_type" in frame.columns
        else {}
    )
    segment_rows = frame[frame["join_key_type"] == "segment_id"].copy()
    known_segments = set(segments["segment_id"].tolist())
    matched_mask = segment_rows["join_key_value"].astype(str).isin(known_segments)
    matched_rows = segment_rows[matched_mask].copy()
    unmatched_rows = segment_rows[~matched_mask].copy()

    enriched = segments.copy()
    capability_summaries: dict[str, Any] = {}
    for capability_code in sorted(CAPABILITY_AGGREGATION):
        capability_frame = _aggregate_capability(matched_rows, pd, capability_code)
        if not capability_frame.empty:
            enriched = enriched.merge(capability_frame, on="segment_id", how="left")
        config = CAPABILITY_AGGREGATION[capability_code]
        if config["available_field"] not in enriched.columns:
            enriched[config["available_field"]] = 0.0
        enriched[config["available_field"]] = pd.to_numeric(
            enriched[config["available_field"]],
            errors="coerce",
        ).fillna(0.0)
        capability_summaries[capability_code] = {
            "matched_observations": int(len(matched_rows[matched_rows["capability_code"] == capability_code])),
            "matched_segments": int(
                enriched.loc[enriched[config["available_field"]] > 0.0, "segment_id"].nunique()
            ),
        }

    if "observed_motorized_available" not in enriched.columns:
        enriched["observed_motorized_available"] = 0.0
    if "observed_speed_available" not in enriched.columns:
        enriched["observed_speed_available"] = 0.0
    if "observed_vru_available" not in enriched.columns:
        enriched["observed_vru_available"] = 0.0
    enriched["observed_connector_capability_count"] = (
        pd.to_numeric(enriched["observed_motorized_available"], errors="coerce").fillna(0.0)
        + pd.to_numeric(enriched["observed_speed_available"], errors="coerce").fillna(0.0)
        + pd.to_numeric(enriched["observed_vru_available"], errors="coerce").fillna(0.0)
    )
    _materialize_canonical_exposure_fields(enriched, pd)
    _coerce_connector_numeric_columns(enriched, pd)
    enriched["connector_observation_version"] = SEGMENT_CONNECTOR_OBSERVATIONS_VERSION
    enriched.to_file(enriched_path, driver="GeoJSON")

    segment_count = int(len(enriched))
    denominator = float(max(1, segment_count))
    motorized_available_segment_count = int(
        enriched.loc[
            pd.to_numeric(enriched["observed_motorized_available"], errors="coerce").fillna(0.0) > 0.0,
            "segment_id",
        ].nunique()
    )
    speed_available_segment_count = int(
        enriched.loc[
            pd.to_numeric(enriched["observed_speed_available"], errors="coerce").fillna(0.0) > 0.0,
            "segment_id",
        ].nunique()
    )
    vru_available_segment_count = int(
        enriched.loc[
            pd.to_numeric(enriched["observed_vru_available"], errors="coerce").fillna(0.0) > 0.0,
            "segment_id",
        ].nunique()
    )
    dual_capability_segment_count = int(
        enriched.loc[
            (pd.to_numeric(enriched["observed_motorized_available"], errors="coerce").fillna(0.0) > 0.0)
            & (pd.to_numeric(enriched["observed_speed_available"], errors="coerce").fillna(0.0) > 0.0),
            "segment_id",
        ].nunique()
    )
    all_three_capability_segment_count = int(
        enriched.loc[
            (pd.to_numeric(enriched["observed_motorized_available"], errors="coerce").fillna(0.0) > 0.0)
            & (pd.to_numeric(enriched["observed_speed_available"], errors="coerce").fillna(0.0) > 0.0)
            & (pd.to_numeric(enriched["observed_vru_available"], errors="coerce").fillna(0.0) > 0.0),
            "segment_id",
        ].nunique()
    )
    matched_segment_count = int(
        enriched.loc[
            pd.to_numeric(enriched["observed_connector_capability_count"], errors="coerce").fillna(0.0) > 0.0,
            "segment_id",
        ].nunique()
    )
    municipality_coverage = _municipality_coverage_stats(
        pd=pd,
        segments=segments,
        segment_rows=segment_rows,
        matched_rows=matched_rows,
        source_manifests=source_manifests,
        total_segment_count=segment_count,
    )

    manifest = {
        "segment_connector_observations_version": SEGMENT_CONNECTOR_OBSERVATIONS_VERSION,
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "observation_manifest_paths": [str(Path(path)) for path in observation_manifest_paths],
            "observation_manifest_sha256": {
                str(Path(path)): _sha256(Path(path))
                for path in observation_manifest_paths
            },
        },
        "outputs": {
            "connector_segments_path": str(enriched_path),
            "connector_segments_sha256": _sha256(enriched_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "segment_connector_observations",
            "public_contract_version": SEGMENT_CONNECTOR_OBSERVATIONS_CONTRACT_VERSION,
            "segment_connector_observations_version": SEGMENT_CONNECTOR_OBSERVATIONS_VERSION,
        },
        "stats": {
            "segment_count": segment_count,
            "input_observation_manifest_count": len(source_manifests),
            "input_observation_row_count": int(total_observations),
            "matched_observations": int(len(matched_rows)),
            "unmatched_observations": int(len(unmatched_rows)),
            "matched_segment_count": matched_segment_count,
            "motorized_available_segment_count": motorized_available_segment_count,
            "speed_available_segment_count": speed_available_segment_count,
            "vru_available_segment_count": vru_available_segment_count,
            "dual_capability_segment_count": dual_capability_segment_count,
            "all_three_capability_segment_count": all_three_capability_segment_count,
            "matched_segment_share": round(matched_segment_count / denominator, 4),
            "motorized_available_segment_share": round(motorized_available_segment_count / denominator, 4),
            "speed_available_segment_share": round(speed_available_segment_count / denominator, 4),
            "vru_available_segment_share": round(vru_available_segment_count / denominator, 4),
            "dual_capability_segment_share": round(dual_capability_segment_count / denominator, 4),
            "all_three_capability_segment_share": round(all_three_capability_segment_count / denominator, 4),
            "municipality_coverage": municipality_coverage,
            "skipped_join_type_counts": {
                str(key): int(value)
                for key, value in skipped_join_type_counts.items()
            },
            "capability_summaries": capability_summaries,
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "segments_geojson",
                    segments_input,
                    _sha256(segments_input),
                ),
                *[
                    _artifact_reference(
                        "connector_observations_manifest",
                        Path(path),
                        _sha256(Path(path)),
                    )
                    for path in observation_manifest_paths
                ],
            ],
            publishable_outputs=[
                _artifact_reference(
                    "segment_connector_observations_geojson",
                    enriched_path,
                    _sha256(enriched_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "segment_connector_observations_version": SEGMENT_CONNECTOR_OBSERVATIONS_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": manifest["stats"],
    }
