"""Ingest phase-1 exposure connector extracts into normalized observation JSONL."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    exposure_source_family_id,
    governance_contract_reference,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_CONNECTOR_OBSERVATIONS_VERSION = "exposure_connector_observations_v1"
EXPOSURE_CONNECTOR_OBSERVATIONS_CONTRACT_VERSION = "exposure_connector_observations_public_v1"
NULL_VALUE_TOKENS = {"", "na", "n/a", "null", "none", "nan", "missing", "-"}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object at: {path}")
    return payload


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in NULL_VALUE_TOKENS
    return True


def _canonical_header(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch == "_")


def _resolve_source_field(row: dict[str, str], mapping: dict[str, Any]) -> str | None:
    source_field = str(mapping.get("source_field", "")).strip()
    target_field = str(mapping.get("target_field", "")).strip()
    header_lookup = {_canonical_header(key): key for key in row}

    candidates = [source_field, target_field]
    if source_field.startswith("TODO_") and "__" in source_field:
        _, fallback = source_field.split("__", 1)
        candidates.append(fallback)

    for candidate in candidates:
        if not candidate:
            continue
        if candidate in row:
            return candidate
        resolved = header_lookup.get(_canonical_header(candidate))
        if resolved:
            return resolved
    return None


def _normalize_datetime(value: str) -> str:
    normalized = value.strip()
    if normalized.lower() in NULL_VALUE_TOKENS:
        raise ValueError("empty datetime value")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed_utc = parsed.astimezone(UTC)
    return parsed_utc.isoformat().replace("+00:00", "Z")


def _normalize_numeric_text(value: str) -> str:
    text = value.strip().replace("\u00a0", "").replace(" ", "").replace("'", "")
    if text.lower() in NULL_VALUE_TOKENS:
        raise ValueError("empty numeric value")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def _coerce_number(value: str) -> float:
    return float(_normalize_numeric_text(value))


def _coerce_integer(value: str) -> int:
    numeric = _coerce_number(value)
    if float(numeric).is_integer():
        return int(numeric)
    return int(round(numeric))


def _coerce_value(value: str, field_type: str) -> Any:
    text = value.strip()
    if field_type in {"string", "enum", "optional"}:
        return text
    if field_type == "integer":
        return _coerce_integer(text)
    if field_type == "number":
        return _coerce_number(text)
    if field_type == "datetime":
        return _normalize_datetime(text)
    raise RuntimeError(f"Unsupported connector field type: {field_type}")


def _auto_coerce_optional(value: str) -> Any:
    text = value.strip()
    if text.lower() in NULL_VALUE_TOKENS:
        return None
    try:
        numeric = _coerce_number(text)
        if float(numeric).is_integer():
            return int(numeric)
        return numeric
    except ValueError:
        return text


def _quality_check_errors(mapped: dict[str, Any], quality_checks: list[str]) -> list[str]:
    errors: list[str] = []

    def add_error(check_name: str, detail: str) -> None:
        errors.append(f"quality_check_failed:{check_name}:{detail}")

    def check_non_negative(check_name: str, fields: list[str]) -> None:
        for field in fields:
            value = mapped.get(field)
            if value is None:
                continue
            try:
                if float(value) < 0:
                    add_error(check_name, field)
            except (TypeError, ValueError):
                add_error(check_name, f"invalid_numeric:{field}")

    for check in quality_checks:
        if check == "non_negative_vehicle_count":
            check_non_negative(check, ["vehicle_count", "sample_size", "aadt", "vehicle_km_estimate"])
        elif check == "observed_start_before_end":
            start = mapped.get("observed_start_utc")
            end = mapped.get("observed_end_utc")
            if start is None or end is None:
                continue
            try:
                start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            except ValueError:
                add_error(check, "invalid_datetime")
                continue
            if start_dt > end_dt:
                add_error(check, "start_after_end")
        elif check == "join_key_resolves_to_current_network_object":
            if not _value_present(mapped.get("join_key_value")):
                add_error(check, "missing_join_key_value")
        elif check == "coverage_threshold_documented":
            coverage = mapped.get("coverage_pct")
            if coverage is None:
                continue
            try:
                coverage_value = float(coverage)
            except (TypeError, ValueError):
                add_error(check, "invalid_coverage_pct")
                continue
            if coverage_value < 0.0 or coverage_value > 1.0:
                add_error(check, "coverage_pct_out_of_range")
        elif check == "non_negative_speed_values":
            check_non_negative(
                check,
                [
                    "mean_speed_kph",
                    "p85_speed_kph",
                    "speed_std_kph",
                    "speed_variance",
                    "speed_limit_kph",
                ],
            )
        elif check == "p85_not_below_mean":
            mean_speed = mapped.get("mean_speed_kph")
            p85_speed = mapped.get("p85_speed_kph")
            if mean_speed is None or p85_speed is None:
                continue
            try:
                if float(p85_speed) < float(mean_speed):
                    add_error(check, "p85_below_mean")
            except (TypeError, ValueError):
                add_error(check, "invalid_speed_values")
        elif check == "sample_size_threshold_documented":
            sample_size = mapped.get("sample_size")
            if sample_size is None:
                continue
            try:
                if int(sample_size) <= 0:
                    add_error(check, "sample_size_not_positive")
            except (TypeError, ValueError):
                add_error(check, "invalid_sample_size")
        elif check == "non_negative_mode_counts":
            check_non_negative(check, ["pedestrian_count", "cyclist_count", "micromobility_trip_count"])
        elif check == "count_method_documented":
            if not _value_present(mapped.get("count_method")):
                add_error(check, "count_method_missing")

    return errors


def _map_row(
    row: dict[str, str],
    mapping_stub: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
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
            if field_type == "optional":
                mapped[target_field] = _auto_coerce_optional(str(value))
            else:
                mapped[target_field] = _coerce_value(str(value), field_type)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid_{field_type}:{target_field}:{exc}")
            mapped[target_field] = None
    return mapped, errors


def _normalized_record(
    mapped: dict[str, Any],
    mapping_stub: dict[str, Any],
) -> dict[str, Any]:
    source_record_id = mapped.get("source_record_id")
    work_item_id = mapping_stub["work_item_id"]
    observation_id = f"{work_item_id}:{source_record_id}"
    return {
        "observation_id": observation_id,
        "connector_version": EXPOSURE_CONNECTOR_OBSERVATIONS_VERSION,
        "municipality_label": mapping_stub["municipality_label"],
        "work_item_id": work_item_id,
        "capability_code": mapping_stub["capability_code"],
        "recommended_contract": mapping_stub["recommended_contract"],
        "provider_profile_id": mapping_stub["provider_profile_id"],
        "provider_profile_label": mapping_stub.get("provider_profile_label"),
        "provider_name": mapped.get("provider_name"),
        "road_owner_scope": mapped.get("road_owner_scope"),
        "join_key_type": mapped.get("join_key_type") or mapping_stub.get("target_join_strategy", {}).get("join_key_type"),
        "join_key_value": mapped.get("join_key_value"),
        "observed_start_utc": mapped.get("observed_start_utc"),
        "observed_end_utc": mapped.get("observed_end_utc"),
        "attributes": mapped,
        "publication_policy": mapping_stub.get("publication_policy", {}),
        "quality_checks": mapping_stub.get("quality_checks", []),
        "governance_gates": mapping_stub.get("governance_gates", []),
    }


def ingest_exposure_connector_extract(
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

    observations_path = output_root / "connector_observations.jsonl"
    rejected_rows_path = output_root / "connector_rejected_rows.jsonl"
    manifest_path = output_root / "connector_observations.manifest.json"

    mapping_stub = _load_json(mapping_stub_input)
    governance = mapping_stub.get("governance")
    if not isinstance(governance, dict):
        governance = governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY],
            source_family_ids=[
                exposure_source_family_id(str(mapping_stub.get("capability_code") or ""))
            ],
            role_policy_ids=artifact_role_policy_ids(EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY),
        )
    total_rows = 0
    written_rows = 0
    rejected_rows = 0
    join_key_type_counts: dict[str, int] = {}
    provider_name_counts: dict[str, int] = {}
    quality_flag_counts: dict[str, int] = {}

    with input_csv.open(encoding="utf-8", newline="") as input_handle, observations_path.open(
        "w",
        encoding="utf-8",
    ) as output_handle, rejected_rows_path.open("w", encoding="utf-8") as rejected_handle:
        reader = csv.DictReader(input_handle)
        for row in reader:
            if limit is not None and total_rows >= limit:
                break
            total_rows += 1
            mapped, errors = _map_row(row, mapping_stub)
            if not errors:
                errors.extend(_quality_check_errors(mapped, list(mapping_stub.get("quality_checks", []))))
            if errors:
                rejected_rows += 1
                rejected_handle.write(
                    json.dumps(
                        {
                            "row_number": total_rows,
                            "errors": errors,
                            "row": row,
                        },
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
            join_key_type = str(record.get("join_key_type") or "unknown")
            join_key_type_counts[join_key_type] = join_key_type_counts.get(join_key_type, 0) + 1
            provider_name = str(record.get("provider_name") or "unknown")
            provider_name_counts[provider_name] = provider_name_counts.get(provider_name, 0) + 1

    manifest = {
        "exposure_connector_observations_version": EXPOSURE_CONNECTOR_OBSERVATIONS_VERSION,
        "inputs": {
            "input_csv_path": str(input_csv),
            "input_csv_sha256": _sha256(input_csv),
            "mapping_stub_path": str(mapping_stub_input),
            "mapping_stub_sha256": _sha256(mapping_stub_input),
        },
        "outputs": {
            "observations_path": str(observations_path),
            "observations_sha256": _sha256(observations_path),
            "rejected_rows_path": str(rejected_rows_path),
            "rejected_rows_sha256": _sha256(rejected_rows_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_connector_observations",
            "public_contract_version": EXPOSURE_CONNECTOR_OBSERVATIONS_CONTRACT_VERSION,
            "exposure_connector_observations_version": EXPOSURE_CONNECTOR_OBSERVATIONS_VERSION,
        },
        "governance": governance,
        "connector": {
            "municipality_label": mapping_stub.get("municipality_label"),
            "work_item_id": mapping_stub.get("work_item_id"),
            "capability_code": mapping_stub.get("capability_code"),
            "recommended_contract": mapping_stub.get("recommended_contract"),
            "provider_profile_id": mapping_stub.get("provider_profile_id"),
            "provider_profile_label": mapping_stub.get("provider_profile_label"),
        },
        "stats": {
            "total_rows": total_rows,
            "written_rows": written_rows,
            "rejected_rows": rejected_rows,
            "join_key_type_counts": join_key_type_counts,
            "provider_name_counts": provider_name_counts,
            "quality_flag_counts": quality_flag_counts,
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "connector_input_csv",
                    input_csv,
                    _sha256(input_csv),
                ),
                _artifact_reference(
                    "connector_mapping_stub_json",
                    mapping_stub_input,
                    _sha256(mapping_stub_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "connector_observations_jsonl",
                    observations_path,
                    _sha256(observations_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "connector_rejected_rows_jsonl",
                    rejected_rows_path,
                    _sha256(rejected_rows_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "exposure_connector_observations_version": EXPOSURE_CONNECTOR_OBSERVATIONS_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": manifest["stats"],
    }
