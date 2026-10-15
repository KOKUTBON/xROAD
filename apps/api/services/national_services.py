"""National enterprise services for multi-tier hierarchies and HSM screening."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from apps.api.settings import get_settings
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from road_risk_modeling.streaming_gateway import (
    STREAM_CONTRACT_VERSION,
    StreamingEventManager,
    StreamSubscriptionFilter,
    TelematicsStreamEvent,
    get_global_stream_manager,
)

from road_risk_modeling.national_hierarchy import (
    AdministrativeTier,
    NationalHierarchy,
    build_sample_italy_national_hierarchy,
)
from road_risk_modeling.hsm_engine import (
    CALIBRATED_HSM_SPFS,
    HSM_CONTRACT_VERSION,
    HSM_ENGINE_VERSION,
    screen_road_network_hsm,
)
from road_risk_modeling.irap_engine import (
    IRAP_CONTRACT_VERSION,
    IRAP_ENGINE_VERSION,
    SRIP_VERSION,
    assess_segment_irap,
    generate_safer_roads_investment_plan,
)
from road_risk_modeling.telematics_engine import (
    TELEMATICS_CONTRACT_VERSION,
    TELEMATICS_ENGINE_VERSION,
    calculate_segment_telematics_metrics,
    detect_events_from_waypoints,
    parse_telematics_events,
)
from road_risk_modeling.cip_engine import (
    CIP_CONTRACT_VERSION,
    CIP_ENGINE_VERSION,
    optimize_capital_improvement_plan,
    parse_cip_candidates,
)
from road_risk_modeling.cv_road_audit import (
    CV_CONTRACT_VERSION,
    CV_ENGINE_VERSION,
    aggregate_frame_detections_to_segments,
    parse_frame_observations,
)
from road_risk_modeling.micro_ssam_engine import (
    SSAM_CONTRACT_VERSION,
    SSAM_ENGINE_VERSION,
    aggregate_conflicts_to_junctions,
    detect_trajectory_conflicts,
    parse_agent_trajectories,
)
from road_risk_modeling.st_gnn_forecasting import (
    DEFAULT_HORIZONS,
    ST_GNN_CONTRACT_VERSION,
    ST_GNN_ENGINE_VERSION,
    GraphEdge,
    RoadGraphNode,
    SpatioTemporalFeatureFrame,
    _safe_float,
    _safe_int,
    execute_st_gnn_forecast,
)
from road_risk_modeling.causal_ml_engine import (
    CAUSAL_CONTRACT_VERSION,
    CAUSAL_ENGINE_VERSION,
    STANDARD_COUNTERMEASURES,
    estimate_double_ml_treatment_effect,
    estimate_segment_cate_heterogeneity,
    parse_observational_units,
)
from road_risk_modeling.cits_v2x_engine import (
    CITS_CONTRACT_VERSION,
    CITS_ENGINE_VERSION,
    create_cits_actuation_bundle,
    parse_operational_risk_alerts,
)
from road_risk_modeling.simulation_sandbox_engine import (
    SIM_CONTRACT_VERSION,
    SIM_SANDBOX_VERSION,
    evaluate_synthetic_countermeasure_pair,
)
from road_risk_modeling.ai_act_compliance_engine import (
    AI_ACT_CONTRACT_VERSION,
    AI_ACT_ENGINE_VERSION,
    REGULATION_REFERENCE,
    generate_eu_ai_act_dossier,
)
from road_risk_modeling.federated_learning_engine import (
    FL_CONTRACT_VERSION,
    FL_ENGINE_VERSION,
    run_federated_training_pipeline,
)
from road_risk_modeling.micromobility_engine import (
    MICROMOBILITY_CONTRACT_VERSION,
    MICROMOBILITY_ENGINE_VERSION,
    run_micromobility_fleet_audit,
)
from road_risk_modeling.ministerial_dossier import (
    DOSSIER_CONTRACT_VERSION,
    DOSSIER_ENGINE_VERSION,
    compile_ministerial_dossier,
    render_ministerial_markdown,
    render_ministerial_pdf,
)
from road_risk_modeling.forensic_reconstruction_engine import (
    FORENSIC_CONTRACT_VERSION,
    FORENSIC_ENGINE_VERSION,
    build_forensic_case_from_payload,
)
from road_risk_modeling.tmc_playbook_engine import (
    TMC_CONTRACT_VERSION,
    TMC_ENGINE_VERSION,
    authorize_and_execute_playbook,
    compile_playbook_actuation_plan,
    evaluate_incident_triggers,
    open_tmc_incident,
    get_standard_tmc_playbooks,
)
from road_risk_modeling.connected_fleet_ivi_engine import (
    CITS_IVI_CONTRACT_VERSION,
    CITS_IVI_ENGINE_VERSION,
    compile_cv2x_transmission,
    compile_iso19321_ivi_message,
    build_connected_fleet_view,
)
from road_risk_modeling.incident_coordination_engine import (
    COORDINATION_CONTRACT_VERSION,
    COORDINATION_ENGINE_VERSION,
    ActiveIncidentNode,
    compute_lwr_shockwave_dynamics,
    detect_rerouting_conflicts,
    generate_coordinated_mitigation_plan,
    parse_incident_scenario,
    optimize_diversion_flow_splits,
)
from road_risk_modeling.segment_panel_engine import (
    PANEL_CONTRACT_VERSION,
    SEGMENT_PANEL_ENGINE_VERSION,
    build_segment_week_panel,
)
from road_risk_modeling.panel_baselines_engine import (
    BASELINES_CONTRACT_VERSION,
    BASELINES_ENGINE_VERSION,
    evaluate_model_suite,
)
from road_risk_modeling.spatial_temporal_validation import (
    forward_temporal_split,
    space_time_blocked_split,
    spatial_group_kfold_split,
)





class NationalServiceError(RuntimeError):
    """Base exception for national hierarchy and HSM screening services."""


def get_national_hierarchy(country_code: str = "IT") -> dict[str, Any]:
    """Retrieve administrative hierarchy tree for a sovereign country."""
    normalized_cc = country_code.strip().upper()
    if normalized_cc == "IT":
        hierarchy = build_sample_italy_national_hierarchy()
    else:
        hierarchy = NationalHierarchy(country_code=normalized_cc, country_name=f"Country {normalized_cc}")

    return hierarchy.to_dict()


def get_national_rollups(
    country_code: str = "IT",
    crashes_by_entity: Mapping[str, Mapping[str, int]] | None = None,
) -> dict[str, Any]:
    """Calculate and return safety roll-ups by administrative tier."""
    normalized_cc = country_code.strip().upper()
    if normalized_cc == "IT":
        hierarchy = build_sample_italy_national_hierarchy()
    else:
        hierarchy = NationalHierarchy(country_code=normalized_cc, country_name=f"Country {normalized_cc}")
    crashes_by_entity = crashes_by_entity or {}

    rollups = hierarchy.calculate_rollups(crashes_by_entity)
    root_rollup = rollups.get(hierarchy.root_id)

    return {
        "country_code": hierarchy.country_code,
        "country_name": hierarchy.country_name,
        "root_entity_id": hierarchy.root_id,
        "total_entities": len(hierarchy._entities),
        "national_summary": root_rollup.to_dict() if root_rollup else None,
        "rollups_by_entity": {k: v.to_dict() for k, v in rollups.items()},
    }


def list_hsm_functional_classes() -> list[dict[str, Any]]:
    """Return catalog of calibrated AASHTO Highway Safety Manual Part C SPFs."""
    return [
        {
            "facility_class": spf.facility_class,
            "description": spf.description,
            "beta_0": spf.beta_0,
            "beta_1": spf.beta_1,
            "overdispersion_k": spf.overdispersion_k,
            "length_adjusted_k": spf.length_adjusted_k,
        }
        for spf in CALIBRATED_HSM_SPFS.values()
    ]


def run_hsm_network_screening(
    segments: Sequence[Mapping[str, Any]],
    facility_class: str = "rural_two_lane_two_way",
    calibration_c: float = 1.0,
    network_label: str = "screened_network",
) -> dict[str, Any]:
    """Execute HSM Empirical Bayes screening on submitted road segments."""
    if not segments:
        raise NationalServiceError("Segment list cannot be empty for HSM screening.")

    results = screen_road_network_hsm(
        segments=segments,
        default_facility_class=facility_class,
        calibration_c=calibration_c,
    )

    high_priority_count = sum(1 for r in results if r.screening_band == "high_priority")
    medium_priority_count = sum(1 for r in results if r.screening_band == "medium_priority")

    return {
        "hsm_engine_version": HSM_ENGINE_VERSION,
        "contract_version": HSM_CONTRACT_VERSION,
        "network_label": network_label,
        "facility_class_used": facility_class,
        "calibration_factor_c": calibration_c,
        "summary": {
            "total_segments_screened": len(results),
            "high_priority_count": high_priority_count,
            "medium_priority_count": medium_priority_count,
            "total_observed_crashes": sum(r.observed_crashes_total for r in results),
            "total_expected_crashes_annual": round(sum(r.eb_expected_annual for r in results), 2),
            "total_psi_excess_annual": round(sum(max(0.0, r.psi_excess_crashes_annual) for r in results), 2),
        },
        "results": [r.to_dict() for r in results],
    }


def run_irap_star_rating(
    segments: Sequence[Mapping[str, Any]],
    network_label: str = "evaluated_network",
) -> dict[str, Any]:
    """Execute iRAP Star Rating assessment across 4 road user groups."""
    if not segments:
        raise NationalServiceError("Segment list cannot be empty for iRAP star rating.")

    assessed = [assess_segment_irap(seg) for seg in segments]
    total_segments = len(assessed)
    un_target_compliant = sum(1 for seg in assessed if seg.scores.meets_un_target_4)
    compliance_pct = (un_target_compliant / max(1, total_segments)) * 100.0

    star_distribution = {
        "vehicle": {star: sum(1 for s in assessed if s.scores.vehicle_stars == star) for star in range(1, 6)},
        "motorcycle": {star: sum(1 for s in assessed if s.scores.motorcycle_stars == star) for star in range(1, 6)},
        "bicycle": {star: sum(1 for s in assessed if s.scores.bicycle_stars == star) for star in range(1, 6)},
        "pedestrian": {star: sum(1 for s in assessed if s.scores.pedestrian_stars == star) for star in range(1, 6)},
    }

    return {
        "irap_engine_version": IRAP_ENGINE_VERSION,
        "contract_version": IRAP_CONTRACT_VERSION,
        "network_label": network_label,
        "un_global_target_4_summary": {
            "total_segments_assessed": total_segments,
            "compliant_3star_or_better_segments": un_target_compliant,
            "compliance_percentage": round(compliance_pct, 2),
            "target_threshold_percentage": 75.0,
            "target_achieved": compliance_pct >= 75.0,
            "star_distribution": star_distribution,
        },
        "results": [s.to_dict() for s in assessed],
    }


def run_srip_generation(
    segments: Sequence[Mapping[str, Any]],
    value_of_statistical_life_eur: float = 1_500_000.0,
    value_of_serious_injury_eur: float = 250_000.0,
    discount_rate: float = 0.04,
    min_bcr_threshold: float = 1.0,
    network_label: str = "evaluated_network",
) -> dict[str, Any]:
    """Generate Safer Roads Investment Plan (SRIP) for sub-3-star segments."""
    if not segments:
        raise NationalServiceError("Segment list cannot be empty for SRIP generation.")

    assessed = [assess_segment_irap(seg) for seg in segments]
    plan = generate_safer_roads_investment_plan(
        assessed_segments=assessed,
        value_of_statistical_life_eur=value_of_statistical_life_eur,
        value_of_serious_injury_eur=value_of_serious_injury_eur,
        discount_rate=discount_rate,
        min_bcr_threshold=min_bcr_threshold,
    )

    total_cost = sum(i.estimated_cost_eur for i in plan)
    total_fsi = sum(i.expected_fsi_prevented_20yr for i in plan)
    total_pvb = sum(i.present_value_benefits_eur for i in plan)
    total_pvc = sum(i.present_value_costs_eur for i in plan)
    prog_bcr = total_pvb / max(1.0, total_pvc) if plan else 0.0

    return {
        "irap_engine_version": IRAP_ENGINE_VERSION,
        "contract_version": IRAP_CONTRACT_VERSION,
        "srip_version": SRIP_VERSION,
        "network_label": network_label,
        "srip_investment_summary": {
            "total_recommended_countermeasures": len(plan),
            "total_investment_budget_eur": round(total_cost, 2),
            "total_fsi_prevented_20yr": round(total_fsi, 2),
            "total_present_value_benefits_eur": round(total_pvb, 2),
            "program_average_bcr": round(prog_bcr, 2),
        },
        "investment_plan": [i.to_dict() for i in plan],
    }


def run_telematics_ingestion(
    observations: Sequence[Mapping[str, Any]],
    is_waypoints: bool = False,
    network_label: str = "telematics_feed",
) -> dict[str, Any]:
    """Ingest telematics waypoints or events and return detected near-miss anomalies."""
    if not observations:
        raise NationalServiceError("Observation list cannot be empty for telematics ingestion.")

    if is_waypoints:
        events = detect_events_from_waypoints(observations)
    else:
        events = parse_telematics_events(observations)

    event_breakdown = {
        "harsh_braking": sum(1 for e in events if e.event_type == "harsh_braking"),
        "harsh_cornering": sum(1 for e in events if e.event_type == "harsh_cornering"),
        "harsh_acceleration": sum(1 for e in events if e.event_type == "harsh_acceleration"),
        "sudden_speed_drop": sum(1 for e in events if e.event_type == "sudden_speed_drop"),
    }

    return {
        "telematics_engine_version": TELEMATICS_ENGINE_VERSION,
        "contract_version": TELEMATICS_CONTRACT_VERSION,
        "network_label": network_label,
        "total_observations_received": len(observations),
        "total_near_miss_events_detected": len(events),
        "event_breakdown": event_breakdown,
        "events": [e.to_dict() for e in events],
    }


def run_near_miss_screening(
    segments: Sequence[Mapping[str, Any]],
    telematics_events: Sequence[Mapping[str, Any]],
    days_analyzed: int = 365,
    fleet_penetration_rate: float = 0.05,
    network_label: str = "screened_network",
) -> dict[str, Any]:
    """Aggregate telematics anomalies onto segments and calculate proactive near-miss risk."""
    if not segments:
        raise NationalServiceError("Segment list cannot be empty for near-miss screening.")

    parsed_events = parse_telematics_events(telematics_events)
    metrics = calculate_segment_telematics_metrics(
        segments=segments,
        telematics_events=parsed_events,
        days_analyzed=days_analyzed,
        fleet_penetration_rate=fleet_penetration_rate,
    )

    tier_counts = {
        "critical_proactive_hotspot": sum(1 for m in metrics if m.risk_tier == "critical_proactive_hotspot"),
        "high_risk_corridor": sum(1 for m in metrics if m.risk_tier == "high_risk_corridor"),
        "monitored_baseline": sum(1 for m in metrics if m.risk_tier == "monitored_baseline"),
        "low_anomaly_network": sum(1 for m in metrics if m.risk_tier == "low_anomaly_network"),
    }

    return {
        "telematics_engine_version": TELEMATICS_ENGINE_VERSION,
        "contract_version": TELEMATICS_CONTRACT_VERSION,
        "network_label": network_label,
        "summary": {
            "total_segments_screened": len(metrics),
            "total_telematics_events": len(parsed_events),
            "tier_distribution": tier_counts,
            "total_mvkt_annual": round(sum(m.mvkt_annual for m in metrics), 2),
            "average_near_miss_rate_per_mvkt": round(
                sum(m.near_miss_rate_per_mvkt for m in metrics) / max(1, len(metrics)), 2
            ),
        },
        "results": [m.to_dict() for m in metrics],
    }


def run_cip_portfolio_optimization(
    candidates: Sequence[Mapping[str, Any]],
    annual_budgets: Sequence[float],
    start_calendar_year: int = 2027,
    inflation_rate: float = 0.025,
    discount_rate: float = 0.04,
    regional_min_quotas: Mapping[str, float] | None = None,
    allow_budget_rollover: bool = False,
    network_label: str = "national_network",
) -> dict[str, Any]:
    """Execute multi-year budget-constrained capital improvement plan optimization."""
    if not candidates:
        raise NationalServiceError("Candidate project list cannot be empty for CIP optimization.")
    if not annual_budgets:
        raise NationalServiceError("Annual budgets list cannot be empty for CIP optimization.")

    parsed = parse_cip_candidates(candidates)
    portfolio = optimize_capital_improvement_plan(
        candidates=parsed,
        annual_budgets=annual_budgets,
        start_calendar_year=start_calendar_year,
        inflation_rate=inflation_rate,
        discount_rate=discount_rate,
        regional_min_quotas=regional_min_quotas,
        allow_budget_rollover=allow_budget_rollover,
    )

    payload = portfolio.to_dict()
    payload["network_label"] = network_label
    return payload


def run_cv_road_audit(
    observations: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    network_label: str = "audited_network",
) -> dict[str, Any]:
    """Execute computer vision safety audit and automated iRAP feature extraction."""
    if not segments:
        raise NationalServiceError("Segment list cannot be empty for CV road audit.")

    parsed_observations = parse_frame_observations(observations)
    audited = aggregate_frame_detections_to_segments(segments, parsed_observations)

    total_segments = len(audited)
    un_target_compliant = sum(1 for s in audited if s.irap_star_ratings.get("meets_un_target_4", False))
    potholes_total = sum(s.pothole_count_total for s in audited)

    return {
        "cv_engine_version": CV_ENGINE_VERSION,
        "contract_version": CV_CONTRACT_VERSION,
        "network_label": network_label,
        "summary": {
            "total_segments_audited": total_segments,
            "total_inspection_frames": len(parsed_observations),
            "total_assets_detected": sum(len(f.detections) for f in parsed_observations),
            "total_potholes_detected": potholes_total,
            "un_target_4_compliance_pct": round((un_target_compliant / max(1, total_segments)) * 100.0, 2),
            "infrastructure_summary": {
                "segments_with_sidewalks": sum(1 for s in audited if s.has_sidewalk),
                "segments_with_median_barriers": sum(1 for s in audited if s.has_median_barrier),
                "segments_with_cycle_tracks": sum(1 for s in audited if s.has_segregated_cycle_facility),
                "segments_with_roadside_barriers": sum(1 for s in audited if s.has_roadside_barrier),
            },
        },
        "results": [s.to_dict() for s in audited],
    }


def run_microscopic_ssam_analysis(
    trajectories: Sequence[Mapping[str, Any]],
    junctions: Sequence[Mapping[str, Any]] | None = None,
    network_label: str = "analyzed_network",
) -> dict[str, Any]:
    """Execute microscopic trajectory SSAM and multi-agent VRU conflict analysis."""
    if not trajectories:
        raise NationalServiceError("Trajectory list cannot be empty for microscopic SSAM analysis.")

    parsed_agents = parse_agent_trajectories(trajectories)
    conflicts = detect_trajectory_conflicts(parsed_agents)
    junction_summaries = aggregate_conflicts_to_junctions(conflicts)

    total_conf = len(conflicts)
    crit_conf = sum(1 for c in conflicts if c.severity_tier == "critical")
    vru_conf = sum(1 for c in conflicts if c.is_vru_involved)

    return {
        "ssam_engine_version": SSAM_ENGINE_VERSION,
        "contract_version": SSAM_CONTRACT_VERSION,
        "network_label": network_label,
        "summary": {
            "total_agents_analyzed": len(parsed_agents),
            "total_conflicts_detected": total_conf,
            "critical_conflicts_count": crit_conf,
            "vru_conflicts_count": vru_conf,
            "vru_conflict_ratio_pct": round((vru_conf / max(1, total_conf)) * 100.0, 2),
            "conflict_type_breakdown": {
                "rear_end": sum(1 for c in conflicts if c.conflict_type == "rear_end"),
                "crossing": sum(1 for c in conflicts if c.conflict_type == "crossing"),
                "head_on": sum(1 for c in conflicts if c.conflict_type == "head_on"),
                "vru_crossing": sum(1 for c in conflicts if c.conflict_type == "vru_crossing"),
                "vru_longitudinal": sum(1 for c in conflicts if c.conflict_type == "vru_longitudinal"),
            },
            "total_junctions_analyzed": len(junction_summaries),
            "critical_junctions_count": sum(1 for j in junction_summaries if j.danger_tier == "critical"),
        },
        "junction_summaries": [j.to_dict() for j in junction_summaries],
        "conflicts": [c.to_dict() for c in conflicts],
    }


def run_st_gnn_risk_forecasting(
    nodes: Sequence[Mapping[str, Any]],
    time_series_frames: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]] | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    network_label: str = "forecasted_network",
) -> dict[str, Any]:
    """Execute Spatio-Temporal Graph Neural Network risk forecasting across lookahead horizons."""
    if not nodes:
        raise NationalServiceError("Node list cannot be empty for ST-GNN risk forecasting.")

    parsed_nodes = [
        RoadGraphNode(
            segment_id=str(n.get("segment_id") or n.get("id")),
            length_km=_safe_float(n.get("length_km") or 0.5),
            free_flow_speed_kmh=_safe_float(n.get("free_flow_speed_kmh") or 50.0),
            functional_class=str(n.get("functional_class") or "urban_arterial"),
            latitude=_safe_float(n.get("latitude")),
            longitude=_safe_float(n.get("longitude")),
        )
        for n in nodes
    ]

    parsed_edges = None
    if edges:
        parsed_edges = [
            GraphEdge(
                from_segment_id=str(e.get("from_segment_id") or e.get("from")),
                to_segment_id=str(e.get("to_segment_id") or e.get("to")),
                distance_m=_safe_float(e.get("distance_m") or 100.0),
                is_connected=bool(e.get("is_connected", True)),
                weight=_safe_float(e.get("weight") or 1.0),
            )
            for e in edges
        ]

    parsed_frames = [
        SpatioTemporalFeatureFrame(
            segment_id=str(f.get("segment_id") or f.get("id")),
            timestamp=str(f.get("timestamp") or datetime.now(UTC).isoformat()),
            historical_crash_count=_safe_float(f.get("historical_crash_count")),
            telematics_near_miss_rate=_safe_float(f.get("telematics_near_miss_rate")),
            current_speed_kmh=_safe_float(f.get("current_speed_kmh") or 45.0),
            speed_ratio=_safe_float(f.get("speed_ratio") or 0.90),
            precipitation_mm_h=_safe_float(f.get("precipitation_mm_h")),
            surface_condition=str(f.get("surface_condition") or "dry").lower(),
            visibility_m=_safe_float(f.get("visibility_m") or 10000.0),
            hour_of_day=_safe_int(f.get("hour_of_day") or 12),
            is_peak_hour=bool(f.get("is_peak_hour") or False),
        )
        for f in time_series_frames
    ]

    forecasts, alerts = execute_st_gnn_forecast(
        nodes=parsed_nodes,
        time_series_frames=parsed_frames,
        edges=parsed_edges,
        horizons=horizons,
    )

    crit_alerts = sum(1 for a in alerts if a.alert_tier == "critical")
    high_alerts = sum(1 for a in alerts if a.alert_tier == "high")

    return {
        "st_gnn_engine_version": ST_GNN_ENGINE_VERSION,
        "contract_version": ST_GNN_CONTRACT_VERSION,
        "network_label": network_label,
        "summary": {
            "total_segments_forecasted": len(parsed_nodes),
            "total_predictions_generated": len(forecasts),
            "total_alerts_issued": len(alerts),
            "critical_threat_alerts_count": crit_alerts,
            "high_threat_alerts_count": high_alerts,
            "forecast_horizons_hours": sorted(list(horizons)),
        },
        "alerts": [a.to_dict() for a in alerts],
        "forecasts": [f.to_dict() for f in forecasts],
    }


def run_causal_countermeasure_evaluation(
    observational_data: Sequence[Mapping[str, Any]],
    countermeasures: Sequence[str] | None = None,
    network_label: str = "evaluated_network",
) -> dict[str, Any]:
    """Execute Double Machine Learning countermeasure evaluation and CATE estimation."""
    if not observational_data:
        raise NationalServiceError("Observational data cannot be empty for causal evaluation.")

    units = parse_observational_units(observational_data)
    unique_cm_ids = sorted(list({u.countermeasure_id for u in units}))
    if countermeasures:
        target_cm_ids = [c.upper() for c in countermeasures if c.upper() in unique_cm_ids]
    else:
        target_cm_ids = unique_cm_ids

    if not target_cm_ids:
        raise NationalServiceError(f"No matching countermeasures found in dataset (available: {unique_cm_ids}).")

    treatment_effects = []
    all_cate_estimates = []

    for cid in target_cm_ids:
        try:
            effect, _ = estimate_double_ml_treatment_effect(units, cid)
            treatment_effects.append(effect)
            cate_estimates = estimate_segment_cate_heterogeneity(units, cid, effect.ate_crashes)
            all_cate_estimates.extend(cate_estimates)
        except RuntimeError:
            continue

    if not treatment_effects:
        raise NationalServiceError("Insufficient observational units (need >=2 treated and >=2 control per countermeasure).")

    all_cate_estimates.sort(key=lambda c: c.predicted_annual_crash_reduction, reverse=True)
    sig_count = sum(1 for te in treatment_effects if te.is_statistically_significant)

    return {
        "causal_engine_version": CAUSAL_ENGINE_VERSION,
        "contract_version": CAUSAL_CONTRACT_VERSION,
        "network_label": network_label,
        "summary": {
            "total_observational_units": len(units),
            "total_countermeasures_evaluated": len(treatment_effects),
            "statistically_significant_countermeasures": sig_count,
            "total_segments_analyzed": len(all_cate_estimates),
            "top_priority_segments_count": sum(1 for c in all_cate_estimates if c.priority_tier == "top_priority"),
        },
        "treatment_effects": [te.to_dict() for te in treatment_effects],
        "cate_estimates": [c.to_dict() for c in all_cate_estimates],
    }


def run_cits_v2x_actuation(
    alerts_data: Sequence[Mapping[str, Any]],
    network_label: str = "evaluated_network",
    sovereign_station_id: str = "IT-MIT-TMC-BA-01",
) -> dict[str, Any]:
    """Execute C-ITS and Cellular V2X operational actuation plan generation."""
    if not alerts_data:
        raise NationalServiceError("Alerts data cannot be empty for C-ITS actuation.")

    parsed_alerts = parse_operational_risk_alerts(alerts_data)
    plan = create_cits_actuation_bundle(
        alerts=parsed_alerts,
        network_label=network_label,
        sovereign_station_id=sovereign_station_id,
    )
    return plan.to_dict()


def run_synthetic_countermeasure_evaluation(
    junction_id: str,
    baseline_template: str = "BASELINE_SIGNALIZED",
    redesign_template: str = "DUTCH_PROTECTED_JUNCTION",
    duration_seconds: float = 60.0,
    vehicle_demand_vph: float = 800.0,
    vru_demand_pph: float = 120.0,
    random_seed: int = 42,
    network_label: str = "evaluated_network",
    include_trajectories: bool = True,
) -> dict[str, Any]:
    """Execute synthetic micro-simulation countermeasure safety appraisal."""
    if not junction_id:
        raise NationalServiceError("junction_id is required for simulation evaluation.")

    base_res, redesign_res, comparison = evaluate_synthetic_countermeasure_pair(
        junction_id=junction_id,
        baseline_template=baseline_template,
        redesign_template=redesign_template,
        duration_seconds=duration_seconds,
        vehicle_demand_vph=vehicle_demand_vph,
        vru_demand_pph=vru_demand_pph,
        random_seed=random_seed,
    )

    return {
        "sim_sandbox_version": SIM_SANDBOX_VERSION,
        "contract_version": SIM_CONTRACT_VERSION,
        "network_label": network_label,
        "junction_id": junction_id,
        "comparison": comparison.to_dict(),
        "baseline_summary": base_res.to_dict(include_trajectories=include_trajectories),
        "redesign_summary": redesign_res.to_dict(include_trajectories=include_trajectories),
    }


def run_ai_act_conformity_audit(
    corridors: Sequence[Mapping[str, Any]],
    network_label: str = "evaluated_network",
    protected_attribute: str = "geographic_tier",
    accuracy_auc_roc: float = 0.885,
    brier_score_loss: float = 0.082,
) -> dict[str, Any]:
    """Execute EU AI Act (Regulation 2024/1689) High-Risk Conformity and Explainable AI audit."""
    if not corridors:
        raise NationalServiceError("Corridors data cannot be empty for EU AI Act compliance audit.")

    dossier = generate_eu_ai_act_dossier(
        corridors_data=corridors,
        network_label=network_label,
        protected_attribute=protected_attribute,
        accuracy_auc_roc=accuracy_auc_roc,
        brier_score_loss=brier_score_loss,
    )

    return dossier.to_dict()


def run_federated_learning_round(
    nodes_data: Sequence[Mapping[str, Any]],
    rounds_count: int = 3,
    aggregation_method: str = "fedavg",
    enable_dp: bool = True,
    target_epsilon: float = 2.0,
    network_label: str = "evaluated_network",
) -> dict[str, Any]:
    """Execute multi-concessionaire privacy-preserving federated training loop."""
    if not nodes_data:
        raise NationalServiceError("nodes_data cannot be empty for federated learning training.")

    report = run_federated_training_pipeline(
        nodes_data=nodes_data,
        rounds_count=rounds_count,
        aggregation_method=aggregation_method,
        enable_dp=enable_dp,
        target_epsilon=target_epsilon,
        network_label=network_label,
    )

    return report.to_dict()


def run_micromobility_risk_audit(
    waypoints: Sequence[Mapping[str, Any]],
    segments_data: Sequence[Mapping[str, Any]] | None = None,
    network_label: str = "evaluated_network",
) -> dict[str, Any]:
    """Execute VRU micromobility sensor fusion audit and iRAP friction calibration."""
    if not waypoints:
        raise NationalServiceError("waypoints data cannot be empty for micromobility risk audit.")

    report, events = run_micromobility_fleet_audit(
        waypoints_data=waypoints,
        segments_data=segments_data,
        network_label=network_label,
    )

    return {
        "micromobility_engine_version": MICROMOBILITY_ENGINE_VERSION,
        "contract_version": MICROMOBILITY_CONTRACT_VERSION,
        "report": report.to_dict(),
        "events": [e.to_dict() for e in events],
    }


def generate_sovereign_ministerial_dossier(
    network_label: str = "national_network",
    jurisdiction_name: str = "Repubblica Italiana / Regione Puglia / Comune di Bari",
    ministry_authority: str = "Ministero delle Infrastrutture e dei Trasporti",
    hsm_data: Mapping[str, Any] | None = None,
    irap_data: Mapping[str, Any] | None = None,
    telematics_data: Mapping[str, Any] | None = None,
    micromobility_data: Mapping[str, Any] | None = None,
    st_gnn_data: Mapping[str, Any] | None = None,
    cits_data: Mapping[str, Any] | None = None,
    simulation_data: Mapping[str, Any] | None = None,
    causal_data: Mapping[str, Any] | None = None,
    ai_act_data: Mapping[str, Any] | None = None,
    cip_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile sovereign ministerial safety dossier and synthesize executive KPIs."""
    dossier = compile_ministerial_dossier(
        network_label=network_label,
        jurisdiction_name=jurisdiction_name,
        ministry_authority=ministry_authority,
        hsm_data=hsm_data,
        irap_data=irap_data,
        telematics_data=telematics_data,
        micromobility_data=micromobility_data,
        st_gnn_data=st_gnn_data,
        cits_data=cits_data,
        simulation_data=simulation_data,
        causal_data=causal_data,
        ai_act_data=ai_act_data,
        cip_data=cip_data,
    )

    return {
        "dossier_engine_version": DOSSIER_ENGINE_VERSION,
        "contract_version": DOSSIER_CONTRACT_VERSION,
        "dossier": dossier.to_dict(),
        "markdown_briefing": render_ministerial_markdown(dossier),
    }


