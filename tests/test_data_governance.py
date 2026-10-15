"""Tests for the data governance bundle (Issue 01)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.canonical_schema import CanonicalCrashRecord
from road_risk_modeling.data_governance import (
    ALL_FIELD_CLASSIFICATIONS,
    CANONICAL_CRASH_FIELD_CLASSIFICATIONS,
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_LEVELS,
    CLASSIFICATION_PUBLIC,
    CLASSIFICATION_RESTRICTED,
    CLASSIFICATION_SENSITIVE,
    DATA_GOVERNANCE_BUNDLE_VERSION,
    NODE_YEAR_METRIC_FIELD_CLASSIFICATIONS,
    PUBLIC_MAP_POLICIES,
    RECORD_KIND_CLASSIFICATIONS,
    REPORT_FIELD_CLASSIFICATIONS,
    RETENTION_RULES,
    SCENARIO_FIELD_CLASSIFICATIONS,
    SEGMENT_SCORE_FIELD_CLASSIFICATIONS,
    SOURCE_LICENSING_REGISTER,
    build_data_governance_bundle,
    classifications_for_record_kind,
    field_classification_for,
    field_classification_index,
    is_field_publishable_for_role,
    license_register_index,
    licenses_by_publication_status,
    public_map_redactable_fields,
    publishable_fields_for_role,
    record_kind_index,
)


CANONICAL_CRASH_FIELDS = tuple(CanonicalCrashRecord.__dataclass_fields__.keys())


class DataGovernanceLookupTests(unittest.TestCase):
    def test_classification_registry_covers_every_canonical_crash_field(self) -> None:
        # Every canonical field other than the internal quality_flags
        # vector should appear in the classification matrix. Missing
        # entries surface as a `KeyError` in `field_classification_for`,
        # but we still want the registry-coverage check at the matrix
        # level so a future field gets caught explicitly.
        registered = {entry.field_name for entry in CANONICAL_CRASH_FIELD_CLASSIFICATIONS}
        # `quality_flags` is internal modeling state, never published.
        expected_registered = set(CANONICAL_CRASH_FIELDS) - {"quality_flags"}
        missing = expected_registered - registered
        self.assertFalse(
            missing,
            f"Canonical crash fields missing from data-governance classification: {sorted(missing)}",
        )

    def test_field_classification_for_returns_expected_entries(self) -> None:
        latitude = field_classification_for("latitude")
        self.assertEqual(latitude.classification, CLASSIFICATION_RESTRICTED)
        self.assertTrue(latitude.publishable_in_aggregate)

        occurred_year = field_classification_for("occurred_year")
        self.assertEqual(occurred_year.classification, CLASSIFICATION_PUBLIC)

        extra = field_classification_for("extra")
        self.assertEqual(extra.classification, CLASSIFICATION_SENSITIVE)
        self.assertFalse(extra.publishable_in_aggregate)

    def test_field_classification_for_raises_on_unknown_field(self) -> None:
        with self.assertRaises(KeyError):
            field_classification_for("not_a_real_field")

    def test_field_classification_index_returns_qualified_keys(self) -> None:
        index = field_classification_index()
        self.assertIn("canonical_crash.latitude", index)
        self.assertEqual(index["canonical_crash.latitude"].classification, CLASSIFICATION_RESTRICTED)

    def test_every_classification_uses_a_known_level(self) -> None:
        for entry in CANONICAL_CRASH_FIELD_CLASSIFICATIONS:
            self.assertIn(entry.classification, CLASSIFICATION_LEVELS)


class SourceLicensingRegisterTests(unittest.TestCase):
    def test_register_includes_known_active_sources(self) -> None:
        index = license_register_index()
        self.assertIn("bari_open_data_crashes", index)
        self.assertIn("osm_road_network", index)
        self.assertIn("bari_signal_phase_provider_data", index)

    def test_bari_open_data_is_cc_by_with_attribution(self) -> None:
        bari = license_register_index()["bari_open_data_crashes"]
        self.assertEqual(bari.license_id, "cc-by-4.0")
        self.assertTrue(bari.attribution_required)
        self.assertIsNotNone(bari.attribution_text)
        self.assertEqual(bari.legal_status, "approved")

    def test_osm_carries_share_alike_obligation(self) -> None:
        osm = license_register_index()["osm_road_network"]
        self.assertEqual(osm.license_id, "odbl-1.0")
        self.assertTrue(osm.share_alike)
        self.assertTrue(osm.attribution_required)

    def test_pending_sources_are_explicitly_pending(self) -> None:
        pending = [s for s in SOURCE_LICENSING_REGISTER if s.legal_status.startswith("pending_")]
        pending_ids = {s.source_family_id for s in pending}
        self.assertEqual(
            pending_ids,
            {
                "motorized_exposure_connector_v1",
                "observed_speed_connector_v1",
                "datex_ii_live_event_feed",
            },
        )

    def test_licenses_by_publication_status_filters_correctly(self) -> None:
        restricted = licenses_by_publication_status(
            "restricted_input_public_summary_only",
            "restricted_input_public_derivatives_only",
        )
        ids = {entry.source_family_id for entry in restricted}
        self.assertIn("motorized_exposure_connector_v1", ids)
        self.assertIn("observed_speed_connector_v1", ids)
        self.assertIn("bari_signal_phase_provider_data", ids)
        self.assertNotIn("osm_road_network", ids)


class RetentionAndPublicMapTests(unittest.TestCase):
    def test_retention_rules_cover_minimum_expected_classes(self) -> None:
        registered = {rule.data_class for rule in RETENTION_RULES}
        for required in (
            "canonical_crash_rows",
            "provider_raw_exports",
            "published_artifacts",
            "audit_logs",
            "ingestion_job_records",
        ):
            self.assertIn(required, registered)

    def test_public_map_policies_define_five_row_floor(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            self.assertGreaterEqual(
                policy.minimum_aggregation_floor,
                5,
                f"Public surface {policy.surface_id} must keep a >=5 aggregation floor",
            )

    def test_public_map_redactable_fields_protect_sensitive_keys(self) -> None:
        # Each PublicMapPolicy is now anchored to one record kind. The
        # union of their redacted_fields therefore lists each policy's
        # record-kind-specific protected fields. Truly sensitive
        # canonical_crash fields (latitude, longitude, fatalities,
        # injuries, occurred_at, source_record_id, extra) remain
        # protected by their `restricted` / `sensitive` matrix entries
        # in CANONICAL_CRASH_FIELD_CLASSIFICATIONS (Issue 01); the
        # public-map policy union now protects the record-kind-specific
        # surfaces (segment_score row-level fields, score-tile
        # ingredients, scenario absolute reductions, etc.).
        redacted = public_map_redactable_fields()
        for sensitive in (
            # segment_score: row-level segment id + raw crash counts
            "segment_id",
            "predicted_crash_count",
            "observed_crash_count",
            # score-tile aggregation ingredients
            "segment_ids",
            "crash_counts",
            "fatalities",
            "injuries",
            "latitude",
            "longitude",
            # scenario absolute reductions + per-asset lineage
            "expected_crash_reduction",
            "expected_crash_reduction_low",
            "expected_crash_reduction_high",
            "baseline_predicted_crash_total",
            "counterfactual_predicted_crash_total",
            "linked_segment_score_ids",
            "affected_assets",
        ):
            self.assertIn(sensitive, redacted)

    def test_public_map_policies_do_not_expose_restricted_classification_fields(self) -> None:
        # Each PublicMapPolicy now declares its `record_kind`, so we
        # cross-check the policy's publishable_fields against the
        # matrix entry under the same record kind (not a hard-coded
        # `canonical_crash` prefix).
        index = field_classification_index()
        for policy in PUBLIC_MAP_POLICIES:
            for field_name in policy.publishable_fields:
                key = f"{policy.record_kind}.{field_name}"
                if key not in index:
                    continue
                classification = index[key].classification
                self.assertNotIn(
                    classification,
                    {CLASSIFICATION_RESTRICTED, CLASSIFICATION_SENSITIVE},
                    f"Public surface {policy.surface_id} ({policy.record_kind}) "
                    f"publishes restricted/sensitive {field_name}",
                )


class DataGovernanceBundleOutputTests(unittest.TestCase):
    def test_build_data_governance_bundle_writes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "governance"
            payload = build_data_governance_bundle(output_dir=output_dir)

            for relative in (
                "data_classification_matrix.csv",
                "source_licensing_register.csv",
                "retention_rules.csv",
                "public_map_policy.csv",
                "data_governance_bundle.json",
                "data_governance_bundle.manifest.json",
                "data_governance_bundle.md",
            ):
                self.assertTrue(
                    (output_dir / relative).is_file(),
                    f"Missing artifact: {relative}",
                )

            self.assertEqual(
                payload["data_governance_bundle_version"], DATA_GOVERNANCE_BUNDLE_VERSION,
            )

            with (output_dir / "data_classification_matrix.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), len(ALL_FIELD_CLASSIFICATIONS))

            manifest = json.loads(
                (output_dir / "data_governance_bundle.manifest.json").read_text(encoding="utf-8"),
            )
            stats = manifest["stats"]
            self.assertEqual(stats["field_classification_count"], len(ALL_FIELD_CLASSIFICATIONS))
            # The per-record-kind rollup must cover every registered kind.
            by_kind = stats["field_classification_by_record_kind"]
            self.assertEqual(
                set(by_kind.keys()), set(RECORD_KIND_CLASSIFICATIONS.keys()),
            )
            self.assertEqual(stats["source_license_count"], len(SOURCE_LICENSING_REGISTER))
            self.assertEqual(stats["retention_rule_count"], len(RETENTION_RULES))
            self.assertEqual(stats["public_map_policy_count"], len(PUBLIC_MAP_POLICIES))

    def test_bundle_includes_class_rollups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = build_data_governance_bundle(output_dir=Path(temp_dir))
        by_class = payload["stats"]["field_classification_by_class"]
        # Every level used in the registry must show up in the rollup.
        used_levels = {entry.classification for entry in ALL_FIELD_CLASSIFICATIONS}
        self.assertEqual(set(by_class.keys()), used_levels)


class ExtendedRecordKindTests(unittest.TestCase):
    def test_segment_score_classifications_band_and_index_are_public(self) -> None:
        # The banded / indexed scores are the platform's public surface;
        # they MUST stay publishable for the public role.
        for field_name in ("public_score_band", "public_score_index", "score_decile"):
            entry = field_classification_for(field_name, record_kind="segment_score")
            self.assertEqual(entry.classification, CLASSIFICATION_PUBLIC)
            self.assertIn("public", entry.role_visibility)

    def test_segment_score_observed_counts_are_restricted(self) -> None:
        observed = field_classification_for("observed_crash_count", record_kind="segment_score")
        self.assertEqual(observed.classification, CLASSIFICATION_RESTRICTED)
        self.assertNotIn("public", observed.role_visibility)
        self.assertIn("analyst", observed.role_visibility)

    def test_node_year_metric_crash_counts_are_restricted(self) -> None:
        for field_name in ("crash_count", "injury_crash_count", "fatal_crash_count"):
            entry = field_classification_for(field_name, record_kind="node_year_metric")
            self.assertEqual(entry.classification, CLASSIFICATION_RESTRICTED)
            self.assertNotIn("public", entry.role_visibility)

    def test_scenario_relative_reduction_is_public_but_asset_list_is_internal(self) -> None:
        rel = field_classification_for("expected_relative_reduction", record_kind="scenario")
        self.assertEqual(rel.classification, CLASSIFICATION_PUBLIC)
        assets = field_classification_for("affected_assets", record_kind="scenario")
        self.assertEqual(assets.classification, CLASSIFICATION_INTERNAL)
        self.assertNotIn("public", assets.role_visibility)

    def test_report_file_storage_uri_is_restricted_to_admin_and_data_operator(self) -> None:
        uri = field_classification_for("file_storage_uri", record_kind="report")
        self.assertEqual(uri.classification, CLASSIFICATION_RESTRICTED)
        self.assertEqual(set(uri.role_visibility), {"data_operator", "admin"})

    def test_classifications_for_record_kind_returns_correct_matrix(self) -> None:
        self.assertEqual(
            classifications_for_record_kind("segment_score"),
            SEGMENT_SCORE_FIELD_CLASSIFICATIONS,
        )
        self.assertEqual(
            classifications_for_record_kind("node_year_metric"),
            NODE_YEAR_METRIC_FIELD_CLASSIFICATIONS,
        )
        self.assertEqual(
            classifications_for_record_kind("scenario"),
            SCENARIO_FIELD_CLASSIFICATIONS,
        )
        self.assertEqual(
            classifications_for_record_kind("report"),
            REPORT_FIELD_CLASSIFICATIONS,
        )

    def test_classifications_for_unknown_kind_raises(self) -> None:
        with self.assertRaises(KeyError):
            classifications_for_record_kind("not_a_record_kind")
        with self.assertRaises(KeyError):
            field_classification_for("anything", record_kind="not_a_record_kind")

    def test_is_field_publishable_for_role_respects_visibility_list(self) -> None:
        self.assertTrue(
            is_field_publishable_for_role(
                "public_score_band", record_kind="segment_score", role="public",
            )
        )
        self.assertFalse(
            is_field_publishable_for_role(
                "observed_crash_count", record_kind="segment_score", role="public",
            )
        )
        self.assertTrue(
            is_field_publishable_for_role(
                "observed_crash_count", record_kind="segment_score", role="analyst",
            )
        )
        with self.assertRaises(KeyError):
            is_field_publishable_for_role(
                "missing", record_kind="segment_score", role="public",
            )

    def test_publishable_fields_for_role_filters_correctly(self) -> None:
        public_segment_fields = set(
            publishable_fields_for_role("segment_score", "public"),
        )
        self.assertIn("public_score_band", public_segment_fields)
        self.assertIn("public_score_index", public_segment_fields)
        self.assertNotIn("observed_crash_count", public_segment_fields)
        self.assertNotIn("segment_id", public_segment_fields)
        # The analyst role gets everything the public role gets, plus the
        # restricted fields that they are explicitly authorized for.
        analyst_segment_fields = set(
            publishable_fields_for_role("segment_score", "analyst"),
        )
        self.assertTrue(public_segment_fields.issubset(analyst_segment_fields))
        self.assertIn("observed_crash_count", analyst_segment_fields)
        self.assertIn("predicted_crash_count", analyst_segment_fields)

    def test_record_kind_index_is_nested_by_kind_then_field_name(self) -> None:
        index = record_kind_index()
        self.assertIn("segment_score", index)
        self.assertIn("public_score_band", index["segment_score"])
        self.assertEqual(
            index["segment_score"]["public_score_band"].classification,
            CLASSIFICATION_PUBLIC,
        )

    def test_field_classification_index_spans_all_record_kinds(self) -> None:
        index = field_classification_index()
        for record_kind in RECORD_KIND_CLASSIFICATIONS.keys():
            # At least one entry of each kind must show up in the flat index.
            self.assertTrue(
                any(key.startswith(f"{record_kind}.") for key in index.keys()),
                f"No flat-index entries for record_kind '{record_kind}'",
            )

    def test_all_record_kind_classifications_use_known_levels(self) -> None:
        for record_kind, entries in RECORD_KIND_CLASSIFICATIONS.items():
            for entry in entries:
                self.assertIn(
                    entry.classification, CLASSIFICATION_LEVELS,
                    f"Unknown classification in {record_kind}.{entry.field_name}",
                )
                # Every entry must keep its record_kind aligned with the
                # registry key it lives under.
                self.assertEqual(entry.record_kind, record_kind)


class PublicMapPolicyRecordKindTests(unittest.TestCase):
    """Cross-policy invariants between PUBLIC_MAP_POLICIES and the matrix.

    Each PublicMapPolicy now declares a `record_kind` discriminator.
    For policies whose `record_kind` is registered in the matrix
    (`is_matrix_tracked == True`), these tests verify that:

    - every publishable_fields entry that IS in the matrix is
      classified `public` (i.e. has 'public' in role_visibility)
    - every redacted_fields entry that IS in the matrix is NOT
      classified `public` (i.e. does not have 'public' in
      role_visibility)
    - publishable_fields and redacted_fields are disjoint

    Policies that mention auxiliary fields not in the matrix (e.g.
    geometry, identifier hashes) are allowed to do so - the
    cross-policy check only fires for matrix-known fields.
    """

    def test_every_policy_declares_a_record_kind(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            self.assertTrue(
                policy.record_kind,
                f"Policy {policy.surface_id} is missing its record_kind discriminator",
            )

    def test_known_record_kinds_are_classification_registered(self) -> None:
        # The current policies declare `segment_score`, `score_tile`,
        # and `scenario`. The first and third must be in the matrix;
        # `score_tile` is intentionally unregistered (no canonical
        # tile-record schema yet) and is documented to bypass the
        # matrix cross-check.
        kinds = {policy.record_kind for policy in PUBLIC_MAP_POLICIES}
        self.assertIn("segment_score", kinds)
        self.assertIn("scenario", kinds)

    def test_matrix_tracked_policies_publish_only_public_matrix_fields(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            if not policy.is_matrix_tracked:
                continue
            matrix_index = {
                entry.field_name: entry
                for entry in classifications_for_record_kind(policy.record_kind)
            }
            for field_name in policy.publishable_fields:
                if field_name not in matrix_index:
                    # auxiliary fields (geometry, identifier hashes)
                    # are allowed
                    continue
                entry = matrix_index[field_name]
                self.assertIn(
                    "public", entry.role_visibility,
                    f"Policy {policy.surface_id} publishes {field_name} but the "
                    f"{policy.record_kind} matrix says role_visibility={entry.role_visibility}",
                )

    def test_matrix_tracked_policies_redact_only_non_public_matrix_fields(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            if not policy.is_matrix_tracked:
                continue
            matrix_index = {
                entry.field_name: entry
                for entry in classifications_for_record_kind(policy.record_kind)
            }
            for field_name in policy.redacted_fields:
                if field_name not in matrix_index:
                    continue
                entry = matrix_index[field_name]
                self.assertNotIn(
                    "public", entry.role_visibility,
                    f"Policy {policy.surface_id} redacts {field_name} but the "
                    f"{policy.record_kind} matrix marks it as 'public' "
                    f"(role_visibility={entry.role_visibility})",
                )

    def test_publishable_and_redacted_fields_are_disjoint(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            overlap = set(policy.publishable_fields) & set(policy.redacted_fields)
            self.assertFalse(
                overlap,
                f"Policy {policy.surface_id} has fields in both publishable "
                f"and redacted: {sorted(overlap)}",
            )

    def test_is_matrix_tracked_matches_record_kind_registration(self) -> None:
        for policy in PUBLIC_MAP_POLICIES:
            expected = policy.record_kind in RECORD_KIND_CLASSIFICATIONS
            self.assertEqual(
                policy.is_matrix_tracked, expected,
                f"Policy {policy.surface_id}.is_matrix_tracked is out of sync "
                f"with RECORD_KIND_CLASSIFICATIONS",
            )

    def test_bundle_carries_record_kind_per_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "governance"
            payload = build_data_governance_bundle(output_dir=output_dir)
        for row in payload["public_map_policies"]:
            self.assertIn("record_kind", row)
            self.assertTrue(row["record_kind"])


class ArtifactConstantSubsetTests(unittest.TestCase):
    """Cross-policy invariants between artifact-generator constants and the matrix.

    The artifact generators in `road_risk_modeling.prediction_store`
    and `road_risk_modeling.public_score_tiles` declare their own
    `PUBLIC_*_FIELDS` lists that get baked into each manifest's
    `contract.public_fields`. These tests pin the constants as a
    matrix-controlled subset so the manifests cannot drift behind the
    classification matrix (an earlier drift had `segment_id` listed in
    PUBLIC_SCORE_FIELDS while the matrix marked it `internal`).
    """

    def test_public_score_fields_are_subset_of_segment_score_public_matrix(self) -> None:
        # Lazy import to avoid hard-coupling to the prediction_store
        # module if it gains a future heavier import set.
        from road_risk_modeling.prediction_store import PUBLIC_SCORE_FIELDS

        public_matrix = set(publishable_fields_for_role("segment_score", "public"))
        leaks = set(PUBLIC_SCORE_FIELDS) - public_matrix
        self.assertFalse(
            leaks,
            f"PUBLIC_SCORE_FIELDS contains fields not marked 'public' in the "
            f"segment_score matrix: {sorted(leaks)}",
        )

    def test_public_tile_fields_are_subset_of_score_tile_public_matrix(self) -> None:
        from road_risk_modeling.public_score_tiles import PUBLIC_TILE_FIELDS

        public_matrix = set(publishable_fields_for_role("score_tile", "public"))
        leaks = set(PUBLIC_TILE_FIELDS) - public_matrix
        self.assertFalse(
            leaks,
            f"PUBLIC_TILE_FIELDS contains fields not marked 'public' in the "
            f"score_tile matrix: {sorted(leaks)}",
        )

    def test_public_score_fields_carry_the_synthetic_id_not_the_raw_segment_id(self) -> None:
        # This is the canonical drift we fixed in this commit. Pin it.
        from road_risk_modeling.prediction_store import PUBLIC_SCORE_FIELDS

        self.assertIn("segment_score_id", PUBLIC_SCORE_FIELDS)
        self.assertNotIn(
            "segment_id", PUBLIC_SCORE_FIELDS,
            "Raw `segment_id` must not appear in PUBLIC_SCORE_FIELDS; "
            "the synthetic `segment_score_id` is the public surface and "
            "the matrix classifies `segment_id` as `internal`.",
        )

    def test_analyst_core_fields_are_subset_of_segment_score_analyst_matrix(self) -> None:
        from road_risk_modeling.prediction_store import ANALYST_CORE_FIELDS

        analyst_matrix = set(publishable_fields_for_role("segment_score", "analyst"))
        leaks = set(ANALYST_CORE_FIELDS) - analyst_matrix
        self.assertFalse(
            leaks,
            f"ANALYST_CORE_FIELDS contains fields not marked analyst-visible in the "
            f"segment_score matrix: {sorted(leaks)}",
        )

    def test_analyst_core_fields_carry_the_internal_csv_metadata(self) -> None:
        # Pin the three internal-CSV metadata fields added to the
        # matrix alongside this commit: prediction_column,
        # score_percentile, score_rank_desc. They are analyst-only and
        # never published.
        from road_risk_modeling.prediction_store import ANALYST_CORE_FIELDS

        for field_name in ("prediction_column", "score_percentile", "score_rank_desc"):
            entry = field_classification_for(field_name, record_kind="segment_score")
            self.assertEqual(entry.classification, CLASSIFICATION_INTERNAL)
            self.assertNotIn("public", entry.role_visibility)
            self.assertIn("analyst", entry.role_visibility)
            self.assertIn(field_name, ANALYST_CORE_FIELDS)

    def test_scenario_rank_is_internal_analyst_visible(self) -> None:
        # `scenario_rank` is emitted by `_scenario_summary_row` but was
        # previously not classified in the matrix. Pin its post-fix
        # classification so a future engineer can't quietly promote
        # ranking metadata to public without updating this test.
        entry = field_classification_for("scenario_rank", record_kind="scenario")
        self.assertEqual(entry.classification, CLASSIFICATION_INTERNAL)
        self.assertNotIn("public", entry.role_visibility)
        self.assertIn("analyst", entry.role_visibility)

    def test_report_matrix_classifies_every_serialize_report_field(self) -> None:
        # `_full_report_record` in `apps.api.services.reporting_hub`
        # emits this fixed set of fields; the matrix must classify every
        # one so the matrix filter never strips a field the artifact
        # emits. Mirror of the scenario-summary-row subset invariant.
        report_record_fields = {
            "report_id",
            "organization_id",
            "title",
            "report_type",
            "status",
            "visibility_tier",
            "output_format",
            "city_key",
            "audience",
            "summary",
            "review_state",
            "publication_state",
            "download_state",
            "lifecycle_actions",
            "file_storage_uri",
            "created_at",
            "generated_at",
            "published_at",
        }
        from road_risk_modeling.data_governance import REPORT_FIELD_CLASSIFICATIONS
        matrix_fields = {entry.field_name for entry in REPORT_FIELD_CLASSIFICATIONS}
        missing = report_record_fields - matrix_fields
        self.assertFalse(
            missing,
            f"reporting_hub._full_report_record emits fields not in the "
            f"report matrix: {sorted(missing)}",
        )

    def test_report_file_storage_uri_remains_restricted_to_data_operator_admin(self) -> None:
        # Pin the file_storage_uri restriction explicitly so a future
        # engineer can't quietly add `analyst` to its role_visibility
        # without updating this test - that would surface raw S3 URIs
        # to the org-history listing.
        entry = field_classification_for("file_storage_uri", record_kind="report")
        self.assertEqual(entry.classification, CLASSIFICATION_RESTRICTED)
        self.assertEqual(set(entry.role_visibility), {"data_operator", "admin"})

    def test_report_public_listing_does_not_leak_organization_id(self) -> None:
        # Pin the privacy invariant introduced alongside the report
        # matrix wiring: `organization_id` is INTERNAL with
        # municipality_viewer/analyst/data_operator/admin visibility -
        # NOT public. The public listing must not surface org-scope ids.
        public_report_fields = set(publishable_fields_for_role("report", "public"))
        self.assertNotIn(
            "organization_id", public_report_fields,
            "organization_id must stay out of the public report listing; "
            "the listing is scoped by city, not by org.",
        )
        self.assertNotIn("file_storage_uri", public_report_fields)
        self.assertNotIn("lifecycle_actions", public_report_fields)
        self.assertNotIn("audience", public_report_fields)
        self.assertNotIn("summary", public_report_fields)
        self.assertNotIn("review_state", public_report_fields)
        self.assertNotIn("created_at", public_report_fields)

    def test_scenario_summary_row_fields_are_subset_of_scenario_analyst_matrix(self) -> None:
        # The fields emitted by the scenario-planner summary row must
        # all be analyst-visible in the matrix; otherwise the matrix
        # filter would silently strip a field the artifact emitted.
        # Mirror of `test_analyst_core_fields_are_subset_of_segment_score_analyst_matrix`
        # for the scenario record kind.
        scenario_summary_fields = {
            "scenario_id",
            "scenario_rank",
            "intervention_code",
            "title",
            "target_context_label",
            "target_context_key",
            "linked_segment_count",
            "target_asset_count",
            "target_asset_types",
            "expected_crash_reduction",
            "expected_crash_reduction_low",
            "expected_crash_reduction_high",
            "expected_relative_reduction",
            "baseline_predicted_crash_total",
            "counterfactual_predicted_crash_total",
        }
        analyst_matrix = set(publishable_fields_for_role("scenario", "analyst"))
        leaks = scenario_summary_fields - analyst_matrix
        self.assertFalse(
            leaks,
            f"scenario_planner._scenario_summary_row emits fields not marked "
            f"analyst-visible in the scenario matrix: {sorted(leaks)}",
        )


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
