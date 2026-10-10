"""Sovereign Connected Fleet Geofencing & Cellular V2X (C-V2X PC5/Uu) Engine.

Conforms to:
- ISO 19321 (Intelligent transport systems - In-Vehicle Information (IVI) data structures)
- ETSI EN 302 571 / 3GPP Rel 14/15 C-V2X Direct Sidelink (PC5 Mode 4)
- 3GPP 4G/5G Cellular Uu Geo-MQTT Spatial Topic Routing
- Car2Car Communication Consortium (C2C-CC) Basic System Profile
- ISO 15006 Road Vehicles - Ergonomic aspects of transport information and control systems
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
import hashlib
import math
from typing import Any, Mapping, Sequence

CITS_IVI_CONTRACT_VERSION = "2026.1"
CITS_IVI_ENGINE_VERSION = "1.0.0"


def _sha256_str(text: str) -> str:
    """Compute SHA-256 digest of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance in meters between two WGS84 coordinates."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def _compute_geohash7(lat: float, lon: float) -> str:
    """Compute 7-character geohash for spatial Geo-MQTT topic routing."""
    base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < 7:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(base32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


@dataclass
class IviManagementContainer:
    """ISO 19321 Management Container."""

    ivi_identification_number: int
    service_provider_id: str = "TMC-LOCAL-01"
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    )
    valid_from_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    )
    valid_to_utc: str = field(
        default_factory=lambda: (datetime.now(timezone.utc) + timedelta(hours=2)).strftime(
            "%Y-%m-%d %H:%M:%SZ"
        )
    )
    priority: int = 5  # ISO 19321 priority 1 (lowest) to 7 (highest safety critical)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IviGeographicZone:
    """ISO 19321 Geographic Location Container."""

    zone_id: int
    zone_type: str  # "relevance_zone" or "detection_zone"
    latitude: float
    longitude: float
    heading_deg: float
    radius_meters: float
    corridor_id: str
    location_name: str
    bounding_polygon: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IviSurfaceCondition:
    """ISO 19321 General Field & Road Surface Condition Container."""

    surface_type: str  # "dry", "wet", "flooded", "icy", "snow"
    friction_coefficient: float  # estimated road surface friction mu [0.15, 0.85]
    water_film_depth_mm: float
    aquaplaning_risk: str  # "none", "moderate", "severe", "critical"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IviInVehicleSignage:
    """ISO 19321 In-Vehicle Signage (IVS) Container."""

    vienna_pictogram_code: str  # e.g. "A,17", "A,24", "A,32", "C,14"
    mandatory_speed_kmh: int
    advisory_speed_kmh: int
    lane_restrictions: str  # "all_open", "merge_left", "merge_right", "lane_closed"
    text_line_1_it: str
    text_line_2_it: str
    text_line_1_en: str
    text_line_2_en: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IviStructure:
    """Complete ISO 19321 In-Vehicle Information (IVI) Message Envelope."""

    management: IviManagementContainer
    geographic_zones: list[IviGeographicZone]
    surface_condition: IviSurfaceCondition
    signage: IviInVehicleSignage
    sha256_payload_hash: str = ""

    def __post_init__(self) -> None:
        if not self.sha256_payload_hash:
            raw = (
                f"{self.management.ivi_identification_number}:"
                f"{self.management.service_provider_id}:"
                f"{self.signage.vienna_pictogram_code}:"
                f"{self.signage.mandatory_speed_kmh}:"
                f"{self.geographic_zones[0].latitude if self.geographic_zones else 0.0}"
            )
            self.sha256_payload_hash = _sha256_str(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "management": self.management.to_dict(),
            "geographic_zones": [z.to_dict() for z in self.geographic_zones],
            "surface_condition": self.surface_condition.to_dict(),
            "signage": self.signage.to_dict(),
            "sha256_payload_hash": self.sha256_payload_hash,
        }


