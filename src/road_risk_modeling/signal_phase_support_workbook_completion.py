"""Build row-level completion queues for live Bari support workbooks."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_WORKBOOK_COMPLETION_BUNDLE_VERSION = (
    "signal_phase_support_workbook_completion_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_WORKBOOK_COMPLETION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_workbook_completion_bundle_public_v1"
)

WORKBOOK_COMPLETION_ROUTES = {
    "support_workbook_fill",
    "support_workbook_repair",
}

WORKBOOK_COMPLETION_QUEUE_FIELDS = [
    "request_id",
    "profile_id",
    "row_number",
    "junction_id",
    "signal_name",
    "signal_type",
    "movement_turn",
    "incoming_arm_id",
    "node_object_id",
    "required_fields_missing",
    "recommended_fields_missing",
    "phase_id_current",
    "stage_id_current",
    "protection_state_current",
    "outgoing_arm_id_current",
    "pedestrian_stage_flag_current",
    "candidate_target_arm_catalog",
    "source_crash_total",
    "source_injury_total",
    "source_peak_year",
    "source_peak_year_crash_count",
    "support_artifact_path",
    "validation_manifest_path",
    "workbook_path",
    "delivery_csv_path",
    "manual_mapping_hint",
    "execution_route",
    "execution_summary",
    "completion_packet_md_path",
    "completion_priority_rank",
]

NON_WORKBOOK_EXECUTION_QUEUE_FIELDS = [
    "support_request_reference",
    "request_id",
    "junction_id",
    "signal_name",
    "final_action_category",
    "execution_route",
    "execution_target_kind",
    "execution_target",
    "execution_summary",
    "execution_packet_md_path",
]

WORKBOOK_COMPLETION_HOLD_QUEUE_FIELDS = [
    "support_request_reference",
    "request_id",
    "junction_id",
    "signal_name",
    "final_action_category",
    "hold_reason",
    "execution_packet_md_path",
]


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


def _required_fields_missing(
    row: dict[str, Any],
    required_fields: tuple[str, ...] = ("phase_id", "stage_id", "protection_state"),
) -> list[str]:
    return [field for field in required_fields if not _clean_text(row.get(field))]


def _recommended_fields_missing(row: dict[str, Any], *, profile_id: str) -> list[str]:
    if profile_id != "arm_phase_mapping_sheet":
        return []
    if _clean_text(row.get("outgoing_arm_id")):
        return []
    if _clean_text(row.get("source_candidate_target_arm_catalog")):
        return ["outgoing_arm_id"]
    return []


def _workbook_path(writeback_payload: dict[str, Any], *names: str) -> Path:
    for name in names:
        value = _clean_text(writeback_payload.get(name))
        if value:
            return Path(value)
    raise RuntimeError(f"Missing workbook path in support writeback bundle: {names}")


def _workbook_request_rows(
    runtime_action_execution_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    ready_rows = runtime_action_execution_payload.get("execution_ready_queue", [])
    if not isinstance(ready_rows, list):
        raise RuntimeError(
            "Support runtime action execution bundle must expose execution_ready_queue."
        )
    return [
        row
        for row in ready_rows
        if isinstance(row, dict)
        and (_clean_text(row.get("execution_route")) or "") in WORKBOOK_COMPLETION_ROUTES
    ]


def _non_workbook_execution_rows(
    runtime_action_execution_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    ready_rows = runtime_action_execution_payload.get("execution_ready_queue", [])
    if not isinstance(ready_rows, list):
        raise RuntimeError(
            "Support runtime action execution bundle must expose execution_ready_queue."
        )
    return [
        _normalise_non_workbook_row(row)
        for row in ready_rows
        if isinstance(row, dict)
        and (_clean_text(row.get("execution_route")) or "")
        not in WORKBOOK_COMPLETION_ROUTES
    ]


def _hold_rows(
    runtime_action_execution_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = runtime_action_execution_payload.get("internal_hold_queue", [])
    if not isinstance(rows, list):
        raise RuntimeError(
            "Support runtime action execution bundle must expose internal_hold_queue."
        )
    return [_normalise_hold_row(row) for row in rows if isinstance(row, dict)]


def _normalise_non_workbook_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "support_request_reference": _clean_text(row.get("support_request_reference")) or "",
        "request_id": _clean_text(row.get("request_id")) or "",
        "junction_id": _clean_text(row.get("junction_id")) or "",
        "signal_name": _clean_text(row.get("signal_name")) or "",
        "final_action_category": _clean_text(row.get("final_action_category")) or "",
        "execution_route": _clean_text(row.get("execution_route")) or "",
        "execution_target_kind": _clean_text(row.get("execution_target_kind")) or "",
        "execution_target": _clean_text(row.get("execution_target")) or "",
        "execution_summary": _clean_text(row.get("execution_summary")) or "",
        "execution_packet_md_path": _clean_text(row.get("execution_packet_md_path")) or "",
    }


def _normalise_hold_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "support_request_reference": _clean_text(row.get("support_request_reference")) or "",
        "request_id": _clean_text(row.get("request_id")) or "",
        "junction_id": _clean_text(row.get("junction_id")) or "",
        "signal_name": _clean_text(row.get("signal_name")) or "",
        "final_action_category": _clean_text(row.get("final_action_category")) or "",
        "hold_reason": _clean_text(row.get("hold_reason")) or "",
        "execution_packet_md_path": _clean_text(row.get("execution_packet_md_path")) or "",
    }


def _completion_row(
    workbook_row: dict[str, Any],
    *,
    row_number: int,
    profile_id: str,
    workbook_path: Path,
    delivery_csv_path: Path,
    runtime_row: dict[str, Any],
) -> dict[str, Any]:
    missing_required = _required_fields_missing(workbook_row)
    missing_recommended = _recommended_fields_missing(workbook_row, profile_id=profile_id)
    return {
        "request_id": _clean_text(workbook_row.get("request_id")) or "",
        "profile_id": profile_id,
        "row_number": row_number,
        "junction_id": _clean_text(workbook_row.get("junction_id")) or "",
        "signal_name": _clean_text(workbook_row.get("signal_name")) or "",
        "signal_type": _clean_text(workbook_row.get("signal_type")) or "",
        "movement_turn": _clean_text(workbook_row.get("movement_turn")) or "",
        "incoming_arm_id": _clean_text(workbook_row.get("incoming_arm_id")) or "",
        "node_object_id": _clean_text(workbook_row.get("node_object_id")) or "",
        "required_fields_missing": "|".join(missing_required),
        "recommended_fields_missing": "|".join(missing_recommended),
        "phase_id_current": _clean_text(workbook_row.get("phase_id")) or "",
        "stage_id_current": _clean_text(workbook_row.get("stage_id")) or "",
        "protection_state_current": _clean_text(workbook_row.get("protection_state")) or "",
        "outgoing_arm_id_current": _clean_text(workbook_row.get("outgoing_arm_id")) or "",
        "pedestrian_stage_flag_current": _clean_text(workbook_row.get("pedestrian_stage_flag")) or "",
        "candidate_target_arm_catalog": _clean_text(
            workbook_row.get("source_candidate_target_arm_catalog")
        )
        or "",
        "source_crash_total": _safe_int(workbook_row.get("source_crash_total")),
        "source_injury_total": _safe_int(workbook_row.get("source_injury_total")),
        "source_peak_year": _clean_text(workbook_row.get("source_peak_year")) or "",
        "source_peak_year_crash_count": _safe_int(
            workbook_row.get("source_peak_year_crash_count")
        ),
        "support_artifact_path": _clean_text(workbook_row.get("support_artifact_path")) or "",
        "validation_manifest_path": _clean_text(workbook_row.get("validation_manifest_path")) or "",
        "workbook_path": str(workbook_path),
        "delivery_csv_path": str(delivery_csv_path),
        "manual_mapping_hint": _clean_text(workbook_row.get("manual_mapping_hint")) or "",
        "execution_route": _clean_text(runtime_row.get("execution_route")) or "",
        "execution_summary": _clean_text(runtime_row.get("execution_summary")) or "",
        "completion_packet_md_path": "",
        "completion_priority_rank": 0,
    }


def _build_completion_queue(
    *,
    workbook_requests: list[dict[str, Any]],
    manual_workbook_path: Path,
    manual_delivery_path: Path,
    pedestrian_workbook_path: Path,
    pedestrian_delivery_path: Path,
) -> list[dict[str, Any]]:
    request_lookup = {
        _clean_text(row.get("request_id")) or "": row for row in workbook_requests
    }
    request_ids = {request_id for request_id in request_lookup if request_id}
    completion_queue: list[dict[str, Any]] = []

    for row_number, row in enumerate(_load_csv_rows(manual_workbook_path), start=1):
        request_id = _clean_text(row.get("request_id")) or ""
        if request_id not in request_ids:
            continue
        if not _required_fields_missing(row):
            continue
        completion_queue.append(
            _completion_row(
                row,
                row_number=row_number,
                profile_id="arm_phase_mapping_sheet",
                workbook_path=manual_workbook_path,
                delivery_csv_path=manual_delivery_path,
                runtime_row=request_lookup[request_id],
            )
        )

    for row_number, row in enumerate(_load_csv_rows(pedestrian_workbook_path), start=1):
        request_id = _clean_text(row.get("request_id")) or ""
        if request_id not in request_ids:
            continue
        if not _required_fields_missing(row):
            continue
        completion_queue.append(
            _completion_row(
                row,
                row_number=row_number,
                profile_id="pedestrian_stage_mapping_sheet",
                workbook_path=pedestrian_workbook_path,
                delivery_csv_path=pedestrian_delivery_path,
                runtime_row=request_lookup[request_id],
            )
        )

    completion_queue.sort(
        key=lambda row: (
            -_safe_int(row.get("source_crash_total")),
            -_safe_int(row.get("source_injury_total")),
            row["request_id"],
            row["profile_id"],
            _safe_int(row["row_number"]),
        )
    )
    for rank, row in enumerate(completion_queue, start=1):
        row["completion_priority_rank"] = rank
    return completion_queue


def _packet_markdown(
    request_id: str,
    rows: list[dict[str, Any]],
    *,
    workbook_request: dict[str, Any],
) -> str:
    lines = [
        f"# {request_id}",
        "",
        "This packet lists workbook rows that still require analyst-supplied phase values.",
        "",
        f"- execution route: `{_clean_text(workbook_request.get('execution_route')) or ''}`",
        f"- execution summary: `{_clean_text(workbook_request.get('execution_summary')) or ''}`",
        "",
        "## Completion Rows",
        "",
    ]
    if not rows:
        lines.append("- No workbook rows are missing required completion fields.")
    else:
        for row in rows[:50]:
            location = row["incoming_arm_id"] or row["node_object_id"]
            lines.append(
                "- "
                f"`{row['profile_id']}` row `{row['row_number']}` "
                f"missing `{row['required_fields_missing']}` "
                f"for `{location}` with crash weight `{row['source_crash_total']}`"
            )
    lines.append("")
    return "\n".join(lines)


def _bundle_markdown(
    summary: dict[str, Any],
    completion_queue: list[dict[str, Any]],
    non_workbook_execution_queue: list[dict[str, Any]],
    hold_queue: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Workbook Completion Bundle",
        "",
        "This bundle expands request-level support runtime execution into row-level workbook completion work.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{summary['request_count']}`",
        f"- workbook completion requests: `{summary['workbook_fill_request_count']}`",
        f"- completion rows: `{summary['completion_row_count']}`",
        f"- manual completion rows: `{summary['manual_completion_row_count']}`",
        f"- pedestrian completion rows: `{summary['pedestrian_completion_row_count']}`",
        f"- non-workbook executions: `{summary['non_workbook_execution_count']}`",
        f"- hold requests: `{summary['hold_request_count']}`",
        f"- total crash weight: `{summary['total_crash_weight']}`",
        f"- top completion crash total: `{summary['top_completion_crash_total']}`",
        "",
        "## Top Completion Rows",
        "",
    ]
    if completion_queue:
        for row in completion_queue[:10]:
            location = row["incoming_arm_id"] or row["node_object_id"]
            lines.append(
                "- "
                f"rank `{row['completion_priority_rank']}` `{row['profile_id']}` "
                f"row `{row['row_number']}` for `{location}` "
                f"missing `{row['required_fields_missing']}`"
            )
    else:
        lines.append("- No workbook rows currently need required-field completion.")
    if non_workbook_execution_queue:
        lines.extend(["", "## Non-Workbook Executions", ""])
        for row in non_workbook_execution_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['execution_summary']}`"
            )
    if hold_queue:
        lines.extend(["", "## Holds", ""])
        for row in hold_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['final_action_category']}` -> `{row['hold_reason']}`"
            )
    lines.append("")
    return "\n".join(lines)


def _write_completion_packets(
    *,
    packets_dir: Path,
    completion_queue: list[dict[str, Any]],
    workbook_requests: list[dict[str, Any]],
) -> None:
    packets_dir.mkdir(parents=True, exist_ok=True)
    rows_by_request: dict[str, list[dict[str, Any]]] = {}
    for row in completion_queue:
        rows_by_request.setdefault(row["request_id"], []).append(row)
    requests_by_id = {
        _clean_text(row.get("request_id")) or "": row for row in workbook_requests
    }
    for request_id, rows in rows_by_request.items():
        packet_path = packets_dir / f"{request_id}.md"
        packet_path.write_text(
            _packet_markdown(
                request_id,
                rows,
                workbook_request=requests_by_id.get(request_id, {}),
            ),
            encoding="utf-8",
        )
        for row in rows:
            row["completion_packet_md_path"] = str(packet_path)


def build_bari_signal_phase_support_workbook_completion_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_workbook_completion/bari",
    signal_phase_support_runtime_action_execution_bundle_path: str | Path = (
        "data/reporting/signal_phase_support_runtime_action_execution/bari/"
        "signal_phase_support_runtime_action_execution_bundle.json"
    ),
    signal_phase_support_writeback_bundle_path: str | Path = (
        "data/reporting/signal_phase_support_writeback/bari/"
        "signal_phase_support_writeback_bundle.json"
    ),
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_action_execution_input = Path(
        signal_phase_support_runtime_action_execution_bundle_path
    )
    writeback_input = Path(signal_phase_support_writeback_bundle_path)
    runtime_action_execution_payload = _load_json(runtime_action_execution_input)
    writeback_payload = _load_json(writeback_input)

    manual_workbook_path = _workbook_path(
        writeback_payload, "manual_mapping_workbook_path", "manual_workbook_path"
    )
    pedestrian_workbook_path = _workbook_path(
        writeback_payload,
        "pedestrian_mapping_workbook_path",
        "pedestrian_workbook_path",
    )
    manual_delivery_path = _workbook_path(
        writeback_payload, "manual_delivery_path", "manual_mapping_delivery_path"
    )
    pedestrian_delivery_path = _workbook_path(
        writeback_payload,
        "pedestrian_delivery_path",
        "pedestrian_mapping_delivery_path",
    )

    workbook_requests = _workbook_request_rows(runtime_action_execution_payload)
    non_workbook_execution_queue = _non_workbook_execution_rows(
        runtime_action_execution_payload
    )
    hold_queue = _hold_rows(runtime_action_execution_payload)
    completion_queue = _build_completion_queue(
        workbook_requests=workbook_requests,
        manual_workbook_path=manual_workbook_path,
        manual_delivery_path=manual_delivery_path,
        pedestrian_workbook_path=pedestrian_workbook_path,
        pedestrian_delivery_path=pedestrian_delivery_path,
    )

    packets_dir = output_root / "completion_packets"
    _write_completion_packets(
        packets_dir=packets_dir,
        completion_queue=completion_queue,
        workbook_requests=workbook_requests,
    )

    completion_queue_path = output_root / "workbook_completion_queue.csv"
    non_workbook_queue_path = output_root / "non_workbook_execution_queue.csv"
    hold_queue_path = output_root / "workbook_completion_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_workbook_completion_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_workbook_completion_bundle.md"
    manifest_path = (
        output_root / "signal_phase_support_workbook_completion_bundle.manifest.json"
    )

    _write_csv(
        completion_queue_path,
        completion_queue,
        WORKBOOK_COMPLETION_QUEUE_FIELDS,
    )
    _write_csv(
        non_workbook_queue_path,
        non_workbook_execution_queue,
        NON_WORKBOOK_EXECUTION_QUEUE_FIELDS,
    )
    _write_csv(
        hold_queue_path,
        hold_queue,
        WORKBOOK_COMPLETION_HOLD_QUEUE_FIELDS,
    )

    total_crash_weight = sum(_safe_int(row["source_crash_total"]) for row in completion_queue)
    summary = {
        "request_count": (
            len(workbook_requests) + len(non_workbook_execution_queue) + len(hold_queue)
        ),
        "workbook_fill_request_count": len(workbook_requests),
        "workbook_repair_request_count": sum(
            1
            for row in workbook_requests
            if _clean_text(row.get("execution_route")) == "support_workbook_repair"
        ),
        "completion_row_count": len(completion_queue),
        "manual_completion_row_count": sum(
            1
            for row in completion_queue
            if row["profile_id"] == "arm_phase_mapping_sheet"
        ),
        "pedestrian_completion_row_count": sum(
            1
            for row in completion_queue
            if row["profile_id"] == "pedestrian_stage_mapping_sheet"
        ),
        "non_workbook_execution_count": len(non_workbook_execution_queue),
        "hold_request_count": len(hold_queue),
        "total_crash_weight": total_crash_weight,
        "top_completion_crash_total": (
            _safe_int(completion_queue[0]["source_crash_total"])
            if completion_queue
            else 0
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_workbook_completion_bundle_version": SIGNAL_PHASE_SUPPORT_WORKBOOK_COMPLETION_BUNDLE_VERSION,
        "signal_phase_support_workbook_completion_bundle_contract_version": SIGNAL_PHASE_SUPPORT_WORKBOOK_COMPLETION_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "completion_queue": completion_queue,
        "non_workbook_execution_queue": non_workbook_execution_queue,
        "hold_queue": hold_queue,
        "workbook_completion_queue_path": str(completion_queue_path),
        "non_workbook_execution_queue_path": str(non_workbook_queue_path),
        "workbook_completion_hold_queue_path": str(hold_queue_path),
    }
    bundle_json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    bundle_md_path.write_text(
        _bundle_markdown(
            summary,
            completion_queue,
            non_workbook_execution_queue,
            hold_queue,
        ),
        encoding="utf-8",
    )

    manifest = {
        "contract": {
            "resource_name": "signal_phase_support_workbook_completion_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_WORKBOOK_COMPLETION_BUNDLE_CONTRACT_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_workbook_completion_builder"
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "signal_phase_support_runtime_action_execution_bundle_path": str(
                runtime_action_execution_input
            ),
            "signal_phase_support_writeback_bundle_path": str(writeback_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(bundle_json_path),
            "report_json_sha256": _sha256(bundle_json_path),
            "report_md_path": str(bundle_md_path),
            "report_md_sha256": _sha256(bundle_md_path),
            "workbook_completion_queue_path": str(completion_queue_path),
            "workbook_completion_queue_sha256": _sha256(completion_queue_path),
            "non_workbook_execution_queue_path": str(non_workbook_queue_path),
            "non_workbook_execution_queue_sha256": _sha256(non_workbook_queue_path),
            "workbook_completion_hold_queue_path": str(hold_queue_path),
            "workbook_completion_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
    }
    supporting_outputs = [
        _artifact_reference(
            "signal_phase_support_workbook_completion_queue_csv",
            completion_queue_path,
            _sha256(completion_queue_path),
        ),
        _artifact_reference(
            "signal_phase_support_non_workbook_execution_queue_csv",
            non_workbook_queue_path,
            _sha256(non_workbook_queue_path),
        ),
        _artifact_reference(
            "signal_phase_support_workbook_completion_hold_queue_csv",
            hold_queue_path,
            _sha256(hold_queue_path),
        ),
    ]
    for packet_path in sorted(packets_dir.glob("*.md")):
        supporting_outputs.append(
            _artifact_reference(
                "signal_phase_support_workbook_completion_packet",
                packet_path,
                _sha256(packet_path),
            )
        )
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_runtime_action_execution_bundle",
                runtime_action_execution_input,
                _sha256(runtime_action_execution_input),
            ),
            _artifact_reference(
                "signal_phase_support_writeback_bundle",
                writeback_input,
                _sha256(writeback_input),
            ),
            _artifact_reference(
                "signal_phase_support_manual_workbook_csv",
                manual_workbook_path,
                _sha256(manual_workbook_path),
            ),
            _artifact_reference(
                "signal_phase_support_pedestrian_workbook_csv",
                pedestrian_workbook_path,
                _sha256(pedestrian_workbook_path),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_workbook_completion_report",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_workbook_completion_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=supporting_outputs,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest
