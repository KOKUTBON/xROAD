from __future__ import annotations

import unittest
import csv
import json
from pathlib import Path
import tempfile

from road_risk_modeling.climate_resilience import score_segment_climate_risk
from road_risk_modeling.weather_risk_model import (
    evaluate_weather_model,
    build_weather_risk_model_bundle,
    model_derived_hazard_profile,
    train_weather_risk_model,
    weather_countermeasures,
)


def fixture_rows() -> list[dict]:
    rows = []
    conditions = ("clear", "wet", "high_wind", "heat")
    cities = ("bari", "foggia", "taranto", "lecce")
    for year in (2022, 2023, 2024, 2025):
        for index in range(24):
            speed = 30 + (index % 4) * 20
            bridge = index % 3 == 0
            city = cities[index % len(cities)]
            for condition in conditions:
                base_rate = 0.001 + speed / 100000
                multiplier = 1.0
                if condition == "wet":
                    multiplier = 1.2 + speed / 100
                elif condition == "high_wind":
                    multiplier = 2.2 if bridge else 1.05
                elif condition == "heat":
                    multiplier = 1.4 if index % 2 else 1.1
                hours = 1000 + (index % 5) * 100
                rows.append(
                    {
                        "segment_id": f"seg-{index}",
                        "city_key": city,
                        "occurred_year": year,
                        "condition": condition,
                        "condition_hours": hours,
                        "crash_count": base_rate * multiplier * hours,
                        "maxspeed_numeric": speed,
                        "sinuosity": 1.0 + (index % 3) * 0.08,
                        "gradient_proxy": (index % 4) / 4,
                        "road_class_rank": 1 + index % 5,
                        "junction_density": (index % 6) / 6,
                        "lighting_quality": 0.4 + (index % 3) * 0.2,
                        "bridge": bridge,
                        "tunnel": index % 7 == 0,
                        "anti_skid_surface": index % 5 == 0,
                    }
                )
    return rows


class WeatherRiskModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = fixture_rows()
        cls.model = train_weather_risk_model(cls.rows, seed=7)

    def test_temporal_holdout_beats_fixed_heuristic(self) -> None:
        evaluation = evaluate_weather_model(self.model, self.rows)
        self.assertTrue(evaluation["beats_heuristic"])
        self.assertLess(
            evaluation["model_mae_crashes"], evaluation["heuristic_mae_crashes"]
        )
        self.assertEqual(set(evaluation["transferability"]), {"bari", "foggia", "lecce", "taranto"})
        self.assertIsNotNone(
            evaluation["calibration"]["predicted_adverse_crash_share"]
        )

    def test_weather_interactions_and_partial_pooling_are_exposed(self) -> None:
        fast = next(row for row in self.rows if row["maxspeed_numeric"] == 90)
        wet = self.model.condition_multiplier(fast, condition="wet")
        self.assertGreater(wet["multiplier"], 1.0)
        self.assertLessEqual(wet["multiplier_low"], wet["multiplier"])
        self.assertGreaterEqual(wet["multiplier_high"], wet["multiplier"])
        unseen = self.model.predict_rate(
            {**fast, "segment_id": "unseen", "city_key": "brindisi"},
            condition="wet",
        )
        self.assertEqual(unseen["segment_pooling_weight"], 0)
        self.assertTrue(unseen["cold_start_city"])

    def test_model_profile_replaces_climate_heuristic_with_intervals(self) -> None:
        bridge = next(row for row in self.rows if row["bridge"])
        profile = model_derived_hazard_profile(self.model, bridge)
        scored = score_segment_climate_risk(
            {**bridge, **profile, "crash_count": 10, "adverse_weather_crash_count": 0},
            {"flood": 0.8, "snow_ice": 0.4, "wind": 0.9, "heat": 0.3},
        )
        self.assertEqual(scored["weather_risk_source"], "trained_model")
        self.assertEqual(
            scored["weather_conditioned_multiplier"],
            profile["weather_model_multiplier"],
        )
        self.assertIsNotNone(scored["weather_conditioned_multiplier_low"])
        self.assertAlmostEqual(sum(scored["hazard_weights"].values()), 1.0, places=5)

    def test_weather_sensitive_sites_feed_countermeasures(self) -> None:
        bridge = next(row for row in self.rows if row["bridge"])
        profile = model_derived_hazard_profile(self.model, bridge)
        measures = weather_countermeasures(profile)
        self.assertTrue(measures)
        self.assertTrue(all("countermeasure_id" in measure for measure in measures))

    def test_training_is_deterministic(self) -> None:
        second = train_weather_risk_model(self.rows, seed=7)
        row = self.rows[0]
        self.assertEqual(
            self.model.condition_multiplier(row, condition="wet"),
            second.condition_multiplier(row, condition="wet"),
        )

    def test_registered_bundle_refreshes_model_powered_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            training = root / "training.csv"
            segments = root / "segments.csv"
            hazards = root / "hazards.csv"
            with training.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(self.rows[0]))
                writer.writeheader()
                writer.writerows(self.rows)
            segment_rows = [
                {
                    **{
                        key: value
                        for key, value in self.rows[0].items()
                        if key not in {"condition", "condition_hours", "crash_count"}
                    },
                    "latitude": 41.12,
                    "longitude": 16.87,
                }
            ]
            with segments.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(segment_rows[0]))
                writer.writeheader()
                writer.writerows(segment_rows)
            with hazards.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["segment_id", "hazard_kind", "intensity"]
                )
                writer.writeheader()
                writer.writerow(
                    {"segment_id": "seg-0", "hazard_kind": "wind", "intensity": 0.8}
                )
            result = build_weather_risk_model_bundle(
                training_rows_path=training,
                segments_path=segments,
                hazards_path=hazards,
                output_dir=root / "model",
                seed=7,
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            surface = json.loads(
                Path(result["climate_risk_surface_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["contract"]["resource_name"], "weather_risk_model")
            self.assertEqual(
                manifest["lineage"]["lineage_contract_version"], "artifact_lineage_v1"
            )
            self.assertEqual(
                surface["features"][0]["properties"]["weather_risk_source"],
                "trained_model",
            )


if __name__ == "__main__":
    unittest.main()
