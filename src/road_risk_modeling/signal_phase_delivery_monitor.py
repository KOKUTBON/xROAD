"""Monitor Bari signal-phase intake drop zones and build validation-ready queues."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_VERSION = "signal_phase_delivery_monitor_bundle_v1"
SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_CONTRACT_VERSION = "signal_phase_delivery_monitor_bundle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _list_delivery_files(dropzone_path: Path) -> list[Path]:
    if not dropzone_path.exists():
        return []
    return sorted(
        path
        for path in dropzone_path.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )


def _monitor_status(file_count: int) -> str:
    if file_count == 0:
        return "awaiting_delivery"
    if file_count == 1:
        return "ready_for_validation"
    return "multiple_files_manual_review"


def _replace_received_path(validation_command: str | None, received_file_path: str | None) -> str | None:
    if validation_command is None or received_file_path is None:
        return None
    return validation_command.replace("<received_file_path>", received_file_path)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Delivery Monitor Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari delivery-intake drop zones have been scanned for arrived files.",
        "",
        "## Summary",
        "",
        f"- monitored delivery rows: `{payload['summary']['monitored_delivery_count']}`",
        f"- detected files: `{payload['summary']['detected_file_count']}`",
        f"- ready for validation: `{payload['summary']['validation_ready_count']}`",
        f"- awaiting delivery: `{payload['summary']['awaiting_delivery_count']}`",
        f"- manual review rows: `{payload['summary']['manual_review_count']}`",
        "",
        "## Monitor Queue",
        "",
    ]
    for row in payload["monitor_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['profile_id']}`: `{row['monitor_status']}` "
            f"({row['detected_file_count']} files)"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_delivery_monitor_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_delivery_monitor/bari",
    signal_phase_delivery_intake_bundle_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    intake_bundle_input = Path(signal_phase_delivery_intake_bundle_path)
    receipt_register_input = Path(delivery_receipt_register_path)
    intake_payload = _load_json(intake_bundle_input)
    receipt_rows = _read_csv_rows(receipt_register_input)

    monitor_queue_rows: list[dict[str, Any]] = []
    validation_ready_rows: list[dict[str, Any]] = []

    sorted_receipts = sorted(
        receipt_rows,
        key=lambda row: (_priority_value(row.get("dispatch_reference")), str(row.get("delivery_item_id") or "")),
    )
    for row in sorted_receipts:
        dropzone_path = Path(row["incoming_dropzone_path"])
        detected_files = _list_delivery_files(dropzone_path)
        detected_file_paths = [str(path) for path in detected_files]
        selected_file_path = detected_file_paths[0] if len(detected_file_paths) == 1 else None
        monitor_status = _monitor_status(len(detected_files))
        resolved_validation_command = _replace_received_path(
            _clean_text(row.get("validation_command")),
            selected_file_path,
        )

        monitor_row = {
            "dispatch_reference": _clean_text(row.get("dispatch_reference")),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "profile_id": _clean_text(row.get("profile_id")),
            "delivery_item_id": _clean_text(row.get("delivery_item_id")),
            "incoming_dropzone_path": str(dropzone_path),
            "detected_file_count": len(detected_files),
            "detected_file_paths": " | ".join(detected_file_paths),
            "selected_received_file_path": selected_file_path,
            "monitor_status": monitor_status,
            "validation_command_ready": resolved_validation_command,
            "validation_output_dir": _clean_text(row.get("validation_output_dir")),
            "validation_status": _clean_text(row.get("validation_status")) or "not_started",
        }
        monitor_queue_rows.append(monitor_row)

        if monitor_status == "ready_for_validation":
            validation_ready_rows.append(monitor_row)

    monitor_queue_path = output_root / "delivery_monitor_queue.csv"
    validation_ready_queue_path = output_root / "validation_ready_queue.csv"
    bundle_json_path = output_root / "signal_phase_delivery_monitor_bundle.json"
    bundle_md_path = output_root / "signal_phase_delivery_monitor_bundle.md"
    manifest_path = output_root / "signal_phase_delivery_monitor_bundle.manifest.json"

    _write_csv(
        monitor_queue_path,
        monitor_queue_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "delivery_item_id",
            "incoming_dropzone_path",
            "detected_file_count",
            "detected_file_paths",
            "selected_received_file_path",
            "monitor_status",
            "validation_command_ready",
            "validation_output_dir",
            "validation_status",
        ],
    )
    _write_csv(
        validation_ready_queue_path,
        validation_ready_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "delivery_item_id",
            "selected_received_file_path",
            "monitor_status",
            "validation_command_ready",
            "validation_output_dir",
            "validation_status",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "monitored_delivery_count": len(monitor_queue_rows),
        "detected_file_count": sum(_safe_int(row["detected_file_count"]) for row in monitor_queue_rows),
        "validation_ready_count": len(validation_ready_rows),
        "awaiting_delivery_count": sum(1 for row in monitor_queue_rows if row["monitor_status"] == "awaiting_delivery"),
        "manual_review_count": sum(
            1 for row in monitor_queue_rows if row["monitor_status"] == "multiple_files_manual_review"
        ),
    }
    bundle_payload = {
        "signal_phase_delivery_monitor_bundle_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_VERSION,
        "signal_phase_delivery_monitor_bundle_contract_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "monitor_queue": monitor_queue_rows,
        "validation_ready_queue": validation_ready_rows,
        "intake_bundle_summary": intake_payload.get("summary", {}),
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_delivery_monitor_bundle_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_delivery_monitor_bundle",
            "public_contract_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_CONTRACT_VERSION,
            "signal_phase_delivery_monitor_bundle_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_delivery_monitor_builder",
        },
        "inputs": {
            "signal_phase_delivery_intake_bundle_path": str(intake_bundle_input),
            "delivery_receipt_register_path": str(receipt_register_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "monitor_queue_path": str(monitor_queue_path),
            "monitor_queue_sha256": _sha256(monitor_queue_path),
            "validation_ready_queue_path": str(validation_ready_queue_path),
            "validation_ready_queue_sha256": _sha256(validation_ready_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_delivery_intake_bundle", intake_bundle_input, _sha256(intake_bundle_input)),
            _artifact_reference("signal_phase_delivery_receipt_register", receipt_register_input, _sha256(receipt_register_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_delivery_monitor_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_delivery_monitor_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_delivery_monitor_queue", monitor_queue_path, _sha256(monitor_queue_path)),
            _artifact_reference("signal_phase_validation_ready_queue", validation_ready_queue_path, _sha256(validation_ready_queue_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_delivery_monitor_bundle_version": SIGNAL_PHASE_DELIVERY_MONITOR_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
