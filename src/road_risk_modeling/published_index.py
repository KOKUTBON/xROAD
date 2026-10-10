"""Build a static dashboard-friendly index for published serving artifacts."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .published_lineage import infer_artifact_root, resolve_published_lineage_trace
from .published_resolver import (
    RESOURCE_ALLOWED_VIEWS,
    RESOURCE_VIEW_OUTPUT_FIELDS,
    _entry_output_map,
    _load_registry_entries,
)


PUBLISHED_RESOURCE_INDEX_VERSION = "published_resource_index_v1"
PUBLISHED_RESOURCE_INDEX_CONTRACT_VERSION = "published_resource_index_public_v1"
PUBLISHED_RESOURCE_SELECTION_POLICY_VERSION = "published_resource_selection_policy_v1"

RESOURCE_VIEW_CONTRACT_FIELDS = {
    "segment_scores": {
        "public_segments": "public_contract_version",
        "analyst_segments": "analyst_contract_version",
    },
    "segment_score_tiles": {
        "public_tiles": "public_contract_version",
    },
}


def _record_sort_key(record: dict[str, Any]) -> tuple[datetime, str]:
    return (
        datetime.fromisoformat(record["document_mtime_utc"]),
        record["manifest_path"],
    )


def _selection_policy() -> dict[str, Any]:
    return {
        "published_resource_selection_policy_version": PUBLISHED_RESOURCE_SELECTION_POLICY_VERSION,
        "latest_sort_order": [
            "document_mtime_utc ascending, newest wins",
            "manifest_path ascending as deterministic tiebreaker",
        ],
        "stale_rule": (
            "A record is stale for a lookup scope when another record with the same selection keys "
            "wins the latest sort order."
        ),
        "lookup_scopes": [
            "resource_name",
            "resource_name + prediction_run_label",
            "resource_name + prediction_run_label + occurred_year",
            "resource_name + prediction_run_label + occurred_year + tile_size_m",
        ],
    }


def _to_catalog_record(entry: dict[str, Any], *, root_dir: Path) -> dict[str, Any] | None:
    summary = entry.get("summary", {})
    resource_name = summary.get("resource_name")
    if resource_name not in RESOURCE_ALLOWED_VIEWS:
        return None

    stats = summary.get("stats", {})
    output_map = _entry_output_map(entry)
    view_details: dict[str, dict[str, Any]] = {}
    for view in RESOURCE_ALLOWED_VIEWS[resource_name]:
        output_field = RESOURCE_VIEW_OUTPUT_FIELDS[resource_name][view]
        path = output_map.get(output_field)
        if path is None:
            continue
        contract_field = RESOURCE_VIEW_CONTRACT_FIELDS[resource_name][view]
        view_details[view] = {
            "path": path,
            "contract_version": summary.get(contract_field),
        }
    if not view_details:
        return None

    return {
        "resource_name": resource_name,
        "artifact_kind": entry.get("artifact_kind"),
        "run_label": entry.get("run_label"),
        "prediction_run_label": stats.get("prediction_run_label") or entry.get("run_label"),
        "prediction_task": stats.get("prediction_task"),
        "occurred_years": list(stats.get("holdout_years") or []),
        "tile_size_m": stats.get("tile_size_m"),
        "document_mtime_utc": entry.get("document_mtime_utc"),
        "manifest_path": entry.get("document_path"),
        "contract_versions": {
            "public_contract_version": summary.get("public_contract_version"),
            "analyst_contract_version": summary.get("analyst_contract_version"),
            "lineage_contract_version": summary.get("lineage_contract_version"),
        },
        "lineage_trace": resolve_published_lineage_trace(
            str(entry.get("document_path")),
            root_dir=root_dir,
        ),
        "views": view_details,
        "stats": stats,
    }


def _prefer_newer(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None or _record_sort_key(candidate) > _record_sort_key(current):
        return candidate
    return current


def _index_contract() -> dict[str, Any]:
    return {
        "resource_name": "published_resource_index",
        "public_contract_version": PUBLISHED_RESOURCE_INDEX_CONTRACT_VERSION,
        "published_resource_index_version": PUBLISHED_RESOURCE_INDEX_VERSION,
        "published_resource_selection_policy_version": PUBLISHED_RESOURCE_SELECTION_POLICY_VERSION,
        "supported_resource_names": sorted(RESOURCE_ALLOWED_VIEWS),
        "latest_lookup_keys": [
            "resource_name",
            "prediction_run_label",
            "occurred_year",
            "tile_size_m",
        ],
        "record_shape": {
            "resource_name": "segment_scores | segment_score_tiles",
            "prediction_run_label": "source model run label",
            "occurred_years": "holdout years exposed by the published artifact",
            "tile_size_m": "tile size for tile resources, otherwise null",
            "views": "view-name to concrete path and contract version",
            "selection": "freshness flags for the supported latest lookup scopes",
            "lineage_trace": "stable path back to the source metrics and training configuration when present",
        },
    }


def _same_record(left: dict[str, Any] | None, right: dict[str, Any]) -> bool:
    if left is None:
        return False
    return (
        left.get("manifest_path") == right.get("manifest_path")
        and left.get("document_mtime_utc") == right.get("document_mtime_utc")
    )


def _selection_metadata(
    record: dict[str, Any],
    *,
    latest_by_resource: dict[str, dict[str, Any]],
    latest_by_resource_run: dict[str, dict[str, dict[str, Any]]],
    latest_by_resource_run_year: dict[str, dict[str, dict[str, dict[str, Any]]]],
    latest_by_resource_run_year_tile: dict[str, dict[str, dict[str, dict[str, dict[str, Any]]]]],
) -> dict[str, Any]:
    resource_name = str(record["resource_name"])
    prediction_run_label = str(record["prediction_run_label"])
    occurred_years = [str(int(year)) for year in record.get("occurred_years", [])]
    tile_size_m = record.get("tile_size_m")
    tile_key = str(float(tile_size_m)) if tile_size_m is not None else None

    latest_year_scopes = [
        year
        for year in occurred_years
        if _same_record(
            latest_by_resource_run_year.get(resource_name, {})
            .get(prediction_run_label, {})
            .get(year),
            record,
        )
    ]
    latest_year_tile_scopes: list[dict[str, str]] = []
    if tile_key is not None:
        for year in occurred_years:
            if _same_record(
                latest_by_resource_run_year_tile.get(resource_name, {})
                .get(prediction_run_label, {})
                .get(year, {})
                .get(tile_key),
                record,
            ):
                latest_year_tile_scopes.append(
                    {
                        "occurred_year": year,
                        "tile_size_m": tile_key,
                    }
                )

    is_latest_for_resource = _same_record(latest_by_resource.get(resource_name), record)
    is_latest_for_prediction_run = _same_record(
        latest_by_resource_run.get(resource_name, {}).get(prediction_run_label),
        record,
    )
    return {
        "published_resource_selection_policy_version": PUBLISHED_RESOURCE_SELECTION_POLICY_VERSION,
        "is_latest_for_resource": is_latest_for_resource,
        "is_latest_for_prediction_run": is_latest_for_prediction_run,
        "latest_prediction_run_years": latest_year_scopes,
        "latest_prediction_run_year_tiles": latest_year_tile_scopes,
        "is_stale_for_resource": not is_latest_for_resource,
        "is_stale_for_prediction_run": not is_latest_for_prediction_run,
        "is_stale_in_any_lookup_scope": (
            (not is_latest_for_resource)
            or (not is_latest_for_prediction_run)
            or (bool(occurred_years) and len(latest_year_scopes) != len(occurred_years))
            or (tile_key is not None and len(latest_year_tile_scopes) != len(occurred_years))
        ),
    }


def build_published_resource_index(
    *,
    registry_path: str | Path = "data/registry/run_registry.jsonl",
    output_dir: str | Path = "data/published_index",
) -> dict[str, Any]:
    registry_input = Path(registry_path)
    root_dir = infer_artifact_root(registry_input)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    index_path = output_root / "published_resources.json"
    manifest_path = output_root / "published_resources.manifest.json"

    registry_entries = _load_registry_entries(registry_input)
    serving_entries = [entry for entry in registry_entries if entry.get("stage") == "serving"]
    catalog_records = [
        record
        for entry in serving_entries
        if (record := _to_catalog_record(entry, root_dir=root_dir)) is not None
    ]
    catalog_records.sort(
        key=lambda item: (
            item["resource_name"],
            item["prediction_run_label"] or "",
            item["document_mtime_utc"],
            item["manifest_path"],
        )
    )

    latest_by_resource: dict[str, dict[str, Any]] = {}
    latest_by_resource_run: dict[str, dict[str, dict[str, Any]]] = {}
    latest_by_resource_run_year: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    latest_by_resource_run_year_tile: dict[str, dict[str, dict[str, dict[str, dict[str, Any]]]]] = {}

    for record in catalog_records:
        resource_name = record["resource_name"]
        prediction_run_label = str(record["prediction_run_label"])
        latest_by_resource[resource_name] = _prefer_newer(
            latest_by_resource.get(resource_name),
            record,
        )

        resource_runs = latest_by_resource_run.setdefault(resource_name, {})
        resource_runs[prediction_run_label] = _prefer_newer(
            resource_runs.get(prediction_run_label),
            record,
        )

        for occurred_year in record["occurred_years"]:
            year_key = str(int(occurred_year))
            resource_years = latest_by_resource_run_year.setdefault(resource_name, {}).setdefault(
                prediction_run_label,
                {},
            )
            resource_years[year_key] = _prefer_newer(resource_years.get(year_key), record)

            tile_size_m = record.get("tile_size_m")
            if tile_size_m is not None:
                tile_key = str(float(tile_size_m))
                year_tiles = latest_by_resource_run_year_tile.setdefault(resource_name, {}).setdefault(
                    prediction_run_label,
                    {},
                ).setdefault(year_key, {})
                year_tiles[tile_key] = _prefer_newer(year_tiles.get(tile_key), record)

    for record in catalog_records:
        record["selection"] = _selection_metadata(
            record,
            latest_by_resource=latest_by_resource,
            latest_by_resource_run=latest_by_resource_run,
            latest_by_resource_run_year=latest_by_resource_run_year,
            latest_by_resource_run_year_tile=latest_by_resource_run_year_tile,
        )

    stats = {
        "registry_entries_scanned": len(registry_entries),
        "serving_entries_scanned": len(serving_entries),
        "catalog_record_count": len(catalog_records),
        "resource_count": len(latest_by_resource),
        "prediction_run_label_count": len(
            {
                record["prediction_run_label"]
                for record in catalog_records
                if record.get("prediction_run_label")
            }
        ),
        "records_by_resource_name": dict(
            sorted(Counter(record["resource_name"] for record in catalog_records).items())
        ),
        "latest_by_resource_count": len(latest_by_resource),
        "stale_catalog_record_count": len(
            [record for record in catalog_records if record["selection"]["is_stale_in_any_lookup_scope"]]
        ),
    }

    index_payload = {
        "published_resource_index_version": PUBLISHED_RESOURCE_INDEX_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "registry_path": str(registry_input),
        "supported_resource_names": sorted(RESOURCE_ALLOWED_VIEWS),
        "selection_policy": _selection_policy(),
        "stats": stats,
        "latest_by_resource": latest_by_resource,
        "latest_by_resource_prediction_run": latest_by_resource_run,
        "latest_by_resource_prediction_run_year": latest_by_resource_run_year,
        "latest_by_resource_prediction_run_year_tile": latest_by_resource_run_year_tile,
        "catalog": catalog_records,
    }
    index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

    contract = _index_contract()
    manifest = {
        "published_resource_index_version": PUBLISHED_RESOURCE_INDEX_VERSION,
        "inputs": {
            "registry_path": str(registry_input),
            "registry_sha256": _sha256(registry_input),
        },
        "outputs": {
            "index_json_path": str(index_path),
            "index_json_sha256": _sha256(index_path),
            "manifest_path": str(manifest_path),
        },
        "contract": contract,
        "stats": stats,
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "run_registry_jsonl",
                    registry_input,
                    _sha256(registry_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "published_resource_index_json",
                    index_path,
                    _sha256(index_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "published_resource_index_version": PUBLISHED_RESOURCE_INDEX_VERSION,
        "contract": {
            "public_contract_version": contract["public_contract_version"],
        },
        "stats": stats,
    }