def run_segment_panel_risk_evaluation(
    segments_data: Sequence[Mapping[str, Any]],
    crashes_data: Sequence[Mapping[str, Any]],
    weather_data: Sequence[Mapping[str, Any]] | None = None,
    split_strategy: str = "forward_temporal",
    weeks_count: int = 8,
    network_label: str = "evaluated_panel",
) -> dict[str, Any]:
    """Execute exposure-normalized segment-time panel evaluation from baselines to boosted trees."""
    if not segments_data:
        raise NationalServiceError("segments_data cannot be empty for panel risk evaluation.")

    panel = build_segment_week_panel(
        segments=segments_data,
        crashes=crashes_data,
        weather=weather_data,
        weeks_count=weeks_count,
        network_label=network_label,
    )

    obs_dicts = [o.to_dict() for o in panel.observations]
    if split_strategy == "spatial_group":
        split = spatial_group_kfold_split(obs_dicts)
    elif split_strategy == "space_time_blocked":
        split = space_time_blocked_split(obs_dicts)
    else:
        split = forward_temporal_split(obs_dicts)

    feature_cols = ["speed_limit_kmh", "lanes", "precipitation_mm", "temperature_c", "dow_sin", "dow_cos"]

    X_train = [[obs_dicts[i][col] for col in feature_cols] for i in split.train_indices]
    y_train = [obs_dicts[i]["crash_count"] for i in split.train_indices]
    exp_train = [obs_dicts[i]["exposure_vehicle_km"] for i in split.train_indices]

    X_test = [[obs_dicts[i][col] for col in feature_cols] for i in split.test_indices]
    y_test = [obs_dicts[i]["crash_count"] for i in split.test_indices]
    exp_test = [obs_dicts[i]["exposure_vehicle_km"] for i in split.test_indices]

    report = evaluate_model_suite(
        X_train=X_train,
        y_train=y_train,
        exp_train=exp_train,
        X_test=X_test,
        y_test=y_test,
        exp_test=exp_test,
        feature_names=feature_cols,
        network_label=network_label,
    )

    return {
        "panel_engine_version": SEGMENT_PANEL_ENGINE_VERSION,
        "contract_version": PANEL_CONTRACT_VERSION,
        "baselines_engine_version": BASELINES_ENGINE_VERSION,
        "network_label": network_label,
        "panel_summary": {
            "total_segments": panel.total_segments,
            "total_periods": panel.total_periods,
            "total_observations": panel.total_observations,
            "total_crashes": panel.total_crashes,
            "mean_exposure_vehicle_km": panel.mean_exposure_vehicle_km,
        },
        "split_summary": split.to_dict(),
        "benchmark_report": report.to_dict(),
    }


