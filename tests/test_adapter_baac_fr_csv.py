from __future__ import annotations

from datetime import datetime
import unittest

from road_risk_modeling.adapters.baac_fr_csv import (
    aggregate_baac_casualties,
    map_baac_caracteristiques_row,
)


class BaacCasualtyAggregationTests(unittest.TestCase):
    def test_aggregate_counts_killed_and_injured_per_accident(self) -> None:
        counts = aggregate_baac_casualties(
            [
                {"Num_Acc": "202300000001", "grav": "2"},  # tué
                {"Num_Acc": "202300000001", "grav": "4"},  # blessé léger
                {"Num_Acc": "202300000001", "grav": "1"},  # indemne -> ignored
                {"Num_Acc": "202300000002", "grav": "3"},  # blessé hospitalisé
            ]
        )

        self.assertEqual(counts["202300000001"], {"fatalities": 1, "injuries": 1})
        self.assertEqual(counts["202300000002"], {"fatalities": 0, "injuries": 1})

    def test_aggregate_normalizes_float_style_codes(self) -> None:
        counts = aggregate_baac_casualties(
            [
                {"Num_Acc": "1.0", "grav": "2.0"},
                {"Num_Acc": "1.0", "grav": "1.0"},
            ]
        )

        self.assertEqual(counts["1"], {"fatalities": 1, "injuries": 0})


class BaacCaracteristiquesAdapterTests(unittest.TestCase):
    def test_map_modern_row_with_casualties(self) -> None:
        casualties = aggregate_baac_casualties(
            [
                {"Num_Acc": "202300000001", "grav": "2"},
                {"Num_Acc": "202300000001", "grav": "3"},
                {"Num_Acc": "202300000001", "grav": "3"},
            ]
        )

        record = map_baac_caracteristiques_row(
            {
                "Num_Acc": "202300000001",
                "jour": "14",
                "mois": "7",
                "an": "2023",
                "hrmn": "08:35",
                "lum": "1",
                "dep": "75",
                "com": "75056",
                "agg": "2",
                "int": "6",
                "atm": "1",
                "col": "3",
                "lat": "48,8566",
                "long": "2,3522",
            },
            source_name="caracteristiques-2023.csv",
            source_row_number=1,
            casualties_by_accident=casualties,
            source_year=2023,
        )

        self.assertEqual(record.country_code, "FR")
        self.assertEqual(record.crash_id, "fr-baac-2023:202300000001")
        self.assertEqual(record.source_system, "fr_baac_caracteristiques_csv")
        self.assertEqual(record.province_code, "75")
        self.assertEqual(record.city_code, "75056")
        self.assertEqual(record.latitude, 48.8566)
        self.assertEqual(record.longitude, 2.3522)
        self.assertEqual(record.occurred_at, datetime(2023, 7, 14, 8, 35))
        self.assertEqual(record.timestamp_precision, "minute")
        self.assertEqual(record.occurred_hour, 8)
        self.assertEqual(record.roadway_type, "roundabout")
        self.assertEqual(record.intersection_type, "roundabout")
        self.assertEqual(record.light_condition, "daylight")
        self.assertEqual(record.fatalities, 1)
        self.assertEqual(record.injuries, 2)
        self.assertEqual(record.severity_level, "fatal")
        self.assertEqual(record.extra["fr_baac"]["area_type"], "urban")
        self.assertTrue(record.extra["fr_baac"]["casualty_counts_available"])
        self.assertNotIn("missing_coordinates", record.quality_flags)
        self.assertNotIn("casualty_counts_unavailable", record.quality_flags)

    def test_map_legacy_row_without_time_or_casualties(self) -> None:
        record = map_baac_caracteristiques_row(
            {
                "Num_Acc": "201800012345",
                "jour": "3",
                "mois": "2",
                "an": "18",  # two-digit legacy year
                "hrmn": "1830",  # HHMM legacy time
                "lum": "5",
                "dep": "13",
                "com": "13055",
                "agg": "1",
                "int": "1",
                "atm": "2",
                "lat": "0",  # missing -> dropped
                "long": "",
            },
            source_name="caracteristiques-2018.csv",
            source_row_number=8,
            source_year=2018,
        )

        self.assertEqual(record.occurred_year, 2018)
        self.assertEqual(record.occurred_at, datetime(2018, 2, 3, 18, 30))
        self.assertEqual(record.timestamp_precision, "minute")
        self.assertEqual(record.light_condition, "night_lighting_on")
        self.assertEqual(record.roadway_type, "non_intersection")
        self.assertEqual(record.extra["fr_baac"]["area_type"], "rural")
        self.assertIsNone(record.severity_level)
        self.assertEqual(record.fatalities, 0)
        self.assertIn("missing_coordinates", record.quality_flags)
        self.assertIn("casualty_counts_unavailable", record.quality_flags)

    def test_coordinates_outside_france_are_flagged(self) -> None:
        record = map_baac_caracteristiques_row(
            {
                "Num_Acc": "202300099999",
                "jour": "1",
                "mois": "1",
                "an": "2023",
                "hrmn": "00:10",
                "lat": "41,9",  # Rome -> outside metropolitan France
                "long": "12,5",
            },
            source_name="caracteristiques-2023.csv",
            source_row_number=99,
            source_year=2023,
        )

        self.assertIn("coordinates_outside_metropolitan_france_bounds", record.quality_flags)


if __name__ == "__main__":
    unittest.main()
