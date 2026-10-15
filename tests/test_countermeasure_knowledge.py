import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.countermeasure_knowledge import (
    APPLICABLE_OBJECT_TYPES,
    COUNTERMEASURE_CATEGORIES,
    COUNTERMEASURE_FIELD_CLASSIFICATIONS,
    Countermeasure,
    CountermeasureValidationError,
    Precondition,
    build_scenario_intervention_library,
    countermeasure_is_applicable,
    derive_reduction_bounds,
    evaluate_precondition,
    export_countermeasure_library,
    load_countermeasure_library,
    parse_precondition,
    select_applicable_countermeasures,
)

_VALID_HEADER = (
    "countermeasure_id,name,category,applicable_object_types,intervention_code,"
    "cmf,cmf_ci_low,cmf_ci_high,crash_types,severities,cost_band,"
    "lead_time_months,preconditions,source,source_ref,notes\n"
)
_VALID_ROW = (
    "CM-TST-001,Test measure,junction,node,,0.7,0.6,0.8,angle,all,low,6,"
    "object_type=node|arm_count>=3,FHWA CMF Clearinghouse,CMF ID 1,note\n"
)


def _write_seed(directory: Path, rows: str) -> Path:
    path = directory / "seed.csv"
    path.write_text(_VALID_HEADER + rows, encoding="utf-8")
    return path


