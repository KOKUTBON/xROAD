from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.behavioural_safety import (
    BEHAVIOURAL_KPIS,
    behavioural_crash_indicator,
    build_enforcement_priorities,
    run_behavioural_analysis,
    speeding_pressure,
)


class SpeedingPressureTests(unittest.TestCase):
    def test_speed_at_limit_is_zero(self) -> None:
        self.assertEqual(
            speeding_pressure({"observed_p85_speed_kph": 50, "observed_speed_limit_kph": 50}), 0.0
        )

    def test_speed_well_over_limit_saturates(self) -> None:
        self.assertEqual(
            speeding_pressure({"observed_p85_speed_kph": 90, "observed_speed_limit_kph": 50}), 1.0
        )

    def test_missing_speed_returns_none(self) -> None:
        self.assertIsNone(speeding_pressure({"observed_speed_limit_kph": 50}))

    def test_falls_back_to_maxspeed_limit(self) -> None:
        # No observed limit, but maxspeed_numeric present.
        value = speeding_pressure({"observed_p85_speed_kph": 60, "maxspeed_numeric": 50})
        self.assertAlmostEqual(value, 0.5)


class IndicatorTests(unittest.TestCase):
    def test_speeding_and_night_flagged(self) -> None:
        indicator = behavioural_crash_indicator(
            {"observed_p85_speed_kph": 70, "observed_speed_limit_kph": 50, "occurred_hour": 2}
        )
        self.assertIn("speeding", indicator["behavioural_signals"])
        self.assertIn("night_or_weekend", indicator["behavioural_signals"])
        self.assertTrue(indicator["is_behavioural"])

    def test_no_signals_is_not_behavioural(self) -> None:
        indicator = behavioural_crash_indicator(
            {"observed_p85_speed_kph": 48, "observed_speed_limit_kph": 50, "occurred_hour": 14}
        )
        self.assertEqual(indicator["behavioural_signals"], [])
        self.assertFalse(indicator["is_behavioural"])


class EnforcementPriorityTests(unittest.TestCase):
    def test_small_cells_are_suppressed(self) -> None:
        rows = [
            {"corridor_id": "A", "occurred_hour": 2, "observed_p85_speed_kph": 80, "observed_speed_limit_kph": 50}
            for _ in range(3)
        ]
        result = build_enforcement_priorities(rows, min_cell=5)
        # 3 crashes < min_cell 5 -> suppressed, no priorities emitted.
        self.assertEqual(result["priorities"], [])
        self.assertEqual(result["cells_suppressed"], 1)

    def test_surviving_cells_ranked_by_concentration(self) -> None:
        rows = []
        # Corridor A overnight: 6 speeding crashes (high behavioural concentration).
        for _ in range(6):
            rows.append({"corridor_id": "A", "occurred_hour": 2, "observed_p85_speed_kph": 85, "observed_speed_limit_kph": 50})
        # Corridor B afternoon: 6 non-behavioural crashes.
        for _ in range(6):
            rows.append({"corridor_id": "B", "occurred_hour": 14, "observed_p85_speed_kph": 48, "observed_speed_limit_kph": 50})
        result = build_enforcement_priorities(rows, min_cell=5)
        self.assertEqual(len(result["priorities"]), 2)
        top = result["priorities"][0]
        self.assertEqual(top["corridor_id"], "A")
        self.assertEqual(top["time_of_day"], "overnight")
        self.assertEqual(top["dominant_signal"], "speeding")
        self.assertGreater(top["concentration_score"], result["priorities"][1]["concentration_score"])


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_privacy_safe_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crashes = root / "crashes.csv"
            fieldnames = ["corridor_id", "occurred_hour", "observed_p85_speed_kph", "observed_speed_limit_kph", "involves_vru"]
            with crashes.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for i in range(8):
                    writer.writerow({
                        "corridor_id": "SS16", "occurred_hour": 23,
                        "observed_p85_speed_kph": 85, "observed_speed_limit_kph": 50,
                        "involves_vru": "yes" if i % 3 == 0 else "no",
                    })
                for i in range(2):  # small cell -> suppressed
                    writer.writerow({
                        "corridor_id": "SP231", "occurred_hour": 9,
                        "observed_p85_speed_kph": 55, "observed_speed_limit_kph": 50,
                        "involves_vru": "no",
                    })

            out = root / "behaviour"
            result = run_behavioural_analysis(crashes_path=crashes, output_dir=out, min_cell=5)

            self.assertTrue(Path(result["enforcement_priorities_csv_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())
            self.assertEqual(result["cells_suppressed"], 1)  # the 2-crash cell

            payload = json.loads(Path(result["summary_json_path"]).read_text(encoding="utf-8"))
            self.assertTrue(payload["privacy"]["aggregate_only"])
            self.assertFalse(payload["privacy"]["person_level_targeting"])
            self.assertEqual(payload["privacy"]["min_cell_suppression"], 5)
            self.assertEqual(len(payload["behavioural_kpis"]), len(BEHAVIOURAL_KPIS))
            self.assertEqual(payload["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            # No person-level fields leak into the priorities.
            for priority in payload["priorities"]:
                self.assertNotIn("driver_id", priority)
                self.assertIn("corridor_id", priority)


if __name__ == "__main__":
    unittest.main()
