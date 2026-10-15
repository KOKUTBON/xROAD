"""Tests for Autonomous Incident Response & TMC Playbook Automation Engine."""

from __future__ import annotations

import unittest

from road_risk_modeling.tmc_playbook_engine import (
    HITL_OVERSIGHT_LEVELS,
    STANDARD_PLAYBOOKS,
    VIENNA_PICTOGRAMS,
    authorize_and_execute_playbook,
    compile_playbook_actuation_plan,
    evaluate_incident_triggers,
    get_standard_tmc_playbooks,
    open_tmc_incident,
)


def _open_incident(incident_id: str = "INC-TEST-001"):
    return open_tmc_incident(
        incident_id=incident_id,
        threat_type="shockwave_congestion",
        severity_tier="critical",
        corridor_id="corridor-a",
        location_name="Test corridor A",
        latitude=0.0,
        longitude=0.0,
        crash_probability=0.8,
        speed_drop_kmh=40.0,
        current_speed_kmh=42.0,
        speed_limit_kmh=90.0,
    )


class TestTmcPlaybookEngine(unittest.TestCase):
    """Test suite for TMC playbook compilation, multi-tier actuation, and HITL authorization."""

    def test_standard_playbooks_catalog(self) -> None:
        """Verify all 5 standard operating playbooks are registered with valid rules."""
        playbooks = get_standard_tmc_playbooks()
        self.assertEqual(len(playbooks), 5)
        p_ids = {p["playbook_id"] for p in playbooks}
        self.assertIn("PB_SHOCKWAVE_CONGESTION", p_ids)
        self.assertIn("PB_ADVERSE_WEATHER_FOG_RAIN", p_ids)
        self.assertIn("PB_VRU_CROSSWALK_SURGE", p_ids)
        self.assertIn("PB_CRITICAL_CORRIDOR_NEAR_MISS", p_ids)
        self.assertIn("PB_SECONDARY_INCIDENT_PROTECTION", p_ids)

        for p in playbooks:
            self.assertGreater(p["expected_crash_reduction_pct"], 25.0)
            self.assertLessEqual(p["target_response_time_seconds"], 60)

    def test_threat_matching_and_trigger_evaluation(self) -> None:
        """Verify automatic trigger matching selects the appropriate playbook."""
        # 1. Congestion shockwave
        pb_shock = evaluate_incident_triggers(
            threat_type="shockwave_congestion",
            severity_tier="critical",
            crash_probability=0.72,
            speed_drop_kmh=35.0,
        )
        self.assertEqual(pb_shock.playbook_id, "PB_SHOCKWAVE_CONGESTION")

        # 2. Weather trigger
        pb_rain = evaluate_incident_triggers(
            threat_type="adverse_weather",
            severity_tier="elevated",
            crash_probability=0.50,
            precipitation_mm_h=12.0,
        )
        self.assertEqual(pb_rain.playbook_id, "PB_ADVERSE_WEATHER_FOG_RAIN")

        # 3. VRU surge
        pb_vru = evaluate_incident_triggers(
            threat_type="vru_crosswalk_surge",
            severity_tier="severe",
            crash_probability=0.65,
            near_miss_count=4,
        )
        self.assertEqual(pb_vru.playbook_id, "PB_VRU_CROSSWALK_SURGE")

    def test_multi_tier_actuation_plan_compilation(self) -> None:
        """Verify compilation of coordinated actions across all 5 field tiers."""
        pb = STANDARD_PLAYBOOKS["PB_SHOCKWAVE_CONGESTION"]
        actions = compile_playbook_actuation_plan(
            playbook=pb,
            corridor_id="SS16-KM804",
            location_name="Tangenziale di Bari SS16",
            latitude=41.0924,
            longitude=16.8835,
            current_speed_kmh=50.0,
            speed_limit_kmh=90.0,
        )
        self.assertEqual(len(actions), 5)
        tiers = {a.action_tier for a in actions}
        self.assertEqual(
            tiers,
            {"vsl_control", "vms_signage", "cits_denm", "micromobility_geofence", "patrol_dispatch"},
        )

        # Tier 1 VSL check
        vsl_action = next(a for a in actions if a.action_tier == "vsl_control")
        self.assertIn("mandatory_vsl_kmh", vsl_action.parameters)
        self.assertLessEqual(vsl_action.parameters["mandatory_vsl_kmh"], 70)

        # Tier 2 VMS check
        vms_action = next(a for a in actions if a.action_tier == "vms_signage")
        self.assertEqual(vms_action.parameters["vienna_pictogram"], VIENNA_PICTOGRAMS["CONGESTION_AHEAD"])

        # Tier 3 C-ITS DENM check
        cits_action = next(a for a in actions if a.action_tier == "cits_denm")
        self.assertEqual(cits_action.parameters["etsi_cause_code"], 1)

    def test_opened_incident_is_staged_for_approval(self) -> None:
        """An incident opened from alert parameters stages all five tiers, actuating none."""
        incident = _open_incident()
        self.assertEqual(incident.severity_tier, "critical")
        self.assertEqual(incident.playbook_id, "PB_SHOCKWAVE_CONGESTION")
        self.assertEqual(incident.authorization_state, "pending_approval")
        self.assertIsNone(incident.operator_id)
        self.assertEqual(len(incident.actions), 5)
        self.assertFalse(any(a.status == "active" for a in incident.actions))

    def test_hitl_one_click_authorization_and_receipt(self) -> None:
        """Operator authorization activates the staged actions and returns a receipt."""
        incident = _open_incident()
        updated, receipt = authorize_and_execute_playbook(
            incident, operator_id="operator-1", authorization_mode="ONE_CLICK"
        )
        self.assertEqual(receipt.incident_id, "INC-TEST-001")
        self.assertEqual(receipt.operator_id, "operator-1")
        self.assertEqual(receipt.authorization_state, "active")
        self.assertEqual(receipt.active_actions_count, 5)
        self.assertEqual(len(receipt.sha256_receipt_hash), 64)
        self.assertEqual(updated.authorization_state, "active")
        self.assertEqual(updated.operator_id, "operator-1")
        self.assertTrue(all(a.status == "active" for a in updated.actions))

    def test_authorization_is_never_fabricated(self) -> None:
        """Authorization requires an operator and a pending incident; no synthetic receipts."""
        incident = _open_incident()
        with self.assertRaises(ValueError):
            authorize_and_execute_playbook(incident, operator_id="  ")
        active, _ = authorize_and_execute_playbook(incident, operator_id="operator-1")
        with self.assertRaises(ValueError):
            authorize_and_execute_playbook(active, operator_id="operator-1")

    def test_hitl_oversight_levels_reference(self) -> None:
        """Verify EU AI Act Article 14 oversight tiers are defined."""
        self.assertIn("ADVISORY", HITL_OVERSIGHT_LEVELS)
        self.assertIn("ONE_CLICK", HITL_OVERSIGHT_LEVELS)
        self.assertIn("AUTONOMOUS_WITH_OVERRIDE", HITL_OVERSIGHT_LEVELS)


if __name__ == "__main__":
    unittest.main()
