"""Build analyst writeback workbooks and validation-ready deliveries from support-resolution outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_VERSION = "signal_phase_support_writeback_bundle_v1"
SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_CONTRACT_VERSION = "signal_phase_support_writeback_bundle_public_v1"

MANUAL_WORKBOOK_FIELDS = [
    "request_id",
    "junction_id",
    "signal_name",
    "signal_type",
    "incoming_arm_id",
    "movement_turn",
    "phase_id",
    "stage_id",
    "protection_state",
    "outgoing_arm_id",
    "pedestrian_stage_flag",
    "notes",
    "source_phase_priority_group",
    "source_crash_total",
    "source_injury_total",
    "source_peak_year",
    "source_peak_year_crash_count",
    "source_candidate_target_arm_catalog",
    "source_movement_variant_count",
    "source_movement_ids",
    "support_artifact_path",
    "validation_manifest_path",
    "manual_mapping_hint",
]

PEDESTRIAN_WORKBOOK_FIELDS = [
    "request_id",
    "junction_id",
    "signal_name",
    "signal_type",
    "node_object_id",
    "movement_turn",
    "phase_id",
    "stage_id",
    "protection_state",
    "pedestrian_stage_flag",
    "notes",
    "source_crash_total",
    "source_injury_total",
    "source_peak_year",
    "source_peak_year_crash_count",
    "support_artifact_path",
    "validation_manifest_path",
    "manual_mapping_hint",
]

MANUAL_DELIVERY_FIELDS = [
    "junction_id",
    "incoming_arm_id",
    "movement_turn",
    "phase_id",
    "stage_id",
    "protection_state",
    "outgoing_arm_id",
    "pedestrian_stage_flag",
    "notes",
]

PEDESTRIAN_DELIVERY_FIELDS = [
    "junction_id",
    "node_object_id",
    "movement_turn",
    "phase_id",
    "stage_id",
    "protection_state",
    "pedestrian_stage_flag",
    "notes",
]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _manual_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _clean_text(row.get("request_id")) or "",
        _clean_text(row.get("junction_id")) or "",
        _clean_text(row.get("incoming_arm_id")) or "",
        _clean_text(row.get("movement_turn")) or "",
    )


def _pedestrian_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean_text(row.get("request_id")) or "",
        _clean_text(row.get("junction_id")) or "",
        _clean_text(row.get("node_object_id")) or "",
    )


def _pick_single_catalog_value(value: Any) -> str | None:
    parts = [part.strip() for part in str(value or "").split("|") if part.strip()]
    if len(parts) == 1:
        return parts[0]
    return None


def _coerce_existing_bool(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return ""


def _build_manual_workbook_rows(
    manual_rows: list[dict[str, Any]],
    *,
    existing_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    existing_lookup = {_manual_key(row): row for row in existing_rows}
    workbook_rows: list[dict[str, Any]] = []
    for row in manual_rows:
        existing = existing_lookup.get(_manual_key(row), {})
        workbook_rows.append(
            {
                "request_id": _clean_text(row.get("request_id")) or "",
                "junction_id": _clean_text(row.get("junction_id")) or "",
                "signal_name": _clean_text(row.get("signal_name")) or "",
                "signal_type": _clean_text(row.get("signal_type")) or "",
                "incoming_arm_id": _clean_text(row.get("incoming_arm_id")) or "",
                "movement_turn": _clean_text(row.get("movement_turn")) or "",
                "phase_id": _clean_text(existing.get("phase_id")) or "",
                "stage_id": _clean_text(existing.get("stage_id")) or "",
                "protection_state": _clean_text(existing.get("protection_state")) or "",
                "outgoing_arm_id": (
                    _clean_text(existing.get("outgoing_arm_id"))
                    or _pick_single_catalog_value(row.get("outgoing_arm_catalog"))
                    or ""
                ),
                "pedestrian_stage_flag": _coerce_existing_bool(existing.get("pedestrian_stage_flag")),
                "notes": _clean_text(existing.get("notes")) or "",
                "source_phase_priority_group": _clean_text(row.get("phase_priority_group")) or "",
                "source_crash_total": _safe_int(row.get("crash_total")),
                "source_injury_total": _safe_int(row.get("injury_total")),
                "source_peak_year": _clean_text(row.get("peak_year")) or "",
                "source_peak_year_crash_count": _safe_int(row.get("peak_year_crash_count")),
                "source_candidate_target_arm_catalog": _clean_text(row.get("candidate_target_arm_catalog")) or "",
                "source_movement_variant_count": _safe_int(row.get("movement_variant_count")),
                "source_movement_ids": _clean_text(row.get("movement_ids")) or "",
                "support_artifact_path": _clean_text(row.get("support_artifact_path")) or "",
                "validation_manifest_path": _clean_text(row.get("validation_manifest_path")) or "",
                "manual_mapping_hint": _clean_text(row.get("manual_mapping_hint")) or "",
            }
        )
    return workbook_rows


def _build_pedestrian_workbook_rows(
    pedestrian_rows: list[dict[str, Any]],
    *,
    existing_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    existing_lookup = {_pedestrian_key(row): row for row in existing_rows}
    workbook_rows: list[dict[str, Any]] = []
    for row in pedestrian_rows:
        existing = existing_lookup.get(_pedestrian_key(row), {})
        existing_flag = _coerce_existing_bool(existing.get("pedestrian_stage_flag"))
        workbook_rows.append(
            {
                "request_id": _clean_text(row.get("request_id")) or "",
                "junction_id": _clean_text(row.get("junction_id")) or "",
                "signal_name": _clean_text(row.get("signal_name")) or "",
                "signal_type": _clean_text(row.get("signal_type")) or "",
                "node_object_id": _clean_text(row.get("node_object_id")) or "",
                "movement_turn": _clean_text(row.get("movement_turn")) or "cross",
                "phase_id": _clean_text(existing.get("phase_id")) or "",
                "stage_id": _clean_text(existing.get("stage_id")) or "",
                "protection_state": _clean_text(existing.get("protection_state")) or "",
                "pedestrian_stage_flag": existing_flag or "true",
                "notes": _clean_text(existing.get("notes")) or "",
                "source_crash_total": _safe_int(row.get("crash_total")),
                "source_injury_total": _safe_int(row.get("injury_total")),
                "source_peak_year": _clean_text(row.get("peak_year")) or "",
                "source_peak_year_crash_count": _safe_int(row.get("peak_year_crash_count")),
                "support_artifact_path": _clean_text(row.get("support_artifact_path")) or "",
                "validation_manifest_path": _clean_text(row.get("validation_manifest_path")) or "",
                "manual_mapping_hint": _clean_text(row.get("manual_mapping_hint")) or "",
            }
        )
    return workbook_rows


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


def _manual_delivery_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field, "") for field in MANUAL_DELIVERY_FIELDS}


def _pedestrian_delivery_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field, "") for field in PEDESTRIAN_DELIVERY_FIELDS}


def _pedestrian_mapping_stub(*, source_template_path: Path) -> dict[str, Any]:
    return {
        "mapping_stub_version": "signal_phase_mapping_stub_v1",
        "profile_id": "pedestrian_stage_mapping_sheet",
        "profile_type": "analyst_mapping",
        "profile_label": "Pedestrian-stage mapping sheet",
        "source_template_path": str(source_template_path),
        "target_join_strategy": {
            "junction_key": "junction_id",
            "movement_mapping_level": "direct_node_object_to_phase",
            "note": "Map directly to Bari pedestrian crossing movement objects via node_object_id.",
        },
        "field_mappings": [
            {"target_field": "junction_id", "source_field": "junction_id", "required": True, "type": "string"},
            {"target_field": "node_object_id", "source_field": "node_object_id", "required": True, "type": "string"},
            {"target_field": "movement_turn", "source_field": "movement_turn", "required": True, "type": "string"},
            {"target_field": "phase_id", "source_field": "phase_id", "required": True, "type": "string"},
            {"target_field": "stage_id", "source_field": "stage_id", "required": True, "type": "string"},
            {"target_field": "protection_state", "source_field": "protection_state", "required": True, "type": "string"},
            {"target_field": "pedestrian_stage_flag", "source_field": "pedestrian_stage_flag", "required": False, "type": "boolean"},
            {"target_field": "notes", "source_field": "notes", "required": False, "type": "string"},
        ],
        "quality_gates": [
            "junction_id present and matches Bari signal node ids",
            "node_object_id present and matches a signalized pedestrian crossing movement object",
            "phase_id and stage_id consistent within each junction",
        ],
        "publication_policy": {
            "publication_tier": "restricted_internal_mapping",
            "public_release_policy": "Publish only derived risk products and summary indicators, never raw control exports.",
            "restricted_use_policy": "Use pedestrian-stage mappings only for internal movement alignment and control-aware model features.",
            "retention_policy": "retain as long as the pedestrian-stage mapping remains current for the modeled junction",
        },
    }


def _validation_command(
    *,
    delivery_csv_path: Path,
    mapping_stub_path: Path,
    output_dir: Path,
    request_id: str,
    junction_id: str,
) -> str:
    return (
        "PYTHONPATH=src python3 -m road_risk_modeling validate-signal-phase-delivery "
        f"{delivery_csv_path} {mapping_stub_path} --output-dir {output_dir} "
        f"--request-id {request_id} --junction-id {junction_id}"
    )


def _markdown_report(summary: dict[str, Any], request_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Bari Signal-Phase Support Writeback Bundle",
        "",
        "This bundle turns support-resolution review rows into analyst-fillable workbooks and exports completed rows as validation-ready deliveries.",
        "",
        "## Summary",
        "",
        f"- support requests: `{summary['support_request_count']}`",
        f"- manual workbook rows: `{summary['manual_workbook_row_count']}`",
        f"- pedestrian workbook rows: `{summary['pedestrian_workbook_row_count']}`",
        f"- requests with unresolved signalized movements: `{summary['requests_with_unresolved_signalized_movements_count']}`",
        f"- unresolved signalized movement rows: `{summary['unresolved_signalized_movement_count_total']}` (`{summary['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{summary['unresolved_signalized_crash_total']}` (`{summary['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        f"- manual delivery rows ready: `{summary['manual_delivery_ready_count']}`",
        f"- pedestrian delivery rows ready: `{summary['pedestrian_delivery_ready_count']}`",
        "",
        "## Request Snapshots",
        "",
    ]
    for row in request_rows[:5]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: "
            f"`{row['manual_workbook_row_count']}` manual rows, "
            f"`{row['pedestrian_workbook_row_count']}` pedestrian rows, "
            f"`{row['unresolved_signalized_movement_count']}` unresolved movements, "
            f"`{row['unresolved_signalized_crash_total']}` unresolved crashes, "
            f"`{row['manual_delivery_ready_count']}` manual ready, "
            f"`{row['pedestrian_delivery_ready_count']}` pedestrian ready"
        )
    if not request_rows:
        lines.append("- No support-resolution requests were supplied.")
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_writeback_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_writeback/bari",
    signal_phase_support_resolution_bundle_path: str | Path = "data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    manual_mapping_stub_path: str | Path = "data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    support_resolution_input = Path(signal_phase_support_resolution_bundle_path)
    manual_mapping_stub_input = Path(manual_mapping_stub_path)
    support_bundle = _load_json(support_resolution_input)

    manual_rows = support_bundle.get("manual_arm_phase_review", [])
    pedestrian_rows = support_bundle.get("pedestrian_stage_review", [])
    request_rows = support_bundle.get("support_resolution_requests", [])
    if not isinstance(manual_rows, list) or not isinstance(pedestrian_rows, list) or not isinstance(request_rows, list):
        raise RuntimeError("Support-resolution bundle must include manual_arm_phase_review, pedestrian_stage_review, and support_resolution_requests lists.")

    workbooks_dir = output_root / "workbooks"
    deliveries_dir = output_root / "deliveries"
    request_deliveries_dir = deliveries_dir / "by_request"
    mappings_dir = output_root / "mapping_stubs"
    validation_dir = output_root / "validation_commands"
    workbooks_dir.mkdir(parents=True, exist_ok=True)
    deliveries_dir.mkdir(parents=True, exist_ok=True)
    request_deliveries_dir.mkdir(parents=True, exist_ok=True)
    mappings_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)

    manual_workbook_path = workbooks_dir / "arm_phase_mapping_sheet_workbook.csv"
    pedestrian_workbook_path = workbooks_dir / "pedestrian_stage_mapping_sheet_workbook.csv"
    manual_delivery_path = deliveries_dir / "arm_phase_mapping_sheet_delivery.csv"
    pedestrian_delivery_path = deliveries_dir / "pedestrian_stage_mapping_sheet_delivery.csv"
    pedestrian_mapping_stub_path = mappings_dir / "pedestrian_stage_mapping_sheet_mapping_stub.json"
    validation_commands_path = validation_dir / "validation_commands.csv"
    report_json_path = output_root / "signal_phase_support_writeback_bundle.json"
    report_md_path = output_root / "signal_phase_support_writeback_bundle.md"
    manifest_path = output_root / "signal_phase_support_writeback_bundle.manifest.json"

    manual_workbook_rows = _build_manual_workbook_rows(
        [row for row in manual_rows if isinstance(row, dict)],
        existing_rows=_load_csv_rows(manual_workbook_path),
    )
    pedestrian_workbook_rows = _build_pedestrian_workbook_rows(
        [row for row in pedestrian_rows if isinstance(row, dict)],
        existing_rows=_load_csv_rows(pedestrian_workbook_path),
    )

    _write_csv(manual_workbook_path, manual_workbook_rows, MANUAL_WORKBOOK_FIELDS)
    _write_csv(pedestrian_workbook_path, pedestrian_workbook_rows, PEDESTRIAN_WORKBOOK_FIELDS)

    manual_ready_rows = [_manual_delivery_row(row) for row in manual_workbook_rows if _manual_row_ready(row)]
    pedestrian_ready_rows = [_pedestrian_delivery_row(row) for row in pedestrian_workbook_rows if _pedestrian_row_ready(row)]
    _write_csv(manual_delivery_path, manual_ready_rows, MANUAL_DELIVERY_FIELDS)
    _write_csv(pedestrian_delivery_path, pedestrian_ready_rows, PEDESTRIAN_DELIVERY_FIELDS)

    pedestrian_mapping_stub = _pedestrian_mapping_stub(source_template_path=pedestrian_workbook_path)
    pedestrian_mapping_stub_path.write_text(json.dumps(pedestrian_mapping_stub, indent=2, sort_keys=True), encoding="utf-8")

    request_summary_lookup = {
        _clean_text(row.get("request_id")) or "": row for row in request_rows if isinstance(row, dict)
    }
    request_level_rows: list[dict[str, Any]] = []
    validation_commands: list[dict[str, Any]] = []
    for request_id, request_row in request_summary_lookup.items():
        junction_id = _clean_text(request_row.get("junction_id")) or ""
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
        manual_count = sum(1 for row in manual_workbook_rows if _clean_text(row.get("request_id")) == request_id)
        pedestrian_count = sum(1 for row in pedestrian_workbook_rows if _clean_text(row.get("request_id")) == request_id)
        manual_ready_count = sum(
            1 for row in manual_workbook_rows if _clean_text(row.get("request_id")) == request_id and _manual_row_ready(row)
        )
        pedestrian_ready_count = sum(
            1
            for row in pedestrian_workbook_rows
            if _clean_text(row.get("request_id")) == request_id and _pedestrian_row_ready(row)
        )
        request_manual_ready_rows = [
            _manual_delivery_row(row)
            for row in manual_workbook_rows
            if _clean_text(row.get("request_id")) == request_id and _manual_row_ready(row)
        ]
        request_pedestrian_ready_rows = [
            _pedestrian_delivery_row(row)
            for row in pedestrian_workbook_rows
            if _clean_text(row.get("request_id")) == request_id and _pedestrian_row_ready(row)
        ]
        request_delivery_dir = request_deliveries_dir / request_id
        request_delivery_dir.mkdir(parents=True, exist_ok=True)
        request_manual_delivery_path = request_delivery_dir / "arm_phase_mapping_sheet_delivery.csv"
        request_pedestrian_delivery_path = request_delivery_dir / "pedestrian_stage_mapping_sheet_delivery.csv"
        _write_csv(request_manual_delivery_path, request_manual_ready_rows, MANUAL_DELIVERY_FIELDS)
        _write_csv(request_pedestrian_delivery_path, request_pedestrian_ready_rows, PEDESTRIAN_DELIVERY_FIELDS)
        request_level_rows.append(
            {
                "request_id": request_id,
                "junction_id": junction_id,
                "signal_name": _clean_text(request_row.get("signal_name")) or "",
                "manual_workbook_row_count": manual_count,
                "pedestrian_workbook_row_count": pedestrian_count,
                "manual_delivery_ready_count": manual_ready_count,
                "pedestrian_delivery_ready_count": pedestrian_ready_count,
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
                "recommended_next_action": _clean_text(request_row.get("recommended_next_action")) or "",
                "manual_workbook_path": str(manual_workbook_path),
                "pedestrian_workbook_path": str(pedestrian_workbook_path),
                "manual_delivery_path": str(request_manual_delivery_path),
                "pedestrian_delivery_path": str(request_pedestrian_delivery_path),
            }
        )
        validation_commands.append(
            {
                "request_id": request_id,
                "junction_id": junction_id,
                "profile_id": "arm_phase_mapping_sheet",
                "delivery_csv_path": str(request_manual_delivery_path),
                "mapping_stub_path": str(manual_mapping_stub_input),
                "validation_command": _validation_command(
                    delivery_csv_path=request_manual_delivery_path,
                    mapping_stub_path=manual_mapping_stub_input,
                    output_dir=output_root / "validation_outputs" / request_id / "arm_phase_mapping_sheet",
                    request_id=request_id,
                    junction_id=junction_id,
                ),
            }
        )
        validation_commands.append(
            {
                "request_id": request_id,
                "junction_id": junction_id,
                "profile_id": "pedestrian_stage_mapping_sheet",
                "delivery_csv_path": str(request_pedestrian_delivery_path),
                "mapping_stub_path": str(pedestrian_mapping_stub_path),
                "validation_command": _validation_command(
                    delivery_csv_path=request_pedestrian_delivery_path,
                    mapping_stub_path=pedestrian_mapping_stub_path,
                    output_dir=output_root / "validation_outputs" / request_id / "pedestrian_stage_mapping_sheet",
                    request_id=request_id,
                    junction_id=junction_id,
                ),
            }
        )
    request_level_rows.sort(key=lambda row: str(row["request_id"]))
    _write_csv(
        validation_commands_path,
        validation_commands,
        ["request_id", "junction_id", "profile_id", "delivery_csv_path", "mapping_stub_path", "validation_command"],
    )

    summary = {
        "support_request_count": len(request_level_rows),
        "manual_workbook_row_count": len(manual_workbook_rows),
        "pedestrian_workbook_row_count": len(pedestrian_workbook_rows),
        "requests_with_unresolved_signalized_movements_count": int(
            sum(
                1
                for row in request_level_rows
                if int(row["unresolved_signalized_movement_count"]) > 0
            )
        ),
        "unresolved_signalized_movement_count_total": int(
            sum(int(row["unresolved_signalized_movement_count"]) for row in request_level_rows)
        ),
        "unresolved_signalized_crash_total": int(
            sum(int(row["unresolved_signalized_crash_total"]) for row in request_level_rows)
        ),
        "unresolved_signalized_movement_share_pct": _safe_pct(
            int(
                sum(
                    int(row["unresolved_signalized_movement_count"])
                    for row in request_level_rows
                )
            ),
            int(sum(int(row["signalized_movement_count"]) for row in request_level_rows)),
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_crash_total"]) for row in request_level_rows)),
            int(
                sum(
                    int(row["matched_crashes_at_junction_total"])
                    for row in request_level_rows
                )
            ),
        ),
        "manual_delivery_ready_count": len(manual_ready_rows),
        "pedestrian_delivery_ready_count": len(pedestrian_ready_rows),
        "validation_command_count": len(validation_commands),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_writeback_bundle_version": SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_VERSION,
        "signal_phase_support_writeback_bundle_contract_version": SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "request_writeback_status": request_level_rows,
        "manual_mapping_workbook_path": str(manual_workbook_path),
        "pedestrian_mapping_workbook_path": str(pedestrian_workbook_path),
        "manual_delivery_path": str(manual_delivery_path),
        "pedestrian_delivery_path": str(pedestrian_delivery_path),
        "validation_commands_path": str(validation_commands_path),
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_markdown_report(summary, request_level_rows), encoding="utf-8")

    manifest = {
        "source": {
            "adapter": "bari_signal_phase_support_writeback_bundle_builder",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_writeback_bundle_version": SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_WRITEBACK_BUNDLE_CONTRACT_VERSION,
        "inputs": {
            "signal_phase_support_resolution_bundle_path": str(support_resolution_input),
            "manual_mapping_stub_path": str(manual_mapping_stub_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "manual_workbook_path": str(manual_workbook_path),
            "manual_workbook_sha256": _sha256(manual_workbook_path),
            "pedestrian_workbook_path": str(pedestrian_workbook_path),
            "pedestrian_workbook_sha256": _sha256(pedestrian_workbook_path),
            "manual_delivery_path": str(manual_delivery_path),
            "manual_delivery_sha256": _sha256(manual_delivery_path),
            "pedestrian_delivery_path": str(pedestrian_delivery_path),
            "pedestrian_delivery_sha256": _sha256(pedestrian_delivery_path),
            "request_delivery_root_path": str(request_deliveries_dir),
            "pedestrian_mapping_stub_path": str(pedestrian_mapping_stub_path),
            "pedestrian_mapping_stub_sha256": _sha256(pedestrian_mapping_stub_path),
            "validation_commands_path": str(validation_commands_path),
            "validation_commands_sha256": _sha256(validation_commands_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_support_resolution_bundle", support_resolution_input, _sha256(support_resolution_input)),
            _artifact_reference("signal_phase_mapping_stub_json", manual_mapping_stub_input, _sha256(manual_mapping_stub_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_support_writeback_report", report_json_path, _sha256(report_json_path)),
            _artifact_reference("signal_phase_support_writeback_markdown", report_md_path, _sha256(report_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("manual_mapping_workbook_csv", manual_workbook_path, _sha256(manual_workbook_path)),
            _artifact_reference("pedestrian_mapping_workbook_csv", pedestrian_workbook_path, _sha256(pedestrian_workbook_path)),
            _artifact_reference("manual_mapping_delivery_csv", manual_delivery_path, _sha256(manual_delivery_path)),
            _artifact_reference("pedestrian_mapping_delivery_csv", pedestrian_delivery_path, _sha256(pedestrian_delivery_path)),
            _artifact_reference("pedestrian_mapping_stub_json", pedestrian_mapping_stub_path, _sha256(pedestrian_mapping_stub_path)),
            _artifact_reference("signal_phase_validation_commands_csv", validation_commands_path, _sha256(validation_commands_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
