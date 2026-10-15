"""International Road Assessment Programme (iRAP) Star Rating & SRIP engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256


IRAP_ENGINE_VERSION = "irap_star_rating_v1"
IRAP_CONTRACT_VERSION = "irap_star_rating_public_v1"
SRIP_VERSION = "srip_economic_investment_v1"


# Standard iRAP Star Rating Score (SRS) cutoffs for 100m/200m roadway segments
# Stars 1 to 5: 5 is safest, 1 is highest risk.
# Ref: iRAP Star Rating Methodology and Technical Specifications (UN Target 4).
STAR_RATING_CUTOFFS = {
    5: 5.0,     # SRS < 5.0  -> 5 Stars
    4: 12.5,    # SRS < 12.5 -> 4 Stars
    3: 25.0,    # SRS < 25.0 -> 3 Stars (UN Minimum Standard)
    2: 50.0,    # SRS < 50.0 -> 2 Stars
    1: 9999.0,  # SRS >= 50.0 -> 1 Star
}


def srs_to_star_rating(srs: float) -> int:
    """Convert continuous Star Rating Score (SRS) to discrete 1-to-5 Star rating."""
    if srs < 0.0:
        return 5
    if srs < STAR_RATING_CUTOFFS[5]:
        return 5
    if srs < STAR_RATING_CUTOFFS[4]:
        return 4
    if srs < STAR_RATING_CUTOFFS[3]:
        return 3
    if srs < STAR_RATING_CUTOFFS[2]:
        return 2
    return 1


@dataclass(frozen=True, slots=True)
class IrapUserScores:
    """Star Rating Score and discrete 1-5 Star Rating for each of the 4 road user groups."""

    vehicle_srs: float
    vehicle_stars: int
    motorcycle_srs: float
    motorcycle_stars: int
    bicycle_srs: float
    bicycle_stars: int
    pedestrian_srs: float
    pedestrian_stars: int

    @property
    def minimum_stars(self) -> int:
        return min(
            self.vehicle_stars,
            self.motorcycle_stars,
            self.bicycle_stars,
            self.pedestrian_stars,
        )

    @property
    def meets_un_target_4(self) -> bool:
        """UN Target 4 requires 3-star or better standards for all road users."""
        return self.minimum_stars >= 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_occupant": {
                "srs": round(self.vehicle_srs, 2),
                "star_rating": self.vehicle_stars,
            },
            "motorcyclist": {
                "srs": round(self.motorcycle_srs, 2),
                "star_rating": self.motorcycle_stars,
            },
            "bicyclist": {
                "srs": round(self.bicycle_srs, 2),
                "star_rating": self.bicycle_stars,
            },
            "pedestrian": {
                "srs": round(self.pedestrian_srs, 2),
                "star_rating": self.pedestrian_stars,
            },
            "minimum_stars_overall": self.minimum_stars,
            "meets_un_target_4": self.meets_un_target_4,
        }


@dataclass(frozen=True, slots=True)
class IrapSegmentRating:
    """Full iRAP Star Rating assessment for a roadway segment."""

    segment_id: str
    length_km: float
    aadt: float
    operating_speed_kmh: float
    scores: IrapUserScores
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "length_km": round(self.length_km, 3),
            "aadt": round(self.aadt, 1),
            "operating_speed_kmh": round(self.operating_speed_kmh, 1),
            "user_ratings": self.scores.to_dict(),
            "attributes": self.attributes,
        }


def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, val))


def calculate_irap_user_scores(
    operating_speed_kmh: float,
    lanes: int = 2,
    is_divided: bool = False,
    has_median_barrier: bool = False,
    carriageway_width_m: float = 7.0,
    sinuosity: float = 1.0,
    has_roadside_barrier: bool = False,
    roadside_hazard_severity: float = 0.5,  # 0.0 (clear zone) to 1.0 (steep drop/trees)
    intersection_density_per_km: float = 1.0,
    has_sidewalk: bool = False,
    has_pedestrian_crossing: bool = False,
    has_segregated_cycle_facility: bool = False,
) -> IrapUserScores:
    """Compute iRAP Star Rating Scores (SRS) and Stars for 4 road user groups.

    Follows iRAP risk equation: SRS = Likelihood x Severity x Flow / Calibration.
    """
    speed = max(20.0, float(operating_speed_kmh))
    speed_factor = (speed / 100.0) ** 2.0  # Kinetic energy scaling

    # --- 1. Vehicle Occupant SRS ---
    # Head-on risk: high on undivided roads at speed
    if is_divided or has_median_barrier:
        head_on_risk = 0.5
    else:
        head_on_risk = 10.0 if lanes <= 2 else 14.0

    # Run-off-road risk: driven by curvature, narrow width, roadside hazards
    width_penalty = max(0.5, (8.0 - carriageway_width_m) * 1.5)
    curve_penalty = max(1.0, (sinuosity - 1.0) * 12.0 + 1.0)
    roadside_risk = (1.0 if has_roadside_barrier else 3.5) * (roadside_hazard_severity + 0.5)
    run_off_risk = width_penalty * curve_penalty * roadside_risk

    # Intersection risk
    intersection_risk = intersection_density_per_km * 2.5

    vehicle_srs = (head_on_risk + run_off_risk + intersection_risk) * speed_factor
    vehicle_stars = srs_to_star_rating(vehicle_srs)

    # --- 2. Motorcyclist SRS ---
    # Extreme sensitivity to roadside hazards, unprotected barriers, and curve radius
    moto_roadside = 2.0 if has_roadside_barrier else (5.0 * (roadside_hazard_severity + 0.5))
    moto_head_on = head_on_risk * 1.2
    moto_srs = (moto_head_on + (run_off_risk * 1.3) + moto_roadside + intersection_risk) * speed_factor
    moto_stars = srs_to_star_rating(moto_srs)

    # --- 3. Bicyclist SRS ---
    # Depends heavily on speed difference and whether segregation exists
    if has_segregated_cycle_facility:
        bicycle_srs = 3.0  # Protected, 5-star baseline
    else:
        # Mixed traffic risk scales drastically with vehicle operating speed
        mix_risk = 3.0 * ((speed / 30.0) ** 2.5)
        bike_intersection = intersection_density_per_km * 4.0
        bicycle_srs = (mix_risk + bike_intersection) * (1.2 if lanes > 2 else 1.0)
    bicycle_stars = srs_to_star_rating(bicycle_srs)

    # --- 4. Pedestrian SRS ---
    # Along-road risk (sidewalk presence) + Crossing risk (crossing facility + lane width)
    if has_sidewalk:
        along_road_ped_risk = 2.0
    else:
        # Walking along carriageway without sidewalk
        along_road_ped_risk = (speed / 25.0) ** 2.2 * 3.5

    # Crossing conflict
    if has_pedestrian_crossing:
        crossing_risk = 3.0 * (1.5 if speed > 50.0 else 0.8)
    else:
        crossing_risk = lanes * 4.0 * (speed / 40.0) ** 1.8

    pedestrian_srs = along_road_ped_risk + crossing_risk
    pedestrian_stars = srs_to_star_rating(pedestrian_srs)

    return IrapUserScores(
        vehicle_srs=max(1.0, vehicle_srs),
        vehicle_stars=vehicle_stars,
        motorcycle_srs=max(1.0, moto_srs),
        motorcycle_stars=moto_stars,
        bicycle_srs=max(1.0, bicycle_srs),
        bicycle_stars=bicycle_stars,
        pedestrian_srs=max(1.0, pedestrian_srs),
        pedestrian_stars=pedestrian_stars,
    )


def _safe_float(val: Any, default: float) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return default
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "null", ""}:
        return default
    try:
        f = float(s)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int) -> int:
    f = _safe_float(val, float(default))
    return int(round(f))


def _safe_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"true", "1", "yes", "t", "y"}


def assess_segment_irap(
    segment_data: Mapping[str, Any],
) -> IrapSegmentRating:
    """Assess a single segment's iRAP Star Ratings from road network attributes."""
    seg_id = str(segment_data.get("segment_id") or segment_data.get("id") or "seg-unknown")

    # Length
    if "length_km" in segment_data:
        length_km = _safe_float(segment_data.get("length_km"), 0.2)
    elif "segment_length_m" in segment_data:
        length_km = _safe_float(segment_data.get("segment_length_m"), 200.0) / 1000.0
    elif "length_m" in segment_data:
        length_km = _safe_float(segment_data.get("length_m"), 200.0) / 1000.0
    else:
        length_km = 0.2

    # AADT
    aadt = _safe_float(
        segment_data.get("aadt") or segment_data.get("flow_daily_estimate"),
        2500.0,
    )

    # Speed
    speed = _safe_float(
        segment_data.get("operating_speed_kmh")
        or segment_data.get("maxspeed_numeric")
        or segment_data.get("maxspeed"),
        50.0,
    )

    # Cross-section & separation
    lanes = _safe_int(segment_data.get("lanes_numeric") or segment_data.get("lanes"), 2)
    width = _safe_float(segment_data.get("width_numeric") or segment_data.get("width"), 7.0)
    is_divided = _safe_bool(segment_data.get("is_divided") or segment_data.get("divided"))
    median_barrier = _safe_bool(segment_data.get("has_median_barrier"))

    # Roadside & geometry
    sinuosity = _safe_float(segment_data.get("sinuosity"), 1.0)
    has_roadside_barrier = _safe_bool(segment_data.get("has_roadside_barrier") or segment_data.get("guardrail"))
    hazard_severity = _safe_float(segment_data.get("roadside_hazard_severity"), 0.7 if segment_data.get("bridge") else 0.4)

    # Intersections
    junction_density = _safe_float(segment_data.get("junction_density") or segment_data.get("intersection_density_per_km"), 1.0)

    # VRU facilities
    has_sidewalk = _safe_bool(segment_data.get("has_sidewalk") or segment_data.get("sidewalk"))
    has_ped_crossing = _safe_bool(segment_data.get("has_pedestrian_crossing") or segment_data.get("crossing"))
    has_cycle_facility = _safe_bool(segment_data.get("has_segregated_cycle_facility") or segment_data.get("cycleway"))

    scores = calculate_irap_user_scores(
        operating_speed_kmh=speed,
        lanes=lanes,
        is_divided=is_divided,
        has_median_barrier=median_barrier,
        carriageway_width_m=width,
        sinuosity=sinuosity,
        has_roadside_barrier=has_roadside_barrier,
        roadside_hazard_severity=hazard_severity,
        intersection_density_per_km=junction_density,
        has_sidewalk=has_sidewalk,
        has_pedestrian_crossing=has_ped_crossing,
        has_segregated_cycle_facility=has_cycle_facility,
    )

    return IrapSegmentRating(
        segment_id=seg_id,
        length_km=length_km,
        aadt=aadt,
        operating_speed_kmh=speed,
        scores=scores,
        attributes={
            "lanes": lanes,
            "width_m": width,
            "is_divided": is_divided,
            "sinuosity": sinuosity,
            "has_sidewalk": has_sidewalk,
            "has_segregated_cycle_facility": has_cycle_facility,
        },
    )


