"""Build Bari dispatch-log repair bundles from dispatch validation results."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_VERSION = "signal_phase_dispatch_repair_bundle_v1"
SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_repair_bundle_public_v1"
)
_REPAIR_OUTCOMES = {"rejected_for_writeback", "incomplete_operator_entry"}


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


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Repair Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari dispatch validation output has been collapsed into request-level repair actions.",
        "",
        "## Summary",
        "",
        f"- validated rows reviewed: `{payload['summary']['validated_row_count']}`",
        f"- repair-ready requests: `{payload['summary']['repair_request_count']}`",
        f"- blocked execution rows: `{payload['summary']['blocked_execution_count']}`",
        f"- incomplete operator rows: `{payload['summary']['incomplete_operator_entry_count']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_repair_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_repair/bari",
    dispatch_validation_queue_path: str | Path = "data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    validation_input = Path(dispatch_validation_queue_path)
    validated_rows = _read_csv_rows(validation_input)

    repair_rows: list[dict[str, Any]] = []
    repair_packet_dir = output_root / "repair_packets"
    repair_packet_dir.mkdir(parents=True, exist_ok=True)

    blocked_execution_count = 0
    incomplete_operator_entry_count = 0

    for row in validated_rows:
        outcome = _clean_text(row.get("dispatch_validation_outcome")) or ""
        if outcome not in _REPAIR_OUTCOMES:
            continue

        request_id = _clean_text(row.get("request_id")) or ""
        issue_codes = _clean_text(row.get("dispatch_validation_issue_codes")) or ""
        if outcome == "incomplete_operator_entry":
            blocked_execution_count += 0
            incomplete_operator_entry_count += 1
            action_category = "complete_dispatch_log_entry"
            repair_summary = "Complete the partially recorded send so validation can pass."
        else:
            blocked_execution_count += 1
            action_category = "repair_dispatch_log_now"
            repair_summary = "Correct the logged send fields that are blocking writeback."

        repair_md_path = repair_packet_dir / f"{request_id or 'unknown_request'}.md"
        repair_json_path = repair_packet_dir / f"{request_id or 'unknown_request'}.json"

        packet_payload = {
            "request_id": request_id,
            "dispatch_reference": _clean_text(row.get("dispatch_reference")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "action_category": action_category,
            "dispatch_validation_outcome": outcome,
            "dispatch_validation_issue_codes": issue_codes,
            "execution_status": _clean_text(row.get("execution_status")),
            "execution_completed_at": _clean_text(row.get("execution_completed_at")),
            "execution_channel_used": _clean_text(row.get("execution_channel_used")),
            "execution_outcome": _clean_text(row.get("execution_outcome")),
            "response_received": _clean_text(row.get("response_received")),
            "response_summary": _clean_text(row.get("response_summary")),
            "protocol_reference": _clean_text(row.get("protocol_reference")),
            "evidence_path": _clean_text(row.get("evidence_path")),
            "execution_packet_md_path": _clean_text(row.get("execution_packet_md_path")),
            "repair_summary": repair_summary,
        }
        repair_json_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
        repair_md_path.write_text(
            "\n".join(
                [
                    f"# Dispatch Repair Packet: {request_id}",
                    "",
                    f"- Signal: `{packet_payload['signal_name'] or 'unknown'}`",
                    f"- Outcome: `{outcome}`",
                    f"- Issue codes: `{issue_codes or 'none'}`",
                    f"- Required action: {repair_summary}",
                ]
            ),
            encoding="utf-8",
        )

        repair_rows.append(
            {
                "dispatch_reference": _clean_text(row.get("dispatch_reference")),
                "request_id": request_id,
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "action_category": action_category,
                "dispatch_validation_outcome": outcome,
                "dispatch_validation_issue_count": _clean_text(row.get("dispatch_validation_issue_count")) or "0",
                "dispatch_validation_issue_codes": issue_codes,
                "repair_summary": repair_summary,
                "repair_packet_md_path": str(repair_md_path),
                "repair_packet_json_path": str(repair_json_path),
            }
        )

    repair_queue_path = output_root / "dispatch_log_repair_queue.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_repair_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_repair_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_repair_bundle.manifest.json"

    _write_csv(
        repair_queue_path,
        repair_rows,
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
            "repair_packet_md_path",
            "repair_packet_json_path",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "validated_row_count": len(validated_rows),
        "repair_request_count": len(repair_rows),
        "blocked_execution_count": blocked_execution_count,
        "incomplete_operator_entry_count": incomplete_operator_entry_count,
    }
    payload = {
        "signal_phase_dispatch_repair_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_VERSION,
        "signal_phase_dispatch_repair_bundle_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_validation_queue_path": str(validation_input),
        },
        "outputs": {
            "repair_queue_path": str(repair_queue_path),
            "manifest_path": str(manifest_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_repair_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_repair_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_repair_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_repair_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "repair_queue_path": str(repair_queue_path),
            "repair_queue_sha256": _sha256(repair_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_dispatch_execution_validated_queue",
                validation_input,
                _sha256(validation_input),
            )
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_queue",
                repair_queue_path,
                _sha256(repair_queue_path),
            )
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_repair_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
