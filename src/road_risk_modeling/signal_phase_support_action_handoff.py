"""Build Bari request-level support action handoff bundles from support action execution."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_VERSION = (
    "signal_phase_support_action_handoff_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_action_handoff_bundle_public_v1"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _handoff_mapping(
    row: dict[str, Any],
    *,
    support_runtime_cycle_manifest_path: Path,
) -> tuple[str, str, str, str]:
    execution_route = _clean_text(row.get("execution_route")) or ""
    workbook_path = _clean_text(row.get("dominant_workbook_path")) or ""
    delivery_csv_path = _clean_text(row.get("dominant_delivery_csv_path")) or ""
    validation_command = _clean_text(row.get("dominant_validation_command")) or ""
    runtime_command = _clean_text(row.get("runtime_command")) or ""
    request_packet_md_path = _clean_text(row.get("request_packet_md_path")) or ""
    packet_md_path = _clean_text(row.get("packet_md_path")) or ""

    if execution_route == "support_workbook_fill":
        return (
            "support_workbook_csv",
            workbook_path,
            validation_command,
            (
                f"Complete the analyst workbook, export `{delivery_csv_path or 'the request-scoped delivery CSV'}`, "
                f"then rerun `{runtime_command}`."
            ),
        )
    if execution_route == "support_runtime_rerun":
        return (
            "support_runtime_cycle_command",
            str(support_runtime_cycle_manifest_path),
            runtime_command,
            (
                f"Rerun `{runtime_command}` so the support-derived delivery can validate and, if accepted, "
                "flow into the movement-layer apply path."
            ),
        )
    if execution_route == "support_validation_review":
        return (
            "support_request_packet",
            request_packet_md_path or packet_md_path,
            runtime_command,
            (
                f"Review the validation context for this request, correct the workbook or delivery export, "
                f"then rerun `{runtime_command}`."
            ),
        )
    if execution_route == "support_workbook_repair":
        return (
            "support_workbook_csv",
            workbook_path,
            validation_command,
            (
                f"Repair the workbook or exported delivery, regenerate `{delivery_csv_path or 'the request-scoped delivery CSV'}`, "
                f"then rerun `{runtime_command}`."
            ),
        )
    return (
        "support_internal_hold",
        "",
        "",
        "No downstream support handoff is required right now.",
    )


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Action Handoff Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support-side request execution queue has been mapped to exact downstream workbook and runtime targets.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- handoff-ready requests: `{payload['summary']['handoff_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- workbook handoffs: `{payload['summary']['workbook_handoff_count']}`",
        f"- runtime-rerun handoffs: `{payload['summary']['runtime_rerun_handoff_count']}`",
        f"- validation-review handoffs: `{payload['summary']['validation_review_handoff_count']}`",
        f"- repair handoffs: `{payload['summary']['repair_handoff_count']}`",
        f"- apply-pending holds: `{payload['summary']['apply_pending_hold_count']}`",
        f"- complete holds: `{payload['summary']['complete_hold_count']}`",
        "",
        "## Ready Queue",
        "",
    ]
    for row in payload["handoff_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['handoff_target_kind']}` at `{row['handoff_target_path'] or 'n/a'}`"
        )
    if payload["internal_hold_queue"]:
        lines.extend(["", "## Holds", ""])
        for row in payload["internal_hold_queue"]:
            lines.append(
                f"- `{row['request_id']}` `{row['action_category']}` -> `{row['hold_reason']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_action_handoff_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_action_handoff/bari",
    signal_phase_support_action_execution_bundle_path: str | Path = "data/reporting/signal_phase_support_action_execution/bari/signal_phase_support_action_execution_bundle.json",
    support_runtime_cycle_manifest_path: str | Path = "data/processed/signal_phase_support_runtime_cycles/bari/signal_phase_support_runtime_cycle.manifest.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    action_execution_input = Path(signal_phase_support_action_execution_bundle_path)
    support_runtime_cycle_manifest_input = Path(support_runtime_cycle_manifest_path)

    action_execution_payload = _load_json(action_execution_input)
    execution_ready_rows = list(action_execution_payload.get("execution_ready_queue", []) or [])
    internal_hold_rows = list(action_execution_payload.get("internal_hold_queue", []) or [])

    handoff_ready_queue: list[dict[str, Any]] = []
    hold_queue: list[dict[str, Any]] = []

    for row in sorted(
        [item for item in execution_ready_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(item.get("priority_rank")),
            str(item.get("request_id") or ""),
        ),
    ):
        (
            handoff_target_kind,
            handoff_target_path,
            handoff_command,
            handoff_instructions,
        ) = _handoff_mapping(
            row,
            support_runtime_cycle_manifest_path=support_runtime_cycle_manifest_input,
        )
        handoff_ready_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "execution_target_kind": _clean_text(row.get("execution_target_kind")),
                "execution_target": _clean_text(row.get("execution_target")),
                "execution_summary": _clean_text(row.get("execution_summary")),
                "dominant_delivery_csv_path": _clean_text(row.get("dominant_delivery_csv_path")),
                "dominant_validation_command": _clean_text(
                    row.get("dominant_validation_command")
                ),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "handoff_target_kind": handoff_target_kind,
                "handoff_target_path": handoff_target_path,
                "handoff_reference_key": "request_id",
                "handoff_reference_value": _clean_text(row.get("request_id")),
                "handoff_command": handoff_command,
                "handoff_instructions": handoff_instructions,
                "handoff_status": "ready_for_operator",
            }
        )

    for row in sorted(
        [item for item in internal_hold_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(item.get("priority_rank")),
            str(item.get("request_id") or ""),
        ),
    ):
        hold_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "hold_reason": _clean_text(row.get("hold_reason")),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
            }
        )

    ready_queue_path = output_root / "action_handoff_queue.csv"
    hold_queue_path = output_root / "action_handoff_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_action_handoff_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_action_handoff_bundle.md"
    manifest_path = output_root / "signal_phase_support_action_handoff_bundle.manifest.json"

    ready_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "execution_route",
        "due_now",
        "dominant_profile_id",
        "execution_target_kind",
        "execution_target",
        "execution_summary",
        "dominant_delivery_csv_path",
        "dominant_validation_command",
        "request_packet_md_path",
        "packet_md_path",
        "handoff_target_kind",
        "handoff_target_path",
        "handoff_reference_key",
        "handoff_reference_value",
        "handoff_command",
        "handoff_instructions",
        "handoff_status",
    ]
    hold_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "execution_route",
        "due_now",
        "dominant_profile_id",
        "hold_reason",
        "request_packet_md_path",
        "packet_md_path",
    ]
    _write_csv(ready_queue_path, handoff_ready_queue, ready_fieldnames)
    _write_csv(hold_queue_path, hold_queue, hold_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(handoff_ready_queue) + len(hold_queue),
        "handoff_ready_count": len(handoff_ready_queue),
        "internal_hold_count": len(hold_queue),
        "workbook_handoff_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "support_workbook_csv"
        ),
        "runtime_rerun_handoff_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "support_runtime_cycle_command"
        ),
        "validation_review_handoff_count": sum(
            1
            for row in handoff_ready_queue
            if row["handoff_target_kind"] == "support_request_packet"
        ),
        "repair_handoff_count": sum(
            1
            for row in handoff_ready_queue
            if row["action_category"] == "repair_support_delivery"
        ),
        "apply_pending_hold_count": sum(
            1
            for row in hold_queue
            if row["action_category"] == "support_apply_pending_refresh"
        ),
        "complete_hold_count": sum(
            1 for row in hold_queue if row["action_category"] == "support_request_complete"
        ),
    }

    payload = {
        "signal_phase_support_action_handoff_bundle_version": SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_VERSION,
        "signal_phase_support_action_handoff_bundle_contract_version": SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "handoff_ready_queue": handoff_ready_queue,
        "internal_hold_queue": hold_queue,
        "inputs": {
            "signal_phase_support_action_execution_bundle_path": str(action_execution_input),
            "support_runtime_cycle_manifest_path": str(support_runtime_cycle_manifest_input),
        },
        "outputs": {
            "action_handoff_queue_path": str(ready_queue_path),
            "action_handoff_hold_queue_path": str(hold_queue_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_action_handoff_bundle_version": SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_action_handoff_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_CONTRACT_VERSION,
            "signal_phase_support_action_handoff_bundle_version": SIGNAL_PHASE_SUPPORT_ACTION_HANDOFF_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_action_handoff_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "action_handoff_queue_path": str(ready_queue_path),
            "action_handoff_queue_sha256": _sha256(ready_queue_path),
            "action_handoff_hold_queue_path": str(hold_queue_path),
            "action_handoff_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_action_execution_bundle_json",
                    action_execution_input,
                    _sha256(action_execution_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_support_action_handoff_queue",
                    ready_queue_path,
                    _sha256(ready_queue_path),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_hold_queue",
                    hold_queue_path,
                    _sha256(hold_queue_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
