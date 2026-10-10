"""Unit tests for Microscopic Trajectory SSAM & Multi-Agent VRU Conflict Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.micro_ssam_engine import (
    SSAM_CONTRACT_VERSION,
    SSAM_ENGINE_VERSION,
    AgentTrajectory,
    JunctionConflictSummary,
    MicroscopicConflictEvent,
    TrajectoryPoint,
    aggregate_conflicts_to_junctions,
    detect_trajectory_conflicts,
    export_micro_ssam_artifacts,
    parse_agent_trajectories,
)


class TestMicroSsamEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_trajectories = [
            # 1. Car traveling south toward intersection (x=50, y from 80 down to 20)
            {
                "agent_id": "car-01",
                "agent_type": "car",
                "junction_id": "jnc-101",
                "segment_id": "seg-north",
                "points": [
                    {"time_sec": 0.0, "x_coord": 50.0, "y_coord": 80.0, "speed_mps": 10.0, "heading_deg": 180.0},
                    {"time_sec": 1.0, "x_coord": 50.0, "y_coord": 70.0, "speed_mps": 10.0, "heading_deg": 180.0},
                    {"time_sec": 2.0, "x_coord": 50.0, "y_coord": 60.0, "speed_mps": 10.0, "heading_deg": 180.0},
                    {"time_sec": 3.0, "x_coord": 50.0, "y_coord": 50.0, "speed_mps": 10.0, "heading_deg": 180.0},
                    {"time_sec": 4.0, "x_coord": 50.0, "y_coord": 40.0, "speed_mps": 10.0, "heading_deg": 180.0},
                ],
            },
            # 2. Pedestrian crossing east-to-west at y=50 (x from 56 down to 44)
            {
                "agent_id": "ped-01",
                "agent_type": "pedestrian",
                "junction_id": "jnc-101",
                "segment_id": "seg-north",
                "points": [
                    {"time_sec": 0.0, "x_coord": 56.0, "y_coord": 50.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    {"time_sec": 1.0, "x_coord": 54.5, "y_coord": 50.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    {"time_sec": 2.0, "x_coord": 53.0, "y_coord": 50.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    {"time_sec": 3.0, "x_coord": 51.5, "y_coord": 50.0, "speed_mps": 1.5, "heading_deg": 270.0},
                    {"time_sec": 4.0, "x_coord": 50.0, "y_coord": 50.0, "speed_mps": 1.5, "heading_deg": 270.0},
                ],
            },
            # 3. Following car behind car-01 (x=50, y from 95 down to 35)
            {
                "agent_id": "car-02",
                "agent_type": "car",
                "junction_id": "jnc-101",
                "segment_id": "seg-north",
                "points": [
                    {"time_sec": 0.0, "x_coord": 50.0, "y_coord": 95.0, "speed_mps": 12.0, "heading_deg": 180.0},
                    {"time_sec": 1.0, "x_coord": 50.0, "y_coord": 83.0, "speed_mps": 12.0, "heading_deg": 180.0},
                    {"time_sec": 2.0, "x_coord": 50.0, "y_coord": 71.0, "speed_mps": 11.0, "heading_deg": 180.0},
                    {"time_sec": 3.0, "x_coord": 50.0, "y_coord": 60.0, "speed_mps": 9.0, "heading_deg": 180.0},
                    {"time_sec": 4.0, "x_coord": 50.0, "y_coord": 51.0, "speed_mps": 7.0, "heading_deg": 180.0},
                ],
            },
            # 4. Faraway independent vehicle (no conflict)
            {
                "agent_id": "car-remote",
                "agent_type": "car",
                "junction_id": "jnc-remote",
                "points": [
                    {"time_sec": 0.0, "x_coord": 500.0, "y_coord": 500.0, "speed_mps": 15.0, "heading_deg": 90.0},
                    {"time_sec": 1.0, "x_coord": 515.0, "y_coord": 500.0, "speed_mps": 15.0, "heading_deg": 90.0},
                ],
            },
        ]

    def test_parse_agent_trajectories(self) -> None:
        agents = parse_agent_trajectories(self.sample_trajectories)
        self.assertEqual(len(agents), 4)

        car1 = agents[0]
        self.assertEqual(car1.agent_id, "car-01")
        self.assertEqual(car1.agent_type, "car")
        self.assertFalse(car1.is_vru)
        self.assertEqual(len(car1.points), 5)

        ped = agents[1]
        self.assertEqual(ped.agent_id, "ped-01")
        self.assertEqual(ped.agent_type, "pedestrian")
        self.assertTrue(ped.is_vru)
        self.assertEqual(ped.length_m, 0.5)

    def test_detect_trajectory_conflicts(self) -> None:
        agents = parse_agent_trajectories(self.sample_trajectories)
        conflicts = detect_trajectory_conflicts(agents)

        # Expected conflicts: car-01 vs ped-01 (vru_crossing) and car-01 vs car-02 (rear_end)
        self.assertGreaterEqual(len(conflicts), 2)

        # 1. Verify VRU crossing conflict
        vru_conflicts = [c for c in conflicts if c.is_vru_involved]
        self.assertGreaterEqual(len(vru_conflicts), 1)
        vc = vru_conflicts[0]
        self.assertEqual(vc.conflict_type, "vru_crossing")
        self.assertTrue(vc.is_vru_involved)
        self.assertLessEqual(vc.ttc_seconds, 4.0)
        self.assertGreater(vc.conflict_severity_index, 0.5)

        # 2. Verify rear-end conflict
        rear_conflicts = [c for c in conflicts if c.conflict_type == "rear_end"]
        self.assertGreaterEqual(len(rear_conflicts), 1)
        rc = rear_conflicts[0]
        self.assertFalse(rc.is_vru_involved)
        self.assertGreater(rc.drac_mps2, 0.0)

        # 3. Verify remote agent has 0 conflicts
        remote_conflicts = [
            c for c in conflicts if c.agent_1_id == "car-remote" or c.agent_2_id == "car-remote"
        ]
        self.assertEqual(len(remote_conflicts), 0)

    def test_aggregate_conflicts_to_junctions(self) -> None:
        agents = parse_agent_trajectories(self.sample_trajectories)
        conflicts = detect_trajectory_conflicts(agents)
        summaries = aggregate_conflicts_to_junctions(conflicts)

        self.assertGreaterEqual(len(summaries), 1)
        j101 = next(s for s in summaries if s.junction_id == "jnc-101")
        self.assertGreaterEqual(j101.total_conflicts, 2)
        self.assertGreaterEqual(j101.vru_conflicts, 1)
        self.assertIn(j101.danger_tier, {"critical", "high", "medium"})
        self.assertGreater(j101.max_csi, 0.5)

    def test_export_micro_ssam_artifacts(self) -> None:
        agents = parse_agent_trajectories(self.sample_trajectories)
        conflicts = detect_trajectory_conflicts(agents)
        summaries = aggregate_conflicts_to_junctions(conflicts)

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            files = export_micro_ssam_artifacts(
                conflicts=conflicts,
                junction_summaries=summaries,
                output_dir=out_dir,
                network_label="test_ssam",
            )

            for key in ["conflicts_csv", "junctions_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, files)
                p = Path(files[key])
                self.assertTrue(p.exists(), f"{key} should exist")
                self.assertGreater(p.stat().st_size, 0)

            # Check JSON Bundle
            bundle = json.loads(Path(files["bundle_json"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["ssam_engine_version"], SSAM_ENGINE_VERSION)
            self.assertEqual(bundle["contract_version"], SSAM_CONTRACT_VERSION)
            self.assertEqual(bundle["network_label"], "test_ssam")
            self.assertGreaterEqual(bundle["summary"]["total_conflicts_detected"], 2)
            self.assertGreaterEqual(bundle["summary"]["vru_conflicts_count"], 1)

            # Check Manifest
            manifest = json.loads(Path(files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "microscopic_ssam_conflict_analysis")
            self.assertIn("conflicts_csv", manifest["files"])
            self.assertIn("sha256", manifest["files"]["conflicts_csv"])


if __name__ == "__main__":
    unittest.main()
