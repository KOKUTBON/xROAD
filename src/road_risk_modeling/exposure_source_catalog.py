"""Build an exposure source catalog and connector contracts from the readiness report."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_SOURCE_CATALOG_VERSION = "exposure_source_catalog_v1"
EXPOSURE_SOURCE_CATALOG_CONTRACT_VERSION = "exposure_source_catalog_public_v1"

OWNER_PROFILES = [
    {
        "scope": "municipal",
        "description": "City or municipal operators covering urban streets, signals, crossings, and local counters.",
        "likely_partners": [
            "municipal mobility department",
            "traffic control center",
            "local police",
            "shared mobility operators",
        ],
    },
    {
        "scope": "provincial",
        "description": "Provincial road authorities covering extra-urban corridors and province-owned count infrastructure.",
        "likely_partners": [
            "province road service",
            "province ITS unit",
            "contracted count providers",
        ],
    },
    {
        "scope": "regional",
        "description": "Regional coordination bodies aggregating ITS, planning, and mobility data across municipalities.",
        "likely_partners": [
            "regional mobility agency",
            "regional open-data office",
            "regional transport observatory",
        ],
    },
    {
        "scope": "national",
        "description": "National operators or concessionaires covering strategic roads and intercity traffic feeds.",
        "likely_partners": [
            "national road operator",
            "motorway concessionaire",
            "national access point",
        ],
    },
]

CONNECTOR_TEMPLATES = {
    "motorized_exposure": {
        "contract_name": "motorized_exposure_connector_v1",
        "capability_code": "motorized_exposure",
        "target_objects": ["segment", "junction"],
        "preferred_time_grain": "daily_or_hourly_aggregate",
        "horizon_alignment": ["D6-14", "PHOEBE", "iDriving", "CONDUCTOR"],
        "required_fields": [
            {"name": "source_record_id", "type": "string"},
            {"name": "provider_name", "type": "string"},
            {"name": "road_owner_scope", "type": "enum", "allowed": ["municipal", "provincial", "regional", "national", "private"]},
            {"name": "join_key_type", "type": "enum", "allowed": ["segment_id", "junction_id"]},
            {"name": "join_key_value", "type": "string"},
            {"name": "observed_start_utc", "type": "datetime"},
            {"name": "observed_end_utc", "type": "datetime"},
            {"name": "vehicle_count", "type": "number"},
            {"name": "sample_size", "type": "integer"},
            {"name": "aggregation_method", "type": "string"},
        ],
        "optional_fields": [
            "aadt",
            "heavy_vehicle_share",
            "vehicle_km_estimate",
            "coverage_pct",
            "flow_quality_flag",
        ],
        "governance_requirements": [
            "aggregated_only_no_raw_vehicle_traces",
            "provider_license_registered",
            "publication_policy_defined",
        ],
        "quality_checks": [
            "non_negative_vehicle_count",
            "observed_start_before_end",
            "join_key_resolves_to_current_network_object",
            "coverage_threshold_documented",
        ],
    },
    "speed_observation": {
        "contract_name": "observed_speed_connector_v1",
        "capability_code": "speed_observation",
        "target_objects": ["segment", "junction_approach"],
        "preferred_time_grain": "hourly_or_15min_aggregate",
        "horizon_alignment": ["D6-14", "iDriving", "CONDUCTOR"],
        "required_fields": [
            {"name": "source_record_id", "type": "string"},
            {"name": "provider_name", "type": "string"},
            {"name": "road_owner_scope", "type": "enum", "allowed": ["municipal", "provincial", "regional", "national", "private"]},
            {"name": "join_key_type", "type": "enum", "allowed": ["segment_id", "junction_id", "junction_approach_id"]},
            {"name": "join_key_value", "type": "string"},
            {"name": "observed_start_utc", "type": "datetime"},
            {"name": "observed_end_utc", "type": "datetime"},
            {"name": "mean_speed_kph", "type": "number"},
            {"name": "p85_speed_kph", "type": "number"},
            {"name": "sample_size", "type": "integer"},
        ],
        "optional_fields": [
            "speed_std_kph",
            "speed_variance",
            "speed_limit_kph",
            "probe_penetration_rate",
            "speed_quality_flag",
        ],
        "governance_requirements": [
            "aggregated_probe_or_sensor_output_only",
            "device_or_provider_metadata_registered",
            "retention_policy_defined",
        ],
        "quality_checks": [
            "non_negative_speed_values",
            "p85_not_below_mean",
            "observed_start_before_end",
            "sample_size_threshold_documented",
        ],
    },
    "vru_exposure": {
        "contract_name": "vru_exposure_connector_v1",
        "capability_code": "vru_exposure",
        "target_objects": ["crossing", "segment", "junction"],
        "preferred_time_grain": "daily_or_hourly_aggregate",
        "horizon_alignment": ["D6-13", "SOTERIA", "AI4CCAM", "VeVuSafety"],
        "required_fields": [
            {"name": "source_record_id", "type": "string"},
            {"name": "provider_name", "type": "string"},
            {"name": "road_owner_scope", "type": "enum", "allowed": ["municipal", "provincial", "regional", "national", "private"]},
            {"name": "join_key_type", "type": "enum", "allowed": ["crossing_id", "segment_id", "junction_id"]},
            {"name": "join_key_value", "type": "string"},
            {"name": "observed_start_utc", "type": "datetime"},
            {"name": "observed_end_utc", "type": "datetime"},
            {"name": "pedestrian_count", "type": "number"},
            {"name": "cyclist_count", "type": "number"},
            {"name": "count_method", "type": "string"},
        ],
        "optional_fields": [
            "micromobility_trip_count",
            "crossing_flow",
            "school_zone_flag",
            "retail_frontage_flag",
            "count_quality_flag",
        ],
        "governance_requirements": [
            "aggregated_counts_only",
            "privacy_review_for_mobile_or_video_sources",
            "location_generalization_policy_defined_if_needed",
        ],
        "quality_checks": [
            "non_negative_mode_counts",
            "observed_start_before_end",
            "count_method_documented",
            "join_key_resolves_to_current_network_object",
        ],
    },
}


def _load_readiness_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("datasets"), list):
        raise RuntimeError("Exposure readiness JSON must include a top-level 'datasets' list.")
    return payload


def _infer_owner_scopes(label: str) -> list[str]:
    normalized = str(label).lower()
    scopes = ["municipal"]
    if "provinc" in normalized:
        scopes.append("provincial")
    return scopes


def _priority_connector_backlog(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    backlog: list[dict[str, Any]] = []
    for capability in dataset.get("capabilities", []):
        code = capability.get("code")
        if code not in CONNECTOR_TEMPLATES:
            continue
        if capability.get("status") == "available":
            continue
        template = CONNECTOR_TEMPLATES[code]
        contract_state = capability.get("connector_contract_state") or "unknown"
        current_status = capability.get("status")
        if current_status == "proxy_only" and contract_state == "contract_ready":
            current_status = "proxy_only_contract_ready"
        backlog.append(
            {
                "capability_code": code,
                "capability_label": capability.get("label"),
                "priority": capability.get("priority"),
                "current_status": current_status,
                "connector_contract_state": contract_state,
                "connector_mapping_stub_count": int(capability.get("connector_mapping_stub_count") or 0),
                "ready_connector_profiles": list(capability.get("ready_connector_profiles") or []),
                "recommended_contract": template["contract_name"],
                "target_objects": template["target_objects"],
                "preferred_time_grain": template["preferred_time_grain"],
                "horizon_alignment": template["horizon_alignment"],
                "next_action": capability.get("next_step"),
            }
        )
    backlog.sort(key=lambda item: (int(item["priority"]), item["capability_label"]))
    return backlog


def _dataset_catalog_entry(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": dataset["label"],
        "dataset_path": dataset["dataset_path"],
        "feature_count": dataset["feature_count"],
        "road_owner_scopes": _infer_owner_scopes(dataset["label"]),
        "priority_connector_backlog": _priority_connector_backlog(dataset),
    }


def _catalog_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Exposure Source Catalog",
        "",
        "This catalog turns the exposure-readiness gaps into concrete connector contracts and acquisition priorities.",
        "",
        "## Municipality Priorities",
        "",
    ]
    for dataset in payload["datasets"]:
        lines.extend(
            [
                f"### {dataset['label']}",
                "",
                f"- Dataset path: `{dataset['dataset_path']}`",
                f"- Feature count: `{dataset['feature_count']}`",
                f"- Road-owner scopes to engage: `{', '.join(dataset['road_owner_scopes'])}`",
                "",
            ]
        )
        for backlog_item in dataset["priority_connector_backlog"]:
            lines.append(
                f"1. **{backlog_item['capability_label']}** (`{backlog_item['current_status']}`). "
                f"Contract state: `{backlog_item['connector_contract_state']}` "
                f"({backlog_item['connector_mapping_stub_count']} stubs; ready profiles: {', '.join(backlog_item['ready_connector_profiles']) or 'none'}). "
                f"Use `{backlog_item['recommended_contract']}` at `{backlog_item['preferred_time_grain']}` granularity. "
                f"Next: {backlog_item['next_action']}"
            )
        lines.append("")

    lines.extend(["## Connector Contracts", ""])
    for code, template in sorted(CONNECTOR_TEMPLATES.items()):
        lines.extend(
            [
                f"### {template['contract_name']}",
                "",
                f"- Capability: `{code}`",
                f"- Target objects: `{', '.join(template['target_objects'])}`",
                f"- Preferred time grain: `{template['preferred_time_grain']}`",
                f"- Horizon alignment: `{', '.join(template['horizon_alignment'])}`",
                f"- Required fields: `{', '.join(field['name'] for field in template['required_fields'])}`",
                f"- Optional fields: `{', '.join(template['optional_fields'])}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_exposure_source_catalog(
    *,
    readiness_report_path: str | Path = "data/planning/exposure_readiness/exposure_readiness.json",
    output_dir: str | Path = "data/planning/exposure_sources",
) -> dict[str, Any]:
    readiness_input = Path(readiness_report_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    catalog_json_path = output_root / "exposure_source_catalog.json"
    catalog_markdown_path = output_root / "exposure_source_catalog.md"
    connector_contracts_path = output_root / "connector_contracts.json"
    manifest_path = output_root / "exposure_source_catalog.manifest.json"

    readiness = _load_readiness_report(readiness_input)
    dataset_catalog = [
        _dataset_catalog_entry(dataset)
        for dataset in readiness.get("datasets", [])
    ]
    dataset_catalog.sort(key=lambda item: item["label"])

    payload = {
        "exposure_source_catalog_version": EXPOSURE_SOURCE_CATALOG_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_readiness_report_path": str(readiness_input),
        "datasets": dataset_catalog,
        "owner_profiles": OWNER_PROFILES,
        "connector_contracts": CONNECTOR_TEMPLATES,
        "stats": {
            "dataset_count": len(dataset_catalog),
            "connector_contract_count": len(CONNECTOR_TEMPLATES),
            "owner_scope_count": len(OWNER_PROFILES),
            "priority_connector_gap_count": sum(
                len(dataset["priority_connector_backlog"])
                for dataset in dataset_catalog
            ),
        },
    }
    catalog_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    catalog_markdown_path.write_text(_catalog_markdown(payload), encoding="utf-8")
    connector_contracts_path.write_text(json.dumps(CONNECTOR_TEMPLATES, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "exposure_source_catalog_version": EXPOSURE_SOURCE_CATALOG_VERSION,
        "inputs": {
            "readiness_report_path": str(readiness_input),
            "readiness_report_sha256": _sha256(readiness_input),
        },
        "outputs": {
            "catalog_json_path": str(catalog_json_path),
            "catalog_json_sha256": _sha256(catalog_json_path),
            "catalog_markdown_path": str(catalog_markdown_path),
            "catalog_markdown_sha256": _sha256(catalog_markdown_path),
            "connector_contracts_path": str(connector_contracts_path),
            "connector_contracts_sha256": _sha256(connector_contracts_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_source_catalog",
            "public_contract_version": EXPOSURE_SOURCE_CATALOG_CONTRACT_VERSION,
            "exposure_source_catalog_version": EXPOSURE_SOURCE_CATALOG_VERSION,
        },
        "stats": payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "exposure_readiness_json",
                    readiness_input,
                    _sha256(readiness_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "exposure_source_catalog_json",
                    catalog_json_path,
                    _sha256(catalog_json_path),
                ),
                _artifact_reference(
                    "exposure_source_catalog_markdown",
                    catalog_markdown_path,
                    _sha256(catalog_markdown_path),
                ),
                _artifact_reference(
                    "exposure_connector_contracts_json",
                    connector_contracts_path,
                    _sha256(connector_contracts_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_source_catalog_version": EXPOSURE_SOURCE_CATALOG_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": payload["stats"],
    }
