"""Run registry utilities for reproducibility and artifact tracing."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


REGISTRY_VERSION = "run_registry_v1"

DOCUMENT_SUFFIXES = ("*.manifest.json", "*.metrics.json")

ARTIFACT_KIND_BY_NAME = {
    "bari_open_data_canonical.manifest.json": "bari_open_data_ingestion",
    "bari_open_data_canonical.curated.manifest.json": "canonical_curation",
    "boundary.manifest.json": "boundary",
    "dashboard_summary.manifest.json": "dashboard_summary",
    "connector_observations.manifest.json": "exposure_connector_observations",
    "connector_intake_pack.manifest.json": "exposure_connector_intake_pack",
    "exposure_onboarding_plan.manifest.json": "exposure_onboarding_plan",
    "exposure_readiness.manifest.json": "exposure_readiness",
    "exposure_source_catalog.manifest.json": "exposure_source_catalog",
    "frequency_baseline.metrics.json": "frequency_model",
    "frequency_transferability.metrics.json": "transferability",
    "transferability_benchmark.manifest.json": "transferability_benchmark",
    "intervention_brief.manifest.json": "intervention_brief",
    "scenario_bundle.manifest.json": "scenario_countermeasure_bundle",
    "vru_exposure_bundle.manifest.json": "vru_exposure_bundle",
    "vru_intelligence_bundle.manifest.json": "vru_intelligence_bundle",
    "istat_codebooks.manifest.json": "jurisdiction_codebooks",
    "jurisdiction_subset.manifest.json": "jurisdiction_subset",
    "matched_records.manifest.json": "matching",
    "matched_node_records.manifest.json": "node_matching",
    "movement_review_pack.manifest.json": "movement_review_pack",
    "puglia_cleaned_canonical.curated.manifest.json": "canonical_curation",
    "puglia_cleaned_canonical.manifest.json": "canonical_ingestion",
    "published_resources.manifest.json": "published_resource_index",
    "published_refresh_bundle.manifest.json": "published_refresh_bundle",
    "signal_phase_intake_pack.manifest.json": "signal_phase_intake_pack",
    "signal_phase_acquisition_plan.manifest.json": "signal_phase_acquisition_plan",
    "signal_phase_coverage.manifest.json": "signal_phase_coverage_report",
    "signal_phase_contact_bundle.manifest.json": "signal_phase_contact_bundle",
    "signal_phase_contact_resolution_bundle.manifest.json": "signal_phase_contact_resolution_bundle",
    "signal_phase_dispatch_bundle.manifest.json": "signal_phase_dispatch_bundle",
    "signal_phase_delivery_intake_bundle.manifest.json": "signal_phase_delivery_intake_bundle",
    "signal_phase_delivery_monitor_bundle.manifest.json": "signal_phase_delivery_monitor_bundle",
    "signal_phase_delivery_validation.manifest.json": "signal_phase_delivery_validation",
    "signal_phase_validation_batch.manifest.json": "signal_phase_validation_batch",
    "signal_phase_receive_cycle.manifest.json": "signal_phase_receive_cycle",
    "signal_phase_lifecycle_report.manifest.json": "signal_phase_lifecycle_report",
    "signal_phase_follow_up_bundle.manifest.json": "signal_phase_follow_up_bundle",
    "signal_phase_follow_up_cycle.manifest.json": "signal_phase_follow_up_cycle",
    "signal_phase_follow_up_execution_bundle.manifest.json": "signal_phase_follow_up_execution_bundle",
    "signal_phase_operations_cycle.manifest.json": "signal_phase_operations_cycle",
    "signal_phase_action_queue.manifest.json": "signal_phase_action_queue",
    "signal_phase_action_execution_bundle.manifest.json": "signal_phase_action_execution_bundle",
    "signal_phase_action_handoff_bundle.manifest.json": "signal_phase_action_handoff_bundle",
    "signal_phase_operator_board_bundle.manifest.json": "signal_phase_operator_board_bundle",
    "signal_phase_dispatch_execution_bundle.manifest.json": "signal_phase_dispatch_execution_bundle",
    "signal_phase_dispatch_recording_bundle.manifest.json": "signal_phase_dispatch_recording_bundle",
    "signal_phase_dispatch_repair_bundle.manifest.json": "signal_phase_dispatch_repair_bundle",
    "signal_phase_dispatch_repair_execution_bundle.manifest.json": "signal_phase_dispatch_repair_execution_bundle",
    "signal_phase_dispatch_repair_recording_bundle.manifest.json": "signal_phase_dispatch_repair_recording_bundle",
    "signal_phase_dispatch_repair_status_bundle.manifest.json": "signal_phase_dispatch_repair_status_bundle",
    "signal_phase_dispatch_validation_bundle.manifest.json": "signal_phase_dispatch_validation_bundle",
    "signal_phase_dispatch_writeback_bundle.manifest.json": "signal_phase_dispatch_writeback_bundle",
    "signal_phase_dispatch_cycle.manifest.json": "signal_phase_dispatch_cycle",
    "signal_phase_runtime_cycle.manifest.json": "signal_phase_runtime_cycle",
    "signal_phase_runtime_rehearsal.manifest.json": "signal_phase_runtime_rehearsal",
    "signal_phase_follow_up_writeback_bundle.manifest.json": "signal_phase_follow_up_writeback_bundle",
    "signal_phase_status_sync_bundle.manifest.json": "signal_phase_status_sync_bundle",
    "signal_phase_delivery_session.manifest.json": "signal_phase_delivery_session",
    "signal_phase_outreach_bundle.manifest.json": "signal_phase_outreach_bundle",
    "signal_phase_request_scope_bundle.manifest.json": "signal_phase_request_scope_bundle",
    "signal_phase_target_bundle.manifest.json": "signal_phase_target_bundle",
    "signal_phase_request_pack.manifest.json": "signal_phase_request_pack",
    "signal_phase_support_resolution_bundle.manifest.json": "signal_phase_support_resolution_bundle",
    "signal_phase_support_writeback_bundle.manifest.json": "signal_phase_support_writeback_bundle",
    "signal_phase_support_status_bundle.manifest.json": "signal_phase_support_status_bundle",
    "signal_phase_support_action_queue.manifest.json": "signal_phase_support_action_queue",
    "signal_phase_support_apply_status_bundle.manifest.json": "signal_phase_support_apply_status_bundle",
    "signal_phase_support_request_state_bundle.manifest.json": "signal_phase_support_request_state_bundle",
    "signal_phase_support_operator_board_bundle.manifest.json": "signal_phase_support_operator_board_bundle",
    "signal_phase_support_action_execution_bundle.manifest.json": "signal_phase_support_action_execution_bundle",
    "signal_phase_support_action_handoff_bundle.manifest.json": "signal_phase_support_action_handoff_bundle",
    "signal_phase_support_runtime_board_bundle.manifest.json": "signal_phase_support_runtime_board_bundle",
    "signal_phase_support_runtime_action_queue.manifest.json": "signal_phase_support_runtime_action_queue",
    "signal_phase_support_runtime_action_execution_bundle.manifest.json": "signal_phase_support_runtime_action_execution_bundle",
    "signal_phase_support_workbook_completion_bundle.manifest.json": "signal_phase_support_workbook_completion_bundle",
    "signal_phase_support_validation_batch.manifest.json": "signal_phase_support_validation_batch",
    "signal_phase_support_apply_cycle.manifest.json": "signal_phase_support_apply_cycle",
    "signal_phase_support_rehearsal.manifest.json": "signal_phase_support_rehearsal",
    "signal_phase_support_runtime_cycle.manifest.json": "signal_phase_support_runtime_cycle",
    "signal_phase_records.manifest.json": "signal_phase_records",
    "road_conflict_zones.manifest.json": "conflict_zone_layer",
    "road_movement_objects.manifest.json": "movement_object_layer",
    "road_movement_objects_signal_phase.manifest.json": "movement_signal_phase_layer",
    "road_segments.manifest.json": "segment_extraction",
    "road_node_objects.manifest.json": "node_object_layer",
    "road_segments_connector_observations.manifest.json": "segment_connector_observations",
    "road_segments_context.manifest.json": "segment_context",
    "road_segments_enriched.manifest.json": "segment_enrichment",
    "road_segments_exposure.manifest.json": "exposure_policy",
    "score_tiles.manifest.json": "public_score_tiles",
    "segment_scores.manifest.json": "prediction_store",
    "segment_year_metrics.manifest.json": "segment_aggregation",
    "severity_baseline.metrics.json": "severity_model",
    "node_year_metrics.manifest.json": "node_aggregation",
    "traffic_signal_nodes.manifest.json": "node_object_layer",
}

STAGE_BY_ARTIFACT_KIND = {
    "bari_open_data_ingestion": "ingestion",
    "boundary": "segmentation",
    "canonical_curation": "quality",
    "canonical_ingestion": "ingestion",
    "conflict_zone_layer": "object_modeling",
    "dashboard_summary": "serving",
    "exposure_connector_observations": "ingestion",
    "exposure_connector_intake_pack": "reporting",
    "exposure_onboarding_plan": "reporting",
    "exposure_readiness": "reporting",
    "exposure_source_catalog": "reporting",
    "exposure_policy": "enrichment",
    "frequency_model": "modeling",
    "intervention_brief": "reporting",
    "scenario_countermeasure_bundle": "reporting",
    "vru_exposure_bundle": "reporting",
    "vru_intelligence_bundle": "reporting",
    "jurisdiction_codebooks": "ingestion",
    "jurisdiction_subset": "ingestion",
    "matching": "matching",
    "movement_object_layer": "object_modeling",
    "movement_review_pack": "reporting",
    "node_aggregation": "aggregation",
    "node_matching": "matching",
    "node_object_layer": "object_modeling",
    "prediction_store": "serving",
    "published_resource_index": "serving",
    "published_refresh_bundle": "reporting",
    "public_score_tiles": "serving",
    "segment_connector_observations": "enrichment",
    "segment_aggregation": "aggregation",
    "segment_context": "enrichment",
    "segment_enrichment": "enrichment",
    "segment_extraction": "segmentation",
    "severity_model": "modeling",
    "signal_phase_records": "ingestion",
    "signal_phase_intake_pack": "reporting",
    "signal_phase_acquisition_plan": "reporting",
    "signal_phase_coverage_report": "reporting",
    "signal_phase_contact_bundle": "reporting",
    "signal_phase_contact_resolution_bundle": "reporting",
    "signal_phase_dispatch_bundle": "reporting",
    "signal_phase_delivery_intake_bundle": "reporting",
    "signal_phase_delivery_monitor_bundle": "reporting",
    "signal_phase_delivery_validation": "quality",
    "signal_phase_validation_batch": "quality",
    "signal_phase_receive_cycle": "quality",
    "signal_phase_lifecycle_report": "reporting",
    "signal_phase_follow_up_bundle": "reporting",
    "signal_phase_follow_up_cycle": "reporting",
    "signal_phase_follow_up_execution_bundle": "reporting",
    "signal_phase_operations_cycle": "reporting",
    "signal_phase_action_queue": "reporting",
    "signal_phase_action_execution_bundle": "reporting",
    "signal_phase_action_handoff_bundle": "reporting",
    "signal_phase_operator_board_bundle": "reporting",
    "signal_phase_dispatch_execution_bundle": "reporting",
    "signal_phase_dispatch_recording_bundle": "reporting",
    "signal_phase_dispatch_repair_bundle": "reporting",
    "signal_phase_dispatch_repair_execution_bundle": "reporting",
    "signal_phase_dispatch_repair_recording_bundle": "reporting",
    "signal_phase_dispatch_repair_status_bundle": "reporting",
    "signal_phase_dispatch_validation_bundle": "quality",
    "signal_phase_dispatch_writeback_bundle": "reporting",
    "signal_phase_dispatch_cycle": "reporting",
    "signal_phase_runtime_cycle": "reporting",
    "signal_phase_runtime_rehearsal": "reporting",
    "signal_phase_follow_up_writeback_bundle": "reporting",
    "signal_phase_status_sync_bundle": "reporting",
    "signal_phase_delivery_session": "enrichment",
    "signal_phase_outreach_bundle": "reporting",
    "signal_phase_request_scope_bundle": "reporting",
    "signal_phase_target_bundle": "reporting",
    "signal_phase_request_pack": "reporting",
    "signal_phase_support_resolution_bundle": "reporting",
    "signal_phase_support_writeback_bundle": "reporting",
    "signal_phase_support_status_bundle": "reporting",
    "signal_phase_support_action_queue": "reporting",
    "signal_phase_support_apply_status_bundle": "reporting",
    "signal_phase_support_request_state_bundle": "reporting",
    "signal_phase_support_operator_board_bundle": "reporting",
    "signal_phase_support_action_execution_bundle": "reporting",
    "signal_phase_support_action_handoff_bundle": "reporting",
    "signal_phase_support_runtime_board_bundle": "reporting",
    "signal_phase_support_runtime_action_queue": "reporting",
    "signal_phase_support_runtime_action_execution_bundle": "reporting",
    "signal_phase_support_workbook_completion_bundle": "reporting",
    "signal_phase_support_validation_batch": "quality",
    "signal_phase_support_apply_cycle": "quality",
    "signal_phase_support_rehearsal": "reporting",
    "signal_phase_support_runtime_cycle": "reporting",
    "movement_signal_phase_layer": "enrichment",
    "transferability": "evaluation",
    "transferability_benchmark": "reporting",
    "unknown": "unknown",
}

PRIMARY_OUTPUT_FIELDS = (
    "context_path",
    "enriched_path",
    "exposure_path",
    "geojson_path",
    "csv_path",
    "matched_path",
    "subset_path",
    "report_path",
    "report_json_path",
    "report_md_path",
    "review_path",
    "model_path",
    "predictions_path",
    "metrics_path",
    "boundary_path",
    "records_path",
    "index_json_path",
    "summary_json_path",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_registry_documents(data_root: Path) -> list[Path]:
    documents: list[Path] = []
    for pattern in DOCUMENT_SUFFIXES:
        documents.extend(data_root.rglob(pattern))
    return sorted({path for path in documents})


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _artifact_kind_for_document(document_path: Path) -> str:
    return ARTIFACT_KIND_BY_NAME.get(document_path.name, "unknown")


def _normalize_path_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if "/" in text or text.endswith((".json", ".jsonl", ".csv", ".geojson", ".joblib", ".html", ".zip")):
        return text
    return None


def _collect_path_refs(payload: Any, prefix: str = "") -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            refs.extend(_collect_path_refs(value, next_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            next_prefix = f"{prefix}[{index}]"
            refs.extend(_collect_path_refs(value, next_prefix))
    else:
        normalized = _normalize_path_value(payload)
        if normalized:
            refs.append({"field": prefix, "path": normalized})
    return refs


def _filter_refs_by_prefix(path_refs: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    return [ref for ref in path_refs if ref["field"].startswith(prefix)]


def _summary_for_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if "policy" in payload:
        summary["policy"] = payload["policy"]
    if "contract" in payload and isinstance(payload["contract"], dict):
        contract = payload["contract"]
        summary["resource_name"] = contract.get("resource_name")
        summary["public_contract_version"] = contract.get("public_contract_version")
        summary["analyst_contract_version"] = contract.get("analyst_contract_version")
    if "governance" in payload and isinstance(payload["governance"], dict):
        governance = payload["governance"]
        summary["governance_contract_version"] = governance.get("governance_contract_version")
        summary["governance_bundle_path"] = governance.get("governance_bundle_path")
        summary["governance_role_policy_ids"] = governance.get("role_policy_ids")
    if "stats" in payload:
        summary["stats"] = payload["stats"]
    summary.update(_lineage_summary(payload))
    return summary


def _training_config_summary(payload: dict[str, Any]) -> dict[str, Any]:
    training_config = payload.get("training_config", {})
    if not isinstance(training_config, dict):
        return {}
    return {
        "training_config_version": training_config.get("training_config_version"),
        "training_task": training_config.get("task"),
        "split_strategy": training_config.get("split_strategy"),
    }


def _lineage_summary(payload: dict[str, Any]) -> dict[str, Any]:
    lineage = payload.get("lineage", {})
    if not isinstance(lineage, dict):
        return {}
    return {
        "lineage_contract_version": lineage.get("lineage_contract_version"),
        "upstream_input_count": len(lineage.get("upstream_inputs", []) or []),
        "publishable_output_count": len(lineage.get("publishable_outputs", []) or []),
    }


def _summary_for_frequency_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    rf_metrics = payload.get("random_forest_poisson_metrics", {})
    summary = {
        "holdout_year": payload.get("holdout_year"),
        "train_rows": payload.get("train_rows"),
        "test_rows": payload.get("test_rows"),
        "train_crash_total": payload.get("train_crash_total"),
        "test_crash_total": payload.get("test_crash_total"),
        "random_forest_poisson_metrics": {
            "mean_poisson_deviance": rf_metrics.get("mean_poisson_deviance"),
            "rmse": rf_metrics.get("rmse"),
            "top_5pct_crash_share": rf_metrics.get("top_5pct_crash_share"),
        },
    }
    summary.update(_training_config_summary(payload))
    summary.update(_lineage_summary(payload))
    return summary


def _summary_for_severity_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    rf_metrics = payload.get("random_forest_classifier_metrics", {})
    summary = {
        "holdout_year": payload.get("holdout_year"),
        "train_rows": payload.get("train_rows"),
        "test_rows": payload.get("test_rows"),
        "train_fatal_count": payload.get("train_fatal_count"),
        "test_fatal_count": payload.get("test_fatal_count"),
        "random_forest_classifier_metrics": {
            "roc_auc": rf_metrics.get("roc_auc"),
            "average_precision": rf_metrics.get("average_precision"),
            "top_10pct_fatal_recall": rf_metrics.get("top_10pct_fatal_recall"),
            "top_20pct_fatal_recall": rf_metrics.get("top_20pct_fatal_recall"),
        },
    }
    summary.update(_training_config_summary(payload))
    summary.update(_lineage_summary(payload))
    return summary


def _transferability_mode_summary(mode_payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for label, metrics in sorted(mode_payload.items()):
        rf_metrics = metrics.get("random_forest_poisson_metrics", {})
        summary[label] = {
            "mean_poisson_deviance": rf_metrics.get("mean_poisson_deviance"),
            "top_5pct_crash_share": rf_metrics.get("top_5pct_crash_share"),
            "train_jurisdictions": metrics.get("train_jurisdictions"),
        }
    return summary


def _summary_for_transferability_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    modes = {
        "within_jurisdiction_temporal": _transferability_mode_summary(
            payload.get("within_jurisdiction_temporal", {})
        ),
        "cross_jurisdiction_temporal": _transferability_mode_summary(
            payload.get("cross_jurisdiction_temporal", {})
        ),
        "cross_jurisdiction_cold_start": _transferability_mode_summary(
            payload.get("cross_jurisdiction_cold_start", {})
        ),
        "cross_jurisdiction_history_free": _transferability_mode_summary(
            payload.get("cross_jurisdiction_history_free", {})
        ),
    }
    summary = {
        "holdout_year": payload.get("holdout_year"),
        "random_forest_n_estimators": payload.get("random_forest_n_estimators"),
        "requested_modes": payload.get("requested_modes", []),
        "dataset_labels": [item.get("label") for item in payload.get("dataset_inputs", [])],
        "mode_summaries": modes,
    }
    summary.update(_training_config_summary(payload))
    summary.update(_lineage_summary(payload))
    return summary


def _summary_for_document(artifact_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if artifact_kind == "frequency_model":
        return _summary_for_frequency_metrics(payload)
    if artifact_kind == "severity_model":
        return _summary_for_severity_metrics(payload)
    if artifact_kind == "transferability":
        return _summary_for_transferability_metrics(payload)
    return _summary_for_manifest(payload)


def _primary_output_path(payload: dict[str, Any], path_refs: list[dict[str, str]]) -> str | None:
    outputs = payload.get("outputs")
    if isinstance(outputs, dict):
        for field in PRIMARY_OUTPUT_FIELDS:
            value = outputs.get(field)
            normalized = _normalize_path_value(value)
            if normalized:
                return normalized
    for field in PRIMARY_OUTPUT_FIELDS:
        value = payload.get(field)
        normalized = _normalize_path_value(value)
        if normalized:
            return normalized
    for ref in path_refs:
        if ref["field"].endswith("metrics_path") or ref["field"].endswith("predictions_path"):
            return ref["path"]
    return path_refs[0]["path"] if path_refs else None


def _csv_summary_row(entry: dict[str, Any]) -> dict[str, Any]:
    summary = entry.get("summary", {})
    rf_frequency = summary.get("random_forest_poisson_metrics", {})
    rf_severity = summary.get("random_forest_classifier_metrics", {})
    return {
        "entry_id": entry["entry_id"],
        "stage": entry["stage"],
        "artifact_kind": entry["artifact_kind"],
        "run_label": entry["run_label"],
        "document_path": entry["document_path"],
        "primary_output_path": entry.get("primary_output_path"),
        "document_mtime_utc": entry["document_mtime_utc"],
        "holdout_year": summary.get("holdout_year"),
        "exposure_policy_version": entry.get("policy", {}).get("exposure_policy_version"),
        "resource_name": summary.get("resource_name"),
        "public_contract_version": summary.get("public_contract_version"),
        "analyst_contract_version": summary.get("analyst_contract_version"),
        "training_task": summary.get("training_task"),
        "split_strategy": summary.get("split_strategy"),
        "lineage_contract_version": summary.get("lineage_contract_version"),
        "upstream_input_count": summary.get("upstream_input_count"),
        "publishable_output_count": summary.get("publishable_output_count"),
        "random_forest_n_estimators": summary.get("random_forest_n_estimators"),
        "frequency_deviance": rf_frequency.get("mean_poisson_deviance"),
        "frequency_top_5pct_crash_share": rf_frequency.get("top_5pct_crash_share"),
        "severity_roc_auc": rf_severity.get("roc_auc"),
        "severity_average_precision": rf_severity.get("average_precision"),
    }


def _build_registry_entry(document_path: Path) -> dict[str, Any]:
    payload = json.loads(document_path.read_text(encoding="utf-8"))
    artifact_kind = _artifact_kind_for_document(document_path)
    stage = STAGE_BY_ARTIFACT_KIND.get(artifact_kind, "unknown")
    path_refs = _collect_path_refs(payload)
    outputs = _filter_refs_by_prefix(path_refs, "outputs")
    input_references = [
        ref
        for ref in path_refs
        if ref["field"].startswith("inputs")
        or ref["field"].startswith("dataset_inputs")
        or ref["field"].endswith("input_path")
        or ".input_path" in ref["field"]
    ]
    entry = {
        "entry_id": f"{artifact_kind}:{document_path.parent.name}:{_sha256(document_path)[:12]}",
        "registry_version": REGISTRY_VERSION,
        "artifact_kind": artifact_kind,
        "stage": stage,
        "run_label": document_path.parent.name,
        "document_name": document_path.name,
        "document_path": str(document_path),
        "document_sha256": _sha256(document_path),
        "document_mtime_utc": datetime.fromtimestamp(document_path.stat().st_mtime, tz=UTC).isoformat(),
        "summary": _summary_for_document(artifact_kind, payload),
        "policy": payload.get("policy", {}),
        "governance": payload.get("governance", {}),
        "training_config": payload.get("training_config", {}),
        "lineage": payload.get("lineage", {}),
        "input_references": input_references,
        "output_references": outputs if outputs else path_refs,
    }
    entry["primary_output_path"] = _primary_output_path(payload, path_refs)
    return entry


def build_run_registry(
    data_root: str | Path = "data",
    output_dir: str | Path = "data/registry",
) -> dict[str, Any]:
    data_path = Path(data_root)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    registry_jsonl_path = output_root / "run_registry.jsonl"
    registry_csv_path = output_root / "run_registry.csv"
    manifest_path = output_root / "run_registry.manifest.json"

    documents = _discover_registry_documents(data_path)
    if _is_relative_to(output_root, data_path):
        documents = [path for path in documents if not _is_relative_to(path, output_root)]
    entries = [_build_registry_entry(document_path) for document_path in documents]

    with registry_jsonl_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")

    csv_rows = [_csv_summary_row(entry) for entry in entries]
    csv_fieldnames = [
        "entry_id",
        "stage",
        "artifact_kind",
        "run_label",
        "document_path",
        "primary_output_path",
        "document_mtime_utc",
        "holdout_year",
        "exposure_policy_version",
        "resource_name",
        "public_contract_version",
        "analyst_contract_version",
        "training_task",
        "split_strategy",
        "lineage_contract_version",
        "upstream_input_count",
        "publishable_output_count",
        "random_forest_n_estimators",
        "frequency_deviance",
        "frequency_top_5pct_crash_share",
        "severity_roc_auc",
        "severity_average_precision",
    ]
    with registry_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    stage_counts = Counter(entry["stage"] for entry in entries)
    artifact_kind_counts = Counter(entry["artifact_kind"] for entry in entries)
    manifest = {
        "registry_version": REGISTRY_VERSION,
        "inputs": {
            "data_root": str(data_path),
            "documents_scanned": len(documents),
            "excluded_output_dir": str(output_root) if _is_relative_to(output_root, data_path) else None,
        },
        "outputs": {
            "registry_jsonl_path": str(registry_jsonl_path),
            "registry_jsonl_sha256": _sha256(registry_jsonl_path),
            "registry_csv_path": str(registry_csv_path),
            "registry_csv_sha256": _sha256(registry_csv_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "entries": len(entries),
            "stage_counts": dict(sorted(stage_counts.items())),
            "artifact_kind_counts": dict(sorted(artifact_kind_counts.items())),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
