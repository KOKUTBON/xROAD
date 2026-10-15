"""Build a request-level Bari support execution bundle from the support operator board."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_ACTION_EXECUTION_BUNDLE_VERSION = (
    "signal_phase_support_action_execution_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_action_execution_bundle_public_v1"
)

_EXECUTION_ROUTE_BY_ACTION = {
    "fill_support_workbook_now": "support_workbook_fill",
    "validate_support_delivery_now": "support_runtime_rerun",
    "review_support_validation_results": "support_validation_review",
    "repair_support_delivery": "support_workbook_repair",
}

_ACTION_PRIORITY = {
    "repair_support_delivery": 1,
    "review_support_validation_results": 2,
    "validate_support_delivery_now": 3,
    "fill_support_workbook_now": 4,
    "support_apply_pending_refresh": 5,
    "support_request_complete": 6,
    "support_internal_hold": 7,
}


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


def _priority_value(action_category: str) -> int:
    return _ACTION_PRIORITY.get(action_category, 999999)


def _execution_route(action_category: str) -> str:
    return _EXECUTION_ROUTE_BY_ACTION.get(action_category, "")


def _target_fields(row: dict[str, Any], action_category: str) -> tuple[str, str]:
    if action_category in {"fill_support_workbook_now", "repair_support_delivery"}:
        return ("support_workbook_csv", _clean_text(row.get("dominant_workbook_path")) or "")
    if action_category == "validate_support_delivery_now":
        return ("support_runtime_command", _clean_text(row.get("runtime_command")) or "")
    if action_category == "review_support_validation_results":
        return (
            "support_request_packet",
            _clean_text(row.get("request_packet_md_path"))
            or _clean_text(row.get("dominant_packet_md_path"))
            or "",
        )
    return ("", "")


def _execution_summary(action_category: str, row: dict[str, Any]) -> str:
    request_id = _clean_text(row.get("request_id")) or "support_request"
    profile_id = _clean_text(row.get("dominant_profile_id")) or "support_profile"
    if action_category == "fill_support_workbook_now":
        return (
            f"Open the support workbook for `{request_id}`, complete the remaining analyst rows, "
            f"starting with `{profile_id}`."
        )
    if action_category == "validate_support_delivery_now":
        return (
            f"Rerun the support runtime cycle for `{request_id}` so the ready support-derived deliveries can validate and apply."
        )
    if action_category == "review_support_validation_results":
        return (
            f"Review validation output for `{request_id}` and resolve any rejected support-derived rows before rerun."
        )
    if action_category == "repair_support_delivery":
        return (
            f"Repair the support workbook or exported delivery for `{request_id}`, then rerun the support runtime cycle."
        )
    return f"No execution step is required right now for `{request_id}`."


def _hold_reason(action_category: str) -> str:
    if action_category == "support_apply_pending_refresh":
        return "Accepted support-derived rows are waiting for apply-state refresh."
    if action_category == "support_request_complete":
        return "The support request is already fully applied to the movement layer."
    return "No request-level support execution is required right now."


def _packet_markdown(row: dict[str, Any]) -> str:
    lines = [
        f"# {row['request_id']}",
        "",
        f"- signal: `{row['signal_name']}`",
        f"- junction: `{row['junction_id']}`",
        f"- action: `{row['action_category']}`",
        f"- execution route: `{row['execution_route']}`",
        f"- target kind: `{row['execution_target_kind']}`",
        f"- dominant profile: `{row['dominant_profile_id']}`",
        "",
        "Execution target:",
        "",
        f"`{row['execution_target']}`" if row["execution_target"] else "`n/a`",
        "",
        "Next step:",
        "",
        row["execution_summary"] if row["execution_route"] else row["hold_reason"],
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(
    summary: dict[str, Any],
    execution_ready_queue: list[dict[str, Any]],
    internal_hold_queue: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Action Execution Bundle",
        "",
        "This bundle converts the request-level support operator board into an execution-ready queue plus a hold queue.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{summary['request_count']}`",
        f"- execution-ready requests: `{summary['execution_ready_count']}`",
        f"- internal holds: `{summary['internal_hold_count']}`",
        f"- workbook-fill requests: `{summary['workbook_fill_request_count']}`",
        f"- runtime-rerun requests: `{summary['runtime_rerun_request_count']}`",
        f"- validation-review requests: `{summary['validation_review_request_count']}`",
        f"- repair requests: `{summary['repair_request_count']}`",
        f"- apply-pending holds: `{summary['apply_pending_hold_count']}`",
        f"- complete holds: `{summary['complete_hold_count']}`",
        "",
        "## Execution Queue",
        "",
    ]
    if execution_ready_queue:
        for row in execution_ready_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['execution_summary']}`"
            )
    else:
        lines.append("- No support requests are execution-ready.")
    if internal_hold_queue:
        lines.extend(["", "## Holds", ""])
        for row in internal_hold_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['action_category']}` -> `{row['hold_reason']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_action_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_action_execution/bari",
    signal_phase_support_operator_board_bundle_path: str | Path = "data/reporting/signal_phase_support_operator_board/bari/signal_phase_support_operator_board_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    operator_board_input = Path(signal_phase_support_operator_board_bundle_path)
    operator_board_payload = _load_json(operator_board_input)

    ready_rows = operator_board_payload.get("operator_ready_queue", [])
    if not isinstance(ready_rows, list):
        raise RuntimeError("Support operator board must expose operator_ready_queue.")
    hold_rows = operator_board_payload.get("operator_hold_queue", [])
    if not isinstance(hold_rows, list):
        raise RuntimeError("Support operator board must expose operator_hold_queue.")

    execution_ready_queue: list[dict[str, Any]] = []
    internal_hold_queue: list[dict[str, Any]] = []
    packets_dir = output_root / "execution_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    for row in sorted(
        [item for item in ready_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(_clean_text(item.get("operator_action_category")) or ""),
            _clean_text(item.get("request_id")) or "",
        ),
    ):
        action_category = _clean_text(row.get("operator_action_category")) or ""
        execution_route = _execution_route(action_category)
        target_kind, target_value = _target_fields(row, action_category)
        payload = {
            "support_request_reference": _clean_text(row.get("support_request_reference")),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "request_runtime_category": _clean_text(row.get("request_runtime_category")),
            "action_category": action_category,
            "execution_route": execution_route,
            "due_now": _clean_text(row.get("due_now")) or "no",
            "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
            "dominant_workbook_path": _clean_text(row.get("dominant_workbook_path")),
            "dominant_delivery_csv_path": _clean_text(row.get("dominant_delivery_csv_path")),
            "dominant_validation_command": _clean_text(row.get("dominant_validation_command")),
            "dominant_packet_md_path": _clean_text(row.get("dominant_packet_md_path")),
            "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
            "runtime_command": _clean_text(row.get("runtime_command")),
            "operator_summary": _clean_text(row.get("operator_summary")),
            "operator_hint": _clean_text(row.get("operator_hint")),
            "execution_target_kind": target_kind,
            "execution_target": target_value,
        }
        payload["execution_summary"] = _execution_summary(action_category, row)
        packet_path = packets_dir / f"{payload['request_id']}.md"
        packet_path.write_text(_packet_markdown(payload), encoding="utf-8")
        payload["packet_md_path"] = str(packet_path)
        execution_ready_queue.append(payload)

    for row in sorted(
        [item for item in hold_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(_clean_text(item.get("operator_action_category")) or ""),
            _clean_text(item.get("request_id")) or "",
        ),
    ):
        action_category = _clean_text(row.get("operator_action_category")) or ""
        payload = {
            "support_request_reference": _clean_text(row.get("support_request_reference")),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "request_runtime_category": _clean_text(row.get("request_runtime_category")),
            "action_category": action_category,
            "execution_route": "",
            "due_now": _clean_text(row.get("due_now")) or "no",
            "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
            "execution_target_kind": "",
            "execution_target": "",
            "hold_reason": _hold_reason(action_category),
            "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
        }
        packet_path = packets_dir / f"{payload['request_id']}.md"
        packet_path.write_text(_packet_markdown(payload), encoding="utf-8")
        payload["packet_md_path"] = str(packet_path)
        internal_hold_queue.append(payload)

    ready_queue_path = output_root / "action_execution_ready_queue.csv"
    hold_queue_path = output_root / "action_internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_action_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_action_execution_bundle.md"
    manifest_path = output_root / "signal_phase_support_action_execution_bundle.manifest.json"

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
        "dominant_workbook_path",
        "dominant_delivery_csv_path",
        "dominant_validation_command",
        "dominant_packet_md_path",
        "request_packet_md_path",
        "runtime_command",
        "operator_summary",
        "operator_hint",
        "execution_target_kind",
        "execution_target",
        "execution_summary",
        "packet_md_path",
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
        "execution_target_kind",
        "execution_target",
        "hold_reason",
        "request_packet_md_path",
        "packet_md_path",
    ]
    _write_csv(ready_queue_path, execution_ready_queue, ready_fieldnames)
    _write_csv(hold_queue_path, internal_hold_queue, hold_fieldnames)

    summary = {
        "request_count": len(execution_ready_queue) + len(internal_hold_queue),
        "execution_ready_count": len(execution_ready_queue),
        "internal_hold_count": len(internal_hold_queue),
        "workbook_fill_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_workbook_fill"
        ),
        "runtime_rerun_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_runtime_rerun"
        ),
        "validation_review_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_validation_review"
        ),
        "repair_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_workbook_repair"
        ),
        "apply_pending_hold_count": sum(
            1
            for row in internal_hold_queue
            if row["action_category"] == "support_apply_pending_refresh"
        ),
        "complete_hold_count": sum(
            1
            for row in internal_hold_queue
            if row["action_category"] == "support_request_complete"
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_action_execution_bundle_version": SIGNAL_PHASE_SUPPORT_ACTION_EXECUTION_BUNDLE_VERSION,
        "signal_phase_support_action_execution_bundle_contract_version": SIGNAL_PHASE_SUPPORT_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "execution_ready_queue": execution_ready_queue,
        "internal_hold_queue": internal_hold_queue,
        "execution_ready_queue_path": str(ready_queue_path),
        "internal_hold_queue_path": str(hold_queue_path),
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(
        _bundle_markdown(summary, execution_ready_queue, internal_hold_queue),
        encoding="utf-8",
    )

    manifest = {
        "contract": {
            "resource_name": "signal_phase_support_action_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
        },
        "source": {"adapter": "bari_signal_phase_support_action_execution_builder"},
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "signal_phase_support_operator_board_bundle_path": str(operator_board_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(bundle_json_path),
            "report_json_sha256": _sha256(bundle_json_path),
            "report_md_path": str(bundle_md_path),
            "report_md_sha256": _sha256(bundle_md_path),
            "execution_ready_queue_path": str(ready_queue_path),
            "execution_ready_queue_sha256": _sha256(ready_queue_path),
            "internal_hold_queue_path": str(hold_queue_path),
            "internal_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_operator_board_bundle",
                operator_board_input,
                _sha256(operator_board_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_action_execution_report",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_action_execution_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_support_action_execution_ready_queue_csv",
                ready_queue_path,
                _sha256(ready_queue_path),
            ),
            _artifact_reference(
                "signal_phase_support_action_internal_hold_queue_csv",
                hold_queue_path,
                _sha256(hold_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
