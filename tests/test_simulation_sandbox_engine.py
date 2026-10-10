"""Tests for Synthetic Countermeasure Sandbox & Digital Twin Micro-Simulation Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.simulation_sandbox_engine import (
    REDESIGN_TEMPLATES,
    SIM_CONTRACT_VERSION,
    SIM_SANDBOX_VERSION,
    CountermeasureAppraisalComparison,
    SimulationRunResult,
    SimulationScenarioConfig,
    _idm_acceleration,
    evaluate_synthetic_countermeasure_pair,
    export_simulation_sandbox_artifacts,
    run_micro_simulation_scenario,
)


class TestSimulationSandboxEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.test_junction_id = "IT-BA-JNC-TEST"
        self.baseline_config = SimulationScenarioConfig(
            scenario_name="test_baseline_signalized",
            junction_id=self.test_junction_id,
            geometry_template="BASELINE_SIGNALIZED",
            duration_seconds=15.0,
            time_step_seconds=0.2,
            vehicle_demand_vph=600.0,
            vru_demand_pph=100.0,
            free_flow_speed_kmh=50.0,
            random_seed=42,
        )
        self.dutch_config = SimulationScenarioConfig(
            scenario_name="test_dutch_protected",
            junction_id=self.test_junction_id,
            geometry_template="DUTCH_PROTECTED_JUNCTION",
            duration_seconds=15.0,
            time_step_seconds=0.2,
            vehicle_demand_vph=600.0,
            vru_demand_pph=100.0,
            free_flow_speed_kmh=50.0,
            random_seed=42,
        )

    def test_idm_acceleration_physics(self) -> None:
        """Test car-following acceleration dynamics under various headways and speeds."""
        # 1. Free-flow acceleration from low speed with large headway
        acc_free = _idm_acceleration(v=5.0, v0=13.89, s=1000.0, delta_v=0.0)
        self.assertGreater(acc_free, 0.5)

        # 2. Cruising at desired speed with open roadway
        acc_cruise = _idm_acceleration(v=13.89, v0=13.89, s=1000.0, delta_v=0.0)
        self.assertAlmostEqual(acc_cruise, 0.0, delta=0.1)

        # 3. Emergency braking when vehicle ahead is close and slower
        acc_brake = _idm_acceleration(v=12.0, v0=13.89, s=3.0, delta_v=8.0)
        self.assertLess(acc_brake, -1.0)

        # 4. Negative speed edge case
        acc_neg = _idm_acceleration(v=-5.0, v0=13.89, s=100.0, delta_v=0.0)
        self.assertGreater(acc_neg, 0.0)

    def test_run_micro_simulation_scenario_baseline(self) -> None:
        """Test micro-simulation scenario generation under baseline signalized geometry."""
        result = run_micro_simulation_scenario(self.baseline_config)
        self.assertIsInstance(result, SimulationRunResult)
        self.assertEqual(result.scenario_name, "test_baseline_signalized")
        self.assertEqual(result.geometry_template, "BASELINE_SIGNALIZED")
        self.assertEqual(result.junction_id, self.test_junction_id)
        self.assertGreater(result.total_agents_simulated, 0)
        self.assertGreater(result.total_vehicles, 0)
        self.assertGreater(result.total_vrus, 0)
        self.assertEqual(len(result.trajectories), result.total_agents_simulated)
        self.assertGreaterEqual(result.total_conflicts_count, 0)
        self.assertGreaterEqual(result.min_ttc_seconds, 0.0)
        self.assertGreaterEqual(result.max_drac_mps2, 0.0)

        data = result.to_dict()
        self.assertIn("total_conflicts_count", data)
        self.assertIn("critical_conflicts_count", data)
        self.assertIn("vru_conflicts_count", data)
        self.assertNotIn("trajectories", data)

        data_with_traj = result.to_dict(include_trajectories=True)
        self.assertIn("trajectories", data_with_traj)
        self.assertIn("conflicts", data_with_traj)
        self.assertEqual(len(data_with_traj["trajectories"]), result.total_agents_simulated)
        if data_with_traj["trajectories"]:
            self.assertIn("points", data_with_traj["trajectories"][0])
            self.assertIn("agent_type", data_with_traj["trajectories"][0])

    def test_run_micro_simulation_other_templates(self) -> None:
        """Test simulation runs under turbo-roundabout and road diet geometry templates."""
        roundabout_cfg = SimulationScenarioConfig(
            scenario_name="test_turbo_roundabout",
            junction_id=self.test_junction_id,
            geometry_template="TURBO_ROUNDABOUT",
            duration_seconds=10.0,
            time_step_seconds=0.2,
            random_seed=101,
        )
        res_roundabout = run_micro_simulation_scenario(roundabout_cfg)
        self.assertEqual(res_roundabout.geometry_template, "TURBO_ROUNDABOUT")
        self.assertGreater(res_roundabout.total_agents_simulated, 0)

        diet_cfg = SimulationScenarioConfig(
            scenario_name="test_road_diet",
            junction_id=self.test_junction_id,
            geometry_template="ROAD_DIET_REFUGE",
            duration_seconds=10.0,
            time_step_seconds=0.2,
            random_seed=202,
        )
        res_diet = run_micro_simulation_scenario(diet_cfg)
        self.assertEqual(res_diet.geometry_template, "ROAD_DIET_REFUGE")
        self.assertGreater(res_diet.total_agents_simulated, 0)

    def test_evaluate_synthetic_countermeasure_pair(self) -> None:
        """Test side-by-side comparative countermeasure appraisal."""
        base_res, redesign_res, comparison = evaluate_synthetic_countermeasure_pair(
            junction_id=self.test_junction_id,
            baseline_template="BASELINE_SIGNALIZED",
            redesign_template="DUTCH_PROTECTED_JUNCTION",
            duration_seconds=15.0,
            vehicle_demand_vph=600.0,
            vru_demand_pph=100.0,
            random_seed=42,
        )
        self.assertIsInstance(base_res, SimulationRunResult)
        self.assertIsInstance(redesign_res, SimulationRunResult)
        self.assertIsInstance(comparison, CountermeasureAppraisalComparison)

        self.assertEqual(comparison.junction_id, self.test_junction_id)
        self.assertEqual(comparison.baseline_template, "BASELINE_SIGNALIZED")
        self.assertEqual(comparison.redesign_template, "DUTCH_PROTECTED_JUNCTION")
        self.assertIn(
            comparison.appraisal_verdict,
            {"strongly_recommended", "recommended", "neutral", "not_recommended"},
        )
        self.assertTrue(len(comparison.primary_safety_benefit) > 0)

        comp_dict = comparison.to_dict()
        self.assertIn("percent_conflict_reduction", comp_dict)
        self.assertIn("percent_vru_conflict_reduction", comp_dict)
        self.assertIn("absolute_conflict_reduction", comp_dict)

    def test_export_simulation_sandbox_artifacts(self) -> None:
        """Test artifact export bundle, CSV, Markdown briefing, and SHA-256 sovereign manifest."""
        base_res, redesign_res, comparison = evaluate_synthetic_countermeasure_pair(
            junction_id=self.test_junction_id,
            baseline_template="BASELINE_SIGNALIZED",
            redesign_template="DUTCH_PROTECTED_JUNCTION",
            duration_seconds=15.0,
            vehicle_demand_vph=600.0,
            vru_demand_pph=100.0,
            random_seed=42,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_files = export_simulation_sandbox_artifacts(
                baseline_result=base_res,
                redesign_result=redesign_res,
                comparison=comparison,
                output_dir=tmpdir,
                network_label="test_junction_eval",
            )

            for key in ["comparison_csv", "trajectories_json", "bundle_json", "briefing_md", "manifest"]:
                self.assertIn(key, out_files)
                fpath = Path(out_files[key])
                self.assertTrue(fpath.exists(), f"File {fpath} does not exist")
                self.assertGreater(fpath.stat().st_size, 0)

            # Validate Manifest
            manifest_content = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest_content["artifact_family"], "synthetic_countermeasure_micro_simulation")
            self.assertEqual(manifest_content["sim_sandbox_version"], SIM_SANDBOX_VERSION)
            self.assertEqual(manifest_content["junction_id"], self.test_junction_id)
            self.assertIn("comparison_csv", manifest_content["files"])
            self.assertIn("briefing_md", manifest_content["files"])

            # Validate Briefing Markdown
            briefing_text = Path(out_files["briefing_md"]).read_text(encoding="utf-8")
            self.assertIn("Synthetic Countermeasure Simulation Appraisal", briefing_text)
            self.assertIn(self.test_junction_id, briefing_text)
            self.assertIn("DUTCH_PROTECTED_JUNCTION", briefing_text)


if __name__ == "__main__":
    unittest.main()