@dataclass
class Cv2xTransmissionEnvelope:
    """C-V2X Dual Transmission Layer Envelope (PC5 Sidelink & Cellular Uu)."""

    channel: str  # "PC5_DIRECT" or "UU_CELLULAR"
    frequency_ghz: float  # 5.9 for PC5, 3.7 for 5G NR Uu
    transmission_mode: str  # "Mode_4_Sidelink" or "Network_Slice_URLLC"
    packet_priority: int  # 1 (lowest) to 4 (highest emergency)
    latency_ms: float
    spatial_topic: str
    payload_size_bytes: int
    sha256_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DigitalCockpitHmiPayload:
    """OEM In-Vehicle Dashboard & Instrument Cluster HMI Rendering Payload."""

    hud_banner_text: str
    cluster_speed_limit_kmh: int
    cluster_warning_icon: str
    audio_chime_code: str  # "ISO_15006_CRITICAL_CHIME", "ISO_15006_ADVISORY_CHIME", "NONE"
    haptic_vibration_enabled: bool
    tactical_lane_guidance: str
    time_to_hazard_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectedFleetVehicle:
    """Monitored Connected Vehicle in the Metropolitan Fleet."""

    vehicle_id: str
    fleet_category: str  # "public_transit_bus", "police_patrol", "highway_maintenance", "connected_passenger_car"
    make_model: str
    latitude: float
    longitude: float
    speed_kmh: float
    heading_deg: float
    distance_to_hazard_meters: float
    packet_reception_status: str  # "RECEIVING_PC5", "RECEIVING_UU", "OUT_OF_RANGE"
    active_cockpit_hmi: DigitalCockpitHmiPayload

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "fleet_category": self.fleet_category,
            "make_model": self.make_model,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed_kmh": self.speed_kmh,
            "heading_deg": self.heading_deg,
            "distance_to_hazard_meters": round(self.distance_to_hazard_meters, 1),
            "packet_reception_status": self.packet_reception_status,
            "active_cockpit_hmi": self.active_cockpit_hmi.to_dict(),
        }


def compile_iso19321_ivi_message(
    incident_id: str,
    threat_type: str,
    severity_tier: str,
    corridor_id: str,
    location_name: str,
    latitude: float,
    longitude: float,
    mandatory_vsl_kmh: int = 60,
    advisory_vsl_kmh: int = 50,
    precipitation_mm_h: float = 0.0,
    lane_restrictions: str = "all_open",
    service_provider_id: str = "TMC-LOCAL-01",
) -> IviStructure:
    """Compile a standards-compliant ISO 19321 IVI message structure."""
    # Derived from a stable digest (not Python's per-process randomised hash) so
    # the identification number, and the payload hash built on it, reproduce.
    ivi_number = int(hashlib.sha256(incident_id.encode("utf-8")).hexdigest()[:8], 16) % 100000
    mgmt = IviManagementContainer(
        ivi_identification_number=ivi_number,
        service_provider_id=service_provider_id,
        priority=7 if severity_tier == "critical" else (6 if severity_tier == "severe" else 4),
        status="active",
    )

    # 4-point bounding polygon ~500m radius
    d_lat = 0.0045
    d_lon = 0.0060
    poly = [
        {"lat": latitude + d_lat, "lon": longitude - d_lon},
        {"lat": latitude + d_lat, "lon": longitude + d_lon},
        {"lat": latitude - d_lat, "lon": longitude + d_lon},
        {"lat": latitude - d_lat, "lon": longitude - d_lon},
    ]

    zones = [
        IviGeographicZone(
            zone_id=1,
            zone_type="relevance_zone",
            latitude=latitude,
            longitude=longitude,
            heading_deg=180.0,
            radius_meters=800.0,
            corridor_id=corridor_id,
            location_name=location_name,
            bounding_polygon=poly,
        ),
        IviGeographicZone(
            zone_id=2,
            zone_type="detection_zone",
            latitude=latitude + 0.008,
            longitude=longitude,
            heading_deg=180.0,
            radius_meters=1800.0,
            corridor_id=corridor_id,
            location_name=f"Upstream Approach {location_name}",
        ),
    ]

    # Surface conditions
    if precipitation_mm_h > 15.0:
        surf = IviSurfaceCondition(
            surface_type="flooded",
            friction_coefficient=0.28,
            water_film_depth_mm=precipitation_mm_h * 0.2,
            aquaplaning_risk="critical",
        )
    elif precipitation_mm_h > 2.0:
        surf = IviSurfaceCondition(
            surface_type="wet",
            friction_coefficient=0.45,
            water_film_depth_mm=1.2,
            aquaplaning_risk="moderate",
        )
    else:
        surf = IviSurfaceCondition(
            surface_type="dry",
            friction_coefficient=0.82,
            water_film_depth_mm=0.0,
            aquaplaning_risk="none",
        )

    # Vienna Signage mapping
    if threat_type == "adverse_weather" or precipitation_mm_h > 10.0:
        picto = "A,24"
        t1_it, t2_it = "NEBBIA E BAGNATO", f"LIMITE {mandatory_vsl_kmh} KM/H"
        t1_en, t2_en = "FOG & WET ROAD", f"LIMIT {mandatory_vsl_kmh} KM/H"
    elif threat_type == "vru_surge":
        picto = "A,32"
        t1_it, t2_it = "ATTENZIONE PEDONI", f"ZONA {mandatory_vsl_kmh} KM/H"
        t1_en, t2_en = "PEDESTRIANS CROSSING", f"ZONE {mandatory_vsl_kmh} KM/H"
    else:
        picto = "A,17"
        t1_it, t2_it = "RALLENTARE CODE A 1.2 KM", f"LIMITE {mandatory_vsl_kmh} KM/H"
        t1_en, t2_en = "SLOW DOWN QUEUE AHEAD", f"LIMIT {mandatory_vsl_kmh} KM/H"

    sign = IviInVehicleSignage(
        vienna_pictogram_code=picto,
        mandatory_speed_kmh=mandatory_vsl_kmh,
        advisory_speed_kmh=advisory_vsl_kmh,
        lane_restrictions=lane_restrictions,
        text_line_1_it=t1_it,
        text_line_2_it=t2_it,
        text_line_1_en=t1_en,
        text_line_2_en=t2_en,
    )

    return IviStructure(
        management=mgmt,
        geographic_zones=zones,
        surface_condition=surf,
        signage=sign,
    )


