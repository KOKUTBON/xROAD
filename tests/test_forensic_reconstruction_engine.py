"""Tests for Automated Incident Reconstruction & Forensic Black-Box Playback Engine."""

from __future__ import annotations

import unittest

from road_risk_modeling.forensic_reconstruction_engine import (
    BENCHMARK_PRT_AASHTO_S,
    BENCHMARK_PRT_ALERT_S,
    ForensicAgentTrace,
    ForensicTelemetrySample,
    compute_kinetic_forensics,
    compute_liability_attribution,
    evaluate_counterfactual_scenarios,
    ForensicInputError,
    build_forensic_case_from_payload,
    generate_judicial_evidence_dossier,
)

from tests.fixtures.forensic_scenarios import (
    ALL_SCENARIOS,
    bus_vs_scooter_angle_collision,
    car_vs_pedestrian_crosswalk,
)


class TestForensicReconstructionEngine(unittest.TestCase):
    """Test suite for forensic kinetic physics, PRT analysis, and counterfactuals."""

    def setUp(self) -> None:
        self.cases = {
            case.case_id: case
            for case in (build_forensic_case_from_payload(scenario()) for scenario in ALL_SCENARIOS)
        }

    def test_cases_build_from_submitted_telemetry(self) -> None:
        """Every synthetic scenario reconstructs from a plain JSON payload."""
        self.assertEqual(set(self.cases), {"CASE-SYN-001", "CASE-SYN-002", "CASE-SYN-003"})
        case1 = self.cases["CASE-SYN-001"]
        self.assertEqual(case1.primary_agent.agent_id, "bus-1")
        self.assertEqual(case1.secondary_agent.agent_id, "scooter-1")
        self.assertEqual(case1.speed_limit_kph, 30.0)

    def test_reconstruction_is_deterministic(self) -> None:
        first = build_forensic_case_from_payload(bus_vs_scooter_angle_collision())
        second = build_forensic_case_from_payload(bus_vs_scooter_angle_collision())
        self.assertEqual(first.sha256_evidence_hash, second.sha256_evidence_hash)

    def test_rejects_telemetry_that_cannot_support_a_reconstruction(self) -> None:
        payload = bus_vs_scooter_angle_collision()
        payload["primary_agent"]["samples"] = payload["primary_agent"]["samples"][:2]
        with self.assertRaises(ForensicInputError):
            build_forensic_case_from_payload(payload)

        payload = bus_vs_scooter_angle_collision()
        payload["secondary_agent"]["samples"] = [
            sample for sample in payload["secondary_agent"]["samples"] if sample["time_sec"] < 0
        ]
        with self.assertRaises(ForensicInputError):
            build_forensic_case_from_payload(payload)

        payload = bus_vs_scooter_angle_collision()
        del payload["hazard_emergence_time_s"]
        with self.assertRaises(ForensicInputError):
            build_forensic_case_from_payload(payload)

    def test_kinetic_momentum_and_energy_conservation(self) -> None:
        """Verify momentum conservation Delta-V and plastic deformation energy dissipation."""
        case = self.cases["CASE-SYN-001"]
        metrics = case.kinetic_metrics

        # Initial speed 44 km/h exceeded 30 km/h speed limit
        self.assertAlmostEqual(metrics.initial_speed_kph, 44.0, delta=1.0)
        self.assertLess(metrics.impact_speed_kph, metrics.initial_speed_kph)
        self.assertGreater(metrics.delta_v_primary_kph, 0.0)
        self.assertGreater(metrics.delta_v_secondary_kph, metrics.delta_v_primary_kph)

        # Bus (12000 kg) vs Scooter (105 kg): lighter secondary agent experiences significant Delta-V
        self.assertGreater(metrics.delta_v_secondary_kph, 5.0)
        self.assertGreater(metrics.energy_dissipated_kj, 0.0)
        self.assertGreater(metrics.equivalent_barrier_speed_kph, 0.0)

    def test_driver_prt_calculation_and_aashto_benchmarks(self) -> None:
        """Verify perception-reaction time extraction and benchmark deviation."""
        case = self.cases["CASE-SYN-001"]
        metrics = case.kinetic_metrics

        # Hazard at -3.2s, brake onset at -1.4s -> PRT = 1.8s
        self.assertAlmostEqual(metrics.driver_prt_seconds, 1.8, delta=0.2)
        # Delayed relative to AASHTO 1.5s
        self.assertGreater(metrics.prt_benchmark_deviation_s, 0.0)
        self.assertGreater(metrics.drac_required_mps2, 0.0)

    def test_counterfactual_scenarios_evaluation(self) -> None:
        """Verify counterfactual collision avoidance outcomes for AEB, speed compliance, and sightlines."""
        case = self.cases["CASE-SYN-001"]
        scenarios = case.counterfactual_scenarios

        self.assertEqual(len(scenarios), 3)
        aeb = next(s for s in scenarios if s.scenario_id == "SCENARIO_A_AEB")
        speed = next(s for s in scenarios if s.scenario_id == "SCENARIO_B_SPEED_COMPLIANCE")
        sightline = next(s for s in scenarios if s.scenario_id == "SCENARIO_C_GEOMETRIC_SIGHTLINE")

        # Under AEB (0.25s reaction + -8.5 m/s²), collision is fully avoided with positive margin
        self.assertTrue(aeb.collision_avoided)
        self.assertGreater(aeb.clearance_margin_m, 0.0)
        self.assertEqual(aeb.counterfactual_impact_speed_kph, 0.0)
        self.assertEqual(aeb.injury_risk_reduction_pct, 100.0)

        # Under 30 km/h speed compliance, collision is avoided
        self.assertTrue(speed.collision_avoided)
        self.assertGreater(speed.clearance_margin_m, 0.0)

        # Verify ghost trajectories generated
        self.assertGreater(len(aeb.ghost_trajectory_samples), 0)
        self.assertGreater(len(speed.ghost_trajectory_samples), 0)

    def test_liability_attribution(self) -> None:
        """Verify quantification of excessive speed, PRT latency, and sightline factors."""
        case = self.cases["CASE-SYN-001"]
        liability = case.liability_factors

        self.assertIn("excessive_speed_contribution_pct", liability)
        self.assertIn("perception_delay_contribution_pct", liability)
        self.assertIn("infrastructure_sightline_deficit_pct", liability)

        total_sum = sum(liability.values())
        self.assertAlmostEqual(total_sum, 100.0, delta=0.5)

    def test_judicial_evidence_dossier_and_integrity_hash(self) -> None:
        """Verify forensic markdown dossier contains judicial metadata and cryptographic SHA-256."""
        case = self.cases["CASE-SYN-002"]
        self.assertTrue(case.judicial_summary_md.startswith("# PERIZIA TECNICO-FORENSE"))
        self.assertIn(case.case_id, case.judicial_summary_md)
        self.assertIn("SHA-256", case.judicial_summary_md)
        self.assertEqual(len(case.sha256_evidence_hash), 64)

        # Serialization to dictionary
        d = case.to_dict(include_samples=True)
        self.assertEqual(d["case_id"], "CASE-SYN-002")
        self.assertIn("kinetic_metrics", d)
        self.assertIn("counterfactual_scenarios", d)


if __name__ == "__main__":
    unittest.main()
