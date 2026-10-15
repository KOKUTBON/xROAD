"""Build request-level Bari analyst and validation queues from support-writeback outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_VERSION = "signal_phase_support_status_bundle_v1"
SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_CONTRACT_VERSION = "signal_phase_support_status_bundle_public_v1"


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


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _manual_row_ready(row: dict[str, Any]) -> bool:
    return all(
        _clean_text(row.get(field))
        for field in ("junction_id", "incoming_arm_id", "movement_turn", "phase_id", "stage_id", "protection_state")
    )


def _pedestrian_row_ready(row: dict[str, Any]) -> bool:
    return all(
        _clean_text(row.get(field))
        for field in ("junction_id", "node_object_id", "movement_turn", "phase_id", "stage_id", "protection_state")
    )


def _request_status_category(*, ready_total: int, pending_total: int, total_rows: int) -> str:
    if total_rows <= 0:
        return "no_resolution_rows"
    if pending_total > 0 and ready_total <= 0:
        return "pending_manual_resolution"
    if pending_total > 0 and ready_total > 0:
        return "partially_ready_for_validation"
    if pending_total <= 0 and ready_total > 0:
        return "ready_for_validation"
    return "unknown"


def _request_next_action(category: str) -> str:
    if category == "pending_manual_resolution":
        return "Continue filling the support-writeback workbooks before running delivery validation."
    if category == "partially_ready_for_validation":
        return "You can validate the completed delivery rows now or finish the remaining workbook rows first."
    if category == "ready_for_validation":
        return "Run the generated validation commands for the completed support-derived delivery rows."
    return "Review the support-writeback bundle and confirm whether this request still needs analyst work."


def _profile_queue_state(*, ready_row_count: int, pending_row_count: int, total_row_count: int) -> str:
    if total_row_count <= 0:
        return "no_rows"
    if ready_row_count > 0 and pending_row_count > 0:
        return "partially_ready_for_validation"
    if ready_row_count > 0 and pending_row_count <= 0:
        return "ready_for_validation"
    return "waiting_for_analyst_resolution"


def _profile_next_action(state: str) -> str:
    if state == "ready_for_validation":
        return "Run the generated validation command for this completed delivery export."
    if state == "partially_ready_for_validation":
        return "Validate the completed rows now or continue workbook completion to clear the remaining pending rows."
    if state == "waiting_for_analyst_resolution":
        return "Continue workbook completion for this profile before delivery validation."
    return "No workbook rows are currently associated with this profile."


def _request_packet(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {row['request_id']}",
            "",
            f"- signal: `{row['signal_name']}`",
            f"- junction: `{row['junction_id']}`",
            f"- status: `{row['request_status_category']}`",
            f"- manual rows ready/pending: `{row['manual_ready_count']}` / `{row['manual_pending_count']}`",
            f"- pedestrian rows ready/pending: `{row['pedestrian_ready_count']}` / `{row['pedestrian_pending_count']}`",
            f"- validation-ready profiles: `{row['validation_ready_profile_count']}`",
            f"- unresolved signalized movements: `{row['unresolved_signalized_movement_count']}` (`{row['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
            f"- unresolved signalized crashes: `{row['unresolved_signalized_crash_total']}` (`{row['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
            "",
            "Next step:",
            "",
            row["next_action"],
            "",
            "Workbook paths:",
            "",
            f"- manual: `{row['manual_workbook_path']}`",
            f"- pedestrian: `{row['pedestrian_workbook_path']}`",
            "",
        ]
    )


def _report_markdown(
    summary: dict[str, Any],
    request_rows: list[dict[str, Any]],
    validation_ready_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Status",
        "",
        "This bundle turns the support-writeback workbooks into request-level analyst status and validation-ready queues.",
        "",
        "## Summary",
        "",
        f"- support requests: `{summary['support_request_count']}`",
        f"- pending analyst requests: `{summary['requests_pending_manual_resolution_count']}`",
        f"- partially ready requests: `{summary['requests_partially_ready_for_validation_count']}`",
        f"- fully ready requests: `{summary['requests_ready_for_validation_count']}`",
        f"- requests with unresolved signalized movements: `{summary['requests_with_unresolved_signalized_movements_count']}`",
        f"- unresolved signalized movement rows: `{summary['unresolved_signalized_movement_count_total']}` (`{summary['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{summary['unresolved_signalized_crash_total']}` (`{summary['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        f"- analyst work queue rows: `{summary['analyst_work_queue_count']}`",
        f"- validation-ready profiles: `{summary['validation_ready_profile_count']}`",
        f"- validation-hold profiles: `{summary['validation_hold_profile_count']}`",
        "",
        "## Request Snapshot",
        "",
    ]
    if request_rows:
        for row in request_rows[:5]:
            lines.append(
                f"- `{row['request_id']}` `{row['request_status_category']}`: "
                f"`{row['manual_ready_count']}` manual ready / `{row['manual_pending_count']}` pending, "
                f"`{row['pedestrian_ready_count']}` pedestrian ready / `{row['pedestrian_pending_count']}` pending, "
                f"`{row['unresolved_signalized_movement_count']}` unresolved movements / "
                f"`{row['unresolved_signalized_crash_total']}` unresolved crashes"
            )
    else:
        lines.append("- No support-writeback requests were found.")
    lines.extend(["", "## Validation Queue", ""])
    if validation_ready_rows:
        for row in validation_ready_rows[:5]:
            lines.append(
                f"- `{row['request_id']}` `{row['profile_id']}` ready rows: `{row['ready_row_count']}` "
                f"(pending `{row['pending_row_count']}`)"
            )
    else:
        lines.append("- No support-derived profile deliveries are ready for validation yet.")
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_status_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_status/bari",
    signal_phase_support_writeback_bundle_path: str | Path = "data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    writeback_bundle_input = Path(signal_phase_support_writeback_bundle_path)
    writeback_bundle = _load_json(writeback_bundle_input)

    request_rows = writeback_bundle.get("request_writeback_status", [])
    if not isinstance(request_rows, list):
        raise RuntimeError("Support-writeback bundle must include a request_writeback_status list.")

    manual_workbook_path = Path(str(writeback_bundle.get("manual_mapping_workbook_path") or ""))
    pedestrian_workbook_path = Path(str(writeback_bundle.get("pedestrian_mapping_workbook_path") or ""))
    manual_delivery_path = Path(str(writeback_bundle.get("manual_delivery_path") or ""))
    pedestrian_delivery_path = Path(str(writeback_bundle.get("pedestrian_delivery_path") or ""))
    validation_commands_path = Path(str(writeback_bundle.get("validation_commands_path") or ""))
    if not all(
        str(path).strip()
        for path in (
            manual_workbook_path,
            pedestrian_workbook_path,
            manual_delivery_path,
            pedestrian_delivery_path,
            validation_commands_path,
        )
    ):
        raise RuntimeError("Support-writeback bundle is missing workbook, delivery, or validation command paths.")

    manual_workbook_rows = _load_csv_rows(manual_workbook_path)
    pedestrian_workbook_rows = _load_csv_rows(pedestrian_workbook_path)
    validation_command_rows = _load_csv_rows(validation_commands_path)

    request_status_path = output_root / "request_support_status.csv"
    analyst_work_queue_path = output_root / "analyst_work_queue.csv"
    validation_ready_queue_path = output_root / "validation_ready_queue.csv"
    validation_hold_queue_path = output_root / "validation_hold_queue.csv"
    request_packets_dir = output_root / "request_packets"
    request_packets_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = output_root / "signal_phase_support_status_bundle.json"
    report_md_path = output_root / "signal_phase_support_status_bundle.md"
    manifest_path = output_root / "signal_phase_support_status_bundle.manifest.json"

    command_lookup = {
        (_clean_text(row.get("request_id")) or "", _clean_text(row.get("profile_id")) or ""): row
        for row in validation_command_rows
    }

    request_status_rows: list[dict[str, Any]] = []
    analyst_work_queue_rows: list[dict[str, Any]] = []
    validation_ready_rows: list[dict[str, Any]] = []
    validation_hold_rows: list[dict[str, Any]] = []

    pending_request_count = 0
    partial_request_count = 0
    ready_request_count = 0

    for request_row in request_rows:
        if not isinstance(request_row, dict):
            continue
        request_id = _clean_text(request_row.get("request_id")) or ""
        junction_id = _clean_text(request_row.get("junction_id")) or ""
        signal_name = _clean_text(request_row.get("signal_name")) or ""
        signalized_movement_count = _safe_int(request_row.get("signalized_movement_count"))
        matched_crashes_at_junction_total = _safe_int(
            request_row.get("matched_crashes_at_junction_total")
        )
        unresolved_signalized_movement_count = _safe_int(
            request_row.get("unresolved_signalized_movement_count")
        )
        unresolved_signalized_crash_total = _safe_int(
            request_row.get("unresolved_signalized_crash_total")
        )

        request_manual_rows = [
            row for row in manual_workbook_rows if (_clean_text(row.get("request_id")) or "") == request_id
        ]
        request_pedestrian_rows = [
            row for row in pedestrian_workbook_rows if (_clean_text(row.get("request_id")) or "") == request_id
        ]

        manual_ready_count = sum(1 for row in request_manual_rows if _manual_row_ready(row))
        manual_pending_count = len(request_manual_rows) - manual_ready_count
        pedestrian_ready_count = sum(1 for row in request_pedestrian_rows if _pedestrian_row_ready(row))
        pedestrian_pending_count = len(request_pedestrian_rows) - pedestrian_ready_count

        profile_rows = [
            {
                "request_id": request_id,
                "junction_id": junction_id,
                "signal_name": signal_name,
                "profile_id": "arm_phase_mapping_sheet",
                "workbook_path": str(manual_workbook_path),
                "delivery_csv_path": _clean_text(request_row.get("manual_delivery_path")) or str(manual_delivery_path),
                "ready_row_count": manual_ready_count,
                "pending_row_count": manual_pending_count,
                "total_row_count": len(request_manual_rows),
            },
            {
                "request_id": request_id,
                "junction_id": junction_id,
                "signal_name": signal_name,
                "profile_id": "pedestrian_stage_mapping_sheet",
                "workbook_path": str(pedestrian_workbook_path),
                "delivery_csv_path": _clean_text(request_row.get("pedestrian_delivery_path")) or str(pedestrian_delivery_path),
                "ready_row_count": pedestrian_ready_count,
                "pending_row_count": pedestrian_pending_count,
                "total_row_count": len(request_pedestrian_rows),
            },
        ]

        validation_ready_profile_count = 0
        for profile_row in profile_rows:
            command_row = command_lookup.get((request_id, profile_row["profile_id"]), {})
            queue_row = {
                **profile_row,
                "mapping_stub_path": _clean_text(command_row.get("mapping_stub_path")) or "",
                "validation_command": _clean_text(command_row.get("validation_command")) or "",
            }
            queue_row["validation_state_category"] = _profile_queue_state(
                ready_row_count=int(profile_row["ready_row_count"]),
                pending_row_count=int(profile_row["pending_row_count"]),
                total_row_count=int(profile_row["total_row_count"]),
            )
            queue_row["next_action"] = _profile_next_action(queue_row["validation_state_category"])
            if int(profile_row["ready_row_count"]) > 0:
                validation_ready_profile_count += 1
                validation_ready_rows.append(queue_row)
            else:
                validation_hold_rows.append(queue_row)

        ready_total = manual_ready_count + pedestrian_ready_count
        pending_total = manual_pending_count + pedestrian_pending_count
        total_rows = len(request_manual_rows) + len(request_pedestrian_rows)
        category = _request_status_category(ready_total=ready_total, pending_total=pending_total, total_rows=total_rows)
        next_action = _request_next_action(category)

        request_status_row = {
            "request_id": request_id,
            "junction_id": junction_id,
            "signal_name": signal_name,
            "manual_workbook_row_count": len(request_manual_rows),
            "manual_ready_count": manual_ready_count,
            "manual_pending_count": manual_pending_count,
            "pedestrian_workbook_row_count": len(request_pedestrian_rows),
            "pedestrian_ready_count": pedestrian_ready_count,
            "pedestrian_pending_count": pedestrian_pending_count,
            "validation_ready_profile_count": validation_ready_profile_count,
            "signalized_movement_count": signalized_movement_count,
            "matched_crashes_at_junction_total": matched_crashes_at_junction_total,
            "unresolved_signalized_movement_count": unresolved_signalized_movement_count,
            "unresolved_signalized_crash_total": unresolved_signalized_crash_total,
            "unresolved_signalized_movement_share_pct": _safe_pct(
                unresolved_signalized_movement_count,
                signalized_movement_count,
            ),
            "unresolved_signalized_crash_coverage_pct": _safe_pct(
                unresolved_signalized_crash_total,
                matched_crashes_at_junction_total,
            ),
            "request_status_category": category,
            "next_action": next_action,
            "recommended_next_action": _clean_text(request_row.get("recommended_next_action")) or "",
            "manual_workbook_path": str(manual_workbook_path),
            "pedestrian_workbook_path": str(pedestrian_workbook_path),
            "manual_delivery_path": _clean_text(request_row.get("manual_delivery_path")) or str(manual_delivery_path),
            "pedestrian_delivery_path": _clean_text(request_row.get("pedestrian_delivery_path")) or str(pedestrian_delivery_path),
        }
        request_status_rows.append(request_status_row)
        if pending_total > 0:
            analyst_work_queue_rows.append(request_status_row)

        if category == "pending_manual_resolution":
            pending_request_count += 1
        elif category == "partially_ready_for_validation":
            partial_request_count += 1
        elif category == "ready_for_validation":
            ready_request_count += 1

        packet_path = request_packets_dir / f"{request_id}.md"
        packet_path.write_text(_request_packet(request_status_row), encoding="utf-8")

    request_status_rows.sort(key=lambda row: str(row["request_id"]))
    analyst_work_queue_rows.sort(key=lambda row: str(row["request_id"]))
    validation_ready_rows.sort(key=lambda row: (str(row["request_id"]), str(row["profile_id"])))
    validation_hold_rows.sort(key=lambda row: (str(row["request_id"]), str(row["profile_id"])))

    request_status_fields = [
        "request_id",
        "junction_id",
        "signal_name",
        "manual_workbook_row_count",
        "manual_ready_count",
        "manual_pending_count",
        "pedestrian_workbook_row_count",
        "pedestrian_ready_count",
        "pedestrian_pending_count",
        "validation_ready_profile_count",
        "signalized_movement_count",
        "matched_crashes_at_junction_total",
        "unresolved_signalized_movement_count",
        "unresolved_signalized_crash_total",
        "unresolved_signalized_movement_share_pct",
        "unresolved_signalized_crash_coverage_pct",
        "request_status_category",
        "next_action",
        "recommended_next_action",
        "manual_workbook_path",
        "pedestrian_workbook_path",
        "manual_delivery_path",
        "pedestrian_delivery_path",
    ]
    profile_queue_fields = [
        "request_id",
        "junction_id",
        "signal_name",
        "profile_id",
        "total_row_count",
        "ready_row_count",
        "pending_row_count",
        "validation_state_category",
        "next_action",
        "workbook_path",
        "delivery_csv_path",
        "mapping_stub_path",
        "validation_command",
    ]
    _write_csv(request_status_path, request_status_rows, request_status_fields)
    _write_csv(analyst_work_queue_path, analyst_work_queue_rows, request_status_fields)
    _write_csv(validation_ready_queue_path, validation_ready_rows, profile_queue_fields)
    _write_csv(validation_hold_queue_path, validation_hold_rows, profile_queue_fields)

    summary = {
        "support_request_count": len(request_status_rows),
        "requests_pending_manual_resolution_count": pending_request_count,
        "requests_partially_ready_for_validation_count": partial_request_count,
        "requests_ready_for_validation_count": ready_request_count,
        "requests_with_unresolved_signalized_movements_count": int(
            sum(
                1
                for row in request_status_rows
                if int(row["unresolved_signalized_movement_count"]) > 0
            )
        ),
        "unresolved_signalized_movement_count_total": int(
            sum(int(row["unresolved_signalized_movement_count"]) for row in request_status_rows)
        ),
        "unresolved_signalized_crash_total": int(
            sum(int(row["unresolved_signalized_crash_total"]) for row in request_status_rows)
        ),
        "unresolved_signalized_movement_share_pct": _safe_pct(
            int(
                sum(
                    int(row["unresolved_signalized_movement_count"])
                    for row in request_status_rows
                )
            ),
            int(sum(int(row["signalized_movement_count"]) for row in request_status_rows)),
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_crash_total"]) for row in request_status_rows)),
            int(
                sum(
                    int(row["matched_crashes_at_junction_total"])
                    for row in request_status_rows
                )
            ),
        ),
        "analyst_work_queue_count": len(analyst_work_queue_rows),
        "validation_ready_profile_count": len(validation_ready_rows),
        "validation_hold_profile_count": len(validation_hold_rows),
        "manual_ready_row_count": sum(int(row["manual_ready_count"]) for row in request_status_rows),
        "pedestrian_ready_row_count": sum(int(row["pedestrian_ready_count"]) for row in request_status_rows),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_status_bundle_version": SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_VERSION,
        "signal_phase_support_status_bundle_contract_version": SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "request_support_status": request_status_rows,
        "analyst_work_queue_path": str(analyst_work_queue_path),
        "validation_ready_queue_path": str(validation_ready_queue_path),
        "validation_hold_queue_path": str(validation_hold_queue_path),
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_report_markdown(summary, request_status_rows, validation_ready_rows), encoding="utf-8")

    manifest = {
        "source": {
            "adapter": "bari_signal_phase_support_status_bundle_builder",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_status_bundle_version": SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_STATUS_BUNDLE_CONTRACT_VERSION,
        "inputs": {
            "signal_phase_support_writeback_bundle_path": str(writeback_bundle_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "request_support_status_path": str(request_status_path),
            "request_support_status_sha256": _sha256(request_status_path),
            "analyst_work_queue_path": str(analyst_work_queue_path),
            "analyst_work_queue_sha256": _sha256(analyst_work_queue_path),
            "validation_ready_queue_path": str(validation_ready_queue_path),
            "validation_ready_queue_sha256": _sha256(validation_ready_queue_path),
            "validation_hold_queue_path": str(validation_hold_queue_path),
            "validation_hold_queue_sha256": _sha256(validation_hold_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_writeback_bundle",
                writeback_bundle_input,
                _sha256(writeback_bundle_input),
            )
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_support_status_report", report_json_path, _sha256(report_json_path)),
            _artifact_reference("signal_phase_support_status_markdown", report_md_path, _sha256(report_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_support_request_status_csv", request_status_path, _sha256(request_status_path)),
            _artifact_reference("signal_phase_support_analyst_work_queue_csv", analyst_work_queue_path, _sha256(analyst_work_queue_path)),
            _artifact_reference("signal_phase_support_validation_ready_queue_csv", validation_ready_queue_path, _sha256(validation_ready_queue_path)),
            _artifact_reference("signal_phase_support_validation_hold_queue_csv", validation_hold_queue_path, _sha256(validation_hold_queue_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