# --- Safer Roads Investment Plan (SRIP) Engine ---

@dataclass(frozen=True, slots=True)
class SripCountermeasureOption:
    """An engineering countermeasure tested in the Safer Roads Investment Plan."""

    code: str
    name: str
    target_user: str
    target_deficiency: str
    cost_per_km_eur: float
    fsi_reduction_fraction: float  # Fatal and Serious Injury reduction rate
    service_life_years: int = 20


# Standard proven iRAP countermeasures catalog
SRIP_COUNTERMEASURES: tuple[SripCountermeasureOption, ...] = (
    SripCountermeasureOption(
        code="MEDIAN_SAFETY_BARRIER",
        name="Install Central Median Safety Barrier",
        target_user="vehicle_occupant",
        target_deficiency="head_on_undivided",
        cost_per_km_eur=75_000.0,
        fsi_reduction_fraction=0.70,
    ),
    SripCountermeasureOption(
        code="ROADSIDE_SAFETY_BARRIER",
        name="Install Roadside Barrier & Clear Hazard Zone",
        target_user="vehicle_occupant",
        target_deficiency="unprotected_roadside",
        cost_per_km_eur=45_000.0,
        fsi_reduction_fraction=0.45,
    ),
    SripCountermeasureOption(
        code="CONTINUOUS_SIDEWALK",
        name="Construct Continuous Paved Sidewalk / Footpath",
        target_user="pedestrian",
        target_deficiency="pedestrian_along_road",
        cost_per_km_eur=60_000.0,
        fsi_reduction_fraction=0.75,
    ),
    SripCountermeasureOption(
        code="SEGREGATED_CYCLE_TRACK",
        name="Construct Physically Segregated Cycle Track",
        target_user="bicyclist",
        target_deficiency="mixed_traffic_cyclist",
        cost_per_km_eur=80_000.0,
        fsi_reduction_fraction=0.80,
    ),
    SripCountermeasureOption(
        code="PEDESTRIAN_REFUGE_ISLAND",
        name="Install Pedestrian Refuge Island & Signal Crossing",
        target_user="pedestrian",
        target_deficiency="unprotected_crossing",
        cost_per_km_eur=25_000.0,
        fsi_reduction_fraction=0.60,
    ),
    SripCountermeasureOption(
        code="ROUNDABOUT_CONVERSION",
        name="Convert High-Conflict Junction to Roundabout",
        target_user="all_users",
        target_deficiency="junction_collision",
        cost_per_km_eur=180_000.0,
        fsi_reduction_fraction=0.65,
    ),
    SripCountermeasureOption(
        code="STREET_LIGHTING",
        name="Install Energy-Efficient LED Street Lighting",
        target_user="all_users",
        target_deficiency="nighttime_risk",
        cost_per_km_eur=30_000.0,
        fsi_reduction_fraction=0.35,
    ),
)


