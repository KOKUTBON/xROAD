"""Run Bari signal-phase validation for monitor rows that are ready for validation."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_delivery_validation import validate_signal_phase_delivery


SIGNAL_PHASE_VALIDATION_BATCH_VERSION = "signal_phase_validation_batch_v1"
SIGNAL_PHASE_VALIDATION_BATCH_CONTRACT_VERSION = "signal_phase_validation_batch_public_v1"


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
        "# Bari Signal-Phase Validation Batch",
        "",
        f"As of {payload['generated_at_utc']}, the validation-ready queue has been processed.",
        "",
        "## Summary",
        "",
        f"- ready queue rows: `{payload['summary']['ready_queue_count']}`",
        f"- executed validations: `{payload['summary']['executed_validation_count']}`",
        f"- accepted for ingestion: `{payload['summary']['accepted_for_ingestion_count']}`",
        f"- accepted support artifacts: `{payload['summary']['accepted_support_artifact_count']}`",
        f"- partial review outcomes: `{payload['summary']['partial_review_count']}`",
        f"- provider-fix outcomes: `{payload['summary']['provider_fix_required_count']}`",
        f"- skipped rows: `{payload['summary']['skipped_count']}`",
        "",
        "## Results",
        "",
    ]
    for row in payload["validation_results"]:
        lines.append(
            f"- `{row['request_id']}` `{row['profile_id']}`: `{row['validation_outcome']}` -> `{row['manifest_path'] or 'not_run'}`"
        )
    lines.append("")
    return "\n".join(lines)


def run_bari_signal_phase_validation_batch(
    *,
    output_dir: str | Path = "data/quality/signal_phase_validation_batches/bari",
    validation_ready_queue_path: str | Path = "data/reporting/signal_phase_delivery_monitor/bari/validation_ready_queue.csv",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    queue_input = Path(validation_ready_queue_path)
    receipt_input = Path(delivery_receipt_register_path)
    checklist_input = Path(delivery_checklist_path)

    ready_rows = _read_csv_rows(queue_input)
    receipt_rows = _read_csv_rows(receipt_input)
    receipt_by_item = {
        str(row["delivery_item_id"]): row
        for row in receipt_rows
        if row.get("delivery_item_id")
    }

    validation_results: list[dict[str, Any]] = []
    executed_manifest_paths: list[str] = []

    for row in ready_rows:
        delivery_item_id = str(row["delivery_item_id"])
        receipt_row = receipt_by_item.get(delivery_item_id, {})
        received_file_path = _clean_text(row.get("selected_received_file_path"))
        mapping_stub_path = _clean_text(receipt_row.get("mapping_stub_path"))
        validation_output_dir = _clean_text(receipt_row.get("validation_output_dir"))
        request_id = _clean_text(row.get("request_id"))
        junction_id = _clean_text(row.get("junction_id"))

        if not received_file_path or not mapping_stub_path or not validation_output_dir:
            validation_results.append(
                {
                    "delivery_item_id": delivery_item_id,
                    "request_id": request_id,
                    "junction_id": junction_id,
                    "profile_id": _clean_text(row.get("profile_id")),
                    "validation_outcome": "skipped_missing_validation_inputs",
                    "manifest_path": "",
                }
            )
            continue

        result = validate_signal_phase_delivery(
            received_file_path,
            mapping_stub_path,
            validation_output_dir,
            delivery_checklist_path=checklist_input,
            request_id=request_id,
            junction_id=junction_id,
            preview_limit=preview_limit,
        )
        manifest_path = str(result["manifest_path"])
        executed_manifest_paths.append(manifest_path)
        validation_results.append(
            {
                "delivery_item_id": delivery_item_id,
                "request_id": request_id,
                "junction_id": junction_id,
                "profile_id": _clean_text(row.get("profile_id")),
                "validation_outcome": result["stats"]["validation_outcome"],
                "manifest_path": manifest_path,
            }
        )

    result_rows_path = output_root / "validation_batch_results.csv"
    batch_json_path = output_root / "signal_phase_validation_batch.json"
    batch_md_path = output_root / "signal_phase_validation_batch.md"
    manifest_path = output_root / "signal_phase_validation_batch.manifest.json"

    _write_csv(
        result_rows_path,
        validation_results,
        [
            "delivery_item_id",
            "request_id",
            "junction_id",
            "profile_id",
            "validation_outcome",
            "manifest_path",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ready_queue_count": len(ready_rows),
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
        "skipped_count": sum(
            1 for row in validation_results if row["validation_outcome"] == "skipped_missing_validation_inputs"
        ),
    }
    payload = {
        "signal_phase_validation_batch_version": SIGNAL_PHASE_VALIDATION_BATCH_VERSION,
        "signal_phase_validation_batch_contract_version": SIGNAL_PHASE_VALIDATION_BATCH_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "validation_results": validation_results,
    }
    batch_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    batch_md_path.write_text(_result_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_validation_batch_version": SIGNAL_PHASE_VALIDATION_BATCH_VERSION,
        "contract": {
            "resource_name": "signal_phase_validation_batch",
            "public_contract_version": SIGNAL_PHASE_VALIDATION_BATCH_CONTRACT_VERSION,
            "signal_phase_validation_batch_version": SIGNAL_PHASE_VALIDATION_BATCH_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_validation_batch_runner",
        },
        "inputs": {
            "validation_ready_queue_path": str(queue_input),
            "delivery_receipt_register_path": str(receipt_input),
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
            _artifact_reference("signal_phase_validation_ready_queue", queue_input, _sha256(queue_input)),
            _artifact_reference("signal_phase_delivery_receipt_register", receipt_input, _sha256(receipt_input)),
            _artifact_reference("signal_phase_delivery_checklist", checklist_input, _sha256(checklist_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_validation_batch_json", batch_json_path, _sha256(batch_json_path)),
            _artifact_reference("signal_phase_validation_batch_markdown", batch_md_path, _sha256(batch_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_validation_batch_results", result_rows_path, _sha256(result_rows_path)),
        ]
        + [
            _artifact_reference("signal_phase_delivery_validation", Path(path), _sha256(Path(path)))
            for path in executed_manifest_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_validation_batch_version": SIGNAL_PHASE_VALIDATION_BATCH_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
