"""Build analyst-ready Bari action queues from support-status outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_VERSION = "signal_phase_support_action_queue_v1"
SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_CONTRACT_VERSION = "signal_phase_support_action_queue_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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


def _profile_priority(row: dict[str, Any]) -> int:
    profile_id = _clean_text(row.get("profile_id")) or ""
    return 1 if profile_id == "arm_phase_mapping_sheet" else 2


def _profile_key(*, request_id: Any, profile_id: Any) -> tuple[str, str]:
    return (_clean_text(request_id) or "", _clean_text(profile_id) or "")


def _load_apply_status_lookup(bundle_path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if bundle_path is None:
        return {}
    bundle_payload = _load_json(bundle_path)
    support_apply_status_path = Path(str(bundle_payload.get("support_apply_status_path") or ""))
    if not str(support_apply_status_path).strip():
        raise RuntimeError("Support apply-status bundle must include support_apply_status_path.")
    return {
        _profile_key(request_id=row.get("request_id"), profile_id=row.get("profile_id")): row
        for row in _load_csv_rows(support_apply_status_path)
        if _profile_key(request_id=row.get("request_id"), profile_id=row.get("profile_id")) != ("", "")
    }


def _action_category(row: dict[str, Any], apply_status_row: dict[str, Any] | None = None) -> str:
    apply_status_category = _clean_text((apply_status_row or {}).get("apply_status_category")) or ""
    if apply_status_category == "applied_to_movement_layer":
        return "support_apply_complete"
    if apply_status_category == "accepted_for_ingestion_pending_apply":
        return "support_apply_pending_refresh"
    if apply_status_category == "validation_partial_review":
        return "review_support_validation_results"
    if apply_status_category == "validation_failed":
        return "repair_support_delivery"
    state = _clean_text(row.get("validation_state_category")) or ""
    if state in {"ready_for_validation", "partially_ready_for_validation"}:
        return "validate_support_delivery_now"
    if state == "waiting_for_analyst_resolution":
        return "fill_support_workbook_now"
    return "support_internal_hold"


def _execution_route(action_category: str) -> str:
    return {
        "validate_support_delivery_now": "validate_delivery",
        "fill_support_workbook_now": "analyst_workbook_fill",
        "review_support_validation_results": "analyst_validation_review",
        "repair_support_delivery": "analyst_workbook_repair",
    }.get(action_category, "")


def _action_summary(row: dict[str, Any], action_category: str) -> str:
    profile_id = _clean_text(row.get("profile_id")) or "support_profile"
    ready_row_count = _safe_int(row.get("ready_row_count"))
    pending_row_count = _safe_int(row.get("pending_row_count"))
    if action_category == "validate_support_delivery_now":
        return (
            f"Run delivery validation for `{profile_id}` using `{ready_row_count}` completed rows"
            + (f" while `{pending_row_count}` rows are still pending." if pending_row_count > 0 else ".")
        )
    if action_category == "fill_support_workbook_now":
        return f"Complete `{pending_row_count}` pending workbook rows for `{profile_id}` before validation."
    if action_category in {
        "support_apply_complete",
        "support_apply_pending_refresh",
        "review_support_validation_results",
        "repair_support_delivery",
    }:
        return _clean_text(row.get("apply_status_summary")) or (
            f"The `{profile_id}` profile is currently in `{action_category}` state."
        )
    return "No direct analyst execution is required for this support-derived profile right now."


def _operator_hint(action_category: str) -> str:
    if action_category == "validate_support_delivery_now":
        return "Run the generated support-derived validation command."
    if action_category == "fill_support_workbook_now":
        return "Fill the workbook rows, export the request-scoped delivery CSV, then re-run support status."
    if action_category == "review_support_validation_results":
        return "Review the validation output, resolve rejected rows, and rerun the support validation/apply path."
    if action_category == "repair_support_delivery":
        return "Correct the workbook or delivery export, then regenerate status and rerun support validation."
    if action_category == "support_apply_complete":
        return "No action is required unless live workbook rows change and you want to supersede the applied mapping."
    if action_category == "support_apply_pending_refresh":
        return "Inspect the support apply cycle and delivery-session outputs before attempting another validation run."
    return "Monitor this profile until it becomes actionable."


def _packet_markdown(row: dict[str, Any]) -> str:
    lines = [
        f"# {row['support_action_reference']}",
        "",
        f"- request: `{row['request_id']}`",
        f"- signal: `{row['signal_name']}`",
        f"- junction: `{row['junction_id']}`",
        f"- profile: `{row['profile_id']}`",
        f"- action: `{row['action_category']}`",
        f"- ready rows: `{row['ready_row_count']}`",
        f"- pending rows: `{row['pending_row_count']}`",
        "",
        "Paths:",
        "",
        f"- workbook: `{row['workbook_path']}`",
        f"- delivery csv: `{row['delivery_csv_path']}`",
        f"- mapping stub: `{row['mapping_stub_path']}`",
        "",
        "Next step:",
        "",
        row["operator_hint"],
    ]
    validation_command = _clean_text(row.get("validation_command"))
    if validation_command:
        lines.extend(["", "Validation command:", "", f"`{validation_command}`"])
    lines.append("")
    return "\n".join(lines)


def _markdown_report(
    summary: dict[str, Any],
    execution_rows: list[dict[str, Any]],
    hold_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Action Queue",
        "",
        "This bundle turns support-status outputs into profile-level analyst actions.",
        "",
        "## Summary",
        "",
        f"- profiles reviewed: `{summary['profile_count']}`",
        f"- execution-ready profiles: `{summary['execution_ready_count']}`",
        f"- workbook-fill actions: `{summary['workbook_fill_action_count']}`",
        f"- validation actions: `{summary['validation_action_count']}`",
        f"- validation-review actions: `{summary['validation_review_action_count']}`",
        f"- repair actions: `{summary['repair_action_count']}`",
        f"- already-applied profiles: `{summary['apply_complete_count']}`",
        f"- accepted pending apply: `{summary['apply_pending_count']}`",
        f"- internal holds: `{summary['internal_hold_count']}`",
        "",
        "## Queue",
        "",
    ]
    if execution_rows:
        for row in execution_rows[:10]:
            lines.append(
                f"- `{row['support_action_reference']}` `{row['action_category']}` "
                f"-> `{row['action_summary']}`"
            )
    else:
        lines.append("- No support-derived analyst actions are ready.")
    if hold_rows:
        lines.extend(["", "## Holds", ""])
        for row in hold_rows[:10]:
            lines.append(
                f"- `{row['support_action_reference']}` `{row['validation_state_category']}` "
                f"-> `{row['action_summary']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_action_queue(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_action_queue/bari",
    signal_phase_support_status_bundle_path: str | Path = "data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    signal_phase_support_apply_status_bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    status_bundle_input = Path(signal_phase_support_status_bundle_path)
    status_bundle = _load_json(status_bundle_input)
    apply_status_bundle_input = (
        Path(signal_phase_support_apply_status_bundle_path)
        if signal_phase_support_apply_status_bundle_path is not None
        else None
    )

    validation_ready_queue_path = Path(str(status_bundle.get("validation_ready_queue_path") or ""))
    validation_hold_queue_path = Path(str(status_bundle.get("validation_hold_queue_path") or ""))
    if not str(validation_ready_queue_path).strip() or not str(validation_hold_queue_path).strip():
        raise RuntimeError("Support-status bundle must include validation-ready and validation-hold queue paths.")

    ready_rows = _load_csv_rows(validation_ready_queue_path)
    hold_rows = _load_csv_rows(validation_hold_queue_path)
    input_rows = ready_rows + hold_rows
    apply_status_lookup = _load_apply_status_lookup(apply_status_bundle_input)

    execution_ready_rows: list[dict[str, Any]] = []
    internal_hold_rows: list[dict[str, Any]] = []
    packets_dir = output_root / "action_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    for row in sorted(
        input_rows,
        key=lambda item: (
            _safe_int(item.get("pending_row_count")),
            _profile_priority(item),
            str(item.get("request_id") or ""),
        ),
        reverse=True,
    ):
        request_id = _clean_text(row.get("request_id")) or ""
        profile_id = _clean_text(row.get("profile_id")) or ""
        apply_status_row = apply_status_lookup.get(
            _profile_key(request_id=request_id, profile_id=profile_id)
        )
        action_category = _action_category(row, apply_status_row)
        execution_route = _execution_route(action_category)
        action_row = {
            "support_action_reference": f"{request_id}:{profile_id}",
            "request_id": request_id,
            "junction_id": _clean_text(row.get("junction_id")) or "",
            "signal_name": _clean_text(row.get("signal_name")) or "",
            "profile_id": profile_id,
            "action_category": action_category,
            "execution_route": execution_route,
            "ready_row_count": _safe_int(row.get("ready_row_count")),
            "pending_row_count": _safe_int(row.get("pending_row_count")),
            "total_row_count": _safe_int(row.get("total_row_count")),
            "validation_state_category": _clean_text(row.get("validation_state_category")) or "",
            "due_now": "yes" if execution_route else "no",
            "workbook_path": _clean_text(row.get("workbook_path")) or "",
            "delivery_csv_path": _clean_text(row.get("delivery_csv_path")) or "",
            "mapping_stub_path": _clean_text(row.get("mapping_stub_path")) or "",
            "validation_command": _clean_text(row.get("validation_command")) or "",
            "next_action": _clean_text(row.get("next_action")) or "",
            "apply_status_category": _clean_text((apply_status_row or {}).get("apply_status_category"))
            or "",
            "apply_status_summary": _clean_text((apply_status_row or {}).get("action_summary")) or "",
            "apply_status_next_action": _clean_text((apply_status_row or {}).get("next_action"))
            or "",
            "validation_outcome": _clean_text((apply_status_row or {}).get("validation_outcome"))
            or "",
            "validation_manifest_path": _clean_text(
                (apply_status_row or {}).get("validation_manifest_path")
            )
            or "",
            "delivery_session_manifest_path": _clean_text(
                (apply_status_row or {}).get("delivery_session_manifest_path")
            )
            or "",
            "movement_signal_phase_manifest_path": _clean_text(
                (apply_status_row or {}).get("movement_signal_phase_manifest_path")
            )
            or "",
            "ingested_manifest_path": _clean_text(
                (apply_status_row or {}).get("ingested_manifest_path")
            )
            or "",
        }
        action_row["action_summary"] = _action_summary(action_row, action_category)
        action_row["operator_hint"] = _operator_hint(action_category)
        packet_path = packets_dir / f"{request_id}__{profile_id}.md"
        packet_path.write_text(_packet_markdown(action_row), encoding="utf-8")
        action_row["packet_md_path"] = str(packet_path)

        if execution_route:
            execution_ready_rows.append(action_row)
        else:
            internal_hold_rows.append(action_row)

    execution_ready_rows.sort(key=lambda row: (row["action_category"], row["profile_id"], row["request_id"]))
    internal_hold_rows.sort(key=lambda row: (row["validation_state_category"], row["profile_id"], row["request_id"]))

    execution_ready_path = output_root / "action_execution_ready_queue.csv"
    internal_hold_path = output_root / "action_internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_action_queue.json"
    bundle_md_path = output_root / "signal_phase_support_action_queue.md"
    manifest_path = output_root / "signal_phase_support_action_queue.manifest.json"

    fieldnames = [
        "support_action_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "profile_id",
        "action_category",
        "execution_route",
        "ready_row_count",
        "pending_row_count",
        "total_row_count",
        "validation_state_category",
        "due_now",
        "workbook_path",
        "delivery_csv_path",
        "mapping_stub_path",
        "validation_command",
        "next_action",
        "apply_status_category",
        "apply_status_summary",
        "apply_status_next_action",
        "validation_outcome",
        "validation_manifest_path",
        "delivery_session_manifest_path",
        "movement_signal_phase_manifest_path",
        "ingested_manifest_path",
        "action_summary",
        "operator_hint",
        "packet_md_path",
    ]
    _write_csv(execution_ready_path, execution_ready_rows, fieldnames)
    _write_csv(internal_hold_path, internal_hold_rows, fieldnames)

    summary = {
        "profile_count": len(input_rows),
        "execution_ready_count": len(execution_ready_rows),
        "workbook_fill_action_count": sum(1 for row in execution_ready_rows if row["action_category"] == "fill_support_workbook_now"),
        "validation_action_count": sum(1 for row in execution_ready_rows if row["action_category"] == "validate_support_delivery_now"),
        "validation_review_action_count": sum(1 for row in execution_ready_rows if row["action_category"] == "review_support_validation_results"),
        "repair_action_count": sum(1 for row in execution_ready_rows if row["action_category"] == "repair_support_delivery"),
        "apply_complete_count": sum(1 for row in internal_hold_rows if row["action_category"] == "support_apply_complete"),
        "apply_pending_count": sum(1 for row in internal_hold_rows if row["action_category"] == "support_apply_pending_refresh"),
        "internal_hold_count": len(internal_hold_rows),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_action_queue_version": SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_VERSION,
        "signal_phase_support_action_queue_contract_version": SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_CONTRACT_VERSION,
        "summary": summary,
        "action_execution_ready_queue": execution_ready_rows,
        "action_internal_hold_queue": internal_hold_rows,
        "action_execution_ready_queue_path": str(execution_ready_path),
        "action_internal_hold_queue_path": str(internal_hold_path),
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_markdown_report(summary, execution_ready_rows, internal_hold_rows), encoding="utf-8")

    manifest = {
        "source": {"adapter": "bari_signal_phase_support_action_queue_builder"},
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_action_queue_version": SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_ACTION_QUEUE_CONTRACT_VERSION,
        "inputs": {
            "signal_phase_support_status_bundle_path": str(status_bundle_input),
            "signal_phase_support_apply_status_bundle_path": (
                str(apply_status_bundle_input) if apply_status_bundle_input else None
            ),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(bundle_json_path),
            "report_json_sha256": _sha256(bundle_json_path),
            "report_md_path": str(bundle_md_path),
            "report_md_sha256": _sha256(bundle_md_path),
            "action_execution_ready_queue_path": str(execution_ready_path),
            "action_execution_ready_queue_sha256": _sha256(execution_ready_path),
            "action_internal_hold_queue_path": str(internal_hold_path),
            "action_internal_hold_queue_sha256": _sha256(internal_hold_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_support_status_bundle", status_bundle_input, _sha256(status_bundle_input)),
        ]
        + (
            [
                _artifact_reference(
                    "signal_phase_support_apply_status_bundle",
                    apply_status_bundle_input,
                    _sha256(apply_status_bundle_input),
                )
            ]
            if apply_status_bundle_input
            else []
        ),
        publishable_outputs=[
            _artifact_reference("signal_phase_support_action_queue_report", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_support_action_queue_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_support_action_execution_ready_queue_csv", execution_ready_path, _sha256(execution_ready_path)),
            _artifact_reference("signal_phase_support_action_internal_hold_queue_csv", internal_hold_path, _sha256(internal_hold_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
