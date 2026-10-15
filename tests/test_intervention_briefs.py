from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.intervention_briefs import build_intervention_briefs


class InterventionBriefTests(unittest.TestCase):
    def test_build_intervention_briefs_writes_json_markdown_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            output_dir = root / "intervention_briefs"
            scenario_bundle_root = root / "scenario_countermeasures"
            prediction_store_dir = root / "prediction_store" / "demo_city"
            tile_store_dir = root / "prediction_store" / "demo_city_tiles"
            prediction_store_dir.mkdir(parents=True, exist_ok=True)
            tile_store_dir.mkdir(parents=True, exist_ok=True)
            (scenario_bundle_root / "demo_city_frequency_context").mkdir(parents=True, exist_ok=True)

            segment_manifest_path = prediction_store_dir / "segment_scores.manifest.json"
            segment_manifest_path.write_text(
                json.dumps({"contract": {"resource_name": "segment_scores"}}, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tile_manifest_path = tile_store_dir / "score_tiles.manifest.json"
            tile_manifest_path.write_text(
                json.dumps({"contract": {"resource_name": "segment_score_tiles"}}, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (scenario_bundle_root / "demo_city_frequency_context" / "scenario_bundle.json").write_text(
                json.dumps(
                    {
                        "planning_brief_summary": {
                            "recommended_portfolio": {
                                "title": "Protect crossings and slow the corridor",
                                "expected_crash_reduction": 2.35,
                            }
                        },
                        "portfolio_rankings": [
                            {
                                "scenario_titles": [
                                    "Protect crossings",
                                    "Reduce corridor speeds",
                                ],
                                "expected_crash_reduction": 2.35,
                                "distinct_segment_count": 3,
                            }
                        ],
                        "scenario_rankings": [
                            {
                                "title": "Reduce corridor speeds",
                                "expected_crash_reduction": 1.4,
                                "linked_segment_count": 2,
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            dashboard_summary_path.write_text(
                json.dumps(
                    {
                        "published_runs": [
                            {
                                "city_key": "demo_city",
                                "display_name": "Demo City",
                                "prediction_run_label": "demo_city_frequency_context",
                                "occurred_years": [2021],
                                "segment_scores": {
                                    "manifest_path": str(segment_manifest_path),
                                    "observed_crash_total": 12,
                                    "predicted_crash_total": 10.5,
                                    "segment_score_rows": 44,
                                    "top_5pct_observed_crash_share": 0.42,
                                },
                                "score_tiles": {
                                    "manifest_path": str(tile_manifest_path),
                                    "tile_rows": 8,
                                },
                            }
                        ],
                        "intervention_priority": [
                            {
                                "city_key": "demo_city",
                                "display_name": "Demo City",
                                "prediction_run_label": "demo_city_frequency_context",
                                "tiles_very_high": 5,
                                "tiles_high_or_very_high": 7,
                                "top_5pct_observed_crash_share": 0.42,
                                "cold_start_gap_vs_temporal": 0.065,
                                "history_free_gap_vs_temporal": 0.08,
                            }
                        ],
                        "transferability_matrix": [
                            {
                                "city_key": "demo_city",
                                "display_name": "Demo City",
                                "metrics_by_mode": {
                                    "cross_jurisdiction_temporal": {"mean_poisson_deviance": 0.21},
                                    "cross_jurisdiction_cold_start": {"mean_poisson_deviance": 0.275},
                                    "cross_jurisdiction_history_free": {"mean_poisson_deviance": 0.29},
                                },
                            }
                        ],
                        "intervention_shortlists": [
                            {
                                "city_key": "demo_city",
                                "display_name": "Demo City",
                                "prediction_run_label": "demo_city_frequency_context",
                                "top_corridors": [
                                    {
                                        "corridor_label": "Tangenziale di Demo",
                                        "segment_count": 3,
                                        "predicted_crash_total": 4.75,
                                        "max_public_score_index": 100.0,
                                        "focus_segment_score_ids": [
                                            "demo_city_frequency_context:2021:seg-1",
                                            "demo_city_frequency_context:2021:seg-2",
                                        ],
                                        "top_segments": [
                                            {
                                                "segment_score_id": "demo_city_frequency_context:2021:seg-1",
                                                "segment_label": "Tangenziale di Demo",
                                                "public_score_band": "very_high",
                                                "public_score_index": 100.0,
                                                "predicted_crash_count": 2.4,
                                                "score_rank_desc": 1,
                                                "segment_length_m": 220.0,
                                            }
                                        ],
                                    }
                                ],
                                "hotspot_tiles": [
                                    {
                                        "tile_score_id": "demo_city_frequency_context:2021:0:0:500m",
                                        "tile_very_high_band_segment_count": 2,
                                        "tile_max_public_score_index": 100.0,
                                        "intersection_segment_count": 3,
                                        "top_segments": [
                                            {
                                                "segment_score_id": "demo_city_frequency_context:2021:seg-1",
                                                "segment_label": "Tangenziale di Demo",
                                                "public_score_band": "very_high",
                                                "public_score_index": 100.0,
                                                "predicted_crash_count": 2.4,
                                                "score_rank_desc": 1,
                                                "segment_length_m": 220.0,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_intervention_briefs(
                dashboard_summary_path=dashboard_summary_path,
                output_dir=output_dir,
                scenario_bundle_root=scenario_bundle_root,
            )

            self.assertEqual(payload["intervention_brief_bundle_version"], "intervention_brief_bundle_v1")
            self.assertEqual(payload["brief_count"], 1)
            brief_dir = output_dir / "demo_city_frequency_context"
            json_path = brief_dir / "intervention_brief.json"
            markdown_path = brief_dir / "intervention_brief.md"
            manifest_path = brief_dir / "intervention_brief.manifest.json"
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(manifest_path.exists())

            brief_payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(brief_payload["display_name"], "Demo City")
            self.assertEqual(brief_payload["planning_profile"]["transferability"]["code"], "moderate_local_dependency")
            self.assertEqual(brief_payload["recommended_actions"][0]["code"], "recommended_countermeasure_portfolio")
            self.assertEqual(brief_payload["recommended_actions"][1]["code"], "corridor_field_review")
            self.assertEqual(brief_payload["scenario_countermeasures"]["portfolio_count"], 1)
            self.assertEqual(
                brief_payload["shortlist"]["top_corridors"][0]["top_segments"][0]["segment_score_id"],
                "demo_city_frequency_context:2021:seg-1",
            )

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Demo City Intervention Brief", markdown)
            self.assertIn("Tangenziale di Demo", markdown)
            self.assertIn("Hotspot Tiles", markdown)
            self.assertIn("Scenario Countermeasures", markdown)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["contract"]["resource_name"], "intervention_brief")
            self.assertEqual(manifest["stats"]["recommended_action_count"], 5)
            self.assertEqual(manifest["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
