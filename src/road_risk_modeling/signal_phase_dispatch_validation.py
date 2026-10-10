"""Validate Bari dispatch execution runtime rows before writeback updates runtime state."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_VERSION = "signal_phase_dispatch_validation_bundle_v1"
SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_validation_bundle_public_v1"
)
_PENDING_EXECUTION_STATUSES = {"", "pending_execution"}
_TRUE_VALUES = {"1", "true", "yes", "y"}
_FALSE_VALUES = {"0", "false", "no", "n", ""}


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


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in _TRUE_VALUES


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


def _is_valid_iso_datetime(value: Any) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _execution_issues(row: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    status = _clean_text(row.get("execution_status"))
    completed_at = _clean_text(row.get("execution_completed_at"))
    channel_used = _clean_text(row.get("execution_channel_used"))
    outcome = _clean_text(row.get("execution_outcome"))
    response_received = (_clean_text(row.get("response_received")) or "no").lower()
    response_summary = _clean_text(row.get("response_summary"))
    protocol_reference = _clean_text(row.get("protocol_reference"))
    evidence_path = _clean_text(row.get("evidence_path"))

    if not status or status.lower() in _PENDING_EXECUTION_STATUSES:
        issues.append(
            {
                "issue_code": "missing_execution_status",
                "field_name": "execution_status",
                "issue_message": "Executed dispatch rows require a non-pending execution status.",
                "field_value": status or "",
            }
        )
    if not completed_at:
        issues.append(
            {
                "issue_code": "missing_execution_completed_at",
                "field_name": "execution_completed_at",
                "issue_message": "Executed dispatch rows require an execution timestamp.",
                "field_value": "",
            }
        )
    elif not _is_valid_iso_datetime(completed_at):
        issues.append(
            {
                "issue_code": "invalid_execution_completed_at",
                "field_name": "execution_completed_at",
                "issue_message": "Execution timestamps must be parseable ISO-8601 values.",
                "field_value": completed_at,
            }
        )
    if not channel_used:
        issues.append(
            {
                "issue_code": "missing_execution_channel_used",
                "field_name": "execution_channel_used",
                "issue_message": "Executed dispatch rows require the channel actually used.",
                "field_value": "",
            }
        )
    if not outcome:
        issues.append(
            {
                "issue_code": "missing_execution_outcome",
                "field_name": "execution_outcome",
                "issue_message": "Executed dispatch rows require an execution outcome.",
                "field_value": "",
            }
        )
    if not protocol_reference and not evidence_path:
        issues.append(
            {
                "issue_code": "missing_protocol_or_evidence",
                "field_name": "protocol_reference|evidence_path",
                "issue_message": "Executed dispatch rows require a protocol reference or evidence path.",
                "field_value": "",
            }
        )
    if response_received not in _TRUE_VALUES | _FALSE_VALUES:
        issues.append(
            {
                "issue_code": "invalid_response_received_flag",
                "field_name": "response_received",
                "issue_message": "response_received must be a yes/no style value.",
                "field_value": response_received,
            }
        )
    if response_received in _TRUE_VALUES and not response_summary:
        issues.append(
            {
                "issue_code": "missing_response_summary",
                "field_name": "response_summary",
                "issue_message": "Rows marked as having a response require a response summary.",
                "field_value": "",
            }
        )
    return issues


def _issue_rows(row: dict[str, Any], issues: list[dict[str, str]]) -> list[dict[str, Any]]:
    request_id = _clean_text(row.get("request_id")) or ""
    dispatch_reference = _clean_text(row.get("dispatch_reference")) or ""
    junction_id = _clean_text(row.get("junction_id")) or ""
    signal_name = _clean_text(row.get("signal_name")) or ""
    recording_status = _clean_text(row.get("recording_status")) or _recording_status(row)
    output: list[dict[str, Any]] = []
    for issue in issues:
        output.append(
            {
                "dispatch_reference": dispatch_reference,
                "request_id": request_id,
                "junction_id": junction_id,
                "signal_name": signal_name,
                "recording_status": recording_status,
                "issue_code": issue["issue_code"],
                "field_name": issue["field_name"],
                "issue_message": issue["issue_message"],
                "field_value": issue["field_value"],
            }
        )
    return output


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Validation Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari runtime dispatch queue from the operator log has been validated before writeback.",
        "",
        "## Summary",
        "",
        f"- runtime rows reviewed: `{payload['summary']['runtime_row_count']}`",
        f"- pending operator rows: `{payload['summary']['pending_operator_entry_count']}`",
        f"- incomplete operator rows: `{payload['summary']['incomplete_operator_entry_count']}`",
        f"- accepted executed rows: `{payload['summary']['accepted_for_writeback_count']}`",
        f"- blocked executed rows: `{payload['summary']['rejected_for_writeback_count']}`",
        f"- issue rows: `{payload['summary']['issue_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across runtime rows: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across runtime rows: `{payload['summary']['unresolved_signalized_crash_total']}`",
        f"- accepted unresolved signalized crashes: `{payload['summary']['accepted_unresolved_signalized_crash_total']}`",
        f"- blocked unresolved signalized crashes: `{payload['summary']['rejected_unresolved_signalized_crash_total']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_validation_bundle(
    *,
    output_dir: str | Path = "data/quality/signal_phase_dispatch_validation/bari",
    dispatch_execution_runtime_queue_path: str | Path = "data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_queue_runtime.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_input = Path(dispatch_execution_runtime_queue_path)
    runtime_rows = _read_csv_rows(runtime_input)

    validated_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []

    pending_operator_entry_count = 0
    incomplete_operator_entry_count = 0
    accepted_for_writeback_count = 0
    rejected_for_writeback_count = 0

    for row in runtime_rows:
        validated_row = dict(row)
        recording_status = _clean_text(row.get("recording_status")) or _recording_status(row)
        issues: list[dict[str, str]] = []

        if recording_status == "awaiting_operator_entry":
            outcome = "pending_operator_entry"
            writeback_eligible = "no"
            pending_operator_entry_count += 1
        elif recording_status in {"partial_operator_entry", "execution_logged_missing_status"}:
            outcome = "incomplete_operator_entry"
            writeback_eligible = "no"
            incomplete_operator_entry_count += 1
            issues.extend(_execution_issues(row))
        elif _is_executed_status(row.get("execution_status")):
            issues.extend(_execution_issues(row))
            if issues:
                outcome = "rejected_for_writeback"
                writeback_eligible = "no"
                rejected_for_writeback_count += 1
            else:
                outcome = "accepted_for_writeback"
                writeback_eligible = "yes"
                accepted_for_writeback_count += 1
        else:
            outcome = "pending_operator_entry"
            writeback_eligible = "no"
            pending_operator_entry_count += 1

        validated_row["recording_status"] = recording_status
        validated_row["dispatch_validation_outcome"] = outcome
        validated_row["writeback_eligible"] = writeback_eligible
        validated_row["dispatch_validation_issue_count"] = len(issues)
        validated_row["dispatch_validation_issue_codes"] = " | ".join(
            issue["issue_code"] for issue in issues
        )
        validated_rows.append(validated_row)
        issue_rows.extend(_issue_rows(validated_row, issues))

    validated_queue_path = output_root / "dispatch_execution_queue_validated.csv"
    issues_path = output_root / "dispatch_validation_issues.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_validation_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_validation_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_validation_bundle.manifest.json"

    fieldnames = list(runtime_rows[0].keys()) if runtime_rows else []
    for field in [
        "dispatch_validation_outcome",
        "writeback_eligible",
        "dispatch_validation_issue_count",
        "dispatch_validation_issue_codes",
    ]:
        if field not in fieldnames:
            fieldnames.append(field)

    _write_csv(validated_queue_path, validated_rows, fieldnames)
    _write_csv(
        issues_path,
        issue_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "recording_status",
            "issue_code",
            "field_name",
            "issue_message",
            "field_value",
        ],
    )

    accepted_rows = [
        row for row in validated_rows if row.get("dispatch_validation_outcome") == "accepted_for_writeback"
    ]
    rejected_rows = [
        row for row in validated_rows if row.get("dispatch_validation_outcome") == "rejected_for_writeback"
    ]

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "runtime_row_count": len(runtime_rows),
        "pending_operator_entry_count": pending_operator_entry_count,
        "incomplete_operator_entry_count": incomplete_operator_entry_count,
        "accepted_for_writeback_count": accepted_for_writeback_count,
        "rejected_for_writeback_count": rejected_for_writeback_count,
        "issue_count": len(issue_rows),
        "targets_with_unresolved_movements": sum(
            1 for row in validated_rows if _safe_int(row.get("unresolved_signalized_movement_count")) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in validated_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in validated_rows
        ),
        "accepted_unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in accepted_rows
        ),
        "accepted_unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in accepted_rows
        ),
        "rejected_unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in rejected_rows
        ),
        "rejected_unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in rejected_rows
        ),
    }
    payload = {
        "signal_phase_dispatch_validation_bundle_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_VERSION,
        "signal_phase_dispatch_validation_bundle_contract_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_execution_runtime_queue_path": str(runtime_input),
        },
        "outputs": {
            "validated_queue_path": str(validated_queue_path),
            "issues_path": str(issues_path),
            "manifest_path": str(manifest_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_validation_bundle_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_validation_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_validation_bundle_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_validation_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "validated_queue_path": str(validated_queue_path),
            "validated_queue_sha256": _sha256(validated_queue_path),
            "issues_path": str(issues_path),
            "issues_sha256": _sha256(issues_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_dispatch_execution_runtime_queue",
                runtime_input,
                _sha256(runtime_input),
            )
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_validation_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_validation_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_execution_validated_queue",
                validated_queue_path,
                _sha256(validated_queue_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_validation_issues",
                issues_path,
                _sha256(issues_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_validation_bundle_version": SIGNAL_PHASE_DISPATCH_VALIDATION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
