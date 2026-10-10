from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.climate_resilience import (
    HAZARD_KINDS,
    assess_climate_resilience,
    ingest_hazard_layer,
    run_climate_resilience_assessment,
    score_segment_climate_risk,
    weather_conditioned_risk,
)


class HazardIngestionTests(unittest.TestCase):
    def test_ingest_keeps_worst_intensity_per_hazard(self) -> None:
        exposures = ingest_hazard_layer(
            [
                {"segment_id": "s1", "hazard_kind": "flood", "intensity": "0.4"},
                {"segment_id": "s1", "hazard_kind": "flood", "intensity": "0.7"},
                {"segment_id": "s1", "hazard_kind": "wind", "intensity": "0.5"},
                {"segment_id": "s2", "hazard_kind": "heat", "intensity": "0.9"},
            ]
        )
        self.assertEqual(exposures["s1"]["flood"], 0.7)
        self.assertEqual(exposures["s1"]["wind"], 0.5)
        self.assertEqual(exposures["s2"]["heat"], 0.9)

    def test_unknown_hazard_kinds_are_ignored(self) -> None:
        exposures = ingest_hazard_layer(
            [{"segment_id": "s1", "hazard_kind": "earthquake", "intensity": "0.9"}]
        )
        self.assertEqual(exposures, {})


class WeatherConditionedRiskTests(unittest.TestCase):
    def test_over_represented_adverse_weather_raises_multiplier(self) -> None:
        # 80% of crashes under adverse weather vs 25% baseline -> >1 multiplier.
        multiplier = weather_conditioned_risk({"crash_count": 10, "adverse_weather_crash_count": 8})
        self.assertGreater(multiplier, 1.0)

    def test_baseline_share_yields_unit_multiplier(self) -> None:
        multiplier = weather_conditioned_risk({"crash_count": 8, "adverse_weather_crash_count": 2})
        self.assertEqual(multiplier, 1.0)

    def test_missing_split_returns_none(self) -> None:
        self.assertIsNone(weather_conditioned_risk({"crash_count": 0}))


class ClimateRiskScoringTests(unittest.TestCase):
    def test_exposed_vulnerable_segment_scores_high(self) -> None:
        scored = score_segment_climate_risk(
            {"maxspeed_numeric": 100, "sinuosity": 1.3, "bridge": "yes", "road_class_rank": 1},
            {"flood": 0.9, "snow_ice": 0.8, "wind": 0.7, "heat": 0.6},
        )
        self.assertGreater(scored["climate_risk_score"], 40.0)
        self.assertIn(scored["dominant_hazard"], HAZARD_KINDS)

    def test_no_hazard_exposure_scores_zero(self) -> None:
        scored = score_segment_climate_risk(
            {"maxspeed_numeric": 90, "bridge": "yes"}, None
        )
        self.assertEqual(scored["climate_risk_score"], 0.0)
        self.assertIsNone(scored["dominant_hazard"])

    def test_assess_network_joins_hazards_by_segment(self) -> None:
        rows = [
            {"segment_id": "a", "maxspeed_numeric": 90, "bridge": "yes"},
            {"segment_id": "b", "maxspeed_numeric": 90, "bridge": ""},
        ]
        hazards = [{"segment_id": "a", "hazard_kind": "flood", "intensity": "0.9"}]
        results = assess_climate_resilience(rows, hazards)
        a = next(r for r in results if r["segment_id"] == "a")
        b = next(r for r in results if r["segment_id"] == "b")
        self.assertGreater(a["climate_risk_score"], b["climate_risk_score"])
        self.assertEqual(b["climate_risk_score"], 0.0)


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_csv_geojson_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments = root / "segments.csv"
            hazards = root / "hazards.csv"
            with segments.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "segment_id", "maxspeed_numeric", "sinuosity", "bridge",
                        "road_class_rank", "latitude", "longitude",
                        "crash_count", "adverse_weather_crash_count",
                    ],
                )
                writer.writeheader()
                for i in range(6):
                    writer.writerow({
                        "segment_id": f"s{i}", "maxspeed_numeric": 80 + i * 4,
                        "sinuosity": 1.0 + i * 0.05, "bridge": "yes" if i % 2 else "",
                        "road_class_rank": 1 + (i % 5), "latitude": 41.0 + i * 0.01,
                        "longitude": 16.8 + i * 0.01, "crash_count": i,
                        "adverse_weather_crash_count": i,
                    })
            with hazards.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["segment_id", "hazard_kind", "intensity"])
                writer.writeheader()
                for i in range(6):
                    writer.writerow({"segment_id": f"s{i}", "hazard_kind": "flood", "intensity": 0.5 + i * 0.05})

            out = root / "climate"
            result = run_climate_resilience_assessment(
                segments_path=segments, hazards_path=hazards, output_dir=out
            )

            self.assertTrue(Path(result["classification_csv_path"]).exists())
            self.assertTrue(Path(result["geojson_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())

            geojson = json.loads(Path(result["geojson_path"]).read_text(encoding="utf-8"))
            self.assertEqual(geojson["type"], "FeatureCollection")
            self.assertEqual(len(geojson["features"]), 6)
            self.assertIn("climate_risk_score", geojson["features"][0]["properties"])

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(set(payload["hazard_kinds"]), set(HAZARD_KINDS))
            # Governance entries for the new record kinds are present.
            self.assertTrue(any(g["record_kind"] == "climate_hazard" for g in payload["governance"]))


if __name__ == "__main__":
    unittest.main()
