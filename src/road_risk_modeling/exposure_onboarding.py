"""Build an actionable exposure-connector onboarding plan from the source catalog."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_ONBOARDING_PLAN_VERSION = "exposure_onboarding_plan_v1"
EXPOSURE_ONBOARDING_PLAN_CONTRACT_VERSION = "exposure_onboarding_plan_public_v1"

PHASES = [
    {
        "phase_code": "phase_1_foundational_flow_and_speed",
        "sequence": 1,
        "label": "Phase 1 - Foundational flow and speed coverage",
        "goal": "Secure municipality-grade motorized exposure and observed-speed feeds on the current scored network.",
        "horizon_alignment": ["D6-14", "PHOEBE", "iDriving", "CONDUCTOR"],
    },
    {
        "phase_code": "phase_2_vru_crossings_and_corridors",
        "sequence": 2,
        "label": "Phase 2 - VRU crossings and corridor coverage",
        "goal": "Add pedestrian, cyclist, and micromobility exposure at crossings, schools, retail frontages, and very-high tiles.",
        "horizon_alignment": ["D6-13", "SOTERIA", "AI4CCAM", "VeVuSafety"],
    },
    {
        "phase_code": "phase_3_scaling_and_refresh",
        "sequence": 3,
        "label": "Phase 3 - Scaling, refresh, and governance hardening",
        "goal": "Turn pilot connectors into repeatable refresh pipelines with publication rules and cross-owner coverage.",
        "horizon_alignment": ["D6-14", "AI4CCAM", "CONDUCTOR"],
    },
]

EXECUTION_PROFILES = {
    "motorized_exposure": {
        "phase_code": "phase_1_foundational_flow_and_speed",
        "acquisition_mode": "aggregate_counts_or_floating_car_flow",
        "delivery_cadence_target": "daily refresh preferred, hourly accepted where already available",
        "minimum_viable_coverage": (
            "Cover the top 15 percent predicted-risk segments, principal arterials, ring roads, and the leading intervention corridors."
        ),
        "pilot_acceptance_gate": (
            "At least 180 days of aggregated flow coverage with join-key resolution above 95 percent on the active scored network."
        ),
        "priority_partner_roles": [
            "municipal mobility department",
            "traffic control center",
            "regional mobility agency",
        ],
        "delivery_artifacts": [
            "signed provider intake record",
            "sample aggregated extract",
            "join-quality validation report",
            "exposure-enriched segment layer",
        ],
        "blocking_dependencies": [
            "segment_id_or_junction_id join table confirmed",
            "provider rights and publication tier registered",
        ],
    },
    "speed_observation": {
        "phase_code": "phase_1_foundational_flow_and_speed",
        "acquisition_mode": "aggregated_probe_speed_or_fixed_counter_export",
        "delivery_cadence_target": "hourly or 15-minute aggregates on priority corridors",
        "minimum_viable_coverage": (
            "Cover the same high-risk and high-volume corridor set as motorized exposure, including junction approaches where feasible."
        ),
        "pilot_acceptance_gate": (
            "Observed speed distributions with sample-size metadata and speed-limit alignment on at least 80 percent of the priority corridor set."
        ),
        "priority_partner_roles": [
            "traffic control center",
            "ITS operator",
            "probe data provider",
        ],
        "delivery_artifacts": [
            "speed provider metadata sheet",
            "hourly aggregate extract",
            "speed quality report",
            "speed-enriched segment layer",
        ],
        "blocking_dependencies": [
            "connector contract approved",
            "retention and access policy registered",
        ],
    },
    "vru_exposure": {
        "phase_code": "phase_2_vru_crossings_and_corridors",
        "acquisition_mode": "counter_program_or_privacy_reviewed_mobile_video_aggregate",
        "delivery_cadence_target": "daily aggregates with campaign-based refresh accepted for the first pilot",
        "minimum_viable_coverage": (
            "Cover very-high hotspot tiles, school zones, retail frontages, and the crossings attached to the top intervention corridors."
        ),
        "pilot_acceptance_gate": (
            "Pedestrian and cyclist counts available for the top hotspot set with documented method, privacy review, and join coverage above 90 percent."
        ),
        "priority_partner_roles": [
            "municipal mobility department",
            "local police",
            "shared mobility operators",
            "school mobility manager",
        ],
        "delivery_artifacts": [
            "VRU counting scope note",
            "privacy and ethics review log",
            "crossing or corridor count extract",
            "VRU-enriched segment or crossing layer",
        ],
        "blocking_dependencies": [
            "crossing and hotspot targeting list exported",
            "privacy review completed for mobile or video-based sources",
        ],
    },
}


def _load_catalog(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("datasets"), list):
        raise RuntimeError("Exposure source catalog JSON must include a top-level 'datasets' list.")
    return payload


def _slugify(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _phase_index() -> dict[str, dict[str, Any]]:
    return {
        phase["phase_code"]: phase
        for phase in PHASES
    }


def _find_owner_profile(scope: str, owner_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for profile in owner_profiles:
        if profile.get("scope") == scope:
            return profile
    return {
        "scope": scope,
        "description": f"{scope.title()} owner profile not yet documented.",
        "likely_partners": [],
    }


def _work_item(
    dataset: dict[str, Any],
    backlog_item: dict[str, Any],
    owner_scope: str,
    *,
    sequence: int,
    owner_profiles: list[dict[str, Any]],
    connector_contracts: dict[str, Any],
) -> dict[str, Any]:
    capability_code = backlog_item["capability_code"]
    execution_profile = EXECUTION_PROFILES[capability_code]
    connector_contract = connector_contracts.get(capability_code, {})
    owner_profile = _find_owner_profile(owner_scope, owner_profiles)
    phase = _phase_index()[execution_profile["phase_code"]]
    municipality_slug = _slugify(dataset["label"])
    return {
        "work_item_id": f"{municipality_slug}_{sequence:02d}_{capability_code}_{owner_scope}",
        "municipality_label": dataset["label"],
        "dataset_path": dataset["dataset_path"],
        "sequence": sequence,
        "phase_code": phase["phase_code"],
        "phase_label": phase["label"],
        "phase_sequence": phase["sequence"],
        "capability_code": capability_code,
        "capability_label": backlog_item["capability_label"],
        "priority": backlog_item["priority"],
        "current_status": backlog_item["current_status"],
        "connector_contract_state": backlog_item.get("connector_contract_state") or "unknown",
        "connector_mapping_stub_count": int(backlog_item.get("connector_mapping_stub_count") or 0),
        "ready_connector_profiles": list(backlog_item.get("ready_connector_profiles") or []),
        "owner_scope": owner_scope,
        "owner_description": owner_profile["description"],
        "priority_partner_roles": sorted(
            {
                *owner_profile.get("likely_partners", []),
                *execution_profile["priority_partner_roles"],
            }
        ),
        "recommended_contract": backlog_item["recommended_contract"],
        "target_objects": backlog_item["target_objects"],
        "preferred_time_grain": backlog_item["preferred_time_grain"],
        "acquisition_mode": execution_profile["acquisition_mode"],
        "delivery_cadence_target": execution_profile["delivery_cadence_target"],
        "minimum_viable_coverage": execution_profile["minimum_viable_coverage"],
        "pilot_acceptance_gate": execution_profile["pilot_acceptance_gate"],
        "governance_gates": [
            "source rights matrix entry approved",
            "restricted vs public publication tier assigned",
            *(connector_contract.get("governance_requirements", []) or []),
        ],
        "quality_checks": connector_contract.get("quality_checks", []) or [],
        "delivery_artifacts": execution_profile["delivery_artifacts"],
        "blocking_dependencies": execution_profile["blocking_dependencies"],
        "next_action": backlog_item["next_action"],
        "horizon_alignment": backlog_item["horizon_alignment"],
    }


def _municipality_plan(
    dataset: dict[str, Any],
    owner_profiles: list[dict[str, Any]],
    connector_contracts: dict[str, Any],
) -> dict[str, Any]:
    work_items: list[dict[str, Any]] = []
    sequence = 1
    for owner_scope in dataset.get("road_owner_scopes", []):
        for backlog_item in dataset.get("priority_connector_backlog", []):
            work_items.append(
                _work_item(
                    dataset,
                    backlog_item,
                    owner_scope,
                    sequence=sequence,
                    owner_profiles=owner_profiles,
                    connector_contracts=connector_contracts,
                )
            )
            sequence += 1

    work_items.sort(
        key=lambda item: (
            int(item["phase_sequence"]),
            int(item["priority"]),
            int(item["sequence"]),
        )
    )
    immediate_actions = [
        f"{item['capability_label']}: {item['next_action']}"
        for item in work_items[:3]
    ]
    return {
        "label": dataset["label"],
        "dataset_path": dataset["dataset_path"],
        "road_owner_scopes": dataset.get("road_owner_scopes", []),
        "work_item_count": len(work_items),
        "immediate_actions": immediate_actions,
        "work_items": work_items,
    }


def _owner_engagement_matrix(
    municipality_plans: list[dict[str, Any]],
    owner_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for profile in owner_profiles:
        scope = profile["scope"]
        scoped_items = [
            work_item
            for municipality in municipality_plans
            for work_item in municipality["work_items"]
            if work_item["owner_scope"] == scope
        ]
        if not scoped_items:
            continue
        matrix.append(
            {
                "owner_scope": scope,
                "description": profile["description"],
                "likely_partners": profile.get("likely_partners", []),
                "municipalities": sorted({item["municipality_label"] for item in scoped_items}),
                "capabilities": sorted({item["capability_code"] for item in scoped_items}),
                "work_item_count": len(scoped_items),
                "first_phase_sequence": min(item["phase_sequence"] for item in scoped_items),
            }
        )
    return matrix


def _matrix_rows(municipality_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for municipality in municipality_plans:
        for work_item in municipality["work_items"]:
            rows.append(
                {
                    "work_item_id": work_item["work_item_id"],
                    "municipality_label": work_item["municipality_label"],
                    "phase_code": work_item["phase_code"],
                    "phase_label": work_item["phase_label"],
                    "sequence": work_item["sequence"],
                    "capability_code": work_item["capability_code"],
                    "capability_label": work_item["capability_label"],
                    "owner_scope": work_item["owner_scope"],
                    "connector_contract_state": work_item["connector_contract_state"],
                    "connector_mapping_stub_count": work_item["connector_mapping_stub_count"],
                    "ready_connector_profiles": ", ".join(work_item["ready_connector_profiles"]),
                    "recommended_contract": work_item["recommended_contract"],
                    "preferred_time_grain": work_item["preferred_time_grain"],
                    "acquisition_mode": work_item["acquisition_mode"],
                    "delivery_cadence_target": work_item["delivery_cadence_target"],
                    "minimum_viable_coverage": work_item["minimum_viable_coverage"],
                    "pilot_acceptance_gate": work_item["pilot_acceptance_gate"],
                    "next_action": work_item["next_action"],
                    "horizon_alignment": ", ".join(work_item["horizon_alignment"]),
                }
            )
    return rows


def _write_matrix_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "work_item_id",
        "municipality_label",
        "phase_code",
        "phase_label",
        "sequence",
        "capability_code",
        "capability_label",
        "owner_scope",
        "connector_contract_state",
        "connector_mapping_stub_count",
        "ready_connector_profiles",
        "recommended_contract",
        "preferred_time_grain",
        "acquisition_mode",
        "delivery_cadence_target",
        "minimum_viable_coverage",
        "pilot_acceptance_gate",
        "next_action",
        "horizon_alignment",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Exposure Connector Onboarding Plan",
        "",
        "This plan converts the exposure source catalog into phased, municipality-specific onboarding work for real flow, speed, and VRU feeds.",
        "",
        "## Phase Structure",
        "",
    ]
    for phase in payload["phases"]:
        lines.extend(
            [
                f"### {phase['label']}",
                "",
                f"- Goal: {phase['goal']}",
                f"- Horizon alignment: `{', '.join(phase['horizon_alignment'])}`",
                "",
            ]
        )

    lines.extend(["## Municipality Rollout", ""])
    for municipality in payload["municipality_plans"]:
        lines.extend(
            [
                f"### {municipality['label']}",
                "",
                f"- Dataset path: `{municipality['dataset_path']}`",
                f"- Road-owner scopes: `{', '.join(municipality['road_owner_scopes'])}`",
                f"- Work items: `{municipality['work_item_count']}`",
                "",
            ]
        )
        for work_item in municipality["work_items"]:
            lines.append(
                f"1. **{work_item['capability_label']}** via `{work_item['recommended_contract']}` "
                f"for `{work_item['owner_scope']}` owner scope. "
                f"Contract state: `{work_item['connector_contract_state']}` "
                f"({work_item['connector_mapping_stub_count']} stubs; ready profiles: {', '.join(work_item['ready_connector_profiles']) or 'none'}). "
                f"Mode: `{work_item['acquisition_mode']}`. "
                f"Coverage target: {work_item['minimum_viable_coverage']} "
                f"Acceptance gate: {work_item['pilot_acceptance_gate']}"
            )
        lines.append("")

    lines.extend(["## Owner Engagement", ""])
    for owner_scope in payload["owner_engagement_matrix"]:
        lines.extend(
            [
                f"### {owner_scope['owner_scope']}",
                "",
                f"- Municipalities: `{', '.join(owner_scope['municipalities'])}`",
                f"- Capabilities: `{', '.join(owner_scope['capabilities'])}`",
                f"- Likely partners: `{', '.join(owner_scope['likely_partners'])}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_exposure_onboarding_plan(
    *,
    source_catalog_path: str | Path = "data/planning/exposure_sources/exposure_source_catalog.json",
    output_dir: str | Path = "data/planning/exposure_onboarding",
) -> dict[str, Any]:
    source_catalog_input = Path(source_catalog_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    plan_json_path = output_root / "exposure_onboarding_plan.json"
    plan_markdown_path = output_root / "exposure_onboarding_plan.md"
    matrix_csv_path = output_root / "connector_onboarding_matrix.csv"
    manifest_path = output_root / "exposure_onboarding_plan.manifest.json"

    source_catalog = _load_catalog(source_catalog_input)
    owner_profiles = list(source_catalog.get("owner_profiles", []))
    connector_contracts = dict(source_catalog.get("connector_contracts", {}))
    municipality_plans = [
        _municipality_plan(dataset, owner_profiles, connector_contracts)
        for dataset in source_catalog.get("datasets", [])
    ]
    municipality_plans.sort(key=lambda item: item["label"])
    owner_engagement_matrix = _owner_engagement_matrix(municipality_plans, owner_profiles)
    matrix_rows = _matrix_rows(municipality_plans)

    payload = {
        "exposure_onboarding_plan_version": EXPOSURE_ONBOARDING_PLAN_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_catalog_path": str(source_catalog_input),
        "phases": PHASES,
        "municipality_plans": municipality_plans,
        "owner_engagement_matrix": owner_engagement_matrix,
        "stats": {
            "dataset_count": len(municipality_plans),
            "work_item_count": len(matrix_rows),
            "phase_count": len(PHASES),
            "active_phase_count": len({row["phase_code"] for row in matrix_rows}),
            "owner_scope_count": len(owner_engagement_matrix),
            "priority_one_work_item_count": sum(
                1
                for municipality in municipality_plans
                for work_item in municipality["work_items"]
                if int(work_item["priority"]) == 1
            ),
        },
    }
    plan_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    plan_markdown_path.write_text(_plan_markdown(payload), encoding="utf-8")
    _write_matrix_csv(matrix_csv_path, matrix_rows)

    manifest = {
        "exposure_onboarding_plan_version": EXPOSURE_ONBOARDING_PLAN_VERSION,
        "inputs": {
            "source_catalog_path": str(source_catalog_input),
            "source_catalog_sha256": _sha256(source_catalog_input),
        },
        "outputs": {
            "plan_json_path": str(plan_json_path),
            "plan_json_sha256": _sha256(plan_json_path),
            "plan_markdown_path": str(plan_markdown_path),
            "plan_markdown_sha256": _sha256(plan_markdown_path),
            "matrix_csv_path": str(matrix_csv_path),
            "matrix_csv_sha256": _sha256(matrix_csv_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_onboarding_plan",
            "public_contract_version": EXPOSURE_ONBOARDING_PLAN_CONTRACT_VERSION,
            "exposure_onboarding_plan_version": EXPOSURE_ONBOARDING_PLAN_VERSION,
        },
        "stats": payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "exposure_source_catalog_json",
                    source_catalog_input,
                    _sha256(source_catalog_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "exposure_onboarding_plan_json",
                    plan_json_path,
                    _sha256(plan_json_path),
                ),
                _artifact_reference(
                    "exposure_onboarding_plan_markdown",
                    plan_markdown_path,
                    _sha256(plan_markdown_path),
                ),
                _artifact_reference(
                    "connector_onboarding_matrix_csv",
                    matrix_csv_path,
                    _sha256(matrix_csv_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_onboarding_plan_version": EXPOSURE_ONBOARDING_PLAN_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": payload["stats"],
    }
