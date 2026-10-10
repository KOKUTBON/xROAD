"""Build a static dashboard summary from published resources and evaluation outputs."""

from __future__ import annotations

import ast
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import shape as _shapely_shape
except Exception:  # pragma: no cover - optional import fallback
    _shapely_shape = None

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


DASHBOARD_SUMMARY_VERSION = "dashboard_summary_v1"
DASHBOARD_SUMMARY_CONTRACT_VERSION = "dashboard_summary_public_v1"
TRANSFERABILITY_MODES = (
    "cross_jurisdiction_temporal",
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
)


def _humanize_label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_published_index(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload.get("catalog"), list):
        raise RuntimeError("Published index JSON must include a top-level 'catalog' list.")
    return payload


def _normalize_city_key(value: str) -> str:
    normalized = str(value).lower()
    normalized = normalized.split("_frequency_")[0]
    for suffix in ("_context_v2", "_context", "_municipality", "_core", "_tiles_500m", "_tiles"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized


def _resolve_reference_path(reference_path: str | Path, *, anchor_path: Path) -> Path:
    path = Path(reference_path)
    if path.is_absolute():
        return path
    candidates = [
        Path(reference_path),
        anchor_path.parent / path,
        anchor_path.parent.parent / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[1]


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_feature_collection(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Expected FeatureCollection at: {path}")
    return list(payload.get("features", []))


def _flatten_literal(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text[0:1] in {"[", "(", "{", '"', "'"}:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return [text.strip("[]'\"")]
            return _flatten_literal(parsed)
        return [text]
    if isinstance(value, (list, tuple, set)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_literal(item))
        return flattened
    return [str(value)]


def _normalize_literal_text(value: Any) -> str | None:
    tokens = [token for token in _flatten_literal(value) if token and token.lower() != "nan"]
    if not tokens:
        return None
    return " / ".join(list(dict.fromkeys(tokens)))


def _clean_corridor_label(name: str, ref: str, highway: str) -> str:
    name_tokens = [token for token in _flatten_literal(name) if token and token.lower() != "nan"]
    ref_tokens = [token for token in _flatten_literal(ref) if token and token.lower() != "nan"]
    highway_tokens = [token for token in _flatten_literal(highway) if token and token.lower() != "nan"]
    if name_tokens:
        unique_names = list(dict.fromkeys(name_tokens))
        return " / ".join(unique_names[:2])
    if ref_tokens:
        return " / ".join(list(dict.fromkeys(ref_tokens))[:2])
    if highway_tokens:
        return " / ".join(list(dict.fromkeys(highway_tokens))[:2])
    return "Unnamed corridor"


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    return int(_safe_float(value))


def _index_features_by_property(
    features: list[dict[str, Any]],
    *,
    property_name: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        identifier = properties.get(property_name)
        if identifier:
            indexed[str(identifier)] = feature
    return indexed


def _iter_coordinate_pairs(value: Any) -> list[tuple[float, float]]:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
            return [(float(value[0]), float(value[1]))]
        pairs: list[tuple[float, float]] = []
        for item in value:
            pairs.extend(_iter_coordinate_pairs(item))
        return pairs
    return []


def _geometry_bounds(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not isinstance(geometry, dict):
        return None
    pairs = _iter_coordinate_pairs(geometry.get("coordinates"))
    if not pairs:
        return None
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    return min(xs), min(ys), max(xs), max(ys)


def _bounds_overlap(
    left: tuple[float, float, float, float] | None,
    right: tuple[float, float, float, float] | None,
) -> bool:
    if left is None or right is None:
        return False
    return not (
        left[2] < right[0]
        or right[2] < left[0]
        or left[3] < right[1]
        or right[3] < left[1]
    )


def _features_intersect(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if _shapely_shape is not None:
        try:
            return bool(_shapely_shape(left.get("geometry")).intersects(_shapely_shape(right.get("geometry"))))
        except Exception:  # nosec B110 # optional conversion/geometry fallback continues below
            pass
    return _bounds_overlap(_geometry_bounds(left.get("geometry")), _geometry_bounds(right.get("geometry")))


def _build_segment_focus_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_score_id": row.get("segment_score_id"),
        "segment_id": row.get("segment_id"),
        "segment_label": _clean_corridor_label(row.get("name", ""), row.get("ref", ""), row.get("highway", "")),
        "public_score_band": row.get("public_score_band"),
        "public_score_index": round(_safe_float(row.get("public_score_index")), 3),
        "predicted_crash_count": round(_safe_float(row.get("predicted_crash_count")), 6),
        "observed_crash_count": round(_safe_float(row.get("observed_crash_count")), 6),
        "score_rank_desc": _safe_int(row.get("score_rank_desc")),
        "score_decile": _safe_int(row.get("score_decile")),
        "segment_length_m": round(
            _safe_float(row.get("segment_length_m") or row.get("length")),
            3,
        ),
        "name": _normalize_literal_text(row.get("name")),
        "ref": _normalize_literal_text(row.get("ref")),
        "highway": _normalize_literal_text(row.get("highway")),
    }


def _run_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("display_name") or ""),
        str(record.get("prediction_run_label") or ""),
    )


def _build_published_run_summary(published_index: dict[str, Any]) -> list[dict[str, Any]]:
    segment_runs = published_index.get("latest_by_resource_prediction_run", {}).get("segment_scores", {})
    tile_runs = published_index.get("latest_by_resource_prediction_run", {}).get("segment_score_tiles", {})
    summaries: list[dict[str, Any]] = []
    for prediction_run_label, segment_record in segment_runs.items():
        segment_stats = segment_record.get("stats", {})
        segment_views = segment_record.get("views", {})
        tile_record = tile_runs.get(prediction_run_label)
        tile_stats = tile_record.get("stats", {}) if isinstance(tile_record, dict) else {}
        tile_views = tile_record.get("views", {}) if isinstance(tile_record, dict) else {}
        display_name = _humanize_label(str(prediction_run_label).split("_frequency_")[0])
        summaries.append(
            {
                "city_key": _normalize_city_key(prediction_run_label),
                "display_name": display_name,
                "prediction_run_label": prediction_run_label,
                "prediction_task": segment_record.get("prediction_task"),
                "occurred_years": segment_record.get("occurred_years", []),
                "segment_scores": {
                    "manifest_path": segment_record.get("manifest_path"),
                    "public_segments_path": (segment_views.get("public_segments") or {}).get("path"),
                    "analyst_segments_path": (segment_views.get("analyst_segments") or {}).get("path"),
                    "contract_versions": segment_record.get("contract_versions", {}),
                    "selection": segment_record.get("selection", {}),
                    "lineage_trace": segment_record.get("lineage_trace"),
                    "segment_score_rows": segment_stats.get("segment_score_rows"),
                    "observed_crash_total": segment_stats.get("observed_crash_total"),
                    "predicted_crash_total": segment_stats.get("predicted_crash_total"),
                    "top_5pct_observed_crash_share": segment_stats.get("top_5pct_observed_crash_share"),
                },
                "score_tiles": {
                    "manifest_path": tile_record.get("manifest_path") if isinstance(tile_record, dict) else None,
                    "public_tiles_path": (tile_views.get("public_tiles") or {}).get("path"),
                    "contract_versions": tile_record.get("contract_versions", {}) if isinstance(tile_record, dict) else {},
                    "selection": tile_record.get("selection", {}) if isinstance(tile_record, dict) else {},
                    "lineage_trace": tile_record.get("lineage_trace") if isinstance(tile_record, dict) else None,
                    "tile_rows": tile_stats.get("tile_rows"),
                    "tile_size_m": tile_stats.get("tile_size_m"),
                    "tiles_high_or_very_high": tile_stats.get("tiles_high_or_very_high"),
                    "tiles_very_high": tile_stats.get("tiles_very_high"),
                },
            }
        )
    return sorted(summaries, key=_run_sort_key)


def _available_transferability_modes(payload: dict[str, Any]) -> list[str]:
    requested_modes = payload.get("requested_modes") or []
    ordered: list[str] = []
    for mode in requested_modes:
        if (
            isinstance(mode, str)
            and mode in TRANSFERABILITY_MODES
            and isinstance(payload.get(mode), dict)
            and payload.get(mode)
            and mode not in ordered
        ):
            ordered.append(mode)
    for mode in TRANSFERABILITY_MODES:
        values = payload.get(mode)
        if isinstance(values, dict) and values and mode not in ordered:
            ordered.append(mode)
    return ordered


def _summarize_transferability_file(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    modes = _available_transferability_modes(payload)
    if not modes:
        raise RuntimeError(f"Transferability metrics file does not contain a supported evaluation mode: {path}")
    summaries: list[dict[str, Any]] = []
    for mode in modes:
        mode_payload = payload.get(mode, {})
        jurisdictions: list[dict[str, Any]] = []
        for label, metrics in sorted(mode_payload.items()):
            rf_metrics = metrics.get("random_forest_poisson_metrics", {})
            jurisdictions.append(
                {
                    "label": label,
                    "display_name": _humanize_label(label),
                    "mean_poisson_deviance": rf_metrics.get("mean_poisson_deviance"),
                    "top_5pct_crash_share": rf_metrics.get("top_5pct_crash_share"),
                    "test_rows": metrics.get("test_rows"),
                    "test_crash_total": metrics.get("test_crash_total"),
                    "train_jurisdictions": metrics.get("train_jurisdictions", []),
                }
            )

        summaries.append(
            {
                "mode": mode,
                "mode_display_name": _humanize_label(mode.replace("cross ", "")),
                "metrics_path": str(path),
                "holdout_year": payload.get("holdout_year"),
                "random_forest_n_estimators": payload.get("random_forest_n_estimators"),
                "jurisdictions": jurisdictions,
            }
        )
    return summaries


def _build_transferability_matrix(
    transferability_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_label: dict[str, dict[str, Any]] = {}
    for summary in transferability_summaries:
        mode = summary["mode"]
        for jurisdiction in summary["jurisdictions"]:
            current = by_label.setdefault(
                jurisdiction["label"],
                {
                    "city_key": _normalize_city_key(jurisdiction["label"]),
                    "label": jurisdiction["label"],
                    "display_name": jurisdiction["display_name"],
                    "metrics_by_mode": {},
                },
            )
            current["metrics_by_mode"][mode] = {
                "mean_poisson_deviance": jurisdiction["mean_poisson_deviance"],
                "top_5pct_crash_share": jurisdiction["top_5pct_crash_share"],
            }
    return sorted(by_label.values(), key=lambda item: str(item["display_name"]))


def _rank_entries(
    entries: list[dict[str, Any]],
    *,
    field_name: str,
    rank_field_name: str,
) -> None:
    sorted_entries = sorted(entries, key=lambda item: float(item.get(field_name) or 0.0), reverse=True)
    for index, entry in enumerate(sorted_entries, start=1):
        entry[rank_field_name] = index


def _build_intervention_priority(
    published_runs: list[dict[str, Any]],
    transferability_matrix: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    transferability_by_city = {
        record["city_key"]: record
        for record in transferability_matrix
    }
    entries: list[dict[str, Any]] = []
    for run in published_runs:
        transferability = transferability_by_city.get(run["city_key"], {})
        metrics_by_mode = transferability.get("metrics_by_mode", {})
        temporal = metrics_by_mode.get("cross_jurisdiction_temporal", {})
        cold_start = metrics_by_mode.get("cross_jurisdiction_cold_start", {})
        history_free = metrics_by_mode.get("cross_jurisdiction_history_free", {})
        temporal_deviance = temporal.get("mean_poisson_deviance")
        cold_start_deviance = cold_start.get("mean_poisson_deviance")
        history_free_deviance = history_free.get("mean_poisson_deviance")
        entries.append(
            {
                "city_key": run["city_key"],
                "display_name": run["display_name"],
                "prediction_run_label": run["prediction_run_label"],
                "observed_crash_total": run["segment_scores"].get("observed_crash_total"),
                "segment_score_rows": run["segment_scores"].get("segment_score_rows"),
                "top_5pct_observed_crash_share": run["segment_scores"].get("top_5pct_observed_crash_share"),
                "tiles_very_high": run["score_tiles"].get("tiles_very_high"),
                "tiles_high_or_very_high": run["score_tiles"].get("tiles_high_or_very_high"),
                "tile_rows": run["score_tiles"].get("tile_rows"),
                "temporal_deviance": temporal_deviance,
                "cold_start_deviance": cold_start_deviance,
                "history_free_deviance": history_free_deviance,
                "cold_start_gap_vs_temporal": (
                    float(cold_start_deviance) - float(temporal_deviance)
                    if cold_start_deviance is not None and temporal_deviance is not None
                    else None
                ),
                "history_free_gap_vs_temporal": (
                    float(history_free_deviance) - float(temporal_deviance)
                    if history_free_deviance is not None and temporal_deviance is not None
                    else None
                ),
            }
        )

    _rank_entries(entries, field_name="tiles_very_high", rank_field_name="very_high_tiles_rank")
    _rank_entries(entries, field_name="top_5pct_observed_crash_share", rank_field_name="top_5_share_rank")
    _rank_entries(entries, field_name="cold_start_gap_vs_temporal", rank_field_name="cold_start_gap_rank")
    return sorted(entries, key=lambda item: str(item["display_name"]))


def _derive_intervention_shortlists(
    published_runs: list[dict[str, Any]],
    *,
    published_index_path: Path,
) -> list[dict[str, Any]]:
    shortlists: list[dict[str, Any]] = []
    for run in published_runs:
        segment_manifest_path = _resolve_reference_path(
            str(run["segment_scores"]["manifest_path"]),
            anchor_path=published_index_path,
        )
        tile_manifest_path = _resolve_reference_path(
            str(run["score_tiles"]["manifest_path"]),
            anchor_path=published_index_path,
        )
        segment_manifest = _load_json(segment_manifest_path)
        tile_manifest = _load_json(tile_manifest_path)

        analyst_csv_path = _resolve_reference_path(
            str(segment_manifest["outputs"]["analyst_csv_path"]),
            anchor_path=segment_manifest_path,
        )
        tile_summary_path = _resolve_reference_path(
            str(tile_manifest["outputs"]["summary_csv_path"]),
            anchor_path=tile_manifest_path,
        )

        analyst_rows = _load_csv_rows(analyst_csv_path)
        tile_rows = _load_csv_rows(tile_summary_path)
        analyst_rows_by_segment_score_id = {
            str(row.get("segment_score_id")): row
            for row in analyst_rows
            if row.get("segment_score_id")
        }

        public_segment_features: list[dict[str, Any]] = []
        public_segment_output = segment_manifest.get("outputs", {}).get("public_geojson_path")
        if public_segment_output:
            public_segment_features = _load_feature_collection(
                _resolve_reference_path(
                    str(public_segment_output),
                    anchor_path=segment_manifest_path,
                )
            )
        public_tile_features: list[dict[str, Any]] = []
        public_tile_output = tile_manifest.get("outputs", {}).get("public_geojson_path")
        if public_tile_output:
            public_tile_features = _load_feature_collection(
                _resolve_reference_path(
                    str(public_tile_output),
                    anchor_path=tile_manifest_path,
                )
            )

        public_segment_by_score_id = _index_features_by_property(
            public_segment_features,
            property_name="segment_score_id",
        )
        public_tile_by_score_id = _index_features_by_property(
            public_tile_features,
            property_name="tile_score_id",
        )

        corridor_groups: dict[str, dict[str, Any]] = {}
        for row in analyst_rows:
            if row.get("public_score_band") not in {"high", "very_high"}:
                continue
            label = _clean_corridor_label(row.get("name", ""), row.get("ref", ""), row.get("highway", ""))
            group = corridor_groups.setdefault(
                label,
                {
                    "corridor_label": label,
                    "segment_count": 0,
                    "predicted_crash_total": 0.0,
                    "max_public_score_index": 0.0,
                    "best_rank": None,
                    "highway": row.get("highway"),
                    "ref": row.get("ref"),
                    "_rows": [],
                },
            )
            group["segment_count"] += 1
            group["predicted_crash_total"] += float(row.get("predicted_crash_count") or 0.0)
            group["max_public_score_index"] = max(
                float(group["max_public_score_index"]),
                float(row.get("public_score_index") or 0.0),
            )
            rank = int(float(row.get("score_rank_desc") or 0))
            if group["best_rank"] is None or rank < int(group["best_rank"]):
                group["best_rank"] = rank
            group["_rows"].append(row)

        top_corridors = sorted(
            corridor_groups.values(),
            key=lambda item: (-float(item["predicted_crash_total"]), int(item["best_rank"] or 10**9)),
        )[:5]
        for item in top_corridors:
            ordered_rows = sorted(
                item.pop("_rows"),
                key=lambda row: (_safe_int(row.get("score_rank_desc")) or 10**9, -_safe_float(row.get("public_score_index"))),
            )
            top_segments = [_build_segment_focus_record(row) for row in ordered_rows[:8]]
            item["predicted_crash_total"] = round(float(item["predicted_crash_total"]), 6)
            item["max_public_score_index"] = round(float(item["max_public_score_index"]), 3)
            item["focus_segment_score_ids"] = [
                record["segment_score_id"]
                for record in top_segments
                if record.get("segment_score_id")
            ]
            item["top_segments"] = top_segments

        hotspot_tiles = [
            {
                "tile_score_id": row.get("tile_score_id"),
                "tile_public_score_band": row.get("tile_public_score_band"),
                "tile_max_public_score_index": float(row.get("tile_max_public_score_index") or 0.0),
                "tile_segment_count": int(float(row.get("tile_segment_count") or 0)),
                "tile_very_high_band_segment_count": int(float(row.get("tile_very_high_band_segment_count") or 0)),
                "tile_high_band_segment_count": int(float(row.get("tile_high_band_segment_count") or 0)),
            }
            for row in tile_rows
            if row.get("tile_public_score_band") == "very_high"
        ]
        hotspot_tiles = sorted(
            hotspot_tiles,
            key=lambda item: (
                -float(item["tile_max_public_score_index"]),
                -int(item["tile_very_high_band_segment_count"]),
                -int(item["tile_segment_count"]),
            ),
        )[:5]
        for item in hotspot_tiles:
            tile_feature = public_tile_by_score_id.get(str(item["tile_score_id"]))
            intersecting_rows: list[dict[str, Any]] = []
            if tile_feature is not None:
                for segment_score_id, feature in public_segment_by_score_id.items():
                    if not _features_intersect(feature, tile_feature):
                        continue
                    analyst_row = analyst_rows_by_segment_score_id.get(segment_score_id)
                    if analyst_row is not None:
                        intersecting_rows.append(analyst_row)
            ordered_rows = sorted(
                intersecting_rows,
                key=lambda row: (_safe_int(row.get("score_rank_desc")) or 10**9, -_safe_float(row.get("public_score_index"))),
            )
            top_segments = [_build_segment_focus_record(row) for row in ordered_rows[:8]]
            item["intersection_segment_count"] = len(intersecting_rows)
            item["focus_segment_score_ids"] = [
                record["segment_score_id"]
                for record in top_segments
                if record.get("segment_score_id")
            ]
            item["top_segments"] = top_segments

        shortlists.append(
            {
                "city_key": run["city_key"],
                "display_name": run["display_name"],
                "prediction_run_label": run["prediction_run_label"],
                "top_corridors": top_corridors,
                "hotspot_tiles": hotspot_tiles,
            }
        )
    return sorted(shortlists, key=lambda item: str(item["display_name"]))


def build_dashboard_summary(
    *,
    published_index_path: str | Path = "data/published_index/published_resources.json",
    transferability_metrics_paths: list[str | Path] | None = None,
    output_dir: str | Path = "data/dashboard",
) -> dict[str, Any]:
    published_index_input = Path(published_index_path)
    transferability_inputs = [Path(path) for path in (transferability_metrics_paths or [])]
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_path = output_root / "dashboard_summary.json"
    manifest_path = output_root / "dashboard_summary.manifest.json"

    published_index = _load_published_index(published_index_input)
    published_runs = _build_published_run_summary(published_index)
    transferability_summaries = [
        summary
        for path in transferability_inputs
        for summary in _summarize_transferability_file(path)
    ]
    transferability_matrix = _build_transferability_matrix(transferability_summaries)
    intervention_priority = _build_intervention_priority(published_runs, transferability_matrix)
    intervention_shortlists = _derive_intervention_shortlists(
        published_runs,
        published_index_path=published_index_input,
    )

    summary_payload = {
        "dashboard_summary_version": DASHBOARD_SUMMARY_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "published_index_path": str(published_index_input),
        "published_resource_selection_policy": published_index.get("selection_policy"),
        "published_runs": published_runs,
        "transferability_evaluations": transferability_summaries,
        "transferability_matrix": transferability_matrix,
        "intervention_priority": intervention_priority,
        "intervention_shortlists": intervention_shortlists,
        "stats": {
            "published_run_count": len(published_runs),
            "transferability_file_count": len(transferability_summaries),
            "transferability_source_file_count": len(transferability_inputs),
            "transferability_jurisdiction_count": len(transferability_matrix),
            "catalog_record_count": published_index.get("stats", {}).get("catalog_record_count"),
            "lineage_traced_run_count": len(
                [
                    run
                    for run in published_runs
                    if (run["segment_scores"].get("lineage_trace") or {}).get("source_metrics_path")
                ]
            ),
        },
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "dashboard_summary_version": DASHBOARD_SUMMARY_VERSION,
        "inputs": {
            "published_index_path": str(published_index_input),
            "published_index_sha256": _sha256(published_index_input),
            "transferability_metrics_paths": [str(path) for path in transferability_inputs],
        },
        "outputs": {
            "summary_json_path": str(summary_path),
            "summary_json_sha256": _sha256(summary_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "dashboard_summary",
            "public_contract_version": DASHBOARD_SUMMARY_CONTRACT_VERSION,
            "dashboard_summary_version": DASHBOARD_SUMMARY_VERSION,
        },
        "stats": summary_payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "published_resource_index_json",
                    published_index_input,
                    _sha256(published_index_input),
                ),
                *[
                    _artifact_reference(
                        "transferability_metrics",
                        path,
                        _sha256(path),
                    )
                    for path in transferability_inputs
                ],
            ],
            publishable_outputs=[
                _artifact_reference(
                    "dashboard_summary_json",
                    summary_path,
                    _sha256(summary_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "dashboard_summary_version": DASHBOARD_SUMMARY_VERSION,
        "contract": {
            "public_contract_version": DASHBOARD_SUMMARY_CONTRACT_VERSION,
        },
        "stats": summary_payload["stats"],
    }
