from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.db.base import Base  # noqa: E402
from apps.api.db.models import (  # noqa: E402
    ArtifactReference,
    AuditLog,
    DataSource,
    IngestionJob,
    Intervention,
    Report,
    User,
)
from apps.api.db.repositories import (  # noqa: E402
    attach_ingestion_job_storage,
    attach_report_storage,
    create_artifact_reference,
    create_data_source,
    create_ingestion_job,
    create_intervention,
    create_report,
    mark_ingestion_job_finished,
    mark_ingestion_job_running,
    mark_report_generated,
    record_audit_log,
    update_user_profile,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self.scalar_result: object | None = None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1

    def scalar(self, statement: object) -> object | None:  # noqa: ARG002
        return self.scalar_result


class ApiDbSchemaTests(unittest.TestCase):
    def test_metadata_includes_operational_metadata_tables(self) -> None:
        expected = {
            "organizations",
            "users",
            "municipalities",
            "organization_memberships",
            "organization_municipalities",
            "data_sources",
            "ingestion_jobs",
            "audit_logs",
            "reports",
            "artifact_references",
            "model_runs",
            "crash_records",
            "road_segments",
            "road_nodes",
            "crossings",
            "movement_objects",
            "risk_scores",
            "public_risk_tiles",
            "scenario_runs",
            "interventions",
        }
        self.assertTrue(expected.issubset(set(Base.metadata.tables)))

        user_columns = Base.metadata.tables["users"].c
        self.assertIn("locale", user_columns)
        self.assertIn("timezone_name", user_columns)
        self.assertIn("preferred_organization_id", user_columns)
        self.assertIn("preferred_municipality_id", user_columns)
        self.assertIn("profile_json", user_columns)

        data_source_columns = Base.metadata.tables["data_sources"].c
        self.assertIn("organization_id", data_source_columns)
        self.assertIn("configuration_json", data_source_columns)
        self.assertEqual(data_source_columns["configuration_json"].type.__class__.__name__, "JSONB")

        ingestion_job_columns = Base.metadata.tables["ingestion_jobs"].c
        self.assertIn("job_type", ingestion_job_columns)
        self.assertIn("job_stats_json", ingestion_job_columns)

        audit_log_columns = Base.metadata.tables["audit_logs"].c
        self.assertIn("action", audit_log_columns)
        self.assertIn("metadata_json", audit_log_columns)

        report_columns = Base.metadata.tables["reports"].c
        self.assertIn("report_type", report_columns)
        self.assertIn("summary_json", report_columns)
        self.assertIn("file_storage_uri", report_columns)

        artifact_columns = Base.metadata.tables["artifact_references"].c
        self.assertIn("storage_uri", artifact_columns)
        self.assertIn("lineage_json", artifact_columns)

        model_run_columns = Base.metadata.tables["model_runs"].c
        self.assertIn("external_run_id", model_run_columns)
        self.assertIn("metrics_json", model_run_columns)
        self.assertIn("lineage_json", model_run_columns)

        segment_columns = Base.metadata.tables["road_segments"].c
        self.assertIn("segment_external_id", segment_columns)
        self.assertEqual(segment_columns["geom"].type.get_col_spec(), "geometry(LINESTRING,4326)")

        node_columns = Base.metadata.tables["road_nodes"].c
        self.assertEqual(node_columns["geom"].type.get_col_spec(), "geometry(POINT,4326)")

        crossing_columns = Base.metadata.tables["crossings"].c
        self.assertIn("protection_type", crossing_columns)

        score_columns = Base.metadata.tables["risk_scores"].c
        self.assertIn("model_run_id", score_columns)
        self.assertIn("score_band", score_columns)

        tile_columns = Base.metadata.tables["public_risk_tiles"].c
        self.assertEqual(tile_columns["geom"].type.get_col_spec(), "geometry(POLYGON,4326)")

        intervention_columns = Base.metadata.tables["interventions"].c
        self.assertIn("source_kind", intervention_columns)
        self.assertIn("owner_subject", intervention_columns)
        self.assertIn("planned_completion_date", intervention_columns)
        self.assertIn("completed_at", intervention_columns)
        self.assertIn("notes", intervention_columns)

    def test_repository_helpers_materialize_profiles_sources_jobs_reports_audit_logs_and_artifacts(self) -> None:
        session = FakeSession()

        user = User(external_subject="demo.user", email="demo@example.test", display_name="Demo User")
        update_user_profile(
            session,
            user,
            locale="it-IT",
            timezone_name="Europe/Rome",
            preferred_organization_id="org-1",
            preferred_municipality_id="mun-1",
            profile={"team": "road-safety"},
        )
        self.assertEqual(user.locale, "it-IT")
        self.assertEqual(user.timezone_name, "Europe/Rome")
        self.assertEqual(user.profile_json, {"team": "road-safety"})

        source = create_data_source(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            refresh_frequency="weekly",
            configuration={"delimiter": ";"},
        )
        self.assertIsInstance(source, DataSource)
        self.assertEqual(source.name, "Bari crash feed")
        self.assertEqual(source.configuration_json, {"delimiter": ";"})

        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            submitted_by_user_id="user-1",
            job_type="crash_ingestion",
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={"dry_run": False},
        )
        self.assertIsInstance(job, IngestionJob)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.parameters_json, {"dry_run": False})

        mark_ingestion_job_running(session, job)
        self.assertEqual(job.status, "running")
        self.assertIsNotNone(job.started_at)

        attach_ingestion_job_storage(
            session,
            job,
            manifest_storage_uri="s3://road-risk/manifests/pending-ingestion.json",
            parameters={"storage_contract_version": "artifact_storage_contract_v1"},
        )
        self.assertEqual(
            job.manifest_storage_uri,
            "s3://road-risk/manifests/pending-ingestion.json",
        )
        self.assertEqual(job.parameters_json["storage_contract_version"], "artifact_storage_contract_v1")

        mark_ingestion_job_finished(
            session,
            job,
            manifest_storage_uri="s3://road-risk/manifests/ingestion.json",
            error_storage_uri="s3://road-risk/errors/ingestion.csv",
            job_stats={"accepted_rows": 42, "rejected_rows": 3},
        )
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.job_stats_json["accepted_rows"], 42)
        self.assertIsNotNone(job.finished_at)

        log = record_audit_log(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            user_id="user-1",
            action="publish_artifact",
            target_type="artifact_reference",
            target_id="artifact-1",
            metadata={"publication_tier": "public"},
        )
        self.assertIsInstance(log, AuditLog)
        self.assertEqual(log.metadata_json, {"publication_tier": "public"})

        report = create_report(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            generated_by_user_id="user-1",
            report_type="monthly_safety_overview",
            title="Bari monthly overview",
            visibility_tier="internal",
            summary={"status": "seeded"},
        )
        self.assertIsInstance(report, Report)
        self.assertEqual(report.summary_json, {"status": "seeded"})

        attach_report_storage(
            session,
            report,
            file_storage_uri="s3://road-risk/reports/bari-monthly-overview.pending.pdf",
            status="pending_upload",
            parameters={"storage_contract_version": "artifact_storage_contract_v1"},
        )
        self.assertEqual(report.status, "pending_upload")
        self.assertEqual(
            report.parameters_json["storage_contract_version"],
            "artifact_storage_contract_v1",
        )

        mark_report_generated(
            session,
            report,
            file_storage_uri="s3://road-risk/reports/bari-monthly-overview.pdf",
            summary={"status": "generated"},
        )
        self.assertEqual(report.status, "generated")
        self.assertEqual(report.file_storage_uri, "s3://road-risk/reports/bari-monthly-overview.pdf")
        self.assertEqual(report.summary_json, {"status": "generated"})
        self.assertIsNotNone(report.generated_at)

        artifact = create_artifact_reference(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            ingestion_job_id="job-1",
            created_by_user_id="user-1",
            artifact_kind="published_resource_index",
            artifact_name="bari published index",
            storage_uri="s3://road-risk/artifacts/published_resources.json",
            publication_tier="internal",
            lineage={"run_label": "demo_run"},
        )
        self.assertIsInstance(artifact, ArtifactReference)
        self.assertEqual(artifact.lineage_json, {"run_label": "demo_run"})
        session.scalar_result = artifact
        updated_artifact = create_artifact_reference(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            ingestion_job_id="job-2",
            created_by_user_id="user-1",
            artifact_kind="published_resource_index",
            artifact_name="bari published index refreshed",
            storage_uri="s3://road-risk/artifacts/published_resources.json",
            publication_tier="internal",
            lineage={"run_label": "second_run"},
        )
        self.assertIs(updated_artifact, artifact)
        self.assertEqual(updated_artifact.ingestion_job_id, "job-2")
        self.assertEqual(updated_artifact.artifact_name, "bari published index refreshed")
        self.assertEqual(updated_artifact.lineage_json, {"run_label": "second_run"})

        intervention = create_intervention(
            session,
            organization_id="org-1",
            target_object_type="corridor",
            target_object_id="bari:tangenziale",
            intervention_type="speed_management",
            cost_class="medium",
            expected_benefit=7.0,
            priority_score=3.5,
            status="planned",
            owner_subject="analyst-1",
            notes="Ready for engineering review.",
            properties={"city_key": "bari"},
        )
        self.assertIsInstance(intervention, Intervention)
        self.assertEqual(intervention.status, "planned")
        self.assertEqual(intervention.owner_subject, "analyst-1")
        self.assertEqual(intervention.properties_json["city_key"], "bari")

        self.assertEqual(len(session.added), 6)
        self.assertEqual(session.flush_count, 13)

    def test_migration_docs_include_upgrade_and_reset_workflow(self) -> None:
        alembic_readme = (
            REPO_ROOT / "apps" / "api" / "alembic" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn("alembic -c alembic.ini upgrade head", alembic_readme)
        self.assertIn("dropdb --if-exists road_risk", alembic_readme)

    def test_postgis_domain_migration_defines_spatial_indexes(self) -> None:
        migration = (
            REPO_ROOT
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "9f2b6a1c4d8e_postgis_product_domain_tables.py"
        ).read_text(encoding="utf-8")
        self.assertIn("road_segments", migration)
        self.assertIn("risk_scores", migration)
        self.assertIn("public_risk_tiles", migration)
        self.assertIn('postgresql_using="gist"', migration)
