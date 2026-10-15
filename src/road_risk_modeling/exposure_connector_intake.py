"""Build connector intake artifacts for phase-1 exposure onboarding work."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
    EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    exposure_source_family_id,
    governance_contract_reference,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_CONNECTOR_INTAKE_VERSION = "exposure_connector_intake_v1"
EXPOSURE_CONNECTOR_INTAKE_CONTRACT_VERSION = "exposure_connector_intake_public_v1"

PHASE_1_CAPABILITIES = ("motorized_exposure", "speed_observation")

BARI_MOTORIZED_MUNICIPAL_COUNTER_SOURCE_FIELDS = {
    "source_record_id": "counter_record_id",
    "provider_name": "provider_name",
    "road_owner_scope": "owner_scope",
    "join_key_type": "network_join_type",
    "join_key_value": "segment_ref",
    "observed_start_utc": "observation_start_utc",
    "observed_end_utc": "observation_end_utc",
    "vehicle_count": "vehicle_count_total",
    "sample_size": "sample_count",
    "aggregation_method": "aggregation_method",
    "aadt": "aadt_estimate",
    "heavy_vehicle_share": "heavy_vehicle_share",
    "vehicle_km_estimate": "vehicle_km_travelled_estimate",
    "coverage_pct": "coverage_share",
    "flow_quality_flag": "flow_quality_flag",
}

BARI_SPEED_FIXED_COUNTER_SOURCE_FIELDS = {
    "source_record_id": "speed_record_id",
    "provider_name": "provider_name",
    "road_owner_scope": "owner_scope",
    "join_key_type": "network_join_type",
    "join_key_value": "segment_ref",
    "observed_start_utc": "observation_start_utc",
    "observed_end_utc": "observation_end_utc",
    "mean_speed_kph": "mean_speed_kph",
    "p85_speed_kph": "p85_speed_kph",
    "sample_size": "sample_count",
    "speed_std_kph": "speed_std_kph",
    "speed_variance": "speed_variance_kph2",
    "speed_limit_kph": "speed_limit_kph",
    "probe_penetration_rate": "probe_penetration_rate",
    "speed_quality_flag": "speed_quality_flag",
}

SOURCE_FIELD_OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
    (
        "bari_01_motorized_exposure_municipal",
        "municipal_counter_export",
    ): BARI_MOTORIZED_MUNICIPAL_COUNTER_SOURCE_FIELDS,
    (
        "bari_02_speed_observation_municipal",
        "fixed_speed_counter_export",
    ): BARI_SPEED_FIXED_COUNTER_SOURCE_FIELDS,
}

JOIN_LOOKUP_NOTE_OVERRIDES: dict[tuple[str, str], str] = {
    (
        "bari_01_motorized_exposure_municipal",
        "municipal_counter_export",
    ): "Resolved against data/processed/segments/bari_context_v2/road_segments_context.geojson::segment_id.",
    (
        "bari_02_speed_observation_municipal",
        "fixed_speed_counter_export",
    ): "Resolved against data/processed/segments/bari_context_v2/road_segments_context.geojson::segment_id.",
}

JOIN_KEY_TYPE_OVERRIDES: dict[tuple[str, str], str] = {
    (
        "bari_02_speed_observation_municipal",
        "fixed_speed_counter_export",
    ): "segment_id",
}

PROVIDER_ARCHETYPES = {
    "motorized_exposure": [
        {
            "provider_profile_id": "municipal_counter_export",
            "label": "Municipal count export",
            "description": "Aggregated loop, camera, or contracted-count exports owned by the municipality or its ITS operator.",
            "recommended_when": "Municipal counters or periodic classified counts already exist on arterial corridors.",
            "publication_tier": "restricted_aggregates_with_public_summary",
            "retention_policy": "retain aggregates for 24 months, do not retain raw traces",
            "datex_exchange_fit": "medium",
            "sample_values": {
                "source_record_id": "bari_counter_2025_05_01_seg_001",
                "provider_name": "municipal_counter_export",
                "road_owner_scope": "municipal",
                "join_key_type": "segment_id",
                "join_key_value": "drive:15502708:335571799:0",
                "observed_start_utc": "2025-05-01T00:00:00Z",
                "observed_end_utc": "2025-05-01T23:59:59Z",
                "vehicle_count": "12458",
                "sample_size": "12458",
                "aggregation_method": "daily_sensor_aggregate",
                "aadt": "13120",
                "heavy_vehicle_share": "0.08",
                "vehicle_km_estimate": "1495.2",
                "coverage_pct": "0.97",
                "flow_quality_flag": "validated",
            },
        },
        {
            "provider_profile_id": "floating_car_flow_aggregate",
            "label": "Floating-car flow aggregate",
            "description": "Aggregated flow and demand estimates derived from probe fleets or mobile mobility providers.",
            "recommended_when": "Municipal counts are sparse but a provider can deliver corridor-level aggregated flow estimates.",
            "publication_tier": "restricted_partner_feed",
            "retention_policy": "retain only delivered aggregates under provider license",
            "datex_exchange_fit": "medium",
            "sample_values": {
                "source_record_id": "fcd_flow_2025_05_01_seg_001",
                "provider_name": "floating_car_flow_aggregate",
                "road_owner_scope": "municipal",
                "join_key_type": "segment_id",
                "join_key_value": "drive:15502708:335571799:0",
                "observed_start_utc": "2025-05-01T00:00:00Z",
                "observed_end_utc": "2025-05-01T23:59:59Z",
                "vehicle_count": "11890",
                "sample_size": "543210",
                "aggregation_method": "daily_probe_flow_estimate",
                "aadt": "12610",
                "heavy_vehicle_share": "0.06",
                "vehicle_km_estimate": "1412.0",
                "coverage_pct": "0.84",
                "flow_quality_flag": "modeled_from_probe_penetration",
            },
        },
    ],
    "speed_observation": [
        {
            "provider_profile_id": "fixed_speed_counter_export",
            "label": "Fixed speed counter export",
            "description": "Hourly or quarter-hour speed summaries from radar, camera, or loop-based counters.",
            "recommended_when": "The city or ITS contractor can export aggregated speed distributions from fixed devices.",
            "publication_tier": "restricted_aggregates_with_public_summary",
            "retention_policy": "retain hourly aggregates for 12 months, purge raw device output",
            "datex_exchange_fit": "high",
            "sample_values": {
                "source_record_id": "speed_counter_2025_05_01_08_seg_001",
                "provider_name": "fixed_speed_counter_export",
                "road_owner_scope": "municipal",
                "join_key_type": "segment_id",
                "join_key_value": "drive:15502708:335571799:0",
                "observed_start_utc": "2025-05-01T08:00:00Z",
                "observed_end_utc": "2025-05-01T08:59:59Z",
                "mean_speed_kph": "46.2",
                "p85_speed_kph": "58.4",
                "sample_size": "921",
                "speed_std_kph": "9.6",
                "speed_variance": "92.16",
                "speed_limit_kph": "50",
                "probe_penetration_rate": "",
                "speed_quality_flag": "validated",
            },
        },
        {
            "provider_profile_id": "probe_speed_aggregate",
            "label": "Probe speed aggregate",
            "description": "Aggregated speed distributions from probe data or connected-vehicle partners.",
            "recommended_when": "Probe speed feeds exist for arterials and junction approaches but local counters are sparse.",
            "publication_tier": "restricted_partner_feed",
            "retention_policy": "retain provider-approved speed aggregates only",
            "datex_exchange_fit": "high",
            "sample_values": {
                "source_record_id": "probe_speed_2025_05_01_08_seg_001",
                "provider_name": "probe_speed_aggregate",
                "road_owner_scope": "municipal",
                "join_key_type": "segment_id",
                "join_key_value": "drive:15502708:335571799:0",
                "observed_start_utc": "2025-05-01T08:00:00Z",
                "observed_end_utc": "2025-05-01T08:59:59Z",
                "mean_speed_kph": "43.8",
                "p85_speed_kph": "55.7",
                "sample_size": "3321",
                "speed_std_kph": "8.7",
                "speed_variance": "75.69",
                "speed_limit_kph": "50",
                "probe_penetration_rate": "0.041",
                "speed_quality_flag": "provider_aggregate",
            },
        },
    ],
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object at: {path}")
    return payload


def _field_names(contract: dict[str, Any]) -> list[str]:
    required = [field["name"] for field in contract.get("required_fields", [])]
    optional = list(contract.get("optional_fields", []))
    return [*required, *optional]


def _write_csv_template(path: Path, fieldnames: list[str], sample_values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({field: sample_values.get(field, "") for field in fieldnames})


def _mapping_stub(
    *,
    work_item: dict[str, Any],
    contract: dict[str, Any],
    provider_profile: dict[str, Any],
    template_path: Path,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    override_key = (work_item["work_item_id"], provider_profile["provider_profile_id"])
    source_field_overrides = SOURCE_FIELD_OVERRIDES.get(override_key, {})

    field_mappings = []
    for field in contract.get("required_fields", []):
        target_field = field["name"]
        field_mappings.append(
            {
                "target_field": target_field,
                "source_field": source_field_overrides.get(
                    target_field,
                    f"TODO_{provider_profile['provider_profile_id']}__{target_field}",
                ),
                "required": True,
                "type": field.get("type"),
            }
        )
    for field_name in contract.get("optional_fields", []):
        field_mappings.append(
            {
                "target_field": field_name,
                "source_field": source_field_overrides.get(
                    field_name,
                    f"TODO_{provider_profile['provider_profile_id']}__{field_name}",
                ),
                "required": False,
                "type": "optional",
            }
        )

    join_key_type = "segment_id"
    allowed_join_types = [
        field.get("allowed", [])
        for field in contract.get("required_fields", [])
        if field.get("name") == "join_key_type"
    ]
    if allowed_join_types and "junction_approach_id" in allowed_join_types[0]:
        join_key_type = "junction_approach_id"
    join_key_type = JOIN_KEY_TYPE_OVERRIDES.get(override_key, join_key_type)

    source_family_id = exposure_source_family_id(str(work_item.get("capability_code") or ""))
    return {
        "mapping_stub_version": "connector_mapping_stub_v1",
        "work_item_id": work_item["work_item_id"],
        "municipality_label": work_item["municipality_label"],
        "capability_code": work_item["capability_code"],
        "recommended_contract": work_item["recommended_contract"],
        "provider_profile_id": provider_profile["provider_profile_id"],
        "provider_profile_label": provider_profile["label"],
        "source_template_path": str(template_path),
        "target_join_strategy": {
            "join_key_type": join_key_type,
            "join_lookup_note": JOIN_LOOKUP_NOTE_OVERRIDES.get(
                override_key,
                "TODO: point this mapping to the current municipality segment or junction lookup export.",
            ),
        },
        "field_mappings": field_mappings,
        "quality_checks": work_item.get("quality_checks", []),
        "governance_gates": work_item.get("governance_gates", []),
        "publication_policy": {
            "publication_tier": provider_profile["publication_tier"],
            "public_release_policy": "Publish only aggregated score products and summary indicators, never the provider extract itself.",
            "restricted_use_policy": "Provider aggregates may be stored in restricted processing zones and used for model features after rights review.",
            "retention_policy": provider_profile["retention_policy"],
        },
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY],
            source_family_ids=[source_family_id],
            role_policy_ids=artifact_role_policy_ids(EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY),
        ),
    }


def _phase_1_work_items(onboarding_plan: dict[str, Any]) -> list[dict[str, Any]]:
    work_items: list[dict[str, Any]] = []
    for municipality in onboarding_plan.get("municipality_plans", []):
        for work_item in municipality.get("work_items", []):
            if work_item.get("capability_code") in PHASE_1_CAPABILITIES:
                work_items.append(work_item)
    work_items.sort(
        key=lambda item: (
            item.get("municipality_label", ""),
            int(item.get("sequence", 0)),
            item.get("capability_code", ""),
        )
    )
    return work_items


def _rights_matrix_rows(work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for work_item in work_items:
        for provider_profile in PROVIDER_ARCHETYPES[work_item["capability_code"]]:
            rows.append(
                {
                    "work_item_id": work_item["work_item_id"],
                    "municipality_label": work_item["municipality_label"],
                    "capability_code": work_item["capability_code"],
                    "provider_profile_id": provider_profile["provider_profile_id"],
                    "owner_scope": work_item["owner_scope"],
                    "recommended_contract": work_item["recommended_contract"],
                    "publication_tier": provider_profile["publication_tier"],
                    "public_release_policy": "publish derived score products only",
                    "restricted_use_policy": "restricted provider aggregate processing",
                    "raw_personal_data_allowed": "no",
                    "retention_policy": provider_profile["retention_policy"],
                    "datex_exchange_fit": provider_profile["datex_exchange_fit"],
                    "rights_checkpoint": "provider license registered and publication matrix approved",
                    "quality_gate": "; ".join(work_item.get("quality_checks", [])),
                }
            )
    return rows


def _write_rights_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "work_item_id",
        "municipality_label",
        "capability_code",
        "provider_profile_id",
        "owner_scope",
        "recommended_contract",
        "publication_tier",
        "public_release_policy",
        "restricted_use_policy",
        "raw_personal_data_allowed",
        "retention_policy",
        "datex_exchange_fit",
        "rights_checkpoint",
        "quality_gate",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Exposure Connector Intake Pack",
        "",
        "This pack converts the phase-1 onboarding work into concrete intake templates, mapping stubs, and source-rights decisions.",
        "",
        "## Scope",
        "",
        f"- Municipalities covered: `{payload['stats']['municipality_count']}`",
        f"- Phase-1 work items covered: `{payload['stats']['phase_1_work_item_count']}`",
        f"- Provider template count: `{payload['stats']['template_count']}`",
        f"- Mapping stub count: `{payload['stats']['mapping_stub_count']}`",
        "",
        "## Work Items",
        "",
    ]
    for intake in payload["connector_intakes"]:
        lines.extend(
            [
                f"### {intake['municipality_label']} / {intake['capability_label']}",
                "",
                f"- Work item: `{intake['work_item_id']}`",
                f"- Contract: `{intake['recommended_contract']}`",
                f"- Owner scope: `{intake['owner_scope']}`",
                f"- Provider profiles: `{', '.join(profile['provider_profile_id'] for profile in intake['provider_profiles'])}`",
                f"- Rights matrix rows: `{intake['rights_matrix_row_count']}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_exposure_connector_intake_pack(
    *,
    source_catalog_path: str | Path = "data/planning/exposure_sources/exposure_source_catalog.json",
    onboarding_plan_path: str | Path = "data/planning/exposure_onboarding/exposure_onboarding_plan.json",
    output_dir: str | Path = "data/planning/exposure_connector_intake",
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    source_catalog_input = Path(source_catalog_path)
    onboarding_plan_input = Path(onboarding_plan_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    pack_json_path = output_root / "connector_intake_pack.json"
    pack_markdown_path = output_root / "connector_intake_pack.md"
    rights_matrix_path = output_root / "source_rights_matrix.csv"
    templates_root = output_root / "sample_templates"
    mappings_root = output_root / "mapping_stubs"
    manifest_path = output_root / "connector_intake_pack.manifest.json"

    source_catalog = _load_json(source_catalog_input)
    onboarding_plan = _load_json(onboarding_plan_input)
    connector_contracts = dict(source_catalog.get("connector_contracts", {}))
    work_items = _phase_1_work_items(onboarding_plan)

    connector_intakes: list[dict[str, Any]] = []
    template_paths: list[Path] = []
    mapping_paths: list[Path] = []

    for work_item in work_items:
        capability_code = work_item["capability_code"]
        contract = connector_contracts[capability_code]
        fieldnames = _field_names(contract)
        provider_profiles_payload = []
        for provider_profile in PROVIDER_ARCHETYPES[capability_code]:
            template_path = templates_root / f"{work_item['recommended_contract']}__{provider_profile['provider_profile_id']}.csv"
            _write_csv_template(template_path, fieldnames, provider_profile["sample_values"])
            if template_path not in template_paths:
                template_paths.append(template_path)

            mapping_stub = _mapping_stub(
                work_item=work_item,
                contract=contract,
                provider_profile=provider_profile,
                template_path=template_path,
                governance_bundle_path=governance_bundle_path,
            )
            mapping_path = mappings_root / f"{work_item['work_item_id']}__{provider_profile['provider_profile_id']}.json"
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text(json.dumps(mapping_stub, indent=2, sort_keys=True), encoding="utf-8")
            mapping_paths.append(mapping_path)

            provider_profiles_payload.append(
                {
                    "provider_profile_id": provider_profile["provider_profile_id"],
                    "label": provider_profile["label"],
                    "description": provider_profile["description"],
                    "recommended_when": provider_profile["recommended_when"],
                    "publication_tier": provider_profile["publication_tier"],
                    "retention_policy": provider_profile["retention_policy"],
                    "datex_exchange_fit": provider_profile["datex_exchange_fit"],
                    "template_path": str(template_path),
                    "mapping_stub_path": str(mapping_path),
                }
            )

        connector_intakes.append(
            {
                "work_item_id": work_item["work_item_id"],
                "municipality_label": work_item["municipality_label"],
                "capability_code": capability_code,
                "capability_label": work_item["capability_label"],
                "owner_scope": work_item["owner_scope"],
                "recommended_contract": work_item["recommended_contract"],
                "provider_profiles": provider_profiles_payload,
                "rights_matrix_row_count": len(provider_profiles_payload),
                "governance_gates": work_item.get("governance_gates", []),
                "quality_checks": work_item.get("quality_checks", []),
            }
        )

    rights_rows = _rights_matrix_rows(work_items)
    _write_rights_matrix(rights_matrix_path, rights_rows)

    payload = {
        "exposure_connector_intake_version": EXPOSURE_CONNECTOR_INTAKE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_catalog_path": str(source_catalog_input),
        "onboarding_plan_path": str(onboarding_plan_input),
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[
                EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
                EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
            ],
            source_family_ids=sorted(
                {exposure_source_family_id(str(item.get("capability_code") or "")) for item in work_items}
            ),
            role_policy_ids=artifact_role_policy_ids(
                EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
                EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
            ),
        ),
        "connector_intakes": connector_intakes,
        "stats": {
            "municipality_count": len({item["municipality_label"] for item in work_items}),
            "phase_1_work_item_count": len(work_items),
            "template_count": len(template_paths),
            "mapping_stub_count": len(mapping_paths),
            "rights_matrix_row_count": len(rights_rows),
        },
    }
    pack_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    pack_markdown_path.write_text(_markdown(payload), encoding="utf-8")

    manifest = {
        "exposure_connector_intake_version": EXPOSURE_CONNECTOR_INTAKE_VERSION,
        "inputs": {
            "source_catalog_path": str(source_catalog_input),
            "source_catalog_sha256": _sha256(source_catalog_input),
            "onboarding_plan_path": str(onboarding_plan_input),
            "onboarding_plan_sha256": _sha256(onboarding_plan_input),
        },
        "outputs": {
            "pack_json_path": str(pack_json_path),
            "pack_json_sha256": _sha256(pack_json_path),
            "pack_markdown_path": str(pack_markdown_path),
            "pack_markdown_sha256": _sha256(pack_markdown_path),
            "rights_matrix_path": str(rights_matrix_path),
            "rights_matrix_sha256": _sha256(rights_matrix_path),
            "sample_template_paths": [str(path) for path in template_paths],
            "mapping_stub_paths": [str(path) for path in mapping_paths],
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_connector_intake_pack",
            "public_contract_version": EXPOSURE_CONNECTOR_INTAKE_CONTRACT_VERSION,
            "exposure_connector_intake_version": EXPOSURE_CONNECTOR_INTAKE_VERSION,
        },
        "governance": payload["governance"],
        "stats": payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "exposure_source_catalog_json",
                    source_catalog_input,
                    _sha256(source_catalog_input),
                ),
                _artifact_reference(
                    "exposure_onboarding_plan_json",
                    onboarding_plan_input,
                    _sha256(onboarding_plan_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "connector_intake_pack_json",
                    pack_json_path,
                    _sha256(pack_json_path),
                ),
                _artifact_reference(
                    "connector_intake_pack_markdown",
                    pack_markdown_path,
                    _sha256(pack_markdown_path),
                ),
                _artifact_reference(
                    "source_rights_matrix_csv",
                    rights_matrix_path,
                    _sha256(rights_matrix_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    f"sample_template:{path.stem}",
                    path,
                    _sha256(path),
                )
                for path in template_paths
            ]
            + [
                _artifact_reference(
                    f"mapping_stub:{path.stem}",
                    path,
                    _sha256(path),
                )
                for path in mapping_paths
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_connector_intake_version": EXPOSURE_CONNECTOR_INTAKE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": payload["stats"],
    }
