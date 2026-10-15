"""PostGIS domain sync and query helpers for v1 map serving."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.db.models import (
    Crossing,
    Intervention,
    ModelRun,
    Municipality,
    PublicRiskTile,
    RiskScore,
    RoadNode,
    RoadSegment,
)
from apps.api.settings import ApiSettings
from road_risk_modeling import published_api


SYNC_CONTRACT_VERSION = "postgis_domain_artifact_sync_v1"
DOMAIN_SERVING_CONTRACT_VERSION = "postgis_domain_serving_v1"

BAND_ORDER = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "very_high": 3,
}


@dataclass(frozen=True)
class DomainSyncScope:
    organization_id: str
    municipality_id: str
    city_key: str
    source_id: str | None = None
    ingestion_job_id: str | None = None


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
    return [item for item in summary.get("published_runs") or [] if isinstance(item, dict)]


def _shortlists(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in summary.get("intervention_shortlists") or [] if isinstance(item, dict)]


def _find_run(summary: dict[str, Any], city_key: str) -> dict[str, Any] | None:
    for run in _published_runs(summary):
        if str(run.get("city_key") or "").strip() == city_key:
            return run
    return None


def _find_shortlist(summary: dict[str, Any], city_key: str) -> dict[str, Any] | None:
    for shortlist in _shortlists(summary):
        if str(shortlist.get("city_key") or "").strip() == city_key:
            return shortlist
    return None


def _load_feature_collection(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = _load_json(path)
    if payload.get("type") != "FeatureCollection":
        return []
    return [feature for feature in payload.get("features") or [] if isinstance(feature, dict)]


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _manifest_outputs(manifest_path: str | None, *, root_dir: Path) -> dict[str, Any]:
    if not manifest_path:
        return {}
    path = _resolve_path(manifest_path, root_dir=root_dir)
    if not path.is_file():
        return {}
    return _load_json(path).get("outputs") or {}


def _feature_path(
    run_section: dict[str, Any],
    manifest_outputs: dict[str, Any],
    *field_names: str,
    root_dir: Path,
) -> Path | None:
    for field_name in field_names:
        value = manifest_outputs.get(field_name) or run_section.get(field_name)
        if isinstance(value, str) and value:
            return _resolve_path(value, root_dir=root_dir)
    return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _geometry_expr(geometry: dict[str, Any] | None) -> Any:
    if not geometry:
        return None
    return sa.func.ST_SetSRID(sa.func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _bands_at_or_above(min_score_band: str | None) -> set[str] | None:
    if min_score_band is None:
        return None
    if min_score_band not in BAND_ORDER:
        raise RuntimeError(f"Unsupported min_score_band: {min_score_band}. Valid values are: {', '.join(BAND_ORDER)}")
    minimum = BAND_ORDER[min_score_band]
    return {band for band, order in BAND_ORDER.items() if order >= minimum}


def _passes_band(value: Any, min_score_band: str | None) -> bool:
    bands = _bands_at_or_above(min_score_band)
    return bands is None or str(value) in bands


def build_domain_sync_plan(settings: ApiSettings, *, city_key: str | None = None) -> dict[str, Any]:
    summary = _load_dashboard_summary(settings)
    cities: list[dict[str, Any]] = []
    root_dir = settings.root_dir
    for run in _published_runs(summary):
        run_city_key = str(run.get("city_key") or "").strip()
        if city_key is not None and run_city_key != city_key:
            continue
        segment_scores = run.get("segment_scores") or {}
        score_tiles = run.get("score_tiles") or {}
        segment_outputs = _manifest_outputs(segment_scores.get("manifest_path"), root_dir=root_dir)
        tile_outputs = _manifest_outputs(score_tiles.get("manifest_path"), root_dir=root_dir)
        segment_path = _feature_path(
            segment_scores,
            segment_outputs,
            "public_geojson_path",
            "public_segments_path",
            root_dir=root_dir,
        )
        analyst_path = _feature_path(
            segment_scores,
            segment_outputs,
            "analyst_csv_path",
            "analyst_segments_path",
            root_dir=root_dir,
        )
        tile_path = _feature_path(
            score_tiles,
            tile_outputs,
            "public_geojson_path",
            "public_tiles_path",
            root_dir=root_dir,
        )
        cities.append(
            {
                "city_key": run_city_key,
                "display_name": run.get("display_name") or run_city_key.title(),
                "prediction_run_label": run.get("prediction_run_label"),
                "occurred_years": list(run.get("occurred_years") or []),
                "segment_features": len(_load_feature_collection(segment_path)) if segment_path else 0,
                "segment_detail_rows": len(_load_csv_rows(analyst_path)) if analyst_path else 0,
                "public_tile_features": len(_load_feature_collection(tile_path)) if tile_path else 0,
                "segment_manifest_path": segment_scores.get("manifest_path"),
                "tile_manifest_path": score_tiles.get("manifest_path"),
            }
        )
    return {
        "sync_contract_version": SYNC_CONTRACT_VERSION,
        "serving_contract_version": DOMAIN_SERVING_CONTRACT_VERSION,
        "cities": cities,
        "stats": {
            "city_count": len(cities),
            "segment_features": sum(int(city["segment_features"]) for city in cities),
            "public_tile_features": sum(int(city["public_tile_features"]) for city in cities),
        },
    }


def _delete_existing_city_domain(session: Session, scope: DomainSyncScope) -> None:
    model_run_ids = select(ModelRun.id).where(
        ModelRun.organization_id == scope.organization_id,
        ModelRun.municipality_id == scope.municipality_id,
    )
    for model in (RiskScore, PublicRiskTile):
        session.execute(
            delete(model).where(
                model.organization_id == scope.organization_id,
                model.municipality_id == scope.municipality_id,
            )
        )
    session.execute(
        delete(Intervention).where(
            Intervention.organization_id == scope.organization_id,
            Intervention.municipality_id == scope.municipality_id,
            Intervention.source_kind == "published_artifact_sync",
        )
    )
    session.execute(
        delete(RoadSegment).where(
            RoadSegment.organization_id == scope.organization_id,
            RoadSegment.municipality_id == scope.municipality_id,
        )
    )
    session.execute(
        delete(RoadNode).where(
            RoadNode.organization_id == scope.organization_id,
            RoadNode.municipality_id == scope.municipality_id,
        )
    )
    session.execute(
        delete(Crossing).where(
            Crossing.organization_id == scope.organization_id,
            Crossing.municipality_id == scope.municipality_id,
        )
    )
    session.execute(delete(ModelRun).where(ModelRun.id.in_(model_run_ids)))


def sync_published_artifacts_to_domain(
    session: Session,
    settings: ApiSettings,
    *,
    organization_id: str,
    municipality_id: str,
    city_key: str,
    source_id: str | None = None,
    ingestion_job_id: str | None = None,
) -> dict[str, Any]:
    summary = _load_dashboard_summary(settings)
    run = _find_run(summary, city_key)
    if run is None:
        raise RuntimeError(f"City '{city_key}' is not available in the dashboard summary.")

    scope = DomainSyncScope(
        organization_id=organization_id,
        municipality_id=municipality_id,
        city_key=city_key,
        source_id=source_id,
        ingestion_job_id=ingestion_job_id,
    )
    _delete_existing_city_domain(session, scope)

    segment_scores = run.get("segment_scores") or {}
    score_tiles = run.get("score_tiles") or {}
    root_dir = settings.root_dir
    model_run = ModelRun(
        organization_id=organization_id,
        municipality_id=municipality_id,
        external_run_id=str(run.get("prediction_run_label") or city_key),
        model_type="crash_frequency_risk",
        prediction_task=run.get("prediction_task"),
        status="published",
        metrics_json={
            "segment_scores": segment_scores,
            "score_tiles": score_tiles,
            "occurred_years": list(run.get("occurred_years") or []),
        },
        lineage_json={
            "sync_contract_version": SYNC_CONTRACT_VERSION,
            "source_dashboard_summary": str(_resolve_path(settings.dashboard_summary_path, root_dir=root_dir)),
            "source_id": source_id,
            "ingestion_job_id": ingestion_job_id,
        },
        artifact_manifest_uri=segment_scores.get("manifest_path"),
    )
    session.add(model_run)
    session.flush()

    segment_outputs = _manifest_outputs(segment_scores.get("manifest_path"), root_dir=root_dir)
    tile_outputs = _manifest_outputs(score_tiles.get("manifest_path"), root_dir=root_dir)
    public_segments_path = _feature_path(
        segment_scores,
        segment_outputs,
        "public_geojson_path",
        "public_segments_path",
        root_dir=root_dir,
    )
    analyst_segments_path = _feature_path(
        segment_scores,
        segment_outputs,
        "analyst_csv_path",
        "analyst_segments_path",
        root_dir=root_dir,
    )
    public_tiles_path = _feature_path(
        score_tiles,
        tile_outputs,
        "public_geojson_path",
        "public_tiles_path",
        root_dir=root_dir,
    )

    analyst_by_score_id = {
        str(row.get("segment_score_id") or ""): row
        for row in (_load_csv_rows(analyst_segments_path) if analyst_segments_path else [])
    }

    segment_count = 0
    score_count = 0
    for feature in _load_feature_collection(public_segments_path) if public_segments_path else []:
        properties = feature.get("properties") or {}
        score_id = str(properties.get("segment_score_id") or "")
        segment_external_id = str(properties.get("segment_id") or score_id)
        analyst_row = analyst_by_score_id.get(score_id, {})
        road_segment = RoadSegment(
            organization_id=organization_id,
            municipality_id=municipality_id,
            segment_external_id=segment_external_id,
            road_name=analyst_row.get("name") or properties.get("name"),
            road_class=str(analyst_row.get("highway") or properties.get("highway") or "") or None,
            length_m=_coerce_float(analyst_row.get("segment_length_m") or properties.get("segment_length_m")),
            properties_json={**properties, "analyst_row": analyst_row},
            geom=_geometry_expr(feature.get("geometry")),
        )
        session.add(road_segment)
        segment_count += 1

        risk_score = RiskScore(
            organization_id=organization_id,
            municipality_id=municipality_id,
            model_run_id=model_run.id,
            score_external_id=score_id or segment_external_id,
            object_type="road_segment",
            object_external_id=segment_external_id,
            occurred_year=_coerce_int(properties.get("occurred_year") or analyst_row.get("occurred_year")),
            risk_score=_coerce_float(properties.get("public_score_index") or analyst_row.get("public_score_index")),
            score_band=properties.get("public_score_band") or analyst_row.get("public_score_band"),
            predicted_crashes=_coerce_float(analyst_row.get("predicted_crash_count")),
            observed_crashes=_coerce_float(analyst_row.get("observed_crash_count")),
            properties_json={**properties, "analyst_row": analyst_row},
        )
        session.add(risk_score)
        score_count += 1

    tile_count = 0
    for feature in _load_feature_collection(public_tiles_path) if public_tiles_path else []:
        properties = feature.get("properties") or {}
        tile = PublicRiskTile(
            organization_id=organization_id,
            municipality_id=municipality_id,
            model_run_id=model_run.id,
            tile_external_id=str(properties.get("tile_score_id") or f"{city_key}:tile:{tile_count + 1}"),
            occurred_year=_coerce_int(properties.get("occurred_year")),
            tile_size_m=_coerce_float(properties.get("tile_size_m")),
            risk_score=_coerce_float(properties.get("tile_max_public_score_index")),
            score_band=properties.get("tile_public_score_band"),
            properties_json=properties,
            geom=_geometry_expr(feature.get("geometry")),
        )
        session.add(tile)
        tile_count += 1

    junction_count = _sync_support_points(
        session,
        settings,
        scope,
        model=RoadNode,
        path_value=settings.get_signal_junction_metrics_path(city_key),
        external_id_fields=("node_object_id", "junction_id", "signal_id"),
        name_fields=("name",),
        type_field="node_role",
        extra_fields={"control_type": "control_type", "signal_id": "signal_id"},
    )
    crossing_count = _sync_support_points(
        session,
        settings,
        scope,
        model=Crossing,
        path_value=settings.get_crossing_priority_path(city_key),
        external_id_fields=("node_object_id", "crossing_id"),
        name_fields=("crossing_name",),
        type_field="crossing_type",
        extra_fields={
            "protection_type": "crossing_protection_state",
            "accessibility_score": "accessibility_score",
        },
    )

    intervention_count = _sync_interventions(session, scope, _find_shortlist(summary, city_key))
    session.flush()
    return {
        "sync_contract_version": SYNC_CONTRACT_VERSION,
        "organization_id": organization_id,
        "municipality_id": municipality_id,
        "city_key": city_key,
        "model_run_id": str(model_run.id),
        "stats": {
            "model_runs": 1,
            "road_segments": segment_count,
            "risk_scores": score_count,
            "public_risk_tiles": tile_count,
            "road_nodes": junction_count,
            "crossings": crossing_count,
            "interventions": intervention_count,
        },
    }


def _sync_support_points(
    session: Session,
    settings: ApiSettings,
    scope: DomainSyncScope,
    *,
    model: type[RoadNode] | type[Crossing],
    path_value: str | Path | None,
    external_id_fields: tuple[str, ...],
    name_fields: tuple[str, ...],
    type_field: str,
    extra_fields: dict[str, str],
) -> int:
    if path_value is None:
        return 0
    path = _resolve_path(path_value, root_dir=settings.root_dir)
    count = 0
    for feature in _load_feature_collection(path):
        properties = feature.get("properties") or {}
        external_id = next((str(properties.get(field)) for field in external_id_fields if properties.get(field)), None)
        if not external_id:
            continue
        name = next((str(properties.get(field)) for field in name_fields if properties.get(field)), None)
        payload: dict[str, Any] = {
            "organization_id": scope.organization_id,
            "municipality_id": scope.municipality_id,
            "properties_json": {**properties, "label": name},
            "geom": _geometry_expr(feature.get("geometry")),
        }
        if model is RoadNode:
            payload.update(
                {
                    "node_external_id": external_id,
                    "node_type": properties.get(type_field),
                    "control_type": properties.get(extra_fields.get("control_type", "")),
                    "signal_id": properties.get(extra_fields.get("signal_id", "")),
                }
            )
        else:
            payload.update(
                {
                    "crossing_external_id": external_id,
                    "crossing_type": properties.get(type_field),
                    "protection_type": properties.get(extra_fields.get("protection_type", "")),
                    "accessibility_score": _coerce_float(properties.get(extra_fields.get("accessibility_score", ""))),
                }
            )
        session.add(model(**payload))
        count += 1
    return count


def _sync_interventions(session: Session, scope: DomainSyncScope, shortlist: dict[str, Any] | None) -> int:
    if not shortlist:
        return 0
    count = 0
    for index, corridor in enumerate(shortlist.get("top_corridors") or [], start=1):
        if not isinstance(corridor, dict):
            continue
        session.add(
            Intervention(
                organization_id=scope.organization_id,
                municipality_id=scope.municipality_id,
                target_object_type="corridor",
                target_object_id=str(corridor.get("corridor_label") or f"corridor-{index}"),
                intervention_type="portfolio_candidate",
                expected_benefit=_coerce_float(corridor.get("predicted_crash_total")),
                priority_score=_coerce_float(corridor.get("best_rank")),
                status="candidate",
                source_kind="published_artifact_sync",
                properties_json=corridor,
            )
        )
        count += 1
    for index, tile in enumerate(shortlist.get("hotspot_tiles") or [], start=1):
        if not isinstance(tile, dict):
            continue
        session.add(
            Intervention(
                organization_id=scope.organization_id,
                municipality_id=scope.municipality_id,
                target_object_type="public_risk_tile",
                target_object_id=str(tile.get("tile_score_id") or f"hotspot-tile-{index}"),
                intervention_type="hotspot_review",
                priority_score=_coerce_float(tile.get("tile_max_public_score_index")),
                status="candidate",
                source_kind="published_artifact_sync",
                properties_json=tile,
            )
        )
        count += 1
    return count


def _city_record(model_run: ModelRun, city_key: str, display_name: str) -> dict[str, Any]:
    metrics = model_run.metrics_json or {}
    score_tiles = metrics.get("score_tiles") or {}
    segment_scores = metrics.get("segment_scores") or {}
    return {
        "city_key": city_key,
        "display_name": display_name,
        "prediction_run_label": model_run.external_run_id,
        "prediction_task": model_run.prediction_task,
        "occurred_years": list(metrics.get("occurred_years") or []),
        "segment_score_rows": segment_scores.get("segment_score_rows"),
        "tile_rows": score_tiles.get("tile_rows"),
        "tile_size_m": score_tiles.get("tile_size_m"),
        "supports_junction_layer": True,
        "supports_crossing_layer": True,
    }


def list_public_cities_from_domain(session: Session) -> dict[str, Any] | None:
    rows = session.execute(
        select(ModelRun, Municipality.slug, Municipality.name)
        .join(Municipality, ModelRun.municipality_id == Municipality.id)
        .where(ModelRun.status == "published")
        .order_by(ModelRun.created_at.desc())
    ).all()
    if not rows:
        return None
    seen: set[str] = set()
    cities: list[dict[str, Any]] = []
    for model_run, slug, name in rows:
        if slug in seen:
            continue
        seen.add(slug)
        cities.append(_city_record(model_run, str(slug), str(name or slug).title()))
    return {
        "summary_stats": {
            "published_run_count": len(cities),
            "serving_source": "postgis",
        },
        "cities": sorted(cities, key=lambda row: str(row["display_name"])),
    }


def _latest_model_run_for_city(session: Session, city_key: str) -> tuple[ModelRun, str, str] | None:
    row = session.execute(
        select(ModelRun, Municipality.slug, Municipality.name)
        .join(Municipality, ModelRun.municipality_id == Municipality.id)
        .where(Municipality.slug == city_key)
        .where(ModelRun.status == "published")
        .order_by(ModelRun.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], str(row[1]), str(row[2] or row[1]).title()


def _geometry_from_db(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _properties_with_numeric_values(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe(value) for key, value in properties.items()}


def _feature(geometry: Any, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _geometry_from_db(geometry),
        "properties": _properties_with_numeric_values(properties),
    }


def build_public_risk_map_from_domain(
    session: Session,
    *,
    city_key: str,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
) -> dict[str, Any] | None:
    run_info = _latest_model_run_for_city(session, city_key)
    if run_info is None:
        return None
    model_run, resolved_city_key, display_name = run_info
    rows = session.execute(
        select(PublicRiskTile, sa.func.ST_AsGeoJSON(PublicRiskTile.geom))
        .where(PublicRiskTile.model_run_id == model_run.id)
        .order_by(PublicRiskTile.risk_score.desc().nullslast())
    ).all()
    filtered = [
        (tile, geom)
        for tile, geom in rows
        if (occurred_year is None or tile.occurred_year == occurred_year)
        and _passes_band(tile.score_band, min_score_band)
    ]
    selected = filtered[:limit] if limit is not None else filtered
    features = [
        _feature(
            geom,
            {
                **dict(tile.properties_json or {}),
                "tile_score_id": tile.tile_external_id,
                "occurred_year": tile.occurred_year,
                "tile_size_m": tile.tile_size_m,
                "tile_max_public_score_index": tile.risk_score,
                "tile_public_score_band": tile.score_band,
            },
        )
        for tile, geom in selected
    ]
    score_tiles = (model_run.metrics_json or {}).get("score_tiles") or {}
    segment_scores = (model_run.metrics_json or {}).get("segment_scores") or {}
    return {
        "serving_source": "postgis",
        "city": _city_record(model_run, resolved_city_key, display_name),
        "filters": {
            "occurred_year": occurred_year,
            "min_score_band": min_score_band,
            "limit": limit,
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
        "map_resource": {
            "resource_name": "segment_score_tiles",
            "view": "public_tiles",
            "contract_version": "segment_score_tiles_postgis_v1",
            "manifest_path": model_run.artifact_manifest_uri or f"postgis://model_runs/{model_run.id}",
            "query": {
                "occurred_year": occurred_year,
                "min_score_band": min_score_band,
                "limit": limit,
            },
            "source_stats": model_run.metrics_json or {},
            "stats": {
                "available_years": sorted({tile.occurred_year for tile, _ in rows if tile.occurred_year is not None}),
                "matched_features": len(filtered),
                "returned_features": len(features),
            },
            "data": _feature_collection(features),
        },
    }


def build_public_interventions_from_domain(session: Session, *, city_key: str) -> dict[str, Any] | None:
    run_info = _latest_model_run_for_city(session, city_key)
    if run_info is None:
        return None
    model_run, resolved_city_key, display_name = run_info
    rows = session.execute(
        select(Intervention)
        .where(Intervention.municipality_id == model_run.municipality_id)
        .where(Intervention.source_kind == "published_artifact_sync")
        .order_by(Intervention.priority_score.asc().nullslast(), Intervention.created_at.asc())
    ).scalars()
    top_corridors: list[dict[str, Any]] = []
    hotspot_tiles: list[dict[str, Any]] = []
    for intervention in rows:
        if intervention.target_object_type == "corridor":
            top_corridors.append(dict(intervention.properties_json or {}))
        elif intervention.target_object_type == "public_risk_tile":
            hotspot_tiles.append(dict(intervention.properties_json or {}))
    if not top_corridors and not hotspot_tiles:
        return None
    return {
        "serving_source": "postgis",
        "city": _city_record(model_run, resolved_city_key, display_name),
        "intervention_shortlist": {
            "top_corridors": top_corridors,
            "hotspot_tiles": hotspot_tiles,
        },
    }


def build_analyst_risk_map_from_domain(
    session: Session,
    *,
    city_key: str,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
    junction_limit: int | None,
    crossing_limit: int | None,
) -> dict[str, Any] | None:
    run_info = _latest_model_run_for_city(session, city_key)
    if run_info is None:
        return None
    model_run, resolved_city_key, display_name = run_info
    rows = session.execute(
        select(RoadSegment, RiskScore, sa.func.ST_AsGeoJSON(RoadSegment.geom))
        .join(
            RiskScore,
            sa.and_(
                RiskScore.model_run_id == model_run.id,
                RiskScore.object_type == "road_segment",
                RiskScore.object_external_id == RoadSegment.segment_external_id,
            ),
        )
        .where(RoadSegment.organization_id == model_run.organization_id)
        .where(RoadSegment.municipality_id == model_run.municipality_id)
        .order_by(RiskScore.risk_score.desc().nullslast())
    ).all()
    filtered = [
        (segment, score, geom)
        for segment, score, geom in rows
        if (occurred_year is None or score.occurred_year == occurred_year)
        and _passes_band(score.score_band, min_score_band)
    ]
    selected = filtered[:limit] if limit is not None else filtered
    features = [
        _feature(
            geom,
            {
                **dict(segment.properties_json or {}),
                "segment_score_id": score.score_external_id,
                "segment_id": segment.segment_external_id,
                "segment_name": segment.road_name,
                "occurred_year": score.occurred_year,
                "public_score_index": score.risk_score,
                "public_score_band": score.score_band,
            },
        )
        for segment, score, geom in selected
    ]
    detail_rows = [
        {
            **dict(score.properties_json or {}),
            "segment_score_id": score.score_external_id,
            "segment_id": segment.segment_external_id,
            "name": segment.road_name,
            "occurred_year": score.occurred_year,
            "public_score_index": _json_safe(score.risk_score),
            "public_score_band": score.score_band,
            "predicted_crash_count": _json_safe(score.predicted_crashes),
            "observed_crash_count": _json_safe(score.observed_crashes),
        }
        for segment, score, _ in selected
    ]
    return {
        "serving_source": "postgis",
        "city": _city_record(model_run, resolved_city_key, display_name),
        "filters": {
            "occurred_year": occurred_year,
            "min_score_band": min_score_band,
            "limit": limit,
            "junction_limit": junction_limit,
            "crossing_limit": crossing_limit,
        },
        "segment_layer": {
            "resource_name": "segment_scores",
            "view": "public_segments",
            "contract_version": "segment_scores_postgis_public_v1",
            "manifest_path": model_run.artifact_manifest_uri or f"postgis://model_runs/{model_run.id}",
            "query": {
                "occurred_year": occurred_year,
                "min_score_band": min_score_band,
                "limit": limit,
            },
            "source_stats": model_run.metrics_json or {},
            "stats": {
                "available_years": sorted({score.occurred_year for _, score, _ in rows if score.occurred_year is not None}),
                "matched_features": len(filtered),
                "returned_features": len(features),
            },
            "data": _feature_collection(features),
        },
        "segment_details": {
            "contract_version": "segment_scores_postgis_analyst_v1",
            "stats": {
                "matched_rows": len(filtered),
                "returned_rows": len(detail_rows),
            },
            "rows": detail_rows,
        },
        "support_layers": {
            "junctions": _support_point_layer(
                session,
                model_run=model_run,
                model=RoadNode,
                limit=junction_limit,
                default_limit=173,
                score_fields=("crash_count", "injury_crash_count"),
            ),
            "crossings": _support_point_layer(
                session,
                model_run=model_run,
                model=Crossing,
                limit=crossing_limit,
                default_limit=180,
                score_fields=("pedestrian_crossing_priority_score", "public_score_index"),
            ),
        },
    }


def _support_point_layer(
    session: Session,
    *,
    model_run: ModelRun,
    model: type[RoadNode] | type[Crossing],
    limit: int | None,
    default_limit: int,
    score_fields: tuple[str, ...],
) -> dict[str, Any]:
    rows = session.execute(
        select(model, sa.func.ST_AsGeoJSON(model.geom))
        .where(model.organization_id == model_run.organization_id)
        .where(model.municipality_id == model_run.municipality_id)
    ).all()
    resolved_limit = default_limit if limit is None else limit

    def sort_key(row: tuple[RoadNode | Crossing, Any]) -> tuple[float, ...]:
        properties = row[0].properties_json or {}
        return tuple(-(_coerce_float(properties.get(field)) or 0.0) for field in score_fields)

    selected = sorted(rows, key=sort_key)[:resolved_limit]
    features = [
        _feature(
            geom,
            {
                **dict(item.properties_json or {}),
                "node_object_id": getattr(item, "node_external_id", None) or getattr(item, "crossing_external_id", None),
            },
        )
        for item, geom in selected
    ]
    return {
        "availability": "available" if rows else "unavailable",
        "source_path": f"postgis://{model.__tablename__}",
        "stats": {
            "matched_features": len(rows),
            "returned_features": len(features),
        },
        "data": _feature_collection(features),
    }


def try_domain_payload(builder: Any, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return builder(*args, **kwargs)
    except SQLAlchemyError:
        return None


__all__ = [
    "DOMAIN_SERVING_CONTRACT_VERSION",
    "SYNC_CONTRACT_VERSION",
    "build_analyst_risk_map_from_domain",
    "build_domain_sync_plan",
    "build_public_interventions_from_domain",
    "build_public_risk_map_from_domain",
    "list_public_cities_from_domain",
    "sync_published_artifacts_to_domain",
    "try_domain_payload",
]
