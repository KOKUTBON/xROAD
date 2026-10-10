"""Multi-Year Capital Improvement Planning (CIP) & Sovereign Portfolio Optimization Engine.

Implements multi-period budget-constrained knapsack optimization, inflation cost
escalation, social benefit discounting, regional equity quotas, and sovereign
audit log generation for national transport authorities.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256


CIP_ENGINE_VERSION = "cip_optimization_v1"
CIP_CONTRACT_VERSION = "cip_optimization_public_v1"


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
class CipCandidateProject:
    """An infrastructure countermeasure project eligible for multi-year CIP scheduling."""

    project_id: str
    segment_id: str
    countermeasure_code: str
    countermeasure_name: str
    target_user_group: str
    base_cost_eur: float
    expected_fsi_prevented_20yr: float
    present_value_benefits_eur: float
    benefit_cost_ratio: float
    region_id: str = "national_network"
    pre_star_rating: int = 2
    post_star_rating: int = 4
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "segment_id": self.segment_id,
            "countermeasure_code": self.countermeasure_code,
            "countermeasure_name": self.countermeasure_name,
            "target_user_group": self.target_user_group,
            "base_cost_eur": round(self.base_cost_eur, 2),
            "expected_fsi_prevented_20yr": round(self.expected_fsi_prevented_20yr, 2),
            "present_value_benefits_eur": round(self.present_value_benefits_eur, 2),
            "benefit_cost_ratio": round(self.benefit_cost_ratio, 2),
            "region_id": self.region_id,
            "pre_star_rating": self.pre_star_rating,
            "post_star_rating": self.post_star_rating,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class CipScheduledProject:
    """An approved project scheduled for execution in a specific fiscal year."""

    project_id: str
    segment_id: str
    countermeasure_code: str
    countermeasure_name: str
    target_user_group: str
    scheduled_year_index: int  # 1 to H (e.g. Year 1, Year 2...)
    calendar_year: int         # e.g. 2027, 2028...
    base_cost_eur: float
    escalated_cost_eur: float  # Base cost inflated to scheduled year
    present_value_benefits_eur: float
    discounted_benefits_eur: float  # Discounted to base year
    effective_bcr: float
    expected_fsi_prevented_20yr: float
    region_id: str
    priority_rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "segment_id": self.segment_id,
            "countermeasure_code": self.countermeasure_code,
            "countermeasure_name": self.countermeasure_name,
            "target_user_group": self.target_user_group,
            "scheduled_year_index": self.scheduled_year_index,
            "calendar_year": self.calendar_year,
            "base_cost_eur": round(self.base_cost_eur, 2),
            "escalated_cost_eur": round(self.escalated_cost_eur, 2),
            "present_value_benefits_eur": round(self.present_value_benefits_eur, 2),
            "discounted_benefits_eur": round(self.discounted_benefits_eur, 2),
            "effective_bcr": round(self.effective_bcr, 2),
            "expected_fsi_prevented_20yr": round(self.expected_fsi_prevented_20yr, 2),
            "region_id": self.region_id,
            "priority_rank": self.priority_rank,
        }


@dataclass(frozen=True, slots=True)
class CipYearlySummary:
    """Fiscal capital flow and safety deliverables for one planning year."""

    fiscal_year_index: int
    calendar_year: int
    budget_ceiling_eur: float
    allocated_cost_eur: float
    remaining_budget_eur: float
    budget_utilization_pct: float
    projects_count: int
    expected_fsi_prevented_20yr: float
    present_value_benefits_eur: float
    average_bcr: float
    regional_spend_eur: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fiscal_year_index": self.fiscal_year_index,
            "calendar_year": self.calendar_year,
            "budget_ceiling_eur": round(self.budget_ceiling_eur, 2),
            "allocated_cost_eur": round(self.allocated_cost_eur, 2),
            "remaining_budget_eur": round(self.remaining_budget_eur, 2),
            "budget_utilization_pct": round(self.budget_utilization_pct, 2),
            "projects_count": self.projects_count,
            "expected_fsi_prevented_20yr": round(self.expected_fsi_prevented_20yr, 2),
            "present_value_benefits_eur": round(self.present_value_benefits_eur, 2),
            "average_bcr": round(self.average_bcr, 2),
            "regional_spend_eur": {k: round(v, 2) for k, v in self.regional_spend_eur.items()},
        }


@dataclass(frozen=True, slots=True)
class CipPortfolioPlan:
    """Complete multi-year capital improvement program across the full planning horizon."""

    horizon_years: int
    start_calendar_year: int
    inflation_rate: float
    discount_rate: float
    total_budget_eur: float
    total_invested_eur: float
    total_budget_utilization_pct: float
    total_projects_scheduled: int
    total_unscheduled_candidates: int
    total_fsi_prevented_20yr: float
    total_present_value_benefits_eur: float
    portfolio_net_present_value_eur: float
    portfolio_average_bcr: float
    yearly_summaries: list[CipYearlySummary]
    scheduled_projects: list[CipScheduledProject]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cip_engine_version": CIP_ENGINE_VERSION,
            "contract_version": CIP_CONTRACT_VERSION,
            "horizon_years": self.horizon_years,
            "start_calendar_year": self.start_calendar_year,
            "inflation_rate": self.inflation_rate,
            "discount_rate": self.discount_rate,
            "financial_summary": {
                "total_budget_eur": round(self.total_budget_eur, 2),
                "total_invested_eur": round(self.total_invested_eur, 2),
                "total_budget_utilization_pct": round(self.total_budget_utilization_pct, 2),
                "total_projects_scheduled": self.total_projects_scheduled,
                "total_unscheduled_candidates": self.total_unscheduled_candidates,
                "total_fsi_prevented_20yr": round(self.total_fsi_prevented_20yr, 2),
                "total_present_value_benefits_eur": round(self.total_present_value_benefits_eur, 2),
                "portfolio_net_present_value_eur": round(self.portfolio_net_present_value_eur, 2),
                "portfolio_average_bcr": round(self.portfolio_average_bcr, 2),
            },
            "yearly_summaries": [y.to_dict() for y in self.yearly_summaries],
            "scheduled_projects": [p.to_dict() for p in self.scheduled_projects],
        }


def parse_cip_candidates(raw_items: Sequence[Mapping[str, Any]]) -> list[CipCandidateProject]:
    """Normalize project candidates from SRIP investment items or custom capital project lists."""
    candidates: list[CipCandidateProject] = []
    for idx, item in enumerate(raw_items, start=1):
        pid = str(item.get("project_id") or f"proj-{idx:04d}")
        seg_id = str(item.get("segment_id") or item.get("id") or f"seg-{idx}")
        code = str(item.get("countermeasure_code") or item.get("code") or "SAFETY_INTERVENTION")
        name = str(item.get("countermeasure_name") or item.get("name") or "Standard Safety Upgrade")
        user = str(item.get("target_user_group") or item.get("target_user") or "all_users")
        cost = _safe_float(item.get("estimated_cost_eur") or item.get("base_cost_eur") or item.get("cost") or 50_000.0)
        fsi = _safe_float(item.get("expected_fsi_prevented_20yr") or item.get("fsi_prevented") or 1.0)
        pvb = _safe_float(item.get("present_value_benefits_eur") or item.get("pvb") or (cost * 2.5))
        bcr = _safe_float(item.get("benefit_cost_ratio") or item.get("bcr") or (pvb / max(1.0, cost)))
        region = str(item.get("region_id") or item.get("province_code") or item.get("region") or "national_network")
        pre_s = _safe_int(item.get("pre_star_rating"), 2)
        post_s = _safe_int(item.get("post_star_rating"), 4)

        candidates.append(
            CipCandidateProject(
                project_id=pid,
                segment_id=seg_id,
                countermeasure_code=code,
                countermeasure_name=name,
                target_user_group=user,
                base_cost_eur=max(100.0, cost),
                expected_fsi_prevented_20yr=max(0.01, fsi),
                present_value_benefits_eur=max(0.0, pvb),
                benefit_cost_ratio=max(0.0, bcr),
                region_id=region,
                pre_star_rating=pre_s,
                post_star_rating=post_s,
            )
        )
    return candidates


def optimize_capital_improvement_plan(
    candidates: Sequence[CipCandidateProject | Mapping[str, Any]],
    annual_budgets: Sequence[float],
    start_calendar_year: int = 2027,
    inflation_rate: float = 0.025,
    discount_rate: float = 0.04,
    regional_min_quotas: Mapping[str, float] | None = None,
    allow_budget_rollover: bool = False,
) -> CipPortfolioPlan:
    """Execute multi-year budget-constrained portfolio knapsack optimization.

    Distributes candidate infrastructure interventions across years 1..H to maximize
    discounted casualty savings and Net Present Value subject to annual CapEx limits.
    """
    if not candidates:
        raise ValueError("Candidate project list cannot be empty for CIP optimization.")
    if not annual_budgets:
        raise ValueError("Annual budget envelopes cannot be empty for CIP optimization.")

    parsed_candidates: list[CipCandidateProject] = [
        c if isinstance(c, CipCandidateProject) else parse_cip_candidates([c])[0]
        for c in candidates
    ]

    # Pre-sort candidate pool by base BCR descending
    unscheduled_pool = sorted(parsed_candidates, key=lambda p: p.benefit_cost_ratio, reverse=True)

    horizon_years = len(annual_budgets)
    scheduled_projects: list[CipScheduledProject] = []
    yearly_summaries: list[CipYearlySummary] = []

    rollover_balance = 0.0
    global_rank = 1

    for year_idx, base_budget in enumerate(annual_budgets, start=1):
        cal_year = start_calendar_year + (year_idx - 1)
        effective_budget = base_budget + (rollover_balance if allow_budget_rollover else 0.0)

        # Cost inflation factor for year t: (1 + i)^(t - 1)
        cost_multiplier = (1.0 + inflation_rate) ** (year_idx - 1)
        # Discount factor for benefits back to base year: (1 + r)^-(t - 1)
        benefit_discount_factor = (1.0 + discount_rate) ** (-(year_idx - 1))

        year_allocated_cost = 0.0
        year_projects: list[CipScheduledProject] = []
        year_regional_spend: dict[str, float] = {}

        # 1. First Pass: Fulfill Regional Minimum Quota commitments (if specified)
        if regional_min_quotas:
            for reg_id, quota_fraction in regional_min_quotas.items():
                min_reg_budget = effective_budget * quota_fraction
                reg_spent = 0.0

                # Find candidates in this region
                reg_candidates = [p for p in unscheduled_pool if p.region_id == reg_id]
                for p in reg_candidates:
                    esc_cost = p.base_cost_eur * cost_multiplier
                    if (year_allocated_cost + esc_cost <= effective_budget) and (reg_spent < min_reg_budget):
                        disc_pvb = p.present_value_benefits_eur * benefit_discount_factor
                        eff_bcr = disc_pvb / max(1.0, esc_cost)

                        item = CipScheduledProject(
                            project_id=p.project_id,
                            segment_id=p.segment_id,
                            countermeasure_code=p.countermeasure_code,
                            countermeasure_name=p.countermeasure_name,
                            target_user_group=p.target_user_group,
                            scheduled_year_index=year_idx,
                            calendar_year=cal_year,
                            base_cost_eur=p.base_cost_eur,
                            escalated_cost_eur=esc_cost,
                            present_value_benefits_eur=p.present_value_benefits_eur,
                            discounted_benefits_eur=disc_pvb,
                            effective_bcr=eff_bcr,
                            expected_fsi_prevented_20yr=p.expected_fsi_prevented_20yr,
                            region_id=p.region_id,
                            priority_rank=global_rank,
                        )
                        year_projects.append(item)
                        scheduled_projects.append(item)
                        unscheduled_pool.remove(p)

                        year_allocated_cost += esc_cost
                        reg_spent += esc_cost
                        year_regional_spend[reg_id] = year_regional_spend.get(reg_id, 0.0) + esc_cost
                        global_rank += 1

        # 2. Second Pass: Greedy knapsack by highest effective BCR
        # Filter remaining candidate projects that can fit within the remaining annual budget
        remaining_budget = effective_budget - year_allocated_cost
        candidates_to_remove = []

        for p in unscheduled_pool:
            esc_cost = p.base_cost_eur * cost_multiplier
            if year_allocated_cost + esc_cost <= effective_budget:
                disc_pvb = p.present_value_benefits_eur * benefit_discount_factor
                eff_bcr = disc_pvb / max(1.0, esc_cost)

                item = CipScheduledProject(
                    project_id=p.project_id,
                    segment_id=p.segment_id,
                    countermeasure_code=p.countermeasure_code,
                    countermeasure_name=p.countermeasure_name,
                    target_user_group=p.target_user_group,
                    scheduled_year_index=year_idx,
                    calendar_year=cal_year,
                    base_cost_eur=p.base_cost_eur,
                    escalated_cost_eur=esc_cost,
                    present_value_benefits_eur=p.present_value_benefits_eur,
                    discounted_benefits_eur=disc_pvb,
                    effective_bcr=eff_bcr,
                    expected_fsi_prevented_20yr=p.expected_fsi_prevented_20yr,
                    region_id=p.region_id,
                    priority_rank=global_rank,
                )
                year_projects.append(item)
                scheduled_projects.append(item)
                candidates_to_remove.append(p)

                year_allocated_cost += esc_cost
                year_regional_spend[p.region_id] = year_regional_spend.get(p.region_id, 0.0) + esc_cost
                global_rank += 1

        for c in candidates_to_remove:
            unscheduled_pool.remove(c)

        unallocated_year = effective_budget - year_allocated_cost
        rollover_balance = unallocated_year if allow_budget_rollover else 0.0

        year_fsi = sum(p.expected_fsi_prevented_20yr for p in year_projects)
        year_pvb = sum(p.discounted_benefits_eur for p in year_projects)
        year_bcr = year_pvb / max(1.0, year_allocated_cost) if year_projects else 0.0
        util_pct = (year_allocated_cost / max(1.0, effective_budget)) * 100.0

        yearly_summaries.append(
            CipYearlySummary(
                fiscal_year_index=year_idx,
                calendar_year=cal_year,
                budget_ceiling_eur=effective_budget,
                allocated_cost_eur=year_allocated_cost,
                remaining_budget_eur=unallocated_year,
                budget_utilization_pct=util_pct,
                projects_count=len(year_projects),
                expected_fsi_prevented_20yr=year_fsi,
                present_value_benefits_eur=year_pvb,
                average_bcr=year_bcr,
                regional_spend_eur=year_regional_spend,
            )
        )

    tot_budget = sum(annual_budgets)
    tot_invested = sum(p.escalated_cost_eur for p in scheduled_projects)
    tot_pvb = sum(p.discounted_benefits_eur for p in scheduled_projects)
    tot_fsi = sum(p.expected_fsi_prevented_20yr for p in scheduled_projects)
    portfolio_npv = tot_pvb - tot_invested
    portfolio_bcr = tot_pvb / max(1.0, tot_invested) if scheduled_projects else 0.0
    tot_util = (tot_invested / max(1.0, tot_budget)) * 100.0

    return CipPortfolioPlan(
        horizon_years=horizon_years,
        start_calendar_year=start_calendar_year,
        inflation_rate=inflation_rate,
        discount_rate=discount_rate,
        total_budget_eur=tot_budget,
        total_invested_eur=tot_invested,
        total_budget_utilization_pct=tot_util,
        total_projects_scheduled=len(scheduled_projects),
        total_unscheduled_candidates=len(unscheduled_pool),
        total_fsi_prevented_20yr=tot_fsi,
        total_present_value_benefits_eur=tot_pvb,
        portfolio_net_present_value_eur=portfolio_npv,
        portfolio_average_bcr=portfolio_bcr,
        yearly_summaries=yearly_summaries,
        scheduled_projects=scheduled_projects,
    )


def export_cip_portfolio_artifacts(
    portfolio: CipPortfolioPlan,
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export multi-year CIP portfolio plan artifacts (Schedule CSV, Cash Flow JSON, MD Report, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export Scheduled Projects CSV
    csv_path = out_dir / f"{network_label}_cip_project_schedule.csv"
    fieldnames = [
        "priority_rank", "scheduled_year_index", "calendar_year", "project_id",
        "segment_id", "countermeasure_code", "countermeasure_name", "target_user_group",
        "base_cost_eur", "escalated_cost_eur", "discounted_benefits_eur",
        "effective_bcr", "expected_fsi_prevented_20yr", "region_id"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for p in portfolio.scheduled_projects:
            writer.writerow({
                "priority_rank": p.priority_rank,
                "scheduled_year_index": p.scheduled_year_index,
                "calendar_year": p.calendar_year,
                "project_id": p.project_id,
                "segment_id": p.segment_id,
                "countermeasure_code": p.countermeasure_code,
                "countermeasure_name": p.countermeasure_name,
                "target_user_group": p.target_user_group,
                "base_cost_eur": round(p.base_cost_eur, 2),
                "escalated_cost_eur": round(p.escalated_cost_eur, 2),
                "discounted_benefits_eur": round(p.discounted_benefits_eur, 2),
                "effective_bcr": round(p.effective_bcr, 2),
                "expected_fsi_prevented_20yr": round(p.expected_fsi_prevented_20yr, 2),
                "region_id": p.region_id,
            })

    # 2. Export Portfolio JSON Bundle
    json_path = out_dir / f"{network_label}_cip_portfolio_bundle.json"
    json_payload = portfolio.to_dict()
    json_payload["generated_at_utc"] = timestamp
    json_payload["network_label"] = network_label
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    # 3. Export Markdown Executive Report
    md_path = out_dir / f"{network_label}_cip_portfolio_report.md"
    lines = [
        f"# Multi-Year Capital Improvement Plan (CIP): {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        f"- **Planning Horizon:** {portfolio.horizon_years} Years ({portfolio.start_calendar_year} – {portfolio.start_calendar_year + portfolio.horizon_years - 1})",
        f"- **Cost Escalation (Inflation):** {portfolio.inflation_rate * 100.0:.1f}% / year",
        f"- **Social Discount Rate:** {portfolio.discount_rate * 100.0:.1f}% / year",
        f"- **Total Multi-Year Fiscal Envelope:** €{portfolio.total_budget_eur:,.2f}",
        f"- **Total Capital Programmed:** **€{portfolio.total_invested_eur:,.2f}** ({portfolio.total_budget_utilization_pct:.1f}% utilization)",
        f"- **Total Projects Scheduled:** {portfolio.total_projects_scheduled:,} interventions",
        f"- **Unscheduled Candidate Backlog:** {portfolio.total_unscheduled_candidates:,} interventions",
        f"- **Fatalities & Serious Injuries (FSI) Prevented (20yr):** **{portfolio.total_fsi_prevented_20yr:,.1f}** casualties",
        f"- **Net Present Value (NPV):** **€{portfolio.portfolio_net_present_value_eur:,.2f}**",
        f"- **Portfolio Average Benefit-Cost Ratio (BCR):** **{portfolio.portfolio_average_bcr:.2f}x** return",
        "",
        "## Multi-Year Fiscal Cash Flow Schedule",
        "",
        "| Fiscal Year | Calendar Year | Budget Cap (€) | Allocated (€) | Remaining (€) | Util. (%) | Projects | 20yr FSI Saved | Discounted PVB (€) | Avg. BCR |",
        "| :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for y in portfolio.yearly_summaries:
        lines.append(
            f"| Year {y.fiscal_year_index} | {y.calendar_year} | €{y.budget_ceiling_eur:,.0f} | €{y.allocated_cost_eur:,.0f} | €{y.remaining_budget_eur:,.0f} | {y.budget_utilization_pct:.1f}% | {y.projects_count} | {y.expected_fsi_prevented_20yr:.1f} | €{y.present_value_benefits_eur:,.0f} | **{y.average_bcr:.1f}x** |"
        )
    lines.extend([
        "",
        "## Top Scheduled Capital Improvement Projects",
        "",
        "| Rank | Year | Segment ID | Countermeasure | Target User | Escalated Cost (€) | 20yr FSI Saved | Effective BCR | Region |",
        "| ---: | :---: | :--- | :--- | :--- | ---: | ---: | ---: | :--- |",
    ])
    for p in portfolio.scheduled_projects[:25]:
        lines.append(
            f"| #{p.priority_rank} | Y{p.scheduled_year_index} ({p.calendar_year}) | `{p.segment_id}` | {p.countermeasure_name} | {p.target_user_group.title()} | €{p.escalated_cost_eur:,.0f} | {p.expected_fsi_prevented_20yr:.1f} | **{p.effective_bcr:.1f}x** | `{p.region_id}` |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 4. Export Sovereign SHA-256 Audit Manifest
    manifest_path = out_dir / f"{network_label}_cip.manifest.json"
    manifest = {
        "artifact_family": "capital_improvement_plan",
        "network_label": network_label,
        "cip_engine_version": CIP_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "schedule_csv": {"path": str(csv_path.name), "sha256": _sha256(csv_path)},
            "bundle_json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "report_md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "schedule_csv": str(csv_path),
        "bundle_json": str(json_path),
        "report_md": str(md_path),
        "manifest": str(manifest_path),
    }