@dataclass(frozen=True, slots=True)
class SripInvestmentItem:
    """A prioritized countermeasure recommendation for one roadway segment."""

    segment_id: str
    countermeasure_code: str
    countermeasure_name: str
    target_user_group: str
    estimated_cost_eur: float
    expected_fsi_prevented_20yr: float
    present_value_benefits_eur: float
    present_value_costs_eur: float
    benefit_cost_ratio: float
    pre_star_rating: int
    post_star_rating: int
    priority_rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "countermeasure_code": self.countermeasure_code,
            "countermeasure_name": self.countermeasure_name,
            "target_user_group": self.target_user_group,
            "estimated_cost_eur": round(self.estimated_cost_eur, 2),
            "expected_fsi_prevented_20yr": round(self.expected_fsi_prevented_20yr, 2),
            "present_value_benefits_eur": round(self.present_value_benefits_eur, 2),
            "present_value_costs_eur": round(self.present_value_costs_eur, 2),
            "benefit_cost_ratio": round(self.benefit_cost_ratio, 2),
            "pre_star_rating": self.pre_star_rating,
            "post_star_rating": self.post_star_rating,
            "priority_rank": self.priority_rank,
        }


def generate_safer_roads_investment_plan(
    assessed_segments: Sequence[IrapSegmentRating],
    value_of_statistical_life_eur: float = 1_500_000.0,
    value_of_serious_injury_eur: float = 250_000.0,
    discount_rate: float = 0.04,
    min_bcr_threshold: float = 1.0,
) -> list[SripInvestmentItem]:
    """Generate a 20-year Safer Roads Investment Plan (SRIP) for segments rated < 3 Stars."""
    # Present Value Factor for a 20-year annual benefit stream at discount rate r
    # PV_factor = (1 - (1+r)^(-20)) / r
    r = max(0.01, discount_rate)
    pv_factor = (1.0 - (1.0 + r) ** (-20)) / r

    raw_items: list[SripInvestmentItem] = []

    for seg in assessed_segments:
        # Only evaluate countermeasures if segment fails UN Target 4 (< 3 stars for any user)
        if seg.scores.meets_un_target_4:
            continue

        length = max(0.05, seg.length_km)

        # Baseline estimated annual severe casualties (FSI) per km based on AADT and stars
        # Higher star deficit produces higher preventable baseline
        star_deficit = max(1, 3 - seg.scores.minimum_stars)
        base_fsi_annual_per_km = (seg.aadt / 10_000.0) * 0.4 * star_deficit
        base_fsi_segment_annual = max(0.05, base_fsi_annual_per_km * length)

        # Test relevant countermeasures based on user deficiencies
        candidate_options: list[SripCountermeasureOption] = []

        if seg.scores.pedestrian_stars < 3:
            if not seg.attributes.get("has_sidewalk"):
                candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "CONTINUOUS_SIDEWALK"))
            else:
                candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "PEDESTRIAN_REFUGE_ISLAND"))

        if seg.scores.bicycle_stars < 3:
            if not seg.attributes.get("has_segregated_cycle_facility"):
                candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "SEGREGATED_CYCLE_TRACK"))

        if seg.scores.vehicle_stars < 3:
            if not seg.attributes.get("is_divided"):
                candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "MEDIAN_SAFETY_BARRIER"))
            else:
                candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "ROADSIDE_SAFETY_BARRIER"))

        # If no specific matched, supply roadside safety barrier as general remedy
        if not candidate_options:
            candidate_options.append(next(c for c in SRIP_COUNTERMEASURES if c.code == "ROADSIDE_SAFETY_BARRIER"))

        # Evaluate each candidate and pick the highest BCR option
        for cm in candidate_options:
            cost = cm.cost_per_km_eur * length
            fsi_saved_annual = base_fsi_segment_annual * cm.fsi_reduction_fraction
            fsi_saved_20yr = fsi_saved_annual * 20.0

            # Economic value: weighted mix (typically 1 fatality per 8 serious injuries)
            benefit_annual = (fsi_saved_annual * 0.12 * value_of_statistical_life_eur) + (
                fsi_saved_annual * 0.88 * value_of_serious_injury_eur
            )
            pvb = benefit_annual * pv_factor
            pvc = cost
            bcr = pvb / max(1.0, pvc)

            if bcr >= min_bcr_threshold:
                # Post-intervention star rating typically reaches 3 or 4 stars
                post_stars = min(5, seg.scores.minimum_stars + 2)

                raw_items.append(
                    SripInvestmentItem(
                        segment_id=seg.segment_id,
                        countermeasure_code=cm.code,
                        countermeasure_name=cm.name,
                        target_user_group=cm.target_user,
                        estimated_cost_eur=cost,
                        expected_fsi_prevented_20yr=fsi_saved_20yr,
                        present_value_benefits_eur=pvb,
                        present_value_costs_eur=pvc,
                        benefit_cost_ratio=bcr,
                        pre_star_rating=seg.scores.minimum_stars,
                        post_star_rating=post_stars,
                        priority_rank=1,
                    )
                )

    # Sort by BCR descending
    raw_items.sort(key=lambda item: item.benefit_cost_ratio, reverse=True)

    # Assign priority ranks
    ranked_plan: list[SripInvestmentItem] = []
    for rank, item in enumerate(raw_items, start=1):
        ranked_plan.append(
            SripInvestmentItem(
                segment_id=item.segment_id,
                countermeasure_code=item.countermeasure_code,
                countermeasure_name=item.countermeasure_name,
                target_user_group=item.target_user_group,
                estimated_cost_eur=item.estimated_cost_eur,
                expected_fsi_prevented_20yr=item.expected_fsi_prevented_20yr,
                present_value_benefits_eur=item.present_value_benefits_eur,
                present_value_costs_eur=item.present_value_costs_eur,
                benefit_cost_ratio=item.benefit_cost_ratio,
                pre_star_rating=item.pre_star_rating,
                post_star_rating=item.post_star_rating,
                priority_rank=rank,
            )
        )

    return ranked_plan


