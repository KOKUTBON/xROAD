"""Build Bari dispatch-log repair recording bundles and repaired runtime queues."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_VERSION = (
    "signal_phase_dispatch_repair_recording_bundle_v1"
)
SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_repair_recording_bundle_public_v1"
)
_PENDING_REPAIR_STATUSES = {"", "pending_repair"}


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


def _append_note(existing: Any, note: Any) -> str:
    current = _clean_text(existing)
    addition = _clean_text(note)
    if not current and not addition:
        return ""
    if not current:
        return str(addition)
    if not addition:
        return str(current)
    return f"{current} | {addition}"


def _repair_status(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    return _clean_text(row.get("repair_status")) or "pending_repair"


def _repair_ready(row: dict[str, Any] | None) -> bool:
    status = _repair_status(row).lower()
    return bool(status and status not in _PENDING_REPAIR_STATUSES)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Repair Recording Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari dispatch repair queue has been synchronized with a repair log and overlaid onto the runtime dispatch queue before validation.",
        "",
        "## Summary",
        "",
        f"- runtime rows reviewed: `{payload['summary']['runtime_row_count']}`",
        f"- repair requests: `{payload['summary']['repair_request_count']}`",
        f"- repair log rows: `{payload['summary']['repair_log_row_count']}`",
        f"- repair-ready rows applied: `{payload['summary']['applied_repair_count']}`",
        f"- pending repair rows: `{payload['summary']['pending_repair_count']}`",
        f"- unmatched repair-log rows: `{payload['summary']['unmatched_repair_log_row_count']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_repair_recording_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari",
    dispatch_execution_runtime_queue_path: str | Path = "data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_queue_runtime.csv",
    dispatch_log_repair_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    dispatch_log_repair_log_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_input = Path(dispatch_execution_runtime_queue_path)
    repair_queue_input = Path(dispatch_log_repair_queue_path)
    repair_log_input = (
        Path(dispatch_log_repair_log_path)
        if dispatch_log_repair_log_path is not None
        else output_root / "dispatch_log_repair_log.csv"
    )
    repair_log_template_path = output_root / "dispatch_log_repair_log_template.csv"
    repaired_runtime_queue_path = output_root / "dispatch_execution_queue_runtime_repaired.csv"
    unmatched_repair_log_path = output_root / "unmatched_dispatch_log_repair_rows.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_repair_recording_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_repair_recording_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_repair_recording_bundle.manifest.json"

    runtime_rows = _read_csv_rows(runtime_input)
    repair_queue_rows = _read_csv_rows(repair_queue_input) if repair_queue_input.exists() else []
    existing_repair_log_rows = (
        _read_csv_rows(repair_log_input) if repair_log_input.exists() else []
    )
    preexisting_repair_log = repair_log_input.exists()

    runtime_by_request = {
        str(row.get("request_id") or ""): row for row in runtime_rows if row.get("request_id")
    }
    existing_repair_log_by_request = {
        str(row.get("request_id") or ""): row
        for row in existing_repair_log_rows
        if row.get("request_id")
    }

    repair_log_rows: list[dict[str, Any]] = []
    repair_log_by_request: dict[str, dict[str, Any]] = {}
    matched_request_ids: set[str] = set()

    for repair_row in repair_queue_rows:
        request_id = str(repair_row.get("request_id") or "")
        runtime_row = runtime_by_request.get(request_id, {})
        existing_row = existing_repair_log_by_request.get(request_id, {})
        matched_request_ids.add(request_id)

        log_row = {
            "dispatch_reference": _clean_text(repair_row.get("dispatch_reference"))
            or _clean_text(runtime_row.get("dispatch_reference")),
            "request_id": request_id,
            "junction_id": _clean_text(repair_row.get("junction_id"))
            or _clean_text(runtime_row.get("junction_id")),
            "signal_name": _clean_text(repair_row.get("signal_name"))
            or _clean_text(runtime_row.get("signal_name")),
            "action_category": _clean_text(repair_row.get("action_category")) or "",
            "dispatch_validation_outcome": _clean_text(
                repair_row.get("dispatch_validation_outcome")
            )
            or "",
            "dispatch_validation_issue_codes": _clean_text(
                repair_row.get("dispatch_validation_issue_codes")
            )
            or "",
            "original_execution_status": _clean_text(runtime_row.get("execution_status")) or "",
            "original_execution_completed_at": _clean_text(
                runtime_row.get("execution_completed_at")
            )
            or "",
            "original_execution_channel_used": _clean_text(
                runtime_row.get("execution_channel_used")
            )
            or "",
            "original_execution_outcome": _clean_text(runtime_row.get("execution_outcome"))
            or "",
            "original_response_received": _clean_text(runtime_row.get("response_received"))
            or "no",
            "original_response_summary": _clean_text(runtime_row.get("response_summary")) or "",
            "original_protocol_reference": _clean_text(runtime_row.get("protocol_reference"))
            or "",
            "original_evidence_path": _clean_text(runtime_row.get("evidence_path")) or "",
            "repair_status": _clean_text(existing_row.get("repair_status")) or "pending_repair",
            "repaired_execution_status": _clean_text(existing_row.get("repaired_execution_status"))
            or "",
            "repaired_execution_completed_at": _clean_text(
                existing_row.get("repaired_execution_completed_at")
            )
            or "",
            "repaired_execution_channel_used": _clean_text(
                existing_row.get("repaired_execution_channel_used")
            )
            or "",
            "repaired_execution_outcome": _clean_text(
                existing_row.get("repaired_execution_outcome")
            )
            or "",
            "repaired_response_received": _clean_text(
                existing_row.get("repaired_response_received")
            )
            or "",
            "repaired_response_summary": _clean_text(
                existing_row.get("repaired_response_summary")
            )
            or "",
            "repaired_protocol_reference": _clean_text(
                existing_row.get("repaired_protocol_reference")
            )
            or "",
            "repaired_evidence_path": _clean_text(existing_row.get("repaired_evidence_path"))
            or "",
            "repaired_execution_notes": _clean_text(existing_row.get("repaired_execution_notes"))
            or "",
            "repair_completed_at": _clean_text(existing_row.get("repair_completed_at")) or "",
            "repair_operator_notes": _clean_text(existing_row.get("repair_operator_notes")) or "",
            "repair_evidence_path": _clean_text(existing_row.get("repair_evidence_path")) or "",
            "repair_match_status": "matched_request_id",
        }
        repair_log_rows.append(log_row)
        repair_log_by_request[request_id] = log_row

    unmatched_repair_log_rows: list[dict[str, Any]] = []
    for existing_row in existing_repair_log_rows:
        request_id = str(existing_row.get("request_id") or "")
        if request_id and request_id not in matched_request_ids:
            unmatched_row = dict(existing_row)
            unmatched_row["repair_match_status"] = "unmatched_request_id"
            repair_log_rows.append(unmatched_row)
            unmatched_repair_log_rows.append(unmatched_row)

    repaired_runtime_rows: list[dict[str, Any]] = []
    applied_repair_count = 0
    pending_repair_count = 0

    for runtime_row in runtime_rows:
        repaired_row = dict(runtime_row)
        request_id = str(runtime_row.get("request_id") or "")
        repair_row = repair_log_by_request.get(request_id)
        repaired_row["repair_status"] = _repair_status(repair_row)
        repaired_row["repair_validation_issue_codes"] = (
            _clean_text(repair_row.get("dispatch_validation_issue_codes"))
            if repair_row
            else ""
        ) or ""
        repaired_row["repair_applied"] = "no" if repair_row else ""

        if repair_row and _repair_ready(repair_row):
            replacements = {
                "execution_status": "repaired_execution_status",
                "execution_completed_at": "repaired_execution_completed_at",
                "execution_channel_used": "repaired_execution_channel_used",
                "execution_outcome": "repaired_execution_outcome",
                "response_received": "repaired_response_received",
                "response_summary": "repaired_response_summary",
                "protocol_reference": "repaired_protocol_reference",
                "evidence_path": "repaired_evidence_path",
            }
            for runtime_field, repair_field in replacements.items():
                repaired_value = _clean_text(repair_row.get(repair_field))
                if repaired_value is not None:
                    repaired_row[runtime_field] = repaired_value
            repaired_row["execution_notes"] = _append_note(
                runtime_row.get("execution_notes"),
                repair_row.get("repaired_execution_notes"),
            )
            repaired_row["repair_applied"] = "yes"
            repaired_row["repair_completed_at"] = (
                _clean_text(repair_row.get("repair_completed_at")) or ""
            )
            applied_repair_count += 1
        elif repair_row:
            pending_repair_count += 1

        repaired_runtime_rows.append(repaired_row)

    repair_log_fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "action_category",
        "dispatch_validation_outcome",
        "dispatch_validation_issue_codes",
        "original_execution_status",
        "original_execution_completed_at",
        "original_execution_channel_used",
        "original_execution_outcome",
        "original_response_received",
        "original_response_summary",
        "original_protocol_reference",
        "original_evidence_path",
        "repair_status",
        "repaired_execution_status",
        "repaired_execution_completed_at",
        "repaired_execution_channel_used",
        "repaired_execution_outcome",
        "repaired_response_received",
        "repaired_response_summary",
        "repaired_protocol_reference",
        "repaired_evidence_path",
        "repaired_execution_notes",
        "repair_completed_at",
        "repair_operator_notes",
        "repair_evidence_path",
        "repair_match_status",
    ]
    runtime_fieldnames = list(runtime_rows[0].keys()) if runtime_rows else []
    for extra_field in [
        "repair_status",
        "repair_validation_issue_codes",
        "repair_applied",
        "repair_completed_at",
    ]:
        if extra_field not in runtime_fieldnames:
            runtime_fieldnames.append(extra_field)

    _write_csv(repair_log_template_path, repair_log_rows, repair_log_fieldnames)
    _write_csv(repair_log_input, repair_log_rows, repair_log_fieldnames)
    _write_csv(repaired_runtime_queue_path, repaired_runtime_rows, runtime_fieldnames)
    _write_csv(unmatched_repair_log_path, unmatched_repair_log_rows, repair_log_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "runtime_row_count": len(runtime_rows),
        "repair_request_count": len(repair_queue_rows),
        "repair_log_row_count": len(repair_log_rows),
        "applied_repair_count": applied_repair_count,
        "pending_repair_count": pending_repair_count,
        "unmatched_repair_log_row_count": len(unmatched_repair_log_rows),
    }
    payload = {
        "signal_phase_dispatch_repair_recording_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_VERSION,
        "signal_phase_dispatch_repair_recording_bundle_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_execution_runtime_queue_path": str(runtime_input),
            "dispatch_log_repair_queue_path": str(repair_queue_input),
            "dispatch_log_repair_log_path": str(repair_log_input),
        },
        "outputs": {
            "dispatch_log_repair_log_template_path": str(repair_log_template_path),
            "dispatch_log_repair_log_path": str(repair_log_input),
            "dispatch_execution_queue_runtime_repaired_path": str(
                repaired_runtime_queue_path
            ),
            "unmatched_dispatch_log_repair_rows_path": str(unmatched_repair_log_path),
            "manifest_path": str(manifest_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    upstream_inputs = [
        _artifact_reference(
            "signal_phase_dispatch_execution_runtime_queue",
            runtime_input,
            _sha256(runtime_input),
        )
    ]
    if repair_queue_input.exists():
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_dispatch_repair_queue",
                repair_queue_input,
                _sha256(repair_queue_input),
            )
        )
    if preexisting_repair_log:
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_dispatch_repair_log",
                repair_log_input,
                _sha256(repair_log_input),
            )
        )

    manifest = {
        "signal_phase_dispatch_repair_recording_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_repair_recording_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_repair_recording_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_repair_recording_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "dispatch_log_repair_log_template_path": str(repair_log_template_path),
            "dispatch_log_repair_log_template_sha256": _sha256(repair_log_template_path),
            "dispatch_log_repair_log_path": str(repair_log_input),
            "dispatch_log_repair_log_sha256": _sha256(repair_log_input),
            "dispatch_execution_queue_runtime_repaired_path": str(
                repaired_runtime_queue_path
            ),
            "dispatch_execution_queue_runtime_repaired_sha256": _sha256(
                repaired_runtime_queue_path
            ),
            "unmatched_dispatch_log_repair_rows_path": str(unmatched_repair_log_path),
            "unmatched_dispatch_log_repair_rows_sha256": _sha256(
                unmatched_repair_log_path
            ),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        upstream_inputs=upstream_inputs,
        run_record_path=manifest_path,
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_recording_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_recording_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_log",
                repair_log_input,
                _sha256(repair_log_input),
            ),
            _artifact_reference(
                "signal_phase_dispatch_execution_runtime_queue_repaired",
                repaired_runtime_queue_path,
                _sha256(repaired_runtime_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_repair_recording_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_RECORDING_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
