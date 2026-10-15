"""Organization-scoped recommendation reads, reviews, and action-plan exports."""

from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
from typing import Any

from apps.api.settings import ApiSettings
from road_risk_modeling.prediction_store import RecommendationReviewStore
from road_risk_modeling.recommendation_model import RECOMMENDATION_MODEL_VERSION


RECOMMENDATIONS_API_CONTRACT_VERSION = "recommendations_api_v1"


class RecommendationsError(RuntimeError):
    pass


def _safe_scope(value: str) -> str:
    normalized = "".join(character for character in value if character.isalnum() or character in "-_")
    if not normalized or normalized != value:
        raise RecommendationsError("Invalid organization or city scope.")
    return normalized


def _paths(settings: ApiSettings, organization_id: str, city_key: str) -> tuple[Path, Path, Path]:
    organization_id = _safe_scope(organization_id)
    city_key = _safe_scope(city_key)
    source = settings.root_dir / "data" / "planning" / "recommendations" / city_key
    return (
        source / "network_recommendations.geojson",
        source / "network_recommendations.manifest.json",
        settings.root_dir
        / "data"
        / "runtime"
        / "recommendation_reviews"
        / f"{organization_id}.sqlite",
    )


def _load_source(settings: ApiSettings, organization_id: str, city_key: str) -> tuple[list[dict], str, Path]:
    geojson_path, manifest_path, store_path = _paths(settings, organization_id, city_key)
    if not geojson_path.exists() or not manifest_path.exists():
        raise RecommendationsError(f"No recommendation bundle is available for city '{city_key}'.")
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lineage_hash = str(
        manifest.get("outputs", {}).get("recommendations_geojson_sha256")
        or manifest.get("inputs", {}).get("dashboard_summary_sha256")
        or "unknown"
    )
    records = []
    for feature in payload.get("features", []):
        properties = dict(feature.get("properties") or {})
        recommendation_id = (
            f"{city_key}:{properties.get('segment_score_id')}:{properties.get('countermeasure_id')}"
        )
        records.append(
            {
                **properties,
                "recommendation_id": recommendation_id,
                "object_type": "segment",
                "geometry": feature.get("geometry"),
                "contributing_factors": properties.get("top_risk_factors")
                or [
                    {
                        "label": "Network risk priority",
                        "value": properties.get("public_score_band", "not reported"),
                    },
                    {
                        "label": "Countermeasure evidence",
                        "value": properties.get("evidence_ref", "cited in model output"),
                    },
                ],
            }
        )
    return records, lineage_hash, store_path


def _seed_reviews(
    store: RecommendationReviewStore, records: list[dict], lineage_hash: str
) -> None:
    for record in records:
        try:
            store.get(record["recommendation_id"])
        except KeyError:
            store.propose(
                recommendation_id=record["recommendation_id"],
                payload=record,
                model_version=RECOMMENDATION_MODEL_VERSION,
                data_lineage_hash=lineage_hash,
            )


def list_recommendations(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    object_type: str | None = None,
    minimum_bcr: float | None = None,
    review_state: str | None = None,
) -> dict[str, Any]:
    records, lineage_hash, store_path = _load_source(settings, organization_id, city_key)
    with RecommendationReviewStore(store_path) as store:
        _seed_reviews(store, records, lineage_hash)
        rows = []
        for record in records:
            review = store.get(record["recommendation_id"])
            row = {
                **record,
                "review_state": review["state"],
                "reviewer": review["reviewer"],
                "review_note": review["review_note"],
                "rejection_reason_code": review["rejection_reason_code"],
                "model_version": review["model_version"],
                "data_lineage_hash": review["data_lineage_hash"],
            }
            if object_type and row["object_type"] != object_type:
                continue
            if minimum_bcr is not None and float(row.get("benefit_cost_ratio") or 0) < minimum_bcr:
                continue
            if review_state and row["review_state"] != review_state:
                continue
            rows.append(row)
    return {
        "contract_version": RECOMMENDATIONS_API_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "recommendation_count": len(rows),
        "recommendations": rows,
    }


def recommendation_detail(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    recommendation_id: str,
) -> dict[str, Any]:
    payload = list_recommendations(
        settings, organization_id=organization_id, city_key=city_key
    )
    row = next(
        (
            item
            for item in payload["recommendations"]
            if item["recommendation_id"] == recommendation_id
        ),
        None,
    )
    if row is None:
        raise RecommendationsError("Recommendation not found in the requested scope.")
    _, _, store_path = _paths(settings, organization_id, city_key)
    with RecommendationReviewStore(store_path) as store:
        events = store.audit_events(recommendation_id)
    return {
        "contract_version": RECOMMENDATIONS_API_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "recommendation": row,
        "audit_events": events,
    }


def transition_recommendation(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    recommendation_id: str,
    to_state: str,
    actor: str,
    note: str | None,
    reason_code: str | None,
) -> dict[str, Any]:
    recommendation_detail(
        settings,
        organization_id=organization_id,
        city_key=city_key,
        recommendation_id=recommendation_id,
    )
    _, _, store_path = _paths(settings, organization_id, city_key)
    try:
        with RecommendationReviewStore(store_path) as store:
            review = store.transition(
                recommendation_id,
                to_state=to_state,
                actor=actor,
                note=note,
                reason_code=reason_code,
            )
    except ValueError as exc:
        raise RecommendationsError(str(exc)) from exc
    return {
        "contract_version": RECOMMENDATIONS_API_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "review": review,
    }


def approved_action_plan(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
) -> list[dict[str, Any]]:
    records, lineage_hash, store_path = _load_source(settings, organization_id, city_key)
    with RecommendationReviewStore(store_path) as store:
        _seed_reviews(store, records, lineage_hash)
        return store.approved_for_api()


def action_plan_csv(rows: list[dict[str, Any]]) -> bytes:
    output = StringIO()
    columns = [
        "recommendation_id",
        "segment_label",
        "countermeasure_name",
        "expected_annual_crashes_prevented",
        "effect_ratio_low",
        "effect_ratio_central",
        "effect_ratio_high",
        "cost_band",
        "benefit_cost_ratio",
        "reviewer",
        "model_version",
        "data_lineage_hash",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "recommendation_id": row["recommendation_id"],
                **{key: row["payload"].get(key) for key in columns},
                "reviewer": row["reviewer"],
                "model_version": row["model_version"],
                "data_lineage_hash": row["data_lineage_hash"],
            }
        )
    return output.getvalue().encode("utf-8")
