from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.forecast_risk import (
    build_forecast_risk_bundle,
    build_forecast_risk_surface,
    build_weather_alerts,
    parse_open_meteo_forecast,
    readiness_rows,
)
from road_risk_modeling.weather_risk_model import train_weather_risk_model
from tests.test_weather_risk_model import fixture_rows


class ForecastRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = train_weather_risk_model(fixture_rows(), seed=7)
        cls.segments = [
            {
                **fixture_rows()[0],
                "segment_id": "bridge-1",
                "baseline_risk_score": 55,
                "bridge": True,
                "latitude": 41.12,
                "longitude": 16.87,
            },
            {
                **fixture_rows()[4],
                "segment_id": "road-2",
                "baseline_risk_score": 20,
                "bridge": False,
                "latitude": 41.13,
                "longitude": 16.88,
            },
        ]
        cls.payload = {
            "hourly": {
                "time": ["2026-01-01T00:00", "2026-01-01T01:00"],
                "temperature_2m": [5, 4],
                "precipitation": [0, 8],
                "snow_depth": [0, 0],
                "wind_speed_10m": [10, 65],
                "weather_code": [0, 61],
                "temperature_2m_spread": [1, 4],
            }
        }

    def test_forecast_parser_and_72_hour_cap(self) -> None:
        rows = parse_open_meteo_forecast(self.payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["condition"], "clear")
        self.assertEqual(rows[1]["condition"], "wet")

    def test_synthetic_storm_fires_honest_alert(self) -> None:
        forecast = parse_open_meteo_forecast(self.payload)
        rows = build_forecast_risk_surface(
            self.model,
            segments=self.segments,
            forecast=forecast,
            generated_at_utc="2026-01-01T00:00:00+00:00",
        )
        alerts = build_weather_alerts(rows, organization_id="org-bari", threshold=60)
        self.assertTrue(alerts)
        self.assertIn("not a prediction of an individual crash", alerts[0]["message"])
        self.assertLessEqual(alerts[0]["minimum_model_confidence"], 0.9)

    def test_readiness_limits_to_weather_sensitive_structures(self) -> None:
        rows = build_forecast_risk_surface(
            self.model,
            segments=self.segments,
            forecast=parse_open_meteo_forecast(self.payload),
            generated_at_utc="2026-01-01T00:00:00+00:00",
        )
        readiness = readiness_rows(rows)
        self.assertTrue(readiness)
        self.assertEqual({row["segment_id"] for row in readiness}, {"bridge-1"})

    def test_bundle_records_retention_lineage_and_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            forecast_path = root / "forecast.json"
            model_path = root / "model.joblib"
            forecast_path.write_text(json.dumps(self.payload), encoding="utf-8")
            model_path.write_bytes(b"fixture-model")
            result = build_forecast_risk_bundle(
                self.model,
                segments=self.segments,
                forecast=parse_open_meteo_forecast(self.payload),
                organization_id="org-bari",
                generated_at_utc="2026-01-01T00:00:00+00:00",
                output_dir=root / "output",
                forecast_source_path=forecast_path,
                model_source_path=model_path,
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["horizon_hours"], 72)
            self.assertEqual(manifest["retention_hours"], 96)
            self.assertFalse(manifest["honesty"]["individual_crash_prediction"])
            self.assertGreaterEqual(manifest["stats"]["alert_count"], 1)


if __name__ == "__main__":
    unittest.main()
