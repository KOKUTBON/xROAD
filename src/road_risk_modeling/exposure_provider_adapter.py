"""Normalize Bari phase-1 provider extracts into connector-profile CSVs."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_PROVIDER_NORMALIZATION_VERSION = "exposure_provider_normalization_v1"
EXPOSURE_PROVIDER_NORMALIZATION_CONTRACT_VERSION = "exposure_provider_normalization_public_v1"
NULL_VALUE_TOKENS = {"", "na", "n/a", "null", "none", "nan", "missing", "-"}


PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "municipal_counter_export": {
        "required_fields": [
            "source_record_id",
            "provider_name",
            "road_owner_scope",
            "join_key_type",
            "join_key_value",
            "observed_start_utc",
            "observed_end_utc",
            "vehicle_count",
            "sample_size",
            "aggregation_method",
        ],
        "optional_fields": [
            "aadt",
            "heavy_vehicle_share",
            "vehicle_km_estimate",
            "coverage_pct",
            "flow_quality_flag",
        ],
        "defaults": {
            "provider_name": "municipal_counter_export",
            "road_owner_scope": "municipal",
            "join_key_type": "segment_id",
            "aggregation_method": "daily_sensor_aggregate",
        },
        "aliases": {
            "source_record_id": ["source_record_id", "counter_record_id", "record_id", "id"],
            "provider_name": ["provider_name", "provider", "provider id", "source_provider"],
            "road_owner_scope": ["road_owner_scope", "owner_scope", "owner", "road_owner"],
            "join_key_type": ["join_key_type", "network_join_type", "join_type"],
            "join_key_value": ["join_key_value", "segment_ref", "segment_id", "segment_identifier", "link_id"],
            "observed_start_utc": [
                "observed_start_utc",
                "observation_start_utc",
                "start_utc",
                "start_time_utc",
                "interval_start",
                "start_time",
            ],
            "observed_end_utc": [
                "observed_end_utc",
                "observation_end_utc",
                "end_utc",
                "end_time_utc",
                "interval_end",
                "end_time",
            ],
            "vehicle_count": [
                "vehicle_count",
                "vehicle_count_total",
                "total_vehicle_count",
                "traffic_count",
                "traffic_volume",
                "volume",
            ],
            "sample_size": ["sample_size", "sample_count", "sample_n", "observation_count", "observations"],
            "aggregation_method": ["aggregation_method", "aggregation_type", "method"],
            "aadt": ["aadt", "aadt_estimate"],
            "heavy_vehicle_share": ["heavy_vehicle_share", "heavy_share", "hv_share"],
            "vehicle_km_estimate": ["vehicle_km_estimate", "vehicle_km_travelled_estimate", "vkt_estimate"],
            "coverage_pct": ["coverage_pct", "coverage_share", "coverage"],
            "flow_quality_flag": ["flow_quality_flag", "quality_flag", "flow_quality"],
        },
    },
    "fixed_speed_counter_export": {
        "required_fields": [
            "source_record_id",
            "provider_name",
            "road_owner_scope",
            "join_key_type",
            "join_key_value",
            "observed_start_utc",
            "observed_end_utc",
            "mean_speed_kph",
            "p85_speed_kph",
            "sample_size",
        ],
        "optional_fields": [
            "speed_std_kph",
            "speed_variance",
            "speed_limit_kph",
            "probe_penetration_rate",
            "speed_quality_flag",
        ],
        "defaults": {
            "provider_name": "fixed_speed_counter_export",
            "road_owner_scope": "municipal",
            "join_key_type": "segment_id",
        },
        "aliases": {
            "source_record_id": ["source_record_id", "speed_record_id", "record_id", "id"],
            "provider_name": ["provider_name", "provider", "provider id", "source_provider"],
            "road_owner_scope": ["road_owner_scope", "owner_scope", "owner", "road_owner"],
            "join_key_type": ["join_key_type", "network_join_type", "join_type"],
            "join_key_value": ["join_key_value", "segment_ref", "segment_id", "segment_identifier", "link_id"],
            "observed_start_utc": [
                "observed_start_utc",
                "observation_start_utc",
                "start_utc",
                "start_time_utc",
                "interval_start",
                "start_time",
            ],
            "observed_end_utc": [
                "observed_end_utc",
                "observation_end_utc",
                "end_utc",
                "end_time_utc",
                "interval_end",
                "end_time",
            ],
            "mean_speed_kph": ["mean_speed_kph", "avg_speed_kph", "average_speed_kph", "mean_speed"],
            "p85_speed_kph": [
                "p85_speed_kph",
                "percentile85_speed_kph",
                "p85_speed",
                "speed_p85_kph",
            ],
            "sample_size": ["sample_size", "sample_count", "sample_n", "observation_count", "observations"],
            "speed_std_kph": ["speed_std_kph", "std_speed_kph", "speed_sd_kph"],
            "speed_variance": ["speed_variance", "speed_variance_kph2", "variance_speed_kph2"],
            "speed_limit_kph": ["speed_limit_kph", "limit_kph", "posted_speed_limit_kph"],
            "probe_penetration_rate": ["probe_penetration_rate", "penetration_rate"],
            "speed_quality_flag": ["speed_quality_flag", "quality_flag"],
        },
    },
}


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


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _canonical_header(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum())


def _detect_delimiter(input_csv_path: Path) -> str:
    sample = input_csv_path.read_text(encoding="utf-8", errors="replace")[:8192]
    if not sample.strip():
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return str(dialect.delimiter)
    except csv.Error:
        return ","


def _resolve_source_columns(fieldnames: list[str], profile_spec: dict[str, Any]) -> dict[str, str | None]:
    lookup = {
        _canonical_header(fieldname): fieldname
        for fieldname in fieldnames
    }
    source_columns: dict[str, str | None] = {}
    aliases = profile_spec["aliases"]
    all_fields = profile_spec["required_fields"] + profile_spec["optional_fields"]
    for target_field in all_fields:
        selected: str | None = None
        for alias in aliases.get(target_field, [target_field]):
            candidate = lookup.get(_canonical_header(str(alias)))
            if candidate:
                selected = candidate
                break
        source_columns[target_field] = selected
    return source_columns


def _normalized_row(
    row: dict[str, str],
    *,
    profile_spec: dict[str, Any],
    source_columns: dict[str, str | None],
    default_field_counts: Counter[str],
) -> tuple[dict[str, str], list[str]]:
    required_fields = set(profile_spec["required_fields"])
    defaults = profile_spec.get("defaults", {})
    all_fields = profile_spec["required_fields"] + profile_spec["optional_fields"]

    normalized: dict[str, str] = {}
    errors: list[str] = []
    for field in all_fields:
        source_column = source_columns.get(field)
        value = _clean_text(row.get(source_column, "") if source_column else "")
        if not _value_present(value):
            default_value = defaults.get(field)
            if _value_present(default_value):
                value = _clean_text(default_value)
                default_field_counts[field] += 1
        normalized[field] = value
        if field in required_fields and not _value_present(value):
            errors.append(f"missing_required_field:{field}")

    return normalized, errors


def _resolve_provider_profile_id(
    *,
    provider_profile_id: str | None,
    mapping_stub_path: str | Path | None,
) -> tuple[str, Path | None]:
    mapping_stub_input: Path | None = None
    mapping_stub_profile_id: str | None = None

    if mapping_stub_path is not None:
        mapping_stub_input = Path(mapping_stub_path)
        if not mapping_stub_input.exists():
            raise RuntimeError(f"Mapping stub does not exist: {mapping_stub_input}")
        mapping_stub_payload = _load_json(mapping_stub_input)
        mapping_stub_profile_id = str(mapping_stub_payload.get("provider_profile_id") or "").strip() or None
        if mapping_stub_profile_id is None:
            raise RuntimeError(
                f"Mapping stub is missing provider_profile_id: {mapping_stub_input}"
            )

    if provider_profile_id and mapping_stub_profile_id and provider_profile_id != mapping_stub_profile_id:
        raise RuntimeError(
            "Provider profile mismatch between command argument and mapping stub: "
            f"{provider_profile_id} vs {mapping_stub_profile_id}."
        )

    resolved_provider_profile_id = provider_profile_id or mapping_stub_profile_id
    if resolved_provider_profile_id is None:
        raise RuntimeError(
            "Either provider_profile_id or mapping_stub_path with provider_profile_id is required."
        )
    if resolved_provider_profile_id not in PROFILE_SPECS:
        raise RuntimeError(
            "Unsupported provider_profile_id "
            f"'{resolved_provider_profile_id}'. Supported values: {', '.join(sorted(PROFILE_SPECS))}."
        )

    return resolved_provider_profile_id, mapping_stub_input


def normalize_exposure_provider_extract(
    input_csv_path: str | Path,
    *,
    provider_profile_id: str | None = None,
    mapping_stub_path: str | Path | None = None,
    output_dir: str | Path,
    limit: int | None = None,
) -> dict[str, Any]:
    resolved_provider_profile_id, mapping_stub_input = _resolve_provider_profile_id(
        provider_profile_id=provider_profile_id,
        mapping_stub_path=mapping_stub_path,
    )

    input_csv = Path(input_csv_path)
    if not input_csv.exists():
        raise RuntimeError(f"Input CSV does not exist: {input_csv}")

    profile_spec = PROFILE_SPECS[resolved_provider_profile_id]
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_csv_path = output_root / f"{resolved_provider_profile_id}__normalized_extract.csv"
    rejected_rows_path = output_root / f"{resolved_provider_profile_id}__rejected_rows.jsonl"
    manifest_path = output_root / f"{resolved_provider_profile_id}__normalization.manifest.json"

    detected_delimiter = _detect_delimiter(input_csv)
    total_rows = 0
    written_rows = 0
    rejected_rows = 0
    missing_required_field_counts: Counter[str] = Counter()
    default_field_counts: Counter[str] = Counter()

    with input_csv.open(encoding="utf-8", newline="") as input_handle:
        reader = csv.DictReader(input_handle, delimiter=detected_delimiter)
        if not reader.fieldnames:
            raise RuntimeError(f"Input CSV is missing a header row: {input_csv}")

        fieldnames = [_clean_text(fieldname).lstrip("\ufeff") for fieldname in reader.fieldnames]
        source_columns = _resolve_source_columns(fieldnames, profile_spec)
        output_fieldnames = profile_spec["required_fields"] + profile_spec["optional_fields"]

        with normalized_csv_path.open("w", encoding="utf-8", newline="") as output_handle, rejected_rows_path.open(
            "w",
            encoding="utf-8",
        ) as rejected_handle:
            writer = csv.DictWriter(output_handle, fieldnames=output_fieldnames)
            writer.writeheader()

            for row in reader:
                if limit is not None and total_rows >= limit:
                    break
                total_rows += 1

                normalized, errors = _normalized_row(
                    row,
                    profile_spec=profile_spec,
                    source_columns=source_columns,
                    default_field_counts=default_field_counts,
                )

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
                        if error.startswith("missing_required_field:"):
                            missing_required_field_counts[error.split(":", 1)[1]] += 1
                    continue

                writer.writerow(normalized)
                written_rows += 1

    manifest = {
        "exposure_provider_normalization_version": EXPOSURE_PROVIDER_NORMALIZATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "inputs": {
            "input_csv_path": str(input_csv),
            "input_csv_sha256": _sha256(input_csv),
            "provider_profile_id": resolved_provider_profile_id,
            "mapping_stub_path": str(mapping_stub_input) if mapping_stub_input else None,
            "mapping_stub_sha256": _sha256(mapping_stub_input) if mapping_stub_input else None,
            "detected_delimiter": detected_delimiter,
        },
        "outputs": {
            "normalized_csv_path": str(normalized_csv_path),
            "normalized_csv_sha256": _sha256(normalized_csv_path),
            "rejected_rows_path": str(rejected_rows_path),
            "rejected_rows_sha256": _sha256(rejected_rows_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_provider_normalization",
            "public_contract_version": EXPOSURE_PROVIDER_NORMALIZATION_CONTRACT_VERSION,
            "exposure_provider_normalization_version": EXPOSURE_PROVIDER_NORMALIZATION_VERSION,
        },
        "profile": {
            "provider_profile_id": resolved_provider_profile_id,
            "required_fields": profile_spec["required_fields"],
            "optional_fields": profile_spec["optional_fields"],
            "resolved_source_columns": source_columns,
        },
        "stats": {
            "total_rows": total_rows,
            "written_rows": written_rows,
            "rejected_rows": rejected_rows,
            "missing_required_field_counts": {
                field: int(count)
                for field, count in sorted(missing_required_field_counts.items())
            },
            "default_field_counts": {
                field: int(count)
                for field, count in sorted(default_field_counts.items())
            },
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "provider_input_csv",
                    input_csv,
                    _sha256(input_csv),
                ),
                *([
                    _artifact_reference(
                        "connector_mapping_stub_json",
                        mapping_stub_input,
                        _sha256(mapping_stub_input),
                    )
                ] if mapping_stub_input else []),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "provider_normalized_connector_csv",
                    normalized_csv_path,
                    _sha256(normalized_csv_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "provider_normalization_rejected_rows_jsonl",
                    rejected_rows_path,
                    _sha256(rejected_rows_path),
                ),
            ],
        ),
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_provider_normalization_version": EXPOSURE_PROVIDER_NORMALIZATION_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "normalized_csv_path": str(normalized_csv_path),
        "rejected_rows_path": str(rejected_rows_path),
        "provider_profile_id": resolved_provider_profile_id,
        "stats": manifest["stats"],
    }
