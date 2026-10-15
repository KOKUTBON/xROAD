from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.weather_ingestion import (
    SOURCE_ATTRIBUTIONS,
    agreement_report,
    build_condition_hour_exposure,
    build_era5_land_request,
    build_open_meteo_url,
    build_weather_join_bundle,
    harmonize_official_weather,
    join_crashes_to_weather,
    parse_era5_records,
    parse_open_meteo_payload,
)


def weather_payload() -> dict:
    return {
        "latitude": 41.125,
        "longitude": 16.875,
        "hourly": {
            "time": [
                "2024-01-01T09:00",
                "2024-01-01T10:00",
                "2024-01-01T12:00",
                "2024-01-02T10:00",
            ],
            "temperature_2m": [8.0, 7.5, 10.0, -1.0],
            "precipitation": [0.0, 1.2, 0.0, 0.4],
            "snow_depth": [0.0, 0.0, 0.0, 0.02],
            "wind_speed_10m": [10.0, 12.0, 45.0, 8.0],
            "wind_gusts_10m": [20.0, 25.0, 60.0, 12.0],
            "weather_code": [0, 61, 2, 71],
        },
    }


class WeatherAdapterTests(unittest.TestCase):
    def test_open_meteo_payload_normalizes_to_canonical_hourly_rows(self) -> None:
        rows = parse_open_meteo_payload(weather_payload())
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1].condition, "wet")
        self.assertEqual(rows[3].condition, "snow_ice")
        self.assertEqual(rows[0].temporal_resolution, "hour")
        self.assertIn("provider_grid_centroid", rows[0].quality_flags)
        self.assertEqual(len({row.weather_observation_id for row in rows}), 4)

    def test_provider_request_contracts_and_attribution(self) -> None:
        url = build_open_meteo_url(
            latitude=41.12,
            longitude=16.87,
            start_date="2024-01-01",
            end_date="2024-01-02",
        )
        self.assertIn("archive-api.open-meteo.com", url)
        self.assertIn("temperature_2m", url)
        request = build_era5_land_request(
            year=2024, month=1, area=[41.3, 16.6, 40.9, 17.1]
        )
        self.assertEqual(request["dataset"], "reanalysis-era5-land")
        self.assertIn("total_precipitation", request["request"]["variable"])
        self.assertEqual(SOURCE_ATTRIBUTIONS["era5_land"]["license"], "CC-BY-4.0")
        self.assertEqual(SOURCE_ATTRIBUTIONS["open_meteo"]["license"], "CC-BY-4.0")

        era5 = parse_era5_records(
            [
                {
                    "latitude": 41.1,
                    "longitude": 16.9,
                    "valid_time": "2024-01-01T10:00:00Z",
                    "t2m": 280.15,
                    "tp": 0.001,
                    "sd": 0.0,
                    "u10": 3.0,
                    "v10": 4.0,
                }
            ]
        )[0]
        self.assertAlmostEqual(era5.temperature_c, 7.0)
        self.assertAlmostEqual(era5.precipitation_mm, 1.0)
        self.assertAlmostEqual(era5.wind_speed_kph, 18.0)
        self.assertEqual(era5.condition, "wet")

    def test_official_weather_harmonization(self) -> None:
        self.assertEqual(harmonize_official_weather("Pioggia in atto"), "wet")
        self.assertEqual(harmonize_official_weather("Nebbia"), "fog")
        self.assertEqual(harmonize_official_weather("Sereno"), "clear")
        self.assertIsNone(harmonize_official_weather(None))


class CrashWeatherJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observations = parse_open_meteo_payload(weather_payload())
        self.crashes = [
            {
                "crash_id": "hourly",
                "occurred_at": "2024-01-01T10:20:00+00:00",
                "occurred_hour": 10,
                "occurred_year": 2024,
                "timestamp_precision": "date_dispatch_time_proxy",
                "latitude": 41.12,
                "longitude": 16.87,
                "segment_id": "seg-1",
                "weather_code": "Pioggia in atto",
            },
            {
                "crash_id": "daily",
                "occurred_at": "2024-01-01T00:00:00+00:00",
                "occurred_hour": None,
                "occurred_year": 2024,
                "timestamp_precision": "date_only",
                "latitude": 41.13,
                "longitude": 16.88,
                "segment_id": "seg-2",
                "weather_code": "Vento forte",
            },
        ]

    def test_join_uses_nearest_hour_and_flags_day_degradation(self) -> None:
        joined = join_crashes_to_weather(self.crashes, self.observations)
        self.assertEqual(joined[0]["weather_join_precision"], "nearest_hour")
        self.assertEqual(joined[0]["weather_condition"], "wet")
        self.assertTrue(joined[0]["weather_condition_agreement"])
        self.assertEqual(joined[1]["weather_join_precision"], "date_noon_proxy")
        self.assertEqual(joined[1]["weather_condition"], "high_wind")

    def test_condition_hours_are_denominators_per_segment_year(self) -> None:
        rows = build_condition_hour_exposure(self.crashes, self.observations)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["observed_weather_hours"], 4)
        self.assertEqual(rows[0]["wet_hours"], 1)
        self.assertEqual(rows[0]["freezing_hours"], 1)

    def test_agreement_report_excludes_unknown_categories(self) -> None:
        joined = join_crashes_to_weather(self.crashes, self.observations)
        report = agreement_report(joined)
        self.assertEqual(report["comparable_crash_count"], 2)
        self.assertEqual(report["agreement_rate"], 1.0)

    def test_bundle_writes_join_exposure_agreement_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crash_path = root / "crashes.jsonl"
            weather_path = root / "weather.json"
            crash_path.write_text(
                "\n".join(json.dumps(row) for row in self.crashes), encoding="utf-8"
            )
            weather_path.write_text(json.dumps(weather_payload()), encoding="utf-8")
            result = build_weather_join_bundle(
                crashes=self.crashes,
                observations=self.observations,
                output_dir=root / "output",
                crash_source_path=crash_path,
                weather_source_path=weather_path,
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["stats"]["matched_crash_count"], 2)
            self.assertEqual(
                manifest["lineage"]["lineage_contract_version"],
                "artifact_lineage_v1",
            )
            self.assertTrue(Path(result["condition_hour_exposure_path"]).exists())
            self.assertTrue(manifest["governance"])


if __name__ == "__main__":
    unittest.main()
