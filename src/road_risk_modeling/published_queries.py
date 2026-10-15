"""Read-only query helpers for published serving artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from road_risk_modeling.data_governance import publishable_fields_for_role


BAND_ORDER = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "very_high": 3,
}

RESOURCE_VIEWS = {
    "segment_scores": {"public_segments", "analyst_segments"},
    "segment_score_tiles": {"public_tiles"},
}


# Map each view to the (record_kind, role) pair whose classification
# matrix entry from `data_governance` governs the publishable field set.
#
# Both public AND analyst surfaces are now matrix-filtered. The
# defense-in-depth value is symmetric: a future segment-score CSV
# column that is not explicitly classified in the matrix is
# default-denied from both public AND analyst output, forcing the
# author to classify it before it can flow through.
#
# This was previously asymmetric (analyst views were unfiltered)
# because some analyst CSV columns (sort ranks, intermediate
# features) were not in the matrix. The matrix has since been
# extended to cover every column carried by ANALYST_CORE_FIELDS
# (see `prediction_store.py`), so the filter is now safe to apply
# uniformly.
#
# Adding a new view to `RESOURCE_VIEWS` without listing it here means
# it stays unfiltered. The contract for the views below is that their
# output respects the Issue 01 matrix.
VIEW_ROLE_POLICY: dict[str, dict[str, tuple[str, str]]] = {
    "segment_scores": {
        "public_segments": ("segment_score", "public"),
        "analyst_segments": ("segment_score", "analyst"),
    },
    "segment_score_tiles": {
        "public_tiles": ("score_tile", "public"),
    },
}


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = payload.get("contract")
    if not isinstance(contract, dict) or not isinstance(contract.get("resource_name"), str):
        raise RuntimeError("Published manifest must include contract.resource_name.")
    return payload


def _normalize_view(resource_name: str, requested_view: str | None) -> str:
    allowed = RESOURCE_VIEWS.get(resource_name)
    if not allowed:
        raise RuntimeError(f"Unsupported published resource type: {resource_name}")
    if requested_view is None:
        if resource_name == "segment_scores":
            return "public_segments"
        return "public_tiles"
    if requested_view not in allowed:
        raise RuntimeError(
            f"View '{requested_view}' is not valid for resource '{resource_name}'. "
            f"Valid views are: {', '.join(sorted(allowed))}"
        )
    return requested_view


def _passes_min_band(value: Any, min_band: str | None) -> bool:
    if min_band is None:
        return True
    current = BAND_ORDER.get(str(value))
    minimum = BAND_ORDER.get(min_band)
    if minimum is None:
        raise RuntimeError(f"Unsupported min_score_band: {min_band}. Valid values are: {', '.join(BAND_ORDER)}")
    if current is None:
        return False
    return current >= minimum


def _coerce_int(value: Any, *, field_name: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse integer value for '{field_name}': {value!r}") from exc


def _coerce_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse numeric value for '{field_name}': {value!r}") from exc


def _resolve_path(path_value: str | Path, *, root_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root_dir / path


def _query_feature_collection(
    geojson_path: Path,
    *,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
    band_field: str,
    score_field: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Expected FeatureCollection at: {geojson_path}")

    features = payload.get("features", [])
    filtered: list[dict[str, Any]] = []
    years: set[int] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        year_value = _coerce_int(properties.get("occurred_year"), field_name="occurred_year")
        years.add(year_value)
        if occurred_year is not None and year_value != occurred_year:
            continue
        if not _passes_min_band(properties.get(band_field), min_score_band):
            continue
        filtered.append(feature)

    filtered.sort(
        key=lambda feature: -_coerce_float(feature.get("properties", {}).get(score_field, 0.0), field_name=score_field)
    )
    matched_count = len(filtered)
    if limit is not None:
        filtered = filtered[:limit]

    return (
        {"type": "FeatureCollection", "features": filtered},
        {
            "available_years": sorted(years),
            "matched_features": matched_count,
            "returned_features": len(filtered),
        },
    )


def _query_analyst_rows(
    csv_path: Path,
    *,
    occurred_year: int | None,
    min_score_band: str | None,
    limit: int | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    filtered: list[dict[str, Any]] = []
    years: set[int] = set()
    for row in rows:
        year_value = _coerce_int(row.get("occurred_year"), field_name="occurred_year")
        years.add(year_value)
        if occurred_year is not None and year_value != occurred_year:
            continue
        if not _passes_min_band(row.get("public_score_band"), min_score_band):
            continue
        filtered.append(row)

    filtered.sort(key=lambda row: _coerce_int(row.get("score_rank_desc"), field_name="score_rank_desc"))
    matched_count = len(filtered)
    if limit is not None:
        filtered = filtered[:limit]

    return (
        {"type": "tabular", "rows": filtered},
        {
            "available_years": sorted(years),
            "matched_rows": matched_count,
            "returned_rows": len(filtered),
        },
    )


def _apply_matrix_filter(
    data: dict[str, Any], record_kind: str, role: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Drop any property/column that the `record_kind` matrix does not publish for `role`.

    Returns the filtered data plus a `policy_meta` dict that
    downstream consumers can pass through to clients so they know
    which redaction policy was applied. The filter is intentionally
    defensive: it never adds keys, never reorders, and never changes
    values - it only restricts the output to the matrix-allowed set.
    """
    publishable = set(publishable_fields_for_role(record_kind, role))
    if data.get("type") == "FeatureCollection":
        filtered_features: list[dict[str, Any]] = []
        for feature in data.get("features", []):
            if not isinstance(feature, dict):
                filtered_features.append(feature)
                continue
            properties = feature.get("properties") or {}
            kept = {key: value for key, value in properties.items() if key in publishable}
            filtered_features.append({**feature, "properties": kept})
        out_data = {**data, "features": filtered_features}
    elif data.get("type") == "tabular":
        filtered_rows: list[dict[str, Any]] = []
        for row in data.get("rows", []):
            if not isinstance(row, dict):
                filtered_rows.append(row)
                continue
            filtered_rows.append({k: v for k, v in row.items() if k in publishable})
        out_data = {**data, "rows": filtered_rows}
    else:
        out_data = data
    return out_data, {
        "record_kind": record_kind,
        "role": role,
        "publishable_fields": sorted(publishable),
    }


