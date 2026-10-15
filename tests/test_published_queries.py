from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.data_governance import (
    SCORE_TILE_FIELD_CLASSIFICATIONS,
    SEGMENT_SCORE_FIELD_CLASSIFICATIONS,
    publishable_fields_for_role,
)
from road_risk_modeling.published_queries import (
    VIEW_ROLE_POLICY,
    _apply_matrix_filter,
    _apply_segment_score_matrix_filter,
    query_published_resource,
)


class PublishedQueriesTests(unittest.TestCase):
    def test_query_published_resource_supports_segment_and_tile_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            public_segments_geojson = root / "segment_scores_public.geojson"
            analyst_segments_csv = root / "segment_scores_analyst.csv"
            segment_manifest = root / "segment_scores.manifest.json"
            public_tiles_geojson = root / "score_tiles_public.geojson"
            tile_manifest = root / "score_tiles.manifest.json"

            public_segments_geojson.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-1",
                                    "segment_id": "seg-1",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 98.0,
                                    "public_score_band": "very_high",
                                    "score_decile": 1,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-2",
                                    "segment_id": "seg-2",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 70.0,
                                    "public_score_band": "moderate",
                                    "score_decile": 4,
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with analyst_segments_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "segment_score_id",
                        "segment_id",
                        "occurred_year",
                        "prediction_run_label",
                        "prediction_task",
                        "prediction_column",
                        "predicted_crash_count",
                        "observed_crash_count",
                        "score_rank_desc",
                        "score_percentile",
                        "score_decile",
                        "public_score_index",
                        "public_score_band",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "segment_score_id": "run:2021:seg-1",
                            "segment_id": "seg-1",
                            "occurred_year": 2021,
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "prediction_column": "random_forest_poisson_prediction",
                            "predicted_crash_count": 2.5,
                            "observed_crash_count": 1,
                            "score_rank_desc": 1,
                            "score_percentile": 1.0,
                            "score_decile": 1,
                            "public_score_index": 98.0,
                            "public_score_band": "very_high",
                        },
                        {
                            "segment_score_id": "run:2021:seg-2",
                            "segment_id": "seg-2",
                            "occurred_year": 2021,
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "prediction_column": "random_forest_poisson_prediction",
                            "predicted_crash_count": 1.0,
                            "observed_crash_count": 0,
                            "score_rank_desc": 2,
                            "score_percentile": 0.5,
                            "score_decile": 4,
                            "public_score_index": 70.0,
                            "public_score_band": "moderate",
                        },
                    ]
                )

            segment_manifest.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_scores",
                            "public_contract_version": "segment_scores_public_v1",
                            "analyst_contract_version": "segment_scores_analyst_v1",
                        },
                        "outputs": {
                            "public_geojson_path": str(public_segments_geojson),
                            "analyst_csv_path": str(analyst_segments_csv),
                        },
                        "stats": {"segment_score_rows": 2},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            public_tiles_geojson.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                                "properties": {
                                    "tile_score_id": "run:2021:0:0:500m",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "tile_size_m": 500,
                                    "tile_segment_count": 4,
                                    "tile_mean_public_score_index": 84.0,
                                    "tile_max_public_score_index": 100.0,
                                    "tile_public_score_band": "very_high",
                                    "tile_score_decile": 1,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]]},
                                "properties": {
                                    "tile_score_id": "run:2021:1:1:500m",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "tile_size_m": 500,
                                    "tile_segment_count": 2,
                                    "tile_mean_public_score_index": 55.0,
                                    "tile_max_public_score_index": 60.0,
                                    "tile_public_score_band": "moderate",
                                    "tile_score_decile": 5,
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            tile_manifest.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_score_tiles",
                            "public_contract_version": "segment_score_tiles_public_v1",
                        },
                        "outputs": {
                            "public_geojson_path": str(public_tiles_geojson),
                        },
                        "stats": {"tile_rows": 2},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            public_segments = query_published_resource(
                segment_manifest,
                view="public_segments",
                occurred_year=2021,
                min_score_band="high",
            )
            self.assertEqual(public_segments["view"], "public_segments")
            self.assertEqual(public_segments["contract_version"], "segment_scores_public_v1")
            self.assertEqual(public_segments["stats"]["returned_features"], 1)
            # `segment_id` is classified as `internal` in the
            # `segment_score` matrix; the public view filter
            # (data_governance / Issue 01) strips it. The synthetic
            # `segment_score_id` is the public surface identifier.
            public_properties = public_segments["data"]["features"][0]["properties"]
            self.assertNotIn("segment_id", public_properties)
            self.assertEqual(
                public_properties["segment_score_id"], "run:2021:seg-1",
            )
            # The matrix-filter metadata must be present so clients know
            # which redaction policy was applied.
            self.assertEqual(public_segments["redaction_policy"]["role"], "public")
            self.assertEqual(
                public_segments["redaction_policy"]["record_kind"], "segment_score",
            )

            analyst_segments = query_published_resource(
                segment_manifest,
                view="analyst_segments",
                occurred_year=2021,
                limit=1,
            )
            self.assertEqual(analyst_segments["view"], "analyst_segments")
            self.assertEqual(analyst_segments["contract_version"], "segment_scores_analyst_v1")
            self.assertEqual(analyst_segments["stats"]["returned_rows"], 1)
            self.assertEqual(analyst_segments["data"]["rows"][0]["score_rank_desc"], "1")
            # `analyst_segments` is now matrix-tracked too (every
            # ANALYST_CORE_FIELDS column is registered in the
            # segment_score matrix). The redaction_policy meta block
            # must report record_kind='segment_score' and role='analyst'.
            self.assertEqual(analyst_segments["redaction_policy"]["record_kind"], "segment_score")
            self.assertEqual(analyst_segments["redaction_policy"]["role"], "analyst")
            # Matrix-known internal/restricted fields still flow through
            # for analyst (the filter only strips fields whose
            # role_visibility excludes 'analyst' or aren't in the matrix
            # at all).
            for matrix_known in ("segment_id", "predicted_crash_count", "observed_crash_count", "score_rank_desc"):
                self.assertIn(matrix_known, analyst_segments["data"]["rows"][0])

            public_tiles = query_published_resource(
                tile_manifest,
                min_score_band="high",
            )
            self.assertEqual(public_tiles["view"], "public_tiles")
            self.assertEqual(public_tiles["contract_version"], "segment_score_tiles_public_v1")
            self.assertEqual(public_tiles["stats"]["returned_features"], 1)
            self.assertEqual(
                public_tiles["data"]["features"][0]["properties"]["tile_score_id"],
                "run:2021:0:0:500m",
            )
            # `public_tiles` is now matrix-tracked (`score_tile` record
            # kind). The redaction policy meta block must announce it.
            self.assertEqual(public_tiles["redaction_policy"]["record_kind"], "score_tile")
            self.assertEqual(public_tiles["redaction_policy"]["role"], "public")

    def test_query_published_resource_resolves_repo_relative_paths_from_root_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data" / "prediction_store" / "demo_run"
            data_root.mkdir(parents=True, exist_ok=True)

            public_segments_geojson = data_root / "segment_scores_public.geojson"
            public_segments_geojson.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-1",
                                    "segment_id": "seg-1",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 98.0,
                                    "public_score_band": "very_high",
                                    "score_decile": 1,
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            segment_manifest = data_root / "segment_scores.manifest.json"
            segment_manifest.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_scores",
                            "public_contract_version": "segment_scores_public_v1",
                            "analyst_contract_version": "segment_scores_analyst_v1",
                        },
                        "outputs": {
                            "public_geojson_path": "data/prediction_store/demo_run/segment_scores_public.geojson",
                            "analyst_csv_path": "data/prediction_store/demo_run/segment_scores_analyst.csv",
                        },
                        "stats": {"segment_score_rows": 1},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = query_published_resource(
                "data/prediction_store/demo_run/segment_scores.manifest.json",
                view="public_segments",
                occurred_year=2021,
                root_dir=root,
            )
            self.assertEqual(payload["stats"]["returned_features"], 1)


