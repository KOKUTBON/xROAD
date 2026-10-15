"""Ingest signal-phase extracts into normalized JSONL records."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    governance_contract_reference,
    signal_phase_source_family_id,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_RECORDS_VERSION = "signal_phase_records_v1"
SIGNAL_PHASE_RECORDS_CONTRACT_VERSION = "signal_phase_records_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object at: {path}")
    return payload


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _resolve_source_field(row: dict[str, str], mapping: dict[str, Any]) -> str | None:
    source_field = str(mapping.get("source_field", "")).strip()
    target_field = str(mapping.get("target_field", "")).strip()
    if source_field in row:
        return source_field
    if target_field in row:
        return target_field
    if source_field.startswith("TODO_") and "__" in source_field:
        _, fallback = source_field.split("__", 1)
        if fallback in row:
            return fallback
    return None


def _normalize_datetime(value: str) -> str:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _coerce_bool(value: str) -> bool:
    text = value.strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise RuntimeError(f"invalid_boolean:{value}")


def _coerce_value(value: str, field_type: str) -> Any:
    text = value.strip()
    if field_type in {"string", "enum"}:
        return text
    if field_type == "integer":
        return int(text)
    if field_type == "number":
        return float(text)
    if field_type == "datetime":
        return _normalize_datetime(text)
    if field_type == "boolean":
        return _coerce_bool(text)
    raise RuntimeError(f"Unsupported signal-phase field type: {field_type}")


def _map_row(row: dict[str, str], mapping_stub: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    mapped: dict[str, Any] = {}
    errors: list[str] = []
    for mapping in mapping_stub.get("field_mappings", []):
        target_field = str(mapping.get("target_field", "")).strip()
        field_type = str(mapping.get("type", "string")).strip()
        required = bool(mapping.get("required"))
        source_field = _resolve_source_field(row, mapping)
        value = row.get(source_field or "", "")
        if not _value_present(value):
            if required:
                errors.append(f"missing_required_field:{target_field}")
            mapped[target_field] = None
            continue
        try:
            mapped[target_field] = _coerce_value(str(value), field_type)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid_{field_type}:{target_field}:{exc}")
            mapped[target_field] = None
    return mapped, errors


def _record_identifier(profile_id: str, mapped: dict[str, Any]) -> str:
    junction_id = str(mapped.get("junction_id") or "unknown_junction")
    if mapped.get("node_object_id"):
        return ":".join(
            [
                profile_id,
                junction_id,
                str(mapped.get("node_object_id") or "unknown_node_object"),
                str(mapped.get("phase_id") or "unknown_phase"),
                str(mapped.get("stage_id") or "unknown_stage"),
            ]
        )
    if profile_id == "controller_event_log_export":
        return ":".join(
            [
                profile_id,
                junction_id,
                str(mapped.get("device_id") or "unknown_device"),
                str(mapped.get("event_start_utc") or "unknown_start"),
                str(mapped.get("phase_id") or "unknown_phase"),
                str(mapped.get("stage_id") or "unknown_stage"),
            ]
        )
    if profile_id == "signal_stage_plan_export":
        return ":".join(
            [
                profile_id,
                junction_id,
                str(mapped.get("plan_id") or "unknown_plan"),
                str(mapped.get("phase_id") or "unknown_phase"),
                str(mapped.get("stage_id") or "unknown_stage"),
                str(mapped.get("active_from_local") or "unknown_window"),
            ]
        )
    return ":".join(
        [
            profile_id,
            junction_id,
            str(mapped.get("incoming_arm_id") or mapped.get("approach_arm_id") or "unknown_arm"),
            str(mapped.get("movement_turn") or "unknown_turn"),
            str(mapped.get("outgoing_arm_id") or "unknown_target"),
        ]
    )


def _normalized_record(mapped: dict[str, Any], mapping_stub: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(mapping_stub.get("profile_id") or "unknown_profile")
    profile_type = str(mapping_stub.get("profile_type") or "unknown_profile_type")
    record_id = _record_identifier(profile_id, mapped)
    base = {
        "signal_phase_record_id": record_id,
        "signal_phase_records_version": SIGNAL_PHASE_RECORDS_VERSION,
        "profile_id": profile_id,
        "profile_label": mapping_stub.get("profile_label"),
        "profile_type": profile_type,
        "junction_id": mapped.get("junction_id"),
        "phase_id": mapped.get("phase_id"),
        "stage_id": mapped.get("stage_id"),
        "attributes": mapped,
        "publication_policy": mapping_stub.get("publication_policy", {}),
        "quality_gates": mapping_stub.get("quality_gates", []),
        "target_join_strategy": mapping_stub.get("target_join_strategy", {}),
    }
    if profile_type == "provider_feed":
        record_kind = "signal_control_observation"
        return {
            **base,
            "record_kind": record_kind,
            "control_mode": mapped.get("control_mode"),
            "observed_start_utc": mapped.get("event_start_utc"),
            "observed_end_utc": mapped.get("event_end_utc"),
            "active_from_local": mapped.get("active_from_local"),
            "active_to_local": mapped.get("active_to_local"),
        }
    return {
        **base,
        "record_kind": "movement_phase_mapping",
        "node_object_id": mapped.get("node_object_id"),
        "incoming_arm_id": mapped.get("incoming_arm_id") or mapped.get("approach_arm_id"),
        "movement_turn": mapped.get("movement_turn"),
        "outgoing_arm_id": mapped.get("outgoing_arm_id"),
        "protection_state": mapped.get("protection_state"),
        "pedestrian_stage_flag": mapped.get("pedestrian_stage_flag"),
    }


def ingest_signal_phase_extract(
    input_csv_path: str | Path,
    mapping_stub_path: str | Path,
    output_dir: str | Path,
    *,
    limit: int | None = None,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    input_csv = Path(input_csv_path)
    mapping_stub_input = Path(mapping_stub_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_path = output_root / "signal_phase_records.jsonl"
    rejected_rows_path = output_root / "signal_phase_rejected_rows.jsonl"
    manifest_path = output_root / "signal_phase_records.manifest.json"

    mapping_stub = _load_json(mapping_stub_input)
    governance = mapping_stub.get("governance")
    if not isinstance(governance, dict):
        governance = governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY],
            source_family_ids=[signal_phase_source_family_id(str(mapping_stub.get("profile_id") or ""))],
            role_policy_ids=artifact_role_policy_ids(SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY),
        )
    total_rows = 0
    written_rows = 0
    rejected_rows = 0
    junction_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    record_kind_counts: dict[str, int] = {}
    control_mode_counts: dict[str, int] = {}
    quality_flag_counts: dict[str, int] = {}

    with input_csv.open(encoding="utf-8", newline="") as input_handle, records_path.open(
        "w",
        encoding="utf-8",
    ) as output_handle, rejected_rows_path.open("w", encoding="utf-8") as rejected_handle:
        reader = csv.DictReader(input_handle)
        for row in reader:
            if limit is not None and total_rows >= limit:
                break
            total_rows += 1
            mapped, errors = _map_row(row, mapping_stub)
            if errors:
                rejected_rows += 1
                rejected_handle.write(
                    json.dumps(
                        {"row_number": total_rows, "errors": errors, "row": row},
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                    + "\n"
                )
                for error in errors:
                    quality_flag_counts[error] = quality_flag_counts.get(error, 0) + 1
                continue

            record = _normalized_record(mapped, mapping_stub)
            output_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            written_rows += 1
            junction_id = str(record.get("junction_id") or "unknown")
            junction_counts[junction_id] = junction_counts.get(junction_id, 0) + 1
            phase_id = str(record.get("phase_id") or "unknown")
            phase_counts[phase_id] = phase_counts.get(phase_id, 0) + 1
            stage_id = str(record.get("stage_id") or "unknown")
            stage_counts[stage_id] = stage_counts.get(stage_id, 0) + 1
            record_kind = str(record.get("record_kind") or "unknown")
            record_kind_counts[record_kind] = record_kind_counts.get(record_kind, 0) + 1
            control_mode = str(record.get("control_mode") or "unknown")
            control_mode_counts[control_mode] = control_mode_counts.get(control_mode, 0) + 1

    manifest = {
        "signal_phase_records_version": SIGNAL_PHASE_RECORDS_VERSION,
        "inputs": {
            "input_csv_path": str(input_csv),
            "input_csv_sha256": _sha256(input_csv),
            "mapping_stub_path": str(mapping_stub_input),
            "mapping_stub_sha256": _sha256(mapping_stub_input),
        },
        "outputs": {
            "records_path": str(records_path),
            "records_sha256": _sha256(records_path),
            "rejected_rows_path": str(rejected_rows_path),
            "rejected_rows_sha256": _sha256(rejected_rows_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "signal_phase_records",
            "public_contract_version": SIGNAL_PHASE_RECORDS_CONTRACT_VERSION,
            "signal_phase_records_version": SIGNAL_PHASE_RECORDS_VERSION,
        },
        "governance": governance,
        "profile": {
            "profile_id": mapping_stub.get("profile_id"),
            "profile_label": mapping_stub.get("profile_label"),
            "profile_type": mapping_stub.get("profile_type"),
        },
        "stats": {
            "total_rows": total_rows,
            "written_rows": written_rows,
            "rejected_rows": rejected_rows,
            "junction_counts": junction_counts,
            "phase_counts": phase_counts,
            "stage_counts": stage_counts,
            "record_kind_counts": record_kind_counts,
            "control_mode_counts": control_mode_counts,
            "quality_flag_counts": quality_flag_counts,
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("signal_phase_input_csv", input_csv, _sha256(input_csv)),
                _artifact_reference("signal_phase_mapping_stub_json", mapping_stub_input, _sha256(mapping_stub_input)),
            ],
            publishable_outputs=[
                _artifact_reference("signal_phase_records_jsonl", records_path, _sha256(records_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_rejected_rows_jsonl", rejected_rows_path, _sha256(rejected_rows_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_records_version": SIGNAL_PHASE_RECORDS_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": manifest["stats"],
    }
