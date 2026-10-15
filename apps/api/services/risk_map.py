"""Read-only product-facing map payload builders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.api.settings import ApiSettings
import apps.api.services.postgis_domain as postgis_domain
from road_risk_modeling import published_api
from road_risk_modeling.published_queries import (
    _apply_matrix_filter,
    query_published_resource,
)


DEFAULT_PUBLIC_TILE_LIMIT = 500
DEFAULT_ANALYST_SEGMENT_LIMIT = 300
DEFAULT_JUNCTION_LIMIT = 173
DEFAULT_CROSSING_LIMIT = 180
BARI_CITY_KEY = "bari"


def _resolve_path(path_value: str | Path, *, root_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root_dir / path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_dashboard_summary(settings: ApiSettings) -> dict[str, Any]:
    summary_path = _resolve_path(settings.dashboard_summary_path, root_dir=settings.root_dir)
    return published_api._load_dashboard_summary(summary_path)


def _published_runs(summary: dict[str, Any]) -> list[dict[str, Any]]:
    runs = summary.get("published_runs")
    if not isinstance(runs, list):
        raise RuntimeError("Dashboard summary must include a published_runs list.")
    return [item for item in runs if isinstance(item, dict)]


def _shortlists(summary: dict[str, Any]) -> list[dict[str, Any]]:
    shortlists = summary.get("intervention_shortlists", [])
    return [item for item in shortlists if isinstance(item, dict)]


def _city_record(run: dict[str, Any]) -> dict[str, Any]:
    segment_scores = run.get("segment_scores") or {}
    score_tiles = run.get("score_tiles") or {}
    city_key = str(run.get("city_key") or "").strip()
    return {
        "city_key": city_key,
        "display_name": run.get("display_name") or city_key.title(),
        "prediction_run_label": run.get("prediction_run_label"),
        "prediction_task": run.get("prediction_task"),
        "occurred_years": list(run.get("occurred_years") or []),
        "segment_score_rows": segment_scores.get("segment_score_rows"),
        "tile_rows": score_tiles.get("tile_rows"),
        "tile_size_m": score_tiles.get("tile_size_m"),
        "supports_junction_layer": city_key == BARI_CITY_KEY,
        "supports_crossing_layer": city_key == BARI_CITY_KEY,
    }


def _find_run(summary: dict[str, Any], city_key: str) -> dict[str, Any]:
    for run in _published_runs(summary):
        if str(run.get("city_key") or "").strip() == city_key:
            return run
    raise RuntimeError(f"City '{city_key}' is not available in the published dashboard summary.")


def _find_shortlist(summary: dict[str, Any], city_key: str) -> dict[str, Any] | None:
    for shortlist in _shortlists(summary):
        if str(shortlist.get("city_key") or "").strip() == city_key:
            return shortlist
    return None


def _resolve_year(run: dict[str, Any], occurred_year: int | None) -> int | None:
    years = [int(year) for year in run.get("occurred_years") or []]
    if not years:
        return occurred_year
    if occurred_year is None:
        return max(years)
    if occurred_year not in years:
        raise RuntimeError(
            f"occurred_year '{occurred_year}' is not available for city '{run.get('city_key')}'. "
            f"Valid years are: {', '.join(str(year) for year in sorted(years))}"
        )
    return occurred_year


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _empty_feature_collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": []}


def _load_geojson_features(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Expected FeatureCollection at: {path}")
    features = payload.get("features")
    if not isinstance(features, list):
        raise RuntimeError(f"Expected feature list at: {path}")
    return [feature for feature in features if isinstance(feature, dict)]


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _sort_signal_junctions(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        features,
        key=lambda feature: (
            -_coerce_float(feature.get("properties", {}).get("crash_count")),
            -_coerce_float(feature.get("properties", {}).get("injury_crash_count")),
            str(feature.get("properties", {}).get("name") or ""),
        ),
    )


def _sort_crossings(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        features,
        key=lambda feature: (
            -_coerce_float(feature.get("properties", {}).get("pedestrian_crossing_priority_score")),
            -_coerce_float(feature.get("properties", {}).get("public_score_index")),
            str(feature.get("properties", {}).get("crossing_name") or ""),
        ),
    )


def _limit_features(features: list[dict[str, Any]], limit: int | None, default_limit: int) -> list[dict[str, Any]]:
    resolved_limit = default_limit if limit is None else limit
    if resolved_limit <= 0:
        raise RuntimeError("limit must be greater than 0 when provided.")
    return features[:resolved_limit]


def list_public_cities(settings: ApiSettings, session: Any | None = None) -> dict[str, Any]:
    if session is not None:
        payload = postgis_domain.try_domain_payload(postgis_domain.list_public_cities_from_domain, session)
        if payload is not None:
            return payload

    summary = _load_dashboard_summary(settings)
    cities = sorted((_city_record(run) for run in _published_runs(summary)), key=lambda row: str(row["display_name"]))
    return {
        "serving_source": "artifact",
        "summary_stats": summary.get("stats", {}),
        "cities": cities,
    }


def build_public_risk_map(
    settings: ApiSettings,
    *,
    city_key: str,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
    session: Any | None = None,
) -> dict[str, Any]:
    if session is not None:
        payload = postgis_domain.try_domain_payload(
            postgis_domain.build_public_risk_map_from_domain,
            session,
            city_key=city_key,
            occurred_year=occurred_year,
            min_score_band=min_score_band,
            limit=limit if limit is not None else DEFAULT_PUBLIC_TILE_LIMIT,
        )
        if payload is not None:
            return payload

    summary = _load_dashboard_summary(settings)
    run = _find_run(summary, city_key)
    resolved_year = _resolve_year(run, occurred_year)
    score_tiles = run.get("score_tiles") or {}
    manifest_path = score_tiles.get("manifest_path")
    if not isinstance(manifest_path, str):
        raise RuntimeError(f"City '{city_key}' does not expose a score-tile manifest.")

    map_resource = query_published_resource(
        manifest_path,
        occurred_year=resolved_year,
        min_score_band=min_score_band,
        limit=limit if limit is not None else DEFAULT_PUBLIC_TILE_LIMIT,
        root_dir=settings.root_dir,
    )

    segment_scores = run.get("segment_scores") or {}
    return {
        "serving_source": "artifact",
        "city": _city_record(run),
        "filters": {
            "occurred_year": resolved_year,
            "min_score_band": min_score_band,
            "limit": map_resource["query"]["limit"],
        },
        "summary": {
            "predicted_crash_total": segment_scores.get("predicted_crash_total"),
            "observed_crash_total": segment_scores.get("observed_crash_total"),
            "segment_score_rows": segment_scores.get("segment_score_rows"),
            "tile_rows": score_tiles.get("tile_rows"),
            "tiles_high_or_very_high": score_tiles.get("tiles_high_or_very_high"),
            "tiles_very_high": score_tiles.get("tiles_very_high"),
            "tile_size_m": score_tiles.get("tile_size_m"),
        },
        "map_resource": map_resource,
    }


def build_public_interventions(
    settings: ApiSettings,
    *,
    city_key: str,
    session: Any | None = None,
) -> dict[str, Any]:
    if session is not None:
        payload = postgis_domain.try_domain_payload(
            postgis_domain.build_public_interventions_from_domain,
            session,
            city_key=city_key,
        )
        if payload is not None:
            return payload

    summary = _load_dashboard_summary(settings)
    run = _find_run(summary, city_key)
    shortlist = _find_shortlist(summary, city_key) or {}
    return {
        "serving_source": "artifact",
        "city": _city_record(run),
        "intervention_shortlist": {
            "top_corridors": list(shortlist.get("top_corridors") or []),
            "hotspot_tiles": list(shortlist.get("hotspot_tiles") or []),
        },
    }


def _build_unavailable_layer(reason: str) -> dict[str, Any]:
    return {
        "availability": "unavailable",
        "reason": reason,
        "stats": {
            "returned_features": 0,
        },
        "data": _empty_feature_collection(),
    }


def _apply_layer_matrix_filter(
    layer: dict[str, Any], *, record_kind: str, role: str,
) -> dict[str, Any]:
    """Gate a support-layer payload through a `record_kind` matrix.

    Calls `_apply_matrix_filter(data, record_kind, role)` on the
    layer's FeatureCollection properties and attaches a
    `redaction_policy` meta block so downstream clients know which
    policy was applied. Compounds the matrix-driven redaction already
    enforced for `segment_score` in `segment_drill_down` and
    `published_queries`.
    """
    data = layer.get("data")
    if not isinstance(data, dict):
        return layer
    filtered_data, policy_meta = _apply_matrix_filter(data, record_kind, role)
    return {**layer, "data": filtered_data, "redaction_policy": policy_meta}


def _apply_node_year_metric_filter(
    layer: dict[str, Any], *, role: str = "analyst",
) -> dict[str, Any]:
    """Gate a junction-layer payload through the `node_year_metric` matrix."""
    return _apply_layer_matrix_filter(layer, record_kind="node_year_metric", role=role)


def _apply_crossing_priority_filter(
    layer: dict[str, Any], *, role: str = "analyst",
) -> dict[str, Any]:
    """Gate a crossing-layer payload through the `crossing_priority` matrix.

    The Bari crossing artifact carries 75 fields per crossing
    (identity, banded priority indices, movement-modeling internals,
    crash counts). The matrix in `data_governance` classifies each
    one; this helper restricts the surface to the role's publishable
    set and attaches a `redaction_policy` block.
    """
    return _apply_layer_matrix_filter(layer, record_kind="crossing_priority", role=role)


def _build_signal_junction_layer(
    settings: ApiSettings, *, city_key: str = BARI_CITY_KEY, limit: int | None
) -> dict[str, Any]:
    source_path = _resolve_path(settings.get_signal_junction_metrics_path(city_key), root_dir=settings.root_dir)
    if not source_path.is_file():
        label = "Bari" if city_key == BARI_CITY_KEY else city_key.capitalize()
        return _build_unavailable_layer(f"{label} signal junction metrics are not published at {source_path}.")
    features = _load_geojson_features(source_path)
    available_years = sorted(
        {
            _coerce_int(feature.get("properties", {}).get("occurred_year"))
            for feature in features
            if feature.get("properties", {}).get("occurred_year") is not None
        }
    )
    resolved_year = max(available_years) if available_years else None
    filtered = [
        feature
        for feature in features
        if resolved_year is None
        or _coerce_int(feature.get("properties", {}).get("occurred_year")) == resolved_year
    ]
    ranked = _sort_signal_junctions(filtered)
    selected = _limit_features(ranked, limit, DEFAULT_JUNCTION_LIMIT)
    layer = {
        "availability": "available",
        "source_path": str(source_path),
        "resolved_year": resolved_year,
        "stats": {
            "available_years": available_years,
            "matched_features": len(filtered),
            "returned_features": len(selected),
        },
        "data": _feature_collection(selected),
    }
    return _apply_node_year_metric_filter(layer, role="analyst")


def _build_bari_signal_junction_layer(settings: ApiSettings, *, limit: int | None) -> dict[str, Any]:
    return _build_signal_junction_layer(settings, city_key=BARI_CITY_KEY, limit=limit)


def _build_crossing_layer(
    settings: ApiSettings, *, city_key: str = BARI_CITY_KEY, limit: int | None
) -> dict[str, Any]:
    source_path = _resolve_path(settings.get_crossing_priority_path(city_key), root_dir=settings.root_dir)
    if not source_path.is_file():
        label = "Bari" if city_key == BARI_CITY_KEY else city_key.capitalize()
        return _build_unavailable_layer(f"{label} crossing priorities are not published at {source_path}.")
    features = _load_geojson_features(source_path)
    ranked = _sort_crossings(features)
    selected = _limit_features(ranked, limit, DEFAULT_CROSSING_LIMIT)
    layer = {
        "availability": "available",
        "source_path": str(source_path),
        "ranking_field": "pedestrian_crossing_priority_score",
        "stats": {
            "matched_features": len(features),
            "returned_features": len(selected),
        },
        "data": _feature_collection(selected),
    }
    return _apply_crossing_priority_filter(layer, role="analyst")


def _build_bari_crossing_layer(settings: ApiSettings, *, limit: int | None) -> dict[str, Any]:
    return _build_crossing_layer(settings, city_key=BARI_CITY_KEY, limit=limit)


def build_analyst_risk_map(
    settings: ApiSettings,
    *,
    city_key: str,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
    junction_limit: int | None,
    crossing_limit: int | None,
    session: Any | None = None,
) -> dict[str, Any]:
    if session is not None:
        payload = postgis_domain.try_domain_payload(
            postgis_domain.build_analyst_risk_map_from_domain,
            session,
            city_key=city_key,
            occurred_year=occurred_year,
            min_score_band=min_score_band,
            limit=limit if limit is not None else DEFAULT_ANALYST_SEGMENT_LIMIT,
            junction_limit=junction_limit if junction_limit is not None else DEFAULT_JUNCTION_LIMIT,
            crossing_limit=crossing_limit if crossing_limit is not None else DEFAULT_CROSSING_LIMIT,
        )
        if payload is not None:
            return payload

    summary = _load_dashboard_summary(settings)
    run = _find_run(summary, city_key)
    resolved_year = _resolve_year(run, occurred_year)
    segment_scores = run.get("segment_scores") or {}
    manifest_path = segment_scores.get("manifest_path")
    if not isinstance(manifest_path, str):
        raise RuntimeError(f"City '{city_key}' does not expose a segment-score manifest.")

    resolved_limit = limit if limit is not None else DEFAULT_ANALYST_SEGMENT_LIMIT
    segment_layer = query_published_resource(
        manifest_path,
        view="public_segments",
        occurred_year=resolved_year,
        min_score_band=min_score_band,
        limit=resolved_limit,
        root_dir=settings.root_dir,
    )
    segment_details = query_published_resource(
        manifest_path,
        view="analyst_segments",
        occurred_year=resolved_year,
        min_score_band=min_score_band,
        limit=resolved_limit,
        root_dir=settings.root_dir,
    )

    junction_layer = _build_signal_junction_layer(settings, city_key=city_key, limit=junction_limit)
    crossing_layer = _build_crossing_layer(settings, city_key=city_key, limit=crossing_limit)

    return {
        "serving_source": "artifact",
        "city": _city_record(run),
        "filters": {
            "occurred_year": resolved_year,
            "min_score_band": min_score_band,
            "limit": resolved_limit,
            "junction_limit": junction_limit if junction_limit is not None else DEFAULT_JUNCTION_LIMIT,
            "crossing_limit": crossing_limit if crossing_limit is not None else DEFAULT_CROSSING_LIMIT,
        },
        "segment_layer": segment_layer,
        "segment_details": {
            "contract_version": segment_details["contract_version"],
            "stats": segment_details["stats"],
            "rows": segment_details["data"]["rows"],
        },
        "support_layers": {
            "junctions": junction_layer,
            "crossings": crossing_layer,
        },
    }
