"""AASHTO Highway Safety Manual (HSM) Empirical Bayes network screening engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256


HSM_ENGINE_VERSION = "hsm_empirical_bayes_v1"
HSM_CONTRACT_VERSION = "hsm_network_screening_v1"


@dataclass(frozen=True, slots=True)
class SpfCoefficients:
    """Safety Performance Function (SPF) regression parameters for a road class."""

    facility_class: str
    beta_0: float  # Intercept
    beta_1: float  # ln(AADT) slope
    overdispersion_k: float  # Base overdispersion parameter k
    length_adjusted_k: bool = True  # Whether k is divided by segment length L
    description: str = ""

    def predict_annual_crashes(
        self,
        aadt: float,
        length_km: float = 1.0,
        calibration_factor_c: float = 1.0,
        cmf_product: float = 1.0,
    ) -> float:
        """Evaluate log-linear SPF: N = L * exp(beta_0 + beta_1 * ln(AADT)) * C * prod(CMF)."""
        if aadt <= 0.0 or length_km <= 0.0:
            return 0.0
        log_aadt = math.log(max(1.0, aadt))
        base_predicted = length_km * math.exp(self.beta_0 + self.beta_1 * log_aadt)
        return max(0.0, base_predicted * calibration_factor_c * cmf_product)

    def effective_overdispersion(self, length_km: float = 1.0) -> float:
        """Compute effective k, adjusted for segment length if applicable."""
        if not self.length_adjusted_k:
            return max(0.001, self.overdispersion_k)
        effective_len = max(0.05, length_km)
        return max(0.001, self.overdispersion_k / effective_len)


# Calibrated AASHTO HSM Part C base SPFs (calibrated for standard km & AADT)
# Ref: AASHTO Highway Safety Manual 1st Edition, Chapters 10 (Rural Two-Lane),
# 11 (Rural Multilane), 12 (Urban/Suburban Arterials).
CALIBRATED_HSM_SPFS: dict[str, SpfCoefficients] = {
    "rural_two_lane_two_way": SpfCoefficients(
        facility_class="rural_two_lane_two_way",
        beta_0=-7.02,
        beta_1=0.96,
        overdispersion_k=0.236,
        length_adjusted_k=True,
        description="AASHTO HSM Ch.10 Rural Two-Lane Two-Way Roadway Segments",
    ),
    "rural_multilane_undivided": SpfCoefficients(
        facility_class="rural_multilane_undivided",
        beta_0=-7.85,
        beta_1=1.04,
        overdispersion_k=0.194,
        length_adjusted_k=True,
        description="AASHTO HSM Ch.11 Rural Multilane Undivided Roadway Segments",
    ),
    "rural_multilane_divided": SpfCoefficients(
        facility_class="rural_multilane_divided",
        beta_0=-7.52,
        beta_1=0.98,
        overdispersion_k=0.178,
        length_adjusted_k=True,
        description="AASHTO HSM Ch.11 Rural Multilane Divided Roadway Segments",
    ),
    "urban_arterial_undivided": SpfCoefficients(
        facility_class="urban_arterial_undivided",
        beta_0=-6.48,
        beta_1=0.92,
        overdispersion_k=0.312,
        length_adjusted_k=True,
        description="AASHTO HSM Ch.12 Urban/Suburban Arterial Undivided Segments",
    ),
    "urban_arterial_divided": SpfCoefficients(
        facility_class="urban_arterial_divided",
        beta_0=-6.22,
        beta_1=0.89,
        overdispersion_k=0.265,
        length_adjusted_k=True,
        description="AASHTO HSM Ch.12 Urban/Suburban Arterial Divided Segments",
    ),
    "motorway_freeway": SpfCoefficients(
        facility_class="motorway_freeway",
        beta_0=-8.12,
        beta_1=1.08,
        overdispersion_k=0.142,
        length_adjusted_k=True,
        description="AASHTO HSM Freeway / Motorway Segments (Access-Controlled)",
    ),
}


@dataclass(frozen=True, slots=True)
class HsmSegmentScreeningResult:
    """Empirical Bayes network screening result for a single road segment."""

    segment_id: str
    facility_class: str
    length_km: float
    aadt: float
    analysis_years: int
    observed_crashes_total: int
    observed_crashes_annual: float
    spf_predicted_annual: float
    spf_predicted_total: float
    eb_weight_w: float
    eb_expected_annual: float
    eb_expected_total: float
    eb_expected_variance: float
    psi_excess_crashes_annual: float  # Potential for Safety Improvement (Expected - Predicted)
    excess_ratio: float  # Expected / Predicted
    priority_rank: int  # Rank by PSI descending
    screening_band: str  # priority_tier: high, medium, baseline, safe
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "facility_class": self.facility_class,
            "length_km": round(self.length_km, 3),
            "aadt": round(self.aadt, 1),
            "analysis_years": self.analysis_years,
            "observed_crashes_total": self.observed_crashes_total,
            "observed_crashes_annual": round(self.observed_crashes_annual, 3),
            "spf_predicted_annual": round(self.spf_predicted_annual, 3),
            "spf_predicted_total": round(self.spf_predicted_total, 3),
            "eb_weight_w": round(self.eb_weight_w, 4),
            "eb_expected_annual": round(self.eb_expected_annual, 3),
            "eb_expected_total": round(self.eb_expected_total, 3),
            "eb_expected_variance": round(self.eb_expected_variance, 4),
            "psi_excess_crashes_annual": round(self.psi_excess_crashes_annual, 3),
            "excess_ratio": round(self.excess_ratio, 3),
            "priority_rank": self.priority_rank,
            "screening_band": self.screening_band,
            "metadata": self.metadata,
        }


def compute_empirical_bayes_segment(
    segment_id: str,
    observed_crashes: int | Sequence[int],
    aadt: float,
    length_km: float,
    facility_class: str = "rural_two_lane_two_way",
    calibration_c: float = 1.0,
    cmf_product: float = 1.0,
    custom_spf: SpfCoefficients | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> HsmSegmentScreeningResult:
    """Compute AASHTO HSM Empirical Bayes screening on one segment across N analysis years."""
    spf = custom_spf or CALIBRATED_HSM_SPFS.get(
        facility_class, CALIBRATED_HSM_SPFS["rural_two_lane_two_way"]
    )

    # Determine observed crashes and number of analysis years
    if isinstance(observed_crashes, (list, tuple)):
        observed_total = sum(int(c) for c in observed_crashes)
        years = max(1, len(observed_crashes))
    else:
        observed_total = int(observed_crashes)
        years = 1

    observed_annual = observed_total / float(years)
    effective_length = max(0.01, float(length_km))
    safe_aadt = max(1.0, float(aadt))

    # 1. Base SPF prediction per year
    spf_annual = spf.predict_annual_crashes(
        aadt=safe_aadt,
        length_km=effective_length,
        calibration_factor_c=calibration_c,
        cmf_product=cmf_product,
    )
    spf_total = spf_annual * years

    # 2. Overdispersion k and EB Weight w
    # w = 1 / (1 + k * sum(N_predicted))
    effective_k = spf.effective_overdispersion(length_km=effective_length)
    eb_weight_w = 1.0 / (1.0 + effective_k * spf_total)
    eb_weight_w = min(1.0, max(0.0, eb_weight_w))

    # 3. EB Expected Crashes (weighted average of predicted and observed)
    # N_expected = w * N_predicted_total + (1 - w) * N_observed_total
    eb_expected_total = (eb_weight_w * spf_total) + ((1.0 - eb_weight_w) * observed_total)
    eb_expected_annual = eb_expected_total / float(years)

    # 4. Variance of EB expected: Var(N_expected) = (1 - w) * N_expected_annual
    eb_variance = (1.0 - eb_weight_w) * eb_expected_annual

    # 5. Potential for Safety Improvement (PSI): Excess Expected Crashes over SPF
    psi_excess = eb_expected_annual - spf_annual
    excess_ratio = eb_expected_annual / max(0.001, spf_annual)

    # 6. Safety screening band
    if psi_excess >= 1.0 or excess_ratio >= 2.0:
        band = "high_priority"
    elif psi_excess >= 0.25 or excess_ratio >= 1.25:
        band = "medium_priority"
    elif psi_excess >= -0.1:
        band = "nominal_baseline"
    else:
        band = "performing_better_than_norm"

    return HsmSegmentScreeningResult(
        segment_id=str(segment_id),
        facility_class=spf.facility_class,
        length_km=effective_length,
        aadt=safe_aadt,
        analysis_years=years,
        observed_crashes_total=observed_total,
        observed_crashes_annual=observed_annual,
        spf_predicted_annual=spf_annual,
        spf_predicted_total=spf_total,
        eb_weight_w=eb_weight_w,
        eb_expected_annual=eb_expected_annual,
        eb_expected_total=eb_expected_total,
        eb_expected_variance=eb_variance,
        psi_excess_crashes_annual=psi_excess,
        excess_ratio=excess_ratio,
        priority_rank=1,  # updated during batch ranking
        screening_band=band,
        metadata=dict(metadata or {}),
    )


def screen_road_network_hsm(
    segments: Sequence[Mapping[str, Any]],
    default_facility_class: str = "rural_two_lane_two_way",
    calibration_c: float = 1.0,
    custom_spfs: Mapping[str, SpfCoefficients] | None = None,
) -> list[HsmSegmentScreeningResult]:
    """Execute Highway Safety Manual Empirical Bayes network screening over road segments.

    Each segment dict expects:
      - 'segment_id' (str)
      - 'observed_crashes' (int or sequence of annual ints)
      - 'length_km' or 'length_m' (float)
      - 'aadt' (float, or derived from built_env_demand / exposure proxies)
      - optional 'facility_class' (str)
      - optional 'cmf_product' (float)
    """
    results: list[HsmSegmentScreeningResult] = []

    for item in segments:
        seg_id = str(item.get("segment_id") or item.get("id") or "unknown")

        # Length resolution
        if "length_km" in item:
            length_km = float(item["length_km"])
        elif "length_m" in item:
            length_km = float(item["length_m"]) / 1000.0
        elif "length" in item:
            val = float(item["length"])
            length_km = val / 1000.0 if val > 20.0 else val
        else:
            length_km = 0.2  # NWRSA default 200m

        # Traffic volume (AADT) resolution
        if "aadt" in item and item["aadt"] is not None:
            aadt = float(item["aadt"])
        elif "flow_daily_estimate" in item and item["flow_daily_estimate"] is not None:
            aadt = float(item["flow_daily_estimate"])
        elif "built_env_demand_proxy" in item and item["built_env_demand_proxy"] is not None:
            # Scaled proxy conversion to plausible AADT
            proxy = float(item["built_env_demand_proxy"])
            aadt = max(500.0, proxy * 12_000.0)
        else:
            aadt = 2500.0  # conservative default baseline

        # Crashes
        crashes_raw = item.get("observed_crashes")
        if crashes_raw is None:
            crashes_raw = item.get("crash_count", item.get("total_crashes", 0))

        facility = str(item.get("facility_class") or default_facility_class)
        cmf = float(item.get("cmf_product", 1.0))

        spf_override = custom_spfs.get(facility) if custom_spfs else None

        res = compute_empirical_bayes_segment(
            segment_id=seg_id,
            observed_crashes=crashes_raw,
            aadt=aadt,
            length_km=length_km,
            facility_class=facility,
            calibration_c=calibration_c,
            cmf_product=cmf,
            custom_spf=spf_override,
            metadata={k: v for k, v in item.items() if k not in {"observed_crashes", "segment_id"}},
        )
        results.append(res)

    # Rank by Potential for Safety Improvement (PSI) descending
    results.sort(key=lambda r: r.psi_excess_crashes_annual, reverse=True)

    ranked_results: list[HsmSegmentScreeningResult] = []
    for rank, item in enumerate(results, start=1):
        ranked = HsmSegmentScreeningResult(
            segment_id=item.segment_id,
            facility_class=item.facility_class,
            length_km=item.length_km,
            aadt=item.aadt,
            analysis_years=item.analysis_years,
            observed_crashes_total=item.observed_crashes_total,
            observed_crashes_annual=item.observed_crashes_annual,
            spf_predicted_annual=item.spf_predicted_annual,
            spf_predicted_total=item.spf_predicted_total,
            eb_weight_w=item.eb_weight_w,
            eb_expected_annual=item.eb_expected_annual,
            eb_expected_total=item.eb_expected_total,
            eb_expected_variance=item.eb_expected_variance,
            psi_excess_crashes_annual=item.psi_excess_crashes_annual,
            excess_ratio=item.excess_ratio,
            priority_rank=rank,
            screening_band=item.screening_band,
            metadata=item.metadata,
        )
        ranked_results.append(ranked)

    return ranked_results


def export_hsm_screening_artifacts(
    screening_results: Sequence[HsmSegmentScreeningResult],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export HSM Empirical Bayes network screening results to JSON, CSV and Markdown."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # CSV Export
    csv_path = out_dir / f"{network_label}_hsm_screening.csv"
    import csv
    fieldnames = [
        "priority_rank",
        "segment_id",
        "screening_band",
        "facility_class",
        "length_km",
        "aadt",
        "analysis_years",
        "observed_crashes_total",
        "observed_crashes_annual",
        "spf_predicted_annual",
        "eb_weight_w",
        "eb_expected_annual",
        "eb_expected_variance",
        "psi_excess_crashes_annual",
        "excess_ratio",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in screening_results:
            d = item.to_dict()
            writer.writerow({k: d.get(k) for k in fieldnames})

    # JSON Export
    json_path = out_dir / f"{network_label}_hsm_screening.json"
    high_priority_count = sum(1 for r in screening_results if r.screening_band == "high_priority")
    medium_priority_count = sum(1 for r in screening_results if r.screening_band == "medium_priority")

    payload = {
        "hsm_engine_version": HSM_ENGINE_VERSION,
        "contract_version": HSM_CONTRACT_VERSION,
        "generated_at_utc": timestamp,
        "network_label": network_label,
        "summary": {
            "total_segments_screened": len(screening_results),
            "high_priority_count": high_priority_count,
            "medium_priority_count": medium_priority_count,
            "total_observed_crashes": sum(r.observed_crashes_total for r in screening_results),
            "total_expected_crashes_annual": round(sum(r.eb_expected_annual for r in screening_results), 2),
            "total_psi_excess_annual": round(sum(max(0.0, r.psi_excess_crashes_annual) for r in screening_results), 2),
        },
        "results": [r.to_dict() for r in screening_results],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Markdown Executive Report
    md_path = out_dir / f"{network_label}_hsm_screening.md"
    lines = [
        f"# Highway Safety Manual (HSM) Network Screening: {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        "- **Methodology:** AASHTO Highway Safety Manual Part C (Safety Performance Functions + Empirical Bayes Adjustments)",
        f"- **Total Segments Screened:** {len(screening_results):,}",
        f"- **High-Priority Remediation Targets (PSI > 1.0 or Excess Ratio > 2.0):** {high_priority_count}",
        f"- **Total Preventable Excess Crashes (PSI > 0):** {payload['summary']['total_psi_excess_annual']} crashes/year",
        "",
        "## Top Priority Remediation Candidates (Ranked by Potential for Safety Improvement - PSI)",
        "",
        "| Rank | Segment ID | Facility Class | Observed/Yr | SPF Pred/Yr | EB Expected/Yr | Weight $w$ | PSI (Excess/Yr) | Band |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in screening_results[:25]:
        lines.append(
            f"| #{row.priority_rank} | `{row.segment_id}` | {row.facility_class} | {row.observed_crashes_annual:.2f} | {row.spf_predicted_annual:.2f} | {row.eb_expected_annual:.2f} | {row.eb_weight_w:.3f} | **{row.psi_excess_crashes_annual:+.2f}** | `{row.screening_band}` |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Manifest
    manifest_path = out_dir / f"{network_label}_hsm_screening.manifest.json"
    manifest = {
        "artifact_family": "hsm_screening",
        "network_label": network_label,
        "hsm_engine_version": HSM_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "csv": {"path": str(csv_path.name), "sha256": _sha256(csv_path)},
            "md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "md": str(md_path),
        "manifest": str(manifest_path),
    }
