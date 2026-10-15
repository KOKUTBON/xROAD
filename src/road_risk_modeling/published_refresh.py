"""Refresh published outputs from the registry and lineage contracts."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .dashboard_summary import build_dashboard_summary
from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .published_index import build_published_resource_index
from .published_lineage import infer_artifact_root
from .published_resolver import _entry_output_map, _load_registry_entries
from .registry import build_run_registry


PUBLISHED_REFRESH_BUNDLE_VERSION = "published_refresh_bundle_v1"
PUBLISHED_REFRESH_CONTRACT_VERSION = "published_refresh_bundle_public_v1"
PUBLISHED_REFRESH_SCHEDULE_VERSION = "published_refresh_schedule_v1"
TRANSFERABILITY_REFRESH_SELECTION_VERSION = "transferability_refresh_selection_v1"
TRANSFERABILITY_MODES = (
    "cross_jurisdiction_temporal",
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry_sort_key(entry: dict[str, Any]) -> tuple[datetime, str]:
    return (
        datetime.fromisoformat(entry["document_mtime_utc"]),
        str(entry["document_path"]),
    )


def _transferability_dataset_count(entry: dict[str, Any]) -> int:
    summary = entry.get("summary", {})
    labels = summary.get("dataset_labels", [])
    if not isinstance(labels, list):
        return 0
    return len([label for label in labels if label])


def _transferability_mode_sort_key(entry: dict[str, Any]) -> tuple[int, datetime, str]:
    return (
        _transferability_dataset_count(entry),
        datetime.fromisoformat(entry["document_mtime_utc"]),
        str(entry["document_path"]),
    )


def _transferability_selection_policy() -> dict[str, Any]:
    return {
        "transferability_refresh_selection_version": TRANSFERABILITY_REFRESH_SELECTION_VERSION,
        "preferred_source": "latest benchmark bundle with a recommended budget for the largest stack",
        "fallback_source": (
            "latest evaluation metrics per mode, sorted by dataset_count, then document_mtime_utc, "
            "then document_path"
        ),
        "stale_rule": (
            "A transferability input is stale when a newer benchmark recommendation or a higher-priority "
            "mode candidate exists for the same automated reporting scope."
        ),
    }


def _schedule_template(
    *,
    data_root: Path,
    registry_output_dir: Path,
    published_index_output_dir: Path,
    dashboard_output_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "published_refresh_schedule_version": PUBLISHED_REFRESH_SCHEDULE_VERSION,
        "recommended_cadence": "weekly and after any new published serving artifact or transferability benchmark",
        "command": (
            "PYTHONPATH=src python3 -m road_risk_modeling build-published-refresh-bundle "
            f"--data-root {data_root} "
            f"--registry-output-dir {registry_output_dir} "
            f"--published-index-output-dir {published_index_output_dir} "
            f"--dashboard-output-dir {dashboard_output_dir} "
            f"--output-dir {output_dir}"
        ),
        "outputs": {
            "registry": str(registry_output_dir / "run_registry.jsonl"),
            "published_index": str(published_index_output_dir / "published_resources.json"),
            "dashboard_summary": str(dashboard_output_dir / "dashboard_summary.json"),
            "refresh_bundle": str(output_dir / "published_refresh_bundle.json"),
        },
    }


def _select_benchmark_transferability_inputs(
    entries: list[dict[str, Any]],
    *,
    root_dir: Path,
) -> dict[str, Any] | None:
    benchmark_entries = [
        entry
        for entry in entries
        if entry.get("artifact_kind") == "transferability_benchmark"
    ]
    if not benchmark_entries:
        return None

    selected_entry = max(benchmark_entries, key=_entry_sort_key)
    output_map = _entry_output_map(selected_entry)
    report_json_path = output_map.get("outputs.report_json_path")
    if report_json_path is None:
        return None
    resolved_report_path = Path(report_json_path)
    if not resolved_report_path.is_absolute():
        resolved_report_path = root_dir / resolved_report_path
    if not resolved_report_path.exists():
        return None

    payload = _load_json(resolved_report_path)
    budget_profiles = payload.get("budget_profiles", [])
    if not isinstance(budget_profiles, list) or not budget_profiles:
        return None
    featured_profile = max(
        budget_profiles,
        key=lambda profile: (
            len(profile.get("dataset_labels") or []),
            int(profile.get("recommended_budget") or 0),
            str(profile.get("stack_display_name") or ""),
        ),
    )
    recommended_run = next(
        (
            run
            for run in payload.get("runs", [])
            if run.get("stack_key") == featured_profile.get("stack_key")
            and int(run.get("random_forest_n_estimators") or 0)
            == int(featured_profile.get("recommended_budget") or 0)
        ),
        None,
    )
    if recommended_run is None:
        return None
    metrics_paths = [
        str(path)
        for path in (recommended_run.get("metrics_paths") or [])
        if isinstance(path, str) and path
    ]
    if not metrics_paths:
        metrics_path = recommended_run.get("metrics_path")
        if isinstance(metrics_path, str) and metrics_path:
            metrics_paths = [metrics_path]
    if not metrics_paths:
        return None

    return {
        "selection_source": "latest_transferability_benchmark",
        "selection_policy": _transferability_selection_policy(),
        "benchmark_label": payload.get("benchmark_label"),
        "benchmark_manifest_path": selected_entry.get("document_path"),
        "benchmark_report_json_path": report_json_path,
        "selected_stack_key": recommended_run.get("stack_key"),
        "selected_stack_display_name": recommended_run.get("stack_display_name"),
        "selected_dataset_count": recommended_run.get("dataset_count"),
        "selected_random_forest_n_estimators": recommended_run.get("random_forest_n_estimators"),
        "selected_modes": recommended_run.get("requested_modes", []),
        "metrics_paths": metrics_paths,
    }


def _select_fallback_transferability_inputs(entries: list[dict[str, Any]]) -> dict[str, Any]:
    selected_metrics_paths: list[str] = []
    seen_paths: set[str] = set()
    mode_selections: list[dict[str, Any]] = []
    for mode in TRANSFERABILITY_MODES:
        candidates = [
            entry
            for entry in entries
            if entry.get("artifact_kind") == "transferability"
            and mode in (entry.get("summary", {}).get("requested_modes") or [])
            and (entry.get("summary", {}).get("mode_summaries", {}).get(mode) or {})
        ]
        if not candidates:
            continue
        selected_entry = max(candidates, key=_transferability_mode_sort_key)
        document_path = str(selected_entry.get("document_path"))
        if document_path not in seen_paths:
            selected_metrics_paths.append(document_path)
            seen_paths.add(document_path)
        mode_selections.append(
            {
                "mode": mode,
                "metrics_path": document_path,
                "dataset_count": _transferability_dataset_count(selected_entry),
                "random_forest_n_estimators": selected_entry.get("summary", {}).get(
                    "random_forest_n_estimators"
                ),
                "document_mtime_utc": selected_entry.get("document_mtime_utc"),
            }
        )

    return {
        "selection_source": "registry_mode_fallback",
        "selection_policy": _transferability_selection_policy(),
        "metrics_paths": selected_metrics_paths,
        "mode_selections": mode_selections,
    }


def _latest_serving_summary(published_index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    latest_by_resource = published_index_payload.get("latest_by_resource", {})
    records: list[dict[str, Any]] = []
    for resource_name, record in sorted(latest_by_resource.items()):
        records.append(
            {
                "resource_name": resource_name,
                "prediction_run_label": record.get("prediction_run_label"),
                "manifest_path": record.get("manifest_path"),
                "document_mtime_utc": record.get("document_mtime_utc"),
                "selection": record.get("selection", {}),
                "lineage_trace": record.get("lineage_trace"),
            }
        )
    return records


def _resolve_artifact_paths(paths: list[str], *, root_dir: Path) -> list[str]:
    resolved_paths: list[str] = []
    for path in paths:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root_dir / candidate
        resolved_paths.append(str(candidate))
    return resolved_paths


def _build_markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Published Refresh Bundle",
        "",
        "## Steps",
        "",
        f"- initial registry snapshot: `{payload['refresh_steps']['initial_registry_manifest_path']}`",
        f"- published index refresh: `{payload['refresh_steps']['published_index_manifest_path']}`",
        f"- dashboard summary refresh: `{payload['refresh_steps']['dashboard_summary_manifest_path']}`",
        f"- final registry snapshot: `{payload['refresh_steps']['final_registry_manifest_path']}`",
        "",
        "## Transferability Selection",
        "",
        f"- source: `{payload['transferability_selection']['selection_source']}`",
    ]
    benchmark_label = payload["transferability_selection"].get("benchmark_label")
    if benchmark_label:
        lines.append(f"- benchmark: `{benchmark_label}`")
    selected_stack = payload["transferability_selection"].get("selected_stack_display_name")
    if selected_stack:
        lines.append(f"- selected stack: `{selected_stack}`")
    selected_budget = payload["transferability_selection"].get("selected_random_forest_n_estimators")
    if selected_budget is not None:
        lines.append(f"- selected budget: `rf{selected_budget}`")
    lines.append(
        f"- metrics inputs: `{len(payload['transferability_selection'].get('metrics_paths', []))}`"
    )
    lines.extend(
        [
            "",
            "## Published Outputs",
            "",
            f"- latest serving resources tracked: `{len(payload['latest_published_resources'])}`",
            f"- published run count in dashboard summary: `{payload['dashboard_summary_stats'].get('published_run_count')}`",
            f"- lineage-traced dashboard runs: `{payload['dashboard_summary_stats'].get('lineage_traced_run_count')}`",
            "",
            "## Refresh Schedule",
            "",
            f"- cadence: `{payload['schedule_template']['recommended_cadence']}`",
            f"- command: `{payload['schedule_template']['command']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_published_refresh_bundle(
    *,
    data_root: str | Path = "data",
    registry_output_dir: str | Path = "data/registry",
    published_index_output_dir: str | Path = "data/published_index",
    dashboard_output_dir: str | Path = "data/dashboard",
    output_dir: str | Path = "data/reporting/published_refresh/latest",
) -> dict[str, Any]:
    data_path = Path(data_root)
    registry_output_path = Path(registry_output_dir)
    published_index_output_path = Path(published_index_output_dir)
    dashboard_output_path = Path(dashboard_output_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    bundle_json_path = output_root / "published_refresh_bundle.json"
    bundle_md_path = output_root / "published_refresh_bundle.md"
    schedule_path = output_root / "published_refresh_schedule.json"
    manifest_path = output_root / "published_refresh_bundle.manifest.json"

    initial_registry_manifest = build_run_registry(
        data_root=data_path,
        output_dir=registry_output_path,
    )
    initial_registry_path = registry_output_path / "run_registry.jsonl"
    initial_entries = _load_registry_entries(initial_registry_path)
    artifact_root = infer_artifact_root(initial_registry_path)

    published_index_manifest = build_published_resource_index(
        registry_path=initial_registry_path,
        output_dir=published_index_output_path,
    )
    published_index_path = published_index_output_path / "published_resources.json"

    transferability_selection = _select_benchmark_transferability_inputs(
        initial_entries,
        root_dir=artifact_root,
    )
    if transferability_selection is None:
        transferability_selection = _select_fallback_transferability_inputs(initial_entries)
    resolved_transferability_paths = _resolve_artifact_paths(
        [
            str(path)
            for path in transferability_selection.get("metrics_paths", [])
            if isinstance(path, str) and path
        ],
        root_dir=artifact_root,
    )

    dashboard_summary_manifest = build_dashboard_summary(
        published_index_path=published_index_path,
        transferability_metrics_paths=resolved_transferability_paths,
        output_dir=dashboard_output_path,
    )
    dashboard_summary_path = dashboard_output_path / "dashboard_summary.json"

    final_registry_manifest = build_run_registry(
        data_root=data_path,
        output_dir=registry_output_path,
    )
    final_registry_path = registry_output_path / "run_registry.jsonl"

    published_index_payload = _load_json(published_index_path)
    dashboard_summary_payload = _load_json(dashboard_summary_path)
    schedule_template = _schedule_template(
        data_root=data_path,
        registry_output_dir=registry_output_path,
        published_index_output_dir=published_index_output_path,
        dashboard_output_dir=dashboard_output_path,
        output_dir=output_root,
    )

    bundle_payload = {
        "published_refresh_bundle_version": PUBLISHED_REFRESH_BUNDLE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "refresh_steps": {
            "initial_registry_manifest_path": initial_registry_manifest["outputs"]["manifest_path"],
            "published_index_manifest_path": published_index_manifest["manifest_path"],
            "dashboard_summary_manifest_path": dashboard_summary_manifest["manifest_path"],
            "final_registry_manifest_path": final_registry_manifest["outputs"]["manifest_path"],
        },
        "transferability_selection": transferability_selection,
        "published_resource_selection_policy": published_index_payload.get("selection_policy"),
        "latest_published_resources": _latest_serving_summary(published_index_payload),
        "published_index_stats": published_index_payload.get("stats", {}),
        "dashboard_summary_stats": dashboard_summary_payload.get("stats", {}),
        "schedule_template": schedule_template,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_build_markdown_report(bundle_payload), encoding="utf-8")
    schedule_path.write_text(json.dumps(schedule_template, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "published_refresh_bundle_version": PUBLISHED_REFRESH_BUNDLE_VERSION,
        "inputs": {
            "data_root": str(data_path),
            "final_registry_path": str(final_registry_path),
            "final_registry_sha256": _sha256(final_registry_path),
            "published_index_path": str(published_index_path),
            "published_index_sha256": _sha256(published_index_path),
            "dashboard_summary_path": str(dashboard_summary_path),
            "dashboard_summary_sha256": _sha256(dashboard_summary_path),
        },
        "outputs": {
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "schedule_json_path": str(schedule_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "published_refresh_bundle",
            "public_contract_version": PUBLISHED_REFRESH_CONTRACT_VERSION,
            "published_refresh_bundle_version": PUBLISHED_REFRESH_BUNDLE_VERSION,
        },
        "stats": {
            "latest_published_resource_count": len(bundle_payload["latest_published_resources"]),
            "selected_transferability_input_count": len(
                bundle_payload["transferability_selection"].get("metrics_paths", [])
            ),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("run_registry_jsonl", final_registry_path, _sha256(final_registry_path)),
                _artifact_reference(
                    "published_resource_index_json",
                    published_index_path,
                    _sha256(published_index_path),
                ),
                _artifact_reference(
                    "dashboard_summary_json",
                    dashboard_summary_path,
                    _sha256(dashboard_summary_path),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "published_refresh_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "published_refresh_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "published_refresh_schedule_json",
                    schedule_path,
                    _sha256(schedule_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "published_refresh_bundle_version": PUBLISHED_REFRESH_BUNDLE_VERSION,
        "contract": {
            "public_contract_version": PUBLISHED_REFRESH_CONTRACT_VERSION,
        },
        "stats": manifest["stats"],
    }
