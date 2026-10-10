from __future__ import annotations

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.services.operational_metadata import (  # noqa: E402
    build_local_development_seed_plan,
    build_organization_operational_snapshot,
    seed_local_development_fixture,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def scalar(self, statement: object) -> object | None:
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1


class ApiOperationalMetadataTests(unittest.TestCase):
    def test_build_local_development_seed_plan_includes_reports_and_seed_fixture(self) -> None:
        plan = build_local_development_seed_plan()
        self.assertEqual(plan["organization"]["slug"], "demo-bari")
        self.assertEqual(plan["user"]["locale"], "it-IT")
        self.assertEqual(plan["report"]["report_type"], "monthly_safety_overview")
        self.assertEqual(len(plan["data_sources"]), 2)
        self.assertTrue(plan["audit_log"]["metadata"]["seed_fixture"])

    def test_seed_local_development_fixture_materializes_operational_entities(self) -> None:
        session = FakeSession()
        result = seed_local_development_fixture(session)

        self.assertEqual(result["organization"].slug, "demo-bari")
        self.assertEqual(result["municipality"].slug, "bari-demo")
        self.assertEqual(result["user"].locale, "it-IT")
        self.assertEqual(result["user"].preferred_organization_id, result["organization"].id)
        self.assertEqual(result["membership"].role, "analyst")
        self.assertEqual(result["municipality_link"].access_level, "restricted")
        self.assertEqual(len(result["data_sources"]), 2)
        self.assertEqual(result["report"].report_type, "monthly_safety_overview")
        self.assertEqual(result["audit_log"].action, "seed_fixture_initialized")
        self.assertEqual(len(session.added), 9)
        self.assertEqual(session.flush_count, 10)

    def test_build_organization_operational_snapshot_separates_operational_metadata_from_artifacts(self) -> None:
        memberships = [SimpleNamespace(user_id="user-1", role="analyst", status="active")]
        municipality_links = [SimpleNamespace(municipality_id="bari", access_level="restricted", status="active")]
        data_sources = [SimpleNamespace(name="Bari crash feed", source_type="crash_feed", publication_tier="internal")]
        ingestion_jobs = [SimpleNamespace(job_type="crash_ingestion", status="completed")]
        reports = [SimpleNamespace(title="Monthly overview", report_type="monthly_safety_overview", status="generated")]
        audit_logs = [SimpleNamespace(action="publish_report", target_type="report", status="recorded")]
        artifacts = [
            SimpleNamespace(
                artifact_kind="published_resource_index",
                artifact_name="published resources",
                storage_uri="s3://road-risk/artifacts/published_resources.json",
                publication_tier="internal",
            )
        ]

        with (
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_memberships_for_organization",
                return_value=memberships,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_municipality_links_for_organization",
                return_value=municipality_links,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_data_sources_for_organization",
                return_value=data_sources,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_ingestion_jobs_for_organization",
                return_value=ingestion_jobs,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_reports_for_organization",
                return_value=reports,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_audit_logs_for_organization",
                return_value=audit_logs,
            ),
            mock.patch(
                "apps.api.services.operational_metadata.repositories.list_artifact_references_for_organization",
                return_value=artifacts,
            ),
        ):
            snapshot = build_organization_operational_snapshot(object(), "org-bari")

        self.assertEqual(snapshot["organization_id"], "org-bari")
        self.assertEqual(snapshot["operational_metadata"]["report_count"], 1)
        self.assertEqual(snapshot["operational_metadata"]["reports"][0]["title"], "Monthly overview")
        self.assertEqual(snapshot["analytics_artifact_references"][0]["artifact_kind"], "published_resource_index")
        self.assertEqual(snapshot["operational_metadata"]["data_source_count"], 1)