class CountermeasureSeedTests(unittest.TestCase):
    def test_default_seed_loads_with_at_least_sixty_entries(self) -> None:
        library = load_countermeasure_library()
        self.assertGreaterEqual(len(library), 60)
        for countermeasure in library:
            self.assertTrue(countermeasure.source)
            self.assertTrue(countermeasure.source_ref)
            self.assertIn(countermeasure.category, COUNTERMEASURE_CATEGORIES)
            self.assertLessEqual(countermeasure.cmf_ci_low, countermeasure.cmf)
            self.assertLessEqual(countermeasure.cmf, countermeasure.cmf_ci_high)
            for object_type in countermeasure.applicable_object_types:
                self.assertIn(object_type, APPLICABLE_OBJECT_TYPES)
            self.assertTrue(countermeasure.preconditions)

    def test_default_seed_covers_all_categories(self) -> None:
        categories = {c.category for c in load_countermeasure_library()}
        self.assertEqual(categories, set(COUNTERMEASURE_CATEGORIES))

    def test_loader_rejects_entry_without_evidence_source(self) -> None:
        row = _VALID_ROW.replace("FHWA CMF Clearinghouse", "")
        with tempfile.TemporaryDirectory() as tmp:
            seed = _write_seed(Path(tmp), row)
            with self.assertRaises(CountermeasureValidationError) as ctx:
                load_countermeasure_library(seed)
        self.assertIn("no evidence source", str(ctx.exception))

    def test_loader_rejects_unknown_category_and_bad_interval(self) -> None:
        bad = (
            "CM-TST-002,Bad measure,volcano,node,,0.9,0.95,0.8,angle,all,low,6,"
            "object_type=node,Some source,ref,\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            seed = _write_seed(Path(tmp), bad)
            with self.assertRaises(CountermeasureValidationError) as ctx:
                load_countermeasure_library(seed)
        message = str(ctx.exception)
        self.assertIn("unknown category", message)
        self.assertIn("confidence interval", message)

    def test_loader_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = _write_seed(Path(tmp), _VALID_ROW + _VALID_ROW)
            with self.assertRaises(CountermeasureValidationError) as ctx:
                load_countermeasure_library(seed)
        self.assertIn("duplicate", str(ctx.exception))


class PreconditionTests(unittest.TestCase):
    def test_parse_handles_all_operators(self) -> None:
        self.assertEqual(
            parse_precondition("arm_count>=3"),
            Precondition("arm_count", ">=", "3"),
        )
        self.assertEqual(
            parse_precondition("signal_control=unsignalized"),
            Precondition("signal_control", "=", "unsignalized"),
        )
        self.assertEqual(
            parse_precondition("curve_radius<=200"),
            Precondition("curve_radius", "<=", "200"),
        )
        with self.assertRaises(CountermeasureValidationError):
            parse_precondition("no-operator-here")

    def test_evaluate_numeric_and_text(self) -> None:
        features = {"arm_count": "4", "signal_control": "Unsignalized", "maxspeed": 50}
        self.assertTrue(evaluate_precondition(parse_precondition("arm_count>=3"), features))
        self.assertFalse(evaluate_precondition(parse_precondition("arm_count>=5"), features))
        self.assertTrue(
            evaluate_precondition(parse_precondition("signal_control=unsignalized"), features)
        )
        self.assertTrue(evaluate_precondition(parse_precondition("maxspeed<=50"), features))
        # Missing features fail closed.
        self.assertFalse(evaluate_precondition(parse_precondition("lighting=absent"), features))

    def test_applicability_selection(self) -> None:
        library = load_countermeasure_library()
        features = {
            "object_type": "node",
            "signal_control": "unsignalized",
            "arm_count": 4,
            "major_aadt": 12000,
            "area_type": "urban",
        }
        applicable = select_applicable_countermeasures(features, countermeasures=library)
        applicable_ids = {c.countermeasure_id for c in applicable}
        self.assertIn("CM-JCT-001", applicable_ids)  # roundabout conversion
        self.assertNotIn("CM-JCT-004", applicable_ids)  # needs signalized control
        # Ordered strongest effect (lowest CMF) first.
        cmfs = [c.cmf for c in applicable]
        self.assertEqual(cmfs, sorted(cmfs))
        roundabout = next(c for c in library if c.countermeasure_id == "CM-JCT-001")
        self.assertTrue(countermeasure_is_applicable(roundabout, features))


class InterventionLibraryTests(unittest.TestCase):
    def test_reduction_bounds_derivation(self) -> None:
        group = [
            Countermeasure(
                countermeasure_id=f"CM-X-{i}",
                name="x",
                category="speed",
                applicable_object_types=("segment",),
                cmf=cmf,
                cmf_ci_low=cmf - 0.1,
                cmf_ci_high=cmf + 0.1,
                crash_types=("all",),
                severities=("all",),
                cost_band="low",
                lead_time_months=3,
                preconditions=(Precondition("object_type", "=", "segment"),),
                source="s",
                source_ref="r",
            )
            for i, cmf in enumerate((0.6, 0.7, 0.8))
        ]
        bounds = derive_reduction_bounds(group)
        self.assertLessEqual(bounds["low"], bounds["central"])
        self.assertLessEqual(bounds["central"], bounds["high"])
        self.assertGreater(bounds["low"], 0.0)
        self.assertLess(bounds["high"], 1.0)
        with self.assertRaises(CountermeasureValidationError):
            derive_reduction_bounds([])

    def test_scenario_intervention_library_is_evidence_backed(self) -> None:
        records = build_scenario_intervention_library()
        codes = {record["intervention_code"] for record in records}
        self.assertEqual(
            codes,
            {
                "speed_management",
                "crossing_protection",
                "signal_timing",
                "cycling_protection",
                "lighting_upgrade",
                "traffic_calming",
            },
        )
        for record in records:
            bounds = record["baseline_reduction_bounds"]
            self.assertLessEqual(bounds["low"], bounds["central"])
            self.assertLessEqual(bounds["central"], bounds["high"])
            evidence = record["evidence"]
            self.assertTrue(evidence["supporting_countermeasure_ids"])
            self.assertTrue(evidence["sources"])


class GovernanceAndExportTests(unittest.TestCase):
    def test_governance_classifications_present(self) -> None:
        field_names = {c.field_name for c in COUNTERMEASURE_FIELD_CLASSIFICATIONS}
        self.assertEqual(field_names, {"cmf", "source", "cost_band"})
        for classification in COUNTERMEASURE_FIELD_CLASSIFICATIONS:
            self.assertEqual(classification.record_kind, "countermeasure_knowledge")

    def test_export_writes_library_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = export_countermeasure_library(output_dir=tmp)
            library_path = Path(result["library_path"])
            manifest_path = Path(result["manifest_path"])
            self.assertTrue(library_path.exists())
            self.assertTrue(manifest_path.exists())
            payload = json.loads(library_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(payload["stats"]["countermeasure_count"], 60)
            self.assertTrue(payload["governance"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("lineage", manifest)
            self.assertEqual(
                manifest["contract"]["resource_name"], "countermeasure_knowledge_library"
            )


if __name__ == "__main__":
    unittest.main()