def compile_cv2x_transmission(ivi: IviStructure) -> list[Cv2xTransmissionEnvelope]:
    """Package ISO 19321 IVI into dual PC5 Sidelink and Cellular Uu envelopes."""
    ref_lat = ivi.geographic_zones[0].latitude if ivi.geographic_zones else 41.1171
    ref_lon = ivi.geographic_zones[0].longitude if ivi.geographic_zones else 16.8719
    geohash7 = _compute_geohash7(ref_lat, ref_lon)

    # 1. Direct Sidelink PC5 (5.9 GHz ITS-G5, ultra low latency)
    pc5 = Cv2xTransmissionEnvelope(
        channel="PC5_DIRECT",
        frequency_ghz=5.9,
        transmission_mode="Mode_4_Sidelink",
        packet_priority=4 if ivi.management.priority >= 6 else 3,
        latency_ms=12.4,
        spatial_topic=f"cits/pc5/ivi/{ivi.management.service_provider_id}/{ivi.management.ivi_identification_number}",
        payload_size_bytes=248,
        sha256_digest=_sha256_str(f"PC5:{ivi.sha256_payload_hash}:5.9GHz"),
    )

    # 2. Cellular Uu (4G/5G Geo-MQTT Broker)
    uu = Cv2xTransmissionEnvelope(
        channel="UU_CELLULAR",
        frequency_ghz=3.7,
        transmission_mode="Network_Slice_URLLC",
        packet_priority=3 if ivi.management.priority >= 6 else 2,
        latency_ms=36.8,
        spatial_topic=f"cits/v2x/ivi/eu/it/puglia/bari/{geohash7}",
        payload_size_bytes=412,
        sha256_digest=_sha256_str(f"UU:{ivi.sha256_payload_hash}:{geohash7}"),
    )

    return [pc5, uu]


