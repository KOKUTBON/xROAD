"""Unit tests for Dynamic Multi-Incident Conflict & Congestion Spillover Manager."""

import unittest
from tests.fixtures.incident_scenarios import multi_incident_scenarios as get_prepackaged_multi_incident_scenarios

from road_risk_modeling.incident_coordination_engine import (
    ActiveIncidentNode,
    CoordinatedSpilloverMitigationPlan,
    DiversionFlowSplit,
    LwrSpilloverPrediction,
    RerouteConflict,
    compute_lwr_shockwave_dynamics,
    detect_rerouting_conflicts,
    generate_coordinated_mitigation_plan,
    optimize_diversion_flow_splits,
    COORDINATION_CONTRACT_VERSION,
    COORDINATION_ENGINE_VERSION,
)


class TestIncidentCoordinationEngine(unittest.TestCase):
    def setUp(self):
        self.scenarios = get_prepackaged_multi_incident_scenarios()

    def test_lwr_shockwave_dynamics_calculation(self):
        """Verify LWR shockwave calculation, queue growth, and upstream reach time."""
        # 2500 vph inflow against 1000 vph residual bottleneck capacity
        lwr = compute_lwr_shockwave_dynamics(
            incoming_flow_vph=2500.0,
            residual_capacity_vph=1000.0,
            free_flow_speed_kmh=85.0,
            jam_density_vpk=140.0,
            upstream_critical_distance_km=2.1,
        )

        self.assertIsInstance(lwr, LwrSpilloverPrediction)
        self.assertGreater(lwr.primary_queue_growth_km_h, 0.0)
        self.assertLess(lwr.shockwave_velocity_mps, 0.0)  # Upstream backward shockwave
        self.assertGreater(lwr.time_to_upstream_bottleneck_min, 0.0)
        self.assertLess(lwr.time_to_upstream_bottleneck_min, 30.0)
        self.assertEqual(lwr.spillover_risk_tier, "CRITICAL_IMMINENT")

        # Horizons must be monotonically increasing
        self.assertLess(lwr.queue_length_km_15m, lwr.queue_length_km_30m)
        self.assertLess(lwr.queue_length_km_30m, lwr.queue_length_km_60m)

    def test_lwr_nominal_condition_when_capacity_sufficient(self):
        """When capacity exceeds demand, no backward queue forms."""
        lwr = compute_lwr_shockwave_dynamics(
            incoming_flow_vph=1000.0,
            residual_capacity_vph=1800.0,
        )
        self.assertEqual(lwr.primary_queue_growth_km_h, 0.0)
        self.assertEqual(lwr.shockwave_velocity_mps, 0.0)
        self.assertEqual(lwr.spillover_risk_tier, "NOMINAL")
        self.assertEqual(lwr.time_to_upstream_bottleneck_min, 999.0)

    def test_detect_rerouting_conflicts_direct_collision(self):
        """Verify detection of DIRECT_COLLISION_COURSE when detour leads to another active incident."""
        incidents = [
            ActiveIncidentNode(
                incident_id="INC-01",
                corridor_id="corridor_a",
                location_name="Corridor A",
                latitude=41.1,
                longitude=16.8,
                severity="critical",
                capacity_reduction_pct=60.0,
                incoming_flow_vph=2000.0,
                residual_capacity_vph=800.0,
                nominal_capacity_vph=2000.0,
                candidate_detour_corridors=["corridor_b", "corridor_c"],
            ),
            ActiveIncidentNode(
                incident_id="INC-02",
                corridor_id="corridor_b",
                location_name="Corridor B",
                latitude=41.12,
                longitude=16.82,
                severity="severe",
                capacity_reduction_pct=50.0,
                incoming_flow_vph=800.0,
                residual_capacity_vph=400.0,
                nominal_capacity_vph=1000.0,
                candidate_detour_corridors=["corridor_c"],
            ),
        ]

        conflicts = detect_rerouting_conflicts(incidents)
        self.assertGreaterEqual(len(conflicts), 1)
        collision_conflicts = [c for c in conflicts if c.conflict_type == "DIRECT_COLLISION_COURSE"]
        self.assertEqual(len(collision_conflicts), 1)
        self.assertEqual(collision_conflicts[0].conflicting_corridor_id, "corridor_b")
        self.assertGreaterEqual(collision_conflicts[0].severity_score, 0.90)

    def test_detect_secondary_spillover_gridlock(self):
        """Verify detection of SECONDARY_SPILLOVER_GRIDLOCK when multiple incidents share a detour corridor."""
        incidents = [
            ActiveIncidentNode(
                incident_id="INC-X",
                corridor_id="corridor_x",
                location_name="Corridor X",
                latitude=41.1,
                longitude=16.8,
                severity="critical",
                capacity_reduction_pct=70.0,
                incoming_flow_vph=1800.0,
                residual_capacity_vph=500.0,
                nominal_capacity_vph=1800.0,
                candidate_detour_corridors=["corridor_shared"],
            ),
            ActiveIncidentNode(
                incident_id="INC-Y",
                corridor_id="corridor_y",
                location_name="Corridor Y",
                latitude=41.15,
                longitude=16.85,
                severity="severe",
                capacity_reduction_pct=60.0,
                incoming_flow_vph=1500.0,
                residual_capacity_vph=600.0,
                nominal_capacity_vph=1500.0,
                candidate_detour_corridors=["corridor_shared"],
            ),
        ]

        conflicts = detect_rerouting_conflicts(incidents, {"corridor_shared": 1000.0})
        gridlock_conflicts = [c for c in conflicts if c.conflict_type == "SECONDARY_SPILLOVER_GRIDLOCK"]
        self.assertEqual(len(gridlock_conflicts), 1)
        self.assertEqual(gridlock_conflicts[0].conflicting_corridor_id, "corridor_shared")

    def test_optimize_diversion_flow_splits_sum_to_100_and_exclude_blocked(self):
        """Verify flow splits sum to exactly 100% and blocked corridors receive 0%."""
        primary = ActiveIncidentNode(
            incident_id="INC-SS16",
            corridor_id="corridor_ss16",
            location_name="Tangenziale SS16",
            latitude=41.107,
            longitude=16.892,
            severity="critical",
            capacity_reduction_pct=60.0,
            incoming_flow_vph=2400.0,
            residual_capacity_vph=1000.0,
            nominal_capacity_vph=2400.0,
            candidate_detour_corridors=["corridor_gentile", "corridor_japigia", "corridor_trieste"],
        )

        alternatives = [
            {"corridor_id": "corridor_gentile", "corridor_name": "Via Gentile", "capacity_vph": 1200.0, "speed_kmh": 45.0, "length_km": 4.0},
            {"corridor_id": "corridor_japigia", "corridor_name": "Japigia Bypass", "capacity_vph": 1600.0, "speed_kmh": 60.0, "length_km": 5.0},
            {"corridor_id": "corridor_trieste", "corridor_name": "Lungomare Trieste", "capacity_vph": 1100.0, "speed_kmh": 40.0, "length_km": 6.0},
        ]

        conflict = RerouteConflict(
            conflict_id="CONF-01",
            incident_a_id="INC-SS16",
            incident_b_id="INC-GENTILE",
            conflicting_corridor_id="corridor_gentile",
            conflict_type="DIRECT_COLLISION_COURSE",
            severity_score=0.95,
            explanation="Via Gentile is blocked.",
            recommended_remedy="Avoid Gentile.",
        )

        splits, hours_saved, crash_reduction = optimize_diversion_flow_splits(
            primary_incident=primary,
            alternative_corridors=alternatives,
            conflicts=[conflict],
        )

        # Total split percentages must sum to exactly 100.0%
        total_pct = sum(s.recommended_split_pct for s in splits)
        self.assertAlmostEqual(total_pct, 100.0, places=1)

        # Blocked corridor (corridor_gentile) must NOT be present in diversion allocation
        split_corridors = [s.corridor_id for s in splits]
        self.assertNotIn("corridor_gentile", split_corridors)
        self.assertIn("corridor_ss16", split_corridors)
        self.assertIn("corridor_japigia", split_corridors)
        self.assertIn("corridor_trieste", split_corridors)

        self.assertGreater(hours_saved, 0.0)
        self.assertGreater(crash_reduction, 0.0)

    def test_synthetic_scenarios_and_mitigation_plan(self):
        """Verify prepackaged scenarios execute correctly and yield valid mitigation plans with SHA-256 hash."""
        self.assertGreaterEqual(len(self.scenarios), 2)
        scenario1 = self.scenarios[0]
        self.assertEqual(scenario1["scenario_id"], "scenario_ring_road_bottleneck")

        plan = generate_coordinated_mitigation_plan(
            scenario_id=scenario1["scenario_id"],
            incidents=scenario1["incidents"],
            alternative_corridors=scenario1["alternative_corridors"],
            upstream_distance_km=scenario1["upstream_distance_km"],
        )

        self.assertIsInstance(plan, CoordinatedSpilloverMitigationPlan)
        self.assertGreaterEqual(plan.conflicts_count, 1)
        self.assertTrue(plan.sha256_plan_hash)
        self.assertEqual(len(plan.sha256_plan_hash), 64)
        self.assertGreater(plan.total_vehicle_hours_saved, 100.0)
        self.assertGreater(plan.secondary_crash_risk_reduction_pct, 15.0)

        # Dictionary serialization
        d = plan.to_dict()
        self.assertEqual(d["contract_version"], COORDINATION_CONTRACT_VERSION)
        self.assertEqual(d["engine_version"], COORDINATION_ENGINE_VERSION)
        self.assertIn("conflicts", d)
        self.assertIn("flow_splits", d)
        self.assertIn("lwr_prediction", d)


if __name__ == "__main__":
    unittest.main()
