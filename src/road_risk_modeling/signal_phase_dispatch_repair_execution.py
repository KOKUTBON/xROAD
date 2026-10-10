"""Build Bari dispatch-log repair execution bundles."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_VERSION = (
    "signal_phase_dispatch_repair_execution_bundle_v1"
)
SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_repair_execution_bundle_public_v1"
)
_TERMINAL_REPAIR_STATUSES = {"ready_for_validation", "completed_after_repair", "completed"}


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


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _issue_code_guidance(issue_codes: str | None) -> str:
    if not issue_codes:
        return "Confirm the corrected runtime values and mark the repair row ready for validation."
    guidance_parts: list[str] = []
    issue_tokens = [token.strip() for token in issue_codes.split("|") if token.strip()]
    mapping = {
        "missing_execution_status": "set `repaired_execution_status`",
        "missing_execution_completed_at": "set `repaired_execution_completed_at`",
        "invalid_execution_completed_at": "replace `repaired_execution_completed_at` with a valid ISO timestamp",
        "missing_execution_channel_used": "set `repaired_execution_channel_used`",
        "missing_execution_outcome": "set `repaired_execution_outcome`",
        "missing_protocol_or_evidence": "set `repaired_protocol_reference` or `repaired_evidence_path`",
        "invalid_response_received_flag": "set `repaired_response_received` to a yes/no value",
        "missing_response_summary": "set `repaired_response_summary`",
    }
    for token in issue_tokens:
        guidance = mapping.get(token)
        if guidance:
            guidance_parts.append(guidance)
    if not guidance_parts:
        return "Update the repaired dispatch fields and evidence, then mark the repair row ready for validation."
    return "; ".join(guidance_parts)


def _execution_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Dispatch Repair Execution: {packet['request_id']}",
        "",
        "## Repair Summary",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Validation outcome: `{packet['dispatch_validation_outcome']}`",
        f"- Issue codes: `{packet['dispatch_validation_issue_codes'] or 'none'}`",
        f"- Current repair status: `{packet['repair_status']}`",
        "",
        "## Original Runtime Values",
        "",
        f"- execution status: `{packet['original_execution_status']}`",
        f"- completed at: `{packet['original_execution_completed_at']}`",
        f"- channel used: `{packet['original_execution_channel_used']}`",
        f"- outcome: `{packet['original_execution_outcome']}`",
        f"- protocol reference: `{packet['original_protocol_reference']}`",
        f"- evidence path: `{packet['original_evidence_path']}`",
        "",
        "## Required Repair",
        "",
        f"- requested action: {packet['repair_summary']}",
        f"- field guidance: {packet['field_guidance']}",
        "",
        "## After Repair",
        "",
        "- update the matching row in `dispatch_log_repair_log.csv`",
        "- set `repair_status` to `ready_for_validation` once the corrected fields are complete",
        "- rerun the Bari runtime cycle or the dispatch validation bundle",
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Repair Execution Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari dispatch repair queue has been filtered into execution-ready repair work and held rows.",
        "",
        "## Summary",
        "",
        f"- repair requests reviewed: `{payload['summary']['request_count']}`",
        f"- execution-ready repair rows: `{payload['summary']['execution_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- pending repair rows: `{payload['summary']['pending_repair_count']}`",
        f"- ready-for-validation rows: `{payload['summary']['ready_for_validation_count']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_repair_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_repair_execution/bari",
    dispatch_log_repair_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    dispatch_log_repair_log_path: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "repair_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    repair_queue_input = Path(dispatch_log_repair_queue_path)
    repair_log_input = Path(dispatch_log_repair_log_path)

    repair_queue_rows = _read_csv_rows(repair_queue_input) if repair_queue_input.exists() else []
    repair_log_rows = _read_csv_rows(repair_log_input) if repair_log_input.exists() else []
    repair_log_by_request = {
        str(row.get("request_id") or ""): row for row in repair_log_rows if row.get("request_id")
    }

    execution_ready_rows: list[dict[str, Any]] = []
    internal_hold_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for repair_row in sorted(
        repair_queue_rows,
        key=lambda row: (_priority_value(row.get("priority_rank")), str(row.get("request_id") or "")),
    ):
        request_id = str(repair_row.get("request_id") or "")
        repair_log_row = repair_log_by_request.get(request_id, {})
        repair_status = _clean_text(repair_log_row.get("repair_status")) or "pending_repair"
        packet_payload = {
            "dispatch_reference": _clean_text(repair_row.get("dispatch_reference")),
            "request_id": request_id,
            "junction_id": _clean_text(repair_row.get("junction_id")),
            "signal_name": _clean_text(repair_row.get("signal_name")),
            "action_category": _clean_text(repair_row.get("action_category")) or "repair_dispatch_log_now",
            "dispatch_validation_outcome": _clean_text(
                repair_row.get("dispatch_validation_outcome")
            )
            or "",
            "dispatch_validation_issue_count": _safe_int(
                repair_row.get("dispatch_validation_issue_count")
            ),
            "dispatch_validation_issue_codes": _clean_text(
                repair_row.get("dispatch_validation_issue_codes")
            )
            or "",
            "repair_summary": _clean_text(repair_row.get("repair_summary"))
            or "Repair the logged dispatch row and rerun validation.",
            "repair_status": repair_status,
            "original_execution_status": _clean_text(repair_log_row.get("original_execution_status"))
            or "",
            "original_execution_completed_at": _clean_text(
                repair_log_row.get("original_execution_completed_at")
            )
            or "",
            "original_execution_channel_used": _clean_text(
                repair_log_row.get("original_execution_channel_used")
            )
            or "",
            "original_execution_outcome": _clean_text(
                repair_log_row.get("original_execution_outcome")
            )
            or "",
            "original_protocol_reference": _clean_text(
                repair_log_row.get("original_protocol_reference")
            )
            or "",
            "original_evidence_path": _clean_text(repair_log_row.get("original_evidence_path"))
            or "",
        }
        packet_payload["field_guidance"] = _issue_code_guidance(
            packet_payload["dispatch_validation_issue_codes"]
        )
        packet_base = _slugify(request_id or "unknown_request")
        packet_md_path = packet_dir / f"{packet_base}.md"
        packet_json_path = packet_dir / f"{packet_base}.json"
        packet_md_path.write_text(_execution_packet_markdown(packet_payload), encoding="utf-8")
        packet_json_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
        packet_paths.extend([str(packet_md_path), str(packet_json_path)])

        row_payload = {
            **packet_payload,
            "due_now": "yes",
            "repair_packet_md_path": str(packet_md_path),
            "repair_packet_json_path": str(packet_json_path),
        }
        if repair_status.lower() in _TERMINAL_REPAIR_STATUSES:
            internal_hold_rows.append(
                {
                    "dispatch_reference": row_payload["dispatch_reference"],
                    "request_id": request_id,
                    "junction_id": row_payload["junction_id"],
                    "signal_name": row_payload["signal_name"],
                    "action_category": row_payload["action_category"],
                    "repair_status": repair_status,
                    "hold_reason": "Repair is already staged for validation; rerun validation or the runtime cycle instead of editing the row again.",
                    "repair_packet_md_path": str(packet_md_path),
                }
            )
        else:
            execution_ready_rows.append(row_payload)

    execution_ready_path = output_root / "dispatch_repair_execution_ready_queue.csv"
    internal_hold_path = output_root / "dispatch_repair_internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_repair_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_repair_execution_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_repair_execution_bundle.manifest.json"

    _write_csv(
        execution_ready_path,
        execution_ready_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "action_category",
            "dispatch_validation_outcome",
            "dispatch_validation_issue_count",
            "dispatch_validation_issue_codes",
            "repair_summary",
            "repair_status",
            "original_execution_status",
            "original_execution_completed_at",
            "original_execution_channel_used",
            "original_execution_outcome",
            "original_protocol_reference",
            "original_evidence_path",
            "field_guidance",
            "due_now",
            "repair_packet_md_path",
            "repair_packet_json_path",
        ],
    )
    _write_csv(
        internal_hold_path,
        internal_hold_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "action_category",
            "repair_status",
            "hold_reason",
            "repair_packet_md_path",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(repair_queue_rows),
        "execution_ready_count": len(execution_ready_rows),
        "internal_hold_count": len(internal_hold_rows),
        "pending_repair_count": sum(
            1
            for row in execution_ready_rows
            if (_clean_text(row.get("repair_status")) or "pending_repair").lower()
            not in _TERMINAL_REPAIR_STATUSES
        ),
        "ready_for_validation_count": sum(
            1
            for row in internal_hold_rows
            if (_clean_text(row.get("repair_status")) or "").lower() == "ready_for_validation"
        ),
    }
    payload = {
        "signal_phase_dispatch_repair_execution_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_VERSION,
        "signal_phase_dispatch_repair_execution_bundle_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_log_repair_queue_path": str(repair_queue_input),
            "dispatch_log_repair_log_path": str(repair_log_input),
        },
        "outputs": {
            "dispatch_repair_execution_ready_queue_path": str(execution_ready_path),
            "dispatch_repair_internal_hold_queue_path": str(internal_hold_path),
            "manifest_path": str(manifest_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    upstream_inputs = []
    if repair_queue_input.exists():
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_dispatch_repair_queue",
                repair_queue_input,
                _sha256(repair_queue_input),
            )
        )
    if repair_log_input.exists():
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_dispatch_repair_log",
                repair_log_input,
                _sha256(repair_log_input),
            )
        )

    manifest = {
        "signal_phase_dispatch_repair_execution_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_repair_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_repair_execution_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_repair_execution_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "dispatch_repair_execution_ready_queue_path": str(execution_ready_path),
            "dispatch_repair_execution_ready_queue_sha256": _sha256(execution_ready_path),
            "dispatch_repair_internal_hold_queue_path": str(internal_hold_path),
            "dispatch_repair_internal_hold_queue_sha256": _sha256(internal_hold_path),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        upstream_inputs=upstream_inputs,
        run_record_path=manifest_path,
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_execution_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_execution_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_execution_ready_queue",
                execution_ready_path,
                _sha256(execution_ready_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_internal_hold_queue",
                internal_hold_path,
                _sha256(internal_hold_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_repair_execution_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_EXECUTION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
