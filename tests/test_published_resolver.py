from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.published_resolver import resolve_latest_published_resource


class PublishedResolverTests(unittest.TestCase):
    def test_resolve_latest_published_resource_uses_latest_matching_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "run_registry.jsonl"

            entries = [
                {
                    "stage": "serving",
                    "artifact_kind": "prediction_store",
                    "run_label": "older_run",
                    "document_path": "data/prediction_store/older_run/segment_scores.manifest.json",
                    "document_mtime_utc": "2026-03-28T11:00:00+00:00",
                    "summary": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                        "governance_contract_version": "governance_interoperability_bundle_public_v1",
                        "governance_bundle_path": "data/planning/governance_interoperability/governance_interoperability_bundle.json",
                        "governance_role_policy_ids": [
                            "segment_scores_public_geojson__public",
                            "segment_scores_analyst_csv__analyst",
                        ],
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "older_run",
                            "holdout_years": [2021],
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/older_run/segment_scores_public.geojson",
                        },
                        {
                            "field": "outputs.analyst_csv_path",
                            "path": "data/prediction_store/older_run/segment_scores_analyst.csv",
                        },
                    ],
                },
                {
                    "stage": "serving",
                    "artifact_kind": "prediction_store",
                    "run_label": "latest_run",
                    "document_path": "data/prediction_store/latest_run/segment_scores.manifest.json",
                    "document_mtime_utc": "2026-03-28T12:00:00+00:00",
                    "summary": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                        "governance_contract_version": "governance_interoperability_bundle_public_v1",
                        "governance_bundle_path": "data/planning/governance_interoperability/governance_interoperability_bundle.json",
                        "governance_role_policy_ids": [
                            "segment_scores_public_geojson__public",
                            "segment_scores_analyst_csv__analyst",
                        ],
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "latest_run",
                            "holdout_years": [2021],
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/latest_run/segment_scores_public.geojson",
                        },
                        {
                            "field": "outputs.analyst_csv_path",
                            "path": "data/prediction_store/latest_run/segment_scores_analyst.csv",
                        },
                    ],
                },
                {
                    "stage": "serving",
                    "artifact_kind": "public_score_tiles",
                    "run_label": "latest_tiles",
                    "document_path": "data/prediction_store/latest_tiles/score_tiles.manifest.json",
                    "document_mtime_utc": "2026-03-28T12:30:00+00:00",
                    "summary": {
                        "resource_name": "segment_score_tiles",
                        "public_contract_version": "segment_score_tiles_public_v1",
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "latest_run",
                            "holdout_years": [2021],
                            "tile_size_m": 500.0,
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/latest_tiles/score_tiles_public.geojson",
                        }
                    ],
                },
            ]
            registry_path.write_text(
                "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n",
                encoding="utf-8",
            )

            resolved_segments = resolve_latest_published_resource(
                "segment_scores",
                registry_path=registry_path,
                occurred_year=2021,
                view="analyst_segments",
            )
            self.assertEqual(resolved_segments["resolved"]["run_label"], "latest_run")
            self.assertEqual(
                resolved_segments["resolved"]["resolved_view_path"],
                "data/prediction_store/latest_run/segment_scores_analyst.csv",
            )
            self.assertEqual(
                resolved_segments["resolved"]["governance"]["governance_contract_version"],
                "governance_interoperability_bundle_public_v1",
            )
            self.assertIn(
                "segment_scores_analyst_csv__analyst",
                resolved_segments["resolved"]["governance"]["role_policy_ids"],
            )

            resolved_tiles = resolve_latest_published_resource(
                "segment_score_tiles",
                registry_path=registry_path,
                prediction_run_label="latest_run",
                tile_size_m=500.0,
            )
            self.assertEqual(resolved_tiles["resolved"]["artifact_kind"], "public_score_tiles")
            self.assertEqual(resolved_tiles["resolved"]["resolved_view"], "public_tiles")
            self.assertEqual(
                resolved_tiles["resolved"]["resolved_view_path"],
                "data/prediction_store/latest_tiles/score_tiles_public.geojson",
            )
