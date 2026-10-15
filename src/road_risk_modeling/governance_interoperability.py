"""Shared governance and interoperability bundle for live-source and published artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
import csv
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


GOVERNANCE_INTEROPERABILITY_VERSION = "governance_interoperability_bundle_v1"
GOVERNANCE_INTEROPERABILITY_CONTRACT_VERSION = "governance_interoperability_bundle_public_v1"
DEFAULT_GOVERNANCE_OUTPUT_DIR = Path("data/planning/governance_interoperability")
DEFAULT_GOVERNANCE_BUNDLE_PATH = DEFAULT_GOVERNANCE_OUTPUT_DIR / "governance_interoperability_bundle.json"

EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY = "exposure_connector_intake_pack"
EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY = "exposure_connector_mapping_stub"
EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY = "exposure_connector_observations"
SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY = "signal_phase_intake_pack"
SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY = "signal_phase_mapping_stub"
SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY = "signal_phase_records"
SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY = "signal_phase_support_artifact"
SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY = "segment_scores_public_geojson"
SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY = "segment_scores_analyst_csv"
SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY = "segment_score_tiles_public_geojson"

EXPOSURE_SOURCE_FAMILY_BY_CAPABILITY = {
    "motorized_exposure": "exposure_motorized_aggregate",
    "speed_observation": "exposure_speed_aggregate",
}

SIGNAL_PHASE_SOURCE_FAMILY_BY_PROFILE = {
    "signal_stage_plan_export": "signal_stage_plan_export",
    "controller_event_log_export": "signal_controller_event_log_export",
    "arm_phase_mapping_sheet": "signal_arm_phase_mapping_sheet",
    "junction_phase_diagram_support": "signal_junction_phase_diagram_support",
}

SOURCE_GOVERNANCE_DECISIONS = [
    {
        "source_family_id": "exposure_motorized_aggregate",
        "domain_family": "exposure",
        "label": "Motorized exposure aggregates",
        "planned_status": "planned_partner_or_municipal_feed",
        "artifact_family_ids": [
            EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
            EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
            EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_aggregates_with_public_summary",
        "publication_status": "restricted_input_public_summary_only",
        "rights_basis": "provider or municipal aggregate license review",
        "retention_policy": "retain approved aggregates under provider or municipality terms only",
        "governance_decision": "Only aggregated flow extracts are accepted; raw probe traces and raw device exhaust stay out of the repo.",
        "exchange_pattern_id": "batch_provider_extract",
        "datex_alignment_id": "datex_exposure_motorized_aggregate",
        "datex_profile": "MeasuredDataPublication concept mapping",
        "datex_exchange_fit": "medium",
        "mobility_data_space_handoff_id": "handoff_batch_provider_extract",
        "mobility_data_space_readiness": "metadata-ready bilateral exchange",
        "role_boundary": "restricted pipeline and partner operators only",
    },
    {
        "source_family_id": "exposure_speed_aggregate",
        "domain_family": "exposure",
        "label": "Observed-speed aggregates",
        "planned_status": "planned_partner_or_municipal_feed",
        "artifact_family_ids": [
            EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
            EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
            EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_aggregates_with_public_summary",
        "publication_status": "restricted_input_public_summary_only",
        "rights_basis": "provider or municipal aggregate license review",
        "retention_policy": "retain only delivered speed aggregates and purge raw device exports",
        "governance_decision": "Speed joins can enter model features only after source-rights review and aggregate-only validation.",
        "exchange_pattern_id": "batch_provider_extract",
        "datex_alignment_id": "datex_exposure_speed_aggregate",
        "datex_profile": "MeasuredDataPublication concept mapping",
        "datex_exchange_fit": "high",
        "mobility_data_space_handoff_id": "handoff_batch_provider_extract",
        "mobility_data_space_readiness": "metadata-ready bilateral exchange",
        "role_boundary": "restricted pipeline and partner operators only",
    },
    {
        "source_family_id": "signal_stage_plan_export",
        "domain_family": "signal_phase",
        "label": "Signal stage-plan exports",
        "planned_status": "restricted_live_partner_delivery",
        "artifact_family_ids": [
            SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
            SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
            SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_operational_control",
        "publication_status": "restricted_input_public_derivatives_only",
        "rights_basis": "signal operator delivery authorization",
        "retention_policy": "retain approved plan tables for up to 24 months while the control plan remains current",
        "governance_decision": "Control plans are restricted operational inputs and can only surface through derived movement-risk products.",
        "exchange_pattern_id": "restricted_signal_plan_export",
        "datex_alignment_id": "datex_signal_stage_plan_export",
        "datex_profile": "Signal plan and timing concept mapping",
        "datex_exchange_fit": "medium",
        "mobility_data_space_handoff_id": "handoff_operational_signal_export",
        "mobility_data_space_readiness": "operator-governed restricted handoff",
        "role_boundary": "restricted pipeline and approved mobility operators only",
    },
    {
        "source_family_id": "signal_controller_event_log_export",
        "domain_family": "signal_phase",
        "label": "Signal controller event logs",
        "planned_status": "restricted_live_partner_delivery",
        "artifact_family_ids": [
            SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
            SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
            SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_operational_control",
        "publication_status": "restricted_input_public_derivatives_only",
        "rights_basis": "signal operator delivery authorization",
        "retention_policy": "retain aggregated controller events for up to 12 months unless stricter operator rules apply",
        "governance_decision": "Controller-state logs stay restricted because they expose operational control behavior and device scope.",
        "exchange_pattern_id": "restricted_controller_event_export",
        "datex_alignment_id": "datex_signal_controller_event_log_export",
        "datex_profile": "Signal-state and measured-data concept mapping",
        "datex_exchange_fit": "high",
        "mobility_data_space_handoff_id": "handoff_operational_signal_export",
        "mobility_data_space_readiness": "operator-governed restricted handoff",
        "role_boundary": "restricted pipeline and approved mobility operators only",
    },
    {
        "source_family_id": "signal_arm_phase_mapping_sheet",
        "domain_family": "signal_phase",
        "label": "Arm-to-phase mapping sheets",
        "planned_status": "restricted_internal_mapping",
        "artifact_family_ids": [
            SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
            SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
            SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_internal_mapping",
        "publication_status": "internal_mapping_only",
        "rights_basis": "internal analyst interpretation with operator confirmation",
        "retention_policy": "retain while the mapped junction geometry and control logic remain current",
        "governance_decision": "Movement-to-phase mappings remain internal working artifacts and are never published directly.",
        "exchange_pattern_id": "analyst_mapping_workbook",
        "datex_alignment_id": "datex_signal_arm_phase_mapping_sheet",
        "datex_profile": "Analyst-side concept mapping only",
        "datex_exchange_fit": "low",
        "mobility_data_space_handoff_id": "handoff_internal_analyst_workbook",
        "mobility_data_space_readiness": "internal only",
        "role_boundary": "restricted pipeline and analysts only",
    },
    {
        "source_family_id": "signal_junction_phase_diagram_support",
        "domain_family": "signal_phase",
        "label": "Junction phase-diagram support",
        "planned_status": "restricted_support_delivery",
        "artifact_family_ids": [
            SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
            SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_operational_support",
        "publication_status": "internal_support_only",
        "rights_basis": "operator support-artifact sharing approval",
        "retention_policy": "retain only the latest validated support file while layout and control remain current",
        "governance_decision": "Support diagrams are restricted because they expose operational layouts and are used only for interpretation.",
        "exchange_pattern_id": "support_diagram_attachment",
        "datex_alignment_id": "datex_signal_junction_phase_diagram_support",
        "datex_profile": "No direct DATEX publication target",
        "datex_exchange_fit": "low",
        "mobility_data_space_handoff_id": "handoff_support_attachment",
        "mobility_data_space_readiness": "attachment-style handoff only",
        "role_boundary": "restricted pipeline and approved operators only",
    },
    {
        "source_family_id": "bari_open_data_crash_feed",
        "domain_family": "crash_feed",
        "label": "Official Bari open-data crash feed",
        "planned_status": "active_public_source",
        "artifact_family_ids": [
            "crash_feed_canonical_rows",
            "matched_node_records",
            "matched_movement_records",
        ],
        "publication_tier": "public_source_restricted_join_products",
        "publication_status": "public_source_with_restricted_row_level_reuse_review",
        "rights_basis": "municipal open-data publication terms",
        "retention_policy": "retain source snapshots with provenance and apply publication review before redistributing enriched row-level derivatives",
        "governance_decision": "The source is public, but enriched row-level crash derivatives still require role and publication review.",
        "exchange_pattern_id": "open_data_snapshot_download",
        "datex_alignment_id": "datex_bari_open_data_crash_feed",
        "datex_profile": "Situation-publication concept mapping",
        "datex_exchange_fit": "medium",
        "mobility_data_space_handoff_id": "handoff_open_data_snapshot",
        "mobility_data_space_readiness": "catalog-ready open-data handoff",
        "role_boundary": "public source with restricted enriched derivatives",
    },
    {
        "source_family_id": "future_live_traffic_state_feed",
        "domain_family": "traffic_feed",
        "label": "Future live traffic-state feeds",
        "planned_status": "future_live_feed",
        "artifact_family_ids": [
            "future_live_traffic_state",
            EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
        ],
        "publication_tier": "restricted_partner_feed",
        "publication_status": "restricted_input_public_aggregates_optional",
        "rights_basis": "future partner API or data-space agreement",
        "retention_policy": "retain only provider-approved state aggregates and document refresh cadence explicitly",
        "governance_decision": "Live traffic-state feeds should land through governed aggregation paths, not raw streaming traces.",
        "exchange_pattern_id": "near_real_time_partner_api",
        "datex_alignment_id": "datex_future_live_traffic_state_feed",
        "datex_profile": "MeasuredDataPublication or ElaboratedData concept mapping",
        "datex_exchange_fit": "high",
        "mobility_data_space_handoff_id": "handoff_streaming_data_space",
        "mobility_data_space_readiness": "data-space compatible with metadata and policy envelopes",
        "role_boundary": "restricted pipeline first, public only through derived aggregates",
    },
    {
        "source_family_id": "future_traffic_event_feed",
        "domain_family": "traffic_feed",
        "label": "Future traffic and event feeds",
        "planned_status": "future_live_feed",
        "artifact_family_ids": [
            "future_traffic_event_feed",
            "exposure_event_enrichment",
        ],
        "publication_tier": "restricted_partner_feed",
        "publication_status": "restricted_input_public_event_summary_optional",
        "rights_basis": "future operator or data-space event-sharing agreement",
        "retention_policy": "retain event snapshots only as long as the event-history policy allows",
        "governance_decision": "Traffic-event feeds should align to event publication concepts and only expose public summaries after agreement review.",
        "exchange_pattern_id": "event_api_or_datastream",
        "datex_alignment_id": "datex_future_traffic_event_feed",
        "datex_profile": "SituationPublication concept mapping",
        "datex_exchange_fit": "high",
        "mobility_data_space_handoff_id": "handoff_streaming_data_space",
        "mobility_data_space_readiness": "data-space compatible with metadata and policy envelopes",
        "role_boundary": "restricted pipeline first, public only through approved event summaries",
    },
]

ARTIFACT_ROLE_POLICIES = [
    {
        "role_policy_id": "exposure_connector_intake_pack__partner_onboarding",
        "artifact_family_id": EXPOSURE_CONNECTOR_INTAKE_ARTIFACT_FAMILY,
        "role": "partner_onboarding",
        "access_level": "restricted",
        "allowed_fields": ["provider_profiles", "connector_intakes", "source_rights_matrix_reference"],
        "restricted_fields": ["provider-delivered raw extracts"],
        "delivery_boundary": "Share templates, mapping stubs, and rights decisions only with approved onboarding counterparts.",
    },
    {
        "role_policy_id": "exposure_connector_mapping_stub__partner_onboarding",
        "artifact_family_id": EXPOSURE_CONNECTOR_MAPPING_STUB_ARTIFACT_FAMILY,
        "role": "partner_onboarding",
        "access_level": "restricted",
        "allowed_fields": ["provider profile id", "field mappings", "publication policy", "quality checks"],
        "restricted_fields": ["raw provider extracts"],
        "delivery_boundary": "Mapping stubs can be shared only with the provider or municipal team responsible for delivery.",
    },
    {
        "role_policy_id": "exposure_connector_observations__restricted_pipeline",
        "artifact_family_id": EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
        "role": "restricted_pipeline",
        "access_level": "allowed",
        "allowed_fields": [
            "observation_id",
            "provider_profile_id",
            "join_key_type",
            "join_key_value",
            "observed_start_utc",
            "observed_end_utc",
            "attributes",
        ],
        "restricted_fields": [],
        "delivery_boundary": "Use normalized connector observations only inside restricted processing zones and derived model features.",
    },
    {
        "role_policy_id": "exposure_connector_observations__public",
        "artifact_family_id": EXPOSURE_CONNECTOR_OBSERVATIONS_ARTIFACT_FAMILY,
        "role": "public",
        "access_level": "denied",
        "allowed_fields": [],
        "restricted_fields": ["all normalized connector records"],
        "delivery_boundary": "Public users receive only downstream score products and summary indicators.",
    },
    {
        "role_policy_id": "signal_phase_intake_pack__partner_ops",
        "artifact_family_id": SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
        "role": "partner_ops",
        "access_level": "restricted",
        "allowed_fields": ["top_priority_signals", "provider_profiles", "source_rights_matrix_reference"],
        "restricted_fields": ["delivered raw control exports"],
        "delivery_boundary": "Signal-phase intake packs can be shared only with approved operator or partner counterparts.",
    },
    {
        "role_policy_id": "signal_phase_mapping_stub__restricted_pipeline",
        "artifact_family_id": SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
        "role": "restricted_pipeline",
        "access_level": "allowed",
        "allowed_fields": ["profile_id", "field_mappings", "publication_policy", "target_join_strategy"],
        "restricted_fields": [],
        "delivery_boundary": "Mapping stubs are restricted operational contracts for controlled partner exchanges and ingestion.",
    },
    {
        "role_policy_id": "signal_phase_support_artifact__restricted_pipeline",
        "artifact_family_id": SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY,
        "role": "restricted_pipeline",
        "access_level": "allowed",
        "allowed_fields": ["validated support attachment references", "publication policy", "support validation rules"],
        "restricted_fields": [],
        "delivery_boundary": "Support artifacts stay inside restricted interpretation and QA workflows.",
    },
    {
        "role_policy_id": "signal_phase_records__restricted_pipeline",
        "artifact_family_id": SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
        "role": "restricted_pipeline",
        "access_level": "allowed",
        "allowed_fields": [
            "signal_phase_record_id",
            "profile_id",
            "junction_id",
            "phase_id",
            "stage_id",
            "attributes",
        ],
        "restricted_fields": [],
        "delivery_boundary": "Normalized signal-phase records stay restricted and can only drive internal movement mapping and model enrichment.",
    },
    {
        "role_policy_id": "signal_phase_records__public",
        "artifact_family_id": SIGNAL_PHASE_RECORDS_ARTIFACT_FAMILY,
        "role": "public",
        "access_level": "denied",
        "allowed_fields": [],
        "restricted_fields": ["all normalized signal-phase records"],
        "delivery_boundary": "Public users receive only downstream movement-risk and intervention outputs.",
    },
    {
        "role_policy_id": "segment_scores_public_geojson__public",
        "artifact_family_id": SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY,
        "role": "public",
        "access_level": "allowed",
        "allowed_fields": [
            "segment_score_id",
            "segment_id",
            "occurred_year",
            "prediction_run_label",
            "prediction_task",
            "public_score_index",
            "public_score_band",
            "score_decile",
        ],
        "restricted_fields": ["predicted_crash_count", "observed_crash_count", "internal feature columns"],
        "delivery_boundary": "Public publication is limited to banded and indexed scores without raw modeled or observed counts.",
    },
    {
        "role_policy_id": "segment_scores_analyst_csv__analyst",
        "artifact_family_id": SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY,
        "role": "analyst",
        "access_level": "allowed",
        "allowed_fields": [
            "segment_score_id",
            "segment_id",
            "occurred_year",
            "prediction_run_label",
            "prediction_task",
            "prediction_column",
            "predicted_crash_count",
            "observed_crash_count",
            "score_rank_desc",
            "score_percentile",
            "score_decile",
            "public_score_index",
            "public_score_band",
        ],
        "restricted_fields": ["connector raw extracts", "restricted signal-phase inputs"],
        "delivery_boundary": "Analyst access is role-gated and does not automatically confer access to restricted source feeds.",
    },
    {
        "role_policy_id": "segment_score_tiles_public_geojson__public",
        "artifact_family_id": SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY,
        "role": "public",
        "access_level": "allowed",
        "allowed_fields": [
            "tile_score_id",
            "occurred_year",
            "prediction_run_label",
            "prediction_task",
            "tile_size_m",
            "tile_segment_count",
            "tile_mean_public_score_index",
            "tile_max_public_score_index",
            "tile_public_score_band",
            "tile_score_decile",
        ],
        "restricted_fields": ["underlying analyst-only segment rows"],
        "delivery_boundary": "Public tiles expose aggregated spatial risk only.",
    },
]

EXCHANGE_PATTERNS = [
    {
        "exchange_pattern_id": "batch_provider_extract",
        "pattern_label": "Batch provider extract",
        "transport": "secure file handoff",
        "description": "Periodic CSV or equivalent aggregate extract delivered under provider or municipal review.",
    },
    {
        "exchange_pattern_id": "restricted_signal_plan_export",
        "pattern_label": "Restricted signal-plan export",
        "transport": "operator-approved file handoff",
        "description": "Signal plan tables shared as restricted operational extracts.",
    },
    {
        "exchange_pattern_id": "restricted_controller_event_export",
        "pattern_label": "Restricted controller-event export",
        "transport": "operator-approved file handoff",
        "description": "Aggregated controller event tables delivered with explicit operator rights scope.",
    },
    {
        "exchange_pattern_id": "analyst_mapping_workbook",
        "pattern_label": "Analyst mapping workbook",
        "transport": "restricted analyst workbook",
        "description": "Human-maintained mapping sheets with explicit QA and review steps.",
    },
    {
        "exchange_pattern_id": "support_diagram_attachment",
        "pattern_label": "Support diagram attachment",
        "transport": "restricted attachment exchange",
        "description": "Diagrams or support files attached to restricted handoff packets.",
    },
    {
        "exchange_pattern_id": "open_data_snapshot_download",
        "pattern_label": "Open-data snapshot",
        "transport": "public catalog download",
        "description": "Public snapshot download with provenance, versioning, and redistribution checks.",
    },
    {
        "exchange_pattern_id": "near_real_time_partner_api",
        "pattern_label": "Near-real-time partner API",
        "transport": "API or managed stream",
        "description": "Partner-governed API for traffic-state aggregates with policy controls.",
    },
    {
        "exchange_pattern_id": "event_api_or_datastream",
        "pattern_label": "Traffic-event API or datastream",
        "transport": "API or event stream",
        "description": "Event feeds aligned to incident or traffic-event publication concepts.",
    },
]

MOBILITY_DATA_SPACE_HANDOFFS = [
    {
        "mobility_data_space_handoff_id": "handoff_batch_provider_extract",
        "source_family_scope": ["exposure_motorized_aggregate", "exposure_speed_aggregate"],
        "mobility_data_space_readiness": "metadata-ready bilateral exchange",
        "handoff_pattern": "Attach contract metadata, publication tier, retention rule, and connector schema version to every delivered aggregate.",
        "required_metadata": ["provider profile", "publication tier", "retention policy", "connector contract version"],
    },
    {
        "mobility_data_space_handoff_id": "handoff_operational_signal_export",
        "source_family_scope": ["signal_stage_plan_export", "signal_controller_event_log_export"],
        "mobility_data_space_readiness": "operator-governed restricted handoff",
        "handoff_pattern": "Use operator-approved delivery manifests with junction scope, publication boundary, and operational retention metadata.",
        "required_metadata": ["junction scope", "operator rights scope", "publication tier", "retention policy"],
    },
    {
        "mobility_data_space_handoff_id": "handoff_internal_analyst_workbook",
        "source_family_scope": ["signal_arm_phase_mapping_sheet"],
        "mobility_data_space_readiness": "internal only",
        "handoff_pattern": "Keep analyst mapping workbooks inside internal review loops with no external publication route.",
        "required_metadata": ["junction scope", "review owner", "mapping revision"],
    },
    {
        "mobility_data_space_handoff_id": "handoff_support_attachment",
        "source_family_scope": ["signal_junction_phase_diagram_support"],
        "mobility_data_space_readiness": "attachment-style handoff only",
        "handoff_pattern": "Catalog support files with junction scope, file-type validation, and rights review before use.",
        "required_metadata": ["junction scope", "support artifact type", "validation state"],
    },
    {
        "mobility_data_space_handoff_id": "handoff_open_data_snapshot",
        "source_family_scope": ["bari_open_data_crash_feed"],
        "mobility_data_space_readiness": "catalog-ready open-data handoff",
        "handoff_pattern": "Preserve provenance, snapshot dates, and enrichment publication review for open-data crash feeds.",
        "required_metadata": ["snapshot date", "source URL", "license note", "enrichment publication review"],
    },
    {
        "mobility_data_space_handoff_id": "handoff_streaming_data_space",
        "source_family_scope": ["future_live_traffic_state_feed", "future_traffic_event_feed"],
        "mobility_data_space_readiness": "data-space compatible with metadata and policy envelopes",
        "handoff_pattern": "Carry policy envelopes, refresh cadence, service-level metadata, and publication boundaries alongside stream subscriptions.",
        "required_metadata": ["provider id", "refresh cadence", "policy envelope", "publication tier", "retention rule"],
    },
]


def exposure_source_family_id(capability_code: str) -> str:
    return EXPOSURE_SOURCE_FAMILY_BY_CAPABILITY.get(capability_code, "exposure_unknown_family")


def signal_phase_source_family_id(profile_id: str) -> str:
    return SIGNAL_PHASE_SOURCE_FAMILY_BY_PROFILE.get(profile_id, "signal_phase_unknown_family")


def artifact_role_policy_ids(*artifact_family_ids: str) -> list[str]:
    artifact_set = set(artifact_family_ids)
    return [
        policy["role_policy_id"]
        for policy in ARTIFACT_ROLE_POLICIES
        if policy["artifact_family_id"] in artifact_set
    ]


def governance_contract_reference(
    *,
    artifact_family_ids: list[str],
    source_family_ids: list[str] | None = None,
    role_policy_ids: list[str] | None = None,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    bundle_path = Path(governance_bundle_path)
    reference = {
        "governance_contract_version": GOVERNANCE_INTEROPERABILITY_CONTRACT_VERSION,
        "governance_bundle_path": str(bundle_path),
        "artifact_family_ids": sorted(dict.fromkeys(artifact_family_ids)),
    }
    if source_family_ids:
        reference["source_family_ids"] = sorted(dict.fromkeys(source_family_ids))
    if role_policy_ids:
        reference["role_policy_ids"] = sorted(dict.fromkeys(role_policy_ids))
    if bundle_path.exists():
        reference["governance_bundle_sha256"] = _sha256(bundle_path)
    return reference


def _csv_string(values: list[str]) -> str:
    return " | ".join(values)


def _source_governance_csv_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for decision in SOURCE_GOVERNANCE_DECISIONS:
        rows.append(
            {
                "source_family_id": decision["source_family_id"],
                "domain_family": decision["domain_family"],
                "label": decision["label"],
                "planned_status": decision["planned_status"],
                "artifact_family_ids": _csv_string(list(decision["artifact_family_ids"])),
                "publication_tier": decision["publication_tier"],
                "publication_status": decision["publication_status"],
                "rights_basis": decision["rights_basis"],
                "retention_policy": decision["retention_policy"],
                "governance_decision": decision["governance_decision"],
                "exchange_pattern_id": decision["exchange_pattern_id"],
                "datex_profile": decision["datex_profile"],
                "datex_exchange_fit": decision["datex_exchange_fit"],
                "mobility_data_space_handoff_id": decision["mobility_data_space_handoff_id"],
                "mobility_data_space_readiness": decision["mobility_data_space_readiness"],
                "role_boundary": decision["role_boundary"],
            }
        )
    return rows


def _artifact_role_policy_csv_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for policy in ARTIFACT_ROLE_POLICIES:
        rows.append(
            {
                "role_policy_id": policy["role_policy_id"],
                "artifact_family_id": policy["artifact_family_id"],
                "role": policy["role"],
                "access_level": policy["access_level"],
                "allowed_fields": _csv_string(list(policy["allowed_fields"])),
                "restricted_fields": _csv_string(list(policy["restricted_fields"])),
                "delivery_boundary": policy["delivery_boundary"],
            }
        )
    return rows


def _datex_alignment_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for decision in SOURCE_GOVERNANCE_DECISIONS:
        rows.append(
            {
                "datex_alignment_id": decision["datex_alignment_id"],
                "source_family_id": decision["source_family_id"],
                "datex_profile": decision["datex_profile"],
                "datex_exchange_fit": decision["datex_exchange_fit"],
                "alignment_strategy": decision["governance_decision"],
            }
        )
    return rows


def _mobility_handoff_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for handoff in MOBILITY_DATA_SPACE_HANDOFFS:
        rows.append(
            {
                "mobility_data_space_handoff_id": handoff["mobility_data_space_handoff_id"],
                "source_family_scope": _csv_string(list(handoff["source_family_scope"])),
                "mobility_data_space_readiness": handoff["mobility_data_space_readiness"],
                "handoff_pattern": handoff["handoff_pattern"],
                "required_metadata": _csv_string(list(handoff["required_metadata"])),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Governance And Interoperability Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the repo-level governance bundle classifies live-source families, role boundaries, DATEX II posture, and mobility-data-space handoff patterns.",
        "",
        "## Source Families",
        "",
    ]
    for decision in payload["source_governance_decisions"]:
        lines.extend(
            [
                f"- `{decision['source_family_id']}`: {decision['publication_status']}, exchange `{decision['exchange_pattern_id']}`, DATEX fit `{decision['datex_exchange_fit']}`",
                f"  Rights basis: {decision['rights_basis']}. Boundary: {decision['role_boundary']}.",
            ]
        )
    lines.extend(["", "## Published Boundary", ""])
    for policy in payload["artifact_role_policies"]:
        if policy["artifact_family_id"] not in {
            SEGMENT_SCORES_PUBLIC_ARTIFACT_FAMILY,
            SEGMENT_SCORES_ANALYST_ARTIFACT_FAMILY,
            SEGMENT_SCORE_TILES_PUBLIC_ARTIFACT_FAMILY,
        }:
            continue
        lines.append(
            f"- `{policy['artifact_family_id']}` for `{policy['role']}`: {policy['access_level']} ({policy['delivery_boundary']})"
        )
    lines.extend(["", "## Mobility-Data-Space Handoffs", ""])
    for handoff in payload["mobility_data_space_handoffs"]:
        lines.append(
            f"- `{handoff['mobility_data_space_handoff_id']}`: {handoff['handoff_pattern']}"
        )
    return "\n".join(lines) + "\n"


def build_governance_interoperability_bundle(
    output_dir: str | Path = DEFAULT_GOVERNANCE_OUTPUT_DIR,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    bundle_json_path = output_root / "governance_interoperability_bundle.json"
    bundle_md_path = output_root / "governance_interoperability_bundle.md"
    source_matrix_path = output_root / "source_governance_matrix.csv"
    role_policy_path = output_root / "artifact_role_policies.csv"
    datex_alignment_path = output_root / "datex_alignment_matrix.csv"
    mobility_handoff_path = output_root / "mobility_data_space_handoffs.csv"
    manifest_path = output_root / "governance_interoperability_bundle.manifest.json"

    source_matrix_rows = _source_governance_csv_rows()
    role_policy_rows = _artifact_role_policy_csv_rows()
    datex_rows = _datex_alignment_rows()
    handoff_rows = _mobility_handoff_rows()

    _write_csv(source_matrix_path, source_matrix_rows)
    _write_csv(role_policy_path, role_policy_rows)
    _write_csv(datex_alignment_path, datex_rows)
    _write_csv(mobility_handoff_path, handoff_rows)

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "governance_interoperability_version": GOVERNANCE_INTEROPERABILITY_VERSION,
        "contract": {
            "resource_name": "governance_interoperability_bundle",
            "public_contract_version": GOVERNANCE_INTEROPERABILITY_CONTRACT_VERSION,
            "governance_interoperability_version": GOVERNANCE_INTEROPERABILITY_VERSION,
        },
        "summary": {
            "source_family_count": len(SOURCE_GOVERNANCE_DECISIONS),
            "artifact_role_policy_count": len(ARTIFACT_ROLE_POLICIES),
            "datex_alignment_count": len(datex_rows),
            "mobility_data_space_handoff_count": len(MOBILITY_DATA_SPACE_HANDOFFS),
        },
        "source_governance_decisions": SOURCE_GOVERNANCE_DECISIONS,
        "artifact_role_policies": ARTIFACT_ROLE_POLICIES,
        "exchange_patterns": EXCHANGE_PATTERNS,
        "mobility_data_space_handoffs": MOBILITY_DATA_SPACE_HANDOFFS,
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_markdown_report(payload), encoding="utf-8")

    manifest = {
        "governance_interoperability_version": GOVERNANCE_INTEROPERABILITY_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "contract": payload["contract"],
        "stats": payload["summary"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "source_governance_matrix_path": str(source_matrix_path),
            "source_governance_matrix_sha256": _sha256(source_matrix_path),
            "artifact_role_policies_path": str(role_policy_path),
            "artifact_role_policies_sha256": _sha256(role_policy_path),
            "datex_alignment_matrix_path": str(datex_alignment_path),
            "datex_alignment_matrix_sha256": _sha256(datex_alignment_path),
            "mobility_data_space_handoffs_path": str(mobility_handoff_path),
            "mobility_data_space_handoffs_sha256": _sha256(mobility_handoff_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[],
            publishable_outputs=[
                _artifact_reference("governance_interoperability_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
                _artifact_reference("governance_interoperability_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
                _artifact_reference("source_governance_matrix_csv", source_matrix_path, _sha256(source_matrix_path)),
                _artifact_reference("artifact_role_policies_csv", role_policy_path, _sha256(role_policy_path)),
                _artifact_reference("datex_alignment_matrix_csv", datex_alignment_path, _sha256(datex_alignment_path)),
                _artifact_reference("mobility_data_space_handoffs_csv", mobility_handoff_path, _sha256(mobility_handoff_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "governance_interoperability_version": GOVERNANCE_INTEROPERABILITY_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": manifest["stats"],
    }
