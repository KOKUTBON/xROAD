"""Automated Computer Vision Road Safety Auditing & iRAP Feature Extraction Engine.

Implements automated road asset detection parsing, spatial frame aggregation,
roadside hazard and pavement defect scoring, and direct automated translation
to iRAP 1-5 Star Ratings (aligned with EU Horizon Europe IVORY & Mobileye REM).
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .irap_engine import IrapSegmentRating, assess_segment_irap
from .modeling import _sha256


CV_ENGINE_VERSION = "cv_road_audit_v1"
CV_CONTRACT_VERSION = "cv_road_audit_public_v1"


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return default if math.isnan(val) else float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "null", ""}:
        return default
    try:
        f = float(s)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    f = _safe_float(val, float(default))
    return int(round(f))


@dataclass(frozen=True, slots=True)
class RoadAssetDetection:
    """A single roadway infrastructure asset, hazard, or defect detected by computer vision."""

    detection_id: str
    asset_class: str
    confidence: float
    relative_position: str = "center"  # left, right, center, roadside_left, roadside_right
    estimated_distance_m: float = 10.0
    bbox: list[float] | None = None     # [ymin, xmin, ymax, xmax] normalized
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "asset_class": self.asset_class,
            "confidence": round(self.confidence, 3),
            "relative_position": self.relative_position,
            "estimated_distance_m": round(self.estimated_distance_m, 1),
            "bbox": self.bbox,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class FrameSafetyObservation:
    """A street-level video frame or inspection image with localized asset detections."""

    frame_id: str
    segment_id: str
    timestamp: str
    latitude: float | None = None
    longitude: float | None = None
    heading_deg: float | None = None
    speed_kmh: float | None = None
    detections: list[RoadAssetDetection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "segment_id": self.segment_id,
            "timestamp": self.timestamp,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "heading_deg": self.heading_deg,
            "speed_kmh": self.speed_kmh,
            "detections": [d.to_dict() for d in self.detections],
        }


@dataclass(frozen=True, slots=True)
class AuditedSegmentFeatures:
    """Aggregated computer-vision derived infrastructure attributes and automated iRAP rating."""

    segment_id: str
    length_km: float
    total_frames_analyzed: int
    has_median_barrier: bool
    median_barrier_confidence: float
    is_divided: bool
    has_roadside_barrier: bool
    roadside_barrier_confidence: float
    roadside_hazard_severity: float  # 0.0 (clear zone) to 1.0 (unshielded concrete/trees)
    has_sidewalk: bool
    sidewalk_coverage_pct: float
    has_pedestrian_crossing: bool
    has_segregated_cycle_facility: bool
    pothole_count_total: int
    pothole_density_per_km: float
    marking_quality_score: float     # 0.0 (faded/absent) to 1.0 (fresh crisp markings)
    street_lighting_detected: bool
    irap_star_ratings: dict[str, Any]
    audit_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "length_km": round(self.length_km, 3),
            "total_frames_analyzed": self.total_frames_analyzed,
            "vision_attributes": {
                "has_median_barrier": self.has_median_barrier,
                "median_barrier_confidence": round(self.median_barrier_confidence, 2),
                "is_divided": self.is_divided,
                "has_roadside_barrier": self.has_roadside_barrier,
                "roadside_barrier_confidence": round(self.roadside_barrier_confidence, 2),
                "roadside_hazard_severity": round(self.roadside_hazard_severity, 2),
                "has_sidewalk": self.has_sidewalk,
                "sidewalk_coverage_pct": round(self.sidewalk_coverage_pct, 1),
                "has_pedestrian_crossing": self.has_pedestrian_crossing,
                "has_segregated_cycle_facility": self.has_segregated_cycle_facility,
                "pothole_count_total": self.pothole_count_total,
                "pothole_density_per_km": round(self.pothole_density_per_km, 2),
                "marking_quality_score": round(self.marking_quality_score, 2),
                "street_lighting_detected": self.street_lighting_detected,
            },
            "automated_irap_assessment": self.irap_star_ratings,
            "audit_timestamp": self.audit_timestamp,
        }


def parse_frame_observations(raw_frames: Sequence[Mapping[str, Any]]) -> list[FrameSafetyObservation]:
    """Parse raw frame observations and asset detections from JSON/dict records."""
    observations: list[FrameSafetyObservation] = []

    for idx, f in enumerate(raw_frames, start=1):
        fid = str(f.get("frame_id") or f"frame-{idx:05d}")
        seg_id = str(f.get("segment_id") or f.get("id") or "seg-unknown")
        ts = str(f.get("timestamp") or datetime.now(UTC).isoformat())
        lat = _safe_float(f.get("latitude") or f.get("lat")) or None
        lon = _safe_float(f.get("longitude") or f.get("lon")) or None
        heading = _safe_float(f.get("heading_deg") or f.get("heading")) or None
        speed = _safe_float(f.get("speed_kmh") or f.get("speed")) or None

        raw_dets = f.get("detections", [])
        parsed_dets: list[RoadAssetDetection] = []
        for didx, d in enumerate(raw_dets, start=1):
            det_id = str(d.get("detection_id") or f"{fid}-d{didx}")
            aclass = str(d.get("asset_class") or d.get("class") or "unknown").lower()
            conf = _safe_float(d.get("confidence") or 0.85)
            pos = str(d.get("relative_position") or "center").lower()
            dist = _safe_float(d.get("estimated_distance_m") or 10.0)
            bbox = d.get("bbox") if isinstance(d.get("bbox"), list) else None

            parsed_dets.append(
                RoadAssetDetection(
                    detection_id=det_id,
                    asset_class=aclass,
                    confidence=conf,
                    relative_position=pos,
                    estimated_distance_m=dist,
                    bbox=bbox,
                    metadata=dict(d.get("metadata") or {}),
                )
            )

        observations.append(
            FrameSafetyObservation(
                frame_id=fid,
                segment_id=seg_id,
                timestamp=ts,
                latitude=lat,
                longitude=lon,
                heading_deg=heading,
                speed_kmh=speed,
                detections=parsed_dets,
            )
        )

    return observations


def aggregate_frame_detections_to_segments(
    segments: Sequence[Mapping[str, Any]],
    observations: Sequence[FrameSafetyObservation],
) -> list[AuditedSegmentFeatures]:
    """Aggregate frame detections onto road segments and evaluate automated iRAP attributes."""
    # Index frames by segment_id
    frames_by_segment: dict[str, list[FrameSafetyObservation]] = {}
    for frame in observations:
        frames_by_segment.setdefault(frame.segment_id, []).append(frame)

    results: list[AuditedSegmentFeatures] = []
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    for seg in segments:
        seg_id = str(seg.get("segment_id") or seg.get("id") or "seg-unknown")
        length_km = _safe_float(seg.get("length_km") or (_safe_float(seg.get("segment_length_m"), 200.0) / 1000.0), 0.2)
        length_km = max(0.05, length_km)
        aadt = _safe_float(seg.get("aadt") or seg.get("flow_daily_estimate") or 2500.0)
        speed = _safe_float(seg.get("operating_speed_kmh") or seg.get("maxspeed_numeric") or 50.0)

        frames = frames_by_segment.get(seg_id, [])
        total_frames = len(frames)

        if total_frames > 0:
            # Flatten detections
            all_dets: list[RoadAssetDetection] = [d for f in frames for d in f.detections]

            # 1. Median Barrier & Divided Roadway
            median_barrier_dets = [
                d for d in all_dets
                if d.asset_class in {"median_barrier_concrete", "median_barrier_guardrail", "jersey_barrier"}
            ]
            has_median_barrier = len(median_barrier_dets) >= max(1, int(total_frames * 0.3))
            median_conf = (
                sum(d.confidence for d in median_barrier_dets) / len(median_barrier_dets)
                if median_barrier_dets else 0.0
            )
            is_divided = has_median_barrier or bool(seg.get("is_divided") or False)

            # 2. Roadside Safety Barrier (Guardrail)
            roadside_barrier_dets = [
                d for d in all_dets
                if d.asset_class in {"guardrail_w_beam", "roadside_barrier", "cable_barrier"}
            ]
            has_roadside_barrier = len(roadside_barrier_dets) >= max(1, int(total_frames * 0.25))
            roadside_conf = (
                sum(d.confidence for d in roadside_barrier_dets) / len(roadside_barrier_dets)
                if roadside_barrier_dets else 0.0
            )

            # 3. Roadside Hazard Severity
            # Rigid unshielded poles, trees, concrete walls, steep drop-offs
            rigid_hazards = [
                d for d in all_dets
                if d.asset_class in {"rigid_pole", "tree_unshielded", "concrete_pillar", "steep_embankment"}
            ]
            if has_roadside_barrier:
                hazard_severity = 0.2  # Shielded roadside
            elif len(rigid_hazards) >= 2:
                hazard_severity = 0.85  # Severe unshielded hazard cluster
            elif len(rigid_hazards) == 1:
                hazard_severity = 0.60
            else:
                hazard_severity = 0.35  # Nominal clear zone

            # 4. Sidewalks & Pedestrian Infrastructure
            sidewalk_frames = sum(
                1 for f in frames
                if any(d.asset_class in {"paved_sidewalk", "footpath", "pedestrian_walkway"} for d in f.detections)
            )
            sidewalk_cov = (sidewalk_frames / total_frames) * 100.0
            has_sidewalk = sidewalk_cov >= 40.0  # At least 40% coverage along segment

            # 5. Pedestrian Crossings (Zebra / Signalized)
            has_crossing = any(
                d.asset_class in {"crosswalk_zebra", "pedestrian_crossing_signal", "refuge_island"}
                for d in all_dets
            )

            # 6. Segregated Cycle Track
            has_cycle = any(
                d.asset_class in {"segregated_cycleway", "cycle_track_protected", "bike_lane_segregated"}
                for d in all_dets
            )

            # 7. Surface Condition & Markings
            potholes = [d for d in all_dets if d.asset_class in {"pothole", "pavement_defect", "rutting"}]
            pothole_count = len(potholes)
            pothole_density = pothole_count / length_km

            faded_markings = [d for d in all_dets if d.asset_class in {"faded_marking", "worn_centerline"}]
            good_markings = [d for d in all_dets if d.asset_class in {"crisp_marking", "fresh_road_line"}]
            if (len(faded_markings) + len(good_markings)) > 0:
                marking_score = len(good_markings) / (len(good_markings) + len(faded_markings))
            else:
                marking_score = 0.70  # default baseline

            # 8. Street Lighting
            has_lighting = any(
                d.asset_class in {"street_light", "street_lamp", "overhead_lighting"}
                for d in all_dets
            )

        else:
            # Fallback to segment metadata if no vision frames were captured for this segment
            has_median_barrier = bool(seg.get("has_median_barrier") or False)
            median_conf = 0.0
            is_divided = bool(seg.get("is_divided") or False)
            has_roadside_barrier = bool(seg.get("has_roadside_barrier") or False)
            roadside_conf = 0.0
            hazard_severity = 0.40
            has_sidewalk = bool(seg.get("has_sidewalk") or False)
            sidewalk_cov = 100.0 if has_sidewalk else 0.0
            has_crossing = bool(seg.get("has_pedestrian_crossing") or False)
            has_cycle = bool(seg.get("has_segregated_cycle_facility") or False)
            pothole_count = 0
            pothole_density = 0.0
            marking_score = 0.75
            has_lighting = True

        # Translate vision features directly to iRAP Star Ratings
        irap_input = {
            "segment_id": seg_id,
            "length_km": length_km,
            "aadt": aadt,
            "operating_speed_kmh": speed,
            "lanes_numeric": _safe_int(seg.get("lanes_numeric") or seg.get("lanes") or 2),
            "width_numeric": _safe_float(seg.get("width_numeric") or seg.get("width") or 7.0),
            "is_divided": is_divided,
            "has_median_barrier": has_median_barrier,
            "has_roadside_barrier": has_roadside_barrier,
            "roadside_hazard_severity": hazard_severity,
            "has_sidewalk": has_sidewalk,
            "has_pedestrian_crossing": has_crossing,
            "has_segregated_cycle_facility": has_cycle,
        }
        rating: IrapSegmentRating = assess_segment_irap(irap_input)

        results.append(
            AuditedSegmentFeatures(
                segment_id=seg_id,
                length_km=length_km,
                total_frames_analyzed=total_frames,
                has_median_barrier=has_median_barrier,
                median_barrier_confidence=median_conf,
                is_divided=is_divided,
                has_roadside_barrier=has_roadside_barrier,
                roadside_barrier_confidence=roadside_conf,
                roadside_hazard_severity=hazard_severity,
                has_sidewalk=has_sidewalk,
                sidewalk_coverage_pct=sidewalk_cov,
                has_pedestrian_crossing=has_crossing,
                has_segregated_cycle_facility=has_cycle,
                pothole_count_total=pothole_count,
                pothole_density_per_km=pothole_density,
                marking_quality_score=marking_score,
                street_lighting_detected=has_lighting,
                irap_star_ratings=rating.scores.to_dict(),
                audit_timestamp=timestamp,
            )
        )

    return results


def export_cv_audit_artifacts(
    audited_segments: Sequence[AuditedSegmentFeatures],
    raw_observations: Sequence[FrameSafetyObservation],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export computer vision road auditing artifacts (CSV, JSON bundle, Markdown report, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export Segment CV Features & iRAP Ratings CSV
    csv_path = out_dir / f"{network_label}_cv_audited_segments.csv"
    fieldnames = [
        "segment_id", "length_km", "total_frames_analyzed",
        "has_median_barrier", "is_divided", "has_roadside_barrier",
        "roadside_hazard_severity", "has_sidewalk", "sidewalk_coverage_pct",
        "has_pedestrian_crossing", "has_segregated_cycle_facility",
        "pothole_count_total", "pothole_density_per_km", "marking_quality_score",
        "street_lighting_detected", "vehicle_stars", "motorcycle_stars",
        "bicycle_stars", "pedestrian_stars", "minimum_stars_overall", "meets_un_target_4"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for seg in audited_segments:
            irap = seg.irap_star_ratings
            writer.writerow({
                "segment_id": seg.segment_id,
                "length_km": round(seg.length_km, 3),
                "total_frames_analyzed": seg.total_frames_analyzed,
                "has_median_barrier": seg.has_median_barrier,
                "is_divided": seg.is_divided,
                "has_roadside_barrier": seg.has_roadside_barrier,
                "roadside_hazard_severity": round(seg.roadside_hazard_severity, 2),
                "has_sidewalk": seg.has_sidewalk,
                "sidewalk_coverage_pct": round(seg.sidewalk_coverage_pct, 1),
                "has_pedestrian_crossing": seg.has_pedestrian_crossing,
                "has_segregated_cycle_facility": seg.has_segregated_cycle_facility,
                "pothole_count_total": seg.pothole_count_total,
                "pothole_density_per_km": round(seg.pothole_density_per_km, 2),
                "marking_quality_score": round(seg.marking_quality_score, 2),
                "street_lighting_detected": seg.street_lighting_detected,
                "vehicle_stars": irap.get("vehicle_occupant", {}).get("star_rating", 3),
                "motorcycle_stars": irap.get("motorcyclist", {}).get("star_rating", 3),
                "bicycle_stars": irap.get("bicyclist", {}).get("star_rating", 3),
                "pedestrian_stars": irap.get("pedestrian", {}).get("star_rating", 3),
                "minimum_stars_overall": irap.get("minimum_stars_overall", 3),
                "meets_un_target_4": irap.get("meets_un_target_4", False),
            })

    # 2. Export Detected Road Assets CSV
    assets_csv_path = out_dir / f"{network_label}_cv_detected_assets.csv"
    asset_fields = ["frame_id", "segment_id", "detection_id", "asset_class", "confidence", "relative_position", "estimated_distance_m"]
    with assets_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=asset_fields)
        writer.writeheader()
        for f in raw_observations:
            for d in f.detections:
                writer.writerow({
                    "frame_id": f.frame_id,
                    "segment_id": f.segment_id,
                    "detection_id": d.detection_id,
                    "asset_class": d.asset_class,
                    "confidence": round(d.confidence, 3),
                    "relative_position": d.relative_position,
                    "estimated_distance_m": round(d.estimated_distance_m, 1),
                })

    # 3. Export Comprehensive JSON Bundle
    json_path = out_dir / f"{network_label}_cv_audit_bundle.json"
    total_segments = len(audited_segments)
    un_target_compliant = sum(1 for s in audited_segments if s.irap_star_ratings.get("meets_un_target_4", False))
    potholes_total = sum(s.pothole_count_total for s in audited_segments)
    payload = {
        "cv_engine_version": CV_ENGINE_VERSION,
        "contract_version": CV_CONTRACT_VERSION,
        "network_label": network_label,
        "generated_at_utc": timestamp,
        "summary": {
            "total_segments_audited": total_segments,
            "total_inspection_frames": len(raw_observations),
            "total_assets_detected": sum(len(f.detections) for f in raw_observations),
            "total_potholes_detected": potholes_total,
            "un_target_4_compliance_pct": round((un_target_compliant / max(1, total_segments)) * 100.0, 2),
            "infrastructure_summary": {
                "segments_with_sidewalks": sum(1 for s in audited_segments if s.has_sidewalk),
                "segments_with_median_barriers": sum(1 for s in audited_segments if s.has_median_barrier),
                "segments_with_cycle_tracks": sum(1 for s in audited_segments if s.has_segregated_cycle_facility),
                "segments_with_roadside_barriers": sum(1 for s in audited_segments if s.has_roadside_barrier),
            },
        },
        "audited_segments_sample": [s.to_dict() for s in audited_segments[:50]],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 4. Export Markdown Executive Inspection Report
    md_path = out_dir / f"{network_label}_cv_road_inspection_report.md"
    lines = [
        f"# Automated Computer Vision Road Safety Audit: {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        "- **Standard Alignment:** EU Horizon Europe IVORY & iRAP Automated Video Inspection Protocols",
        f"- **Total Network Segments Audited:** {total_segments:,}",
        f"- **Total Inspection Frames Analyzed:** {len(raw_observations):,}",
        f"- **Total Roadside Infrastructure Assets Detected:** {payload['summary']['total_assets_detected']:,}",
        f"- **Total Surface Potholes & Pavement Defects:** **{potholes_total:,}** defects",
        f"- **UN Target 4 Compliance (Automated iRAP ≥ 3★):** **{payload['summary']['un_target_4_compliance_pct']:.1f}%**",
        "",
        "## Infrastructure Inventory from Vision Detections",
        "",
        "| Infrastructure Feature | Audited Count | Coverage (% of Network) |",
        "| :--- | ---: | ---: |",
        f"| 🚶 Continuous Paved Sidewalks | {payload['summary']['infrastructure_summary']['segments_with_sidewalks']:,} | {payload['summary']['infrastructure_summary']['segments_with_sidewalks'] / max(1, total_segments) * 100.0:.1f}% |",
        f"| 🛡️ Central Median Safety Barriers | {payload['summary']['infrastructure_summary']['segments_with_median_barriers']:,} | {payload['summary']['infrastructure_summary']['segments_with_median_barriers'] / max(1, total_segments) * 100.0:.1f}% |",
        f"| 🚲 Segregated Bicycle Tracks | {payload['summary']['infrastructure_summary']['segments_with_cycle_tracks']:,} | {payload['summary']['infrastructure_summary']['segments_with_cycle_tracks'] / max(1, total_segments) * 100.0:.1f}% |",
        f"| 🚧 Roadside Guardrails | {payload['summary']['infrastructure_summary']['segments_with_roadside_barriers']:,} | {payload['summary']['infrastructure_summary']['segments_with_roadside_barriers'] / max(1, total_segments) * 100.0:.1f}% |",
        "",
        "## Sample Audited Corridors (Vision Features & Automated Stars)",
        "",
        "| Segment ID | Length | Sidewalk | Barrier | Hazards | Potholes | Markings | Stars (Veh/Moto/Bike/Ped) | UN Target 4 |",
        "| :--- | ---: | :---: | :---: | ---: | ---: | ---: | :---: | :---: |",
    ]
    for s in audited_segments[:25]:
        irap = s.irap_star_ratings
        veh = irap.get("vehicle_occupant", {}).get("star_rating", 3)
        moto = irap.get("motorcyclist", {}).get("star_rating", 3)
        bike = irap.get("bicyclist", {}).get("star_rating", 3)
        ped = irap.get("pedestrian", {}).get("star_rating", 3)
        stars_str = f"{veh}★/{moto}★/{bike}★/{ped}★"
        t4_str = "✅ Pass" if irap.get("meets_un_target_4") else "❌ Fail"
        lines.append(
            f"| `{s.segment_id}` | {s.length_km:.2f} km | {'Yes' if s.has_sidewalk else 'No'} ({s.sidewalk_coverage_pct:.0f}%) | {'Yes' if s.has_median_barrier else 'No'} | {s.roadside_hazard_severity:.2f} | {s.pothole_count_total} | {s.marking_quality_score:.2f} | {stars_str} | {t4_str} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 5. Export Manifest
    manifest_path = out_dir / f"{network_label}_cv_audit.manifest.json"
    manifest = {
        "artifact_family": "computer_vision_road_audit",
        "network_label": network_label,
        "cv_engine_version": CV_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "segments_csv": {"path": str(csv_path.name), "sha256": _sha256(csv_path)},
            "assets_csv": {"path": str(assets_csv_path.name), "sha256": _sha256(assets_csv_path)},
            "bundle_json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "report_md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "segments_csv": str(csv_path),
        "assets_csv": str(assets_csv_path),
        "bundle_json": str(json_path),
        "report_md": str(md_path),
        "manifest": str(manifest_path),
    }