def export_irap_and_srip_artifacts(
    assessed_segments: Sequence[IrapSegmentRating],
    investment_plan: Sequence[SripInvestmentItem],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export iRAP Star Rating and SRIP investment plan artifacts (JSON, CSV, MD, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export iRAP Ratings CSV
    ratings_csv_path = out_dir / f"{network_label}_irap_ratings.csv"
    import csv

    rating_fieldnames = [
        "segment_id", "length_km", "aadt", "operating_speed_kmh",
        "vehicle_stars", "vehicle_srs", "motorcycle_stars", "motorcycle_srs",
        "bicycle_stars", "bicycle_srs", "pedestrian_stars", "pedestrian_srs",
        "minimum_stars_overall", "meets_un_target_4"
    ]
    with ratings_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rating_fieldnames)
        writer.writeheader()
        for seg in assessed_segments:
            writer.writerow({
                "segment_id": seg.segment_id,
                "length_km": round(seg.length_km, 3),
                "aadt": round(seg.aadt, 1),
                "operating_speed_kmh": round(seg.operating_speed_kmh, 1),
                "vehicle_stars": seg.scores.vehicle_stars,
                "vehicle_srs": round(seg.scores.vehicle_srs, 2),
                "motorcycle_stars": seg.scores.motorcycle_stars,
                "motorcycle_srs": round(seg.scores.motorcycle_srs, 2),
                "bicycle_stars": seg.scores.bicycle_stars,
                "bicycle_srs": round(seg.scores.bicycle_srs, 2),
                "pedestrian_stars": seg.scores.pedestrian_stars,
                "pedestrian_srs": round(seg.scores.pedestrian_srs, 2),
                "minimum_stars_overall": seg.scores.minimum_stars,
                "meets_un_target_4": seg.scores.meets_un_target_4,
            })

    # 2. Export SRIP Plan CSV
    srip_csv_path = out_dir / f"{network_label}_srip_investment_plan.csv"
    srip_fieldnames = [
        "priority_rank", "segment_id", "countermeasure_code", "countermeasure_name",
        "target_user_group", "estimated_cost_eur", "expected_fsi_prevented_20yr",
        "present_value_benefits_eur", "present_value_costs_eur", "benefit_cost_ratio",
        "pre_star_rating", "post_star_rating"
    ]
    with srip_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=srip_fieldnames)
        writer.writeheader()
        for item in investment_plan:
            d = item.to_dict()
            writer.writerow({k: d.get(k) for k in srip_fieldnames})

    # 3. Export Comprehensive JSON Bundle
    json_path = out_dir / f"{network_label}_irap_and_srip_bundle.json"
    total_segments = len(assessed_segments)
    un_target_compliant_count = sum(1 for seg in assessed_segments if seg.scores.meets_un_target_4)
    compliance_percentage = (un_target_compliant_count / max(1, total_segments)) * 100.0

    star_distribution = {
        "vehicle": {star: sum(1 for s in assessed_segments if s.scores.vehicle_stars == star) for star in range(1, 6)},
        "motorcycle": {star: sum(1 for s in assessed_segments if s.scores.motorcycle_stars == star) for star in range(1, 6)},
        "bicycle": {star: sum(1 for s in assessed_segments if s.scores.bicycle_stars == star) for star in range(1, 6)},
        "pedestrian": {star: sum(1 for s in assessed_segments if s.scores.pedestrian_stars == star) for star in range(1, 6)},
    }

    payload = {
        "irap_engine_version": IRAP_ENGINE_VERSION,
        "contract_version": IRAP_CONTRACT_VERSION,
        "srip_version": SRIP_VERSION,
        "generated_at_utc": timestamp,
        "network_label": network_label,
        "un_global_target_4_summary": {
            "total_segments_assessed": total_segments,
            "compliant_3star_or_better_segments": un_target_compliant_count,
            "compliance_percentage": round(compliance_percentage, 2),
            "target_threshold_percentage": 75.0,
            "target_achieved": compliance_percentage >= 75.0,
            "star_distribution": star_distribution,
        },
        "srip_investment_summary": {
            "total_recommended_countermeasures": len(investment_plan),
            "total_investment_budget_eur": round(sum(i.estimated_cost_eur for i in investment_plan), 2),
            "total_fsi_prevented_20yr": round(sum(i.expected_fsi_prevented_20yr for i in investment_plan), 2),
            "total_present_value_benefits_eur": round(sum(i.present_value_benefits_eur for i in investment_plan), 2),
            "program_average_bcr": round(
                sum(i.present_value_benefits_eur for i in investment_plan) / max(1.0, sum(i.present_value_costs_eur for i in investment_plan)),
                2,
            ) if investment_plan else 0.0,
        },
        "ratings_sample": [s.to_dict() for s in assessed_segments[:50]],
        "investment_plan": [i.to_dict() for i in investment_plan],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 4. Export Markdown Executive Report
    md_path = out_dir / f"{network_label}_irap_and_srip_report.md"
    lines = [
        f"# iRAP Star Rating & Safer Roads Investment Plan (SRIP): {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        "- **Standard Alignment:** International Road Assessment Programme (iRAP) & UN Global Target 4 (SDG 3.6)",
        f"- **Total Network Segments Assessed:** {total_segments:,}",
        f"- **UN Target 4 Compliance (≥ 3 Stars for All Users):** **{compliance_percentage:.1f}%** (Target: ≥ 75%)",
        f"- **Total Recommended Countermeasures:** {len(investment_plan):,}",
        f"- **Total Investment Budget Required:** €{payload['srip_investment_summary']['total_investment_budget_eur']:,}",
        f"- **Estimated Fatalities & Serious Injuries (FSI) Prevented (20yr):** **{payload['srip_investment_summary']['total_fsi_prevented_20yr']:,}** casualties",
        f"- **Program Benefit-Cost Ratio (BCR):** **{payload['srip_investment_summary']['program_average_bcr']:.2f}x** return",
        "",
        "## Star Rating Distribution by Road User Group",
        "",
        "| Road User Group | 5 Stars ⭐⭐⭐⭐⭐ | 4 Stars ⭐⭐⭐⭐ | 3 Stars ⭐⭐⭐ | 2 Stars ⭐⭐ | 1 Star ⭐ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    user_labels = {
        "vehicle": "🚗 Vehicle Occupants",
        "motorcycle": "🏍️ Motorcyclists",
        "bicycle": "🚲 Bicyclists",
        "pedestrian": "🚶 Pedestrians",
    }
    for user_key, label in user_labels.items():
        dist = star_distribution[user_key]
        lines.append(
            f"| {label} | {dist.get(5, 0):,} | {dist.get(4, 0):,} | {dist.get(3, 0):,} | {dist.get(2, 0):,} | {dist.get(1, 0):,} |"
        )
    lines.extend([
        "",
        "## Top Safer Roads Investment Plan (SRIP) Priorities",
        "",
        "| Rank | Segment ID | Countermeasure | Target User | Est. Cost (€) | 20yr FSI Saved | BCR | Stars (Pre → Post) |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for item in investment_plan[:25]:
        lines.append(
            f"| #{item.priority_rank} | `{item.segment_id}` | {item.countermeasure_name} | {item.target_user_group.title()} | €{item.estimated_cost_eur:,.0f} | {item.expected_fsi_prevented_20yr:.1f} | **{item.benefit_cost_ratio:.1f}x** | {item.pre_star_rating}★ → {item.post_star_rating}★ |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 5. Manifest
    manifest_path = out_dir / f"{network_label}_irap_srip.manifest.json"
    manifest = {
        "artifact_family": "irap_and_srip",
        "network_label": network_label,
        "irap_engine_version": IRAP_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "ratings_csv": {"path": str(ratings_csv_path.name), "sha256": _sha256(ratings_csv_path)},
            "srip_csv": {"path": str(srip_csv_path.name), "sha256": _sha256(srip_csv_path)},
            "json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "ratings_csv": str(ratings_csv_path),
        "srip_csv": str(srip_csv_path),
        "json": str(json_path),
        "md": str(md_path),
        "manifest": str(manifest_path),
    }
