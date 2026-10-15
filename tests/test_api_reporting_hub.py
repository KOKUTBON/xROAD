"""Tests for the reporting and executive-dashboard product surface (#95)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.auth import (  # noqa: E402
    AuthContext,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_MUNICIPALITY_VIEWER,
    get_auth_context,
)
from apps.api.db.session import get_db_session  # noqa: E402
from apps.api.main import create_app  # noqa: E402
from apps.api.services import reporting_hub  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _scaffold_reporting_root(root: Path) -> ApiSettings:
    segment_geojson = root / "data" / "prediction_store" / "demo_bari_frequency" / "segment_scores_public.geojson"
    analyst_csv = root / "data" / "prediction_store" / "demo_bari_frequency" / "segment_scores_analyst.csv"
    tile_geojson = root / "data" / "prediction_store" / "demo_bari_frequency_tiles_500m" / "score_tiles_public.geojson"
    dashboard_summary = root / "data" / "dashboard" / "dashboard_summary.json"
    intervention_brief = root / "data" / "intervention_briefs" / "demo_bari_frequency" / "intervention_brief.json"

    _write_json(
        segment_geojson,
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[16.86, 41.11], [16.87, 41.12]]},
                    "properties": {"segment_label": "Tangenziale di Bari", "public_score_index": 100},
                }
            ],
        },
    )
    _write_csv(
        analyst_csv,
        [
            {
                "segment_label": "Tangenziale di Bari",
                "predicted_crash_count": 19.70,
                "public_score_index": 100.0,
                "observed_crash_count": 76.0,
            }
        ],
    )
    _write_json(
        tile_geojson,
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[16.85, 41.10], [16.86, 41.10], [16.86, 41.11], [16.85, 41.11], [16.85, 41.10]]],
                    },
                    "properties": {"tile_public_score_band": "very_high", "tile_max_public_score_index": 100.0},
                }
            ],
        },
    )
    _write_json(
        dashboard_summary,
        {
            "generated_at_utc": "2026-05-15T00:00:00+00:00",
            "stats": {"published_run_count": 1},
            "published_runs": [
                {
                    "city_key": "bari",
                    "display_name": "Bari",
                    "occurred_years": [2021],
                    "prediction_run_label": "demo_bari_frequency",
                    "prediction_task": "segment_frequency_baseline",
                    "segment_scores": {
                        "public_segments_path": str(segment_geojson.relative_to(root)),
                        "predicted_crash_total": 42.17,
                        "observed_crash_total": 1415.0,
                        "segment_score_rows": 13769,
                        "lineage_trace": {
                            "direct_publishable_outputs": [
                                {
                                    "path": str(segment_geojson.relative_to(root)),
                                    "role": "segment_scores_public_geojson",
                                },
                                {
                                    "path": str(analyst_csv.relative_to(root)),
                                    "role": "segment_scores_analyst_csv",
                                },
                            ]
                        },
                    },
                    "score_tiles": {
                        "tiles_very_high": 196,
                        "tile_rows": 614,
                        "lineage_trace": {
                            "direct_publishable_outputs": [
                                {
                                    "path": str(tile_geojson.relative_to(root)),
                                    "role": "score_tiles_public_geojson",
                                }
                            ]
                        },
                    },
                }
            ],
        },
    )
    _write_json(
        intervention_brief,
        {
            "city_key": "bari",
            "display_name": "Bari",
            "prediction_run_label": "demo_bari_frequency",
            "overview": {
                "predicted_crash_total": 42.17,
                "observed_crash_total": 1415.0,
                "tiles_very_high": 196,
            },
            "recommended_actions": [
                {
                    "priority": "1",
                    "title": "Reduce operating speeds on Tangenziale di Bari",
                    "rationale": "Highest crash burden corridor in the current shortlist.",
                    "code": "speed_management",
                }
            ],
            "shortlist": {
                "top_corridors": [
                    {
                        "corridor_label": "Tangenziale di Bari",
                        "predicted_crash_total": 19.70,
                        "max_public_score_index": 100.0,
                        "segment_count": 8,
                        "top_segments": [{"segment_label": "Tangenziale di Bari"}],
                    }
                ],
                "hotspot_tiles": [],
            },
            "scenario_countermeasures": {
                "recommended_summary": {
                    "recommended_portfolio": {
                        "title": "Speed + cycling + signal timing package",
                        "expected_crash_reduction": 30.84,
                        "expected_relative_reduction": 0.73,
                    },
                    "recommended_scenario": {
                        "title": "Reduce operating speeds on Tangenziale di Bari",
                        "expected_crash_reduction": 10.96,
                    },
                }
            },
            "transferability": {
                "cold_start_gap_vs_temporal": 0.097,
                "history_free_gap_vs_temporal": 0.082,
            },
        },
    )
    return ApiSettings(root_dir=root)


class ReportingHubServiceTests(unittest.TestCase):
    def test_build_reporting_overview_returns_executive_bundle_and_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            with mock.patch(
                "apps.api.services.reporting_hub.repositories.list_reports_for_organization",
                return_value=[],
            ):
                payload = reporting_hub.build_reporting_overview(
                    object(),
                    settings,
                    organization_id="org-1",
                    city_key="bari",
                )

        self.assertEqual(payload["contract_version"], reporting_hub.REPORTING_OVERVIEW_CONTRACT_VERSION)
        self.assertEqual(payload["selected_city_key"], "bari")
        self.assertEqual(payload["executive_overview"]["kpis"]["very_high_risk_tiles"], 196)
        self.assertEqual(payload["executive_overview"]["kpis"]["model_confidence"], "medium")
        self.assertEqual(len(payload["report_templates"]), 5)
        self.assertIn(
            "public_transparency",
            {template["report_type"] for template in payload["report_templates"]},
        )

    def test_execute_report_generation_persists_markdown_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            report = SimpleNamespace(
                id="report-1",
                organization_id="org-1",
                report_type="executive_overview",
                title="Bari Executive Safety Overview",
                output_format="md",
                visibility_tier="restricted",
                parameters_json={"city_key": "bari"},
                summary_json={},
                status="queued",
                file_storage_uri=None,
                created_at=None,
                generated_at=None,
            )
            captured: dict[str, object] = {}

            def _persist_generated_artifact(*args, **kwargs):  # noqa: ARG001
                captured.update(kwargs)
                report.status = "generated"
                report.file_storage_uri = "s3://road-risk/reports/bari.md"
                return {
                    "access": SimpleNamespace(
                        as_dict=lambda: {  # noqa: ARG005
                            "download_url": "https://signed.example/report-md",
                            "storage_uri": report.file_storage_uri,
                        }
                    )
                }

            with (
                mock.patch(
                    "apps.api.services.reporting_hub.artifact_storage.persist_generated_artifact",
                    side_effect=_persist_generated_artifact,
                ),
                mock.patch(
                    "apps.api.services.reporting_hub.repositories.record_audit_log",
                    return_value=None,
                ),
            ):
                payload = reporting_hub.execute_report_generation(object(), settings, report)

        self.assertEqual(payload["contract_version"], reporting_hub.REPORT_GENERATION_CONTRACT_VERSION)
        self.assertEqual(payload["report"]["status"], "generated")
        self.assertEqual(captured["content_type"], "text/markdown")
        self.assertIn(b"# Bari Executive Safety Overview", captured["payload"])

    def test_execute_intervention_portfolio_report_uses_managed_portfolio_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            report = SimpleNamespace(
                id="report-portfolio-1",
                organization_id="org-1",
                report_type="intervention_portfolio",
                title="Bari Intervention Portfolio",
                output_format="csv",
                visibility_tier="restricted",
                parameters_json={"city_key": "bari"},
                summary_json={},
                status="queued",
                file_storage_uri=None,
                created_at=None,
                generated_at=None,
            )
            captured: dict[str, object] = {}

            def _persist_generated_artifact(*args, **kwargs):  # noqa: ARG001
                captured.update(kwargs)
                report.status = "generated"
                report.file_storage_uri = "s3://road-risk/reports/bari-portfolio.csv"
                return {
                    "access": SimpleNamespace(
                        as_dict=lambda: {
                            "download_url": "https://signed.example/portfolio-csv",
                            "storage_uri": report.file_storage_uri,
                        }
                    )
                }

            with (
                mock.patch(
                    "apps.api.services.reporting_hub.intervention_portfolio.build_portfolio_export",
                    return_value={
                        "contract_version": "intervention_portfolio_export_v1",
                        "organization_id": "org-1",
                        "city_key": "bari",
                        "availability": "available",
                        "unavailable_reason": None,
                        "summary": {"portfolio_count": 1, "expected_benefit": 7.0, "by_status": {"planned": 1}},
                        "rows": [
                            {
                                "priority_rank": 1,
                                "target": "Tangenziale di Bari",
                                "intervention_type": "speed_management",
                                "status": "planned",
                                "expected_benefit": 7.0,
                            }
                        ],
                    },
                ),
                mock.patch(
                    "apps.api.services.reporting_hub.artifact_storage.persist_generated_artifact",
                    side_effect=_persist_generated_artifact,
                ),
                mock.patch(
                    "apps.api.services.reporting_hub.repositories.record_audit_log",
                    return_value=None,
                ),
            ):
                payload = reporting_hub.execute_report_generation(object(), settings, report)

        self.assertEqual(payload["report"]["status"], "generated")
        self.assertEqual(captured["content_type"], "text/csv")
        self.assertIn(b"Tangenziale di Bari", captured["payload"])
        self.assertIn("intervention_portfolio_report_output", str(captured["artifact_kind"]))

    def test_execute_report_generation_persists_csv_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            report = SimpleNamespace(
                id="report-2",
                organization_id="org-1",
                report_type="technical_hotspot",
                title="Bari Technical Hotspot Pack",
                output_format="csv",
                visibility_tier="restricted",
                parameters_json={"city_key": "bari"},
                summary_json={},
                status="queued",
                file_storage_uri=None,
                created_at=None,
                generated_at=None,
            )
            captured: dict[str, object] = {}

            def _persist_generated_artifact(*args, **kwargs):  # noqa: ARG001
                captured.update(kwargs)
                report.status = "generated"
                report.file_storage_uri = "s3://road-risk/reports/bari.csv"
                return {
                    "access": SimpleNamespace(
                        as_dict=lambda: {  # noqa: ARG005
                            "download_url": "https://signed.example/report-csv",
                            "storage_uri": report.file_storage_uri,
                        }
                    )
                }

            with (
                mock.patch(
                    "apps.api.services.reporting_hub.artifact_storage.persist_generated_artifact",
                    side_effect=_persist_generated_artifact,
                ),
                mock.patch(
                    "apps.api.services.reporting_hub.repositories.record_audit_log",
                    return_value=None,
                ),
            ):
                payload = reporting_hub.execute_report_generation(object(), settings, report)

        self.assertEqual(payload["report"]["status"], "generated")
        self.assertEqual(captured["content_type"], "text/csv")
        self.assertIn(b"segment_label", captured["payload"])

    def test_generate_transient_report_returns_non_persisted_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            payload = reporting_hub.generate_transient_report(
                settings,
                organization_id="org-1",
                city_key="bari",
                report_type="executive_overview",
                output_format="pdf",
            )

        self.assertEqual(payload["contract_version"], reporting_hub.REPORT_GENERATION_CONTRACT_VERSION)
        self.assertEqual(payload["persistence_mode"], "transient")
        self.assertEqual(payload["report"]["download_state"], "not_persisted")
        self.assertGreater(payload["artifact_summary"]["payload_bytes"], 0)

    def test_public_transparency_report_supports_public_safe_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            captured_types: dict[str, str] = {}

            def _persist_generated_artifact(*args, **kwargs):  # noqa: ARG001
                report = kwargs["report"]
                captured_types[str(report.output_format)] = str(kwargs["content_type"])
                report.status = "generated"
                report.file_storage_uri = f"s3://road-risk/reports/bari-public.{report.output_format}"
                return {
                    "access": SimpleNamespace(
                        as_dict=lambda: {
                            "download_url": "https://signed.example/public",
                            "storage_uri": report.file_storage_uri,
                        }
                    )
                }

            with (
                mock.patch(
                    "apps.api.services.reporting_hub.artifact_storage.persist_generated_artifact",
                    side_effect=_persist_generated_artifact,
                ),
                mock.patch(
                    "apps.api.services.reporting_hub.repositories.record_audit_log",
                    return_value=None,
                ),
            ):
                for output_format in ["pdf", "md", "csv", "geojson", "xlsx"]:
                    report = SimpleNamespace(
                        id=f"report-public-{output_format}",
                        organization_id="org-1",
                        report_type="public_transparency",
                        title="Bari Public Transparency Report",
                        output_format=output_format,
                        visibility_tier="public",
                        parameters_json={"city_key": "bari"},
                        summary_json={},
                        status="queued",
                        file_storage_uri=None,
                        created_at=None,
                        generated_at=None,
                    )
                    payload = reporting_hub.execute_report_generation(object(), settings, report)
                    self.assertEqual(payload["report"]["status"], "generated")

        self.assertEqual(captured_types["pdf"], "application/pdf")
        self.assertEqual(captured_types["md"], "text/markdown")
        self.assertEqual(captured_types["csv"], "text/csv")
        self.assertEqual(captured_types["geojson"], "application/geo+json")
        self.assertIn("spreadsheetml", captured_types["xlsx"])

    def test_report_lifecycle_review_publish_and_audit(self) -> None:
        report = SimpleNamespace(
            id="report-public-1",
            organization_id="org-1",
            report_type="public_transparency",
            title="Bari Public Transparency Report",
            status="generated",
            visibility_tier="restricted",
            output_format="pdf",
            file_storage_uri="s3://road-risk/reports/bari-public.pdf",
            parameters_json={"city_key": "bari"},
            summary_json={},
            created_at=None,
            generated_at=None,
            published_at=None,
        )

        class FakeSession:
            def flush(self) -> None:
                return None

        with (
            mock.patch("apps.api.services.reporting_hub.repositories.get_report", return_value=report),
            mock.patch("apps.api.services.reporting_hub.repositories.record_audit_log", return_value=None) as audit_mock,
        ):
            reviewed = reporting_hub.transition_report_lifecycle(
                FakeSession(),
                organization_id="org-1",
                report_id="report-public-1",
                action="review",
                actor_subject="user-1",
            )
            published = reporting_hub.transition_report_lifecycle(
                FakeSession(),
                organization_id="org-1",
                report_id="report-public-1",
                action="publish",
                visibility_tier="public",
                actor_subject="user-1",
            )

        self.assertEqual(reviewed["report"]["status"], "reviewed")
        self.assertEqual(published["report"]["status"], "published")
        self.assertEqual(published["report"]["visibility_tier"], "public")
        self.assertEqual(published["report"]["publication_state"], "public")
        self.assertIsNotNone(report.published_at)
        self.assertEqual(audit_mock.call_count, 2)

    def test_internal_report_download_enforces_report_role_policy(self) -> None:
        report = SimpleNamespace(
            id="report-technical-1",
            organization_id="org-1",
            report_type="technical_hotspot",
            title="Bari Technical Hotspot Pack",
            status="generated",
            visibility_tier="restricted",
            output_format="csv",
            file_storage_uri="s3://road-risk/reports/bari.csv",
            parameters_json={"city_key": "bari"},
            summary_json={},
            created_at=None,
            generated_at=None,
            published_at=None,
        )

        with mock.patch("apps.api.services.reporting_hub.repositories.get_report", return_value=report):
            with self.assertRaises(reporting_hub.ReportingHubAuthorizationError):
                reporting_hub.get_report_download(
                    object(),
                    organization_id="org-1",
                    report_id="report-technical-1",
                    role_names={ROLE_MUNICIPALITY_VIEWER},
                )

        with (
            mock.patch("apps.api.services.reporting_hub.repositories.get_report", return_value=report),
            mock.patch(
                "apps.api.services.reporting_hub.resolve_artifact_download",
                return_value=SimpleNamespace(as_dict=lambda: {"download_url": "https://signed.example/report"}),
            ),
        ):
            payload = reporting_hub.get_report_download(
                object(),
                organization_id="org-1",
                report_id="report-technical-1",
                role_names={ROLE_ANALYST, ROLE_MUNICIPALITY_VIEWER},
            )
        self.assertEqual(payload["access"]["download_url"], "https://signed.example/report")

    def test_public_reports_list_hides_storage_uri(self) -> None:
        report = SimpleNamespace(
            id="report-public-1",
            organization_id="org-1",
            report_type="public_transparency",
            title="Bari Public Transparency Report",
            status="published",
            visibility_tier="public",
            output_format="pdf",
            file_storage_uri="s3://road-risk/reports/bari-public.pdf",
            parameters_json={"city_key": "bari"},
            summary_json={},
            created_at=None,
            generated_at=None,
            published_at=None,
        )
        with mock.patch(
            "apps.api.services.reporting_hub.repositories.list_public_reports_for_city",
            return_value=[report],
        ):
            payload = reporting_hub.list_public_reports(object(), city_key="bari")

        self.assertEqual(payload["contract_version"], reporting_hub.PUBLIC_REPORTS_CONTRACT_VERSION)
        self.assertEqual(payload["rows"][0]["download_state"], "ready")
        self.assertNotIn("file_storage_uri", payload["rows"][0])

    # ---- matrix-filter regression coverage (report record-kind) ----

    def _public_report_fixture(self) -> Any:
        return SimpleNamespace(
            id="report-public-1",
            organization_id="org-1",
            report_type="public_transparency",
            title="Bari Public Transparency Report",
            status="published",
            visibility_tier="public",
            output_format="pdf",
            file_storage_uri="s3://road-risk/reports/bari-public.pdf",
            parameters_json={"city_key": "bari", "audience": "public"},
            summary_json={"review_state": "published", "leak": "internal-only note"},
            created_at=None,
            generated_at=None,
            published_at=None,
        )

    def test_public_report_listing_strips_internal_only_fields(self) -> None:
        report = self._public_report_fixture()
        with mock.patch(
            "apps.api.services.reporting_hub.repositories.list_public_reports_for_city",
            return_value=[report],
        ):
            payload = reporting_hub.list_public_reports(object(), city_key="bari")
        row = payload["rows"][0]
        # Public-visible fields flow through:
        for kept in (
            "report_id",
            "title",
            "report_type",
            "output_format",
            "status",
            "visibility_tier",
            "city_key",
            "publication_state",
            "download_state",
        ):
            self.assertIn(kept, row, msg=f"public matrix should expose {kept!r}")
        # Internal-only / restricted fields default-denied for public:
        for stripped in (
            "organization_id",
            "audience",
            "summary",
            "review_state",
            "lifecycle_actions",
            "created_at",
            "file_storage_uri",
        ):
            self.assertNotIn(
                stripped, row,
                msg=f"public listing must NOT expose {stripped!r} (matrix internal/restricted)",
            )

    def test_public_report_listing_attaches_redaction_policy(self) -> None:
        report = self._public_report_fixture()
        with mock.patch(
            "apps.api.services.reporting_hub.repositories.list_public_reports_for_city",
            return_value=[report],
        ):
            payload = reporting_hub.list_public_reports(object(), city_key="bari")
        self.assertIn("redaction_policy", payload)
        self.assertEqual(payload["redaction_policy"]["record_kind"], "report")
        self.assertEqual(payload["redaction_policy"]["role"], "public")
        # The published fields list should not include any of the
        # internal-only or restricted entries:
        published = set(payload["redaction_policy"]["publishable_fields"])
        self.assertNotIn("organization_id", published)
        self.assertNotIn("file_storage_uri", published)
        self.assertNotIn("lifecycle_actions", published)
        self.assertNotIn("created_at", published)

    def test_report_history_analyst_role_keeps_internal_fields(self) -> None:
        report = SimpleNamespace(
            id="report-1",
            organization_id="org-1",
            report_type="technical_hotspot",
            title="Bari Hotspots",
            status="reviewed",
            visibility_tier="restricted",
            output_format="csv",
            file_storage_uri="s3://road-risk/reports/bari.csv",
            parameters_json={"city_key": "bari", "audience": "analyst"},
            summary_json={"review_state": "reviewed"},
            created_at=None,
            generated_at=None,
            published_at=None,
        )
        with mock.patch(
            "apps.api.services.reporting_hub.repositories.list_reports_for_organization",
            return_value=[report],
        ):
            payload = reporting_hub.list_report_history(
                object(),
                organization_id="org-1",
                role="analyst",
            )
        row = payload["rows"][0]
        # Internal fields flow through to analyst:
        for kept in (
            "report_id",
            "organization_id",
            "audience",
            "summary",
            "review_state",
            "lifecycle_actions",
            "created_at",
        ):
            self.assertIn(kept, row, msg=f"analyst should see {kept!r}")
        # file_storage_uri is restricted to data_operator/admin:
        self.assertNotIn(
            "file_storage_uri", row,
            msg="analyst must not see file_storage_uri (restricted)",
        )
        # Redaction policy carries the analyst role:
        self.assertEqual(payload["redaction_policy"]["role"], "analyst")

    def test_report_history_data_operator_role_keeps_restricted_storage_uri(self) -> None:
        report = SimpleNamespace(
            id="report-1",
            organization_id="org-1",
            report_type="technical_hotspot",
            title="Bari Hotspots",
            status="reviewed",
            visibility_tier="restricted",
            output_format="csv",
            file_storage_uri="s3://road-risk/reports/bari.csv",
            parameters_json={"city_key": "bari"},
            summary_json={},
            created_at=None,
            generated_at=None,
            published_at=None,
        )
        with mock.patch(
            "apps.api.services.reporting_hub.repositories.list_reports_for_organization",
            return_value=[report],
        ):
            payload = reporting_hub.list_report_history(
                object(),
                organization_id="org-1",
                role="data_operator",
            )
        row = payload["rows"][0]
        self.assertIn(
            "file_storage_uri", row,
            msg="data_operator must see file_storage_uri (restricted -> data_operator/admin)",
        )
        self.assertEqual(payload["redaction_policy"]["role"], "data_operator")

    def test_resolve_report_role_for_auth_picks_highest_precedence(self) -> None:
        # Highest-precedence role wins regardless of insertion order.
        self.assertEqual(
            reporting_hub.resolve_report_role_for_auth({"municipality_viewer", "analyst", "data_operator"}),
            "data_operator",
        )
        self.assertEqual(
            reporting_hub.resolve_report_role_for_auth({"analyst"}),
            "analyst",
        )
        self.assertEqual(
            reporting_hub.resolve_report_role_for_auth({"municipality_viewer"}),
            "municipality_viewer",
        )
        # Unknown / no roles fall back to public:
        self.assertEqual(
            reporting_hub.resolve_report_role_for_auth({"traffic_engineer", "anonymous"}),
            "public",
        )
        self.assertEqual(reporting_hub.resolve_report_role_for_auth(set()), "public")

    def test_create_report_request_rejects_public_visibility_for_restricted_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_reporting_root(Path(temp_dir))
            with self.assertRaises(reporting_hub.ReportingHubError):
                reporting_hub.create_report_request(
                    object(),
                    settings,
                    organization_id="org-1",
                    city_key="bari",
                    report_type="technical_hotspot",
                    output_format="csv",
                    visibility_tier="public",
                )


class ReportingHubEndpointTests(unittest.TestCase):
    def _build_client(self, *, roles: frozenset[str], auth_enabled: bool = True) -> TestClient:
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=auth_enabled))

        class FakeSession:
            def __init__(self) -> None:
                self.committed = 0
                self.rolled_back = 0

            def commit(self) -> None:
                self.committed += 1

            def rollback(self) -> None:
                self.rolled_back += 1

        self.session = FakeSession()

        def _session_override():
            yield self.session

        app.dependency_overrides[get_db_session] = _session_override
        if auth_enabled:
            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="user-1",
                assigned_roles=roles,
                roles=roles,
                scopes=frozenset(),
                claims={},
                organization_ids=frozenset({"org-1"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
        return TestClient(app)

    def test_reports_overview_endpoint_allows_viewer_scope(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_MUNICIPALITY_VIEWER}))
        with mock.patch(
            "apps.api.main.reporting_hub.build_reporting_overview",
            return_value={
                "contract_version": reporting_hub.REPORTING_OVERVIEW_CONTRACT_VERSION,
                "organization_id": "org-1",
                "selected_city_key": "bari",
                "city_catalog": [{"city_key": "bari", "display_name": "Bari", "prediction_run_label": "demo", "occurred_years": [2021]}],
                "executive_overview": {"city": {"city_key": "bari"}, "kpis": {}, "budget_impact": {}, "priority_areas": {"top_corridors": [], "top_actions": []}, "reporting_context": {}},
                "report_templates": [],
                "report_history": {"rows": []},
            },
        ):
            response = client.get("/v1/reports/overview", params={"organization_id": "org-1", "city_key": "bari"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], reporting_hub.REPORTING_OVERVIEW_CONTRACT_VERSION)

    def test_generate_report_endpoint_blocks_technical_report_for_viewer(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_MUNICIPALITY_VIEWER}))
        response = client.post(
            "/v1/reports/generate",
            json={
                "organization_id": "org-1",
                "city_key": "bari",
                "report_type": "technical_hotspot",
                "output_format": "csv",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_generate_report_endpoint_allows_analyst_inline(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ANALYST}))
        with (
            mock.patch(
                "apps.api.main.reporting_hub.create_report_request",
                return_value={
                    "contract_version": reporting_hub.REPORT_GENERATION_CONTRACT_VERSION,
                    "report": {"report_id": "report-1", "status": "queued"},
                },
            ),
            mock.patch(
                "apps.api.main.repositories.get_report",
                return_value=SimpleNamespace(id="report-1"),
            ),
            mock.patch(
                "apps.api.main._dispatch_report_generation",
                return_value=("inline", None),
            ),
            mock.patch(
                "apps.api.main.reporting_hub.execute_report_generation",
                return_value={
                    "contract_version": reporting_hub.REPORT_GENERATION_CONTRACT_VERSION,
                    "report": {"report_id": "report-1", "status": "generated"},
                    "artifact_access": {"download_url": "https://signed.example/report"},
                },
            ),
        ):
            response = client.post(
                "/v1/reports/generate",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "report_type": "technical_hotspot",
                    "output_format": "csv",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dispatch_mode"], "inline")
        self.assertEqual(response.json()["report"]["status"], "generated")

    def test_generate_report_endpoint_falls_back_to_transient_when_database_is_unavailable(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ANALYST}))
        with (
            mock.patch(
                "apps.api.main.reporting_hub.create_report_request",
                side_effect=SQLAlchemyError("database unavailable"),
            ),
            mock.patch(
                "apps.api.main.reporting_hub.generate_transient_report",
                return_value={
                    "contract_version": reporting_hub.REPORT_GENERATION_CONTRACT_VERSION,
                    "persistence_mode": "transient",
                    "report": {"report_id": "transient-1", "status": "generated", "download_state": "not_persisted"},
                    "artifact_access": {"download_url": ""},
                },
            ) as transient_mock,
        ):
            response = client.post(
                "/v1/reports/generate",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "report_type": "technical_hotspot",
                    "output_format": "csv",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["persistence_mode"], "transient")
        self.assertEqual(response.json()["dispatch_mode"], "inline")
        self.assertEqual(self.session.rolled_back, 1)
        transient_mock.assert_called_once()

    def test_report_download_endpoint_returns_access_bundle(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_MUNICIPALITY_VIEWER}))
        with mock.patch(
            "apps.api.main.reporting_hub.get_report_download",
            return_value={
                "contract_version": reporting_hub.REPORT_DETAIL_CONTRACT_VERSION,
                "report": {"report_id": "report-1", "status": "generated"},
                "access": {"download_url": "https://signed.example/report"},
            },
        ) as download_mock:
            response = client.get("/v1/reports/report-1/download", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access"]["download_url"], "https://signed.example/report")
        self.assertEqual(download_mock.call_args.kwargs["role_names"], {ROLE_MUNICIPALITY_VIEWER})

    def test_report_download_endpoint_skips_service_role_filter_when_auth_disabled(self) -> None:
        client = self._build_client(roles=frozenset(), auth_enabled=False)
        with mock.patch(
            "apps.api.main.reporting_hub.get_report_download",
            return_value={
                "contract_version": reporting_hub.REPORT_DETAIL_CONTRACT_VERSION,
                "report": {"report_id": "report-1", "status": "generated"},
                "access": {"download_url": "https://signed.example/report"},
            },
        ) as download_mock:
            response = client.get("/v1/reports/report-1/download", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(download_mock.call_args.kwargs["role_names"])

    def test_report_lifecycle_endpoint_requires_admin_for_publish(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ANALYST}))
        with mock.patch("apps.api.main.reporting_hub.transition_report_lifecycle") as lifecycle_mock:
            response = client.patch(
                "/v1/reports/report-1/lifecycle",
                json={"organization_id": "org-1", "action": "publish", "visibility_tier": "public"},
            )
        self.assertEqual(response.status_code, 403)
        lifecycle_mock.assert_not_called()

    def test_report_lifecycle_endpoint_allows_admin_publish(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ADMIN}))
        with mock.patch(
            "apps.api.main.reporting_hub.transition_report_lifecycle",
            return_value={
                "contract_version": reporting_hub.REPORT_LIFECYCLE_CONTRACT_VERSION,
                "report": {"report_id": "report-1", "status": "published", "visibility_tier": "public"},
            },
        ) as lifecycle_mock:
            response = client.patch(
                "/v1/reports/report-1/lifecycle",
                json={"organization_id": "org-1", "action": "publish", "visibility_tier": "public"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report"]["status"], "published")
        lifecycle_mock.assert_called_once()

    def test_public_reports_endpoint_exposes_published_rows_without_auth(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_MUNICIPALITY_VIEWER}))
        with mock.patch(
            "apps.api.main.reporting_hub.list_public_reports",
            return_value={
                "contract_version": reporting_hub.PUBLIC_REPORTS_CONTRACT_VERSION,
                "city_key": "bari",
                "availability": "available",
                "rows": [{"report_id": "report-public-1", "title": "Bari Public Transparency Report"}],
            },
        ):
            response = client.get("/v1/public/cities/bari/reports")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], reporting_hub.PUBLIC_REPORTS_CONTRACT_VERSION)