class MatrixPolicyFilterTests(unittest.TestCase):
    """Cross-policy invariants between `data_governance` and `published_queries`.

    The filter at the bottom of `query_published_resource` is the
    defense-in-depth that compounds the matrix-driven redaction enforced
    upstream in `apps/api/services/segment_drill_down.py`.
    """

    def _feature_collection_with_all_segment_fields(self) -> dict:
        # Build a FeatureCollection whose first feature carries every
        # known `segment_score` field plus an internal QC field that
        # should be stripped.
        properties = {entry.field_name: f"value:{entry.field_name}" for entry in SEGMENT_SCORE_FIELD_CLASSIFICATIONS}
        properties["debug_internal_qc"] = "should_be_stripped_if_filtered"
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": properties,
                }
            ],
        }

    def test_public_filter_strips_every_non_public_segment_score_field(self) -> None:
        data = self._feature_collection_with_all_segment_fields()
        filtered, meta = _apply_segment_score_matrix_filter(data, "public")
        kept = set(filtered["features"][0]["properties"].keys())
        for entry in SEGMENT_SCORE_FIELD_CLASSIFICATIONS:
            if "public" not in entry.role_visibility and entry.field_name in kept:
                self.fail(
                    f"Public filter leaked `{entry.field_name}` "
                    f"(classification={entry.classification})"
                )

    def test_public_filter_strips_unregistered_internal_fields(self) -> None:
        # `debug_internal_qc` is not registered in the matrix at all;
        # default-deny must drop it from the public view.
        data = self._feature_collection_with_all_segment_fields()
        filtered, _ = _apply_segment_score_matrix_filter(data, "public")
        self.assertNotIn(
            "debug_internal_qc",
            filtered["features"][0]["properties"].keys(),
        )

    def test_public_filter_keeps_every_public_segment_score_field(self) -> None:
        data = self._feature_collection_with_all_segment_fields()
        filtered, _ = _apply_segment_score_matrix_filter(data, "public")
        kept = set(filtered["features"][0]["properties"].keys())
        for field_name in publishable_fields_for_role("segment_score", "public"):
            self.assertIn(
                field_name, kept,
                f"Public filter dropped matrix-allowed field `{field_name}`",
            )

    def test_policy_meta_records_role_and_publishable_field_list(self) -> None:
        data = self._feature_collection_with_all_segment_fields()
        _, meta = _apply_segment_score_matrix_filter(data, "public")
        self.assertEqual(meta["record_kind"], "segment_score")
        self.assertEqual(meta["role"], "public")
        self.assertEqual(
            set(meta["publishable_fields"]),
            set(publishable_fields_for_role("segment_score", "public")),
        )

    def test_tabular_filter_strips_non_public_columns(self) -> None:
        properties = {entry.field_name: "v" for entry in SEGMENT_SCORE_FIELD_CLASSIFICATIONS}
        properties["debug_internal_qc"] = "should_be_stripped"
        data = {"type": "tabular", "rows": [properties]}
        filtered, _ = _apply_segment_score_matrix_filter(data, "public")
        kept = set(filtered["rows"][0].keys())
        self.assertNotIn("segment_id", kept)
        self.assertNotIn("predicted_crash_count", kept)
        self.assertNotIn("observed_crash_count", kept)
        self.assertNotIn("debug_internal_qc", kept)
        self.assertIn("public_score_band", kept)
        self.assertIn("public_score_index", kept)

    def test_view_role_policy_filters_analyst_view_with_analyst_role(self) -> None:
        # Once every column in ANALYST_CORE_FIELDS was registered in
        # the segment_score matrix, the analyst_segments view became
        # safe to default-deny too. The bulk-query path now strips any
        # column that is unregistered or whose role_visibility
        # excludes 'analyst', symmetric with public_segments.
        tile_policy = VIEW_ROLE_POLICY.get("segment_scores", {})
        self.assertEqual(tile_policy.get("analyst_segments"), ("segment_score", "analyst"))
        self.assertEqual(tile_policy.get("public_segments"), ("segment_score", "public"))

    def test_analyst_filter_strips_unregistered_columns_but_keeps_internal_restricted(self) -> None:
        # Build a tabular row carrying every segment_score matrix field
        # plus one unregistered debug column. The analyst filter must
        # strip the debug column but keep the internal and restricted
        # fields (segment_id, predicted_crash_count, observed_crash_count
        # are analyst-visible per the matrix).
        properties = {entry.field_name: "v" for entry in SEGMENT_SCORE_FIELD_CLASSIFICATIONS}
        properties["debug_unregistered"] = "should_be_stripped"
        data = {"type": "tabular", "rows": [properties]}
        filtered, meta = _apply_matrix_filter(data, "segment_score", "analyst")
        kept = set(filtered["rows"][0].keys())
        # Unregistered column stripped.
        self.assertNotIn("debug_unregistered", kept)
        # Internal + restricted fields preserved for analyst.
        self.assertIn("segment_id", kept)
        self.assertIn("predicted_crash_count", kept)
        self.assertIn("observed_crash_count", kept)
        # Analyst-CSV metadata preserved (the three fields added under
        # the previous ANALYST_CORE_FIELDS subset commit).
        self.assertIn("prediction_column", kept)
        self.assertIn("score_percentile", kept)
        self.assertIn("score_rank_desc", kept)
        # Public fields obviously preserved.
        self.assertIn("public_score_band", kept)
        self.assertIn("public_score_index", kept)
        # Policy meta block reports the role applied.
        self.assertEqual(meta["role"], "analyst")
        self.assertEqual(meta["record_kind"], "segment_score")


