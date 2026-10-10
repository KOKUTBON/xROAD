"""Unit tests for Commercial Floating Car Data (FCD) & Telematics Near-Miss Engine."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.telematics_engine import (
    TELEMATICS_CONTRACT_VERSION,
    TELEMATICS_ENGINE_VERSION,
    KinematicNearMissEvent,
    SegmentTelematicsMetrics,
    calculate_segment_telematics_metrics,
    classify_acceleration_severity,
    classify_braking_severity,
    classify_cornering_severity,
    detect_events_from_waypoints,
    export_telematics_screening_artifacts,
    parse_telematics_events,
)


class TestTelematicsEngine(unittest.TestCase):
    def test_classify_braking_severity(self) -> None:
        self.assertIsNone(classify_braking_severity(-0.20))
        self.assertEqual(classify_braking_severity(-0.38), "moderate")
        self.assertEqual(classify_braking_severity(-0.48), "severe")
        self.assertEqual(classify_braking_severity(-0.65), "critical")

    def test_classify_cornering_severity(self) -> None:
        self.assertIsNone(classify_cornering_severity(0.20))
        self.assertEqual(classify_cornering_severity(0.35), "moderate")
        self.assertEqual(classify_cornering_severity(-0.45), "severe")  # handles negative lateral
        self.assertEqual(classify_cornering_severity(0.58), "critical")

    def test_classify_acceleration_severity(self) -> None:
        self.assertIsNone(classify_acceleration_severity(0.15))
        self.assertEqual(classify_acceleration_severity(0.32), "moderate")
        self.assertEqual(classify_acceleration_severity(0.48), "severe")

    def test_detect_events_from_waypoints(self) -> None:
        # Waypoints experiencing emergency braking
        waypoints = [
            {"timestamp_s": 0.0, "speed_kmh": 60.0, "accel_x_g": 0.0, "accel_y_g": 0.0},
            {"timestamp_s": 1.0, "speed_kmh": 35.0, "accel_x_g": -0.52, "accel_y_g": 0.05},
            {"timestamp_s": 2.0, "speed_kmh": 34.0, "accel_x_g": 0.0, "accel_y_g": 0.42},
        ]
        events = detect_events_from_waypoints(waypoints, segment_id="test-seg-1")
        self.assertEqual(len(events), 2)

        # Event 1: Harsh braking
        e1 = events[0]
        self.assertEqual(e1.segment_id, "test-seg-1")
        self.assertEqual(e1.event_type, "harsh_braking")
        self.assertEqual(e1.severity, "severe")
        self.assertAlmostEqual(e1.peak_accel_g, -0.52)

        # Event 2: Harsh cornering (swerve)
        e2 = events[1]
        self.assertEqual(e2.event_type, "harsh_cornering")
        self.assertEqual(e2.severity, "severe")
        self.assertAlmostEqual(e2.peak_accel_g, 0.42)

    def test_parse_telematics_events(self) -> None:
        records = [
            {
                "event_id": "fcd-001",
                "segment_id": "seg-corridor-a",
                "event_type": "harsh_braking",
                "peak_accel_g": -0.62,
                "initial_speed_kmh": 85.0,
                "final_speed_kmh": 20.0,
                "duration_s": 2.1,
                "vehicle_type": "heavy_truck",
            }
        ]
        events = parse_telematics_events(records)
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.event_id, "fcd-001")
        self.assertEqual(evt.severity, "critical")
        self.assertEqual(evt.vehicle_type, "heavy_truck")

    def test_calculate_segment_telematics_metrics_and_fusion(self) -> None:
        segments = [
            {
                "segment_id": "seg-high-anomaly",
                "length_km": 1.0,
                "aadt": 10000.0,
                "psi_excess_crashes_annual": 2.5,
                "minimum_stars_overall": 2,
            },
            {
                "segment_id": "seg-peaceful",
                "length_km": 1.0,
                "aadt": 10000.0,
                "psi_excess_crashes_annual": -0.5,
                "minimum_stars_overall": 4,
            },
        ]
        # Ingest multiple severe and critical braking events on seg-high-anomaly
        events = [
            KinematicNearMissEvent(
                event_id=f"evt-{i}",
                segment_id="seg-high-anomaly",
                timestamp="2026-09-14T12:00:00Z",
                event_type="harsh_braking",
                severity="critical" if i % 2 == 0 else "severe",
                peak_accel_g=-0.65,
                initial_speed_kmh=70.0,
                final_speed_kmh=10.0,
                delta_v_kmh=60.0,
                duration_s=2.0,
            )
            for i in range(12)
        ]

        metrics = calculate_segment_telematics_metrics(
            segments=segments,
            telematics_events=events,
            days_analyzed=365,
            fleet_penetration_rate=0.05,
        )

        self.assertEqual(len(metrics), 2)
        top = metrics[0]
        self.assertEqual(top.segment_id, "seg-high-anomaly")
        self.assertEqual(top.priority_rank, 1)
        self.assertEqual(top.risk_tier, "critical_proactive_hotspot")
        self.assertGreater(top.near_miss_rate_per_mvkt, 50.0)
        self.assertGreater(top.predictive_risk_score, 65.0)

        bottom = metrics[1]
        self.assertEqual(bottom.segment_id, "seg-peaceful")
        self.assertEqual(bottom.priority_rank, 2)
        self.assertEqual(bottom.risk_tier, "low_anomaly_network")
        self.assertEqual(bottom.total_near_miss_events, 0)
        self.assertLess(bottom.predictive_risk_score, top.predictive_risk_score)

    def test_export_telematics_screening_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            segments = [{"segment_id": "s1", "length_km": 0.5, "aadt": 5000}]
            events = [
                KinematicNearMissEvent(
                    event_id="e1",
                    segment_id="s1",
                    timestamp="2026-09-14T10:00:00Z",
                    event_type="harsh_braking",
                    severity="severe",
                    peak_accel_g=-0.48,
                    initial_speed_kmh=50.0,
                    final_speed_kmh=20.0,
                    delta_v_kmh=30.0,
                    duration_s=1.5,
                )
            ]
            metrics = calculate_segment_telematics_metrics(segments, events)

            paths = export_telematics_screening_artifacts(
                metrics=metrics,
                events=events,
                output_dir=out_dir,
                network_label="test_telematics",
            )

            for key in ["rates_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, paths)
                self.assertTrue(Path(paths[key]).exists())

            # Verify bundle JSON contents
            with Path(paths["bundle_json"]).open("r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["telematics_engine_version"], TELEMATICS_ENGINE_VERSION)
                self.assertEqual(data["contract_version"], TELEMATICS_CONTRACT_VERSION)
                self.assertIn("tier_distribution", data["summary"])


if __name__ == "__main__":
    unittest.main()
