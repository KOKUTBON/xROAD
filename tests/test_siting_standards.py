from __future__ import annotations

import unittest

from road_risk_modeling.siting_standards import (
    ItalySitingAdapter,
    applicable_rules,
    check_siting_compliance,
    evaluate_site,
    load_siting_standards,
)


class SitingStandardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_siting_standards()

    def test_library_has_at_least_thirty_cited_rules(self) -> None:
        self.assertGreaterEqual(len(self.rules), 30)
        self.assertEqual(len({rule.rule_id for rule in self.rules}), len(self.rules))
        for rule in self.rules:
            with self.subTest(rule=rule.rule_id):
                self.assertTrue(rule.citation)
                self.assertTrue(rule.source_url)

    def test_every_rule_predicate_passes_fails_and_reports_missing_data(self) -> None:
        for rule in self.rules:
            with self.subTest(rule=rule.rule_id):
                predicate = rule.predicate
                field = predicate["field"]
                operator = predicate["operator"]
                expected = predicate.get("value")
                if operator == "gte":
                    passing, failing = expected, float(expected) - 1
                elif operator == "lte":
                    passing, failing = expected, float(expected) + 1
                elif operator == "eq":
                    passing, failing = expected, not expected if isinstance(expected, bool) else "wrong"
                elif operator == "not_in":
                    passing, failing = "__allowed__", expected[0]
                else:
                    passing, failing = True, False
                self.assertEqual(
                    check_siting_compliance(rule, {field: passing})["status"], "pass"
                )
                self.assertEqual(
                    check_siting_compliance(rule, {field: failing})["status"], "fail"
                )
                missing = check_siting_compliance(rule, {})
                self.assertEqual(missing["status"], "insufficient_data")
                self.assertEqual(missing["citation"], rule.citation)

    def test_country_adapter_combines_italian_eu_global_and_platform_rules(self) -> None:
        selected = applicable_rules(
            self.rules,
            asset_type="school",
            school_grade="primaria",
            adapter=ItalySitingAdapter(),
        )
        jurisdictions = {rule.jurisdiction for rule in selected}
        self.assertTrue({"IT", "RARM"}.issubset(jurisdictions))
        self.assertNotIn("FR", jurisdictions)

    def test_school_grade_rules_are_scoped(self) -> None:
        primary = applicable_rules(
            self.rules,
            asset_type="school",
            school_grade="primaria",
            adapter=ItalySitingAdapter(),
        )
        ids = {rule.rule_id for rule in primary}
        self.assertIn("IT-DM1975-WALK-PRI-10", ids)
        self.assertNotIn("IT-DM1975-WALK-INF-09", ids)

    def test_overall_result_fails_closed_on_mandatory_rule(self) -> None:
        selected = [
            rule for rule in self.rules
            if rule.rule_id in {"RARM-RISK-ENTRANCE-25", "RARM-TRANSIT-31"}
        ]
        result = evaluate_site(
            {
                "entrance_segment_risk_decile": 10,
                "accessible_transit_stop_distance_m": 200,
            },
            asset_type="school",
            rules=selected,
        )
        self.assertEqual(result["overall_status"], "fail")
        self.assertEqual(result["mandatory_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