def publish_telematics_stream_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Classify, buffer, and asynchronously broadcast a real-time telematics event."""
    mgr = get_global_stream_manager()
    evt = mgr.classify_and_build_event(raw)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(mgr.broadcast(evt))
    except RuntimeError:
        asyncio.run(mgr.broadcast(evt))
    return {
        "contract_version": STREAM_CONTRACT_VERSION,
        "status": "broadcasted",
        "event": evt.to_dict(),
        "active_subscribers": mgr.total_subscribers,
    }


def get_recent_telematics_events(limit: int = 50) -> dict[str, Any]:
    """Retrieve sliding-window buffer of recent broadcast events."""
    mgr = get_global_stream_manager()
    events = mgr.get_recent_events(limit=limit)
    return {
        "contract_version": STREAM_CONTRACT_VERSION,
        "total_events": len(events),
        "events": events,
        "active_subscribers": mgr.total_subscribers,
    }


def _local_records(name: str) -> list[dict[str, Any]]:
    """Read operator-supplied records; a clean installation has no observations."""
    path = get_settings().root_dir / "data" / "operations" / f"{name}.json"
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError(f"{name}.json must contain an array of objects")
    return records


def _forensic_cases():
    cases = [build_forensic_case_from_payload(row) for row in _local_records("forensic_cases")]
    return {case.case_id: case for case in cases}


def _incident_scenarios():
    return [dict(parse_incident_scenario(row), city=str(row.get("city", "")))
            for row in _local_records("incident_scenarios")]


def _active_incidents():
    return {row["incident_id"]: open_tmc_incident(**row) for row in _local_records("tmc_incidents")}


def get_forensic_cases() -> dict[str, Any]:
    """Retrieve summarized catalog of forensic incident reconstruction cases."""
    cases = _forensic_cases()
    summary_list = []
    for c in cases.values():
        aeb_scen = next((s for s in c.counterfactual_scenarios if s.scenario_id == "SCENARIO_A_AEB"), None)
        speed_scen = next((s for s in c.counterfactual_scenarios if s.scenario_id == "SCENARIO_B_SPEED_COMPLIANCE"), None)
        summary_list.append({
            "case_id": c.case_id,
            "title": c.title,
            "location_name": c.location_name,
            "incident_timestamp_utc": c.incident_timestamp_utc,
            "speed_limit_kph": c.speed_limit_kph,
            "weather_condition": c.weather_condition,
            "surface_condition": c.surface_condition,
            "primary_agent_type": c.primary_agent.agent_type,
            "secondary_agent_type": c.secondary_agent.agent_type,
            "initial_speed_kph": c.kinetic_metrics.initial_speed_kph,
            "impact_speed_kph": c.kinetic_metrics.impact_speed_kph,
            "driver_prt_seconds": c.kinetic_metrics.driver_prt_seconds,
            "energy_dissipated_kj": c.kinetic_metrics.energy_dissipated_kj,
            "aeb_avoided": aeb_scen.collision_avoided if aeb_scen else False,
            "speed_compliance_avoided": speed_scen.collision_avoided if speed_scen else False,
            "sha256_evidence_hash": c.sha256_evidence_hash,
        })
    return {
        "contract_version": FORENSIC_CONTRACT_VERSION,
        "engine_version": FORENSIC_ENGINE_VERSION,
        "total_cases": len(summary_list),
        "cases": summary_list,
    }


def get_forensic_case_detail(case_id: str) -> dict[str, Any] | None:
    """Retrieve full forensic case record with synchronized trajectories and counterfactuals."""
    case = _forensic_cases().get(case_id)
    if case is None:
        return None
    return {
        "contract_version": FORENSIC_CONTRACT_VERSION,
        "engine_version": FORENSIC_ENGINE_VERSION,
        "case": case.to_dict(include_samples=True),
    }


def generate_forensic_dossier_content(case_id: str) -> dict[str, Any] | None:
    """Retrieve formatted judicial evidence dossier markdown and cryptographic hash."""
    case = _forensic_cases().get(case_id)
    if case is None:
        return None
    return {
        "contract_version": FORENSIC_CONTRACT_VERSION,
        "case_id": case.case_id,
        "title": case.title,
        "sha256_evidence_hash": case.sha256_evidence_hash,
        "dossier_markdown": case.judicial_summary_md,
    }


def get_tmc_playbooks() -> dict[str, Any]:
    """Retrieve catalog of standard operating playbooks."""
    return {
        "contract_version": TMC_CONTRACT_VERSION,
        "engine_version": TMC_ENGINE_VERSION,
        "playbooks": get_standard_tmc_playbooks(),
    }


def get_active_tmc_incidents_list() -> dict[str, Any]:
    """Retrieve active incident queue with staged or active playbooks."""
    incidents = _active_incidents()
    return {
        "contract_version": TMC_CONTRACT_VERSION,
        "engine_version": TMC_ENGINE_VERSION,
        "total_active_incidents": len(incidents),
        "incidents": [inc.to_dict() for inc in incidents.values()],
    }


def evaluate_tmc_trigger_service(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate threat parameters against playbooks and compile 5-tier actuation plan."""
    threat_type = str(raw.get("threat_type", "shockwave_congestion"))
    severity_tier = str(raw.get("severity_tier", "severe"))
    crash_prob = _safe_float(raw.get("crash_probability", 0.65))
    speed_drop = _safe_float(raw.get("speed_drop_kmh", 25.0))
    precip = _safe_float(raw.get("precipitation_mm_h", 0.0))
    near_miss = _safe_int(raw.get("near_miss_count", 0))

    pb = evaluate_incident_triggers(
        threat_type=threat_type,
        severity_tier=severity_tier,
        crash_probability=crash_prob,
        speed_drop_kmh=speed_drop,
        precipitation_mm_h=precip,
        near_miss_count=near_miss,
    )
    corridor_id = str(raw.get("corridor_id", "CORRIDOR-CUSTOM-01"))
    location_name = str(raw.get("location_name", "Metropolitan Corridor"))
    lat = _safe_float(raw.get("latitude", 41.1171))
    lon = _safe_float(raw.get("longitude", 16.8719))

    actions = compile_playbook_actuation_plan(
        playbook=pb,
        corridor_id=corridor_id,
        location_name=location_name,
        latitude=lat,
        longitude=lon,
    )

    return {
        "contract_version": TMC_CONTRACT_VERSION,
        "engine_version": TMC_ENGINE_VERSION,
        "matched_playbook": pb.to_dict(),
        "actions_count": len(actions),
        "actions": [a.to_dict() for a in actions],
    }


