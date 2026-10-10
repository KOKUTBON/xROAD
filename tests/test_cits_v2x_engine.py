"""Tests for Closed-Loop C-ITS and Cellular V2X Operational Actuation Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.cits_v2x_engine import (
    CITS_CONTRACT_VERSION,
    CITS_ENGINE_VERSION,
    CitsActuationPlan,
    CitsDenmMessage,
    CitsIvimMessage,
    OperationalRiskAlert,
    VariableSpeedLimitCommand,
    VmsSignLayout,
    compute_dynamic_vsl_plan,
    create_cits_actuation_bundle,
    export_cits_actuation_artifacts,
    generate_etsi_denm_messages,
    generate_etsi_ivim_messages,
    generate_vms_layouts,
    parse_operational_risk_alerts,
)


class TestCitsV2xEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_alerts_data = [
            {
                "alert_id": "cits-1",
                "segment_id": "seg-1",
                "crash_probability": 0.85,
                "alert_tier": "critical",
                "primary_threat": "rain_storm_aquaplaning",
                "current_speed_kmh": 60.0,
                "free_flow_speed_kmh": 70.0,
                "speed_limit_kmh": 70.0,
                "precipitation_mm_h": 12.0,
                "surface_condition": "slippery",
                "latitude": 41.11,
                "longitude": 16.87,
                "upstream_segment_id": None,
                "downstream_segment_id": "seg-2",
            },
            {
                "alert_id": "cits-2",
                "segment_id": "seg-2",
                "crash_probability": 0.75,
                "alert_tier": "critical",
                "primary_threat": "shockwave_congestion",
                "current_speed_kmh": 25.0,
                "free_flow_speed_kmh": 50.0,
                "speed_limit_kmh": 50.0,
                "precipitation_mm_h": 0.0,
                "surface_condition": "dry",
                "latitude": 41.12,
                "longitude": 16.88,
                "upstream_segment_id": "seg-1",
                "downstream_segment_id": None,
            },
            {
                "alert_id": "cits-3",
                "segment_id": "seg-3",
                "crash_probability": 0.70,
                "alert_tier": "high",
                "primary_threat": "vru_crossing_hazard",
                "current_speed_kmh": 35.0,
                "free_flow_speed_kmh": 50.0,
                "speed_limit_kmh": 50.0,
                "precipitation_mm_h": 0.0,
                "surface_condition": "dry",
                "latitude": 41.13,
                "longitude": 16.89,
            },
        ]

    def test_parse_operational_risk_alerts(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        self.assertEqual(len(alerts), 3)
        self.assertEqual(alerts[0].alert_id, "cits-1")
        self.assertEqual(alerts[0].alert_tier, "critical")
        self.assertAlmostEqual(alerts[0].crash_probability, 0.85)
        self.assertEqual(alerts[0].surface_condition, "slippery")
        self.assertAlmostEqual(alerts[0].precipitation_mm_h, 12.0)

    def test_compute_dynamic_vsl_plan(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        commands = compute_dynamic_vsl_plan(alerts)

        self.assertEqual(len(commands), 3)
        self.assertIsInstance(commands[0], VariableSpeedLimitCommand)

        # seg-1: 70 km/h nominal with storm -> should drop to 40 km/h
        cmd1 = commands[0]
        self.assertEqual(cmd1.segment_id, "seg-1")
        self.assertEqual(cmd1.nominal_speed_limit_kmh, 70)
        self.assertEqual(cmd1.mandatory_vsl_kmh, 40)
        self.assertEqual(cmd1.recommended_vsl_kmh, 30)  # critical alert has -10 advisory
        self.assertEqual(cmd1.speed_drop_kmh, 30)
        self.assertIn("AQUAPLANING", cmd1.damping_reason)
        self.assertGreater(cmd1.expected_crash_reduction_pct, 20.0)

        # seg-2: 50 km/h nominal with shockwave -> should drop to 30 km/h
        cmd2 = commands[1]
        self.assertEqual(cmd2.segment_id, "seg-2")
        self.assertEqual(cmd2.nominal_speed_limit_kmh, 50)
        self.assertEqual(cmd2.mandatory_vsl_kmh, 30)
        self.assertEqual(cmd2.speed_drop_kmh, 20)

    def test_generate_etsi_denm_messages(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        denm_msgs = generate_etsi_denm_messages(alerts)

        self.assertEqual(len(denm_msgs), 3)
        self.assertIsInstance(denm_msgs[0], CitsDenmMessage)

        # Check weather cause code for seg-1 (cause 17)
        self.assertEqual(denm_msgs[0].cause_code, 17)
        self.assertEqual(denm_msgs[0].severity, "critical")
        self.assertEqual(denm_msgs[0].relevance_distance_m, 2500)

        # Check VRU cause code for seg-3 (cause 91)
        self.assertEqual(denm_msgs[2].cause_code, 91)
        self.assertEqual(denm_msgs[2].severity, "high")
        self.assertEqual(denm_msgs[2].relevance_distance_m, 1000)

        # Check to_dict conforms to ETSI header
        denm_dict = denm_msgs[0].to_dict()
        self.assertEqual(denm_dict["header"]["protocol_version"], 2)
        self.assertEqual(denm_dict["header"]["message_id"], 1)
        self.assertIn("management", denm_dict["denm"])
        self.assertIn("situation", denm_dict["denm"])

    def test_generate_etsi_ivim_messages(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        vsl_cmds = compute_dynamic_vsl_plan(alerts)
        ivim_msgs = generate_etsi_ivim_messages(vsl_cmds, alerts)

        self.assertEqual(len(ivim_msgs), 3)
        self.assertIsInstance(ivim_msgs[0], CitsIvimMessage)
        self.assertEqual(ivim_msgs[0].mandatory_speed_kmh, 40)
        self.assertEqual(ivim_msgs[0].road_condition, "aquaplaning_risk")
        self.assertIn("C,14", ivim_msgs[0].pictogram_code)

        ivim_dict = ivim_msgs[0].to_dict()
        self.assertEqual(ivim_dict["header"]["protocol_version"], 2)
        self.assertEqual(ivim_dict["header"]["message_id"], 6)
        self.assertEqual(ivim_dict["ivim"]["speed_mandate"]["mandatory_vsl_kmh"], 40)

    def test_generate_vms_layouts(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        vsl_cmds = compute_dynamic_vsl_plan(alerts)
        layouts = generate_vms_layouts(vsl_cmds, alerts)

        self.assertEqual(len(layouts), 3)
        self.assertIsInstance(layouts[0], VmsSignLayout)
        self.assertEqual(layouts[0].line_1_text, "ATTENZIONE PIOGGIA")
        self.assertIn("en", layouts[0].languages)
        self.assertEqual(layouts[0].languages["en"][0], "CAUTION HEAVY RAIN")
        self.assertIn("de", layouts[0].languages)
        self.assertIn("fr", layouts[0].languages)

    def test_create_cits_actuation_bundle(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        plan = create_cits_actuation_bundle(
            alerts=alerts,
            network_label="test_cits_network",
            sovereign_station_id="TEST-SOVEREIGN-TMC-01",
        )

        self.assertIsInstance(plan, CitsActuationPlan)
        self.assertEqual(plan.network_label, "test_cits_network")
        self.assertEqual(plan.sovereign_signer_station_id, "TEST-SOVEREIGN-TMC-01")
        self.assertEqual(len(plan.vsl_commands), 3)
        self.assertEqual(len(plan.denm_messages), 3)
        self.assertEqual(len(plan.ivim_messages), 3)
        self.assertEqual(len(plan.vms_layouts), 3)
        self.assertTrue(len(plan.payload_sha256) == 64)

        plan_dict = plan.to_dict()
        self.assertEqual(plan_dict["cits_engine_version"], CITS_ENGINE_VERSION)
        self.assertEqual(plan_dict["contract_version"], CITS_CONTRACT_VERSION)
        self.assertEqual(plan_dict["summary"]["total_vsl_commands"], 3)
        self.assertEqual(plan_dict["summary"]["critical_actuations_count"], 2)

    def test_export_cits_actuation_artifacts(self) -> None:
        alerts = parse_operational_risk_alerts(self.sample_alerts_data)
        plan = create_cits_actuation_bundle(alerts=alerts, network_label="test_artifacts_network")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_files = export_cits_actuation_artifacts(
                plan=plan,
                output_dir=tmp_dir,
                network_label="test_artifacts_network",
            )

            self.assertTrue(Path(out_files["vsl_schedule_csv"]).exists())
            self.assertTrue(Path(out_files["denm_json"]).exists())
            self.assertTrue(Path(out_files["ivim_json"]).exists())
            self.assertTrue(Path(out_files["bundle_json"]).exists())
            self.assertTrue(Path(out_files["briefing_md"]).exists())
            self.assertTrue(Path(out_files["manifest"]).exists())

            # Verify manifest
            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "cits_v2x_operational_actuation")
            self.assertIn("vsl_schedule_csv", manifest["files"])
            self.assertIn("sha256", manifest["files"]["vsl_schedule_csv"])


if __name__ == "__main__":
    unittest.main()
