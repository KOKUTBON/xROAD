"""Build Bari initial-dispatch recording bundles from operator execution logs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_VERSION = "signal_phase_dispatch_recording_bundle_v1"
SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_recording_bundle_public_v1"
)
_PENDING_EXECUTION_STATUSES = {"", "pending_execution"}


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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _is_executed_status(value: Any) -> bool:
    status = (_clean_text(value) or "").lower()
    return status not in _PENDING_EXECUTION_STATUSES


def _recording_status(row: dict[str, Any]) -> str:
    if _is_executed_status(row.get("execution_status")):
        return "execution_logged"
    if _clean_text(row.get("execution_completed_at")):
        return "execution_logged_missing_status"
    if _clean_text(row.get("protocol_reference")) or _clean_text(row.get("evidence_path")):
        return "partial_operator_entry"
    return "awaiting_operator_entry"


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Recording Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari initial-send execution queue has been synchronized with the operator execution log and materialized as a runtime-ready dispatch queue.",
        "",
        "## Summary",
        "",
        f"- execution-ready requests: `{payload['summary']['request_count']}`",
        f"- log rows written: `{payload['summary']['log_row_count']}`",
        f"- logged executions applied: `{payload['summary']['applied_execution_count']}`",
        f"- runtime pending rows: `{payload['summary']['pending_execution_count']}`",
        f"- unmatched log rows: `{payload['summary']['unmatched_log_row_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across runtime rows: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across runtime rows: `{payload['summary']['unresolved_signalized_crash_total']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_recording_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_recording/bari",
    dispatch_execution_ready_queue_path: str | Path = "data/reporting/signal_phase_dispatch_execution/bari/dispatch_execution_ready_queue.csv",
    dispatch_execution_log_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    execution_queue_input = Path(dispatch_execution_ready_queue_path)
    execution_log_input = (
        Path(dispatch_execution_log_path)
        if dispatch_execution_log_path is not None
        else output_root / "dispatch_execution_log.csv"
    )

    execution_ready_rows = _read_csv_rows(execution_queue_input)
    existing_log_rows = (
        _read_csv_rows(execution_log_input) if execution_log_input.exists() else []
    )
    existing_log_by_request = {
        str(row.get("request_id") or ""): row
        for row in existing_log_rows
        if row.get("request_id")
    }
    matched_request_ids = {
        str(row.get("request_id") or "")
        for row in execution_ready_rows
        if row.get("request_id")
    }

    log_rows: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    unmatched_log_rows: list[dict[str, Any]] = []

    for ready_row in execution_ready_rows:
        request_id = str(ready_row.get("request_id") or "")
        existing_log = existing_log_by_request.get(request_id, {})
        log_row = {
            "dispatch_reference": _clean_text(ready_row.get("dispatch_reference")),
            "request_id": request_id,
            "junction_id": _clean_text(ready_row.get("junction_id")),
            "signal_name": _clean_text(ready_row.get("signal_name")),
            "due_date": _clean_text(ready_row.get("due_date")),
            "primary_channel_value": _clean_text(ready_row.get("primary_channel_value")),
            "secondary_channel_value": _clean_text(ready_row.get("secondary_channel_value")),
            "unresolved_signalized_movement_count": _safe_int(
                ready_row.get("unresolved_signalized_movement_count")
            ),
            "unresolved_signalized_crash_count": _safe_int(
                ready_row.get("unresolved_signalized_crash_count")
            ),
            "unresolved_coverage_pct": round(_safe_float(ready_row.get("unresolved_coverage_pct")), 2),
            "unresolved_crash_coverage_pct": round(
                _safe_float(ready_row.get("unresolved_crash_coverage_pct")), 2
            ),
            "execution_status": _clean_text(existing_log.get("execution_status"))
            or "pending_execution",
            "execution_completed_at": _clean_text(existing_log.get("execution_completed_at")) or "",
            "execution_channel_used": _clean_text(existing_log.get("execution_channel_used")) or "",
            "execution_outcome": _clean_text(existing_log.get("execution_outcome")) or "",
            "response_received": _clean_text(existing_log.get("response_received")) or "no",
            "response_summary": _clean_text(existing_log.get("response_summary")) or "",
            "protocol_reference": _clean_text(existing_log.get("protocol_reference")) or "",
            "evidence_path": _clean_text(existing_log.get("evidence_path")) or "",
            "execution_notes": _clean_text(existing_log.get("execution_notes")) or "",
            "log_match_status": "matched_request_id",
        }
        log_rows.append(log_row)

        runtime_row = dict(ready_row)
        for field in [
            "execution_status",
            "execution_completed_at",
            "execution_channel_used",
            "execution_outcome",
            "response_received",
            "response_summary",
            "protocol_reference",
            "evidence_path",
            "execution_notes",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
        ]:
            runtime_row[field] = log_row[field]
        runtime_row["recording_status"] = _recording_status(log_row)
        runtime_rows.append(runtime_row)

    for existing_log in existing_log_rows:
        request_id = str(existing_log.get("request_id") or "")
        if request_id and request_id not in matched_request_ids:
            row = dict(existing_log)
            row["log_match_status"] = "unmatched_request_id"
            unmatched_log_rows.append(row)
            log_rows.append(row)

    log_template_path = output_root / "dispatch_execution_log_template.csv"
    log_path = output_root / "dispatch_execution_log.csv"
    runtime_queue_path = output_root / "dispatch_execution_queue_runtime.csv"
    unmatched_log_path = output_root / "unmatched_dispatch_execution_log_rows.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_recording_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_recording_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_recording_bundle.manifest.json"

    log_fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "due_date",
        "primary_channel_value",
        "secondary_channel_value",
        "unresolved_signalized_movement_count",
        "unresolved_signalized_crash_count",
        "unresolved_coverage_pct",
        "unresolved_crash_coverage_pct",
        "execution_status",
        "execution_completed_at",
        "execution_channel_used",
        "execution_outcome",
        "response_received",
        "response_summary",
        "protocol_reference",
        "evidence_path",
        "execution_notes",
        "log_match_status",
    ]
    runtime_fieldnames = list(execution_ready_rows[0].keys()) if execution_ready_rows else []
    for field in [
        "unresolved_signalized_movement_count",
        "unresolved_signalized_crash_count",
        "unresolved_coverage_pct",
        "unresolved_crash_coverage_pct",
    ]:
        if field not in runtime_fieldnames:
            runtime_fieldnames.append(field)
    if "recording_status" not in runtime_fieldnames:
        runtime_fieldnames.append("recording_status")

    _write_csv(log_template_path, log_rows, log_fieldnames)
    _write_csv(log_path, log_rows, log_fieldnames)
    _write_csv(runtime_queue_path, runtime_rows, runtime_fieldnames)
    _write_csv(unmatched_log_path, unmatched_log_rows, log_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(execution_ready_rows),
        "log_row_count": len(log_rows),
        "applied_execution_count": sum(
            1 for row in runtime_rows if row.get("recording_status") == "execution_logged"
        ),
        "pending_execution_count": sum(
            1
            for row in runtime_rows
            if row.get("recording_status") == "awaiting_operator_entry"
        ),
        "partial_operator_entry_count": sum(
            1
            for row in runtime_rows
            if row.get("recording_status") == "partial_operator_entry"
        ),
        "unmatched_log_row_count": len(unmatched_log_rows),
        "response_received_count": sum(
            1
            for row in runtime_rows
            if row.get("recording_status") == "execution_logged"
            and _is_true(row.get("response_received"))
        ),
        "targets_with_unresolved_movements": sum(
            1 for row in runtime_rows if _safe_int(row.get("unresolved_signalized_movement_count")) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in runtime_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in runtime_rows
        ),
    }

    payload = {
        "signal_phase_dispatch_recording_bundle_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_VERSION,
        "signal_phase_dispatch_recording_bundle_contract_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_execution_ready_queue_path": str(execution_queue_input),
            "dispatch_execution_log_path": str(execution_log_input),
        },
        "outputs": {
            "dispatch_execution_log_template_path": str(log_template_path),
            "dispatch_execution_log_path": str(log_path),
            "dispatch_execution_queue_runtime_path": str(runtime_queue_path),
            "unmatched_dispatch_execution_log_rows_path": str(unmatched_log_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_recording_bundle_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_recording_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_recording_bundle_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_recording_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "dispatch_execution_log_template_path": str(log_template_path),
            "dispatch_execution_log_template_sha256": _sha256(log_template_path),
            "dispatch_execution_log_path": str(log_path),
            "dispatch_execution_log_sha256": _sha256(log_path),
            "dispatch_execution_queue_runtime_path": str(runtime_queue_path),
            "dispatch_execution_queue_runtime_sha256": _sha256(runtime_queue_path),
            "unmatched_dispatch_execution_log_rows_path": str(unmatched_log_path),
            "unmatched_dispatch_execution_log_rows_sha256": _sha256(unmatched_log_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_ready_queue",
                    execution_queue_input,
                    _sha256(execution_queue_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_log",
                    execution_log_input,
                    _sha256(execution_log_input) if execution_log_input.exists() else "",
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_recording_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_recording_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue_runtime",
                    runtime_queue_path,
                    _sha256(runtime_queue_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_log_csv",
                    log_path,
                    _sha256(log_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_dispatch_recording_bundle_version": SIGNAL_PHASE_DISPATCH_RECORDING_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
