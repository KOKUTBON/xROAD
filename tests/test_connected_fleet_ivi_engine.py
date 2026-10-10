"""Unit tests for Connected Fleet Geofencing & Cellular V2X (C-V2X PC5/Uu) Engine."""

from __future__ import annotations

import unittest

from road_risk_modeling.connected_fleet_ivi_engine import (
    CITS_IVI_CONTRACT_VERSION,
    CITS_IVI_ENGINE_VERSION,
    compile_iso19321_ivi_message,
    compile_cv2x_transmission,
    render_digital_cockpit_hmi,
    build_connected_fleet_view,
    reception_status_for_distance,
)


class TestConnectedFleetIviEngine(unittest.TestCase):
    def test_version_constants(self) -> None:
        self.assertEqual(CITS_IVI_CONTRACT_VERSION, "2026.1")
        self.assertEqual(CITS_IVI_ENGINE_VERSION, "1.0.0")

    def test_iso19321_ivi_message_compilation(self) -> None:
        ivi = compile_iso19321_ivi_message(
            incident_id="INC-TEST-001",
            threat_type="shockwave_congestion",
            severity_tier="critical",
            corridor_id="corridor-a",
            location_name="Test corridor km 12.4",
            latitude=45.0,
            longitude=9.0,
            mandatory_vsl_kmh=60,
            advisory_vsl_kmh=50,
            lane_restrictions="merge_left",
        )
        self.assertEqual(ivi.management.service_provider_id, "TMC-LOCAL-01")
        self.assertEqual(ivi.management.priority, 7)  # critical priority
        self.assertEqual(len(ivi.geographic_zones), 2)
        self.assertEqual(ivi.geographic_zones[0].zone_type, "relevance_zone")
        self.assertEqual(ivi.geographic_zones[1].zone_type, "detection_zone")
        self.assertEqual(ivi.signage.vienna_pictogram_code, "A,17")
        self.assertEqual(ivi.signage.mandatory_speed_kmh, 60)
        self.assertEqual(ivi.signage.lane_restrictions, "merge_left")
        self.assertTrue(len(ivi.sha256_payload_hash) == 64)

    def test_cv2x_dual_transmission_envelopes(self) -> None:
        ivi = compile_iso19321_ivi_message(
            incident_id="INC-TEST-001",
            threat_type="shockwave_congestion",
            severity_tier="critical",
            corridor_id="corridor-a",
            location_name="Test corridor km 12.4",
            latitude=45.0,
            longitude=9.0,
        )
        envelopes = compile_cv2x_transmission(ivi)
        self.assertEqual(len(envelopes), 2)

        pc5 = next(e for e in envelopes if e.channel == "PC5_DIRECT")
        self.assertEqual(pc5.frequency_ghz, 5.9)
        self.assertEqual(pc5.transmission_mode, "Mode_4_Sidelink")
        self.assertLess(pc5.latency_ms, 20.0)
        self.assertTrue(pc5.spatial_topic.startswith("cits/pc5/ivi/"))

        uu = next(e for e in envelopes if e.channel == "UU_CELLULAR")
        self.assertEqual(uu.frequency_ghz, 3.7)
        self.assertEqual(uu.transmission_mode, "Network_Slice_URLLC")
        self.assertTrue(uu.spatial_topic.startswith("cits/v2x/ivi/eu/it/puglia/bari/"))
        self.assertTrue(len(uu.sha256_digest) == 64)

    def test_digital_cockpit_hmi_rendering(self) -> None:
        ivi = compile_iso19321_ivi_message(
            incident_id="INC-TEST-001",
            threat_type="shockwave_congestion",
            severity_tier="critical",
            corridor_id="corridor-a",
            location_name="Test corridor km 12.4",
            latitude=45.0,
            longitude=9.0,
            mandatory_vsl_kmh=60,
            lane_restrictions="merge_left",
        )
        # Vehicle approaching at 450m and 85 km/h (exceeding 60 km/h)
        hmi = render_digital_cockpit_hmi(ivi, distance_meters=450.0, vehicle_speed_kmh=85.0)
        self.assertIn("RALLENTARE CODE", hmi.hud_banner_text)
        self.assertEqual(hmi.cluster_speed_limit_kmh, 60)
        self.assertEqual(hmi.cluster_warning_icon, "A,17")
        self.assertEqual(hmi.audio_chime_code, "ISO_15006_CRITICAL_CHIME")
        self.assertTrue(hmi.haptic_vibration_enabled)
        self.assertIn("MERGE LEFT", hmi.tactical_lane_guidance)
        self.assertGreater(hmi.time_to_hazard_seconds, 0.0)

    def test_tactical_lane_guidance_variations(self) -> None:
        for restrictions, expected in [
            ("merge_left", "MERGE LEFT"),
            ("merge_right", "MERGE RIGHT"),
            ("lane_closed", "REDUCED CAPACITY"),
            ("all_open", "ALL LANES OPEN"),
        ]:
            ivi = compile_iso19321_ivi_message(
                incident_id="INC-TEST",
                threat_type="shockwave",
                severity_tier="severe",
                corridor_id="CORR-1",
                location_name="Loc 1",
                latitude=41.11,
                longitude=16.87,
                lane_restrictions=restrictions,
            )
            hmi = render_digital_cockpit_hmi(ivi, distance_meters=800.0, vehicle_speed_kmh=60.0)
            self.assertIn(expected, hmi.tactical_lane_guidance)

    def _hazard(self):
        return compile_iso19321_ivi_message(
            incident_id="INC-TEST-001",
            threat_type="shockwave_congestion",
            severity_tier="critical",
            corridor_id="corridor-a",
            location_name="Test corridor km 12.4",
            latitude=45.0,
            longitude=9.0,
            mandatory_vsl_kmh=60,
            lane_restrictions="merge_left",
        )

    def test_fleet_view_projects_reported_positions(self) -> None:
        reported = [
            {"vehicle_id": "far", "latitude": 45.05, "longitude": 9.0, "speed_kmh": 80},
            {"vehicle_id": "near", "latitude": 45.002, "longitude": 9.0, "speed_kmh": 50,
             "fleet_category": "bus"},
            {"vehicle_id": "mid", "latitude": 45.015, "longitude": 9.0, "speed_kmh": 70},
            {"vehicle_id": "no-position", "speed_kmh": 30},
        ]
        fleet = build_connected_fleet_view(reported, self._hazard())
        self.assertEqual([v.vehicle_id for v in fleet], ["near", "mid", "far"])
        self.assertEqual(fleet[0].packet_reception_status, "RECEIVING_PC5")
        self.assertEqual(fleet[1].packet_reception_status, "RECEIVING_UU")
        self.assertEqual(fleet[2].packet_reception_status, "OUT_OF_RANGE")
        self.assertEqual(fleet[0].fleet_category, "bus")
        self.assertEqual(fleet[1].fleet_category, "unspecified")
        for vehicle in fleet:
            self.assertIsNotNone(vehicle.active_cockpit_hmi)

    def test_empty_fleet_stays_empty(self) -> None:
        self.assertEqual(build_connected_fleet_view([], self._hazard()), [])

    def test_reception_thresholds(self) -> None:
        self.assertEqual(reception_status_for_distance(799.0), "RECEIVING_PC5")
        self.assertEqual(reception_status_for_distance(2999.0), "RECEIVING_UU")
        self.assertEqual(reception_status_for_distance(3001.0), "OUT_OF_RANGE")

    def test_ivi_payload_hash_is_reproducible(self) -> None:
        self.assertEqual(self._hazard().sha256_payload_hash, self._hazard().sha256_payload_hash)


if __name__ == "__main__":
    unittest.main()
