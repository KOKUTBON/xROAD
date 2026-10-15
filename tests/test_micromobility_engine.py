"""Tests for VRU Micromobility Sensor Fusion Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.micromobility_engine import (
    CURB_STRIKE_THRESHOLD_G,
    EVASIVE_SWERVE_LATERAL_G,
    EVASIVE_SWERVE_YAW_DEG_S,
    MICROMOBILITY_CONTRACT_VERSION,
    MICROMOBILITY_ENGINE_VERSION,
    SIDEWALK_ROUGHNESS_G,
    SIDEWALK_SPEED_LIMIT_MPS,
    TRAM_SLIP_RATIO_THRESHOLD,
    MicromobilityEvent,
    MicromobilityFleetAuditReport,
    MicromobilityWaypoint,
    SegmentMicromobilityProfile,
    aggregate_micromobility_profiles,
    detect_micromobility_events,
    export_micromobility_artifacts,
    run_micromobility_fleet_audit,
)


class TestMicromobilityEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_waypoints = [
            # 1. Sidewalk riding waypoint (> 1.67 m/s on sidewalk)
            {
                "device_id": "scooter-01",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:00:00Z",
                "latitude": 41.1215,
                "longitude": 16.8710,
                "speed_mps": 3.8,  # ~13.7 km/h
                "accel_x": 0.05,
                "accel_y": 0.02,
                "accel_z": 1.02,
                "yaw_rate_deg_s": 2.1,
                "is_sidewalk": True,
                "segment_id": "seg-sparano",
            },
            # 2. Consecutive waypoints triggering curb strike (|delta a_z| >= 1.8g)
            {
                "device_id": "scooter-02",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:05:00Z",
                "latitude": 41.1180,
                "longitude": 16.8690,
                "speed_mps": 4.0,
                "accel_x": 0.08,
                "accel_y": 0.05,
                "accel_z": 1.00,
                "yaw_rate_deg_s": 3.0,
                "is_sidewalk": False,
                "segment_id": "seg-cavour",
            },
            {
                "device_id": "scooter-02",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:05:01Z",
                "latitude": 41.1183,
                "longitude": 16.8692,
                "speed_mps": 4.1,
                "accel_x": -0.15,
                "accel_y": 0.02,
                "accel_z": 3.10,  # Delta az = 2.10g >= 1.80g
                "yaw_rate_deg_s": 4.5,
                "is_sidewalk": False,
                "segment_id": "seg-cavour",
            },
            # 3. Evasive near-miss swerve (|a_y| >= 0.35g and |yaw_rate| >= 45 deg/s)
            {
                "device_id": "bike-03",
                "vehicle_type": "cargo_bike",
                "timestamp": "2026-09-17T10:10:00Z",
                "latitude": 41.1090,
                "longitude": 16.8850,
                "speed_mps": 5.2,
                "accel_x": 0.04,
                "accel_y": 0.42,  # Lateral g >= 0.35g
                "accel_z": 1.02,
                "yaw_rate_deg_s": -50.0,  # Yaw rate >= 45 deg/s
                "is_sidewalk": False,
                "segment_id": "seg-caldarola",
            },
            # 4. Tram track wheel slip (slip ratio >= 0.30)
            {
                "device_id": "scooter-04",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:15:00Z",
                "latitude": 41.1170,
                "longitude": 16.8700,
                "speed_mps": 3.0,
                "accel_x": -0.20,
                "accel_y": 0.10,
                "accel_z": 1.01,
                "yaw_rate_deg_s": 5.0,
                "is_sidewalk": False,
                "wheel_speed_mps": 4.8,  # |4.8 - 3.0| / 3.0 = 0.60 >= 0.30
                "segment_id": "seg-moro",
            },
            # 5. Normal cruising waypoint
            {
                "device_id": "scooter-05",
                "vehicle_type": "e_scooter",
                "timestamp": "2026-09-17T10:20:00Z",
                "latitude": 41.1250,
                "longitude": 16.8800,
                "speed_mps": 4.5,
                "accel_x": 0.01,
                "accel_y": 0.02,
                "accel_z": 1.00,
                "yaw_rate_deg_s": 0.5,
                "is_sidewalk": False,
                "segment_id": "seg-lungomare",
            },
        ]

        self.sample_segments = [
            {"segment_id": "seg-sparano", "total_trips": 300, "total_distance_km": 150.0, "nominal_bicycle_srs": 20.0},
            {"segment_id": "seg-cavour", "total_trips": 500, "total_distance_km": 250.0, "nominal_bicycle_srs": 18.0},
            {"segment_id": "seg-caldarola", "total_trips": 400, "total_distance_km": 200.0, "nominal_bicycle_srs": 15.0},
            {"segment_id": "seg-moro", "total_trips": 350, "total_distance_km": 180.0, "nominal_bicycle_srs": 25.0},
            {"segment_id": "seg-lungomare", "total_trips": 600, "total_distance_km": 300.0, "nominal_bicycle_srs": 12.0},
        ]

    def test_detect_micromobility_events_all_categories(self) -> None:
        """Verify accurate detection of sidewalk riding, curb strike, evasive swerve, and tram slip."""
        events = detect_micromobility_events(self.sample_waypoints)
        self.assertGreaterEqual(len(events), 4)

        event_types = {e.event_type for e in events}
        self.assertIn("sidewalk_riding", event_types)
        self.assertIn("curb_strike", event_types)
        self.assertIn("evasive_swerve", event_types)
        self.assertIn("tram_track_slip", event_types)

        # Check sidewalk riding event properties
        sw_events = [e for e in events if e.event_type == "sidewalk_riding"]
        self.assertEqual(sw_events[0].device_id, "scooter-01")
        self.assertEqual(sw_events[0].segment_id, "seg-sparano")
        self.assertGreaterEqual(sw_events[0].metric_value, 6.0)

        # Check curb strike event properties
        cs_events = [e for e in events if e.event_type == "curb_strike"]
        self.assertEqual(cs_events[0].device_id, "scooter-02")
        self.assertEqual(cs_events[0].segment_id, "seg-cavour")
        self.assertGreaterEqual(cs_events[0].peak_g, CURB_STRIKE_THRESHOLD_G)

        # Check evasive swerve properties
        es_events = [e for e in events if e.event_type == "evasive_swerve"]
        self.assertEqual(es_events[0].device_id, "bike-03")
        self.assertEqual(es_events[0].segment_id, "seg-caldarola")
        self.assertGreaterEqual(es_events[0].metric_value, EVASIVE_SWERVE_YAW_DEG_S)

        # Check tram track slip properties
        ts_events = [e for e in events if e.event_type == "tram_track_slip"]
        self.assertEqual(ts_events[0].device_id, "scooter-04")
        self.assertEqual(ts_events[0].segment_id, "seg-moro")
        self.assertGreaterEqual(ts_events[0].peak_g, TRAM_SLIP_RATIO_THRESHOLD)

    def test_aggregate_micromobility_profiles_and_irap_calibration(self) -> None:
        """Verify corridor profile aggregation, MCI calculation, and iRAP SRS adjustment."""
        events = detect_micromobility_events(self.sample_waypoints)
        profiles = aggregate_micromobility_profiles(events, self.sample_segments)

        self.assertEqual(len(profiles), 5)
        prof_map = {p.segment_id: p for p in profiles}

        # Check seg-sparano has sidewalk events and positive MCI
        sparano = prof_map["seg-sparano"]
        self.assertEqual(sparano.sidewalk_riding_events, 1)
        self.assertGreater(sparano.micromobility_conflict_index, 0.0)
        self.assertGreaterEqual(sparano.calibrated_bicycle_srs, sparano.nominal_bicycle_srs)

        # Check seg-lungomare has 0 conflicts and calibrated SRS == nominal SRS
        lungo = prof_map["seg-lungomare"]
        self.assertEqual(lungo.sidewalk_riding_events, 0)
        self.assertEqual(lungo.curb_strikes, 0)
        self.assertEqual(lungo.evasive_swerves, 0)
        self.assertEqual(lungo.tram_slips, 0)
        self.assertEqual(lungo.micromobility_conflict_index, 0.0)
        self.assertAlmostEqual(lungo.calibrated_bicycle_srs, lungo.nominal_bicycle_srs, places=2)

    def test_run_micromobility_fleet_audit_end_to_end(self) -> None:
        """Verify run_micromobility_fleet_audit full pipeline execution."""
        report, events = run_micromobility_fleet_audit(
            waypoints_data=self.sample_waypoints,
            segments_data=self.sample_segments,
            network_label="test_fleet_net",
        )

        self.assertIsInstance(report, MicromobilityFleetAuditReport)
        self.assertEqual(report.network_label, "test_fleet_net")
        self.assertEqual(report.total_devices, 5)
        self.assertGreaterEqual(report.total_events_detected, 4)
        self.assertGreater(report.total_distance_km, 0.0)
        self.assertEqual(len(report.segment_profiles), 5)

        r_dict = report.to_dict()
        self.assertEqual(r_dict["micromobility_engine_version"], MICROMOBILITY_ENGINE_VERSION)
        self.assertEqual(r_dict["contract_version"], MICROMOBILITY_CONTRACT_VERSION)
        self.assertIn("fleet_spec_standards", r_dict)

    def test_export_micromobility_artifacts(self) -> None:
        """Verify export of events CSV, profiles CSV, bundle JSON, report MD, and SHA-256 manifest."""
        report, events = run_micromobility_fleet_audit(
            waypoints_data=self.sample_waypoints,
            segments_data=self.sample_segments,
            network_label="test_export_vru",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_files = export_micromobility_artifacts(
                report=report,
                events=events,
                output_dir=tmpdir,
                network_label="test_export_vru",
            )

            for key in ["events_csv", "profiles_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, out_files)
                fpath = Path(out_files[key])
                self.assertTrue(fpath.exists(), f"File {fpath} does not exist")
                self.assertGreater(fpath.stat().st_size, 0)

            # Check Manifest Integrity
            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "micromobility_vru_sensor_fusion")
            self.assertEqual(manifest["micromobility_engine_version"], MICROMOBILITY_ENGINE_VERSION)
            self.assertIn("events_csv", manifest["files"])
            self.assertIn("profiles_csv", manifest["files"])
            self.assertIn("report_md", manifest["files"])

            # Check Report Markdown Content
            md_text = Path(out_files["report_md"]).read_text(encoding="utf-8")
            self.assertIn("VRU Micromobility Sensor Fusion Report", md_text)
            self.assertIn("Corridor Micro-Safety Friction", md_text)
            self.assertIn("Segregated Physical Protection", md_text)


if __name__ == "__main__":
    unittest.main()
