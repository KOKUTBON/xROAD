"""Real-Time Telematics & Micromobility Streaming Gateway.

Provides in-memory asynchronous pub-sub broadcasting, a sliding-window ring buffer,
and real-time kinematic and 6-axis IMU anomaly classification for connected vehicle
Floating Car Data (FCD) and shared micromobility fleets.
Supports WebSocket and Server-Sent Events (SSE) for sovereign air-gapped deployments.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
import random
from typing import Any, AsyncGenerator, Mapping, Sequence
import uuid

from .micromobility_engine import (
    CURB_STRIKE_THRESHOLD_G,
    EVASIVE_SWERVE_LATERAL_G,
    EVASIVE_SWERVE_YAW_DEG_S,
    SIDEWALK_ROUGHNESS_G,
)
from .modeling import _sha256
from .telematics_engine import (
    HARSH_ACCEL_THRESHOLDS,
    HARSH_BRAKING_THRESHOLDS,
    HARSH_CORNERING_THRESHOLDS,
)


STREAM_CONTRACT_VERSION = "telematics_stream_public_v1"
STREAM_BUFFER_CAPACITY = 100


@dataclass(frozen=True, slots=True)
class TelematicsStreamEvent:
    """A real-time kinematic or micromobility anomaly event."""

    event_id: str
    timestamp: str
    event_type: str  # harsh_braking, harsh_cornering, sudden_speed_drop, sidewalk_riding, curb_impact, evasive_swerve
    source_type: str  # connected_vehicle, shared_e_scooter, shared_e_bike, commercial_fleet
    severity: str    # critical, severe, moderate, info
    segment_id: str
    latitude: float
    longitude: float
    speed_kmh: float
    peak_accel_g: float
    secondary_metric: float = 0.0  # yaw_rate_degs or psd_vibration
    vehicle_id: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "source_type": self.source_type,
            "severity": self.severity,
            "segment_id": self.segment_id,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "speed_kmh": round(self.speed_kmh, 1),
            "peak_accel_g": round(self.peak_accel_g, 3),
            "secondary_metric": round(self.secondary_metric, 3),
            "vehicle_id": self.vehicle_id or "anonymous",
            "description": self.description,
        }

    def to_sse_format(self) -> str:
        """Format event as a Server-Sent Events data frame."""
        payload = json.dumps(self.to_dict())
        return f"event: telematics_event\ndata: {payload}\n\n"


@dataclass(frozen=True, slots=True)
class StreamSubscriptionFilter:
    """Filter criteria for a streaming client subscription."""

    topics: tuple[str, ...] = field(default_factory=tuple)  # Empty means all topics
    min_lat: float | None = None
    max_lat: float | None = None
    min_lon: float | None = None
    max_lon: float | None = None
    min_severity: str = "moderate"  # moderate, severe, critical

    def matches(self, event: TelematicsStreamEvent) -> bool:
        """Check if an event matches subscription criteria."""
        # 1. Topic filter
        if self.topics and event.event_type not in self.topics:
            return False

        # 2. Bounding box spatial filter
        if self.min_lat is not None and event.latitude < self.min_lat:
            return False
        if self.max_lat is not None and event.latitude > self.max_lat:
            return False
        if self.min_lon is not None and event.longitude < self.min_lon:
            return False
        if self.max_lon is not None and event.longitude > self.max_lon:
            return False

        # 3. Severity filter
        severity_rank = {"info": 0, "moderate": 1, "severe": 2, "critical": 3}
        event_rank = severity_rank.get(event.severity, 0)
        min_rank = severity_rank.get(self.min_severity, 1)
        if event_rank < min_rank:
            return False

        return True


class StreamingEventManager:
    """Manages active WebSocket and SSE client queues and in-memory event distribution."""

    def __init__(self, capacity: int = STREAM_BUFFER_CAPACITY) -> None:
        self.capacity = capacity
        self._history: deque[TelematicsStreamEvent] = deque(maxlen=capacity)
        # Subscribers map: subscriber_id -> (queue, filter)
        self._subscribers: dict[str, tuple[asyncio.Queue[TelematicsStreamEvent], StreamSubscriptionFilter]] = {}
        self._lock = asyncio.Lock()

    @property
    def total_subscribers(self) -> int:
        return len(self._subscribers)

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent sliding-window events buffer."""
        evts = list(self._history)
        evts.reverse()
        return [e.to_dict() for e in evts[:limit]]

    def register_subscriber(
        self,
        subscriber_id: str,
        sub_filter: StreamSubscriptionFilter | None = None,
    ) -> asyncio.Queue[TelematicsStreamEvent]:
        """Register a new client queue with optional filtering."""
        q: asyncio.Queue[TelematicsStreamEvent] = asyncio.Queue(maxsize=100)
        flt = sub_filter or StreamSubscriptionFilter()
        self._subscribers[subscriber_id] = (q, flt)
        return q

    def unregister_subscriber(self, subscriber_id: str) -> None:
        """Remove a disconnected client queue."""
        self._subscribers.pop(subscriber_id, None)

    async def broadcast(self, event: TelematicsStreamEvent) -> int:
        """Broadcast an event to all matching active subscriber queues."""
        self._history.append(event)
        delivered_count = 0

        for sub_id, (q, flt) in list(self._subscribers.items()):
            if flt.matches(event):
                try:
                    # Non-blocking push; drop oldest if client queue is full
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    q.put_nowait(event)
                    delivered_count += 1
                except Exception:
                    # Drop dead queue
                    self._subscribers.pop(sub_id, None)

        return delivered_count

    def classify_and_build_event(self, raw: Mapping[str, Any]) -> TelematicsStreamEvent:
        """Classify raw kinematics or IMU metrics into a structured stream event."""
        event_id = str(raw.get("event_id") or f"evt-{uuid.uuid4().hex[:10]}")
        ts = str(raw.get("timestamp") or datetime.now(UTC).isoformat())
        source = str(raw.get("source_type") or "connected_vehicle")
        segment_id = str(raw.get("segment_id") or "corridor-bari-central")
        lat = float(raw.get("latitude", 41.117143))
        lon = float(raw.get("longitude", 16.871871))
        speed = float(raw.get("speed_kmh", 35.0))
        accel_x = float(raw.get("peak_accel_g", raw.get("accel_x_g", -0.42)))
        accel_y = float(raw.get("accel_y_g", 0.0))
        accel_z = float(raw.get("accel_z_g", 1.0))
        yaw_rate = float(raw.get("yaw_rate_degs", 0.0))
        psd_vibration = float(raw.get("psd_vibration", 0.0))

        # Default classification
        event_type = str(raw.get("event_type") or "")
        severity = str(raw.get("severity") or "")
        sec_metric = 0.0
        desc = ""

        # Kinematic Classification Logic
        if not event_type:
            if "e_scooter" in source or "e_bike" in source or "micromobility" in source:
                # 6-Axis IMU Rules
                if psd_vibration >= SIDEWALK_ROUGHNESS_G and speed <= 12.0:
                    event_type = "sidewalk_riding"
                    severity = "severe"
                    sec_metric = psd_vibration
                    desc = f"Sidewalk riding incursion detected (PSD={psd_vibration:.2f} at {speed:.1f} km/h)"
                elif accel_z >= CURB_STRIKE_THRESHOLD_G:
                    event_type = "curb_impact"
                    severity = "critical"
                    sec_metric = accel_z
                    desc = f"High-g vertical curb impact shock ({accel_z:.1f}g)"
                elif abs(yaw_rate) >= EVASIVE_SWERVE_YAW_DEG_S:
                    event_type = "evasive_swerve"
                    severity = "severe"
                    sec_metric = yaw_rate
                    desc = f"Evasive swerve maneuver ({yaw_rate:.1f}°/s)"
                else:
                    event_type = "kinematic_vibration"
                    severity = "moderate"
                    desc = f"Vibration anomaly on micromobility corridor"
            else:
                # Connected Vehicle FCD Rules
                if accel_x <= HARSH_BRAKING_THRESHOLDS["critical"]:
                    event_type = "harsh_braking"
                    severity = "critical"
                    desc = f"Critical collision-avoidance braking ({accel_x:.2f}g)"
                elif accel_x <= HARSH_BRAKING_THRESHOLDS["severe"]:
                    event_type = "harsh_braking"
                    severity = "severe"
                    desc = f"Emergency braking event ({accel_x:.2f}g)"
                elif accel_x <= HARSH_BRAKING_THRESHOLDS["moderate"]:
                    event_type = "harsh_braking"
                    severity = "moderate"
                    desc = f"Moderate deceleration ({accel_x:.2f}g)"
                elif abs(accel_y) >= HARSH_CORNERING_THRESHOLDS["critical"]:
                    event_type = "harsh_cornering"
                    severity = "critical"
                    sec_metric = accel_y
                    desc = f"Critical lateral loss-of-control cornering ({accel_y:.2f}g)"
                elif abs(accel_y) >= HARSH_CORNERING_THRESHOLDS["severe"]:
                    event_type = "harsh_cornering"
                    severity = "severe"
                    sec_metric = accel_y
                    desc = f"Severe cornering swerve ({accel_y:.2f}g)"
                else:
                    event_type = "sudden_speed_drop"
                    severity = "moderate"
                    desc = f"Kinematic traffic shockwave at {speed:.1f} km/h"

        if not severity:
            severity = "moderate"

        return TelematicsStreamEvent(
            event_id=event_id,
            timestamp=ts,
            event_type=event_type,
            source_type=source,
            severity=severity,
            segment_id=segment_id,
            latitude=lat,
            longitude=lon,
            speed_kmh=speed,
            peak_accel_g=accel_x,
            secondary_metric=sec_metric,
            vehicle_id=raw.get("vehicle_id"),
            description=desc or str(raw.get("description", "")),
        )

    def generate_demo_event(self) -> TelematicsStreamEvent:
        """Generate a realistic synthetic event for demo/verification rooms."""
        bari_corridors = [
            ("seg-via-sparano", 41.1215, 16.8698, "shared_e_scooter", "sidewalk_riding", "severe", -0.15, 0.58),
            ("seg-piazza-moro", 41.1180, 16.8702, "connected_vehicle", "harsh_braking", "critical", -0.62, 0.0),
            ("seg-corso-cavour", 41.1232, 16.8724, "connected_vehicle", "harsh_braking", "severe", -0.48, 0.0),
            ("seg-via-gentile", 41.1085, 16.8920, "commercial_fleet", "sudden_speed_drop", "moderate", -0.38, 0.0),
            ("seg-lungomare-nazario", 41.1250, 16.8785, "shared_e_bike", "curb_impact", "critical", -0.20, 3.10),
        ]
        seg_id, lat, lon, source, evt_type, sev, a_x, sec = random.choice(bari_corridors)  # nosec B311 # synthetic simulation/sampling, not security randomness
        # Jitter coordinates slightly
        lat += random.uniform(-0.001, 0.001)  # nosec B311 # synthetic simulation/sampling, not security randomness
        lon += random.uniform(-0.001, 0.001)  # nosec B311 # synthetic simulation/sampling, not security randomness

        return TelematicsStreamEvent(
            event_id=f"evt-live-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(UTC).isoformat(),
            event_type=evt_type,
            source_type=source,
            severity=sev,
            segment_id=seg_id,
            latitude=lat,
            longitude=lon,
            speed_kmh=round(random.uniform(12.0, 48.0), 1),  # nosec B311 # synthetic simulation/sampling, not security randomness
            peak_accel_g=a_x,
            secondary_metric=sec,
            vehicle_id=f"veh-{random.randint(100, 999)}",  # nosec B311 # synthetic simulation/sampling, not security randomness
            description=f"Live {evt_type.replace('_', ' ')} incident on {seg_id}",
        )


# Global singleton streaming manager instance
_GLOBAL_STREAM_MANAGER: StreamingEventManager | None = None


def get_global_stream_manager() -> StreamingEventManager:
    """Retrieve or initialize the global streaming event manager singleton."""
    global _GLOBAL_STREAM_MANAGER
    if _GLOBAL_STREAM_MANAGER is None:
        _GLOBAL_STREAM_MANAGER = StreamingEventManager()
        # Seed initial sliding buffer with demo events
        for _ in range(5):
            _GLOBAL_STREAM_MANAGER._history.append(_GLOBAL_STREAM_MANAGER.generate_demo_event())
    return _GLOBAL_STREAM_MANAGER
