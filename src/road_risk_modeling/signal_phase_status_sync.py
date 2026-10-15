"""Build synced Bari signal-phase operational status exports."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_STATUS_SYNC_BUNDLE_VERSION = "signal_phase_status_sync_bundle_v1"
SIGNAL_PHASE_STATUS_SYNC_BUNDLE_CONTRACT_VERSION = "signal_phase_status_sync_bundle_public_v1"
_NON_VALIDATED_STATUSES = {"not_started"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _load_applied_validation_manifest_paths(receive_cycle_path: Path) -> set[str]:
    if not receive_cycle_path.exists():
        return set()
    receive_cycle = _load_json(receive_cycle_path)
    session_manifest_value = receive_cycle.get("outputs", {}).get("delivery_session_manifest_path")
    session_manifest_path = _clean_text(session_manifest_value)
    if not session_manifest_path:
        return set()
    session_manifest = _load_json(Path(session_manifest_path))
    session_json_value = session_manifest.get("outputs", {}).get("session_json_path")
    session_json_path = _clean_text(session_json_value)
    if not session_json_path:
        return set()
    session_payload = _load_json(Path(session_json_path))
    return {
        str(row.get("validation_manifest_path"))
        for row in session_payload.get("accepted_deliveries", [])
        if _clean_text(row.get("validation_manifest_path"))
    }


def _receipt_status_from_monitor(monitor_status: str | None, fallback: str | None) -> str | None:
    if monitor_status == "ready_for_validation":
        return "delivery_detected"
    if monitor_status == "multiple_files_manual_review":
        return "multiple_files_manual_review"
    if monitor_status == "awaiting_delivery":
        return "awaiting_delivery"
    return fallback


def _checklist_status(
    *,
    validation_outcome: str | None,
    receipt_status: str | None,
    applied_to_movement_layer: bool,
    fallback: str | None,
) -> str | None:
    if applied_to_movement_layer:
        return "mapped_to_movements"
    if validation_outcome == "accepted_for_ingestion":
        return "validated_ready_for_ingestion"
    if validation_outcome == "accepted_support_artifact":
        return "validated_support_artifact"
    if validation_outcome == "accepted_with_rejections":
        return "partial_validation_review"
    if validation_outcome in {"provider_fix_required", "schema_not_ready", "empty_delivery"}:
        return "provider_fix_required"
    if receipt_status == "multiple_files_manual_review":
        return "manual_delivery_review"
    if receipt_status == "delivery_detected":
        return "delivery_detected"
    return fallback


def _is_validated_status(value: Any) -> bool:
    status = _clean_text(value)
    if not status:
        return False
    return status not in _NON_VALIDATED_STATUSES


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Status Sync Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari receipt register and delivery checklist have been synchronized against the current monitor, validation, and receive-cycle outputs.",
        "",
        "## Summary",
        "",
        f"- receipt rows: `{payload['summary']['receipt_row_count']}`",
        f"- checklist rows: `{payload['summary']['checklist_row_count']}`",
        f"- detected deliveries: `{payload['summary']['detected_delivery_count']}`",
        f"- manual-review deliveries: `{payload['summary']['manual_review_count']}`",
        f"- validated deliveries: `{payload['summary']['validated_count']}`",
        f"- validated support artifacts: `{payload['summary']['validated_support_artifact_count']}`",
        f"- mapped deliveries: `{payload['summary']['mapped_count']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_status_sync_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_status_sync/bari",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_monitor_queue_path: str | Path = "data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    validation_batch_results_path: str | Path = "data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    receive_cycle_path: str | Path = "data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    receipt_input = Path(delivery_receipt_register_path)
    monitor_input = Path(delivery_monitor_queue_path)
    validation_input = Path(validation_batch_results_path)
    checklist_input = Path(delivery_checklist_path)
    receive_cycle_input = Path(receive_cycle_path)

    receipt_rows = _read_csv_rows(receipt_input)
    monitor_rows = _read_csv_rows(monitor_input)
    validation_rows = _read_csv_rows(validation_input)
    checklist_rows = _read_csv_rows(checklist_input)
    applied_manifests = _load_applied_validation_manifest_paths(receive_cycle_input)

    monitor_by_item = {str(row["delivery_item_id"]): row for row in monitor_rows if row.get("delivery_item_id")}
    validation_by_item = {
        str(row["delivery_item_id"]): row for row in validation_rows if row.get("delivery_item_id")
    }
    checklist_by_item = {
        str(row["delivery_item_id"]): row for row in checklist_rows if row.get("delivery_item_id")
    }

    synced_receipts: list[dict[str, Any]] = []
    synced_checklist_rows: list[dict[str, Any]] = []

    for receipt_row in receipt_rows:
        delivery_item_id = str(receipt_row.get("delivery_item_id") or "")
        monitor_row = monitor_by_item.get(delivery_item_id, {})
        validation_row = validation_by_item.get(delivery_item_id, {})
        validation_outcome = _clean_text(validation_row.get("validation_outcome"))
        validation_manifest_path = _clean_text(validation_row.get("manifest_path"))
        applied_to_movement_layer = bool(
            validation_manifest_path and validation_manifest_path in applied_manifests
        )
        synced_receipt = dict(receipt_row)
        synced_receipt["receipt_status"] = _receipt_status_from_monitor(
            _clean_text(monitor_row.get("monitor_status")),
            _clean_text(receipt_row.get("receipt_status")),
        )
        synced_receipt["received_file_path"] = _clean_text(monitor_row.get("selected_received_file_path")) or _clean_text(
            receipt_row.get("received_file_path")
        ) or ""
        synced_receipt["validation_status"] = validation_outcome or _clean_text(receipt_row.get("validation_status")) or ""
        synced_receipt["validation_manifest_path"] = validation_manifest_path or _clean_text(
            receipt_row.get("validation_manifest_path")
        ) or ""
        synced_receipt["synced_applied_to_movement_layer"] = "yes" if applied_to_movement_layer else "no"
        synced_receipt["synced_detected_file_count"] = str(int(float(monitor_row.get("detected_file_count") or 0)))
        synced_receipts.append(synced_receipt)

        checklist_row = checklist_by_item.get(delivery_item_id)
        if checklist_row is not None:
            synced_checklist = dict(checklist_row)
            synced_checklist["delivery_status"] = _checklist_status(
                validation_outcome=validation_outcome,
                receipt_status=_clean_text(synced_receipt.get("receipt_status")),
                applied_to_movement_layer=applied_to_movement_layer,
                fallback=_clean_text(checklist_row.get("delivery_status")),
            ) or ""
            if validation_outcome:
                synced_checklist["validation_outcome"] = validation_outcome
            synced_checklist["mapped_to_movements"] = "yes" if applied_to_movement_layer else str(
                checklist_row.get("mapped_to_movements") or "no"
            )
            synced_checklist_rows.append(synced_checklist)

    synced_receipt_path = output_root / "delivery_receipt_register_synced.csv"
    synced_checklist_path = output_root / "delivery_checklist_synced.csv"
    report_json_path = output_root / "signal_phase_status_sync_bundle.json"
    report_md_path = output_root / "signal_phase_status_sync_bundle.md"
    manifest_path = output_root / "signal_phase_status_sync_bundle.manifest.json"

    receipt_fieldnames = list(receipt_rows[0].keys()) + [
        "synced_applied_to_movement_layer",
        "synced_detected_file_count",
    ]
    checklist_fieldnames = list(checklist_rows[0].keys())
    if "validation_outcome" not in checklist_fieldnames:
        checklist_fieldnames.append("validation_outcome")

    _write_csv(synced_receipt_path, synced_receipts, receipt_fieldnames)
    _write_csv(synced_checklist_path, synced_checklist_rows, checklist_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "receipt_row_count": len(synced_receipts),
        "checklist_row_count": len(synced_checklist_rows),
        "detected_delivery_count": sum(
            1
            for row in synced_receipts
            if _clean_text(row.get("receipt_status")) in {"delivery_detected", "multiple_files_manual_review"}
        ),
        "manual_review_count": sum(
            1 for row in synced_receipts if _clean_text(row.get("receipt_status")) == "multiple_files_manual_review"
        ),
        "validated_count": sum(1 for row in synced_receipts if _is_validated_status(row.get("validation_status"))),
        "validated_support_artifact_count": sum(
            1 for row in synced_receipts if _clean_text(row.get("validation_status")) == "accepted_support_artifact"
        ),
        "mapped_count": sum(1 for row in synced_receipts if row.get("synced_applied_to_movement_layer") == "yes"),
    }
    payload = {
        "signal_phase_status_sync_bundle_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_VERSION,
        "signal_phase_status_sync_bundle_contract_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "outputs": {
            "synced_receipt_path": str(synced_receipt_path),
            "synced_checklist_path": str(synced_checklist_path),
        },
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_status_sync_bundle_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_status_sync_bundle",
            "public_contract_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_CONTRACT_VERSION,
            "signal_phase_status_sync_bundle_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_status_sync_builder",
        },
        "inputs": {
            "delivery_receipt_register_path": str(receipt_input),
            "delivery_monitor_queue_path": str(monitor_input),
            "validation_batch_results_path": str(validation_input),
            "delivery_checklist_path": str(checklist_input),
            "receive_cycle_path": str(receive_cycle_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "synced_receipt_path": str(synced_receipt_path),
            "synced_receipt_sha256": _sha256(synced_receipt_path),
            "synced_checklist_path": str(synced_checklist_path),
            "synced_checklist_sha256": _sha256(synced_checklist_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_delivery_receipt_register", receipt_input, _sha256(receipt_input)),
                _artifact_reference("signal_phase_delivery_monitor_queue", monitor_input, _sha256(monitor_input)),
                _artifact_reference("signal_phase_validation_batch_results", validation_input, _sha256(validation_input)),
                _artifact_reference("signal_phase_delivery_checklist", checklist_input, _sha256(checklist_input)),
                _artifact_reference("signal_phase_receive_cycle_json", receive_cycle_input, _sha256(receive_cycle_input)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_status_sync_json", report_json_path, _sha256(report_json_path)),
                _artifact_reference("signal_phase_status_sync_markdown", report_md_path, _sha256(report_md_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_delivery_receipt_register_synced", synced_receipt_path, _sha256(synced_receipt_path)),
                _artifact_reference("signal_phase_delivery_checklist_synced", synced_checklist_path, _sha256(synced_checklist_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_status_sync_bundle_version": SIGNAL_PHASE_STATUS_SYNC_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
