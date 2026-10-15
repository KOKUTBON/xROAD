"""Unit tests for the National Multi-Tier Jurisdictional Hierarchy engine."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.national_hierarchy import (
    AdministrativeEntity,
    AdministrativeTier,
    NationalHierarchy,
    build_sample_italy_national_hierarchy,
    export_national_rollup_report,
)


class TestNationalHierarchy(unittest.TestCase):
    def test_entity_creation_and_serialization(self) -> None:
        entity = AdministrativeEntity(
            entity_id="region:it-75",
            tier=AdministrativeTier.REGION,
            code="IT-75",
            name="Puglia",
            country_code="IT",
            population=3953305,
            land_area_km2=19541.0,
            centerline_km=14200.0,
        )
        data = entity.to_dict()
        self.assertEqual(data["tier"], "region")
        self.assertEqual(data["code"], "IT-75")
        self.assertEqual(data["population"], 3953305)

        restored = AdministrativeEntity.from_dict(data)
        self.assertEqual(restored.entity_id, entity.entity_id)
        self.assertEqual(restored.name, "Puglia")
        self.assertEqual(restored.centerline_km, 14200.0)

    def test_hierarchy_tree_structure(self) -> None:
        hierarchy = NationalHierarchy(country_code="FR", country_name="France")
        root_id = hierarchy.root_id
        self.assertEqual(root_id, "country:fr")

        # Add region
        reg_entity = AdministrativeEntity(
            entity_id="region:fr-idf",
            tier=AdministrativeTier.REGION,
            code="FR-IDF",
            name="Île-de-France",
            country_code="FR",
            parent_id=root_id,
            population=12278210,
        )
        hierarchy.add_entity(reg_entity)

        # Add department
        dept_entity = AdministrativeEntity(
            entity_id="province:fr-75",
            tier=AdministrativeTier.PROVINCE,
            code="75",
            name="Paris",
            country_code="FR",
            parent_id="region:fr-idf",
            population=2145906,
        )
        hierarchy.add_entity(dept_entity)

        # Verify parent-child
        children = hierarchy.get_children(root_id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].entity_id, "region:fr-idf")

        dept_children = hierarchy.get_children("region:fr-idf")
        self.assertEqual(len(dept_children), 1)
        self.assertEqual(dept_children[0].entity_id, "province:fr-75")

        # Verify ancestors
        ancestors = hierarchy.get_ancestors("province:fr-75")
        self.assertEqual(len(ancestors), 2)
        self.assertEqual([a.entity_id for a in ancestors], ["region:fr-idf", "country:fr"])

    def test_sample_italy_hierarchy(self) -> None:
        hierarchy = build_sample_italy_national_hierarchy()
        self.assertEqual(hierarchy.country_code, "IT")
        self.assertEqual(hierarchy.country_name, "Italy")

        regions = hierarchy.list_entities_by_tier(AdministrativeTier.REGION)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].code, "IT-75")

        provinces = hierarchy.list_entities_by_tier(AdministrativeTier.PROVINCE)
        self.assertEqual(len(provinces), 5)  # BA, FG, TA, LE, BR

        municipalities = hierarchy.list_entities_by_tier(AdministrativeTier.MUNICIPALITY)
        self.assertEqual(len(municipalities), 5)

        concessionaires = hierarchy.list_entities_by_tier(AdministrativeTier.CONCESSIONAIRE)
        self.assertEqual(len(concessionaires), 1)

    def test_rollup_calculations(self) -> None:
        hierarchy = build_sample_italy_national_hierarchy()

        crashes_by_entity = {
            "municipality:it-072006": {  # Bari
                "total_crashes": 1000,
                "fatal_crashes": 10,
                "injury_crashes": 700,
                "fatalities": 12,
                "injuries": 850,
            },
            "municipality:it-071024": {  # Foggia
                "total_crashes": 500,
                "fatal_crashes": 5,
                "injury_crashes": 350,
                "fatalities": 6,
                "injuries": 420,
            },
        }

        rollups = hierarchy.calculate_rollups(crashes_by_entity)

        # Bari municipality
        bari_muni = rollups["municipality:it-072006"]
        self.assertEqual(bari_muni.total_crashes, 1000)
        self.assertEqual(bari_muni.fatalities, 12)
        self.assertIsNotNone(bari_muni.fatalities_per_100k_pop)
        self.assertGreater(bari_muni.fatalities_per_100k_pop, 0.0)

        # Bari province
        bari_prov = rollups["province:it-ba-ba"]
        self.assertEqual(bari_prov.total_crashes, 1000)
        self.assertEqual(bari_prov.fatalities, 12)

        # Foggia province
        fg_prov = rollups["province:it-ba-fg"]
        self.assertEqual(fg_prov.total_crashes, 500)
        self.assertEqual(fg_prov.fatalities, 6)

        # Puglia Region
        puglia = rollups["region:it-75"]
        self.assertEqual(puglia.total_crashes, 1500)
        self.assertEqual(puglia.fatalities, 18)

        # Country Root
        country = rollups[hierarchy.root_id]
        self.assertEqual(country.total_crashes, 1500)
        self.assertEqual(country.fatalities, 18)

    def test_hierarchy_json_serialization_cycle(self) -> None:
        original = build_sample_italy_national_hierarchy()
        json_str = original.to_json()

        restored = NationalHierarchy.from_json(json_str)
        self.assertEqual(restored.country_code, original.country_code)
        self.assertEqual(restored.country_name, original.country_name)
        self.assertEqual(len(restored._entities), len(original._entities))

    def test_export_national_rollup_report(self) -> None:
        hierarchy = build_sample_italy_national_hierarchy()
        rollups = hierarchy.calculate_rollups({
            "municipality:it-072006": {"total_crashes": 200, "fatalities": 2, "injuries": 150},
        })

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = export_national_rollup_report(hierarchy, rollups, output_dir=tmp_dir)
            self.assertTrue(Path(paths["json"]).exists())
            self.assertTrue(Path(paths["csv"]).exists())
            self.assertTrue(Path(paths["md"]).exists())

            json_content = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(json_content["country_code"], "IT")
            self.assertIn("rollups", json_content)


if __name__ == "__main__":
    unittest.main()
