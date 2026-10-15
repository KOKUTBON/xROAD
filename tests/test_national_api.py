"""Unit and service integration tests for National Hierarchy and HSM API endpoints."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Provide mock for boto3 if running in isolated sandbox environment without dateutil
for mod in ["boto3", "botocore", "botocore.client", "botocore.exceptions"]:
    if mod not in sys.modules:
        mock_mod = MagicMock()
        mock_mod.ClientError = type("ClientError", (Exception,), {})
        sys.modules[mod] = mock_mod

from apps.api.auth import AuthContext, ROLE_ANALYST
from apps.api.main import (
    AiActComplianceAuditRequest,
    CausalCountermeasureRequest,
    CitsActuationRequest,
    CipOptimizationRequest,
    CvRoadAuditRequest,
    FederatedTrainingRoundRequest,
    HsmScreeningRequest,
    IrapStarRatingRequest,
    MicroscopicSsamRequest,
    MicromobilityAuditRequest,
    MinisterialDossierRequest,
    NearMissScreeningRequest,
    ResearchPanelRiskRequest,
    SripGenerationRequest,
    StGnnForecastRequest,
    SyntheticCountermeasureEvalRequest,
    TelematicsEventPublishRequest,
    TelematicsIngestionRequest,
    CitsIviCompileRequest,
    MultiIncidentEvaluationRequest,
    SpilloverOptimizationRequest,
    TmcPlaybookActuateRequest,
    TmcTriggerEvaluateRequest,
    create_app,
)
from apps.api.services import national_services
from apps.api.settings import ApiSettings


class TestNationalApiServices(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.app = create_app(ApiSettings(root_dir=self.root))

        self.mock_auth = AuthContext(
            subject="test-analyst",
            assigned_roles=frozenset([ROLE_ANALYST]),
            roles=frozenset([ROLE_ANALYST]),
            scopes=frozenset(["openid"]),
            claims={},
            organization_ids=frozenset(["org-national-test"]),
            municipality_ids=frozenset(["bari"]),
            is_authenticated=True,
            auth_enabled=True,
            provider="mock",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_get_national_hierarchy_service(self) -> None:
        data = national_services.get_national_hierarchy("IT")
        self.assertEqual(data["country_code"], "IT")
        self.assertEqual(data["country_name"], "Italy")
        self.assertGreater(data["entity_count"], 5)
        self.assertIn("entities", data)

        entity_codes = [e["code"] for e in data["entities"]]
        self.assertIn("IT", entity_codes)
        self.assertIn("IT-75", entity_codes)
        self.assertIn("BA", entity_codes)

    def test_get_national_rollups_service(self) -> None:
        data = national_services.get_national_rollups("IT")
        self.assertEqual(data["country_code"], "IT")
        self.assertIn("national_summary", data)
        self.assertIn("rollups_by_entity", data)

        summary = data["national_summary"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["total_crashes"], 0)
        self.assertEqual(summary["fatalities"], 0)
        self.assertIsNotNone(summary["fatalities_per_100k_pop"])

    def test_list_hsm_functional_classes_service(self) -> None:
        classes = national_services.list_hsm_functional_classes()
        self.assertGreaterEqual(len(classes), 5)
        class_names = [c["facility_class"] for c in classes]
        self.assertIn("rural_two_lane_two_way", class_names)
        self.assertIn("urban_arterial_divided", class_names)
        self.assertIn("motorway_freeway", class_names)

        r2u = next(c for c in classes if c["facility_class"] == "rural_two_lane_two_way")
        self.assertIn("beta_0", r2u)
        self.assertIn("beta_1", r2u)
        self.assertIn("overdispersion_k", r2u)

    def test_run_hsm_network_screening_service(self) -> None:
        segments = [
            {
                "segment_id": "corridor-seg-1",
                "observed_crashes": [10, 12, 11],
                "length_km": 1.5,
                "aadt": 6000,
            },
            {
                "segment_id": "corridor-seg-2",
                "observed_crashes": [0, 0, 1],
                "length_km": 1.0,
                "aadt": 2500,
            },
        ]
        result = national_services.run_hsm_network_screening(
            segments=segments,
            facility_class="rural_two_lane_two_way",
            calibration_c=1.0,
            network_label="state_corridor_sample",
        )

        self.assertEqual(result["network_label"], "state_corridor_sample")
        self.assertEqual(result["summary"]["total_segments_screened"], 2)
        self.assertEqual(len(result["results"]), 2)

        top_seg = result["results"][0]
        self.assertEqual(top_seg["segment_id"], "corridor-seg-1")
        self.assertEqual(top_seg["priority_rank"], 1)
        self.assertGreater(top_seg["psi_excess_crashes_annual"], 0.0)

    def test_run_irap_star_rating_service(self) -> None:
        segments = [
            {
                "segment_id": "seg-hwy-1",
                "length_km": 1.2,
                "aadt": 8000,
                "operating_speed_kmh": 80,
                "lanes": 2,
                "is_divided": False,
            },
            {
                "segment_id": "seg-urban-safe",
                "length_km": 0.5,
                "aadt": 3000,
                "operating_speed_kmh": 30,
                "lanes": 2,
                "is_divided": True,
                "has_sidewalk": True,
                "has_pedestrian_crossing": True,
                "has_segregated_cycle_facility": True,
            },
        ]
        result = national_services.run_irap_star_rating(
            segments=segments,
            network_label="irap_test_network",
        )
        self.assertEqual(result["network_label"], "irap_test_network")
        self.assertIn("un_global_target_4_summary", result)
        self.assertEqual(result["un_global_target_4_summary"]["total_segments_assessed"], 2)
        self.assertEqual(len(result["results"]), 2)

    def test_run_srip_generation_service(self) -> None:
        segments = [
            {
                "segment_id": "seg-hwy-sub3",
                "length_km": 2.0,
                "aadt": 12000,
                "operating_speed_kmh": 80,
                "lanes": 2,
                "is_divided": False,
            }
        ]
        result = national_services.run_srip_generation(
            segments=segments,
            value_of_statistical_life_eur=1_500_000.0,
            network_label="srip_test_network",
        )
        self.assertEqual(result["network_label"], "srip_test_network")
        self.assertIn("srip_investment_summary", result)
        self.assertGreater(result["srip_investment_summary"]["total_recommended_countermeasures"], 0)
        self.assertGreater(len(result["investment_plan"]), 0)
        top = result["investment_plan"][0]
        self.assertEqual(top["priority_rank"], 1)
        self.assertGreater(top["benefit_cost_ratio"], 1.0)

    def test_run_telematics_ingestion_service(self) -> None:
        observations = [
            {
                "event_id": "obs-1",
                "segment_id": "seg-1",
                "event_type": "harsh_braking",
                "peak_accel_g": -0.55,
                "initial_speed_kmh": 60,
                "final_speed_kmh": 20,
            }
        ]
        result = national_services.run_telematics_ingestion(
            observations=observations,
            is_waypoints=False,
            network_label="test_telematics_feed",
        )
        self.assertEqual(result["network_label"], "test_telematics_feed")
        self.assertEqual(result["total_near_miss_events_detected"], 1)
        self.assertEqual(result["event_breakdown"]["harsh_braking"], 1)

    def test_run_near_miss_screening_service(self) -> None:
        segments = [{"segment_id": "seg-1", "length_km": 1.0, "aadt": 8000}]
        events = [
            {
                "event_id": "evt-1",
                "segment_id": "seg-1",
                "event_type": "harsh_braking",
                "peak_accel_g": -0.65,
                "severity": "critical",
            }
        ]
        result = national_services.run_near_miss_screening(
            segments=segments,
            telematics_events=events,
            network_label="test_near_miss_screen",
        )
        self.assertEqual(result["network_label"], "test_near_miss_screen")
        self.assertEqual(result["summary"]["total_segments_screened"], 1)
        self.assertGreater(len(result["results"]), 0)
        self.assertEqual(result["results"][0]["segment_id"], "seg-1")

    def test_run_cip_portfolio_optimization_service(self) -> None:
        candidates = [
            {
                "project_id": "proj-cip-1",
                "segment_id": "seg-1",
                "countermeasure_code": "BARRIER",
                "base_cost_eur": 50_000,
                "expected_fsi_prevented_20yr": 10.0,
                "present_value_benefits_eur": 500_000,
                "benefit_cost_ratio": 10.0,
            }
        ]
        result = national_services.run_cip_portfolio_optimization(
            candidates=candidates,
            annual_budgets=[100_000.0, 100_000.0],
            network_label="test_cip_network",
        )
        self.assertEqual(result["network_label"], "test_cip_network")
        self.assertEqual(result["horizon_years"], 2)
        self.assertIn("financial_summary", result)
        self.assertEqual(result["financial_summary"]["total_projects_scheduled"], 1)

    def test_run_cv_road_audit_service(self) -> None:
        segments = [{"segment_id": "seg-cv-1", "length_km": 0.5, "aadt": 5000, "operating_speed_kmh": 50}]
        observations = [
            {
                "frame_id": "f-1",
                "segment_id": "seg-cv-1",
                "detections": [
                    {"detection_id": "d-1", "asset_class": "paved_sidewalk", "confidence": 0.9},
                    {"detection_id": "d-2", "asset_class": "pothole", "confidence": 0.85},
                ],
            }
        ]
        res = national_services.run_cv_road_audit(
            observations=observations,
            segments=segments,
            network_label="test_cv_network",
        )
        self.assertEqual(res["network_label"], "test_cv_network")
        self.assertEqual(res["summary"]["total_segments_audited"], 1)
        self.assertEqual(res["summary"]["total_inspection_frames"], 1)
        self.assertEqual(res["summary"]["total_assets_detected"], 2)
        self.assertEqual(res["summary"]["total_potholes_detected"], 1)
        self.assertEqual(len(res["results"]), 1)

    def test_run_microscopic_ssam_analysis_service(self) -> None:
        trajectories = [
            {
                "agent_id": "a1",
                "agent_type": "car",
                "junction_id": "j1",
                "points": [
                    {"time_sec": 0.0, "x_coord": 0.0, "y_coord": 10.0, "speed_mps": 10.0, "heading_deg": 0.0},
                    {"time_sec": 1.0, "x_coord": 0.0, "y_coord": 20.0, "speed_mps": 10.0, "heading_deg": 0.0},
                ],
            },
            {
                "agent_id": "a2",
                "agent_type": "pedestrian",
                "junction_id": "j1",
                "points": [
                    {"time_sec": 0.0, "x_coord": 5.0, "y_coord": 15.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    {"time_sec": 1.0, "x_coord": 0.0, "y_coord": 15.0, "speed_mps": 1.5, "heading_deg": 270.0},
                ],
            },
        ]
        res = national_services.run_microscopic_ssam_analysis(
            trajectories=trajectories,
            network_label="test_ssam_network",
        )
        self.assertEqual(res["network_label"], "test_ssam_network")
        self.assertEqual(res["summary"]["total_agents_analyzed"], 2)
        self.assertGreaterEqual(res["summary"]["total_conflicts_detected"], 1)
        self.assertGreaterEqual(res["summary"]["vru_conflicts_count"], 1)

    def test_run_st_gnn_risk_forecasting_service(self) -> None:
        nodes = [{"segment_id": "seg-g1", "length_km": 0.5, "functional_class": "urban_arterial"}]
        frames = [{"segment_id": "seg-g1", "precipitation_mm_h": 10.0, "surface_condition": "wet"}]
        res = national_services.run_st_gnn_risk_forecasting(
            nodes=nodes,
            time_series_frames=frames,
            horizons=[1, 6],
            network_label="test_gnn_service",
        )
        self.assertEqual(res["network_label"], "test_gnn_service")
        self.assertEqual(res["summary"]["total_segments_forecasted"], 1)
        self.assertEqual(res["summary"]["total_predictions_generated"], 2)

    def test_run_causal_countermeasure_evaluation_service(self) -> None:
        sample_data = [
            {
                "segment_id": f"seg-tr-{i}",
                "countermeasure_id": "SPEED_CAMERA",
                "treated": True,
                "baseline_crashes_pre": 7.0,
                "outcome_crashes_post": 3.2,
                "operating_speed_kmh": 68.0,
            }
            for i in range(8)
        ] + [
            {
                "segment_id": f"seg-ctrl-{i}",
                "countermeasure_id": "SPEED_CAMERA",
                "treated": False,
                "baseline_crashes_pre": 6.8,
                "outcome_crashes_post": 6.6,
                "operating_speed_kmh": 66.0,
            }
            for i in range(8)
        ]
        res = national_services.run_causal_countermeasure_evaluation(
            observational_data=sample_data,
            countermeasures=["SPEED_CAMERA"],
            network_label="test_causal_service",
        )
        self.assertEqual(res["network_label"], "test_causal_service")
        self.assertEqual(res["summary"]["total_observational_units"], 16)
        self.assertEqual(res["summary"]["total_countermeasures_evaluated"], 1)
        self.assertEqual(res["summary"]["statistically_significant_countermeasures"], 1)
        self.assertEqual(len(res["treatment_effects"]), 1)
        self.assertLess(res["treatment_effects"][0]["ate_crashes"], -2.0)

    def test_run_cits_v2x_actuation_service(self) -> None:
        alerts = [
            {
                "alert_id": "cits-test-1",
                "segment_id": "seg-test-1",
                "crash_probability": 0.82,
                "alert_tier": "critical",
                "primary_threat": "rain_storm",
                "precipitation_mm_h": 12.0,
                "surface_condition": "slippery",
                "speed_limit_kmh": 70.0,
            }
        ]
        res = national_services.run_cits_v2x_actuation(
            alerts_data=alerts,
            network_label="test_cits_service",
            sovereign_station_id="TEST-TMC-01",
        )
        self.assertEqual(res["network_label"], "test_cits_service")
        self.assertEqual(res["summary"]["total_vsl_commands"], 1)
        self.assertEqual(res["summary"]["total_denm_broadcasts"], 1)
        self.assertEqual(res["summary"]["total_ivim_mandates"], 1)
        self.assertEqual(res["summary"]["total_vms_displays"], 1)
        self.assertEqual(res["vsl_commands"][0]["mandatory_vsl_kmh"], 40)

    def test_run_synthetic_countermeasure_evaluation_service(self) -> None:
        res = national_services.run_synthetic_countermeasure_evaluation(
            junction_id="IT-BA-JNC-TEST-SVC",
            network_label="test_sim_service",
            baseline_template="BASELINE_SIGNALIZED",
            redesign_template="DUTCH_PROTECTED_JUNCTION",
            duration_seconds=10.0,
            vehicle_demand_vph=400.0,
            vru_demand_pph=80.0,
            random_seed=42,
        )
        self.assertEqual(res["network_label"], "test_sim_service")
        self.assertEqual(res["junction_id"], "IT-BA-JNC-TEST-SVC")
        self.assertIn("comparison", res)
        self.assertIn("baseline_summary", res)
        self.assertIn("redesign_summary", res)
        self.assertIn("appraisal_verdict", res["comparison"])
        self.assertIn(
            res["comparison"]["appraisal_verdict"],
            {"strongly_recommended", "recommended", "neutral", "not_recommended"},
        )

    def test_run_ai_act_conformity_audit_service(self) -> None:
        corridors = [
            {"segment_id": "c1", "geographic_tier": "urban_core", "predicted_risk": 0.75},
            {"segment_id": "c2", "geographic_tier": "peripheral", "predicted_risk": 0.70},
        ]
        res = national_services.run_ai_act_conformity_audit(
            corridors=corridors,
            network_label="test_compliance_service",
            protected_attribute="geographic_tier",
            accuracy_auc_roc=0.885,
            brier_score_loss=0.082,
        )
        self.assertEqual(res["network_label"], "test_compliance_service")
        self.assertEqual(res["total_articles_evaluated"], 7)
        self.assertIn("overall_conformity_verdict", res)
        self.assertIn("fairness_metrics", res)
        self.assertIn("article_evaluations", res)

    def test_run_federated_learning_service(self) -> None:
        nodes = [
            {"node_id": "n1", "concessionaire_name": "Op 1", "sample_size": 200},
            {"node_id": "n2", "concessionaire_name": "Op 2", "sample_size": 200},
        ]
        res = national_services.run_federated_learning_round(
            nodes_data=nodes,
            rounds_count=2,
            aggregation_method="fedavg",
            enable_dp=True,
            target_epsilon=2.0,
            network_label="test_fl_service",
        )
        self.assertEqual(res["network_label"], "test_fl_service")
        self.assertEqual(res["total_rounds"], 2)
        self.assertIn("final_auc", res)
        self.assertIn("final_global_weights", res)

    def test_run_micromobility_risk_audit_service(self) -> None:
        waypoints = [
            {
                "device_id": "scooter-01",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:00:00Z",
                "latitude": 41.1215,
                "longitude": 16.8710,
                "speed_mps": 3.8,
                "is_sidewalk": True,
                "segment_id": "seg-sparano",
            }
        ]
        res = national_services.run_micromobility_risk_audit(
            waypoints=waypoints,
            network_label="test_micromobility_service",
        )
        self.assertIn("micromobility_engine_version", res)
        self.assertIn("report", res)
        self.assertIn("events", res)
        self.assertEqual(res["report"]["network_label"], "test_micromobility_service")
        self.assertGreaterEqual(len(res["events"]), 1)

    def test_generate_sovereign_ministerial_dossier_service(self) -> None:
        res = national_services.generate_sovereign_ministerial_dossier(
            network_label="test_dossier_service",
            hsm_data={"total_segments": 100, "fatality_rate_per_100k": 3.5},
            irap_data={"target_4_compliance_pct": 12.0},
        )
        self.assertIn("dossier_engine_version", res)
        self.assertIn("dossier", res)
        self.assertIn("markdown_briefing", res)
        self.assertEqual(res["dossier"]["network_label"], "test_dossier_service")
        self.assertEqual(res["dossier"]["executive_kpis"]["population_fatality_rate_per_100k"], 3.5)

    def test_run_segment_panel_risk_evaluation_service(self) -> None:
        segs = [{"segment_id": "s1", "length_km": 1.0, "aadt": 10000.0, "spatial_group": "g1"}]
        crashes = [{"crash_id": "c1", "latitude": 0.0, "longitude": 0.0, "timestamp_utc": "2026-01-08T10:00:00Z"}]
        res = national_services.run_segment_panel_risk_evaluation(
            segments_data=segs,
            crashes_data=crashes,
            weeks_count=4,
            network_label="test_panel_service",
        )
        self.assertIn("panel_engine_version", res)
        self.assertIn("benchmark_report", res)
        self.assertEqual(res["network_label"], "test_panel_service")
        self.assertGreaterEqual(len(res["benchmark_report"]["model_benchmarks"]), 4)

    def test_tmc_playbook_services(self) -> None:
        pb_res = national_services.get_tmc_playbooks()
        self.assertIn("playbooks", pb_res)
        self.assertGreaterEqual(len(pb_res["playbooks"]), 5)

        inc_res = national_services.get_active_tmc_incidents_list()
        self.assertIn("incidents", inc_res)
        self.assertEqual(inc_res["total_active_incidents"], 0)

        trig_res = national_services.evaluate_tmc_trigger_service({
            "threat_type": "shockwave_congestion",
            "severity_tier": "severe",
            "crash_probability": 0.72,
            "speed_drop_kmh": 30.0,
            "corridor_id": "CORRIDOR-SS16-TEST",
        })
        self.assertEqual(trig_res["matched_playbook"]["playbook_id"], "PB_SHOCKWAVE_CONGESTION")
        self.assertEqual(trig_res["actions_count"], 5)

        with self.assertRaises(KeyError):
            national_services.actuate_tmc_playbook_service("missing", "test-operator")

    def test_cits_ivi_and_fleet_services(self) -> None:
        ivi_cat = national_services.get_cits_ivi_messages()
        self.assertIn("messages", ivi_cat)
        self.assertEqual(ivi_cat["total_messages"], 0)

        fleet_res = national_services.get_connected_fleet_telemetry(hazard_lat=41.1085, hazard_lon=16.8920)
        self.assertIn("fleet", fleet_res)
        self.assertEqual(fleet_res["total_connected_vehicles"], 0)

        compile_res = national_services.compile_cits_ivi_broadcast_service({
            "incident_id": "INC-TEST-001",
            "threat_type": "shockwave_congestion",
            "severity_tier": "critical",
            "corridor_id": "CORR-TEST",
            "location_name": "Test Corridor",
            "mandatory_vsl_kmh": 60,
        })
        self.assertIn("ivi_message", compile_res)
        self.assertIn("cv2x_envelopes", compile_res)
        self.assertEqual(len(compile_res["cv2x_envelopes"]), 2)

    def test_multi_incident_coordination_services(self) -> None:
        scenarios_res = national_services.get_multi_incident_scenarios()
        self.assertIn("scenarios", scenarios_res)
        self.assertEqual(scenarios_res["total_scenarios"], 0)
        with self.assertRaises(ValueError):
            national_services.evaluate_incident_conflict_spillover_service({})
        with self.assertRaises(ValueError):
            national_services.optimize_spillover_mitigation_service({})

        from tests.fixtures.incident_scenarios import multi_incident_scenarios
        scenario = multi_incident_scenarios()[0]
        payload = {**scenario, "incidents": [i.to_dict() for i in scenario["incidents"]]}
        result = national_services.evaluate_incident_conflict_spillover_service(payload)
        self.assertGreater(result["conflicts_count"], 0)
        plan = national_services.optimize_spillover_mitigation_service(payload)
        self.assertGreater(len(plan["flow_splits"]), 0)
        self.assertEqual(len(plan["sha256_plan_hash"]), 64)

    def test_app_routes_registered(self) -> None:
        """Verify all national, HSM, iRAP, telematics, CIP, CV, SSAM, ST-GNN, Causal, C-ITS, Simulation, AI Act, Federated, Micromobility, Dossier, Research Panel, Forensics, TMC, IVI, and Multi-Incident routes are registered."""
        routes = [route.path for route in self.app.routes if hasattr(route, "path")]  # type: ignore[attr-defined]
        self.assertIn("/v1/national/hierarchies/{country_code}", routes)
        self.assertIn("/v1/national/rollups/{country_code}", routes)
        self.assertIn("/v1/hsm/functional-classes", routes)
        self.assertIn("/v1/hsm/screen-network", routes)
        self.assertIn("/v1/irap/star-ratings", routes)
        self.assertIn("/v1/irap/investment-plans", routes)
        self.assertIn("/v1/telematics/ingest", routes)
        self.assertIn("/v1/telematics/near-misses", routes)
        self.assertIn("/v1/cip/optimize-schedule", routes)
        self.assertIn("/v1/cv/audit-roadway", routes)
        self.assertIn("/v1/ssam/analyze-conflicts", routes)
        self.assertIn("/v1/forecasting/st-gnn-predict", routes)
        self.assertIn("/v1/causal/evaluate-countermeasures", routes)
        self.assertIn("/v1/cits/generate-actuation", routes)
        self.assertIn("/v1/simulation/synthetic-countermeasure-eval", routes)
        self.assertIn("/v1/compliance/ai-act-audit", routes)
        self.assertIn("/v1/federated/train-round", routes)
        self.assertIn("/v1/micromobility/analyze-trips", routes)
        self.assertIn("/v1/reporting/ministerial-dossier", routes)
        self.assertIn("/v1/research/evaluate-panel-risk", routes)
        self.assertIn("/v1/telematics/events/publish", routes)
        self.assertIn("/v1/telematics/events/recent", routes)
        self.assertIn("/v1/forensics/cases", routes)
        self.assertIn("/v1/forensics/cases/{case_id}", routes)
        self.assertIn("/v1/forensics/cases/{case_id}/dossier", routes)
        self.assertIn("/v1/tmc/playbooks", routes)
        self.assertIn("/v1/tmc/active-incidents", routes)
        self.assertIn("/v1/tmc/evaluate-trigger", routes)
        self.assertIn("/v1/tmc/actuate-playbook", routes)
        self.assertIn("/v1/cits/ivi/messages", routes)
        self.assertIn("/v1/cits/fleets/telemetry", routes)
        self.assertIn("/v1/cits/ivi/compile", routes)
        self.assertIn("/v1/tmc/multi-incident/scenarios", routes)
        self.assertIn("/v1/tmc/multi-incident/evaluate-conflicts", routes)
        self.assertIn("/v1/tmc/multi-incident/optimize-mitigation", routes)




    def test_app_route_handlers_direct_invocation(self) -> None:
        """Directly invoke registered endpoint handlers with mock auth to verify response contracts."""
        handler_map = {
            route.path: route.endpoint
            for route in self.app.routes
            if hasattr(route, "path") and hasattr(route, "endpoint")
        }

        # 1. National Hierarchy handler
        h_func = handler_map["/v1/national/hierarchies/{country_code}"]
        h_res = h_func(country_code="IT", auth=self.mock_auth)
        self.assertEqual(h_res["api_version"], "v1")
        self.assertEqual(h_res["country_code"], "IT")

        # 2. National Rollups handler
        r_func = handler_map["/v1/national/rollups/{country_code}"]
        r_res = r_func(country_code="IT", auth=self.mock_auth)
        self.assertEqual(r_res["api_version"], "v1")
        self.assertIn("national_summary", r_res)

        # 3. HSM Functional Classes handler
        fc_func = handler_map["/v1/hsm/functional-classes"]
        fc_res = fc_func()
        self.assertEqual(fc_res["api_version"], "v1")
        self.assertIn("classes", fc_res)

        # 4. HSM Screen Network handler
        req = HsmScreeningRequest(
            organization_id="org-national-test",
            facility_class="rural_two_lane_two_way",
            calibration_factor_c=1.0,
            network_label="direct_test",
            segments=[{"segment_id": "s1", "observed_crashes": 3, "length_km": 1.0, "aadt": 4000}],
        )
        sn_func = handler_map["/v1/hsm/screen-network"]
        sn_res = sn_func(request=req, auth=self.mock_auth)
        self.assertEqual(sn_res["api_version"], "v1")
        self.assertEqual(sn_res["network_label"], "direct_test")
        self.assertEqual(len(sn_res["results"]), 1)

        # 5. iRAP Star Ratings handler
        irap_req = IrapStarRatingRequest(
            organization_id="org-national-test",
            network_label="direct_irap_test",
            segments=[{"segment_id": "s1", "length_km": 1.0, "aadt": 4000, "operating_speed_kmh": 60}],
        )
        irap_func = handler_map["/v1/irap/star-ratings"]
        irap_res = irap_func(request=irap_req, auth=self.mock_auth)
        self.assertEqual(irap_res["api_version"], "v1")
        self.assertEqual(irap_res["network_label"], "direct_irap_test")
        self.assertEqual(len(irap_res["results"]), 1)

        # 6. iRAP Investment Plans handler
        srip_req = SripGenerationRequest(
            organization_id="org-national-test",
            network_label="direct_srip_test",
            segments=[{"segment_id": "s1", "length_km": 1.0, "aadt": 4000, "operating_speed_kmh": 60}],
        )
        srip_func = handler_map["/v1/irap/investment-plans"]
        srip_res = srip_func(request=srip_req, auth=self.mock_auth)
        self.assertEqual(srip_res["api_version"], "v1")
        self.assertEqual(srip_res["network_label"], "direct_srip_test")
        self.assertIn("investment_plan", srip_res)

        # 7. Telematics Ingestion handler
        tele_req = TelematicsIngestionRequest(
            organization_id="org-national-test",
            network_label="direct_telematics_test",
            observations=[{"event_id": "e1", "segment_id": "s1", "event_type": "harsh_braking", "peak_accel_g": -0.55}],
        )
        tele_func = handler_map["/v1/telematics/ingest"]
        tele_res = tele_func(request=tele_req, auth=self.mock_auth)
        self.assertEqual(tele_res["api_version"], "v1")
        self.assertEqual(tele_res["network_label"], "direct_telematics_test")
        self.assertEqual(tele_res["total_near_miss_events_detected"], 1)

        # 8. Near-Miss Screening handler
        screen_req = NearMissScreeningRequest(
            organization_id="org-national-test",
            network_label="direct_near_miss_test",
            segments=[{"segment_id": "s1", "length_km": 1.0, "aadt": 4000}],
            telematics_events=[{"event_id": "e1", "segment_id": "s1", "event_type": "harsh_braking", "peak_accel_g": -0.55}],
        )
        screen_func = handler_map["/v1/telematics/near-misses"]
        screen_res = screen_func(request=screen_req, auth=self.mock_auth)
        self.assertEqual(screen_res["api_version"], "v1")
        self.assertEqual(screen_res["network_label"], "direct_near_miss_test")
        self.assertEqual(len(screen_res["results"]), 1)

        # 9. CIP Portfolio Optimization handler
        cip_req = CipOptimizationRequest(
            organization_id="org-national-test",
            network_label="direct_cip_test",
            annual_budgets=[100_000.0, 100_000.0],
            candidate_projects=[
                {
                    "project_id": "proj-cip-1",
                    "segment_id": "s1",
                    "countermeasure_code": "BARRIER",
                    "base_cost_eur": 50_000,
                    "expected_fsi_prevented_20yr": 10.0,
                    "present_value_benefits_eur": 500_000,
                    "benefit_cost_ratio": 10.0,
                }
            ],
        )
        cip_func = handler_map["/v1/cip/optimize-schedule"]
        cip_res = cip_func(request=cip_req, auth=self.mock_auth)
        self.assertEqual(cip_res["api_version"], "v1")
        self.assertEqual(cip_res["network_label"], "direct_cip_test")
        self.assertEqual(cip_res["horizon_years"], 2)
        self.assertEqual(len(cip_res["scheduled_projects"]), 1)

        # 10. CV Roadway Audit handler
        cv_req = CvRoadAuditRequest(
            organization_id="org-national-test",
            network_label="direct_cv_test",
            segments=[{"segment_id": "s1", "length_km": 1.0, "aadt": 4000}],
            observations=[
                {
                    "frame_id": "f1",
                    "segment_id": "s1",
                    "detections": [{"detection_id": "d1", "asset_class": "paved_sidewalk", "confidence": 0.95}],
                }
            ],
        )
        cv_func = handler_map["/v1/cv/audit-roadway"]
        cv_res = cv_func(request=cv_req, auth=self.mock_auth)
        self.assertEqual(cv_res["api_version"], "v1")
        self.assertEqual(cv_res["network_label"], "direct_cv_test")
        self.assertEqual(cv_res["summary"]["total_segments_audited"], 1)
        self.assertEqual(cv_res["summary"]["total_inspection_frames"], 1)
        self.assertEqual(len(cv_res["results"]), 1)

        # 11. Microscopic SSAM Conflicts handler
        ssam_req = MicroscopicSsamRequest(
            organization_id="org-national-test",
            network_label="direct_ssam_test",
            trajectories=[
                {
                    "agent_id": "a1",
                    "agent_type": "car",
                    "points": [
                        {"time_sec": 0.0, "x_coord": 0.0, "y_coord": 10.0, "speed_mps": 10.0, "heading_deg": 0.0},
                        {"time_sec": 1.0, "x_coord": 0.0, "y_coord": 20.0, "speed_mps": 10.0, "heading_deg": 0.0},
                    ],
                },
                {
                    "agent_id": "a2",
                    "agent_type": "pedestrian",
                    "points": [
                        {"time_sec": 0.0, "x_coord": 5.0, "y_coord": 15.0, "speed_mps": 1.5, "heading_deg": 270.0},
                        {"time_sec": 1.0, "x_coord": 0.0, "y_coord": 15.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    ],
                },
            ],
        )
        ssam_func = handler_map["/v1/ssam/analyze-conflicts"]
        ssam_res = ssam_func(request=ssam_req, auth=self.mock_auth)
        self.assertEqual(ssam_res["api_version"], "v1")
        self.assertEqual(ssam_res["network_label"], "direct_ssam_test")
        self.assertEqual(ssam_res["summary"]["total_agents_analyzed"], 2)
        self.assertGreaterEqual(ssam_res["summary"]["total_conflicts_detected"], 1)

        # 12. ST-GNN Risk Forecasting handler
        gnn_req = StGnnForecastRequest(
            organization_id="org-national-test",
            network_label="direct_gnn_test",
            nodes=[{"segment_id": "seg-g1", "length_km": 0.5}],
            time_series_frames=[{"segment_id": "seg-g1", "precipitation_mm_h": 5.0}],
            horizons=[1],
        )
        gnn_func = handler_map["/v1/forecasting/st-gnn-predict"]
        gnn_res = gnn_func(request=gnn_req, auth=self.mock_auth)
        self.assertEqual(gnn_res["api_version"], "v1")
        self.assertEqual(gnn_res["network_label"], "direct_gnn_test")
        self.assertEqual(gnn_res["summary"]["total_segments_forecasted"], 1)
        self.assertEqual(len(gnn_res["forecasts"]), 1)

        # 13. Causal Countermeasure Evaluation handler
        causal_req = CausalCountermeasureRequest(
            organization_id="org-national-test",
            network_label="direct_causal_test",
            observational_data=[
                {
                    "segment_id": f"seg-tr-{i}",
                    "countermeasure_id": "SPEED_CAMERA",
                    "treated": True,
                    "baseline_crashes_pre": 7.0,
                    "outcome_crashes_post": 3.2,
                    "operating_speed_kmh": 68.0,
                }
                for i in range(8)
            ] + [
                {
                    "segment_id": f"seg-ctrl-{i}",
                    "countermeasure_id": "SPEED_CAMERA",
                    "treated": False,
                    "baseline_crashes_pre": 6.8,
                    "outcome_crashes_post": 6.6,
                    "operating_speed_kmh": 66.0,
                }
                for i in range(8)
            ],
            countermeasures=["SPEED_CAMERA"],
        )
        causal_func = handler_map["/v1/causal/evaluate-countermeasures"]
        causal_res = causal_func(request=causal_req, auth=self.mock_auth)
        self.assertEqual(causal_res["api_version"], "v1")
        self.assertEqual(causal_res["network_label"], "direct_causal_test")
        self.assertEqual(causal_res["summary"]["total_observational_units"], 16)
        self.assertEqual(causal_res["summary"]["total_countermeasures_evaluated"], 1)
        self.assertEqual(causal_res["summary"]["statistically_significant_countermeasures"], 1)
        self.assertEqual(len(causal_res["treatment_effects"]), 1)
        self.assertLess(causal_res["treatment_effects"][0]["ate_crashes"], -2.0)

        # 14. C-ITS Actuation handler
        cits_req = CitsActuationRequest(
            organization_id="org-national-test",
            network_label="direct_cits_test",
            alerts=[
                {
                    "alert_id": "cits-direct-1",
                    "segment_id": "seg-direct-1",
                    "crash_probability": 0.85,
                    "alert_tier": "critical",
                    "primary_threat": "rain_storm_aquaplaning",
                    "precipitation_mm_h": 14.0,
                    "surface_condition": "slippery",
                    "speed_limit_kmh": 70.0,
                }
            ],
            sovereign_station_id="IT-MIT-TMC-TEST",
        )
        cits_func = handler_map["/v1/cits/generate-actuation"]
        cits_res = cits_func(request=cits_req, auth=self.mock_auth)
        self.assertEqual(cits_res["api_version"], "v1")
        self.assertEqual(cits_res["network_label"], "direct_cits_test")
        self.assertEqual(cits_res["summary"]["total_vsl_commands"], 1)
        self.assertEqual(cits_res["summary"]["total_denm_broadcasts"], 1)
        self.assertEqual(cits_res["summary"]["critical_actuations_count"], 1)
        self.assertEqual(cits_res["vsl_commands"][0]["mandatory_vsl_kmh"], 40)

        # 15. Synthetic Countermeasure Simulation handler
        sim_req = SyntheticCountermeasureEvalRequest(
            organization_id="org-national-test",
            network_label="direct_sim_test",
            junction_id="IT-BA-JNC-DIRECT",
            baseline_template="BASELINE_SIGNALIZED",
            redesign_template="DUTCH_PROTECTED_JUNCTION",
            duration_seconds=10.0,
            vehicle_demand_vph=400.0,
            vru_demand_pph=80.0,
            random_seed=42,
        )
        sim_func = handler_map["/v1/simulation/synthetic-countermeasure-eval"]
        sim_res = sim_func(request=sim_req, auth=self.mock_auth)
        self.assertEqual(sim_res["api_version"], "v1")
        self.assertEqual(sim_res["network_label"], "direct_sim_test")
        self.assertEqual(sim_res["junction_id"], "IT-BA-JNC-DIRECT")
        self.assertIn("comparison", sim_res)
        self.assertIn("baseline_summary", sim_res)
        self.assertIn("redesign_summary", sim_res)
        self.assertIn("appraisal_verdict", sim_res["comparison"])
        self.assertIn("trajectories", sim_res["baseline_summary"])
        self.assertIn("conflicts", sim_res["baseline_summary"])
        self.assertIn("trajectories", sim_res["redesign_summary"])
        self.assertIn("conflicts", sim_res["redesign_summary"])

        # 16. EU AI Act Compliance handler
        comp_req = AiActComplianceAuditRequest(
            organization_id="org-national-test",
            network_label="direct_compliance_test",
            corridors=[
                {"segment_id": "c1", "geographic_tier": "urban_core", "predicted_risk": 0.75},
                {"segment_id": "c2", "geographic_tier": "peripheral", "predicted_risk": 0.70},
            ],
            protected_attribute="geographic_tier",
            accuracy_auc_roc=0.885,
            brier_score_loss=0.082,
        )
        comp_func = handler_map["/v1/compliance/ai-act-audit"]
        comp_res = comp_func(request=comp_req, auth=self.mock_auth)
        self.assertEqual(comp_res["api_version"], "v1")
        self.assertEqual(comp_res["network_label"], "direct_compliance_test")
        self.assertEqual(comp_res["total_articles_evaluated"], 7)
        self.assertIn("overall_conformity_verdict", comp_res)
        self.assertIn("fairness_metrics", comp_res)
        self.assertIn("article_evaluations", comp_res)

        # 17. Federated Training Round handler
        fl_req = FederatedTrainingRoundRequest(
            organization_id="org-national-test",
            network_label="direct_fl_test",
            nodes_data=[
                {"node_id": "n1", "concessionaire_name": "Op 1", "sample_size": 200},
                {"node_id": "n2", "concessionaire_name": "Op 2", "sample_size": 200},
            ],
            rounds_count=2,
            aggregation_method="fedavg",
            enable_dp=True,
            target_epsilon=2.0,
        )
        fl_func = handler_map["/v1/federated/train-round"]
        fl_res = fl_func(request=fl_req, auth=self.mock_auth)
        self.assertEqual(fl_res["api_version"], "v1")
        self.assertEqual(fl_res["network_label"], "direct_fl_test")
        self.assertEqual(fl_res["total_rounds"], 2)
        self.assertIn("final_auc", fl_res)
        self.assertIn("final_global_weights", fl_res)

        # 18. Micromobility Audit handler
        mm_req = MicromobilityAuditRequest(
            organization_id="org-national-test",
            network_label="direct_mm_test",
            waypoints=[
                {
                    "device_id": "scooter-01",
                    "vehicle_type": "e_scooter",
                    "timestamp": "2026-09-17T10:00:00Z",
                    "latitude": 41.1215,
                    "longitude": 16.8710,
                    "speed_mps": 3.8,
                    "is_sidewalk": True,
                    "segment_id": "seg-sparano",
                }
            ],
            segments_data=[
                {"segment_id": "seg-sparano", "total_trips": 100, "total_distance_km": 50.0, "nominal_bicycle_srs": 18.0}
            ],
        )
        mm_func = handler_map["/v1/micromobility/analyze-trips"]
        mm_res = mm_func(request=mm_req, auth=self.mock_auth)
        self.assertEqual(mm_res["api_version"], "v1")
        self.assertIn("report", mm_res)
        self.assertIn("events", mm_res)
        self.assertEqual(mm_res["report"]["network_label"], "direct_mm_test")
        self.assertGreaterEqual(len(mm_res["events"]), 1)

        # 19. Ministerial Dossier handler
        dos_req = MinisterialDossierRequest(
            organization_id="org-national-test",
            network_label="direct_dos_test",
            hsm_data={"total_segments": 50, "fatality_rate_per_100k": 4.1},
        )
        dos_func = handler_map["/v1/reporting/ministerial-dossier"]
        dos_res = dos_func(request=dos_req, auth=self.mock_auth)
        self.assertEqual(dos_res["api_version"], "v1")
        self.assertIn("dossier", dos_res)
        self.assertIn("markdown_briefing", dos_res)
        self.assertEqual(dos_res["dossier"]["network_label"], "direct_dos_test")

        # 20. Research Panel Risk Evaluation handler
        pnl_req = ResearchPanelRiskRequest(
            organization_id="org-national-test",
            network_label="direct_pnl_test",
            segments_data=[{"segment_id": "seg-1", "length_km": 1.0, "aadt": 12000.0, "spatial_group": "g1"}],
            crashes_data=[{"crash_id": "cr-1", "latitude": 0.0, "longitude": 0.0, "timestamp_utc": "2026-01-08T10:00:00Z"}],
            weeks_count=4,
        )
        pnl_func = handler_map["/v1/research/evaluate-panel-risk"]
        pnl_res = pnl_func(request=pnl_req, auth=self.mock_auth)
        self.assertEqual(pnl_res["api_version"], "v1")
        self.assertIn("panel_summary", pnl_res)
        self.assertIn("benchmark_report", pnl_res)
        self.assertEqual(pnl_res["network_label"], "direct_pnl_test")

        # 21. Telematics Stream Publish handler
        pub_req = TelematicsEventPublishRequest(
            organization_id="org-national-test",
            segment_id="seg-bari-direct",
            latitude=41.12,
            longitude=16.87,
            peak_accel_g=-0.58,
        )
        pub_func = handler_map["/v1/telematics/events/publish"]
        pub_res = pub_func(request=pub_req, auth=self.mock_auth)
        self.assertEqual(pub_res["api_version"], "v1")
        self.assertEqual(pub_res["status"], "broadcasted")
        self.assertEqual(pub_res["event"]["event_type"], "harsh_braking")
        self.assertEqual(pub_res["event"]["severity"], "severe")

        # 22. Telematics Recent Events handler
        rec_func = handler_map["/v1/telematics/events/recent"]
        rec_res = rec_func(limit=10, auth=self.mock_auth)
        self.assertEqual(rec_res["api_version"], "v1")
        self.assertGreaterEqual(rec_res["total_events"], 1)

        # A clean install never substitutes sample observations.
        for path, key in [
            ("/v1/forensics/cases", "cases"),
            ("/v1/tmc/active-incidents", "incidents"),
            ("/v1/cits/ivi/messages", "messages"),
            ("/v1/tmc/multi-incident/scenarios", "scenarios"),
        ]:
            result = handler_map[path](auth=self.mock_auth)
            self.assertEqual(result[key], [])
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as missing:
            handler_map["/v1/forensics/cases/{case_id}"]("missing", auth=self.mock_auth)
        self.assertEqual(missing.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()




