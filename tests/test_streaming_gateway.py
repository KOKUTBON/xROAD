"""Unit tests for Real-Time Telematics & Micromobility Streaming Gateway."""

from __future__ import annotations

import asyncio
import unittest

from road_risk_modeling.streaming_gateway import (
    STREAM_CONTRACT_VERSION,
    StreamingEventManager,
    StreamSubscriptionFilter,
    TelematicsStreamEvent,
    get_global_stream_manager,
)


class TestStreamingGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = StreamingEventManager(capacity=10)

    def test_classify_and_build_harsh_braking_event(self) -> None:
        """Test classification of connected vehicle kinematic braking events."""
        # 1. Critical braking (-0.65g)
        raw_crit = {
            "source_type": "connected_vehicle",
            "segment_id": "seg-test-1",
            "peak_accel_g": -0.65,
            "speed_kmh": 60.0,
        }
        evt_crit = self.mgr.classify_and_build_event(raw_crit)
        self.assertEqual(evt_crit.event_type, "harsh_braking")
        self.assertEqual(evt_crit.severity, "critical")
        self.assertEqual(evt_crit.segment_id, "seg-test-1")

        # 2. Severe braking (-0.48g)
        raw_sev = {
            "source_type": "connected_vehicle",
            "segment_id": "seg-test-2",
            "peak_accel_g": -0.48,
        }
        evt_sev = self.mgr.classify_and_build_event(raw_sev)
        self.assertEqual(evt_sev.event_type, "harsh_braking")
        self.assertEqual(evt_sev.severity, "severe")

    def test_classify_and_build_micromobility_event(self) -> None:
        """Test classification of 6-axis IMU micromobility anomalies."""
        # Sidewalk riding
        raw_sidewalk = {
            "source_type": "shared_e_scooter",
            "segment_id": "seg-micro-1",
            "speed_kmh": 10.0,
            "psd_vibration": 0.55,
        }
        evt_sw = self.mgr.classify_and_build_event(raw_sidewalk)
        self.assertEqual(evt_sw.event_type, "sidewalk_riding")
        self.assertEqual(evt_sw.severity, "severe")

        # Curb impact
        raw_curb = {
            "source_type": "shared_e_bike",
            "segment_id": "seg-micro-2",
            "accel_z_g": 3.2,
        }
        evt_curb = self.mgr.classify_and_build_event(raw_curb)
        self.assertEqual(evt_curb.event_type, "curb_impact")
        self.assertEqual(evt_curb.severity, "critical")

    def test_sliding_buffer_retention(self) -> None:
        """Test that event history is bounded to capacity."""
        for i in range(25):
            evt = TelematicsStreamEvent(
                event_id=f"evt-{i}",
                timestamp="2026-09-21T12:00:00Z",
                event_type="harsh_braking",
                source_type="connected_vehicle",
                severity="moderate",
                segment_id="seg-1",
                latitude=41.12,
                longitude=16.87,
                speed_kmh=40.0,
                peak_accel_g=-0.40,
            )
            asyncio.run(self.mgr.broadcast(evt))

        recent = self.mgr.get_recent_events(limit=50)
        self.assertEqual(len(recent), 10)  # Capacity is 10
        self.assertEqual(recent[0]["event_id"], "evt-24")  # Most recent first

    def test_subscription_filter_topic_and_spatial(self) -> None:
        """Test filtering by topic and geographic bounding box."""
        filt = StreamSubscriptionFilter(
            topics=("harsh_braking",),
            min_lat=41.10,
            max_lat=41.15,
            min_lon=16.85,
            max_lon=16.90,
            min_severity="severe",
        )

        # Match
        e_match = TelematicsStreamEvent(
            event_id="e-match",
            timestamp="2026-09-21T12:00:00Z",
            event_type="harsh_braking",
            source_type="connected_vehicle",
            severity="critical",
            segment_id="seg-1",
            latitude=41.12,
            longitude=16.87,
            speed_kmh=40.0,
            peak_accel_g=-0.62,
        )
        self.assertTrue(filt.matches(e_match))

        # Mismatch: wrong topic
        e_wrong_topic = TelematicsStreamEvent(
            event_id="e-wrong",
            timestamp="2026-09-21T12:00:00Z",
            event_type="sidewalk_riding",
            source_type="shared_e_scooter",
            severity="critical",
            segment_id="seg-1",
            latitude=41.12,
            longitude=16.87,
            speed_kmh=10.0,
            peak_accel_g=-0.1,
        )
        self.assertFalse(filt.matches(e_wrong_topic))

        # Mismatch: out of bounding box
        e_out_of_bounds = TelematicsStreamEvent(
            event_id="e-oob",
            timestamp="2026-09-21T12:00:00Z",
            event_type="harsh_braking",
            source_type="connected_vehicle",
            severity="critical",
            segment_id="seg-1",
            latitude=42.50,
            longitude=16.87,
            speed_kmh=50.0,
            peak_accel_g=-0.65,
        )
        self.assertFalse(filt.matches(e_out_of_bounds))

    def test_subscriber_registration_and_broadcast(self) -> None:
        """Test real-time message delivery to subscriber queue."""
        q = self.mgr.register_subscriber("sub-1")
        self.assertEqual(self.mgr.total_subscribers, 1)

        evt = self.mgr.generate_demo_event()
        delivered = asyncio.run(self.mgr.broadcast(evt))
        self.assertEqual(delivered, 1)
        self.assertFalse(q.empty())

        received = q.get_nowait()
        self.assertEqual(received.event_id, evt.event_id)

        self.mgr.unregister_subscriber("sub-1")
        self.assertEqual(self.mgr.total_subscribers, 0)

    def test_singleton_manager(self) -> None:
        """Test global singleton retrieval and initial buffer."""
        mgr = get_global_stream_manager()
        self.assertIsInstance(mgr, StreamingEventManager)
        recent = mgr.get_recent_events(limit=5)
        self.assertGreaterEqual(len(recent), 1)


if __name__ == "__main__":
    unittest.main()
