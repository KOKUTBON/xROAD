"""Unit tests for Multi-Year Capital Improvement Planning (CIP) Optimization Engine."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.cip_engine import (
    CIP_CONTRACT_VERSION,
    CIP_ENGINE_VERSION,
    CipCandidateProject,
    CipPortfolioPlan,
    export_cip_portfolio_artifacts,
    optimize_capital_improvement_plan,
    parse_cip_candidates,
)


class TestCipEngine(unittest.TestCase):
    def test_parse_cip_candidates(self) -> None:
        raw_items = [
            {
                "project_id": "proj-001",
                "segment_id": "seg-101",
                "countermeasure_code": "MEDIAN_SAFETY_BARRIER",
                "countermeasure_name": "Install Central Median Barrier",
                "base_cost_eur": 120_000.0,
                "expected_fsi_prevented_20yr": 15.5,
                "present_value_benefits_eur": 850_000.0,
                "benefit_cost_ratio": 7.08,
                "region_id": "puglia",
            }
        ]
        candidates = parse_cip_candidates(raw_items)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.project_id, "proj-001")
        self.assertEqual(c.countermeasure_code, "MEDIAN_SAFETY_BARRIER")
        self.assertEqual(c.region_id, "puglia")
        self.assertAlmostEqual(c.base_cost_eur, 120_000.0)

    def test_budget_ceilings_strictly_enforced(self) -> None:
        """Verify that in each year, allocated capital does NOT exceed annual budget cap."""
        # 10 candidate projects of 40,000 EUR each
        candidates = [
            CipCandidateProject(
                project_id=f"proj-{i}",
                segment_id=f"seg-{i}",
                countermeasure_code="SIDEWALK",
                countermeasure_name="Sidewalk",
                target_user_group="pedestrian",
                base_cost_eur=40_000.0,
                expected_fsi_prevented_20yr=2.0,
                present_value_benefits_eur=200_000.0,
                benefit_cost_ratio=5.0 - (i * 0.1),
            )
            for i in range(10)
        ]
        # 3-year horizon with 100k budget per year
        annual_budgets = [100_000.0, 100_000.0, 100_000.0]

        portfolio = optimize_capital_improvement_plan(
            candidates=candidates,
            annual_budgets=annual_budgets,
            start_calendar_year=2027,
            inflation_rate=0.0,  # 0% inflation to test clean integer division
            discount_rate=0.0,
            allow_budget_rollover=False,
        )

        self.assertEqual(portfolio.horizon_years, 3)
        self.assertEqual(len(portfolio.yearly_summaries), 3)

        # In each year, exactly 2 projects (80,000 EUR) can fit within 100,000 EUR
        for summary in portfolio.yearly_summaries:
            self.assertLessEqual(summary.allocated_cost_eur, summary.budget_ceiling_eur)
            self.assertEqual(summary.projects_count, 2)
            self.assertEqual(summary.allocated_cost_eur, 80_000.0)
            self.assertEqual(summary.remaining_budget_eur, 20_000.0)

        # Total scheduled projects = 6, unscheduled backlog = 4
        self.assertEqual(portfolio.total_projects_scheduled, 6)
        self.assertEqual(portfolio.total_unscheduled_candidates, 4)

        # Verify deduplication: all scheduled project IDs must be unique
        scheduled_ids = [p.project_id for p in portfolio.scheduled_projects]
        self.assertEqual(len(scheduled_ids), len(set(scheduled_ids)))

    def test_cost_inflation_and_benefit_discounting(self) -> None:
        """Verify cost escalates and benefits discount over multi-year horizon."""
        candidates = [
            CipCandidateProject(
                project_id=f"proj-{i}",
                segment_id=f"seg-{i}",
                countermeasure_code="BARRIER",
                countermeasure_name="Barrier",
                target_user_group="vehicle",
                base_cost_eur=100_000.0,
                expected_fsi_prevented_20yr=5.0,
                present_value_benefits_eur=500_000.0,
                benefit_cost_ratio=5.0,
            )
            for i in range(3)
        ]
        # 1 project per year
        annual_budgets = [105_000.0, 110_000.0, 115_000.0]

        portfolio = optimize_capital_improvement_plan(
            candidates=candidates,
            annual_budgets=annual_budgets,
            start_calendar_year=2027,
            inflation_rate=0.03,  # 3% inflation
            discount_rate=0.05,  # 5% discount
        )

        y1_proj = portfolio.scheduled_projects[0]
        y2_proj = portfolio.scheduled_projects[1]
        y3_proj = portfolio.scheduled_projects[2]

        self.assertEqual(y1_proj.scheduled_year_index, 1)
        self.assertEqual(y2_proj.scheduled_year_index, 2)
        self.assertEqual(y3_proj.scheduled_year_index, 3)

        # Year 1: no inflation applied
        self.assertAlmostEqual(y1_proj.escalated_cost_eur, 100_000.0)
        # Year 2: 100,000 * 1.03 = 103,000
        self.assertAlmostEqual(y2_proj.escalated_cost_eur, 103_000.0)
        # Year 3: 100,000 * (1.03^2) = 106,090
        self.assertAlmostEqual(y3_proj.escalated_cost_eur, 106_090.0)

        # Discounted benefits: Year 1 > Year 2 > Year 3
        self.assertGreater(y1_proj.discounted_benefits_eur, y2_proj.discounted_benefits_eur)
        self.assertGreater(y2_proj.discounted_benefits_eur, y3_proj.discounted_benefits_eur)

    def test_regional_minimum_quotas(self) -> None:
        """Verify that regional minimum allocations are satisfied even if another region has slightly higher BCR."""
        # Region North has higher BCR (10.0), Region South has lower BCR (4.0)
        candidates = [
            CipCandidateProject(
                project_id="proj-north-1",
                segment_id="seg-n1",
                countermeasure_code="BARRIER",
                countermeasure_name="North Barrier",
                target_user_group="vehicle",
                base_cost_eur=50_000.0,
                expected_fsi_prevented_20yr=10.0,
                present_value_benefits_eur=500_000.0,
                benefit_cost_ratio=10.0,
                region_id="region_north",
            ),
            CipCandidateProject(
                project_id="proj-north-2",
                segment_id="seg-n2",
                countermeasure_code="BARRIER",
                countermeasure_name="North Barrier 2",
                target_user_group="vehicle",
                base_cost_eur=50_000.0,
                expected_fsi_prevented_20yr=10.0,
                present_value_benefits_eur=500_000.0,
                benefit_cost_ratio=10.0,
                region_id="region_north",
            ),
            CipCandidateProject(
                project_id="proj-south-1",
                segment_id="seg-s1",
                countermeasure_code="SIDEWALK",
                countermeasure_name="South Sidewalk",
                target_user_group="pedestrian",
                base_cost_eur=40_000.0,
                expected_fsi_prevented_20yr=4.0,
                present_value_benefits_eur=160_000.0,
                benefit_cost_ratio=4.0,
                region_id="region_south",
            ),
        ]
        # Total budget 100,000 EUR in Year 1. Quota: Region South must receive at least 30% (30,000 EUR)
        portfolio = optimize_capital_improvement_plan(
            candidates=candidates,
            annual_budgets=[100_000.0],
            start_calendar_year=2027,
            inflation_rate=0.0,
            regional_min_quotas={"region_south": 0.30},
        )

        scheduled_pids = {p.project_id for p in portfolio.scheduled_projects}
        # Despite North having higher BCR, South-1 must be scheduled due to regional quota
        self.assertIn("proj-south-1", scheduled_pids)
        self.assertIn("proj-north-1", scheduled_pids)
        self.assertNotIn("proj-north-2", scheduled_pids)  # 50k + 40k = 90k, north-2 cannot fit

    def test_export_cip_portfolio_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            candidates = [
                CipCandidateProject(
                    project_id="p1",
                    segment_id="s1",
                    countermeasure_code="CROSSING",
                    countermeasure_name="Pedestrian Crossing",
                    target_user_group="pedestrian",
                    base_cost_eur=30_000.0,
                    expected_fsi_prevented_20yr=1.5,
                    present_value_benefits_eur=150_000.0,
                    benefit_cost_ratio=5.0,
                )
            ]
            portfolio = optimize_capital_improvement_plan(candidates, [50_000.0, 50_000.0])

            paths = export_cip_portfolio_artifacts(portfolio, out_dir, "test_cip")

            for key in ["schedule_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, paths)
                self.assertTrue(Path(paths[key]).exists())

            with Path(paths["bundle_json"]).open("r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["cip_engine_version"], CIP_ENGINE_VERSION)
                self.assertEqual(data["contract_version"], CIP_CONTRACT_VERSION)
                self.assertEqual(data["financial_summary"]["total_projects_scheduled"], 1)


if __name__ == "__main__":
    unittest.main()
