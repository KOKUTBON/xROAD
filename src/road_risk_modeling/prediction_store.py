"""Prediction-store publishing utilities for segment-level score artifacts."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY,
    SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    governance_contract_reference,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


PREDICTION_STORE_VERSION = "segment_prediction_store_v1"
SEGMENT_SCORES_PUBLIC_CONTRACT_VERSION = "segment_scores_public_v1"
SEGMENT_SCORES_ANALYST_CONTRACT_VERSION = "segment_scores_analyst_v1"
RECOMMENDATION_REVIEW_STORE_VERSION = "recommendation_review_store_v1"

RECOMMENDATION_REVIEW_STATES = {
    "proposed",
    "engineer_reviewed",
    "approved",
    "rejected",
}
REJECTION_REASON_CODES = {
    "site_constraint",
    "insufficient_evidence",
    "cost_or_deliverability",
    "conflicts_with_plan",
    "unsafe_or_inapplicable",
    "duplicate",
    "other",
}

# Public-facing field whitelist projected into segment-score GeoJSON
# features. Must stay a subset of the `segment_score` matrix entries
# whose `role_visibility` includes 'public' (see
# `road_risk_modeling.data_governance` and the
# tests/test_prediction_store.py invariant). The raw OSM `segment_id`
# is classified `internal` in the matrix, so it is intentionally
# excluded here - downstream consumers route via `segment_score_id`.
PUBLIC_SCORE_FIELDS = [
    "segment_score_id",
    "occurred_year",
    "prediction_run_label",
    "prediction_task",
    "public_score_index",
    "public_score_band",
    "score_decile",
]

ANALYST_CORE_FIELDS = [
    "segment_score_id",
    "segment_id",
    "occurred_year",
    "prediction_run_label",
    "prediction_task",
    "prediction_column",
    "predicted_crash_count",
    "observed_crash_count",
    "score_rank_desc",
    "score_percentile",
    "score_decile",
    "public_score_index",
    "public_score_band",
]


class RecommendationReviewStore:
    """SQLite-backed, append-only audit trail for recommendation decisions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS recommendation_reviews (
                recommendation_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                state TEXT NOT NULL,
                model_version TEXT NOT NULL,
                data_lineage_hash TEXT NOT NULL,
                reviewer TEXT,
                review_note TEXT,
                rejection_reason_code TEXT,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recommendation_review_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason_code TEXT,
                note TEXT,
                occurred_at_utc TEXT NOT NULL,
                FOREIGN KEY (recommendation_id)
                    REFERENCES recommendation_reviews(recommendation_id)
            );
            """
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> RecommendationReviewStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def propose(
        self,
        *,
        recommendation_id: str,
        payload: dict[str, Any],
        model_version: str,
        data_lineage_hash: str,
        actor: str = "system",
    ) -> dict[str, Any]:
        if not recommendation_id or not model_version or not data_lineage_hash:
            raise ValueError("recommendation_id, model_version, and data_lineage_hash are required.")
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO recommendation_reviews (
                    recommendation_id, payload_json, state, model_version,
                    data_lineage_hash, created_at_utc, updated_at_utc
                ) VALUES (?, ?, 'proposed', ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    json.dumps(payload, sort_keys=True),
                    model_version,
                    data_lineage_hash,
                    now,
                    now,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO recommendation_review_events (
                    recommendation_id, from_state, to_state, actor, occurred_at_utc
                ) VALUES (?, NULL, 'proposed', ?, ?)
                """,
                (recommendation_id, actor, now),
            )
        return self.get(recommendation_id)

    def transition(
        self,
        recommendation_id: str,
        *,
        to_state: str,
        actor: str,
        note: str | None = None,
        reason_code: str | None = None,
    ) -> dict[str, Any]:
        if to_state not in RECOMMENDATION_REVIEW_STATES:
            raise ValueError(f"Unknown recommendation review state: {to_state}")
        if not actor.strip():
            raise ValueError("A named actor is required for review transitions.")
        current = self.get(recommendation_id)
        allowed = {
            "proposed": {"engineer_reviewed", "rejected"},
            "engineer_reviewed": {"approved", "rejected"},
            "approved": set(),
            "rejected": set(),
        }
        if to_state not in allowed[current["state"]]:
            raise ValueError(f"Invalid review transition: {current['state']} -> {to_state}")
        if to_state == "engineer_reviewed" and not note:
            raise ValueError("Engineer review requires a review note.")
        if to_state == "rejected" and reason_code not in REJECTION_REASON_CODES:
            raise ValueError("Rejection requires a valid reason code.")
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE recommendation_reviews
                SET state = ?,
                    reviewer = CASE
                        WHEN ? = 'engineer_reviewed' THEN ?
                        ELSE reviewer
                    END,
                    review_note = COALESCE(?, review_note),
                    rejection_reason_code = ?, updated_at_utc = ?
                WHERE recommendation_id = ?
                """,
                (
                    to_state,
                    to_state,
                    actor,
                    note,
                    reason_code,
                    now,
                    recommendation_id,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO recommendation_review_events (
                    recommendation_id, from_state, to_state, actor,
                    reason_code, note, occurred_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    current["state"],
                    to_state,
                    actor,
                    reason_code,
                    note,
                    now,
                ),
            )
        return self.get(recommendation_id)

    def get(self, recommendation_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT * FROM recommendation_reviews WHERE recommendation_id = ?",
            (recommendation_id,),
        ).fetchone()
        if row is None:
            raise KeyError(recommendation_id)
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def audit_events(self, recommendation_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT * FROM recommendation_review_events
            WHERE recommendation_id = ? ORDER BY event_id
            """,
            (recommendation_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def approved_for_api(self) -> list[dict[str, Any]]:
        """Return only records that have an explicit engineer review and approval."""
        rows = self._connection.execute(
            """
            SELECT r.* FROM recommendation_reviews r
            WHERE r.state = 'approved'
              AND EXISTS (
                SELECT 1 FROM recommendation_review_events e
                WHERE e.recommendation_id = r.recommendation_id
                  AND e.to_state = 'engineer_reviewed'
              )
            ORDER BY r.recommendation_id
            """
        ).fetchall()
        approved: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            approved.append(item)
        return approved

    def rejection_training_signals(self) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT recommendation_id, model_version, data_lineage_hash,
                   reviewer, rejection_reason_code, review_note, payload_json
            FROM recommendation_reviews
            WHERE state = 'rejected'
            ORDER BY recommendation_id
            """
        ).fetchall()
        return [
            {
                **{key: value for key, value in dict(row).items() if key != "payload_json"},
                "payload": json.loads(row["payload_json"]),
                "accepted_label": 0,
            }
            for row in rows
        ]


def _normalize_prediction_segment_id(segment_id: str) -> tuple[str, str | None]:
    if "::" in segment_id:
        jurisdiction, normalized = segment_id.split("::", 1)
        return normalized, jurisdiction
    return segment_id, None


def _coerce_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse numeric value for '{field_name}': {value!r}") from exc


def _public_score_band(percentile: float) -> str:
    if percentile >= 0.95:
        return "very_high"
    if percentile >= 0.80:
        return "high"
    if percentile >= 0.50:
        return "moderate"
    return "low"


def _load_segment_features(segments_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = json.loads(segments_path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError("Segment GeoJSON must be a FeatureCollection.")

    features = payload.get("features", [])
    by_segment_id: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        segment_id = properties.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise RuntimeError("Every segment feature must include a non-empty 'segment_id' property.")
        if segment_id in by_segment_id:
            raise RuntimeError(f"Duplicate segment_id found in segment layer: {segment_id}")
        by_segment_id[segment_id] = feature
    return features, by_segment_id


def _prediction_store_contract(
    prediction_run_label: str,
    prediction_column: str,
) -> dict[str, Any]:
    return {
        "resource_name": "segment_scores",
        "prediction_store_version": PREDICTION_STORE_VERSION,
        "public_contract_version": SEGMENT_SCORES_PUBLIC_CONTRACT_VERSION,
        "analyst_contract_version": SEGMENT_SCORES_ANALYST_CONTRACT_VERSION,
        "prediction_run_label": prediction_run_label,
        "prediction_column": prediction_column,
        "public_fields": PUBLIC_SCORE_FIELDS,
        "analyst_core_fields": ANALYST_CORE_FIELDS,
        "public_response_shape": {
            "type": "FeatureCollection",
            "feature_id": "segment_score_id",
            "properties": PUBLIC_SCORE_FIELDS,
        },
        "analyst_response_shape": {
            "type": "tabular",
            "primary_key": "segment_score_id",
            "minimum_fields": ANALYST_CORE_FIELDS,
        },
    }


def publish_segment_scores(
    predictions_path: str | Path,
    segments_path: str | Path,
    metrics_path: str | Path,
    output_dir: str | Path,
    prediction_column: str = "random_forest_poisson_prediction",
    *,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    predictions_input = Path(predictions_path)
    segments_input = Path(segments_path)
    metrics_input = Path(metrics_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    analyst_csv_path = output_root / "segment_scores_analyst.csv"
    analyst_geojson_path = output_root / "segment_scores_analyst.geojson"
    public_geojson_path = output_root / "segment_scores_public.geojson"
    manifest_path = output_root / "segment_scores.manifest.json"

    metrics_payload = json.loads(metrics_input.read_text(encoding="utf-8"))
    prediction_run_label = metrics_input.parent.name
    prediction_task = (
        metrics_payload.get("training_config", {}).get("task")
        if isinstance(metrics_payload.get("training_config"), dict)
        else None
    ) or "unknown_prediction_task"

    _, segments_by_id = _load_segment_features(segments_input)
    with predictions_input.open(encoding="utf-8", newline="") as handle:
        prediction_rows = list(csv.DictReader(handle))
    if not prediction_rows:
        raise RuntimeError("Prediction CSV is empty.")
    if prediction_column not in prediction_rows[0]:
        raise RuntimeError(f"Prediction CSV does not contain required column: {prediction_column}")

    scored_rows: list[dict[str, Any]] = []
    for row in prediction_rows:
        segment_id_raw = row.get("segment_id")
        occurred_year = row.get("occurred_year")
        if not segment_id_raw:
            raise RuntimeError("Prediction CSV must contain non-empty 'segment_id' values.")
        normalized_segment_id, target_jurisdiction = _normalize_prediction_segment_id(segment_id_raw)
        segment_feature = segments_by_id.get(normalized_segment_id)
        if segment_feature is None:
            raise RuntimeError(
                f"Prediction row segment_id '{segment_id_raw}' could not be matched to the segment layer."
            )
        if not occurred_year:
            raise RuntimeError("Prediction CSV must contain non-empty 'occurred_year' values.")

        predicted_crash_count = _coerce_float(row.get(prediction_column), field_name=prediction_column)
        observed_crash_count = _coerce_float(row.get("crash_count", 0.0), field_name="crash_count")

        segment_properties = dict(segment_feature.get("properties") or {})
        scored_rows.append(
            {
                **segment_properties,
                "segment_id": normalized_segment_id,
                "segment_score_id": f"{prediction_run_label}:{occurred_year}:{normalized_segment_id}",
                "occurred_year": int(float(occurred_year)),
                "prediction_run_label": prediction_run_label,
                "prediction_task": prediction_task,
                "prediction_column": prediction_column,
                "target_jurisdiction": target_jurisdiction,
                "predicted_crash_count": predicted_crash_count,
                "observed_crash_count": observed_crash_count,
                "__geometry": segment_feature.get("geometry"),
            }
        )

    ranked_rows = sorted(
        scored_rows,
        key=lambda item: (-float(item["predicted_crash_count"]), str(item["segment_id"])),
    )
    total_rows = len(ranked_rows)
    max_prediction = max(float(row["predicted_crash_count"]) for row in ranked_rows) if ranked_rows else 0.0
    total_predicted = sum(float(row["predicted_crash_count"]) for row in ranked_rows)
    total_observed = sum(float(row["observed_crash_count"]) for row in ranked_rows)
    top_k = max(1, total_rows // 20)
    top_5pct_observed = sum(float(row["observed_crash_count"]) for row in ranked_rows[:top_k])

    analyst_records: list[dict[str, Any]] = []
    analyst_features: list[dict[str, Any]] = []
    public_features: list[dict[str, Any]] = []
    for index, row in enumerate(ranked_rows, start=1):
        percentile = 1.0 if total_rows == 1 else 1.0 - ((index - 1) / (total_rows - 1))
        score_decile = max(1, min(10, 11 - int(percentile * 10 + 1e-9)))
        public_score_index = round(percentile * 100.0, 3)
        public_score_band = _public_score_band(percentile)

        analyst_record = {
            key: value
            for key, value in row.items()
            if key != "__geometry"
        }
        analyst_record.update(
            {
                "score_rank_desc": index,
                "score_percentile": round(percentile, 6),
                "score_decile": score_decile,
                "public_score_index": public_score_index,
                "public_score_band": public_score_band,
                "prediction_relative_to_max": round(
                    float(row["predicted_crash_count"]) / max_prediction if max_prediction > 0 else 0.0,
                    6,
                ),
            }
        )
        analyst_records.append(analyst_record)

        analyst_features.append(
            {
                "type": "Feature",
                "geometry": row["__geometry"],
                "properties": analyst_record,
            }
        )
        public_features.append(
            {
                "type": "Feature",
                "geometry": row["__geometry"],
                "properties": {field: analyst_record.get(field) for field in PUBLIC_SCORE_FIELDS},
            }
        )

    analyst_fieldnames = sorted({key for record in analyst_records for key in record.keys()})
    with analyst_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=analyst_fieldnames)
        writer.writeheader()
        writer.writerows(analyst_records)

    analyst_geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": analyst_features}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    public_geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": public_features}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    contract = _prediction_store_contract(prediction_run_label, prediction_column)
    manifest = {
        "prediction_store_version": PREDICTION_STORE_VERSION,
        "inputs": {
            "predictions_path": str(predictions_input),
            "predictions_sha256": _sha256(predictions_input),
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "metrics_path": str(metrics_input),
            "metrics_sha256": _sha256(metrics_input),
        },
        "outputs": {
            "analyst_csv_path": str(analyst_csv_path),
            "analyst_csv_sha256": _sha256(analyst_csv_path),
            "analyst_geojson_path": str(analyst_geojson_path),
            "analyst_geojson_sha256": _sha256(analyst_geojson_path),
            "public_geojson_path": str(public_geojson_path),
            "public_geojson_sha256": _sha256(public_geojson_path),
            "manifest_path": str(manifest_path),
        },
        "contract": contract,
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[
                SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY,
                SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY,
            ],
            role_policy_ids=artifact_role_policy_ids(
                SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY,
                SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY,
            ),
        ),
        "stats": {
            "segment_score_rows": total_rows,
            "holdout_years": sorted({record["occurred_year"] for record in analyst_records}),
            "prediction_run_label": prediction_run_label,
            "prediction_task": prediction_task,
            "prediction_column": prediction_column,
            "max_predicted_crash_count": max_prediction,
            "predicted_crash_total": round(total_predicted, 6),
            "observed_crash_total": round(total_observed, 6),
            "top_5pct_observed_crash_share": round(top_5pct_observed / total_observed, 6) if total_observed > 0 else 0.0,
        },
        "source_run": {
            "training_config": metrics_payload.get("training_config", {}),
            "lineage": metrics_payload.get("lineage", {}),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("model_metrics", metrics_input, _sha256(metrics_input)),
                _artifact_reference("model_predictions", predictions_input, _sha256(predictions_input)),
                _artifact_reference("segment_layer", segments_input, _sha256(segments_input)),
            ],
            publishable_outputs=[
                _artifact_reference("segment_scores_public_geojson", public_geojson_path, _sha256(public_geojson_path)),
                _artifact_reference("segment_scores_analyst_csv", analyst_csv_path, _sha256(analyst_csv_path)),
            ],
            supporting_outputs=[
                _artifact_reference("segment_scores_analyst_geojson", analyst_geojson_path, _sha256(analyst_geojson_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "prediction_store_version": PREDICTION_STORE_VERSION,
        "stats": manifest["stats"],
        "contract": {
            "public_contract_version": contract["public_contract_version"],
            "analyst_contract_version": contract["analyst_contract_version"],
        },
    }
