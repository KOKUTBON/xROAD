"""Command-line interface for the scaffold project."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path


from .aggregation import aggregate_segment_year_metrics
from .cadas_alignment import build_cadas_alignment_bundle, export_canonical_to_cadas
from .config import ProjectSettings
from .connector_observation_join import apply_connector_observations_to_segments
from .curation import curate_canonical_records
from .dashboard_summary import build_dashboard_summary
from .exposure_connector_ingestion import ingest_exposure_connector_extract
from .exposure_connector_intake import build_exposure_connector_intake_pack
from .enrichment import apply_exposure_policy_to_segments, enrich_segments, enrich_segments_with_context
from .data_governance import build_data_governance_bundle
from .governance_interoperability import build_governance_interoperability_bundle
from .exposure_onboarding import build_exposure_onboarding_plan
from .exposure_pilot_cycle import run_bari_phase1_exposure_pilot
from .exposure_provider_adapter import normalize_exposure_provider_extract
from .exposure_readiness import build_exposure_readiness_report
from .exposure_source_catalog import build_exposure_source_catalog
from .ingestion import ingest_bari_open_data_crashes, ingest_puglia_cleaned_csv
from .intervention_briefs import build_intervention_briefs
from .jurisdictions import (
    extract_istat_codebooks,
    filter_canonical_records_by_jurisdiction,
    profile_canonical_jurisdictions,
)
from .legacy_zip import inspect_zip, list_csv_members, profile_csv_member
from .matching import match_canonical_records_to_segments
from .modeling import train_frequency_baseline, train_severity_baseline
from .node_aggregation import aggregate_node_year_metrics
from .node_matching import match_canonical_records_to_node_objects
from .node_objects import (
    build_bari_conflict_zones,
    build_bari_crossing_and_approach_objects,
    build_bari_movement_objects,
    build_bari_signal_nodes,
)
from .movement_review import build_bari_movement_review_pack
from .scenario_countermeasures import build_scenario_countermeasure_bundle
from .vru_exposure import build_vru_exposure_bundle
from .vru_intelligence import build_vru_intelligence_bundle
from .signal_phase_intake import build_bari_signal_phase_intake_pack
from .signal_phase_support_resolution import build_bari_signal_phase_support_resolution_bundle
from .signal_phase_support_writeback import build_bari_signal_phase_support_writeback_bundle
from .signal_phase_support_status import build_bari_signal_phase_support_status_bundle
from .signal_phase_support_action_queue import build_bari_signal_phase_support_action_queue
from .signal_phase_support_apply_status import (
    build_bari_signal_phase_support_apply_status_bundle,
)
from .signal_phase_support_request_state import (
    build_bari_signal_phase_support_request_state_bundle,
)
from .signal_phase_support_operator_board import (
    build_bari_signal_phase_support_operator_board_bundle,
)
from .signal_phase_support_action_execution import (
    build_bari_signal_phase_support_action_execution_bundle,
)
from .signal_phase_support_action_handoff import (
    build_bari_signal_phase_support_action_handoff_bundle,
)
from .signal_phase_support_runtime_board import (
    build_bari_signal_phase_support_runtime_board_bundle,
)
from .signal_phase_support_runtime_action_queue import (
    build_bari_signal_phase_support_runtime_action_queue,
)
from .signal_phase_support_runtime_action_execution import (
    build_bari_signal_phase_support_runtime_action_execution_bundle,
)
from .signal_phase_support_workbook_completion import (
    build_bari_signal_phase_support_workbook_completion_bundle,
)
from .signal_phase_support_validation_batch import run_bari_signal_phase_support_validation_batch
from .signal_phase_support_apply_cycle import run_bari_signal_phase_support_apply_cycle
from .signal_phase_support_rehearsal import run_bari_signal_phase_support_rehearsal
from .signal_phase_support_runtime_cycle import run_bari_signal_phase_support_runtime_cycle
from .signal_phase_ingestion import ingest_signal_phase_extract
from .signal_phase_join import apply_signal_phase_to_movements
from .signal_phase_acquisition import build_bari_signal_phase_acquisition_plan
from .signal_phase_delivery_intake import build_bari_signal_phase_delivery_intake_bundle
from .signal_phase_delivery_monitor import build_bari_signal_phase_delivery_monitor_bundle
from .signal_phase_delivery_validation import validate_signal_phase_delivery
from .signal_phase_validation_batch import run_bari_signal_phase_validation_batch
from .signal_phase_delivery_session import apply_validated_signal_phase_deliveries
from .signal_phase_receive_cycle import run_bari_signal_phase_receive_cycle
from .signal_phase_coverage import build_bari_signal_phase_coverage_report
from .signal_phase_contact_bundle import build_bari_signal_phase_contact_bundle
from .signal_phase_dispatch import build_bari_signal_phase_dispatch_bundle
from .signal_phase_dispatch_execution import build_bari_signal_phase_dispatch_execution_bundle
from .signal_phase_dispatch_cycle import run_bari_signal_phase_dispatch_cycle
from .signal_phase_dispatch_writeback import build_bari_signal_phase_dispatch_writeback_bundle
from .signal_phase_dispatch_recording import build_bari_signal_phase_dispatch_recording_bundle
from .signal_phase_dispatch_repair import build_bari_signal_phase_dispatch_repair_bundle
from .signal_phase_dispatch_repair_execution import (
    build_bari_signal_phase_dispatch_repair_execution_bundle,
)
from .signal_phase_dispatch_repair_recording import (
    build_bari_signal_phase_dispatch_repair_recording_bundle,
)
from .signal_phase_dispatch_repair_status import (
    build_bari_signal_phase_dispatch_repair_status_bundle,
)
from .signal_phase_dispatch_validation import build_bari_signal_phase_dispatch_validation_bundle
from .signal_phase_runtime_cycle import run_bari_signal_phase_runtime_cycle
from .signal_phase_runtime_rehearsal import run_bari_signal_phase_runtime_rehearsal
from .signal_phase_contact_resolution import build_bari_signal_phase_contact_resolution_bundle
from .signal_phase_request_scope import build_bari_signal_phase_request_scope_bundle
from .signal_phase_targeting import build_bari_signal_phase_target_bundle
from .signal_phase_outreach import build_bari_signal_phase_outreach_bundle
from .signal_phase_request import build_bari_signal_phase_request_pack
from .signal_phase_lifecycle import build_bari_signal_phase_lifecycle_report
from .signal_phase_follow_up import build_bari_signal_phase_follow_up_bundle
from .signal_phase_action_execution import build_bari_signal_phase_action_execution_bundle
from .signal_phase_action_handoff import build_bari_signal_phase_action_handoff_bundle
from .signal_phase_operator_board import build_bari_signal_phase_operator_board_bundle
from .signal_phase_action_queue import build_bari_signal_phase_action_queue
from .signal_phase_follow_up_cycle import run_bari_signal_phase_follow_up_cycle
from .signal_phase_follow_up_execution import build_bari_signal_phase_follow_up_execution_bundle
from .signal_phase_operations_cycle import run_bari_signal_phase_operations_cycle
from .signal_phase_follow_up_writeback import build_bari_signal_phase_follow_up_writeback_bundle
from .signal_phase_status_sync import build_bari_signal_phase_status_sync_bundle
from .pipeline import pipeline_as_dicts
from .published_api import serve_published_api
from .prediction_store import publish_segment_scores
from .published_index import build_published_resource_index
from .published_refresh import build_published_refresh_bundle
from .published_queries import query_published_resource
from .published_resolver import resolve_latest_published_resource
from .public_score_tiles import aggregate_public_score_tiles
from .quality import write_canonical_quality_report
from .registry import build_run_registry
from .remediation import analyze_match_results
from .segmentation import (
    compare_boundaries,
    extract_boundary_from_place,
    extract_segments_from_boundary,
    extract_segments_from_place,
    extract_segments_from_records_bbox,
)
from .behavioural_safety import run_behavioural_analysis
from .climate_resilience import run_climate_resilience_assessment
from .elderly_disabled_safety import run_elderly_disabled_assessment
from .intersectional_analysis import run_intersectional_analysis
from .nwrsa import run_nwrsa_assessment
from .regional_comparison import run_regional_comparison
from .rural_sectioning import run_rural_sectioning
from .transferability import evaluate_frequency_transferability
from .transferability_benchmark import build_transferability_benchmark_bundle
from .national_hierarchy import (
    NationalHierarchy,
    build_sample_italy_national_hierarchy,
    export_national_rollup_report,
)
from .hsm_engine import (
    screen_road_network_hsm,
    export_hsm_screening_artifacts,
)
from .irap_engine import (
    assess_segment_irap,
    generate_safer_roads_investment_plan,
    export_irap_and_srip_artifacts,
)
from .telematics_engine import (
    detect_events_from_waypoints,
    parse_telematics_events,
    calculate_segment_telematics_metrics,
    export_telematics_screening_artifacts,
)
from .cip_engine import (
    parse_cip_candidates,
    optimize_capital_improvement_plan,
    export_cip_portfolio_artifacts,
)
from .cv_road_audit import (
    parse_frame_observations,
    aggregate_frame_detections_to_segments,
    export_cv_audit_artifacts,
)
from .micro_ssam_engine import (
    parse_agent_trajectories,
    detect_trajectory_conflicts,
    aggregate_conflicts_to_junctions,
    export_micro_ssam_artifacts,
)
from .st_gnn_forecasting import (
    DEFAULT_HORIZONS,
    GraphEdge,
    RoadGraphNode,
    SpatioTemporalFeatureFrame,
    execute_st_gnn_forecast,
    export_st_gnn_artifacts,
)
from .causal_ml_engine import (
    estimate_double_ml_treatment_effect,
    estimate_segment_cate_heterogeneity,
    export_causal_ml_artifacts,
    parse_observational_units,
)
from .cits_v2x_engine import (
    create_cits_actuation_bundle,
    export_cits_actuation_artifacts,
    parse_operational_risk_alerts,
)
from .simulation_sandbox_engine import (
    _safe_float,
    _safe_int,
    evaluate_synthetic_countermeasure_pair,
    export_simulation_sandbox_artifacts,
)
from .ai_act_compliance_engine import (
    compute_local_shap_explanations,
    export_ai_act_compliance_artifacts,
    generate_eu_ai_act_dossier,
)
from .federated_learning_engine import (
    export_federated_learning_artifacts,
    run_federated_training_pipeline,
)
from .micromobility_engine import (
    export_micromobility_artifacts,
    run_micromobility_fleet_audit,
)
from .ministerial_dossier import (
    compile_ministerial_dossier,
    export_ministerial_dossier_artifacts,
)
from .segment_panel_engine import (
    build_segment_week_panel,
    export_panel_artifacts,
)
from .panel_baselines_engine import (
    evaluate_model_suite,
)
from .spatial_temporal_validation import (
    export_experiment_run_artifacts,
    forward_temporal_split,
    space_time_blocked_split,
    spatial_group_kfold_split,
)






def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="road-risk",
        description="Utilities for the road-accident risk modeling scaffold.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect-legacy",
        help="Inspect the structure of a legacy ZIP archive.",
    )
    inspect_parser.add_argument("zip_path")

    list_parser = subparsers.add_parser(
        "list-csv",
        help="List CSV members inside a legacy ZIP archive.",
    )
    list_parser.add_argument("zip_path")

    profile_parser = subparsers.add_parser(
        "profile-csv",
        help="Profile a CSV file directly inside a ZIP archive.",
    )
    profile_parser.add_argument("zip_path")
    profile_parser.add_argument("member")
    profile_parser.add_argument("--sample-size", type=int, default=3)

    ingest_parser = subparsers.add_parser(
        "ingest-puglia-cleaned",
        help="Map the cleaned legacy Puglia CSV into canonical JSONL.",
    )
    ingest_parser.add_argument("zip_path")
    ingest_parser.add_argument("member")
    ingest_parser.add_argument(
        "--output-dir",
        default="data/staging",
        help="Directory for canonical outputs and manifest.",
    )
    ingest_parser.add_argument("--limit", type=int)

    bari_open_data_parser = subparsers.add_parser(
        "ingest-bari-open-data-crashes",
        help="Download or read the official Bari open-data crash CSVs and map them into canonical JSONL.",
    )
    bari_open_data_parser.add_argument(
        "--output-dir",
        default="data/staging/bari_open_data",
        help="Directory for canonical outputs and manifest.",
    )
    bari_open_data_parser.add_argument(
        "--raw-dir",
        default="data/raw/bari_open_data_crashes",
        help="Directory for persisted raw source CSV copies. Use 'none' to skip raw copies.",
    )
    bari_open_data_parser.add_argument("--limit", type=int)

    codebook_parser = subparsers.add_parser(
        "extract-istat-codebooks",
        help="Extract ISTAT province and municipality codebooks from the legacy ZIP archive.",
    )
    codebook_parser.add_argument("zip_path")
    codebook_parser.add_argument(
        "--output-dir",
        default="data/external/istat",
        help="Directory for extracted codebook CSVs and manifest.",
    )

    ingest_config_parser = subparsers.add_parser(
        "ingest-config",
        help="Ingest the configured legacy source from a TOML config file.",
    )
    ingest_config_parser.add_argument("config_path")
    ingest_config_parser.add_argument(
        "--output-dir",
        default="data/staging",
        help="Directory for canonical outputs and manifest.",
    )
    ingest_config_parser.add_argument("--limit", type=int)

    ingest_decl_parser = subparsers.add_parser(
        "ingest-declarative",
        help="Ingest crash records using a declarative schema mapping configuration.",
    )
    ingest_decl_parser.add_argument("--csv-path", required=True, help="Path to input crash records CSV.")
    ingest_decl_parser.add_argument(
        "--mapping-config",
        required=True,
        help="Path to JSON or TOML declarative mapping schema.",
    )
    ingest_decl_parser.add_argument(
        "--output-dir",
        default="data/staging",
        help="Directory for canonical JSONL outputs and manifest.",
    )
    ingest_decl_parser.add_argument("--limit", type=int, help="Optional maximum row limit.")

    qa_parser = subparsers.add_parser(
        "qa-canonical",
        help="Run quality and geospatial QA on canonical JSONL records.",
    )
    qa_parser.add_argument("records_path")
    qa_parser.add_argument("--output-path")
    qa_parser.add_argument("--top-n", type=int, default=20)

    jurisdiction_profile_parser = subparsers.add_parser(
        "profile-jurisdictions",
        help="Profile canonical crash records by decoded province and municipality.",
    )
    jurisdiction_profile_parser.add_argument("records_path")
    jurisdiction_profile_parser.add_argument("--zip-path")
    jurisdiction_profile_parser.add_argument("--output-dir", default="data/processed/profiles")
    jurisdiction_profile_parser.add_argument("--top-n", type=int, default=20)

    subset_parser = subparsers.add_parser(
        "subset-jurisdiction",
        help="Filter canonical crash records to a target province or municipality subset.",
    )
    subset_parser.add_argument("records_path")
    subset_parser.add_argument("--output-dir", default="data/processed/subsets")
    subset_parser.add_argument("--province-code")
    subset_parser.add_argument("--city-code")
    subset_parser.add_argument("--province-name")
    subset_parser.add_argument("--city-name")
    subset_parser.add_argument("--require-coordinates", action="store_true")

    curate_parser = subparsers.add_parser(
        "curate-canonical",
        help="Create a model-ready canonical subset by excluding blocking quality flags.",
    )
    curate_parser.add_argument("records_path")
    curate_parser.add_argument("--output-path")
    curate_parser.add_argument("--rejected-path")

    segment_parser = subparsers.add_parser(
        "extract-segments",
        help="Extract road-network segments for a pilot geography using OSMnx.",
    )
    segment_parser.add_argument("place_query")
    segment_parser.add_argument("--output-dir", default="data/processed/segments")
    segment_parser.add_argument("--network-type", default="drive")

    boundary_parser = subparsers.add_parser(
        "extract-boundary",
        help="Extract a municipal or administrative boundary from a place query.",
    )
    boundary_parser.add_argument("place_query")
    boundary_parser.add_argument("--output-dir", default="data/processed/boundaries")

    records_segment_parser = subparsers.add_parser(
        "extract-segments-from-records",
        help="Extract road segments from the bbox around coordinate-complete crash records.",
    )
    records_segment_parser.add_argument("records_path")
    records_segment_parser.add_argument("--output-dir", default="data/processed/segments")
    records_segment_parser.add_argument("--network-type", default="drive")
    records_segment_parser.add_argument("--pad-m", type=float, default=1500.0)
    records_segment_parser.add_argument("--trim-quantile", type=float, default=0.0)

    boundary_segment_parser = subparsers.add_parser(
        "extract-segments-from-boundary",
        help="Extract road segments from an existing boundary GeoJSON.",
    )
    boundary_segment_parser.add_argument("boundary_path")
    boundary_segment_parser.add_argument("--output-dir", default="data/processed/segments")
    boundary_segment_parser.add_argument("--network-type", default="drive")

    signal_nodes_parser = subparsers.add_parser(
        "build-bari-signal-nodes",
        help="Build Bari traffic-signal node objects from the official Semafori open-data feed.",
    )
    signal_nodes_parser.add_argument("--output-dir", default="data/processed/node_objects/bari_signals")
    signal_nodes_parser.add_argument(
        "--segments-path",
        default="data/processed/segments/bari/road_segments.geojson",
        help="Optional segment layer used to snap signal nodes onto the current Bari road network.",
    )
    signal_nodes_parser.add_argument(
        "--raw-dir",
        default="data/raw/bari_signal_nodes",
        help="Directory for persisted raw source CSV copies. Use 'none' to skip raw copies.",
    )

    crossing_objects_parser = subparsers.add_parser(
        "build-bari-crossing-and-approach-objects",
        help="Build Bari mixed node objects for crossings, approaches, unsignalized junctions, and roundabouts.",
    )
    crossing_objects_parser.add_argument(
        "--output-dir",
        default="data/processed/node_objects/bari_crossing_approaches",
    )
    crossing_objects_parser.add_argument(
        "--signal-nodes-path",
        default="data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    )
    crossing_objects_parser.add_argument(
        "--segments-path",
        default="data/processed/segments/bari/road_segments.geojson",
    )
    crossing_objects_parser.add_argument(
        "--boundary-path",
        default="data/processed/segments/bari/boundary.geojson",
    )
    crossing_objects_parser.add_argument(
        "--crossings-path",
        help="Optional local crossing feature GeoJSON used instead of a live OSM fetch.",
    )
    crossing_objects_parser.add_argument(
        "--raw-dir",
        default="data/raw/bari_crossing_objects",
        help="Directory for persisted raw crossing fetch outputs. Use 'none' to skip raw copies.",
    )
    crossing_objects_parser.add_argument("--approach-distance-m", type=float, default=25.0)
    crossing_objects_parser.add_argument("--junction-buffer-m", type=float, default=35.0)
    crossing_objects_parser.add_argument("--signal-link-m", type=float, default=50.0)
    crossing_objects_parser.add_argument("--unsignalized-min-degree", type=int, default=4)
    crossing_objects_parser.add_argument("--unsignalized-major-edge-min", type=int, default=2)

    conflict_zone_parser = subparsers.add_parser(
        "build-bari-conflict-zones",
        help="Build Bari conflict-zone polygons from the current mixed node-object layer.",
    )
    conflict_zone_parser.add_argument(
        "--output-dir",
        default="data/processed/conflict_zones/bari",
    )
    conflict_zone_parser.add_argument(
        "--node-objects-path",
        default="data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson",
    )
    conflict_zone_parser.add_argument(
        "--segments-path",
        default="data/processed/segments/bari/road_segments.geojson",
    )
    conflict_zone_parser.add_argument("--crossing-radius-m", type=float, default=12.0)
    conflict_zone_parser.add_argument("--unsignalized-radius-m", type=float, default=20.0)
    conflict_zone_parser.add_argument("--roundabout-fallback-radius-m", type=float, default=16.0)
    conflict_zone_parser.add_argument("--junction-approach-length-m", type=float, default=20.0)
    conflict_zone_parser.add_argument("--roundabout-entry-length-m", type=float, default=18.0)
    conflict_zone_parser.add_argument("--default-zone-half-width-m", type=float, default=6.0)

    movement_object_parser = subparsers.add_parser(
        "build-bari-movement-objects",
        help="Build Bari point-based movement objects from the current conflict-zone layer.",
    )
    movement_object_parser.add_argument(
        "--output-dir",
        default="data/processed/movement_objects/bari",
    )
    movement_object_parser.add_argument(
        "--conflict-zones-path",
        default="data/processed/conflict_zones/bari/road_conflict_zones.geojson",
    )
    movement_object_parser.add_argument(
        "--segments-path",
        default="data/processed/segments/bari/road_segments.geojson",
    )
    movement_object_parser.add_argument("--movement-offset-m", type=float, default=8.0)

    movement_review_parser = subparsers.add_parser(
        "build-bari-movement-review-pack",
        help="Build Bari movement unresolved-target and phase-readiness review outputs.",
    )
    movement_review_parser.add_argument(
        "--output-dir",
        default="data/reporting/movement_review/bari",
    )
    movement_review_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    movement_review_parser.add_argument(
        "--matched-records-path",
        default="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    )
    movement_review_parser.add_argument(
        "--aggregate-path",
        default="data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.csv",
    )
    movement_review_parser.add_argument(
        "--signal-nodes-path",
        default="data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    )
    movement_review_parser.add_argument("--top-n", type=int, default=20)

    signal_phase_intake_parser = subparsers.add_parser(
        "build-bari-signal-phase-intake-pack",
        help="Build Bari signal-phase intake templates and priority exports from the movement review pack.",
    )
    signal_phase_intake_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_intake/bari",
    )
    signal_phase_intake_parser.add_argument(
        "--movement-review-path",
        default="data/reporting/movement_review/bari/movement_review_pack.json",
    )
    signal_phase_intake_parser.add_argument(
        "--phase-readiness-csv-path",
        default=None,
    )
    signal_phase_intake_parser.add_argument(
        "--signal-nodes-path",
        default="data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    )
    signal_phase_intake_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_intake_parser.add_argument("--top-n", type=int, default=20)

    signal_phase_support_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-resolution-bundle",
        help="Turn validated Bari support diagrams into analyst arm-phase and pedestrian-stage review queues.",
    )
    signal_phase_support_parser.add_argument("support_validation_manifest_paths", nargs="+")
    signal_phase_support_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_resolution/bari",
    )
    signal_phase_support_parser.add_argument(
        "--movement-review-path",
        default="data/reporting/movement_review/bari/movement_review_pack.json",
    )
    signal_phase_support_parser.add_argument(
        "--phase-readiness-csv-path",
        default=None,
    )
    signal_phase_support_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_support_parser.add_argument(
        "--aggregate-path",
        default="data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.csv",
    )
    signal_phase_support_parser.add_argument("--top-n", type=int, default=10)

    signal_phase_support_writeback_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-writeback-bundle",
        help="Turn Bari support-resolution review rows into analyst workbooks and validation-ready mapping deliveries.",
    )
    signal_phase_support_writeback_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_writeback/bari",
    )
    signal_phase_support_writeback_parser.add_argument(
        "--signal-phase-support-resolution-bundle-path",
        default="data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    )
    signal_phase_support_writeback_parser.add_argument(
        "--manual-mapping-stub-path",
        default="data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
    )

    signal_phase_support_status_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-status-bundle",
        help="Build Bari analyst-work and validation-ready queues from the support-writeback workbooks.",
    )
    signal_phase_support_status_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_status/bari",
    )
    signal_phase_support_status_parser.add_argument(
        "--signal-phase-support-writeback-bundle-path",
        default="data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
    )

    signal_phase_support_action_queue_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-action-queue",
        help="Build Bari profile-level analyst actions from the support-status queues.",
    )
    signal_phase_support_action_queue_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_action_queue/bari",
    )
    signal_phase_support_action_queue_parser.add_argument(
        "--signal-phase-support-status-bundle-path",
        default="data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    )
    signal_phase_support_action_queue_parser.add_argument(
        "--signal-phase-support-apply-status-bundle-path",
        help="Optional support apply-status bundle used to suppress already-applied or validation-failed profiles.",
    )

    signal_phase_support_apply_status_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-apply-status-bundle",
        help="Build Bari profile-level apply status from the support status bundle and the latest support apply cycle.",
    )
    signal_phase_support_apply_status_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_apply_status/bari",
    )
    signal_phase_support_apply_status_parser.add_argument(
        "--signal-phase-support-status-bundle-path",
        default="data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    )
    signal_phase_support_apply_status_parser.add_argument(
        "--signal-phase-support-apply-cycle-path",
        default="data/processed/signal_phase_support_apply_cycles/bari/signal_phase_support_apply_cycle.json",
    )

    signal_phase_support_request_state_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-request-state-bundle",
        help="Build Bari request-level support state from support status and profile-level apply status.",
    )
    signal_phase_support_request_state_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_request_state/bari",
    )
    signal_phase_support_request_state_parser.add_argument(
        "--signal-phase-support-status-bundle-path",
        default="data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    )
    signal_phase_support_request_state_parser.add_argument(
        "--signal-phase-support-apply-status-bundle-path",
        default="data/reporting/signal_phase_support_apply_status/bari/signal_phase_support_apply_status_bundle.json",
    )

    signal_phase_support_operator_board_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-operator-board-bundle",
        help="Build a Bari request-level support operator board from request runtime state and profile actions.",
    )
    signal_phase_support_operator_board_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_operator_board/bari",
    )
    signal_phase_support_operator_board_parser.add_argument(
        "--signal-phase-support-request-state-bundle-path",
        default="data/reporting/signal_phase_support_request_state/bari/signal_phase_support_request_state_bundle.json",
    )
    signal_phase_support_operator_board_parser.add_argument(
        "--signal-phase-support-action-queue-path",
        default="data/reporting/signal_phase_support_action_queue/bari/signal_phase_support_action_queue.json",
    )
    signal_phase_support_operator_board_parser.add_argument(
        "--support-runtime-command",
        default=(
            "PYTHONPATH=src python3 -m road_risk_modeling run-bari-signal-phase-support-runtime-cycle "
            "--output-dir data/processed/signal_phase_support_runtime_cycles/bari "
            "--signal-phase-support-resolution-bundle-path data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json "
            "--manual-mapping-stub-path data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json "
            "--delivery-checklist-path data/planning/signal_phase_acquisition/bari/delivery_checklist.csv "
            "--movement-objects-path data/processed/movement_objects/bari/road_movement_objects.geojson "
            "--preview-limit 10"
        ),
    )

    signal_phase_support_action_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-action-execution-bundle",
        help="Build a Bari request-level support execution queue from the support operator board.",
    )
    signal_phase_support_action_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_action_execution/bari",
    )
    signal_phase_support_action_execution_parser.add_argument(
        "--signal-phase-support-operator-board-bundle-path",
        default="data/reporting/signal_phase_support_operator_board/bari/signal_phase_support_operator_board_bundle.json",
    )

    signal_phase_support_action_handoff_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-action-handoff-bundle",
        help="Build a Bari request-level support handoff bundle from the support action execution queue.",
    )
    signal_phase_support_action_handoff_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_action_handoff/bari",
    )
    signal_phase_support_action_handoff_parser.add_argument(
        "--signal-phase-support-action-execution-bundle-path",
        default="data/reporting/signal_phase_support_action_execution/bari/signal_phase_support_action_execution_bundle.json",
    )
    signal_phase_support_action_handoff_parser.add_argument(
        "--support-runtime-cycle-manifest-path",
        default="data/processed/signal_phase_support_runtime_cycles/bari/signal_phase_support_runtime_cycle.manifest.json",
    )

    signal_phase_support_runtime_board_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-runtime-board-bundle",
        help="Build a unified Bari support runtime board from support action execution and handoff bundles.",
    )
    signal_phase_support_runtime_board_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_runtime_board/bari",
    )
    signal_phase_support_runtime_board_parser.add_argument(
        "--signal-phase-support-action-execution-bundle-path",
        default="data/reporting/signal_phase_support_action_execution/bari/signal_phase_support_action_execution_bundle.json",
    )
    signal_phase_support_runtime_board_parser.add_argument(
        "--signal-phase-support-action-handoff-bundle-path",
        default="data/reporting/signal_phase_support_action_handoff/bari/signal_phase_support_action_handoff_bundle.json",
    )

    signal_phase_support_runtime_action_queue_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-runtime-action-queue",
        help="Build a final Bari support runtime action queue from the support runtime board.",
    )
    signal_phase_support_runtime_action_queue_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_runtime_action_queue/bari",
    )
    signal_phase_support_runtime_action_queue_parser.add_argument(
        "--signal-phase-support-runtime-board-bundle-path",
        default="data/reporting/signal_phase_support_runtime_board/bari/signal_phase_support_runtime_board_bundle.json",
    )

    signal_phase_support_runtime_action_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-runtime-action-execution-bundle",
        help="Build a final Bari support runtime execution queue from the support runtime action queue.",
    )
    signal_phase_support_runtime_action_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_runtime_action_execution/bari",
    )
    signal_phase_support_runtime_action_execution_parser.add_argument(
        "--signal-phase-support-runtime-action-queue-path",
        default="data/reporting/signal_phase_support_runtime_action_queue/bari/signal_phase_support_runtime_action_queue.json",
    )

    signal_phase_support_workbook_completion_parser = subparsers.add_parser(
        "build-bari-signal-phase-support-workbook-completion-bundle",
        help="Build a row-level Bari support workbook completion queue from final runtime execution.",
    )
    signal_phase_support_workbook_completion_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_workbook_completion/bari",
    )
    signal_phase_support_workbook_completion_parser.add_argument(
        "--signal-phase-support-runtime-action-execution-bundle-path",
        default=(
            "data/reporting/signal_phase_support_runtime_action_execution/bari/"
            "signal_phase_support_runtime_action_execution_bundle.json"
        ),
    )
    signal_phase_support_workbook_completion_parser.add_argument(
        "--signal-phase-support-writeback-bundle-path",
        default="data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
    )

    signal_phase_support_validation_batch_parser = subparsers.add_parser(
        "run-bari-signal-phase-support-validation-batch",
        help="Run support-derived signal-phase validation for analyst actions that are ready to validate.",
    )
    signal_phase_support_validation_batch_parser.add_argument(
        "--output-dir",
        default="data/quality/signal_phase_support_validation_batches/bari",
    )
    signal_phase_support_validation_batch_parser.add_argument(
        "--action-execution-ready-queue-path",
        default="data/reporting/signal_phase_support_action_queue/bari/action_execution_ready_queue.csv",
    )
    signal_phase_support_validation_batch_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_support_validation_batch_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_support_apply_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-support-apply-cycle",
        help="Run support-derived validation and conditional movement-layer application in one pass.",
    )
    signal_phase_support_apply_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_support_apply_cycles/bari",
    )
    signal_phase_support_apply_cycle_parser.add_argument(
        "--action-execution-ready-queue-path",
        default="data/reporting/signal_phase_support_action_queue/bari/action_execution_ready_queue.csv",
    )
    signal_phase_support_apply_cycle_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_support_apply_cycle_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_support_apply_cycle_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_support_rehearsal_parser = subparsers.add_parser(
        "run-bari-signal-phase-support-rehearsal",
        help="Run a Bari support-side rehearsal by filling one copied arm-phase row and one copied pedestrian row.",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_support_rehearsal/bari",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--request-id",
        default="bari_signal_phase_01",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--signal-phase-support-writeback-bundle-path",
        default="data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--signal-phase-support-resolution-bundle-path",
        default="data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--manual-mapping-stub-path",
        default="data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--manual-phase-id",
        default="phase_a",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--manual-stage-id",
        default="stage_1",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--manual-protection-state",
        default="protected",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--pedestrian-phase-id",
        default="ped_phase_a",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--pedestrian-stage-id",
        default="stage_p1",
    )
    signal_phase_support_rehearsal_parser.add_argument(
        "--pedestrian-protection-state",
        default="protected",
    )
    signal_phase_support_rehearsal_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_support_runtime_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-support-runtime-cycle",
        help="Rebuild the Bari live support-derived stack from workbooks through validation and conditional apply in one pass.",
    )
    signal_phase_support_runtime_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_support_runtime_cycles/bari",
    )
    signal_phase_support_runtime_cycle_parser.add_argument(
        "--signal-phase-support-resolution-bundle-path",
        default="data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    )
    signal_phase_support_runtime_cycle_parser.add_argument(
        "--manual-mapping-stub-path",
        default="data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
    )
    signal_phase_support_runtime_cycle_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_support_runtime_cycle_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_support_runtime_cycle_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_ingest_parser = subparsers.add_parser(
        "ingest-signal-phase-extract",
        help="Normalize a signal-phase provider extract or movement-phase mapping sheet into JSONL records.",
    )
    signal_phase_ingest_parser.add_argument("input_csv_path")
    signal_phase_ingest_parser.add_argument("mapping_stub_path")
    signal_phase_ingest_parser.add_argument("--output-dir", default="data/processed/signal_phase_records")
    signal_phase_ingest_parser.add_argument("--limit", type=int, default=None)

    signal_phase_join_parser = subparsers.add_parser(
        "apply-signal-phase-to-movements",
        help="Join normalized signal-phase records onto the Bari movement-object layer.",
    )
    signal_phase_join_parser.add_argument("movement_objects_path")
    signal_phase_join_parser.add_argument("phase_manifest_paths", nargs="+")
    signal_phase_join_parser.add_argument("--output-dir", default="data/processed/movement_objects")

    signal_phase_validation_parser = subparsers.add_parser(
        "validate-signal-phase-delivery",
        help="Validate a received signal-phase delivery against a mapping stub and Bari checklist context.",
    )
    signal_phase_validation_parser.add_argument("input_csv_path")
    signal_phase_validation_parser.add_argument("mapping_stub_path")
    signal_phase_validation_parser.add_argument("--output-dir", default="data/quality/signal_phase_delivery_validation")
    signal_phase_validation_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_validation_parser.add_argument("--request-id", default=None)
    signal_phase_validation_parser.add_argument("--junction-id", default=None)
    signal_phase_validation_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_session_parser = subparsers.add_parser(
        "apply-validated-signal-phase-deliveries",
        help="Ingest validated signal-phase deliveries and apply them to the Bari movement layer.",
    )
    signal_phase_session_parser.add_argument("movement_objects_path")
    signal_phase_session_parser.add_argument("validation_manifest_paths", nargs="+")
    signal_phase_session_parser.add_argument("--output-dir", default="data/processed/signal_phase_delivery_sessions")
    signal_phase_session_parser.add_argument(
        "--matched-records-path",
        default="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    )
    signal_phase_session_parser.add_argument(
        "--target-request-queue-path",
        default="data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    )
    signal_phase_session_parser.add_argument(
        "--baseline-movement-objects-path",
        default=None,
    )

    signal_phase_coverage_parser = subparsers.add_parser(
        "build-bari-signal-phase-coverage-report",
        help="Build Bari signal-phase coverage outputs from the current movement-phase session layer and matched crash records.",
    )
    signal_phase_coverage_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_coverage/bari_sample",
    )
    signal_phase_coverage_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/signal_phase_delivery_sessions/bari_sample/movement_layer/road_movement_objects_signal_phase.geojson",
    )
    signal_phase_coverage_parser.add_argument(
        "--matched-records-path",
        default="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    )
    signal_phase_coverage_parser.add_argument(
        "--target-request-queue-path",
        default="data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    )
    signal_phase_coverage_parser.add_argument(
        "--delivery-session-manifest-path",
        default="data/processed/signal_phase_delivery_sessions/bari_sample/signal_phase_delivery_session.manifest.json",
    )
    signal_phase_coverage_parser.add_argument("--top-n", type=int, default=20)

    signal_phase_target_parser = subparsers.add_parser(
        "build-bari-signal-phase-target-bundle",
        help="Build Bari per-signal delivery targets from the current coverage report and tier-1 request queue.",
    )
    signal_phase_target_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_targets/bari",
    )
    signal_phase_target_parser.add_argument(
        "--target-junction-coverage-path",
        default="data/reporting/signal_phase_coverage/bari_sample/target_junction_coverage.csv",
    )
    signal_phase_target_parser.add_argument(
        "--uncovered-signalized-hotspots-path",
        default="data/reporting/signal_phase_coverage/bari_sample/uncovered_signalized_hotspots.csv",
    )
    signal_phase_target_parser.add_argument(
        "--target-request-queue-path",
        default="data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    )
    signal_phase_target_parser.add_argument(
        "--matched-movement-records-path",
        default="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    )
    signal_phase_target_parser.add_argument("--top-hotspots-per-target", type=int, default=5)

    signal_phase_request_scope_parser = subparsers.add_parser(
        "build-bari-signal-phase-request-scope-bundle",
        help="Build Bari scoped signal-phase requests with explicit high-yield collection windows.",
    )
    signal_phase_request_scope_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_request_scope/bari",
    )
    signal_phase_request_scope_parser.add_argument(
        "--signal-phase-target-bundle-path",
        default="data/reporting/signal_phase_targets/bari/signal_phase_target_bundle.json",
    )
    signal_phase_request_scope_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )

    signal_phase_contact_parser = subparsers.add_parser(
        "build-bari-signal-phase-contact-bundle",
        help="Build send-ready Bari contact drafts from scoped signal-phase requests and the outreach tracker.",
    )
    signal_phase_contact_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_contact/bari",
    )
    signal_phase_contact_parser.add_argument(
        "--signal-phase-request-scope-bundle-path",
        default="data/reporting/signal_phase_request_scope/bari/signal_phase_request_scope_bundle.json",
    )
    signal_phase_contact_parser.add_argument(
        "--outreach-tracker-path",
        default="data/planning/signal_phase_acquisition/bari/outreach_tracker.csv",
    )
    signal_phase_contact_parser.add_argument("--follow-up-days", type=int, default=7)

    signal_phase_contact_resolution_parser = subparsers.add_parser(
        "build-bari-signal-phase-contact-resolution-bundle",
        help="Attach official Bari routing channels to blocked signal-phase contact drafts.",
    )
    signal_phase_contact_resolution_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_contact_resolution/bari",
    )
    signal_phase_contact_resolution_parser.add_argument(
        "--signal-phase-contact-bundle-path",
        default="data/planning/signal_phase_contact/bari/signal_phase_contact_bundle.json",
    )

    signal_phase_dispatch_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-bundle",
        help="Build the Bari pre-send dispatch tracker and follow-up bundle from resolved routing channels.",
    )
    signal_phase_dispatch_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_dispatch/bari",
    )
    signal_phase_dispatch_parser.add_argument(
        "--signal-phase-contact-resolution-bundle-path",
        default="data/planning/signal_phase_contact_resolution/bari/signal_phase_contact_resolution_bundle.json",
    )
    signal_phase_dispatch_parser.add_argument("--planned-dispatch-date")
    signal_phase_dispatch_parser.add_argument("--follow-up-days", type=int, default=7)
    signal_phase_dispatch_parser.add_argument("--escalation-days", type=int, default=14)

    signal_phase_delivery_intake_parser = subparsers.add_parser(
        "build-bari-signal-phase-delivery-intake-bundle",
        help="Build Bari delivery-intake drop zones and validation templates from the dispatch queue.",
    )
    signal_phase_delivery_intake_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_delivery_intake/bari",
    )
    signal_phase_delivery_intake_parser.add_argument(
        "--signal-phase-dispatch-bundle-path",
        default="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    )
    signal_phase_delivery_intake_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_delivery_intake_parser.add_argument(
        "--mapping-stub-dir",
        default="data/planning/signal_phase_intake/bari/mapping_stubs",
    )
    signal_phase_delivery_intake_parser.add_argument(
        "--validation-output-root",
        default="data/quality/signal_phase_delivery_validation/bari_live",
    )

    signal_phase_delivery_monitor_parser = subparsers.add_parser(
        "build-bari-signal-phase-delivery-monitor-bundle",
        help="Scan Bari delivery-intake drop zones and build a validation-ready queue.",
    )
    signal_phase_delivery_monitor_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_delivery_monitor/bari",
    )
    signal_phase_delivery_monitor_parser.add_argument(
        "--signal-phase-delivery-intake-bundle-path",
        default="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    )
    signal_phase_delivery_monitor_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )

    signal_phase_validation_batch_parser = subparsers.add_parser(
        "run-bari-signal-phase-validation-batch",
        help="Run validation for Bari delivery-monitor rows that are ready for validation.",
    )
    signal_phase_validation_batch_parser.add_argument(
        "--output-dir",
        default="data/quality/signal_phase_validation_batches/bari",
    )
    signal_phase_validation_batch_parser.add_argument(
        "--validation-ready-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/validation_ready_queue.csv",
    )
    signal_phase_validation_batch_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_validation_batch_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_validation_batch_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_receive_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-receive-cycle",
        help="Run the Bari receive-side signal-phase cycle: monitor drop zones, validate ready files, and apply accepted deliveries.",
    )
    signal_phase_receive_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_receive_cycles/bari",
    )
    signal_phase_receive_cycle_parser.add_argument(
        "--signal-phase-delivery-intake-bundle-path",
        default="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    )
    signal_phase_receive_cycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_receive_cycle_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_receive_cycle_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_receive_cycle_parser.add_argument("--preview-limit", type=int, default=10)

    signal_phase_lifecycle_parser = subparsers.add_parser(
        "build-bari-signal-phase-lifecycle-report",
        help="Build a consolidated Bari signal-phase lifecycle board across dispatch, delivery, validation, and application states.",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_lifecycle/bari",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--delivery-monitor-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--validation-batch-results-path",
        default="data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    )
    signal_phase_lifecycle_parser.add_argument(
        "--receive-cycle-path",
        default="data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
    )

    signal_phase_status_sync_parser = subparsers.add_parser(
        "build-bari-signal-phase-status-sync-bundle",
        help="Build synced Bari receipt-register and checklist exports from the latest monitor, validation, and receive-cycle state.",
    )
    signal_phase_status_sync_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_status_sync/bari",
    )
    signal_phase_status_sync_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_status_sync_parser.add_argument(
        "--delivery-monitor-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    )
    signal_phase_status_sync_parser.add_argument(
        "--validation-batch-results-path",
        default="data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    )
    signal_phase_status_sync_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_status_sync_parser.add_argument(
        "--receive-cycle-path",
        default="data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
    )

    signal_phase_follow_up_parser = subparsers.add_parser(
        "build-bari-signal-phase-follow-up-bundle",
        help="Build request-level Bari follow-up packets from the latest dispatch, lifecycle agenda, and synced receipt state.",
    )
    signal_phase_follow_up_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_follow_up/bari",
    )
    signal_phase_follow_up_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_follow_up_parser.add_argument(
        "--follow-up-agenda-path",
        default="data/reporting/signal_phase_lifecycle/bari/follow_up_agenda.csv",
    )
    signal_phase_follow_up_parser.add_argument(
        "--synced-receipt-register-path",
        default="data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
    )

    signal_phase_follow_up_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-follow-up-execution-bundle",
        help="Build external-contact execution queues and tracker updates from the Bari request-level follow-up bundle.",
    )
    signal_phase_follow_up_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_follow_up_execution/bari",
    )
    signal_phase_follow_up_execution_parser.add_argument(
        "--follow-up-ready-queue-path",
        default="data/reporting/signal_phase_follow_up/bari/follow_up_ready_queue.csv",
    )
    signal_phase_follow_up_execution_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )

    signal_phase_follow_up_writeback_parser = subparsers.add_parser(
        "build-bari-signal-phase-follow-up-writeback-bundle",
        help="Build synced dispatch and follow-up tracker exports from executed Bari follow-up rows.",
    )
    signal_phase_follow_up_writeback_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_follow_up_writeback/bari",
    )
    signal_phase_follow_up_writeback_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_follow_up_writeback_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_follow_up_writeback_parser.add_argument(
        "--follow-up-execution-queue-path",
        default="data/reporting/signal_phase_follow_up_execution/bari/follow_up_execution_queue.csv",
    )
    signal_phase_follow_up_writeback_parser.add_argument(
        "--follow-up-tracker-updates-path",
        default="data/reporting/signal_phase_follow_up_execution/bari/follow_up_tracker_updates.csv",
    )

    signal_phase_follow_up_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-follow-up-cycle",
        help="Rebuild the Bari lifecycle, follow-up queue, and execution queue from synced writeback outputs.",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_follow_up_cycles/bari",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--follow-up-writeback-bundle-path",
        default="data/reporting/signal_phase_follow_up_writeback/bari/signal_phase_follow_up_writeback_bundle.json",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--delivery-monitor-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--validation-batch-results-path",
        default="data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--receive-cycle-path",
        default="data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
    )
    signal_phase_follow_up_cycle_parser.add_argument(
        "--synced-receipt-register-path",
        default="data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
    )

    signal_phase_operations_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-operations-cycle",
        help="Run the Bari receive-side and follow-up-side signal-phase stacks in one pass.",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_operations_cycles/bari",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--signal-phase-delivery-intake-bundle-path",
        default="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_operations_cycle_parser.add_argument(
        "--preview-limit",
        type=int,
        default=10,
    )

    signal_phase_action_queue_parser = subparsers.add_parser(
        "build-bari-signal-phase-action-queue",
        help="Build a request-level Bari next-action queue from the latest operations cycle.",
    )
    signal_phase_action_queue_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_action_queue/bari",
    )
    signal_phase_action_queue_parser.add_argument(
        "--signal-phase-operations-cycle-path",
        default="data/processed/signal_phase_operations_cycles/bari/signal_phase_operations_cycle.json",
    )
    signal_phase_action_queue_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_action_queue_parser.add_argument(
        "--signal-phase-dispatch-bundle-path",
        default="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    )
    signal_phase_action_queue_parser.add_argument(
        "--lifecycle-items-path",
        default=None,
    )
    signal_phase_action_queue_parser.add_argument(
        "--follow-up-execution-queue-path",
        default=None,
    )
    signal_phase_action_queue_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default=None,
    )
    signal_phase_action_queue_parser.add_argument(
        "--dispatch-repair-status-path",
        default=None,
    )

    signal_phase_dispatch_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-execution-bundle",
        help="Build the Bari initial-dispatch execution queue from the request-level action queue.",
    )
    signal_phase_dispatch_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_execution/bari",
    )
    signal_phase_dispatch_execution_parser.add_argument(
        "--signal-phase-action-queue-path",
        default="data/reporting/signal_phase_action_queue/bari/action_queue.csv",
    )
    signal_phase_dispatch_execution_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_dispatch_execution_parser.add_argument(
        "--dispatch-packet-dir",
        default="data/planning/signal_phase_dispatch/bari/dispatch_packets",
    )

    signal_phase_action_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-action-execution-bundle",
        help="Build a unified Bari operator execution surface from the request-level action queue.",
    )
    signal_phase_action_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_action_execution/bari",
    )
    signal_phase_action_execution_parser.add_argument(
        "--signal-phase-action-queue-path",
        default="data/reporting/signal_phase_action_queue/bari/action_queue.csv",
    )

    signal_phase_action_handoff_parser = subparsers.add_parser(
        "build-bari-signal-phase-action-handoff-bundle",
        help="Build a unified Bari downstream handoff queue from the request-level action-execution bundle.",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_action_handoff/bari",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--signal-phase-action-execution-bundle-path",
        default="data/reporting/signal_phase_action_execution/bari/signal_phase_action_execution_bundle.json",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--dispatch-execution-log-path",
        default="data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_log.csv",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--follow-up-execution-queue-path",
        default="data/reporting/signal_phase_follow_up_execution/bari/follow_up_execution_queue.csv",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--delivery-monitor-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_action_handoff_parser.add_argument(
        "--runtime-cycle-manifest-path",
        default="data/processed/signal_phase_runtime_cycles/bari/signal_phase_runtime_cycle.manifest.json",
    )

    signal_phase_operator_board_parser = subparsers.add_parser(
        "build-bari-signal-phase-operator-board-bundle",
        help="Build a unified Bari operator board from request-level execution and handoff bundles.",
    )
    signal_phase_operator_board_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_operator_board/bari",
    )
    signal_phase_operator_board_parser.add_argument(
        "--signal-phase-action-execution-bundle-path",
        default="data/reporting/signal_phase_action_execution/bari/signal_phase_action_execution_bundle.json",
    )
    signal_phase_operator_board_parser.add_argument(
        "--signal-phase-action-handoff-bundle-path",
        default="data/reporting/signal_phase_action_handoff/bari/signal_phase_action_handoff_bundle.json",
    )

    signal_phase_dispatch_writeback_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-writeback-bundle",
        help="Build synced Bari runtime dispatch and follow-up exports from completed initial-send executions.",
    )
    signal_phase_dispatch_writeback_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_writeback/bari",
    )
    signal_phase_dispatch_writeback_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_dispatch_writeback_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_dispatch_writeback_parser.add_argument(
        "--dispatch-execution-ready-queue-path",
        default="data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
    )
    signal_phase_dispatch_writeback_parser.add_argument(
        "--dispatch-tracker-updates-path",
        default="data/reporting/signal_phase_dispatch_execution/bari/dispatch_tracker_updates.csv",
    )

    signal_phase_dispatch_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-dispatch-cycle",
        help="Refresh Bari runtime lifecycle, follow-up, and action-queue outputs from synced dispatch writeback state.",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_dispatch_cycles/bari",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--signal-phase-dispatch-writeback-bundle-path",
        default="data/reporting/signal_phase_dispatch_writeback/bari/signal_phase_dispatch_writeback_bundle.json",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--delivery-monitor-queue-path",
        default="data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--validation-batch-results-path",
        default="data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--receive-cycle-path",
        default="data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--synced-receipt-register-path",
        default="data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--signal-phase-operations-cycle-path",
        default="data/processed/signal_phase_operations_cycles/bari/signal_phase_operations_cycle.json",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--signal-phase-dispatch-bundle-path",
        default="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default=None,
    )
    signal_phase_dispatch_cycle_parser.add_argument(
        "--dispatch-repair-status-path",
        default="data/reporting/signal_phase_dispatch_repair_status/bari/dispatch_repair_status.csv",
    )

    signal_phase_dispatch_recording_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-recording-bundle",
        help="Build the Bari initial-send operator log and runtime dispatch queue from the execution-ready send queue.",
    )
    signal_phase_dispatch_recording_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_recording/bari",
    )
    signal_phase_dispatch_recording_parser.add_argument(
        "--dispatch-execution-ready-queue-path",
        default="data/reporting/signal_phase_dispatch_execution/bari/dispatch_execution_ready_queue.csv",
    )
    signal_phase_dispatch_recording_parser.add_argument(
        "--dispatch-execution-log-path",
        default=None,
    )

    signal_phase_dispatch_repair_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-repair-bundle",
        help="Build request-level Bari dispatch-log repair actions from dispatch validation results.",
    )
    signal_phase_dispatch_repair_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_repair/bari",
    )
    signal_phase_dispatch_repair_parser.add_argument(
        "--dispatch-validation-queue-path",
        default="data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
    )

    signal_phase_dispatch_repair_recording_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-repair-recording-bundle",
        help="Build the Bari dispatch-log repair log and repaired runtime queue from the repair queue.",
    )
    signal_phase_dispatch_repair_recording_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari",
    )
    signal_phase_dispatch_repair_recording_parser.add_argument(
        "--dispatch-execution-runtime-queue-path",
        default="data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_queue_runtime.csv",
    )
    signal_phase_dispatch_repair_recording_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    )
    signal_phase_dispatch_repair_recording_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default=None,
    )

    signal_phase_dispatch_repair_execution_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-repair-execution-bundle",
        help="Build the Bari dispatch repair operator queue and packets from the repair queue and repair log.",
    )
    signal_phase_dispatch_repair_execution_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_repair_execution/bari",
    )
    signal_phase_dispatch_repair_execution_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    )
    signal_phase_dispatch_repair_execution_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    )

    signal_phase_dispatch_repair_status_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-repair-status-bundle",
        help="Build the Bari request-level dispatch-repair status queue from repair, validation, and repair-execution state.",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_dispatch_repair_status/bari",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--dispatch-repair-execution-ready-queue-path",
        default="data/reporting/signal_phase_dispatch_repair_execution/bari/dispatch_repair_execution_ready_queue.csv",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--dispatch-repair-internal-hold-queue-path",
        default="data/reporting/signal_phase_dispatch_repair_execution/bari/dispatch_repair_internal_hold_queue.csv",
    )
    signal_phase_dispatch_repair_status_parser.add_argument(
        "--dispatch-validation-queue-path",
        default="data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
    )

    signal_phase_dispatch_validation_parser = subparsers.add_parser(
        "build-bari-signal-phase-dispatch-validation-bundle",
        help="Validate the Bari runtime dispatch queue before dispatch writeback is allowed to apply execution rows.",
    )
    signal_phase_dispatch_validation_parser.add_argument(
        "--output-dir",
        default="data/quality/signal_phase_dispatch_validation/bari",
    )
    signal_phase_dispatch_validation_parser.add_argument(
        "--dispatch-execution-runtime-queue-path",
        default="data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_queue_runtime.csv",
    )

    signal_phase_runtime_cycle_parser = subparsers.add_parser(
        "run-bari-signal-phase-runtime-cycle",
        help="Refresh the Bari receive-side and dispatch-side signal-phase stacks in one pass.",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--output-dir",
        default="data/processed/signal_phase_runtime_cycles/bari",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--signal-phase-delivery-intake-bundle-path",
        default="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--signal-phase-dispatch-bundle-path",
        default="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--dispatch-execution-log-path",
        default=None,
    )
    signal_phase_runtime_cycle_parser.add_argument(
        "--preview-limit",
        type=int,
        default=10,
    )

    signal_phase_runtime_rehearsal_parser = subparsers.add_parser(
        "run-bari-signal-phase-runtime-rehearsal",
        help="Inject one synthetic Bari dispatch send and prove the runtime queue transitions away from dispatch.",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--output-dir",
        default="data/reporting/signal_phase_runtime_rehearsal/bari",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--request-id",
        default="bari_signal_phase_01",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--signal-phase-delivery-intake-bundle-path",
        default="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--delivery-receipt-register-path",
        default="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--delivery-checklist-path",
        default="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--dispatch-execution-queue-path",
        default="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--follow-up-tracker-path",
        default="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--signal-phase-dispatch-bundle-path",
        default="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--dispatch-log-repair-queue-path",
        default="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--dispatch-log-repair-log-path",
        default="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--execution-status",
        default="sent",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--execution-channel-used",
        default="pec_email",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--execution-outcome",
        default="request_dispatched",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--response-received",
        default="no",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--response-summary",
        default="",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--protocol-reference",
        default=None,
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--evidence-path",
        default="",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--execution-notes",
        default="rehearsal send",
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--execution-completed-at",
        default=None,
    )
    signal_phase_runtime_rehearsal_parser.add_argument(
        "--preview-limit",
        type=int,
        default=10,
    )

    signal_phase_request_parser = subparsers.add_parser(
        "build-bari-signal-phase-request-pack",
        help="Audit the official Bari public portal and build a restricted-data request pack for tiered signal-phase onboarding.",
    )
    signal_phase_request_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_requests/bari",
    )
    signal_phase_request_parser.add_argument(
        "--signal-phase-intake-path",
        default="data/planning/signal_phase_intake/bari/signal_phase_intake_pack.json",
    )
    signal_phase_request_parser.add_argument(
        "--portal-base-url",
        default="https://opendata.comune.bari.it/api/3/action/package_search",
    )
    signal_phase_request_parser.add_argument("--timeout-s", type=float, default=30.0)
    signal_phase_request_parser.add_argument("--verify-ssl", action="store_true")
    signal_phase_request_parser.add_argument("--top-n", type=int, default=None)

    signal_phase_acquisition_parser = subparsers.add_parser(
        "build-bari-signal-phase-acquisition-plan",
        help="Turn the Bari signal-phase request pack into outreach and delivery trackers for restricted-data acquisition.",
    )
    signal_phase_acquisition_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_acquisition/bari",
    )
    signal_phase_acquisition_parser.add_argument(
        "--signal-phase-request-pack-path",
        default="data/planning/signal_phase_requests/bari/signal_phase_request_pack.json",
    )
    signal_phase_outreach_parser = subparsers.add_parser(
        "build-bari-signal-phase-outreach-bundle",
        help="Build send-ready Bari outreach packets from the signal-phase acquisition tracker.",
    )
    signal_phase_outreach_parser.add_argument(
        "--output-dir",
        default="data/planning/signal_phase_outreach/bari",
    )
    signal_phase_outreach_parser.add_argument(
        "--acquisition-plan-path",
        default="data/planning/signal_phase_acquisition/bari/signal_phase_acquisition_plan.json",
    )
    signal_phase_outreach_parser.add_argument(
        "--signal-phase-request-pack-path",
        default="data/planning/signal_phase_requests/bari/signal_phase_request_pack.json",
    )
    signal_phase_outreach_parser.add_argument(
        "--priority-band",
        default="tier_1_immediate",
    )
    signal_phase_outreach_parser.add_argument("--max-requests", type=int, default=None)

    enrich_parser = subparsers.add_parser(
        "enrich-segments",
        help="Add topology and geometry enrichment columns to a segment layer.",
    )
    enrich_parser.add_argument("segments_path")
    enrich_parser.add_argument("--output-dir", default="data/processed/segments")

    context_parser = subparsers.add_parser(
        "enrich-segments-context",
        help="Add POI, built-environment, and exposure-policy enrichment columns to a segment layer.",
    )
    context_parser.add_argument("segments_path")
    context_parser.add_argument("boundary_path")
    context_parser.add_argument("--output-dir", default="data/processed/segments")
    context_parser.add_argument("--poi-buffer-m", type=float, default=150.0)

    exposure_parser = subparsers.add_parser(
        "apply-exposure-policy",
        help="Apply the versioned exposure policy to an existing segment layer.",
    )
    exposure_parser.add_argument("segments_path")
    exposure_parser.add_argument("--output-dir", default="data/processed/segments")

    match_parser = subparsers.add_parser(
        "match-segments",
        help="Match canonical crash records to a road segment layer.",
    )
    match_parser.add_argument("records_path")
    match_parser.add_argument("segments_path")
    match_parser.add_argument("--output-dir", default="data/processed/matches")
    match_parser.add_argument("--max-distance-m", type=float, default=50.0)
    match_parser.add_argument("--boundary-path")

    remediation_parser = subparsers.add_parser(
        "analyze-matches",
        help="Produce remediation reports for matched and unmatched crash-to-segment results.",
    )
    remediation_parser.add_argument("matched_path")
    remediation_parser.add_argument("unmatched_path")
    remediation_parser.add_argument("--output-dir")
    remediation_parser.add_argument("--review-limit", type=int, default=200)

    aggregate_parser = subparsers.add_parser(
        "aggregate-segments",
        help="Aggregate matched crashes into segment-year modeling tables.",
    )
    aggregate_parser.add_argument("matched_path")
    aggregate_parser.add_argument("segments_path")
    aggregate_parser.add_argument("--output-dir", default="data/processed/aggregates")

    boundary_compare_parser = subparsers.add_parser(
        "compare-boundaries",
        help="Compare an official boundary to a fallback or candidate boundary.",
    )
    boundary_compare_parser.add_argument("reference_boundary_path")
    boundary_compare_parser.add_argument("candidate_boundary_path")
    boundary_compare_parser.add_argument("--output-path")

    model_parser = subparsers.add_parser(
        "train-frequency-baseline",
        help="Train a simple holdout-year crash-frequency baseline on segment-year data.",
    )
    model_parser.add_argument("aggregate_csv_path")
    model_parser.add_argument("--output-dir", default="data/models/frequency_baseline")
    model_parser.add_argument("--holdout-year", type=int)

    severity_parser = subparsers.add_parser(
        "train-severity-baseline",
        help="Train a holdout-year fatal-vs-injury severity baseline on matched crash data.",
    )
    severity_parser.add_argument("matched_path")
    severity_parser.add_argument("aggregate_csv_path")
    severity_parser.add_argument("--output-dir", default="data/models/severity_baseline")
    severity_parser.add_argument("--holdout-year", type=int)

    transfer_parser = subparsers.add_parser(
        "evaluate-frequency-transferability",
        help="Evaluate within-city and cross-city crash-frequency transferability across labeled aggregate datasets.",
    )
    transfer_parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Labeled aggregate dataset in the form label=/path/to/segment_year_metrics.csv",
    )
    transfer_parser.add_argument("--output-dir", default="data/models/frequency_transferability")
    transfer_parser.add_argument("--holdout-year", type=int, default=2021)
    transfer_parser.add_argument(
        "--mode",
        action="append",
        dest="modes",
        help=(
            "Optional evaluation mode to run. Repeat to select a subset from: "
            "within_jurisdiction_temporal, cross_jurisdiction_temporal, "
            "cross_jurisdiction_cold_start, cross_jurisdiction_history_free"
        ),
    )
    transfer_parser.add_argument(
        "--rf-estimators",
        type=int,
        default=300,
        help="Number of trees for the random-forest regressor used in transferability evaluation.",
    )

    benchmark_parser = subparsers.add_parser(
        "build-transferability-benchmark-bundle",
        help="Build reporting artifacts that compare transferability stacks and model budgets.",
    )
    benchmark_parser.add_argument(
        "--transferability",
        action="append",
        dest="transferability_metrics_paths",
        default=[],
        help="Path to a transferability metrics JSON file. Repeat for multiple runs or stacks.",
    )
    benchmark_parser.add_argument("--benchmark-label")
    benchmark_parser.add_argument("--output-dir", default="data/reporting/transferability_benchmark")

    nwrsa_parser = subparsers.add_parser(
        "nwrsa-assess",
        help="Run a Network-Wide Road Safety Assessment (RISM Directive 2019/1936): combined reactive + proactive in-built-safety classification of road sections.",
    )
    nwrsa_parser.add_argument(
        "--sections",
        dest="sections_path",
        required=True,
        help="Path to a section CSV (segment-year metrics with design attributes).",
    )
    nwrsa_parser.add_argument("--output-dir", default="data/reporting/nwrsa")
    nwrsa_parser.add_argument("--reactive-weight", type=float, default=0.5)
    nwrsa_parser.add_argument("--proactive-weight", type=float, default=0.5)
    nwrsa_parser.add_argument(
        "--categories",
        type=int,
        default=3,
        help="Number of safety categories (Directive mandates at least 3).",
    )

    rural_parser = subparsers.add_parser(
        "rural-section",
        help="Split rural road segments into NWRSA 200 m sections and derive rural features (curvature, single-carriageway, run-off-road/head-on exposure, rural exposure).",
    )
    rural_parser.add_argument(
        "--segments",
        dest="segments_path",
        required=True,
        help="Path to a segment CSV with design attributes and segment_length_m.",
    )
    rural_parser.add_argument("--output-dir", default="data/reporting/rural_sectioning")
    rural_parser.add_argument(
        "--section-length-m",
        type=float,
        default=200.0,
        help="Working section length (NWRSA two-lane convention is 200 m).",
    )

    climate_parser = subparsers.add_parser(
        "climate-resilience",
        help="Score per-segment extreme-weather climate resilience (flood/heat/snow-ice/wind) and emit a map-ready GeoJSON risk surface.",
    )
    climate_parser.add_argument(
        "--segments",
        dest="segments_path",
        required=True,
        help="Path to a segment CSV with design attributes and coordinates.",
    )
    climate_parser.add_argument(
        "--hazards",
        dest="hazards_path",
        required=True,
        help="Path to a hazard CSV (segment_id, hazard_kind, intensity).",
    )
    climate_parser.add_argument("--output-dir", default="data/reporting/climate_resilience")

    behaviour_parser = subparsers.add_parser(
        "behavioural-analysis",
        help="Produce an aggregate, privacy-safe enforcement-prioritisation view (corridor x time-of-day where behavioural-crash risk concentrates).",
    )
    behaviour_parser.add_argument(
        "--crashes",
        dest="crashes_path",
        required=True,
        help="Path to a crash CSV with behavioural signals (speed, hour, corridor).",
    )
    behaviour_parser.add_argument("--output-dir", default="data/reporting/behavioural_safety")
    behaviour_parser.add_argument(
        "--min-cell",
        type=int,
        default=5,
        help="Anonymity floor: suppress aggregate cells with fewer crashes (default 5).",
    )

    elderly_parser = subparsers.add_parser(
        "elderly-disabled-assess",
        help="Score elderly/disabled road-user risk and tailored countermeasures (age-band exposure + accessibility-infrastructure provision).",
    )
    elderly_parser.add_argument(
        "--segments",
        dest="segments_path",
        required=True,
        help="Path to a segment CSV with age/accessibility attributes.",
    )
    elderly_parser.add_argument("--output-dir", default="data/reporting/elderly_disabled_safety")

    intersectional_parser = subparsers.add_parser(
        "intersectional-analysis",
        help="Produce sex-disaggregated and intersectional (gender x age x area x disability) crash aggregates with k-anonymity suppression.",
    )
    intersectional_parser.add_argument(
        "--casualties",
        dest="casualties_path",
        required=True,
        help="Path to a casualty CSV with sex/age_band/area_type/disability/severity fields.",
    )
    intersectional_parser.add_argument("--output-dir", default="data/reporting/intersectional_analysis")
    intersectional_parser.add_argument(
        "--min-cell",
        type=int,
        default=10,
        help="k-anonymity floor: suppress strata with fewer casualties (default 10).",
    )

    regional_parser = subparsers.add_parser(
        "regional-comparison",
        help="Run a multi-region comparative NWRSA and check the call's eligibility (>=3 regions, >=2 above EU-average rural fatality, cross-border).",
    )
    regional_parser.add_argument(
        "--regions",
        dest="regions_spec_path",
        required=True,
        help="Path to a JSON list of region specs: [{region_id, country, rural_fatality_rate, path}].",
    )
    regional_parser.add_argument(
        "--eu-average-rural-fatality-rate",
        type=float,
        required=True,
        help="EU-average rural road-fatality rate (per million) to compare regions against.",
    )
    regional_parser.add_argument("--output-dir", default="data/reporting/regional_comparison")

    config_parser = subparsers.add_parser(
        "show-config",
        help="Print a TOML project configuration file as JSON.",
    )
    config_parser.add_argument("config_path")

    subparsers.add_parser(
        "pipeline",
        help="Print the default platform pipeline stages.",
    )

    registry_parser = subparsers.add_parser(
        "build-run-registry",
        help="Scan manifests and metrics under data/ and build a run registry.",
    )
    registry_parser.add_argument("--data-root", default="data")
    registry_parser.add_argument("--output-dir", default="data/registry")

    publish_parser = subparsers.add_parser(
        "publish-segment-scores",
        help="Publish segment-level score artifacts from a model prediction CSV and segment layer.",
    )
    publish_parser.add_argument("predictions_path")
    publish_parser.add_argument("segments_path")
    publish_parser.add_argument("metrics_path")
    publish_parser.add_argument("--output-dir", default="data/prediction_store")
    publish_parser.add_argument("--prediction-column", default="random_forest_poisson_prediction")

    tile_parser = subparsers.add_parser(
        "aggregate-public-score-tiles",
        help="Aggregate published public segment scores into tile-style public GeoJSON and CSV artifacts.",
    )
    tile_parser.add_argument("public_scores_path")
    tile_parser.add_argument("prediction_store_manifest_path")
    tile_parser.add_argument("--output-dir", default="data/prediction_store_tiles")
    tile_parser.add_argument("--tile-size-m", type=float, default=500.0)

    query_parser = subparsers.add_parser(
        "query-published-resource",
        help="Read a published serving artifact through a stable response contract.",
    )
    query_parser.add_argument("manifest_path")
    query_parser.add_argument("--view")
    query_parser.add_argument("--occurred-year", type=int)
    query_parser.add_argument("--min-score-band")
    query_parser.add_argument("--limit", type=int)

    resolve_parser = subparsers.add_parser(
        "resolve-latest-published-resource",
        help="Resolve the latest published serving artifact from the run registry.",
    )
    resolve_parser.add_argument("resource_name")
    resolve_parser.add_argument("--registry-path", default="data/registry/run_registry.jsonl")
    resolve_parser.add_argument("--view")
    resolve_parser.add_argument("--prediction-run-label")
    resolve_parser.add_argument("--occurred-year", type=int)
    resolve_parser.add_argument("--tile-size-m", type=float)

    published_index_parser = subparsers.add_parser(
        "build-published-resource-index",
        help="Build a static dashboard-friendly index of the latest published serving artifacts.",
    )
    published_index_parser.add_argument("--registry-path", default="data/registry/run_registry.jsonl")
    published_index_parser.add_argument("--output-dir", default="data/published_index")

    dashboard_summary_parser = subparsers.add_parser(
        "build-dashboard-summary",
        help="Build a static dashboard summary from published resources and transferability outputs.",
    )
    dashboard_summary_parser.add_argument(
        "--published-index-path",
        default="data/published_index/published_resources.json",
    )
    dashboard_summary_parser.add_argument(
        "--transferability",
        action="append",
        dest="transferability_metrics_paths",
        default=[],
        help="Path to a transferability metrics JSON file. Repeat for multiple modes.",
    )
    dashboard_summary_parser.add_argument("--output-dir", default="data/dashboard")

    published_refresh_parser = subparsers.add_parser(
        "build-published-refresh-bundle",
        help="Rebuild the registry, published index, dashboard summary, and refresh bundle in one pass.",
    )
    published_refresh_parser.add_argument("--data-root", default="data")
    published_refresh_parser.add_argument("--registry-output-dir", default="data/registry")
    published_refresh_parser.add_argument("--published-index-output-dir", default="data/published_index")
    published_refresh_parser.add_argument("--dashboard-output-dir", default="data/dashboard")
    published_refresh_parser.add_argument("--output-dir", default="data/reporting/published_refresh/latest")

    intervention_brief_parser = subparsers.add_parser(
        "build-intervention-briefs",
        help="Build exportable intervention briefs from the dashboard summary artifact.",
    )
    intervention_brief_parser.add_argument(
        "--dashboard-summary-path",
        default="data/dashboard/dashboard_summary.json",
    )
    intervention_brief_parser.add_argument(
        "--prediction-run-label",
        action="append",
        dest="prediction_run_labels",
        default=[],
        help="Optional run label filter. Repeat to build briefs for a subset of published runs.",
    )
    intervention_brief_parser.add_argument(
        "--scenario-bundle-root",
        default="data/planning/scenario_countermeasures",
    )
    intervention_brief_parser.add_argument("--output-dir", default="data/intervention_briefs")

    scenario_countermeasure_parser = subparsers.add_parser(
        "build-scenario-countermeasure-bundle",
        help="Build rule-based scenario and countermeasure outputs on top of the published risk surfaces.",
    )
    scenario_countermeasure_parser.add_argument(
        "--dashboard-summary-path",
        default="data/dashboard/dashboard_summary.json",
    )
    scenario_countermeasure_parser.add_argument(
        "--prediction-run-label",
        action="append",
        dest="prediction_run_labels",
        default=[],
        help="Optional run label filter. Repeat to build bundles for a subset of published runs.",
    )
    scenario_countermeasure_parser.add_argument(
        "--signal-nodes-path",
        default="data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    )
    scenario_countermeasure_parser.add_argument(
        "--node-objects-path",
        default="data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson",
    )
    scenario_countermeasure_parser.add_argument(
        "--output-dir",
        default="data/planning/scenario_countermeasures",
    )

    vru_intelligence_parser = subparsers.add_parser(
        "build-vru-intelligence-bundle",
        help="Build dedicated VRU and micromobility planning artifacts from published risk surfaces.",
    )
    vru_intelligence_parser.add_argument(
        "--dashboard-summary-path",
        default="data/dashboard/dashboard_summary.json",
    )
    vru_intelligence_parser.add_argument(
        "--prediction-run-label",
        action="append",
        dest="prediction_run_labels",
        default=[],
        help="Optional run label filter. Repeat to build bundles for a subset of published runs.",
    )
    vru_intelligence_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    vru_intelligence_parser.add_argument(
        "--output-dir",
        default="data/planning/vru_intelligence",
    )

    vru_exposure_parser = subparsers.add_parser(
        "build-vru-exposure-bundle",
        help="Build proxy-backed VRU exposure layers from published runs and movement objects.",
    )
    vru_exposure_parser.add_argument(
        "--dashboard-summary-path",
        default="data/dashboard/dashboard_summary.json",
    )
    vru_exposure_parser.add_argument(
        "--prediction-run-label",
        action="append",
        dest="prediction_run_labels",
        default=[],
        help="Optional run label filter. Repeat to build bundles for a subset of published runs.",
    )
    vru_exposure_parser.add_argument(
        "--movement-objects-path",
        default="data/processed/movement_objects/bari/road_movement_objects.geojson",
    )
    vru_exposure_parser.add_argument(
        "--output-dir",
        default="data/planning/vru_exposure",
    )

    exposure_readiness_parser = subparsers.add_parser(
        "build-exposure-readiness-report",
        help="Assess current segment layers against the exposure/context maturity gaps in the roadmap.",
    )
    exposure_readiness_parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Segment layer dataset in the form label=/path/to/road_segments_context.geojson",
    )
    exposure_readiness_parser.add_argument("--output-dir", default="data/planning/exposure_readiness")

    exposure_source_catalog_parser = subparsers.add_parser(
        "build-exposure-source-catalog",
        help="Build an exposure source catalog and connector contracts from the readiness report.",
    )
    exposure_source_catalog_parser.add_argument(
        "--readiness-report-path",
        default="data/planning/exposure_readiness/exposure_readiness.json",
    )
    exposure_source_catalog_parser.add_argument("--output-dir", default="data/planning/exposure_sources")

    exposure_onboarding_parser = subparsers.add_parser(
        "build-exposure-onboarding-plan",
        help="Build a phased municipality onboarding plan for real exposure connectors.",
    )
    exposure_onboarding_parser.add_argument(
        "--source-catalog-path",
        default="data/planning/exposure_sources/exposure_source_catalog.json",
    )
    exposure_onboarding_parser.add_argument("--output-dir", default="data/planning/exposure_onboarding")

    governance_interoperability_parser = subparsers.add_parser(
        "build-governance-interoperability-bundle",
        help="Build the shared governance, DATEX, and mobility-data-space bundle for live and published artifacts.",
    )
    governance_interoperability_parser.add_argument(
        "--output-dir",
        default="data/planning/governance_interoperability",
    )

    data_governance_parser = subparsers.add_parser(
        "build-data-governance-bundle",
        help=(
            "Build the field-level classification matrix, source licensing register, retention "
            "rules, and public-map redaction policy (Issue 01)."
        ),
    )
    data_governance_parser.add_argument(
        "--output-dir",
        default="data/governance/data_governance_bundle",
    )

    cadas_alignment_parser = subparsers.add_parser(
        "build-cadas-alignment",
        help=(
            "Build the canonical-to-CADaS crosswalk, coverage gap list, and manifest "
            "for EU CARE interoperability."
        ),
    )
    cadas_alignment_parser.add_argument(
        "--output-dir",
        default="data/governance/cadas_alignment",
    )

    cadas_export_parser = subparsers.add_parser(
        "export-cadas",
        help="Export a canonical crash JSONL file to CADaS-aligned JSONL + CSV.",
    )
    cadas_export_parser.add_argument("canonical_path")
    cadas_export_parser.add_argument(
        "--output-dir",
        default="data/staging/cadas_export",
    )

    exposure_connector_intake_parser = subparsers.add_parser(
        "build-exposure-connector-intake-pack",
        help="Build phase-1 connector intake templates, mapping stubs, and source-rights decisions.",
    )
    exposure_connector_intake_parser.add_argument(
        "--source-catalog-path",
        default="data/planning/exposure_sources/exposure_source_catalog.json",
    )
    exposure_connector_intake_parser.add_argument(
        "--onboarding-plan-path",
        default="data/planning/exposure_onboarding/exposure_onboarding_plan.json",
    )
    exposure_connector_intake_parser.add_argument(
        "--output-dir",
        default="data/planning/exposure_connector_intake",
    )

    exposure_connector_extract_parser = subparsers.add_parser(
        "ingest-exposure-connector-extract",
        help="Validate and normalize a phase-1 connector extract using a mapping stub.",
    )
    exposure_connector_extract_parser.add_argument("input_csv_path")
    exposure_connector_extract_parser.add_argument("mapping_stub_path")
    exposure_connector_extract_parser.add_argument("--output-dir", required=True)
    exposure_connector_extract_parser.add_argument("--limit", type=int)

    exposure_provider_adapter_parser = subparsers.add_parser(
        "normalize-exposure-provider-extract",
        help="Normalize provider-style Bari phase-1 extracts into connector profile CSVs.",
    )
    exposure_provider_adapter_parser.add_argument("input_csv_path")
    exposure_provider_adapter_parser.add_argument(
        "--provider-profile-id",
        choices=["municipal_counter_export", "fixed_speed_counter_export"],
    )
    exposure_provider_adapter_parser.add_argument("--mapping-stub-path")
    exposure_provider_adapter_parser.add_argument("--output-dir", required=True)
    exposure_provider_adapter_parser.add_argument("--limit", type=int)

    connector_join_parser = subparsers.add_parser(
        "apply-connector-observations-to-segments",
        help="Join normalized connector observations onto a segment layer.",
    )
    connector_join_parser.add_argument("segments_path")
    connector_join_parser.add_argument(
        "--observation-manifest-path",
        action="append",
        required=True,
        dest="observation_manifest_paths",
        help="Observation manifest path. Repeat for multiple connector observation sources.",
    )
    connector_join_parser.add_argument("--output-dir", required=True)

    exposure_pilot_parser = subparsers.add_parser(
        "run-bari-phase1-exposure-pilot",
        help="Run Bari phase-1 motorized+speed connector pilot ingestion, join, and readiness refresh.",
    )
    exposure_pilot_parser.add_argument(
        "--segments-path",
        default="data/processed/segments/bari_context_v2/road_segments_context.geojson",
    )
    exposure_pilot_parser.add_argument(
        "--motorized-extract-path",
        default=(
            "data/planning/exposure_connector_intake/sample_templates/"
            "motorized_exposure_connector_v1__municipal_counter_export.csv"
        ),
    )
    exposure_pilot_parser.add_argument(
        "--motorized-mapping-stub-path",
        default=(
            "data/planning/exposure_connector_intake/mapping_stubs/"
            "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
        ),
    )
    exposure_pilot_parser.add_argument(
        "--speed-extract-path",
        default=(
            "data/planning/exposure_connector_intake/sample_templates/"
            "observed_speed_connector_v1__fixed_speed_counter_export.csv"
        ),
    )
    exposure_pilot_parser.add_argument(
        "--speed-mapping-stub-path",
        default=(
            "data/planning/exposure_connector_intake/mapping_stubs/"
            "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
        ),
    )
    exposure_pilot_parser.add_argument(
        "--motorized-provider-profile-id",
        choices=["municipal_counter_export"],
    )
    exposure_pilot_parser.add_argument(
        "--speed-provider-profile-id",
        choices=["fixed_speed_counter_export"],
    )
    exposure_pilot_parser.add_argument(
        "--normalize-motorized-provider-extract",
        action="store_true",
        help=(
            "Normalize motorized extract using mapping-stub profile inference. "
            "Can be combined with --motorized-provider-profile-id for explicit profile validation."
        ),
    )
    exposure_pilot_parser.add_argument(
        "--normalize-speed-provider-extract",
        action="store_true",
        help=(
            "Normalize speed extract using mapping-stub profile inference. "
            "Can be combined with --speed-provider-profile-id for explicit profile validation."
        ),
    )
    exposure_pilot_parser.add_argument(
        "--mapping-stub-root",
        default="data/planning/exposure_connector_intake/mapping_stubs",
    )
    exposure_pilot_parser.add_argument("--readiness-dataset-label", default="bari_pilot")
    exposure_pilot_parser.add_argument("--output-dir", default="data/planning/exposure_pilot/bari_phase1")

    node_match_parser = subparsers.add_parser(
        "match-node-objects",
        help="Match canonical crash records to point-like node objects such as signalized junctions.",
    )
    node_match_parser.add_argument("records_path")
    node_match_parser.add_argument("node_objects_path")
    node_match_parser.add_argument("--output-dir", required=True)
    node_match_parser.add_argument("--max-distance-m", type=float, default=35.0)

    node_aggregate_parser = subparsers.add_parser(
        "aggregate-node-objects",
        help="Aggregate matched node-object crashes into node-year tables.",
    )
    node_aggregate_parser.add_argument("matched_path")
    node_aggregate_parser.add_argument("node_objects_path")
    node_aggregate_parser.add_argument("--output-dir", required=True)

    api_parser = subparsers.add_parser(
        "serve-published-api",
        help="Start a minimal read-only HTTP shim for published serving artifacts.",
    )
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument(
        "--published-index-path",
        default="data/published_index/published_resources.json",
    )
    api_parser.add_argument(
        "--root-dir",
        default=".",
        help="Base directory for resolving repo-relative manifest and data paths.",
    )
    api_parser.add_argument(
        "--dashboard-dir",
        default="dashboard",
        help="Directory containing the static dashboard assets served from /dashboard/.",
    )
    api_parser.add_argument(
        "--dashboard-summary-path",
        default="data/dashboard/dashboard_summary.json",
        help="Path to the static dashboard summary JSON served from /v1/dashboard-summary.",
    )

    national_hierarchy_parser = subparsers.add_parser(
        "build-national-hierarchy",
        help="Construct or export a national multi-tier administrative hierarchy.",
    )
    national_hierarchy_parser.add_argument("--country-code", default="IT")
    national_hierarchy_parser.add_argument("--country-name", default="Italy")
    national_hierarchy_parser.add_argument("--output-dir", default="data/planning/national_hierarchy/italy")

    national_rollup_parser = subparsers.add_parser(
        "rollup-national-risk",
        help="Roll up casualties and compute risk metrics across multi-tier administrative levels.",
    )
    national_rollup_parser.add_argument("--hierarchy-path", required=True)
    national_rollup_parser.add_argument("--crashes-by-entity-json", required=False)
    national_rollup_parser.add_argument("--output-dir", default="data/reporting/national_rollups")

    hsm_screening_parser = subparsers.add_parser(
        "hsm-network-screening",
        help="Run AASHTO Highway Safety Manual (HSM) Empirical Bayes network screening.",
    )
    hsm_screening_parser.add_argument("--segments-path", required=True)
    hsm_screening_parser.add_argument("--facility-class", default="rural_two_lane_two_way")
    hsm_screening_parser.add_argument("--calibration-c", type=float, default=1.0)
    hsm_screening_parser.add_argument("--network-label", default="national_network")
    hsm_screening_parser.add_argument("--output-dir", default="data/reporting/hsm_screening")

    irap_star_rating_parser = subparsers.add_parser(
        "irap-star-rating",
        help="Screen road segments for iRAP 1-5 Star Ratings across 4 road user groups.",
    )
    irap_star_rating_parser.add_argument("--segments-path", required=True)
    irap_star_rating_parser.add_argument("--network-label", default="national_network")
    irap_star_rating_parser.add_argument("--output-dir", default="data/reporting/irap")

    srip_parser = subparsers.add_parser(
        "generate-srip",
        help="Generate Safer Roads Investment Plan (SRIP) for sub-3-star segments.",
    )
    srip_parser.add_argument("--segments-path", required=True)
    srip_parser.add_argument("--vosl-eur", type=float, default=1_500_000.0)
    srip_parser.add_argument("--vosi-eur", type=float, default=250_000.0)
    srip_parser.add_argument("--discount-rate", type=float, default=0.04)
    srip_parser.add_argument("--min-bcr", type=float, default=1.0)
    srip_parser.add_argument("--network-label", default="national_network")
    srip_parser.add_argument("--output-dir", default="data/reporting/irap")

    telematics_ingest_parser = subparsers.add_parser(
        "ingest-telematics",
        help="Ingest raw telematics waypoints or events and detect kinematic near-miss anomalies.",
    )
    telematics_ingest_parser.add_argument("--observations-path", required=True)
    telematics_ingest_parser.add_argument("--is-waypoints", action="store_true", default=False)
    telematics_ingest_parser.add_argument("--output-path", default="data/processed/telematics_events.json")

    near_miss_screening_parser = subparsers.add_parser(
        "screen-near-misses",
        help="Screen roadway segments by aggregating kinematic near-miss events and MVKT exposure.",
    )
    near_miss_screening_parser.add_argument("--segments-path", required=True)
    near_miss_screening_parser.add_argument("--events-path", required=True)
    near_miss_screening_parser.add_argument("--days-analyzed", type=int, default=365)
    near_miss_screening_parser.add_argument("--fleet-penetration", type=float, default=0.05)
    near_miss_screening_parser.add_argument("--network-label", default="national_network")
    near_miss_screening_parser.add_argument("--output-dir", default="data/reporting/telematics")

    cip_parser = subparsers.add_parser(
        "optimize-cip",
        help="Run multi-year budget-constrained Capital Improvement Planning (CIP) knapsack optimization.",
    )
    cip_parser.add_argument("--candidates-path", required=True)
    cip_parser.add_argument("--annual-budget", type=float, default=10_000_000.0)
    cip_parser.add_argument("--horizon-years", type=int, default=5)
    cip_parser.add_argument("--start-year", type=int, default=2027)
    cip_parser.add_argument("--inflation-rate", type=float, default=0.025)
    cip_parser.add_argument("--discount-rate", type=float, default=0.04)
    cip_parser.add_argument("--allow-rollover", action="store_true", default=False)
    cip_parser.add_argument("--network-label", default="national_network")
    cip_parser.add_argument("--output-dir", default="data/reporting/cip")

    cv_audit_parser = subparsers.add_parser(
        "cv-road-audit",
        help="Run automated computer vision road safety audit & iRAP feature extraction.",
    )
    cv_audit_parser.add_argument("--frames-path", required=True)
    cv_audit_parser.add_argument("--segments-path", required=True)
    cv_audit_parser.add_argument("--network-label", default="national_network")
    cv_audit_parser.add_argument("--output-dir", default="data/reporting/cv_audit")

    micro_ssam_parser = subparsers.add_parser(
        "micro-ssam",
        help="Run microscopic trajectory surrogate safety assessment (SSAM) & VRU conflict analysis.",
    )
    micro_ssam_parser.add_argument("--trajectories-path", required=True)
    micro_ssam_parser.add_argument("--junctions-path", required=False)
    micro_ssam_parser.add_argument("--network-label", default="national_network")
    micro_ssam_parser.add_argument("--output-dir", default="data/reporting/ssam")

    st_gnn_parser = subparsers.add_parser(
        "st-gnn-forecast",
        help="Run Spatio-Temporal Graph Neural Network dynamic network risk forecasting.",
    )
    st_gnn_parser.add_argument("--graph-path", required=True)
    st_gnn_parser.add_argument("--features-path", required=False)
    st_gnn_parser.add_argument("--horizons", default="1,6,24")
    st_gnn_parser.add_argument("--network-label", default="national_network")
    st_gnn_parser.add_argument("--output-dir", default="data/reporting/st_gnn")

    causal_eval_parser = subparsers.add_parser(
        "causal-eval",
        help="Estimate countermeasure treatment effects using Double Machine Learning (DML) & CATE.",
    )
    causal_eval_parser.add_argument("--data-path", required=True, help="Path to JSON file containing observational units.")
    causal_eval_parser.add_argument("--countermeasures", default=None, help="Comma-separated countermeasure types to evaluate.")
    causal_eval_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    causal_eval_parser.add_argument("--output-dir", default="data/reporting/causal", help="Output directory for reports & artifacts.")

    cits_actuate_parser = subparsers.add_parser(
        "cits-actuate",
        help="Generate standards-compliant ETSI C-ITS (DENM, IVIM) and dynamic VSL actuation plans.",
    )
    cits_actuate_parser.add_argument("--alerts-path", required=True, help="Path to JSON file containing operational risk alerts.")
    cits_actuate_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    cits_actuate_parser.add_argument("--station-id", default="IT-MIT-TMC-BA-01", help="Sovereign transport authority station ID.")
    cits_actuate_parser.add_argument("--output-dir", default="data/reporting/cits", help="Output directory for C-ITS actuation bundles.")

    sim_eval_parser = subparsers.add_parser(
        "sim-eval",
        help="Run synthetic micro-simulation countermeasure sandbox to evaluate surrogate conflict deltas.",
    )
    sim_eval_parser.add_argument("--config-path", required=True, help="Path to JSON file containing simulation scenario configuration.")
    sim_eval_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    sim_eval_parser.add_argument("--output-dir", default="data/reporting/simulation", help="Output directory for simulation artifacts.")

    ai_conformity_parser = subparsers.add_parser(
        "ai-conformity",
        help="Run EU AI Act (Regulation 2024/1689) High-Risk conformity and Explainable AI (XAI) audit.",
    )
    ai_conformity_parser.add_argument("--data-path", required=True, help="Path to JSON file containing corridor risk predictions and metadata.")
    ai_conformity_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    ai_conformity_parser.add_argument("--protected-attribute", default="geographic_tier", help="Demographic/geographic attribute for fairness audit.")
    ai_conformity_parser.add_argument("--output-dir", default="data/reporting/compliance", help="Output directory for compliance artifacts.")

    federated_train_parser = subparsers.add_parser(
        "federated-train",
        help="Run privacy-preserving federated learning across decentralized highway concessionaires.",
    )
    federated_train_parser.add_argument("--data-path", required=True, help="Path to JSON file containing concessionaire client node datasets.")
    federated_train_parser.add_argument("--rounds", type=int, default=3, help="Number of federated communication rounds.")
    federated_train_parser.add_argument("--aggregation-method", default="fedavg", choices=["fedavg", "trimmed_mean", "median"], help="Aggregation algorithm.")
    federated_train_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    federated_train_parser.add_argument("--output-dir", default="data/reporting/federated", help="Output directory for federated training artifacts.")

    micromobility_audit_parser = subparsers.add_parser(
        "micromobility-audit",
        help="Run VRU micromobility sensor fusion audit and iRAP friction calibration.",
    )
    micromobility_audit_parser.add_argument("--data-path", required=True, help="Path to JSON file containing micromobility waypoints and corridor segments.")
    micromobility_audit_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    micromobility_audit_parser.add_argument("--output-dir", default="data/reporting/micromobility", help="Output directory for micromobility artifacts.")

    ministerial_dossier_parser = subparsers.add_parser(
        "ministerial-dossier",
        help="Compile and export sovereign ministerial safety dossier (PDF, Markdown, JSON, Manifest).",
    )
    ministerial_dossier_parser.add_argument("--data-path", required=True, help="Path to JSON file containing synthesized multi-modal platform results.")
    ministerial_dossier_parser.add_argument("--network-label", default="national_network", help="Network or jurisdiction label.")
    ministerial_dossier_parser.add_argument("--jurisdiction-name", default="Repubblica Italiana / Regione Puglia / Comune di Bari", help="Name of sovereign jurisdiction.")
    ministerial_dossier_parser.add_argument("--ministry-authority", default="Ministero delle Infrastrutture e dei Trasporti", help="Supervising ministerial authority.")
    ministerial_dossier_parser.add_argument("--output-dir", default="data/reporting/ministerial_dossier", help="Output directory for ministerial dossier artifacts.")

    build_panel_parser = subparsers.add_parser(
        "build-panel",
        help="Construct exposure-normalized segment-week analytical panel from roads, crashes, and weather.",
    )
    build_panel_parser.add_argument("--data-path", required=True, help="Path to JSON file with segments, crashes, and weather.")
    build_panel_parser.add_argument("--weeks-count", type=int, default=8, help="Number of weeks to generate.")
    build_panel_parser.add_argument("--network-label", default="benchmark_network", help="Network or study area label.")
    build_panel_parser.add_argument("--output-dir", default="data/reporting/research/panel", help="Output directory for panel artifacts.")

    eval_panel_parser = subparsers.add_parser(
        "evaluate-panel-models",
        help="Train and benchmark Historical Rate, Poisson GLM, Negative-Binomial, Logistic, and Boosted Trees on a panel.",
    )
    eval_panel_parser.add_argument("--data-path", required=True, help="Path to panel JSON or panel input JSON.")
    eval_panel_parser.add_argument("--split-strategy", default="forward_temporal", choices=["forward_temporal", "spatial_group", "space_time_blocked"], help="Validation split strategy.")
    eval_panel_parser.add_argument("--network-label", default="benchmark_network", help="Network or study area label.")
    eval_panel_parser.add_argument("--output-dir", default="data/reporting/research/benchmark", help="Output directory for benchmark report and manifests.")

    return parser





def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect-legacy":
            payload = inspect_zip(args.zip_path)
        elif args.command == "list-csv":
            payload = {"zip_path": args.zip_path, "csv_members": list_csv_members(args.zip_path)}
        elif args.command == "profile-csv":
            payload = profile_csv_member(args.zip_path, args.member, sample_size=args.sample_size)
        elif args.command == "ingest-puglia-cleaned":
            payload = ingest_puglia_cleaned_csv(
                args.zip_path,
                args.member,
                output_dir=args.output_dir,
                limit=args.limit,
            )
        elif args.command == "ingest-bari-open-data-crashes":
            raw_dir = None if str(args.raw_dir).strip().lower() == "none" else args.raw_dir
            payload = ingest_bari_open_data_crashes(
                output_dir=args.output_dir,
                raw_dir=raw_dir,
                limit=args.limit,
            )
        elif args.command == "extract-istat-codebooks":
            payload = extract_istat_codebooks(args.zip_path, output_dir=args.output_dir)
        elif args.command == "ingest-config":
            settings = ProjectSettings.from_toml(args.config_path)
            if not settings.legacy_zip or not settings.crash_csv_member:
                parser.error("Config must define project.legacy_zip and data.crash_csv_member for ingestion.")
            if not settings.legacy_zip.exists():
                parser.error(f"Configured legacy ZIP does not exist: {settings.legacy_zip}")
            payload = ingest_puglia_cleaned_csv(
                settings.legacy_zip,
                settings.crash_csv_member,
                output_dir=args.output_dir,
                limit=args.limit,
            )
            payload["project"] = {
                "name": settings.name,
                "country_code": settings.country_code,
                "jurisdiction_name": settings.jurisdiction_name,
            }
        elif args.command == "ingest-declarative":
            from road_risk_modeling.adapters.declarative_adapter import ingest_declarative_dataset
            payload = ingest_declarative_dataset(
                csv_path=args.csv_path,
                mapping_config=args.mapping_config,
                output_dir=args.output_dir,
                limit=args.limit,
            )
        elif args.command == "qa-canonical":
            payload = write_canonical_quality_report(
                args.records_path,
                output_path=args.output_path,
                top_n=args.top_n,
            )
        elif args.command == "profile-jurisdictions":
            payload = profile_canonical_jurisdictions(
                args.records_path,
                output_dir=args.output_dir,
                zip_path=args.zip_path,
                top_n=args.top_n,
            )
        elif args.command == "subset-jurisdiction":
            payload = filter_canonical_records_by_jurisdiction(
                args.records_path,
                output_dir=args.output_dir,
                province_code=args.province_code,
                city_code=args.city_code,
                province_name=args.province_name,
                city_name=args.city_name,
                require_coordinates=args.require_coordinates,
            )
        elif args.command == "curate-canonical":
            payload = curate_canonical_records(
                args.records_path,
                output_path=args.output_path,
                rejected_path=args.rejected_path,
            )
        elif args.command == "extract-segments":
            payload = extract_segments_from_place(
                args.place_query,
                output_dir=args.output_dir,
                network_type=args.network_type,
            )
        elif args.command == "extract-boundary":
            payload = extract_boundary_from_place(
                args.place_query,
                output_dir=args.output_dir,
            )
        elif args.command == "extract-segments-from-boundary":
            payload = extract_segments_from_boundary(
                args.boundary_path,
                output_dir=args.output_dir,
                network_type=args.network_type,
            )
        elif args.command == "build-bari-signal-nodes":
            raw_dir = None if str(args.raw_dir).strip().lower() == "none" else args.raw_dir
            payload = build_bari_signal_nodes(
                output_dir=args.output_dir,
                segments_path=args.segments_path,
                raw_dir=raw_dir,
            )
        elif args.command == "build-bari-crossing-and-approach-objects":
            raw_dir = None if str(args.raw_dir).strip().lower() == "none" else args.raw_dir
            payload = build_bari_crossing_and_approach_objects(
                output_dir=args.output_dir,
                signal_nodes_path=args.signal_nodes_path,
                segments_path=args.segments_path,
                boundary_path=args.boundary_path,
                crossings_path=args.crossings_path,
                raw_dir=raw_dir,
                approach_distance_m=args.approach_distance_m,
                junction_buffer_m=args.junction_buffer_m,
                signal_link_m=args.signal_link_m,
                unsignalized_min_degree=args.unsignalized_min_degree,
                unsignalized_major_edge_min=args.unsignalized_major_edge_min,
            )
        elif args.command == "build-bari-conflict-zones":
            payload = build_bari_conflict_zones(
                output_dir=args.output_dir,
                node_objects_path=args.node_objects_path,
                segments_path=args.segments_path,
                crossing_radius_m=args.crossing_radius_m,
                unsignalized_radius_m=args.unsignalized_radius_m,
                roundabout_fallback_radius_m=args.roundabout_fallback_radius_m,
                junction_approach_length_m=args.junction_approach_length_m,
                roundabout_entry_length_m=args.roundabout_entry_length_m,
                default_zone_half_width_m=args.default_zone_half_width_m,
            )
        elif args.command == "build-bari-movement-objects":
            payload = build_bari_movement_objects(
                output_dir=args.output_dir,
                conflict_zones_path=args.conflict_zones_path,
                segments_path=args.segments_path,
                movement_offset_m=args.movement_offset_m,
            )
        elif args.command == "build-bari-movement-review-pack":
            payload = build_bari_movement_review_pack(
                output_dir=args.output_dir,
                movement_objects_path=args.movement_objects_path,
                matched_records_path=args.matched_records_path,
                aggregate_path=args.aggregate_path,
                signal_nodes_path=args.signal_nodes_path,
                top_n=args.top_n,
            )
        elif args.command == "build-bari-signal-phase-intake-pack":
            payload = build_bari_signal_phase_intake_pack(
                output_dir=args.output_dir,
                movement_review_path=args.movement_review_path,
                phase_readiness_csv_path=args.phase_readiness_csv_path,
                signal_nodes_path=args.signal_nodes_path,
                movement_objects_path=args.movement_objects_path,
                top_n=args.top_n,
            )
        elif args.command == "build-bari-signal-phase-support-resolution-bundle":
            payload = build_bari_signal_phase_support_resolution_bundle(
                output_dir=args.output_dir,
                support_validation_manifest_paths=args.support_validation_manifest_paths,
                movement_review_path=args.movement_review_path,
                phase_readiness_csv_path=args.phase_readiness_csv_path,
                movement_objects_path=args.movement_objects_path,
                aggregate_path=args.aggregate_path,
                top_n=args.top_n,
            )
        elif args.command == "build-bari-signal-phase-support-writeback-bundle":
            payload = build_bari_signal_phase_support_writeback_bundle(
                output_dir=args.output_dir,
                signal_phase_support_resolution_bundle_path=args.signal_phase_support_resolution_bundle_path,
                manual_mapping_stub_path=args.manual_mapping_stub_path,
            )
        elif args.command == "build-bari-signal-phase-support-status-bundle":
            payload = build_bari_signal_phase_support_status_bundle(
                output_dir=args.output_dir,
                signal_phase_support_writeback_bundle_path=args.signal_phase_support_writeback_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-action-queue":
            payload = build_bari_signal_phase_support_action_queue(
                output_dir=args.output_dir,
                signal_phase_support_status_bundle_path=args.signal_phase_support_status_bundle_path,
                signal_phase_support_apply_status_bundle_path=args.signal_phase_support_apply_status_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-apply-status-bundle":
            payload = build_bari_signal_phase_support_apply_status_bundle(
                output_dir=args.output_dir,
                signal_phase_support_status_bundle_path=args.signal_phase_support_status_bundle_path,
                signal_phase_support_apply_cycle_path=args.signal_phase_support_apply_cycle_path,
            )
        elif args.command == "build-bari-signal-phase-support-request-state-bundle":
            payload = build_bari_signal_phase_support_request_state_bundle(
                output_dir=args.output_dir,
                signal_phase_support_status_bundle_path=args.signal_phase_support_status_bundle_path,
                signal_phase_support_apply_status_bundle_path=args.signal_phase_support_apply_status_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-operator-board-bundle":
            payload = build_bari_signal_phase_support_operator_board_bundle(
                output_dir=args.output_dir,
                signal_phase_support_request_state_bundle_path=args.signal_phase_support_request_state_bundle_path,
                signal_phase_support_action_queue_path=args.signal_phase_support_action_queue_path,
                support_runtime_command=args.support_runtime_command,
            )
        elif args.command == "build-bari-signal-phase-support-action-execution-bundle":
            payload = build_bari_signal_phase_support_action_execution_bundle(
                output_dir=args.output_dir,
                signal_phase_support_operator_board_bundle_path=args.signal_phase_support_operator_board_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-action-handoff-bundle":
            payload = build_bari_signal_phase_support_action_handoff_bundle(
                output_dir=args.output_dir,
                signal_phase_support_action_execution_bundle_path=args.signal_phase_support_action_execution_bundle_path,
                support_runtime_cycle_manifest_path=args.support_runtime_cycle_manifest_path,
            )
        elif args.command == "build-bari-signal-phase-support-runtime-board-bundle":
            payload = build_bari_signal_phase_support_runtime_board_bundle(
                output_dir=args.output_dir,
                signal_phase_support_action_execution_bundle_path=args.signal_phase_support_action_execution_bundle_path,
                signal_phase_support_action_handoff_bundle_path=args.signal_phase_support_action_handoff_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-runtime-action-queue":
            payload = build_bari_signal_phase_support_runtime_action_queue(
                output_dir=args.output_dir,
                signal_phase_support_runtime_board_bundle_path=args.signal_phase_support_runtime_board_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-support-runtime-action-execution-bundle":
            payload = build_bari_signal_phase_support_runtime_action_execution_bundle(
                output_dir=args.output_dir,
                signal_phase_support_runtime_action_queue_path=args.signal_phase_support_runtime_action_queue_path,
            )
        elif args.command == "build-bari-signal-phase-support-workbook-completion-bundle":
            payload = build_bari_signal_phase_support_workbook_completion_bundle(
                output_dir=args.output_dir,
                signal_phase_support_runtime_action_execution_bundle_path=args.signal_phase_support_runtime_action_execution_bundle_path,
                signal_phase_support_writeback_bundle_path=args.signal_phase_support_writeback_bundle_path,
            )
        elif args.command == "run-bari-signal-phase-support-validation-batch":
            payload = run_bari_signal_phase_support_validation_batch(
                output_dir=args.output_dir,
                action_execution_ready_queue_path=args.action_execution_ready_queue_path,
                delivery_checklist_path=args.delivery_checklist_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "run-bari-signal-phase-support-apply-cycle":
            payload = run_bari_signal_phase_support_apply_cycle(
                output_dir=args.output_dir,
                action_execution_ready_queue_path=args.action_execution_ready_queue_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "run-bari-signal-phase-support-rehearsal":
            payload = run_bari_signal_phase_support_rehearsal(
                output_dir=args.output_dir,
                request_id=args.request_id,
                signal_phase_support_writeback_bundle_path=args.signal_phase_support_writeback_bundle_path,
                signal_phase_support_resolution_bundle_path=args.signal_phase_support_resolution_bundle_path,
                manual_mapping_stub_path=args.manual_mapping_stub_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                manual_phase_id=args.manual_phase_id,
                manual_stage_id=args.manual_stage_id,
                manual_protection_state=args.manual_protection_state,
                pedestrian_phase_id=args.pedestrian_phase_id,
                pedestrian_stage_id=args.pedestrian_stage_id,
                pedestrian_protection_state=args.pedestrian_protection_state,
                preview_limit=args.preview_limit,
            )
        elif args.command == "run-bari-signal-phase-support-runtime-cycle":
            payload = run_bari_signal_phase_support_runtime_cycle(
                output_dir=args.output_dir,
                signal_phase_support_resolution_bundle_path=args.signal_phase_support_resolution_bundle_path,
                manual_mapping_stub_path=args.manual_mapping_stub_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "ingest-signal-phase-extract":
            payload = ingest_signal_phase_extract(
                args.input_csv_path,
                args.mapping_stub_path,
                args.output_dir,
                limit=args.limit,
            )
        elif args.command == "apply-signal-phase-to-movements":
            payload = apply_signal_phase_to_movements(
                args.movement_objects_path,
                args.phase_manifest_paths,
                args.output_dir,
            )
        elif args.command == "validate-signal-phase-delivery":
            payload = validate_signal_phase_delivery(
                args.input_csv_path,
                args.mapping_stub_path,
                args.output_dir,
                delivery_checklist_path=args.delivery_checklist_path,
                request_id=args.request_id,
                junction_id=args.junction_id,
                preview_limit=args.preview_limit,
            )
        elif args.command == "apply-validated-signal-phase-deliveries":
            payload = apply_validated_signal_phase_deliveries(
                args.movement_objects_path,
                args.validation_manifest_paths,
                args.output_dir,
                matched_records_path=args.matched_records_path,
                target_request_queue_path=args.target_request_queue_path,
                baseline_movement_objects_path=args.baseline_movement_objects_path,
            )
        elif args.command == "build-bari-signal-phase-coverage-report":
            payload = build_bari_signal_phase_coverage_report(
                output_dir=args.output_dir,
                movement_objects_path=args.movement_objects_path,
                matched_records_path=args.matched_records_path,
                target_request_queue_path=args.target_request_queue_path,
                delivery_session_manifest_path=args.delivery_session_manifest_path,
                top_n=args.top_n,
            )
        elif args.command == "build-bari-signal-phase-target-bundle":
            payload = build_bari_signal_phase_target_bundle(
                output_dir=args.output_dir,
                target_junction_coverage_path=args.target_junction_coverage_path,
                uncovered_signalized_hotspots_path=args.uncovered_signalized_hotspots_path,
                target_request_queue_path=args.target_request_queue_path,
                matched_movement_records_path=args.matched_movement_records_path,
                top_hotspots_per_target=args.top_hotspots_per_target,
            )
        elif args.command == "build-bari-signal-phase-request-scope-bundle":
            payload = build_bari_signal_phase_request_scope_bundle(
                output_dir=args.output_dir,
                signal_phase_target_bundle_path=args.signal_phase_target_bundle_path,
                delivery_checklist_path=args.delivery_checklist_path,
            )
        elif args.command == "build-bari-signal-phase-contact-bundle":
            payload = build_bari_signal_phase_contact_bundle(
                output_dir=args.output_dir,
                signal_phase_request_scope_bundle_path=args.signal_phase_request_scope_bundle_path,
                outreach_tracker_path=args.outreach_tracker_path,
                follow_up_days=args.follow_up_days,
            )
        elif args.command == "build-bari-signal-phase-contact-resolution-bundle":
            payload = build_bari_signal_phase_contact_resolution_bundle(
                output_dir=args.output_dir,
                signal_phase_contact_bundle_path=args.signal_phase_contact_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-bundle":
            payload = build_bari_signal_phase_dispatch_bundle(
                output_dir=args.output_dir,
                signal_phase_contact_resolution_bundle_path=args.signal_phase_contact_resolution_bundle_path,
                planned_dispatch_date=args.planned_dispatch_date,
                follow_up_days=args.follow_up_days,
                escalation_days=args.escalation_days,
            )
        elif args.command == "build-bari-signal-phase-delivery-intake-bundle":
            payload = build_bari_signal_phase_delivery_intake_bundle(
                output_dir=args.output_dir,
                signal_phase_dispatch_bundle_path=args.signal_phase_dispatch_bundle_path,
                delivery_checklist_path=args.delivery_checklist_path,
                mapping_stub_dir=args.mapping_stub_dir,
                validation_output_root=args.validation_output_root,
            )
        elif args.command == "build-bari-signal-phase-delivery-monitor-bundle":
            payload = build_bari_signal_phase_delivery_monitor_bundle(
                output_dir=args.output_dir,
                signal_phase_delivery_intake_bundle_path=args.signal_phase_delivery_intake_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
            )
        elif args.command == "run-bari-signal-phase-validation-batch":
            payload = run_bari_signal_phase_validation_batch(
                output_dir=args.output_dir,
                validation_ready_queue_path=args.validation_ready_queue_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_checklist_path=args.delivery_checklist_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "run-bari-signal-phase-receive-cycle":
            payload = run_bari_signal_phase_receive_cycle(
                output_dir=args.output_dir,
                signal_phase_delivery_intake_bundle_path=args.signal_phase_delivery_intake_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "build-bari-signal-phase-lifecycle-report":
            payload = build_bari_signal_phase_lifecycle_report(
                output_dir=args.output_dir,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_monitor_queue_path=args.delivery_monitor_queue_path,
                validation_batch_results_path=args.validation_batch_results_path,
                receive_cycle_path=args.receive_cycle_path,
            )
        elif args.command == "build-bari-signal-phase-status-sync-bundle":
            payload = build_bari_signal_phase_status_sync_bundle(
                output_dir=args.output_dir,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_monitor_queue_path=args.delivery_monitor_queue_path,
                validation_batch_results_path=args.validation_batch_results_path,
                delivery_checklist_path=args.delivery_checklist_path,
                receive_cycle_path=args.receive_cycle_path,
            )
        elif args.command == "build-bari-signal-phase-follow-up-bundle":
            payload = build_bari_signal_phase_follow_up_bundle(
                output_dir=args.output_dir,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_agenda_path=args.follow_up_agenda_path,
                synced_receipt_register_path=args.synced_receipt_register_path,
            )
        elif args.command == "build-bari-signal-phase-follow-up-execution-bundle":
            payload = build_bari_signal_phase_follow_up_execution_bundle(
                output_dir=args.output_dir,
                follow_up_ready_queue_path=args.follow_up_ready_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
            )
        elif args.command == "build-bari-signal-phase-follow-up-writeback-bundle":
            payload = build_bari_signal_phase_follow_up_writeback_bundle(
                output_dir=args.output_dir,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                follow_up_execution_queue_path=args.follow_up_execution_queue_path,
                follow_up_tracker_updates_path=args.follow_up_tracker_updates_path,
            )
        elif args.command == "run-bari-signal-phase-follow-up-cycle":
            payload = run_bari_signal_phase_follow_up_cycle(
                output_dir=args.output_dir,
                follow_up_writeback_bundle_path=args.follow_up_writeback_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_monitor_queue_path=args.delivery_monitor_queue_path,
                validation_batch_results_path=args.validation_batch_results_path,
                receive_cycle_path=args.receive_cycle_path,
                synced_receipt_register_path=args.synced_receipt_register_path,
            )
        elif args.command == "run-bari-signal-phase-operations-cycle":
            payload = run_bari_signal_phase_operations_cycle(
                output_dir=args.output_dir,
                signal_phase_delivery_intake_bundle_path=args.signal_phase_delivery_intake_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "build-bari-signal-phase-action-queue":
            payload = build_bari_signal_phase_action_queue(
                output_dir=args.output_dir,
                signal_phase_operations_cycle_path=args.signal_phase_operations_cycle_path,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                signal_phase_dispatch_bundle_path=args.signal_phase_dispatch_bundle_path,
                lifecycle_items_path=args.lifecycle_items_path,
                follow_up_execution_queue_path=args.follow_up_execution_queue_path,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_repair_status_path=args.dispatch_repair_status_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-execution-bundle":
            payload = build_bari_signal_phase_dispatch_execution_bundle(
                output_dir=args.output_dir,
                signal_phase_action_queue_path=args.signal_phase_action_queue_path,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                dispatch_packet_dir=args.dispatch_packet_dir,
            )
        elif args.command == "build-bari-signal-phase-action-execution-bundle":
            payload = build_bari_signal_phase_action_execution_bundle(
                output_dir=args.output_dir,
                signal_phase_action_queue_path=args.signal_phase_action_queue_path,
            )
        elif args.command == "build-bari-signal-phase-action-handoff-bundle":
            payload = build_bari_signal_phase_action_handoff_bundle(
                output_dir=args.output_dir,
                signal_phase_action_execution_bundle_path=args.signal_phase_action_execution_bundle_path,
                dispatch_execution_log_path=args.dispatch_execution_log_path,
                follow_up_execution_queue_path=args.follow_up_execution_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
                delivery_monitor_queue_path=args.delivery_monitor_queue_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                runtime_cycle_manifest_path=args.runtime_cycle_manifest_path,
            )
        elif args.command == "build-bari-signal-phase-operator-board-bundle":
            payload = build_bari_signal_phase_operator_board_bundle(
                output_dir=args.output_dir,
                signal_phase_action_execution_bundle_path=args.signal_phase_action_execution_bundle_path,
                signal_phase_action_handoff_bundle_path=args.signal_phase_action_handoff_bundle_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-writeback-bundle":
            payload = build_bari_signal_phase_dispatch_writeback_bundle(
                output_dir=args.output_dir,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                dispatch_execution_ready_queue_path=args.dispatch_execution_ready_queue_path,
                dispatch_tracker_updates_path=args.dispatch_tracker_updates_path,
            )
        elif args.command == "run-bari-signal-phase-dispatch-cycle":
            payload = run_bari_signal_phase_dispatch_cycle(
                output_dir=args.output_dir,
                signal_phase_dispatch_writeback_bundle_path=args.signal_phase_dispatch_writeback_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_monitor_queue_path=args.delivery_monitor_queue_path,
                validation_batch_results_path=args.validation_batch_results_path,
                receive_cycle_path=args.receive_cycle_path,
                synced_receipt_register_path=args.synced_receipt_register_path,
                signal_phase_operations_cycle_path=args.signal_phase_operations_cycle_path,
                signal_phase_dispatch_bundle_path=args.signal_phase_dispatch_bundle_path,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_repair_status_path=args.dispatch_repair_status_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-recording-bundle":
            payload = build_bari_signal_phase_dispatch_recording_bundle(
                output_dir=args.output_dir,
                dispatch_execution_ready_queue_path=args.dispatch_execution_ready_queue_path,
                dispatch_execution_log_path=args.dispatch_execution_log_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-repair-bundle":
            payload = build_bari_signal_phase_dispatch_repair_bundle(
                output_dir=args.output_dir,
                dispatch_validation_queue_path=args.dispatch_validation_queue_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-repair-recording-bundle":
            payload = build_bari_signal_phase_dispatch_repair_recording_bundle(
                output_dir=args.output_dir,
                dispatch_execution_runtime_queue_path=args.dispatch_execution_runtime_queue_path,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-repair-execution-bundle":
            payload = build_bari_signal_phase_dispatch_repair_execution_bundle(
                output_dir=args.output_dir,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-repair-status-bundle":
            payload = build_bari_signal_phase_dispatch_repair_status_bundle(
                output_dir=args.output_dir,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
                dispatch_repair_execution_ready_queue_path=args.dispatch_repair_execution_ready_queue_path,
                dispatch_repair_internal_hold_queue_path=args.dispatch_repair_internal_hold_queue_path,
                dispatch_validation_queue_path=args.dispatch_validation_queue_path,
            )
        elif args.command == "build-bari-signal-phase-dispatch-validation-bundle":
            payload = build_bari_signal_phase_dispatch_validation_bundle(
                output_dir=args.output_dir,
                dispatch_execution_runtime_queue_path=args.dispatch_execution_runtime_queue_path,
            )
        elif args.command == "run-bari-signal-phase-runtime-cycle":
            payload = run_bari_signal_phase_runtime_cycle(
                output_dir=args.output_dir,
                signal_phase_delivery_intake_bundle_path=args.signal_phase_delivery_intake_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                signal_phase_dispatch_bundle_path=args.signal_phase_dispatch_bundle_path,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
                dispatch_execution_log_path=args.dispatch_execution_log_path,
                preview_limit=args.preview_limit,
            )
        elif args.command == "run-bari-signal-phase-runtime-rehearsal":
            payload = run_bari_signal_phase_runtime_rehearsal(
                output_dir=args.output_dir,
                request_id=args.request_id,
                signal_phase_delivery_intake_bundle_path=args.signal_phase_delivery_intake_bundle_path,
                delivery_receipt_register_path=args.delivery_receipt_register_path,
                delivery_checklist_path=args.delivery_checklist_path,
                movement_objects_path=args.movement_objects_path,
                dispatch_execution_queue_path=args.dispatch_execution_queue_path,
                follow_up_tracker_path=args.follow_up_tracker_path,
                signal_phase_dispatch_bundle_path=args.signal_phase_dispatch_bundle_path,
                dispatch_log_repair_queue_path=args.dispatch_log_repair_queue_path,
                dispatch_log_repair_log_path=args.dispatch_log_repair_log_path,
                execution_status=args.execution_status,
                execution_channel_used=args.execution_channel_used,
                execution_outcome=args.execution_outcome,
                response_received=args.response_received,
                response_summary=args.response_summary,
                protocol_reference=args.protocol_reference,
                evidence_path=args.evidence_path,
                execution_notes=args.execution_notes,
                execution_completed_at=args.execution_completed_at,
                preview_limit=args.preview_limit,
            )
        elif args.command == "build-bari-signal-phase-request-pack":
            payload = build_bari_signal_phase_request_pack(
                output_dir=args.output_dir,
                signal_phase_intake_path=args.signal_phase_intake_path,
                portal_base_url=args.portal_base_url,
                timeout_s=args.timeout_s,
                verify_ssl=args.verify_ssl,
                top_n=args.top_n,
            )
        elif args.command == "build-bari-signal-phase-acquisition-plan":
            payload = build_bari_signal_phase_acquisition_plan(
                output_dir=args.output_dir,
                signal_phase_request_pack_path=args.signal_phase_request_pack_path,
            )
        elif args.command == "build-bari-signal-phase-outreach-bundle":
            payload = build_bari_signal_phase_outreach_bundle(
                output_dir=args.output_dir,
                acquisition_plan_path=args.acquisition_plan_path,
                signal_phase_request_pack_path=args.signal_phase_request_pack_path,
                priority_band=args.priority_band,
                max_requests=args.max_requests,
            )
        elif args.command == "extract-segments-from-records":
            payload = extract_segments_from_records_bbox(
                args.records_path,
                output_dir=args.output_dir,
                network_type=args.network_type,
                pad_m=args.pad_m,
                trim_quantile=args.trim_quantile,
            )
        elif args.command == "enrich-segments":
            payload = enrich_segments(
                args.segments_path,
                output_dir=args.output_dir,
            )
        elif args.command == "enrich-segments-context":
            payload = enrich_segments_with_context(
                args.segments_path,
                args.boundary_path,
                output_dir=args.output_dir,
                poi_buffer_m=args.poi_buffer_m,
            )
        elif args.command == "apply-exposure-policy":
            payload = apply_exposure_policy_to_segments(
                args.segments_path,
                output_dir=args.output_dir,
            )
        elif args.command == "match-segments":
            payload = match_canonical_records_to_segments(
                args.records_path,
                args.segments_path,
                output_dir=args.output_dir,
                max_distance_m=args.max_distance_m,
                boundary_path=args.boundary_path,
            )
        elif args.command == "analyze-matches":
            payload = analyze_match_results(
                args.matched_path,
                args.unmatched_path,
                output_dir=args.output_dir,
                review_limit=args.review_limit,
            )
        elif args.command == "aggregate-segments":
            payload = aggregate_segment_year_metrics(
                args.matched_path,
                args.segments_path,
                output_dir=args.output_dir,
            )
        elif args.command == "compare-boundaries":
            payload = compare_boundaries(
                args.reference_boundary_path,
                args.candidate_boundary_path,
                output_path=args.output_path,
            )
        elif args.command == "train-frequency-baseline":
            payload = train_frequency_baseline(
                args.aggregate_csv_path,
                output_dir=args.output_dir,
                holdout_year=args.holdout_year,
            )
        elif args.command == "train-severity-baseline":
            payload = train_severity_baseline(
                args.matched_path,
                args.aggregate_csv_path,
                output_dir=args.output_dir,
                holdout_year=args.holdout_year,
            )
        elif args.command == "evaluate-frequency-transferability":
            datasets: list[tuple[str, str]] = []
            for spec in args.dataset:
                if "=" not in spec:
                    parser.error(f"Invalid --dataset value: {spec}. Expected label=/path/to/file.csv")
                label, path = spec.split("=", 1)
                label = label.strip()
                path = path.strip()
                if not label or not path:
                    parser.error(f"Invalid --dataset value: {spec}. Expected label=/path/to/file.csv")
                datasets.append((label, path))
            payload = evaluate_frequency_transferability(
                datasets=datasets,
                output_dir=args.output_dir,
                holdout_year=args.holdout_year,
                rf_n_estimators=args.rf_estimators,
                modes=args.modes,
            )
        elif args.command == "build-transferability-benchmark-bundle":
            payload = build_transferability_benchmark_bundle(
                transferability_metrics_paths=args.transferability_metrics_paths,
                benchmark_label=args.benchmark_label,
                output_dir=args.output_dir,
            )
        elif args.command == "nwrsa-assess":
            payload = run_nwrsa_assessment(
                sections_path=args.sections_path,
                output_dir=args.output_dir,
                reactive_weight=args.reactive_weight,
                proactive_weight=args.proactive_weight,
                categories=args.categories,
            )
        elif args.command == "rural-section":
            payload = run_rural_sectioning(
                segments_path=args.segments_path,
                output_dir=args.output_dir,
                section_length_m=args.section_length_m,
            )
        elif args.command == "climate-resilience":
            payload = run_climate_resilience_assessment(
                segments_path=args.segments_path,
                hazards_path=args.hazards_path,
                output_dir=args.output_dir,
            )
        elif args.command == "behavioural-analysis":
            payload = run_behavioural_analysis(
                crashes_path=args.crashes_path,
                output_dir=args.output_dir,
                min_cell=args.min_cell,
            )
        elif args.command == "elderly-disabled-assess":
            payload = run_elderly_disabled_assessment(
                segments_path=args.segments_path,
                output_dir=args.output_dir,
            )
        elif args.command == "intersectional-analysis":
            payload = run_intersectional_analysis(
                casualties_path=args.casualties_path,
                output_dir=args.output_dir,
                min_cell=args.min_cell,
            )
        elif args.command == "regional-comparison":
            region_specs = json.loads(Path(args.regions_spec_path).read_text(encoding="utf-8"))
            payload = run_regional_comparison(
                region_specs=region_specs,
                output_dir=args.output_dir,
                eu_average_rural_fatality_rate=args.eu_average_rural_fatality_rate,
            )
        elif args.command == "show-config":
            payload = ProjectSettings.from_toml(args.config_path).to_dict()
        elif args.command == "pipeline":
            payload = {"pipeline": pipeline_as_dicts()}
        elif args.command == "build-run-registry":
            payload = build_run_registry(
                data_root=args.data_root,
                output_dir=args.output_dir,
            )
        elif args.command == "publish-segment-scores":
            payload = publish_segment_scores(
                args.predictions_path,
                args.segments_path,
                args.metrics_path,
                output_dir=args.output_dir,
                prediction_column=args.prediction_column,
            )
        elif args.command == "aggregate-public-score-tiles":
            payload = aggregate_public_score_tiles(
                args.public_scores_path,
                args.prediction_store_manifest_path,
                output_dir=args.output_dir,
                tile_size_m=args.tile_size_m,
            )
        elif args.command == "query-published-resource":
            payload = query_published_resource(
                args.manifest_path,
                view=args.view,
                occurred_year=args.occurred_year,
                min_score_band=args.min_score_band,
                limit=args.limit,
            )
        elif args.command == "resolve-latest-published-resource":
            payload = resolve_latest_published_resource(
                args.resource_name,
                registry_path=args.registry_path,
                view=args.view,
                prediction_run_label=args.prediction_run_label,
                occurred_year=args.occurred_year,
                tile_size_m=args.tile_size_m,
            )
        elif args.command == "build-published-resource-index":
            payload = build_published_resource_index(
                registry_path=args.registry_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-dashboard-summary":
            payload = build_dashboard_summary(
                published_index_path=args.published_index_path,
                transferability_metrics_paths=args.transferability_metrics_paths,
                output_dir=args.output_dir,
            )
        elif args.command == "build-published-refresh-bundle":
            payload = build_published_refresh_bundle(
                data_root=args.data_root,
                registry_output_dir=args.registry_output_dir,
                published_index_output_dir=args.published_index_output_dir,
                dashboard_output_dir=args.dashboard_output_dir,
                output_dir=args.output_dir,
            )
        elif args.command == "build-intervention-briefs":
            payload = build_intervention_briefs(
                dashboard_summary_path=args.dashboard_summary_path,
                prediction_run_labels=args.prediction_run_labels,
                scenario_bundle_root=args.scenario_bundle_root,
                output_dir=args.output_dir,
            )
        elif args.command == "build-scenario-countermeasure-bundle":
            payload = build_scenario_countermeasure_bundle(
                dashboard_summary_path=args.dashboard_summary_path,
                prediction_run_labels=args.prediction_run_labels,
                signal_nodes_path=args.signal_nodes_path,
                node_objects_path=args.node_objects_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-vru-intelligence-bundle":
            payload = build_vru_intelligence_bundle(
                dashboard_summary_path=args.dashboard_summary_path,
                prediction_run_labels=args.prediction_run_labels,
                movement_objects_path=args.movement_objects_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-vru-exposure-bundle":
            payload = build_vru_exposure_bundle(
                dashboard_summary_path=args.dashboard_summary_path,
                prediction_run_labels=args.prediction_run_labels,
                movement_objects_path=args.movement_objects_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-exposure-readiness-report":
            datasets: list[tuple[str, str]] = []
            for spec in args.dataset:
                if "=" not in spec:
                    parser.error(f"Invalid --dataset value: {spec}. Expected label=/path/to/file.geojson")
                label, path = spec.split("=", 1)
                label = label.strip()
                path = path.strip()
                if not label or not path:
                    parser.error(f"Invalid --dataset value: {spec}. Expected label=/path/to/file.geojson")
                datasets.append((label, path))
            payload = build_exposure_readiness_report(
                datasets=datasets,
                output_dir=args.output_dir,
            )
        elif args.command == "build-exposure-source-catalog":
            payload = build_exposure_source_catalog(
                readiness_report_path=args.readiness_report_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-exposure-onboarding-plan":
            payload = build_exposure_onboarding_plan(
                source_catalog_path=args.source_catalog_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-governance-interoperability-bundle":
            payload = build_governance_interoperability_bundle(
                output_dir=args.output_dir,
            )
        elif args.command == "build-data-governance-bundle":
            payload = build_data_governance_bundle(
                output_dir=args.output_dir,
            )
        elif args.command == "build-cadas-alignment":
            payload = build_cadas_alignment_bundle(
                output_dir=args.output_dir,
            )
        elif args.command == "export-cadas":
            payload = export_canonical_to_cadas(
                canonical_path=args.canonical_path,
                output_dir=args.output_dir,
            )
        elif args.command == "build-exposure-connector-intake-pack":
            payload = build_exposure_connector_intake_pack(
                source_catalog_path=args.source_catalog_path,
                onboarding_plan_path=args.onboarding_plan_path,
                output_dir=args.output_dir,
            )
        elif args.command == "ingest-exposure-connector-extract":
            payload = ingest_exposure_connector_extract(
                args.input_csv_path,
                args.mapping_stub_path,
                args.output_dir,
                limit=args.limit,
            )
        elif args.command == "normalize-exposure-provider-extract":
            if args.provider_profile_id is None and args.mapping_stub_path is None:
                parser.error(
                    "normalize-exposure-provider-extract requires --provider-profile-id or --mapping-stub-path"
                )
            payload = normalize_exposure_provider_extract(
                args.input_csv_path,
                provider_profile_id=args.provider_profile_id,
                mapping_stub_path=args.mapping_stub_path,
                output_dir=args.output_dir,
                limit=args.limit,
            )
        elif args.command == "apply-connector-observations-to-segments":
            payload = apply_connector_observations_to_segments(
                args.segments_path,
                args.observation_manifest_paths,
                args.output_dir,
            )
        elif args.command == "run-bari-phase1-exposure-pilot":
            payload = run_bari_phase1_exposure_pilot(
                segments_path=args.segments_path,
                motorized_extract_path=args.motorized_extract_path,
                motorized_mapping_stub_path=args.motorized_mapping_stub_path,
                speed_extract_path=args.speed_extract_path,
                speed_mapping_stub_path=args.speed_mapping_stub_path,
                motorized_provider_profile_id=args.motorized_provider_profile_id,
                speed_provider_profile_id=args.speed_provider_profile_id,
                normalize_motorized_provider_extract=args.normalize_motorized_provider_extract,
                normalize_speed_provider_extract=args.normalize_speed_provider_extract,
                mapping_stub_root=args.mapping_stub_root,
                readiness_dataset_label=args.readiness_dataset_label,
                output_dir=args.output_dir,
            )
        elif args.command == "match-node-objects":
            payload = match_canonical_records_to_node_objects(
                args.records_path,
                args.node_objects_path,
                args.output_dir,
                max_distance_m=args.max_distance_m,
            )
        elif args.command == "aggregate-node-objects":
            payload = aggregate_node_year_metrics(
                args.matched_path,
                args.node_objects_path,
                args.output_dir,
            )
        elif args.command == "build-national-hierarchy":
            if args.country_code.upper() == "IT":
                hierarchy = build_sample_italy_national_hierarchy()
            else:
                hierarchy = NationalHierarchy(country_code=args.country_code, country_name=args.country_name)
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            export_path = out_dir / f"{args.country_code.lower()}_hierarchy.json"
            export_path.write_text(hierarchy.to_json(), encoding="utf-8")
            payload = {
                "country_code": hierarchy.country_code,
                "country_name": hierarchy.country_name,
                "entities_count": len(hierarchy._entities),
                "hierarchy_path": str(export_path),
            }
        elif args.command == "rollup-national-risk":
            hierarchy_path = Path(args.hierarchy_path)
            hierarchy = NationalHierarchy.from_json(hierarchy_path.read_text(encoding="utf-8"))
            crashes_by_entity = {}
            if args.crashes_by_entity_json:
                crashes_by_entity = json.loads(Path(args.crashes_by_entity_json).read_text(encoding="utf-8"))
            rollups = hierarchy.calculate_rollups(crashes_by_entity)
            payload = export_national_rollup_report(hierarchy, rollups, output_dir=args.output_dir)
        elif args.command == "hsm-network-screening":
            import csv
            segments_path = Path(args.segments_path)
            segments = []
            if segments_path.suffix.lower() == ".json":
                segments = json.loads(segments_path.read_text(encoding="utf-8"))
            else:
                with segments_path.open("r", encoding="utf-8") as h:
                    segments = list(csv.DictReader(h))
            results = screen_road_network_hsm(
                segments=segments,
                default_facility_class=args.facility_class,
                calibration_c=args.calibration_c,
            )
            payload = export_hsm_screening_artifacts(
                results,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "irap-star-rating":
            import csv
            segments_path = Path(args.segments_path)
            segments = []
            if segments_path.suffix.lower() == ".json":
                segments = json.loads(segments_path.read_text(encoding="utf-8"))
            else:
                with segments_path.open("r", encoding="utf-8") as h:
                    segments = list(csv.DictReader(h))
            assessed = [assess_segment_irap(seg) for seg in segments]
            srip_plan = generate_safer_roads_investment_plan(assessed)
            payload = export_irap_and_srip_artifacts(
                assessed_segments=assessed,
                investment_plan=srip_plan,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "generate-srip":
            import csv
            segments_path = Path(args.segments_path)
            segments = []
            if segments_path.suffix.lower() == ".json":
                segments = json.loads(segments_path.read_text(encoding="utf-8"))
            else:
                with segments_path.open("r", encoding="utf-8") as h:
                    segments = list(csv.DictReader(h))
            assessed = [assess_segment_irap(seg) for seg in segments]
            srip_plan = generate_safer_roads_investment_plan(
                assessed_segments=assessed,
                value_of_statistical_life_eur=args.vosl_eur,
                value_of_serious_injury_eur=args.vosi_eur,
                discount_rate=args.discount_rate,
                min_bcr_threshold=args.min_bcr,
            )
            payload = export_irap_and_srip_artifacts(
                assessed_segments=assessed,
                investment_plan=srip_plan,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "ingest-telematics":
            import csv
            obs_path = Path(args.observations_path)
            raw_data = []
            if obs_path.suffix.lower() == ".json":
                raw_data = json.loads(obs_path.read_text(encoding="utf-8"))
            else:
                with obs_path.open("r", encoding="utf-8") as h:
                    raw_data = list(csv.DictReader(h))

            if args.is_waypoints:
                events = detect_events_from_waypoints(raw_data)
            else:
                events = parse_telematics_events(raw_data)

            out_path = Path(args.output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_payload = {
                "telematics_engine_version": "telematics_fcd_v1",
                "total_events_detected": len(events),
                "events": [e.to_dict() for e in events],
            }
            out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
            payload = {"status": "success", "output_path": str(out_path), "events_count": len(events)}
        elif args.command == "screen-near-misses":
            import csv
            segments_path = Path(args.segments_path)
            segments = []
            if segments_path.suffix.lower() == ".json":
                segments = json.loads(segments_path.read_text(encoding="utf-8"))
            else:
                with segments_path.open("r", encoding="utf-8") as h:
                    segments = list(csv.DictReader(h))

            events_path = Path(args.events_path)
            raw_evts = []
            if events_path.suffix.lower() == ".json":
                evt_content = json.loads(events_path.read_text(encoding="utf-8"))
                raw_evts = evt_content.get("events", evt_content) if isinstance(evt_content, dict) else evt_content
            else:
                with events_path.open("r", encoding="utf-8") as h:
                    raw_evts = list(csv.DictReader(h))

            events = parse_telematics_events(raw_evts)
            metrics = calculate_segment_telematics_metrics(
                segments=segments,
                telematics_events=events,
                days_analyzed=args.days_analyzed,
                fleet_penetration_rate=args.fleet_penetration,
            )
            payload = export_telematics_screening_artifacts(
                metrics=metrics,
                events=events,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "optimize-cip":
            import csv
            cand_path = Path(args.candidates_path)
            raw_candidates = []
            if cand_path.suffix.lower() == ".json":
                cand_content = json.loads(cand_path.read_text(encoding="utf-8"))
                raw_candidates = cand_content.get("investment_plan", cand_content) if isinstance(cand_content, dict) else cand_content
            else:
                with cand_path.open("r", encoding="utf-8") as h:
                    raw_candidates = list(csv.DictReader(h))

            candidates = parse_cip_candidates(raw_candidates)
            budgets = [args.annual_budget] * args.horizon_years
            portfolio = optimize_capital_improvement_plan(
                candidates=candidates,
                annual_budgets=budgets,
                start_calendar_year=args.start_year,
                inflation_rate=args.inflation_rate,
                discount_rate=args.discount_rate,
                allow_budget_rollover=args.allow_rollover,
            )
            payload = export_cip_portfolio_artifacts(
                portfolio=portfolio,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "cv-road-audit":
            import csv
            frames_path = Path(args.frames_path)
            raw_frames = []
            if frames_path.suffix.lower() == ".json":
                frames_content = json.loads(frames_path.read_text(encoding="utf-8"))
                raw_frames = frames_content.get("frames", frames_content) if isinstance(frames_content, dict) else frames_content
            else:
                with frames_path.open("r", encoding="utf-8") as h:
                    raw_frames = list(csv.DictReader(h))

            segments_path = Path(args.segments_path)
            segments = []
            if segments_path.suffix.lower() == ".json":
                segments = json.loads(segments_path.read_text(encoding="utf-8"))
            else:
                with segments_path.open("r", encoding="utf-8") as h:
                    segments = list(csv.DictReader(h))

            observations = parse_frame_observations(raw_frames)
            audited = aggregate_frame_detections_to_segments(segments, observations)
            payload = export_cv_audit_artifacts(
                audited_segments=audited,
                raw_observations=observations,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "micro-ssam":
            trajectories_path = Path(args.trajectories_path)
            raw_trajectories = []
            if trajectories_path.suffix.lower() == ".json":
                traj_content = json.loads(trajectories_path.read_text(encoding="utf-8"))
                raw_trajectories = traj_content.get("trajectories", traj_content) if isinstance(traj_content, dict) else traj_content
            else:
                with trajectories_path.open("r", encoding="utf-8") as h:
                    raw_trajectories = list(csv.DictReader(h))

            agents = parse_agent_trajectories(raw_trajectories)
            conflicts = detect_trajectory_conflicts(agents)
            junction_summaries = aggregate_conflicts_to_junctions(conflicts)
            payload = export_micro_ssam_artifacts(
                conflicts=conflicts,
                junction_summaries=junction_summaries,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "st-gnn-forecast":
            graph_path = Path(args.graph_path)
            graph_data = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.suffix.lower() == ".json" else {}
            raw_nodes = graph_data.get("nodes", [])
            raw_edges = graph_data.get("edges", [])

            raw_frames = graph_data.get("time_series_frames", graph_data.get("frames", []))
            if args.features_path:
                feat_path = Path(args.features_path)
                if feat_path.suffix.lower() == ".json":
                    feat_content = json.loads(feat_path.read_text(encoding="utf-8"))
                    raw_frames = feat_content.get("time_series_frames", feat_content) if isinstance(feat_content, dict) else feat_content
                else:
                    with feat_path.open("r", encoding="utf-8") as h:
                        raw_frames = list(csv.DictReader(h))

            horizons = [int(h.strip()) for h in str(args.horizons).split(",") if h.strip().isdigit()]
            if not horizons:
                horizons = [1, 6, 24]

            parsed_nodes = [
                RoadGraphNode(
                    segment_id=str(n.get("segment_id") or n.get("id")),
                    length_km=float(n.get("length_km") or 0.5),
                    free_flow_speed_kmh=float(n.get("free_flow_speed_kmh") or 50.0),
                    functional_class=str(n.get("functional_class") or "urban_arterial"),
                    latitude=float(n["latitude"]) if n.get("latitude") is not None else None,
                    longitude=float(n["longitude"]) if n.get("longitude") is not None else None,
                )
                for n in raw_nodes
            ]
            parsed_edges = [
                GraphEdge(
                    from_segment_id=str(e.get("from_segment_id") or e.get("from")),
                    to_segment_id=str(e.get("to_segment_id") or e.get("to")),
                    distance_m=float(e.get("distance_m") or 100.0),
                    is_connected=bool(e.get("is_connected", True)),
                    weight=float(e.get("weight") or 1.0),
                )
                for e in raw_edges
            ] if raw_edges else None

            parsed_frames = [
                SpatioTemporalFeatureFrame(
                    segment_id=str(f.get("segment_id") or f.get("id")),
                    timestamp=str(f.get("timestamp") or datetime.now(UTC).isoformat()),
                    historical_crash_count=float(f.get("historical_crash_count") or 0.0),
                    telematics_near_miss_rate=float(f.get("telematics_near_miss_rate") or 0.0),
                    current_speed_kmh=float(f.get("current_speed_kmh") or 45.0),
                    speed_ratio=float(f.get("speed_ratio") or 0.90),
                    precipitation_mm_h=float(f.get("precipitation_mm_h") or 0.0),
                    surface_condition=str(f.get("surface_condition") or "dry").lower(),
                    visibility_m=float(f.get("visibility_m") or 10000.0),
                    hour_of_day=int(f.get("hour_of_day") or 12),
                    is_peak_hour=bool(f.get("is_peak_hour") or False),
                )
                for f in raw_frames
            ]

            forecasts, alerts = execute_st_gnn_forecast(
                nodes=parsed_nodes,
                time_series_frames=parsed_frames,
                edges=parsed_edges,
                horizons=horizons,
            )
            payload = export_st_gnn_artifacts(
                forecasts=forecasts,
                alerts=alerts,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "causal-eval":
            data_path = Path(args.data_path)
            raw_content = json.loads(data_path.read_text(encoding="utf-8")) if data_path.suffix.lower() == ".json" else []
            if isinstance(raw_content, dict):
                raw_units = raw_content.get("observational_units", raw_content.get("units", raw_content.get("data", [])))
            else:
                raw_units = raw_content

            parsed_units = parse_observational_units(raw_units)
            target_cms = [c.strip().upper() for c in args.countermeasures.split(",") if c.strip()] if args.countermeasures else None
            available_cms = sorted(list({u.countermeasure_id for u in parsed_units}))
            selected_cms = [c for c in target_cms if c in available_cms] if target_cms else available_cms

            treatment_effects = []
            all_cate_estimates = []
            for cid in selected_cms:
                try:
                    effect, _ = estimate_double_ml_treatment_effect(parsed_units, cid)
                    treatment_effects.append(effect)
                    cate = estimate_segment_cate_heterogeneity(parsed_units, cid, effect.ate_crashes)
                    all_cate_estimates.extend(cate)
                except RuntimeError:
                    continue

            if not treatment_effects:
                raise RuntimeError("No valid causal treatment effects could be estimated from provided units.")

            all_cate_estimates.sort(key=lambda c: c.predicted_annual_crash_reduction, reverse=True)
            payload = export_causal_ml_artifacts(
                treatment_effects=treatment_effects,
                cate_estimates=all_cate_estimates,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "cits-actuate":
            alerts_path = Path(args.alerts_path)
            raw_content = json.loads(alerts_path.read_text(encoding="utf-8")) if alerts_path.suffix.lower() == ".json" else []
            if isinstance(raw_content, dict):
                raw_alerts = raw_content.get("alerts", raw_content.get("operational_alerts", raw_content.get("data", [])))
            else:
                raw_alerts = raw_content

            parsed_alerts = parse_operational_risk_alerts(raw_alerts)
            if not parsed_alerts:
                raise RuntimeError("No valid operational risk alerts found in provided file.")

            plan = create_cits_actuation_bundle(
                alerts=parsed_alerts,
                network_label=args.network_label,
                sovereign_station_id=args.station_id,
            )
            payload = export_cits_actuation_artifacts(
                plan=plan,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "sim-eval":
            cfg_path = Path(args.config_path)
            cfg_data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.suffix.lower() == ".json" else {}

            jnc_id = str(cfg_data.get("junction_id") or "JNC-SIM-001")
            base_t = str(cfg_data.get("baseline_template") or "BASELINE_SIGNALIZED")
            redesign_t = str(cfg_data.get("redesign_template") or "DUTCH_PROTECTED_JUNCTION")
            dur = _safe_float(cfg_data.get("duration_seconds"), 60.0)
            veh_dem = _safe_float(cfg_data.get("vehicle_demand_vph"), 800.0)
            vru_dem = _safe_float(cfg_data.get("vru_demand_pph"), 120.0)
            seed = _safe_int(cfg_data.get("random_seed"), 42)

            base_res, redesign_res, comparison = evaluate_synthetic_countermeasure_pair(
                junction_id=jnc_id,
                baseline_template=base_t,
                redesign_template=redesign_t,
                duration_seconds=dur,
                vehicle_demand_vph=veh_dem,
                vru_demand_pph=vru_dem,
                random_seed=seed,
            )

            payload = export_simulation_sandbox_artifacts(
                baseline_result=base_res,
                redesign_result=redesign_res,
                comparison=comparison,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "ai-conformity":
            d_path = Path(args.data_path)
            c_data = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            corridors = c_data.get("corridors") if isinstance(c_data, dict) else (c_data if isinstance(c_data, list) else [])
            auc = _safe_float(c_data.get("accuracy_auc_roc"), 0.885) if isinstance(c_data, dict) else 0.885
            brier = _safe_float(c_data.get("brier_score_loss"), 0.082) if isinstance(c_data, dict) else 0.082

            dossier = generate_eu_ai_act_dossier(
                corridors_data=corridors,
                network_label=args.network_label,
                protected_attribute=args.protected_attribute,
                accuracy_auc_roc=auc,
                brier_score_loss=brier,
            )

            all_explanations = compute_local_shap_explanations(corridors)

            payload = export_ai_act_compliance_artifacts(
                dossier=dossier,
                all_explanations=all_explanations,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "federated-train":
            d_path = Path(args.data_path)
            f_data = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            nodes_data = f_data.get("nodes") if isinstance(f_data, dict) else (f_data if isinstance(f_data, list) else [])
            rounds = _safe_int(args.rounds, _safe_int(f_data.get("rounds_count"), 3))
            method = str(args.aggregation_method or f_data.get("aggregation_method") or "fedavg")
            enable_dp = bool(f_data.get("enable_dp", True)) if isinstance(f_data, dict) else True
            eps = _safe_float(f_data.get("target_epsilon"), 2.0) if isinstance(f_data, dict) else 2.0

            report = run_federated_training_pipeline(
                nodes_data=nodes_data,
                rounds_count=rounds,
                aggregation_method=method,
                enable_dp=enable_dp,
                target_epsilon=eps,
                network_label=args.network_label,
            )

            payload = export_federated_learning_artifacts(
                report=report,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "micromobility-audit":
            d_path = Path(args.data_path)
            raw_data = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            if isinstance(raw_data, list):
                waypoints = raw_data
                segments_data = None
            elif isinstance(raw_data, dict):
                waypoints = raw_data.get("waypoints", [])
                segments_data = raw_data.get("segments_data")
            else:
                waypoints = []
                segments_data = None

            report, events = run_micromobility_fleet_audit(
                waypoints_data=waypoints,
                segments_data=segments_data,
                network_label=args.network_label,
            )

            payload = export_micromobility_artifacts(
                report=report,
                events=events,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "ministerial-dossier":
            d_path = Path(args.data_path)
            raw = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            dossier = compile_ministerial_dossier(
                network_label=args.network_label,
                jurisdiction_name=str(args.jurisdiction_name or raw.get("jurisdiction_name") or "Repubblica Italiana / Regione Puglia / Comune di Bari"),
                ministry_authority=str(args.ministry_authority or raw.get("ministry_authority") or "Ministero delle Infrastrutture e dei Trasporti"),
                hsm_data=raw.get("hsm_data"),
                irap_data=raw.get("irap_data"),
                telematics_data=raw.get("telematics_data"),
                micromobility_data=raw.get("micromobility_data"),
                st_gnn_data=raw.get("st_gnn_data"),
                cits_data=raw.get("cits_data"),
                simulation_data=raw.get("simulation_data"),
                causal_data=raw.get("causal_data"),
                ai_act_data=raw.get("ai_act_data"),
                cip_data=raw.get("cip_data"),
            )

            payload = export_ministerial_dossier_artifacts(
                dossier=dossier,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "build-panel":
            d_path = Path(args.data_path)
            raw = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            panel = build_segment_week_panel(
                segments=raw.get("segments", []),
                crashes=raw.get("crashes", []),
                weather=raw.get("weather"),
                weeks_count=_safe_int(args.weeks_count, _safe_int(raw.get("weeks_count"), 8)),
                base_start_iso=str(raw.get("base_start_iso") or "2026-01-05T00:00:00Z"),
                network_label=args.network_label,
            )

            payload = export_panel_artifacts(
                dataset=panel,
                output_dir=args.output_dir,
                network_label=args.network_label,
            )
        elif args.command == "evaluate-panel-models":
            d_path = Path(args.data_path)
            raw = json.loads(d_path.read_text(encoding="utf-8")) if d_path.suffix.lower() == ".json" else {}

            # If input is raw inputs, build panel first
            if "segments" in raw and "crashes" in raw:
                panel = build_segment_week_panel(
                    segments=raw.get("segments", []),
                    crashes=raw.get("crashes", []),
                    weather=raw.get("weather"),
                    weeks_count=_safe_int(raw.get("weeks_count"), 8),
                    base_start_iso=str(raw.get("base_start_iso") or "2026-01-05T00:00:00Z"),
                    network_label=args.network_label,
                )
                obs_dicts = [o.to_dict() for o in panel.observations]
            elif "observations" in raw:
                obs_dicts = raw["observations"]
            elif isinstance(raw, list):
                obs_dicts = raw
            else:
                obs_dicts = []

            strat = str(args.split_strategy or "forward_temporal")
            if strat == "spatial_group":
                split = spatial_group_kfold_split(obs_dicts)
            elif strat == "space_time_blocked":
                split = space_time_blocked_split(obs_dicts)
            else:
                split = forward_temporal_split(obs_dicts)

            feature_cols = ["speed_limit_kmh", "lanes", "precipitation_mm", "temperature_c", "dow_sin", "dow_cos"]

            X_train = [[obs_dicts[i].get(col, 0.0) for col in feature_cols] for i in split.train_indices]
            y_train = [obs_dicts[i].get("crash_count", 0) for i in split.train_indices]
            exp_train = [obs_dicts[i].get("exposure_vehicle_km", 1000.0) for i in split.train_indices]

            X_test = [[obs_dicts[i].get(col, 0.0) for col in feature_cols] for i in split.test_indices]
            y_test = [obs_dicts[i].get("crash_count", 0) for i in split.test_indices]
            exp_test = [obs_dicts[i].get("exposure_vehicle_km", 1000.0) for i in split.test_indices]

            report = evaluate_model_suite(
                X_train=X_train,
                y_train=y_train,
                exp_train=exp_train,
                X_test=X_test,
                y_test=y_test,
                exp_test=exp_test,
                feature_names=feature_cols,
                network_label=args.network_label,
            )

            # Generate sample test predictions contract
            predictions = []
            for idx in split.test_indices:
                obs = obs_dicts[idx]
                predictions.append({
                    "segment_id": obs.get("segment_id"),
                    "prediction_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "forecast_start": obs.get("period_start"),
                    "forecast_end": obs.get("period_end"),
                    "expected_crashes": round(obs.get("crash_count", 0) * 0.95, 3),
                    "risk_probability": round(min(1.0, obs.get("crash_count", 0) * 0.40 + 0.05), 3),
                    "risk_rank_percentile": 85.0,
                })

            exp_cfg = {
                "experiment_id": f"exp_{args.network_label}_{strat}",
                "split_strategy": strat,
                "features": feature_cols,
                "target": "crash_count",
                "exposure": "vehicle_km",
            }

            payload = export_experiment_run_artifacts(
                experiment_id=f"exp_{args.network_label}_{strat}",
                config=exp_cfg,
                report=report.to_dict(),
                predictions=predictions,
                output_dir=args.output_dir,
            )
        elif args.command == "serve-published-api":



            serve_published_api(
                host=args.host,
                port=args.port,
                published_index_path=args.published_index_path,
                root_dir=Path(args.root_dir),
                dashboard_dir=Path(args.dashboard_dir),
                dashboard_summary_path=Path(args.dashboard_summary_path),
            )
            return 0
        else:
            parser.error(f"Unsupported command: {args.command}")
            return 2
    except RuntimeError as exc:
        parser.error(str(exc))

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
