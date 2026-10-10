"""Run Bari support-derived validation for analyst actions that are ready to validate."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_delivery_validation import validate_signal_phase_delivery


SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_VERSION = "signal_phase_support_validation_batch_v1"
SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_CONTRACT_VERSION = "signal_phase_support_validation_batch_public_v1"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _result_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Validation Batch",
        "",
        f"As of {payload['generated_at_utc']}, the support-derived action queue has been processed for validation-ready profiles.",
        "",
        "## Summary",
        "",
        f"- action queue rows: `{payload['summary']['action_queue_count']}`",
        f"- validation candidates: `{payload['summary']['validation_candidate_count']}`",
        f"- executed validations: `{payload['summary']['executed_validation_count']}`",
        f"- accepted for ingestion: `{payload['summary']['accepted_for_ingestion_count']}`",
        f"- accepted support artifacts: `{payload['summary']['accepted_support_artifact_count']}`",
        f"- partial review outcomes: `{payload['summary']['partial_review_count']}`",
        f"- provider-fix outcomes: `{payload['summary']['provider_fix_required_count']}`",
        f"- skipped non-validation actions: `{payload['summary']['skipped_non_validation_action_count']}`",
        f"- skipped missing inputs: `{payload['summary']['skipped_missing_validation_inputs_count']}`",
        "",
        "## Results",
        "",
    ]
    for row in payload["validation_results"]:
        lines.append(
            f"- `{row['support_action_reference']}` `{row['batch_outcome']}`"
            + (
                f" -> `{row['validation_outcome']}` `{row['manifest_path']}`"
                if row["manifest_path"]
                else ""
            )
        )
    lines.append("")
    return "\n".join(lines)


def run_bari_signal_phase_support_validation_batch(
    *,
    output_dir: str | Path = "data/quality/signal_phase_support_validation_batches/bari",
    action_execution_ready_queue_path: str | Path = "data/reporting/signal_phase_support_action_queue/bari/action_execution_ready_queue.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    queue_input = Path(action_execution_ready_queue_path)
    checklist_input = Path(delivery_checklist_path)

    action_rows = _read_csv_rows(queue_input)
    validation_results: list[dict[str, Any]] = []
    executed_manifest_paths: list[str] = []

    for row in action_rows:
        support_action_reference = _clean_text(row.get("support_action_reference")) or ""
        request_id = _clean_text(row.get("request_id"))
        junction_id = _clean_text(row.get("junction_id"))
        signal_name = _clean_text(row.get("signal_name"))
        profile_id = _clean_text(row.get("profile_id"))
        action_category = _clean_text(row.get("action_category")) or ""
        execution_route = _clean_text(row.get("execution_route")) or ""
        delivery_csv_path = _clean_text(row.get("delivery_csv_path"))
        mapping_stub_path = _clean_text(row.get("mapping_stub_path"))

        result_row = {
            "support_action_reference": support_action_reference,
            "request_id": request_id or "",
            "junction_id": junction_id or "",
            "signal_name": signal_name or "",
            "profile_id": profile_id or "",
            "action_category": action_category,
            "execution_route": execution_route,
            "batch_outcome": "",
            "validation_outcome": "",
            "manifest_path": "",
        }

        if execution_route != "validate_delivery":
            result_row["batch_outcome"] = "skipped_non_validation_action"
            validation_results.append(result_row)
            continue

        if not delivery_csv_path or not mapping_stub_path:
            result_row["batch_outcome"] = "skipped_missing_validation_inputs"
            validation_results.append(result_row)
            continue

        validation_output_dir = output_root / "validation_outputs" / (request_id or "unknown_request") / (profile_id or "unknown_profile")
        result = validate_signal_phase_delivery(
            delivery_csv_path,
            mapping_stub_path,
            validation_output_dir,
            delivery_checklist_path=checklist_input,
            request_id=request_id,
            junction_id=junction_id,
            preview_limit=preview_limit,
        )
        manifest_path = str(result["manifest_path"])
        executed_manifest_paths.append(manifest_path)
        result_row["batch_outcome"] = "executed_validation"
        result_row["validation_outcome"] = result["stats"]["validation_outcome"]
        result_row["manifest_path"] = manifest_path
        validation_results.append(result_row)

    result_rows_path = output_root / "support_validation_batch_results.csv"
    batch_json_path = output_root / "signal_phase_support_validation_batch.json"
    batch_md_path = output_root / "signal_phase_support_validation_batch.md"
    manifest_path = output_root / "signal_phase_support_validation_batch.manifest.json"

    _write_csv(
        result_rows_path,
        validation_results,
        [
            "support_action_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "action_category",
            "execution_route",
            "batch_outcome",
            "validation_outcome",
            "manifest_path",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "action_queue_count": len(action_rows),
        "validation_candidate_count": sum(
            1 for row in action_rows if (_clean_text(row.get("execution_route")) or "") == "validate_delivery"
        ),
        "executed_validation_count": len(executed_manifest_paths),
        "accepted_for_ingestion_count": sum(
            1 for row in validation_results if row["validation_outcome"] == "accepted_for_ingestion"
        ),
        "accepted_support_artifact_count": sum(
            1 for row in validation_results if row["validation_outcome"] == "accepted_support_artifact"
        ),
        "partial_review_count": sum(
            1 for row in validation_results if row["validation_outcome"] == "accepted_with_rejections"
        ),
        "provider_fix_required_count": sum(
            1
            for row in validation_results
            if row["validation_outcome"] in {"provider_fix_required", "schema_not_ready", "empty_delivery"}
        ),
        "skipped_non_validation_action_count": sum(
            1 for row in validation_results if row["batch_outcome"] == "skipped_non_validation_action"
        ),
        "skipped_missing_validation_inputs_count": sum(
            1 for row in validation_results if row["batch_outcome"] == "skipped_missing_validation_inputs"
        ),
    }
    payload = {
        "signal_phase_support_validation_batch_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_VERSION,
        "signal_phase_support_validation_batch_contract_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "validation_results": validation_results,
        "executed_manifest_paths": executed_manifest_paths,
    }
    batch_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    batch_md_path.write_text(_result_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_validation_batch_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_validation_batch",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_CONTRACT_VERSION,
            "signal_phase_support_validation_batch_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_validation_batch_runner",
        },
        "inputs": {
            "action_execution_ready_queue_path": str(queue_input),
            "delivery_checklist_path": str(checklist_input),
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "batch_json_path": str(batch_json_path),
            "batch_json_sha256": _sha256(batch_json_path),
            "batch_md_path": str(batch_md_path),
            "batch_md_sha256": _sha256(batch_md_path),
            "result_rows_path": str(result_rows_path),
            "result_rows_sha256": _sha256(result_rows_path),
            "executed_manifest_paths": executed_manifest_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_support_action_execution_ready_queue", queue_input, _sha256(queue_input)),
            _artifact_reference("signal_phase_delivery_checklist", checklist_input, _sha256(checklist_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_support_validation_batch_json", batch_json_path, _sha256(batch_json_path)),
            _artifact_reference("signal_phase_support_validation_batch_markdown", batch_md_path, _sha256(batch_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_support_validation_batch_results", result_rows_path, _sha256(result_rows_path)),
        ]
        + [
            _artifact_reference("signal_phase_delivery_validation", Path(path), _sha256(Path(path)))
            for path in executed_manifest_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_support_validation_batch_version": SIGNAL_PHASE_SUPPORT_VALIDATION_BATCH_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