def actuate_tmc_playbook_service(
    incident_id: str,
    operator_id: str = "OPERATOR-TMC-CONSOLE",
    authorization_mode: str = "ONE_CLICK",
) -> dict[str, Any]:
    """Authorize and execute coordinated field actuation plan."""
    # This research distribution has no field-device transport adapter.
    # Never claim an action reached infrastructure when no delivery occurred.
    if incident_id not in _active_incidents():
        raise KeyError(f"Incident {incident_id} not found")
    raise ValueError("Field actuation is unavailable. Configure and validate a transport adapter before deployment.")


def get_cits_ivi_messages() -> dict[str, Any]:
    """Retrieve catalog of active ISO 19321 IVI messages and C-V2X transmission envelopes."""
    catalog = [compile_cits_ivi_broadcast_service(row) for row in _local_records("ivi_messages")]
    return {
        "contract_version": CITS_IVI_CONTRACT_VERSION,
        "engine_version": CITS_IVI_ENGINE_VERSION,
        "total_messages": len(catalog),
        "messages": catalog,
    }


def get_connected_fleet_telemetry(
    hazard_lat: float = 41.1085,
    hazard_lon: float = 16.8920,
) -> dict[str, Any]:
    """Retrieve telemetry and in-vehicle cockpit HMI status for monitored fleet."""
    messages = _local_records("ivi_messages")
    vehicles = _local_records("fleet_telemetry")
    fleet = []
    if messages and vehicles:
        message = dict(messages[0], latitude=hazard_lat, longitude=hazard_lon)
        allowed = {"incident_id", "threat_type", "severity_tier", "corridor_id", "location_name",
                   "latitude", "longitude", "mandatory_vsl_kmh", "advisory_vsl_kmh",
                   "precipitation_mm_h", "lane_restrictions"}
        ivi = compile_iso19321_ivi_message(**{k: v for k, v in message.items() if k in allowed})
        fleet = build_connected_fleet_view(vehicles, ivi)
    return {
        "contract_version": CITS_IVI_CONTRACT_VERSION,
        "engine_version": CITS_IVI_ENGINE_VERSION,
        "target_hazard_coordinates": {"latitude": hazard_lat, "longitude": hazard_lon},
        "total_connected_vehicles": len(fleet),
        "fleet": [v.to_dict() for v in fleet],
    }