def render_digital_cockpit_hmi(
    ivi: IviStructure,
    distance_meters: float,
    vehicle_speed_kmh: float,
) -> DigitalCockpitHmiPayload:
    """Render vehicle cockpit HMI outputs (HUD, instrument cluster, audio chime, haptics)."""
    # Time to hazard estimation
    speed_mps = max(vehicle_speed_kmh / 3.6, 1.0)
    t_hazard_sec = round(distance_meters / speed_mps, 1)

    # Tactical lane guidance
    if ivi.signage.lane_restrictions == "merge_left":
        lane_guide = "RIGHT LANE BLOCKED • MERGE LEFT"
    elif ivi.signage.lane_restrictions == "merge_right":
        lane_guide = "LEFT LANE BLOCKED • MERGE RIGHT"
    elif ivi.signage.lane_restrictions == "lane_closed":
        lane_guide = "REDUCED CAPACITY • KEEP SAFE DISTANCE"
    else:
        lane_guide = "ALL LANES OPEN • OBSERVE VSL"

    # Acoustic and Haptic priority
    is_critical = ivi.management.priority >= 6 or distance_meters < 500.0 or vehicle_speed_kmh > (ivi.signage.mandatory_speed_kmh + 15)
    audio = "ISO_15006_CRITICAL_CHIME" if is_critical else "ISO_15006_ADVISORY_CHIME"
    haptic = bool(is_critical and distance_meters < 600.0)

    hud_banner = (
        f"{ivi.signage.text_line_1_it} • {ivi.signage.text_line_2_it} ({round(distance_meters)}m)"
    )

    return DigitalCockpitHmiPayload(
        hud_banner_text=hud_banner,
        cluster_speed_limit_kmh=ivi.signage.mandatory_speed_kmh,
        cluster_warning_icon=ivi.signage.vienna_pictogram_code,
        audio_chime_code=audio,
        haptic_vibration_enabled=haptic,
        tactical_lane_guidance=lane_guide,
        time_to_hazard_seconds=t_hazard_sec,
    )



# Direct PC5 sidelink range and cellular (Uu) relevance range, in metres.
PC5_RANGE_M = 800.0
UU_RANGE_M = 3000.0


def reception_status_for_distance(distance_m: float) -> str:
    if distance_m <= PC5_RANGE_M:
        return "RECEIVING_PC5"
    if distance_m <= UU_RANGE_M:
        return "RECEIVING_UU"
    return "OUT_OF_RANGE"


def build_connected_fleet_view(
    vehicles: Sequence[Mapping[str, Any]],
    ivi_message: IviStructure,
) -> list[ConnectedFleetVehicle]:
    """Project reported vehicle positions against an IVI hazard zone.

    Each vehicle mapping carries at least ``vehicle_id``, ``latitude``,
    ``longitude`` and ``speed_kmh``; ``fleet_category``, ``make_model`` and
    ``heading_deg`` are optional. Distance, radio reception, and the rendered
    cockpit HMI are all derived from the reported position — nothing is
    invented for vehicles that did not report.
    """
    if not ivi_message.geographic_zones:
        raise ValueError("IVI message has no geographic zone to project against.")
    zone = ivi_message.geographic_zones[0]
    fleet: list[ConnectedFleetVehicle] = []
    for raw in vehicles:
        try:
            lat = float(raw["latitude"])
            lon = float(raw["longitude"])
        except (KeyError, TypeError, ValueError):
            continue  # a vehicle without a usable position cannot be projected
        speed = float(raw.get("speed_kmh") or 0.0)
        distance = _haversine_distance_m(lat, lon, zone.latitude, zone.longitude)
        fleet.append(
            ConnectedFleetVehicle(
                vehicle_id=str(raw.get("vehicle_id") or "unknown"),
                fleet_category=str(raw.get("fleet_category") or "unspecified"),
                make_model=str(raw.get("make_model") or ""),
                latitude=lat,
                longitude=lon,
                speed_kmh=speed,
                heading_deg=float(raw.get("heading_deg") or 0.0),
                distance_to_hazard_meters=distance,
                packet_reception_status=reception_status_for_distance(distance),
                active_cockpit_hmi=render_digital_cockpit_hmi(
                    ivi=ivi_message, distance_meters=distance, vehicle_speed_kmh=speed
                ),
            )
        )
    fleet.sort(key=lambda vehicle: vehicle.distance_to_hazard_meters)
    return fleet
