"""Organization-scoped operational metadata services."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from apps.api.db import repositories


def build_local_development_seed_plan(
    *,
    organization_slug: str = "demo-bari",
    organization_name: str = "Demo Bari Mobility Office",
    municipality_slug: str = "bari-demo",
    municipality_name: str = "Bari",
    country_code: str = "IT",
    region_code: str = "PUG",
    city_code: str = "072006",
    user_subject: str = "demo.analyst",
    user_email: str = "demo.analyst@example.test",
    report_title: str = "Monthly safety overview",
) -> dict[str, Any]:
    return {
        "organization": {
            "slug": organization_slug,
            "name": organization_name,
            "status": "active",
        },
        "municipality": {
            "slug": municipality_slug,
            "name": municipality_name,
            "country_code": country_code,
            "region_code": region_code,
            "city_code": city_code,
            "status": "active",
        },
        "user": {
            "subject": user_subject,
            "email": user_email,
            "display_name": "Demo Analyst",
            "locale": "it-IT",
            "timezone_name": "Europe/Rome",
            "profile": {"team": "road-safety", "seed_fixture": True},
        },
        "membership": {
            "role": "analyst",
            "status": "active",
        },
        "municipality_link": {
            "access_level": "restricted",
            "status": "active",
        },
        "data_sources": [
            {
                "name": "Bari crash feed",
                "source_type": "crash_feed",
                "provider_name": "Comune di Bari",
                "governance_status": "approved",
                "publication_tier": "internal",
                "refresh_frequency": "monthly",
                "configuration": {"format": "csv"},
            },
            {
                "name": "Bari public dashboard tiles",
                "source_type": "published_resource_index",
                "provider_name": "Road Risk Platform",
                "governance_status": "approved",
                "publication_tier": "public",
                "refresh_frequency": "weekly",
                "configuration": {"resource_name": "segment_scores"},
            },
        ],
        "report": {
            "report_type": "monthly_safety_overview",
            "title": report_title,
            "status": "generated",
            "visibility_tier": "internal",
            "output_format": "pdf",
            "file_storage_uri": "s3://road-risk/reports/demo-bari-monthly-overview.pdf",
            "summary": {"generated_from_seed_fixture": True},
        },
        "audit_log": {
            "action": "seed_fixture_initialized",
            "target_type": "organization",
            "status": "recorded",
            "metadata": {"seed_fixture": True},
        },
    }


def seed_local_development_fixture(
    session: Session,
    *,
    seed_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = seed_plan or build_local_development_seed_plan()

    organization = repositories.create_organization(session, **plan["organization"])
    municipality = repositories.create_municipality(session, **plan["municipality"])
    user = repositories.upsert_user_by_subject(
        session,
        subject=plan["user"]["subject"],
        email=plan["user"]["email"],
        display_name=plan["user"]["display_name"],
    )
    repositories.update_user_profile(
        session,
        user,
        locale=plan["user"]["locale"],
        timezone_name=plan["user"]["timezone_name"],
        preferred_organization_id=organization.id,
        preferred_municipality_id=municipality.id,
        profile=plan["user"]["profile"],
    )
    membership = repositories.add_membership(
        session,
        organization_id=organization.id,
        user_id=user.id,
        **plan["membership"],
    )
    municipality_link = repositories.link_organization_municipality(
        session,
        organization_id=organization.id,
        municipality_id=municipality.id,
        **plan["municipality_link"],
    )
    data_sources = [
        repositories.create_data_source(
            session,
            organization_id=organization.id,
            municipality_id=municipality.id,
            **source_plan,
        )
        for source_plan in plan["data_sources"]
    ]
    report = repositories.create_report(
        session,
        organization_id=organization.id,
        municipality_id=municipality.id,
        generated_by_user_id=user.id,
        **plan["report"],
    )
    audit_log = repositories.record_audit_log(
        session,
        organization_id=organization.id,
        municipality_id=municipality.id,
        user_id=user.id,
        target_id=str(organization.id),
        **plan["audit_log"],
    )

    return {
        "organization": organization,
        "municipality": municipality,
        "user": user,
        "membership": membership,
        "municipality_link": municipality_link,
        "data_sources": data_sources,
        "report": report,
        "audit_log": audit_log,
    }


def build_organization_operational_snapshot(session: Session, organization_id: str) -> dict[str, Any]:
    memberships = repositories.list_memberships_for_organization(session, organization_id)
    municipality_links = repositories.list_municipality_links_for_organization(session, organization_id)
    data_sources = repositories.list_data_sources_for_organization(session, organization_id)
    ingestion_jobs = repositories.list_ingestion_jobs_for_organization(session, organization_id)
    reports = repositories.list_reports_for_organization(session, organization_id)
    audit_logs = repositories.list_audit_logs_for_organization(session, organization_id)
    artifacts = repositories.list_artifact_references_for_organization(session, organization_id)

    return {
        "organization_id": organization_id,
        "operational_metadata": {
            "membership_count": len(memberships),
            "municipality_access_count": len(municipality_links),
            "data_source_count": len(data_sources),
            "ingestion_job_count": len(ingestion_jobs),
            "report_count": len(reports),
            "audit_log_count": len(audit_logs),
            "memberships": [
                {
                    "user_id": str(row.user_id),
                    "role": row.role,
                    "status": row.status,
                }
                for row in memberships
            ],
            "municipality_links": [
                {
                    "municipality_id": str(row.municipality_id),
                    "access_level": row.access_level,
                    "status": row.status,
                }
                for row in municipality_links
            ],
            "data_sources": [
                {
                    "name": row.name,
                    "source_type": row.source_type,
                    "publication_tier": row.publication_tier,
                }
                for row in data_sources
            ],
            "ingestion_jobs": [
                {
                    "job_type": row.job_type,
                    "status": row.status,
                }
                for row in ingestion_jobs
            ],
            "reports": [
                {
                    "title": row.title,
                    "report_type": row.report_type,
                    "status": row.status,
                }
                for row in reports
            ],
            "audit_logs": [
                {
                    "action": row.action,
                    "target_type": row.target_type,
                    "status": row.status,
                }
                for row in audit_logs
            ],
        },
        "analytics_artifact_references": [
            {
                "artifact_kind": row.artifact_kind,
                "artifact_name": row.artifact_name,
                "storage_uri": row.storage_uri,
                "publication_tier": row.publication_tier,
            }
            for row in artifacts
        ],
    }