def compile_cits_ivi_broadcast_service(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Compile custom ISO 19321 IVI message and C-V2X transmission envelopes."""
    incident_id = str(raw.get("incident_id", "INC-CUSTOM-001"))
    threat_type = str(raw.get("threat_type", "shockwave_congestion"))
    severity_tier = str(raw.get("severity_tier", "severe"))
    corridor_id = str(raw.get("corridor_id", "CORRIDOR-CUSTOM-01"))
    location_name = str(raw.get("location_name", "Metropolitan Corridor"))
    latitude = _safe_float(raw.get("latitude", 41.1085))
    longitude = _safe_float(raw.get("longitude", 16.8920))
    mandatory_vsl = _safe_int(raw.get("mandatory_vsl_kmh", 60))
    advisory_vsl = _safe_int(raw.get("advisory_vsl_kmh", 50))
    precip = _safe_float(raw.get("precipitation_mm_h", 0.0))
    lane_rest = str(raw.get("lane_restrictions", "all_open"))

    ivi = compile_iso19321_ivi_message(
        incident_id=incident_id,
        threat_type=threat_type,
        severity_tier=severity_tier,
        corridor_id=corridor_id,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        mandatory_vsl_kmh=mandatory_vsl,
        advisory_vsl_kmh=advisory_vsl,
        precipitation_mm_h=precip,
        lane_restrictions=lane_rest,
    )
    envelopes = compile_cv2x_transmission(ivi)

    return {
        "contract_version": CITS_IVI_CONTRACT_VERSION,
        "engine_version": CITS_IVI_ENGINE_VERSION,
        "ivi_message": ivi.to_dict(),
        "cv2x_envelopes": [e.to_dict() for e in envelopes],
    }


def get_multi_incident_scenarios() -> dict[str, Any]:
    """Retrieve prepackaged metropolitan multi-incident scenarios."""
    raw_scenarios = _incident_scenarios()
    serialized = []
    for s in raw_scenarios:
        serialized.append({
            "scenario_id": s["scenario_id"],
            "title": s["title"],
            "city": s["city"],
            "description": s["description"],
            "upstream_distance_km": s["upstream_distance_km"],
            "incidents": [i.to_dict() for i in s["incidents"]],
            "alternative_corridors": s["alternative_corridors"],
        })
    return {
        "contract_version": COORDINATION_CONTRACT_VERSION,
        "engine_version": COORDINATION_ENGINE_VERSION,
        "total_scenarios": len(serialized),
        "scenarios": serialized,
    }


def evaluate_incident_conflict_spillover_service(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate conflict graph and LWR shockwave dynamics for multi-incident scenarios."""
    scenario_id = str(raw.get("scenario_id", ""))
    all_scenarios = {s["scenario_id"]: s for s in _incident_scenarios()}
    base_scenario = all_scenarios.get(scenario_id)

    if raw.get("incidents"):
        incidents = []
        for inc_raw in raw["incidents"]:
            incidents.append(
                ActiveIncidentNode(
                    incident_id=str(inc_raw.get("incident_id", "INC-CUSTOM")),
                    corridor_id=str(inc_raw.get("corridor_id", "corridor_custom")),
                    location_name=str(inc_raw.get("location_name", "Custom Corridor")),
                    latitude=_safe_float(inc_raw.get("latitude"), 41.11),
                    longitude=_safe_float(inc_raw.get("longitude"), 16.87),
                    severity=str(inc_raw.get("severity", "severe")),
                    capacity_reduction_pct=_safe_float(inc_raw.get("capacity_reduction_pct"), 50.0),
                    incoming_flow_vph=_safe_float(inc_raw.get("incoming_flow_vph"), 2000.0),
                    residual_capacity_vph=_safe_float(inc_raw.get("residual_capacity_vph"), 1000.0),
                    nominal_capacity_vph=_safe_float(inc_raw.get("nominal_capacity_vph"), 2000.0),
                    candidate_detour_corridors=list(inc_raw.get("candidate_detour_corridors", [])),
                    description=str(inc_raw.get("description", "")),
                )
            )
    elif base_scenario:
        incidents = base_scenario["incidents"]
    else:
        incidents = []

    upstream_distance = _safe_float(
        raw.get("upstream_distance_km"),
        base_scenario["upstream_distance_km"] if base_scenario else 2.1,
    )

    if not incidents:
        raise ValueError("Supply observed incidents or a configured scenario.")
    primary = incidents[0]

    lwr_pred = compute_lwr_shockwave_dynamics(
        incoming_flow_vph=primary.incoming_flow_vph,
        residual_capacity_vph=primary.residual_capacity_vph,
        upstream_critical_distance_km=upstream_distance,
    )

    conflicts = detect_rerouting_conflicts(incidents)

    return {
        "contract_version": COORDINATION_CONTRACT_VERSION,
        "engine_version": COORDINATION_ENGINE_VERSION,
        "scenario_id": scenario_id,
        "incidents_count": len(incidents),
        "conflicts_count": len(conflicts),
        "conflicts": [c.to_dict() for c in conflicts],
        "lwr_prediction": lwr_pred.to_dict(),
    }


def optimize_spillover_mitigation_service(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Generate coordinated capacity-constrained flow split plan and VMS/IVI directives."""
    scenario_id = str(raw.get("scenario_id", ""))
    all_scenarios = {s["scenario_id"]: s for s in _incident_scenarios()}
    base_scenario = all_scenarios.get(scenario_id)

    if raw.get("incidents"):
        incidents = []
        for inc_raw in raw["incidents"]:
            incidents.append(
                ActiveIncidentNode(
                    incident_id=str(inc_raw.get("incident_id", "INC-CUSTOM")),
                    corridor_id=str(inc_raw.get("corridor_id", "corridor_custom")),
                    location_name=str(inc_raw.get("location_name", "Custom Corridor")),
                    latitude=_safe_float(inc_raw.get("latitude"), 41.11),
                    longitude=_safe_float(inc_raw.get("longitude"), 16.87),
                    severity=str(inc_raw.get("severity", "severe")),
                    capacity_reduction_pct=_safe_float(inc_raw.get("capacity_reduction_pct"), 50.0),
                    incoming_flow_vph=_safe_float(inc_raw.get("incoming_flow_vph"), 2000.0),
                    residual_capacity_vph=_safe_float(inc_raw.get("residual_capacity_vph"), 1000.0),
                    nominal_capacity_vph=_safe_float(inc_raw.get("nominal_capacity_vph"), 2000.0),
                    candidate_detour_corridors=list(inc_raw.get("candidate_detour_corridors", [])),
                    description=str(inc_raw.get("description", "")),
                )
            )
    elif base_scenario:
        incidents = base_scenario["incidents"]
    else:
        incidents = []

    if raw.get("alternative_corridors"):
        alternatives = list(raw["alternative_corridors"])
    elif base_scenario:
        alternatives = base_scenario["alternative_corridors"]
    else:
        alternatives = []

    upstream_distance = _safe_float(
        raw.get("upstream_distance_km"),
        base_scenario["upstream_distance_km"] if base_scenario else 2.1,
    )

    if not incidents or not alternatives:
        raise ValueError("Supply incidents and alternative corridors before optimization.")

    plan = generate_coordinated_mitigation_plan(
        scenario_id=scenario_id,
        incidents=incidents,
        alternative_corridors=alternatives,
        upstream_distance_km=upstream_distance,
    )

    return plan.to_dict()