class ScoreTileMatrixFilterTests(unittest.TestCase):
    """Cross-policy invariants for the `score_tile` record kind + public_tiles view."""

    def _feature_collection_with_all_score_tile_fields(self) -> dict:
        properties = {entry.field_name: f"value:{entry.field_name}" for entry in SCORE_TILE_FIELD_CLASSIFICATIONS}
        # Inject an unregistered internal-looking field; the default-
        # deny pass must drop it from the public view.
        properties["debug_internal_raw_segment_ids"] = ["s1", "s2", "s3"]
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                    "properties": properties,
                }
            ],
        }

    def test_public_tiles_view_is_in_VIEW_ROLE_POLICY(self) -> None:
        tile_policy = VIEW_ROLE_POLICY.get("segment_score_tiles")
        self.assertIsNotNone(tile_policy)
        assert tile_policy is not None  # type narrowing for mypy
        self.assertEqual(tile_policy.get("public_tiles"), ("score_tile", "public"))

    def test_apply_matrix_filter_drops_unregistered_tile_field(self) -> None:
        data = self._feature_collection_with_all_score_tile_fields()
        filtered, meta = _apply_matrix_filter(data, "score_tile", "public")
        kept = set(filtered["features"][0]["properties"].keys())
        self.assertNotIn("debug_internal_raw_segment_ids", kept)
        self.assertEqual(meta["record_kind"], "score_tile")
        self.assertEqual(meta["role"], "public")

    def test_apply_matrix_filter_keeps_every_public_score_tile_field(self) -> None:
        data = self._feature_collection_with_all_score_tile_fields()
        filtered, _ = _apply_matrix_filter(data, "score_tile", "public")
        kept = set(filtered["features"][0]["properties"].keys())
        for entry in SCORE_TILE_FIELD_CLASSIFICATIONS:
            self.assertIn(
                entry.field_name, kept,
                f"Public filter dropped matrix-allowed score_tile field `{entry.field_name}`",
            )

    def test_segment_score_back_compat_wrapper_still_works(self) -> None:
        # The original `_apply_segment_score_matrix_filter` was renamed
        # to the generic `_apply_matrix_filter`. The old name must keep
        # working for external callers, dispatching to
        # `_apply_matrix_filter(data, "segment_score", role)`.
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "segment_score_id": "s1",
                        "public_score_index": 95.0,
                        "public_score_band": "very_high",
                        "segment_id": "raw-segment-id-should-be-stripped",
                    },
                }
            ],
        }
        filtered, meta = _apply_segment_score_matrix_filter(data, "public")
        kept = set(filtered["features"][0]["properties"].keys())
        self.assertNotIn("segment_id", kept)
        self.assertIn("segment_score_id", kept)
        self.assertEqual(meta["record_kind"], "segment_score")
        self.assertEqual(meta["role"], "public")
