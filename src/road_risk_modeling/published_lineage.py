"""Resolve stable lineage traces for published and reporting artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PUBLISHED_LINEAGE_TRACE_VERSION = "published_lineage_trace_v1"


def infer_artifact_root(anchor_path: str | Path) -> Path:
    anchor = Path(anchor_path)
    search_start = anchor if anchor.is_dir() else anchor.parent
    for candidate in [search_start, *search_start.parents]:
        if (candidate / "data").exists():
            return candidate
    return search_start


def _resolve_path(path_value: str | Path, *, root_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root_dir / path


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _normalize_lineage_refs(payload: dict[str, Any], field_name: str) -> list[dict[str, str]]:
    lineage = payload.get("lineage", {})
    if not isinstance(lineage, dict):
        return []
    values = lineage.get(field_name, [])
    if not isinstance(values, list):
        return []
    refs: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        path = value.get("path")
        role = value.get("role")
        if not isinstance(path, str) or not path.strip():
            continue
        refs.append(
            {
                "role": str(role) if isinstance(role, str) and role else "artifact",
                "path": path,
                **({"sha256": value["sha256"]} if isinstance(value.get("sha256"), str) else {}),
            }
        )
    return refs


def _run_record_path(payload: dict[str, Any]) -> str | None:
    lineage = payload.get("lineage", {})
    if not isinstance(lineage, dict):
        return None
    run_record = lineage.get("run_record", {})
    if not isinstance(run_record, dict):
        return None
    path = run_record.get("path")
    if isinstance(path, str) and path.strip():
        return path
    return None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def resolve_published_lineage_trace(
    manifest_path: str | Path,
    *,
    root_dir: str | Path | None = None,
    max_depth: int = 4,
) -> dict[str, Any]:
    root_path = Path(root_dir) if root_dir is not None else infer_artifact_root(manifest_path)
    manifest_input = str(manifest_path)
    resolved_manifest_path = _resolve_path(manifest_path, root_dir=root_path)
    manifest_payload = _load_json(resolved_manifest_path)

    trace: dict[str, Any] = {
        "published_lineage_trace_version": PUBLISHED_LINEAGE_TRACE_VERSION,
        "manifest_path": manifest_input,
        "manifest_exists": manifest_payload is not None,
        "trace_status": "manifest_missing",
        "lineage_contract_version": None,
        "run_record_path": None,
        "direct_upstream_inputs": [],
        "direct_supporting_outputs": [],
        "direct_publishable_outputs": [],
        "upstream_manifest_paths": [],
        "upstream_metric_paths": [],
        "upstream_run_record_paths": [],
        "source_metrics_path": None,
        "source_training_config": None,
    }
    if manifest_payload is None:
        return trace

    lineage = manifest_payload.get("lineage", {})
    trace["lineage_contract_version"] = (
        lineage.get("lineage_contract_version") if isinstance(lineage, dict) else None
    )
    trace["run_record_path"] = _run_record_path(manifest_payload)
    trace["direct_upstream_inputs"] = _normalize_lineage_refs(manifest_payload, "upstream_inputs")
    trace["direct_supporting_outputs"] = _normalize_lineage_refs(manifest_payload, "supporting_outputs")
    trace["direct_publishable_outputs"] = _normalize_lineage_refs(manifest_payload, "publishable_outputs")

    if isinstance(manifest_payload.get("training_config"), dict):
        trace["source_metrics_path"] = manifest_input
        trace["source_training_config"] = manifest_payload["training_config"]

    seen_paths: set[str] = set()
    queue: list[tuple[dict[str, str], int]] = [
        (reference, 1) for reference in trace["direct_upstream_inputs"]
    ]
    upstream_manifest_paths: list[str] = []
    upstream_metric_paths: list[str] = []
    upstream_run_record_paths: list[str] = []
    while queue:
        reference, depth = queue.pop(0)
        path_value = reference["path"]
        if path_value in seen_paths:
            continue
        seen_paths.add(path_value)

        if path_value.endswith(".manifest.json"):
            upstream_manifest_paths.append(path_value)
        if path_value.endswith(".metrics.json"):
            upstream_metric_paths.append(path_value)

        payload = _load_json(_resolve_path(path_value, root_dir=root_path))
        if payload is None:
            continue

        run_record_path = _run_record_path(payload)
        if run_record_path:
            upstream_run_record_paths.append(run_record_path)
        if trace["source_training_config"] is None and isinstance(payload.get("training_config"), dict):
            trace["source_metrics_path"] = path_value
            trace["source_training_config"] = payload["training_config"]

        if depth >= max_depth:
            continue
        for child_reference in _normalize_lineage_refs(payload, "upstream_inputs"):
            if child_reference["path"] not in seen_paths:
                queue.append((child_reference, depth + 1))

    trace["upstream_manifest_paths"] = _dedupe(upstream_manifest_paths)
    trace["upstream_metric_paths"] = _dedupe(upstream_metric_paths)
    trace["upstream_run_record_paths"] = _dedupe(upstream_run_record_paths)
    if trace["source_training_config"] is not None:
        trace["trace_status"] = "resolved"
    elif trace["direct_upstream_inputs"]:
        trace["trace_status"] = "lineage_only"
    else:
        trace["trace_status"] = "no_lineage"
    return trace
