"""Repository helpers for core operational tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ArtifactReference,
    AuditLog,
    DataSource,
    IngestionJob,
    Intervention,
    Municipality,
    Organization,
    OrganizationMembership,
    OrganizationMunicipality,
    Report,
    User,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_organization_by_slug(session: Session, slug: str) -> Organization | None:
    return session.scalar(select(Organization).where(Organization.slug == slug))


def create_organization(
    session: Session,
    *,
    slug: str,
    name: str,
    status: str = "active",
) -> Organization:
    organization = Organization(slug=slug, name=name, status=status)
    session.add(organization)
    session.flush()
    return organization


def get_user_by_subject(session: Session, subject: str) -> User | None:
    return session.scalar(select(User).where(User.external_subject == subject))


def upsert_user_by_subject(
    session: Session,
    *,
    subject: str,
    email: str | None = None,
    display_name: str | None = None,
) -> User:
    user = get_user_by_subject(session, subject)
    if user is None:
        user = User(external_subject=subject, email=email, display_name=display_name)
        session.add(user)
        session.flush()
        return user

    if email and user.email != email:
        user.email = email
    if display_name and user.display_name != display_name:
        user.display_name = display_name
    session.flush()
    return user


def update_user_profile(
    session: Session,
    user: User,
    *,
    locale: str | None = None,
    timezone_name: str | None = None,
    preferred_organization_id: str | None = None,
    preferred_municipality_id: str | None = None,
    profile: dict[str, Any] | None = None,
) -> User:
    if locale is not None:
        user.locale = locale
    if timezone_name is not None:
        user.timezone_name = timezone_name
    if preferred_organization_id is not None:
        user.preferred_organization_id = preferred_organization_id
    if preferred_municipality_id is not None:
        user.preferred_municipality_id = preferred_municipality_id
    if profile is not None:
        user.profile_json = dict(profile)
    session.flush()
    return user


def add_membership(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: str = "analyst",
    status: str = "active",
) -> OrganizationMembership:
    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        status=status,
    )
    session.add(membership)
    session.flush()
    return membership


def get_membership(session: Session, membership_id: str) -> OrganizationMembership | None:
    return session.scalar(select(OrganizationMembership).where(OrganizationMembership.id == membership_id))


def get_membership_for_user(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
) -> OrganizationMembership | None:
    return session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )


def list_memberships_for_organization(session: Session, organization_id: str) -> list[OrganizationMembership]:
    return list(
        session.scalars(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.created_at.asc())
        )
    )


def get_municipality_by_slug(session: Session, slug: str) -> Municipality | None:
    return session.scalar(select(Municipality).where(Municipality.slug == slug))


def create_municipality(
    session: Session,
    *,
    slug: str,
    name: str,
    country_code: str,
    region_code: str | None = None,
    province_code: str | None = None,
    city_code: str | None = None,
    status: str = "active",
) -> Municipality:
    municipality = Municipality(
        slug=slug,
        name=name,
        country_code=country_code,
        region_code=region_code,
        province_code=province_code,
        city_code=city_code,
        status=status,
    )
    session.add(municipality)
    session.flush()
    return municipality


def link_organization_municipality(
    session: Session,
    *,
    organization_id: str,
    municipality_id: str,
    access_level: str = "restricted",
    status: str = "active",
) -> OrganizationMunicipality:
    link = OrganizationMunicipality(
        organization_id=organization_id,
        municipality_id=municipality_id,
        access_level=access_level,
        status=status,
    )
    session.add(link)
    session.flush()
    return link


def get_organization_municipality_link(
    session: Session,
    *,
    organization_id: str,
    municipality_id: str,
) -> OrganizationMunicipality | None:
    return session.scalar(
        select(OrganizationMunicipality).where(
            OrganizationMunicipality.organization_id == organization_id,
            OrganizationMunicipality.municipality_id == municipality_id,
        )
    )


def list_municipality_links_for_organization(
    session: Session,
    organization_id: str,
) -> list[OrganizationMunicipality]:
    return list(
        session.scalars(
            select(OrganizationMunicipality)
            .where(OrganizationMunicipality.organization_id == organization_id)
            .order_by(OrganizationMunicipality.created_at.asc())
        )
    )


def get_data_source_by_name(session: Session, organization_id: str, name: str) -> DataSource | None:
    return session.scalar(
        select(DataSource).where(
            DataSource.organization_id == organization_id,
            DataSource.name == name,
        )
    )


def get_data_source(session: Session, source_id: str) -> DataSource | None:
    return session.scalar(select(DataSource).where(DataSource.id == source_id))


def get_ingestion_job(session: Session, job_id: str) -> IngestionJob | None:
    return session.scalar(select(IngestionJob).where(IngestionJob.id == job_id))


def create_data_source(
    session: Session,
    *,
    organization_id: str,
    name: str,
    source_type: str,
    municipality_id: str | None = None,
    provider_name: str | None = None,
    governance_status: str = "draft",
    publication_tier: str = "restricted",
    refresh_frequency: str | None = None,
    configuration: dict[str, Any] | None = None,
    status: str = "active",
) -> DataSource:
    source = DataSource(
        organization_id=organization_id,
        municipality_id=municipality_id,
        name=name,
        source_type=source_type,
        provider_name=provider_name,
        governance_status=governance_status,
        publication_tier=publication_tier,
        refresh_frequency=refresh_frequency,
        configuration_json=dict(configuration or {}),
        status=status,
    )
    session.add(source)
    session.flush()
    return source


def list_data_sources_for_organization(session: Session, organization_id: str) -> list[DataSource]:
    return list(
        session.scalars(
            select(DataSource)
            .where(DataSource.organization_id == organization_id)
            .order_by(DataSource.name.asc())
        )
    )


def create_ingestion_job(
    session: Session,
    *,
    organization_id: str,
    job_type: str,
    municipality_id: str | None = None,
    source_id: str | None = None,
    submitted_by_user_id: str | None = None,
    status: str = "queued",
    input_storage_uri: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> IngestionJob:
    job = IngestionJob(
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        submitted_by_user_id=submitted_by_user_id,
        job_type=job_type,
        status=status,
        input_storage_uri=input_storage_uri,
        parameters_json=dict(parameters or {}),
    )
    session.add(job)
    session.flush()
    return job


def list_ingestion_jobs_for_organization(
    session: Session,
    organization_id: str,
    *,
    municipality_id: str | None = None,
    source_id: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[IngestionJob]:
    statement = (
        select(IngestionJob)
        .where(IngestionJob.organization_id == organization_id)
        .order_by(IngestionJob.created_at.desc())
    )
    if municipality_id is not None:
        statement = statement.where(IngestionJob.municipality_id == municipality_id)
    if source_id is not None:
        statement = statement.where(IngestionJob.source_id == source_id)
    if status is not None:
        statement = statement.where(IngestionJob.status == status)
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def mark_ingestion_job_running(
    session: Session,
    job: IngestionJob,
    *,
    started_at: datetime | None = None,
    status: str = "running",
) -> IngestionJob:
    job.status = status
    job.started_at = started_at or _utc_now()
    session.flush()
    return job


def mark_ingestion_job_finished(
    session: Session,
    job: IngestionJob,
    *,
    status: str = "completed",
    finished_at: datetime | None = None,
    manifest_storage_uri: str | None = None,
    error_storage_uri: str | None = None,
    job_stats: dict[str, Any] | None = None,
) -> IngestionJob:
    job.status = status
    job.finished_at = finished_at or _utc_now()
    if manifest_storage_uri is not None:
        job.manifest_storage_uri = manifest_storage_uri
    if error_storage_uri is not None:
        job.error_storage_uri = error_storage_uri
    if job_stats is not None:
        job.job_stats_json = dict(job_stats)
    session.flush()
    return job


def attach_ingestion_job_storage(
    session: Session,
    job: IngestionJob,
    *,
    input_storage_uri: str | None = None,
    manifest_storage_uri: str | None = None,
    error_storage_uri: str | None = None,
    status: str | None = None,
    parameters: dict[str, Any] | None = None,
    job_stats: dict[str, Any] | None = None,
) -> IngestionJob:
    if input_storage_uri is not None:
        job.input_storage_uri = input_storage_uri
    if manifest_storage_uri is not None:
        job.manifest_storage_uri = manifest_storage_uri
    if error_storage_uri is not None:
        job.error_storage_uri = error_storage_uri
    if status is not None:
        job.status = status
    if parameters is not None:
        merged_parameters = dict(job.parameters_json or {})
        merged_parameters.update(parameters)
        job.parameters_json = merged_parameters
    if job_stats is not None:
        merged_job_stats = dict(job.job_stats_json or {})
        merged_job_stats.update(job_stats)
        job.job_stats_json = merged_job_stats
    session.flush()
    return job


def record_audit_log(
    session: Session,
    *,
    organization_id: str,
    action: str,
    target_type: str,
    municipality_id: str | None = None,
    user_id: str | None = None,
    target_id: str | None = None,
    status: str = "recorded",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        organization_id=organization_id,
        municipality_id=municipality_id,
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        status=status,
        metadata_json=dict(metadata or {}),
    )
    session.add(log)
    session.flush()
    return log


def list_audit_logs_for_organization(session: Session, organization_id: str) -> list[AuditLog]:
    return list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc())
        )
    )


def create_report(
    session: Session,
    *,
    organization_id: str,
    report_type: str,
    title: str,
    municipality_id: str | None = None,
    generated_by_user_id: str | None = None,
    status: str = "draft",
    visibility_tier: str = "restricted",
    output_format: str = "pdf",
    file_storage_uri: str | None = None,
    parameters: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> Report:
    report = Report(
        organization_id=organization_id,
        municipality_id=municipality_id,
        generated_by_user_id=generated_by_user_id,
        report_type=report_type,
        title=title,
        status=status,
        visibility_tier=visibility_tier,
        output_format=output_format,
        file_storage_uri=file_storage_uri,
        parameters_json=dict(parameters or {}),
        summary_json=dict(summary or {}),
    )
    session.add(report)
    session.flush()
    return report


def list_reports_for_organization(session: Session, organization_id: str) -> list[Report]:
    return list(
        session.scalars(
            select(Report)
            .where(Report.organization_id == organization_id)
            .order_by(Report.created_at.desc())
        )
    )


def list_public_reports_for_city(session: Session, city_key: str, *, limit: int = 50) -> list[Report]:
    reports = list(
        session.scalars(
            select(Report)
            .where(Report.status == "published")
            .where(Report.visibility_tier == "public")
            .order_by(Report.published_at.desc().nullslast(), Report.generated_at.desc().nullslast())
        )
    )
    rows = [
        report
        for report in reports
        if str((report.parameters_json or {}).get("city_key") or "") == city_key
    ]
    return rows[:limit]


def get_report(session: Session, report_id: str) -> Report | None:
    return session.get(Report, report_id)


def mark_report_generated(
    session: Session,
    report: Report,
    *,
    status: str = "generated",
    file_storage_uri: str | None = None,
    summary: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> Report:
    report.status = status
    report.generated_at = generated_at or _utc_now()
    if file_storage_uri is not None:
        report.file_storage_uri = file_storage_uri
    if summary is not None:
        report.summary_json = dict(summary)
    session.flush()
    return report


def attach_report_storage(
    session: Session,
    report: Report,
    *,
    file_storage_uri: str | None = None,
    status: str | None = None,
    parameters: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> Report:
    if file_storage_uri is not None:
        report.file_storage_uri = file_storage_uri
    if status is not None:
        report.status = status
    if parameters is not None:
        merged_parameters = dict(report.parameters_json or {})
        merged_parameters.update(parameters)
        report.parameters_json = merged_parameters
    if summary is not None:
        merged_summary = dict(report.summary_json or {})
        merged_summary.update(summary)
        report.summary_json = merged_summary
    session.flush()
    return report


def update_report_lifecycle(
    session: Session,
    report: Report,
    *,
    status: str | None = None,
    visibility_tier: str | None = None,
    published_at: datetime | None = None,
    clear_published_at: bool = False,
    summary: dict[str, Any] | None = None,
) -> Report:
    if status is not None:
        report.status = status
    if visibility_tier is not None:
        report.visibility_tier = visibility_tier
    if clear_published_at:
        report.published_at = None
    elif published_at is not None:
        report.published_at = published_at
    if summary is not None:
        merged_summary = dict(report.summary_json or {})
        merged_summary.update(summary)
        report.summary_json = merged_summary
    session.flush()
    return report


def create_intervention(
    session: Session,
    *,
    organization_id: str,
    target_object_type: str,
    target_object_id: str,
    intervention_type: str,
    municipality_id: str | None = None,
    scenario_run_id: str | None = None,
    cost_class: str | None = None,
    expected_benefit: float | None = None,
    priority_score: float | None = None,
    status: str = "candidate",
    owner_subject: str | None = None,
    planned_start_date: Any | None = None,
    planned_completion_date: Any | None = None,
    completed_at: datetime | None = None,
    notes: str | None = None,
    source_kind: str | None = None,
    properties: dict[str, Any] | None = None,
) -> Intervention:
    intervention = Intervention(
        organization_id=organization_id,
        municipality_id=municipality_id,
        scenario_run_id=scenario_run_id,
        target_object_type=target_object_type,
        target_object_id=target_object_id,
        intervention_type=intervention_type,
        cost_class=cost_class,
        expected_benefit=expected_benefit,
        priority_score=priority_score,
        status=status,
        owner_subject=owner_subject,
        planned_start_date=planned_start_date,
        planned_completion_date=planned_completion_date,
        completed_at=completed_at,
        notes=notes,
        source_kind=source_kind,
        properties_json=dict(properties or {}),
    )
    session.add(intervention)
    session.flush()
    return intervention


def get_intervention(session: Session, intervention_id: str) -> Intervention | None:
    return session.get(Intervention, intervention_id)


def list_interventions_for_organization(
    session: Session,
    organization_id: str,
    *,
    municipality_id: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[Intervention]:
    statement = (
        select(Intervention)
        .where(Intervention.organization_id == organization_id)
        .order_by(Intervention.priority_score.desc().nullslast(), Intervention.updated_at.desc())
    )
    if municipality_id is not None:
        statement = statement.where(Intervention.municipality_id == municipality_id)
    if status is not None:
        statement = statement.where(Intervention.status == status)
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def update_intervention(
    session: Session,
    intervention: Intervention,
    *,
    status: str | None = None,
    owner_subject: str | None = None,
    planned_start_date: Any | None = None,
    planned_completion_date: Any | None = None,
    completed_at: datetime | None = None,
    notes: str | None = None,
    cost_class: str | None = None,
    expected_benefit: float | None = None,
    priority_score: float | None = None,
    properties: dict[str, Any] | None = None,
) -> Intervention:
    if status is not None:
        intervention.status = status
    if owner_subject is not None:
        intervention.owner_subject = owner_subject
    if planned_start_date is not None:
        intervention.planned_start_date = planned_start_date
    if planned_completion_date is not None:
        intervention.planned_completion_date = planned_completion_date
    if completed_at is not None:
        intervention.completed_at = completed_at
    if notes is not None:
        intervention.notes = notes
    if cost_class is not None:
        intervention.cost_class = cost_class
    if expected_benefit is not None:
        intervention.expected_benefit = expected_benefit
    if priority_score is not None:
        intervention.priority_score = priority_score
    if properties is not None:
        merged_properties = dict(intervention.properties_json or {})
        merged_properties.update(properties)
        intervention.properties_json = merged_properties
    session.flush()
    return intervention


def create_artifact_reference(
    session: Session,
    *,
    organization_id: str,
    artifact_kind: str,
    artifact_name: str,
    storage_uri: str,
    municipality_id: str | None = None,
    source_id: str | None = None,
    ingestion_job_id: str | None = None,
    created_by_user_id: str | None = None,
    content_type: str | None = None,
    publication_tier: str = "restricted",
    lifecycle_status: str = "active",
    lineage: dict[str, Any] | None = None,
) -> ArtifactReference:
    artifact = (
        session.scalar(
            select(ArtifactReference).where(
                ArtifactReference.organization_id == organization_id,
                ArtifactReference.storage_uri == storage_uri,
            )
        )
        if hasattr(session, "scalar")
        else None
    )
    if artifact is not None:
        artifact.municipality_id = municipality_id
        artifact.source_id = source_id
        artifact.ingestion_job_id = ingestion_job_id
        artifact.created_by_user_id = created_by_user_id
        artifact.artifact_kind = artifact_kind
        artifact.artifact_name = artifact_name
        artifact.content_type = content_type
        artifact.publication_tier = publication_tier
        artifact.lifecycle_status = lifecycle_status
        artifact.lineage_json = dict(lineage or {})
        session.flush()
        return artifact

    artifact = ArtifactReference(
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        ingestion_job_id=ingestion_job_id,
        created_by_user_id=created_by_user_id,
        artifact_kind=artifact_kind,
        artifact_name=artifact_name,
        storage_uri=storage_uri,
        content_type=content_type,
        publication_tier=publication_tier,
        lifecycle_status=lifecycle_status,
        lineage_json=dict(lineage or {}),
    )
    session.add(artifact)
    session.flush()
    return artifact


def list_organization_municipality_ids(session: Session, organization_id: str) -> list[str]:
    rows = session.scalars(
        select(OrganizationMunicipality.municipality_id).where(
            OrganizationMunicipality.organization_id == organization_id
        )
    )
    return list(rows)


def list_memberships_for_user(session: Session, user_id: str) -> list[OrganizationMembership]:
    return list(
        session.scalars(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id))
    )


def list_artifact_references_for_organization(
    session: Session,
    organization_id: str,
    *,
    artifact_kind: str | None = None,
) -> list[ArtifactReference]:
    statement = select(ArtifactReference).where(ArtifactReference.organization_id == organization_id)
    if artifact_kind:
        statement = statement.where(ArtifactReference.artifact_kind == artifact_kind)
    return list(session.scalars(statement.order_by(ArtifactReference.created_at.desc())))


def list_artifact_references_for_job(
    session: Session,
    ingestion_job_id: str,
) -> list[ArtifactReference]:
    return list(
        session.scalars(
            select(ArtifactReference)
            .where(ArtifactReference.ingestion_job_id == ingestion_job_id)
            .order_by(ArtifactReference.created_at.asc())
        )
    )


def remove_memberships(session: Session, membership_ids: Iterable[str]) -> int:
    ids = list(membership_ids)
    if not ids:
        return 0
    result = session.query(OrganizationMembership).filter(OrganizationMembership.id.in_(ids)).delete()
    session.flush()
    return int(result or 0)
