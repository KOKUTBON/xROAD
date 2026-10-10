"""Resolve latest published serving artifacts from the run registry."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


RESOURCE_ALLOWED_VIEWS = {
    "segment_scores": ["public_segments", "analyst_segments"],
    "segment_score_tiles": ["public_tiles"],
}

RESOURCE_VIEW_OUTPUT_FIELDS = {
    "segment_scores": {
        "public_segments": "outputs.public_geojson_path",
        "analyst_segments": "outputs.analyst_csv_path",
    },
    "segment_score_tiles": {
        "public_tiles": "outputs.public_geojson_path",
    },
}


def _load_registry_entries(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        raise RuntimeError(
            f"Registry file does not exist: {registry_path}. "
            "Build it first with: road-risk build-run-registry --data-root data --output-dir data/registry"
        )
    entries: list[dict[str, Any]] = []
    with registry_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _entry_output_map(entry: dict[str, Any]) -> dict[str, str]:
    return {
        item["field"]: item["path"]
        for item in entry.get("output_references", [])
        if isinstance(item, dict) and isinstance(item.get("field"), str) and isinstance(item.get("path"), str)
    }


def _entry_sort_key(entry: dict[str, Any]) -> tuple[datetime, str]:
    return (
        datetime.fromisoformat(entry["document_mtime_utc"]),
        entry["document_path"],
    )


def _matches_filter(
    entry: dict[str, Any],
    *,
    resource_name: str,
    prediction_run_label: str | None,
    occurred_year: int | None,
    tile_size_m: float | None,
) -> bool:
    summary = entry.get("summary", {})
    stats = summary.get("stats", {})
    if entry.get("stage") != "serving":
        return False
    if summary.get("resource_name") != resource_name:
        return False
    if prediction_run_label is not None:
        candidate_label = stats.get("prediction_run_label") or entry.get("run_label")
        if candidate_label != prediction_run_label:
            return False
    if occurred_year is not None:
        years = stats.get("holdout_years") or []
        if occurred_year not in years:
            return False
    if tile_size_m is not None:
        candidate_tile_size = stats.get("tile_size_m")
        if candidate_tile_size is None or float(candidate_tile_size) != float(tile_size_m):
            return False
    return True


def resolve_latest_published_resource(
    resource_name: str,
    *,
    registry_path: str | Path = "data/registry/run_registry.jsonl",
    view: str | None = None,
    prediction_run_label: str | None = None,
    occurred_year: int | None = None,
    tile_size_m: float | None = None,
) -> dict[str, Any]:
    allowed_views = RESOURCE_ALLOWED_VIEWS.get(resource_name)
    if allowed_views is None:
        raise RuntimeError(
            f"Unsupported resource_name: {resource_name}. Valid values are: {', '.join(sorted(RESOURCE_ALLOWED_VIEWS))}"
        )
    if view is not None and view not in allowed_views:
        raise RuntimeError(
            f"View '{view}' is not valid for resource '{resource_name}'. "
            f"Valid values are: {', '.join(allowed_views)}"
        )

    registry_input = Path(registry_path)
    entries = _load_registry_entries(registry_input)
    matched = [
        entry
        for entry in entries
        if _matches_filter(
            entry,
            resource_name=resource_name,
            prediction_run_label=prediction_run_label,
            occurred_year=occurred_year,
            tile_size_m=tile_size_m,
        )
    ]
    if not matched:
        raise RuntimeError(
            "No published resource matched the requested filters. "
            f"resource_name={resource_name!r}, prediction_run_label={prediction_run_label!r}, "
            f"occurred_year={occurred_year!r}, tile_size_m={tile_size_m!r}"
        )

    resolved = max(matched, key=_entry_sort_key)
    output_map = _entry_output_map(resolved)
    resolved_view = view or allowed_views[0]
    resolved_view_path = output_map.get(RESOURCE_VIEW_OUTPUT_FIELDS[resource_name][resolved_view])
    if resolved_view_path is None:
        raise RuntimeError(
            f"Resolved manifest does not expose the expected output for view '{resolved_view}'."
        )

    summary = resolved.get("summary", {})
    stats = summary.get("stats", {})
    contract_versions = {
        "public_contract_version": summary.get("public_contract_version"),
        "analyst_contract_version": summary.get("analyst_contract_version"),
        "lineage_contract_version": summary.get("lineage_contract_version"),
    }

    return {
        "resource_name": resource_name,
        "registry_path": str(registry_input),
        "filters": {
            "prediction_run_label": prediction_run_label,
            "occurred_year": occurred_year,
            "tile_size_m": tile_size_m,
            "view": resolved_view,
        },
        "resolved": {
            "manifest_path": resolved["document_path"],
            "artifact_kind": resolved["artifact_kind"],
            "run_label": resolved["run_label"],
            "document_mtime_utc": resolved["document_mtime_utc"],
            "available_views": allowed_views,
            "resolved_view": resolved_view,
            "resolved_view_path": resolved_view_path,
            "contract_versions": contract_versions,
            "governance": {
                "governance_contract_version": summary.get("governance_contract_version"),
                "governance_bundle_path": summary.get("governance_bundle_path"),
                "role_policy_ids": summary.get("governance_role_policy_ids"),
            },
            "stats": stats,
        },
    }
