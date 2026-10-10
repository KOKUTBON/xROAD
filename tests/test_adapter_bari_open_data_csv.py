from __future__ import annotations

from datetime import datetime
import unittest

from road_risk_modeling.adapters.bari_open_data_csv import map_bari_open_data_row


class BariOpenDataAdapterTests(unittest.TestCase):
    def test_map_row_with_dispatch_time_and_scaled_coordinates(self) -> None:
        record = map_bari_open_data_row(
            {
                "Data incidente": "01/01/2025",
                "Latitudine": "4.110.309",
                "Longitudine": "1.687.909",
                "Centro abitato": "si",
                "Tipo di strada": "Strada Urbana",
                "Caratteristiche della strada": "Rettilineo",
                "Stato fondo stradale": "Asciutto",
                "Tipo pavimentazione": "Asfaltata",
                "Condizioni meteo": "Sereno",
                "Condizioni traffico": "Scarso",
                "Danni a cose": "no",
                "Incidente con lesioni": "si",
                "Inviata ore": "20:30",
                "Sul posto ore": "20:45",
            },
            source_name="incidenti-2025.csv",
            source_row_number=1,
            source_year=2025,
        )

        self.assertEqual(record.country_code, "IT")
        self.assertEqual(record.city_name, "Bari")
        self.assertEqual(record.province_code, "072")
        self.assertEqual(record.city_code, "006")
        self.assertEqual(record.latitude, 41.10309)
        self.assertEqual(record.longitude, 16.87909)
        self.assertEqual(record.timestamp_precision, "date_dispatch_time_proxy")
        self.assertEqual(record.occurred_at, datetime(2025, 1, 1, 20, 30))
        self.assertEqual(record.occurred_hour, 20)
        self.assertEqual(record.occurred_minute, 30)
        self.assertEqual(record.roadway_type, "straight")
        self.assertEqual(record.intersection_type, "non_intersection")
        self.assertEqual(record.weather_code, "Sereno")
        self.assertEqual(record.severity_level, "injury")
        self.assertEqual(record.injuries, 1)
        self.assertEqual(record.fatalities, 0)
        self.assertEqual(
            record.extra["official_bari_open_data"]["time_of_day_bucket"],
            "evening",
        )
        self.assertNotIn("missing_coordinates", record.quality_flags)

    def test_map_legacy_2022_semicolon_row_without_time(self) -> None:
        record = map_bari_open_data_row(
            {
                "Data incidente": "01/01/2022",
                "lat": "41.07788",
                "lon": "16.87029",
                "Centro abitato": "Sì",
                "Tipo di strada": "Strada urbana",
                "Caratteristiche della strada": "Incrocio",
                "Stato fondo stradale": "Asciutto",
                "Tipo pavimentazione": "Asfaltata",
                "Condizioni meteo": "Sereno",
                "Condizioni traffico": "Scarso",
                "Danni a cose": "No",
                "Incidente con lesioni": "No",
                "Pattuglia inviata ore": "",
                "Pattuglia sul posto ore": "",
            },
            source_name="incidenti-2022.csv",
            source_row_number=8,
            source_year=2022,
        )

        self.assertEqual(record.occurred_year, 2022)
        self.assertEqual(record.timestamp_precision, "day")
        self.assertEqual(record.occurred_at, datetime(2022, 1, 1))
        self.assertEqual(record.roadway_type, "intersection")
        self.assertEqual(record.intersection_type, "intersection")
        self.assertEqual(record.severity_level, "no_injury")
        self.assertIn("missing_dispatch_time", record.quality_flags)