# Back-compat alias: the matrix filter was named after segment_score
# when it was first introduced. The current helper accepts any
# record_kind; keep the original name for any external callers.
def _apply_segment_score_matrix_filter(
    data: dict[str, Any], role: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Back-compat wrapper around `_apply_matrix_filter(data, "segment_score", role)`."""
    return _apply_matrix_filter(data, "segment_score", role)


def query_published_resource(
    manifest_path: str | Path,
    *,
    view: str | None = None,
    occurred_year: int | None = None,
    min_score_band: str | None = None,
    limit: int | None = None,
    root_dir: str | Path = ".",
) -> dict[str, Any]:
    if limit is not None and limit <= 0:
        raise RuntimeError("limit must be greater than 0 when provided.")

    root_path = Path(root_dir)
    manifest_input = _resolve_path(manifest_path, root_dir=root_path)
    manifest = _load_manifest(manifest_input)
    contract = manifest["contract"]
    resource_name = contract["resource_name"]
    resolved_view = _normalize_view(resource_name, view)

    if resolved_view == "public_segments":
        data_path = _resolve_path(manifest["outputs"]["public_geojson_path"], root_dir=root_path)
        data, stats = _query_feature_collection(
            data_path,
            occurred_year=occurred_year,
            min_score_band=min_score_band,
            limit=limit,
            band_field="public_score_band",
            score_field="public_score_index",
        )
        contract_version = contract.get("public_contract_version")
    elif resolved_view == "analyst_segments":
        data_path = _resolve_path(manifest["outputs"]["analyst_csv_path"], root_dir=root_path)
        data, stats = _query_analyst_rows(
            data_path,
            occurred_year=occurred_year,
            min_score_band=min_score_band,
            limit=limit,
        )
        contract_version = contract.get("analyst_contract_version")
    elif resolved_view == "public_tiles":
        data_path = _resolve_path(manifest["outputs"]["public_geojson_path"], root_dir=root_path)
        data, stats = _query_feature_collection(
            data_path,
            occurred_year=occurred_year,
            min_score_band=min_score_band,
            limit=limit,
            band_field="tile_public_score_band",
            score_field="tile_max_public_score_index",
        )
        contract_version = contract.get("public_contract_version")
    else:
        raise RuntimeError(f"Unhandled view: {resolved_view}")

    # Defense-in-depth: when the view is governed by a matrix policy,
    # restrict the output to the matrix-allowed fields before
    # returning. This compounds the redaction enforced upstream in
    # `apps/api/services/segment_drill_down.py` so any future caller of
    # `query_published_resource` automatically inherits the policy.
    policy_meta: dict[str, Any] | None = None
    view_policy_map = VIEW_ROLE_POLICY.get(resource_name)
    if view_policy_map is not None:
        view_policy = view_policy_map.get(resolved_view)
        if view_policy is not None:
            policy_record_kind, policy_role = view_policy
            data, policy_meta = _apply_matrix_filter(
                data, policy_record_kind, policy_role,
            )

    payload = {
        "resource_name": resource_name,
        "view": resolved_view,
        "contract_version": contract_version,
        "manifest_path": str(manifest_input),
        "query": {
            "occurred_year": occurred_year,
            "min_score_band": min_score_band,
            "limit": limit,
        },
        "source_stats": manifest.get("stats", {}),
        "stats": stats,
        "data": data,
    }
    if policy_meta is not None:
        payload["redaction_policy"] = policy_meta
    return payload
