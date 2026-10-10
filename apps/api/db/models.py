"""Core operational tables for the API service."""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _utc_now() -> sa.sql.elements.TextClause:
    return sa.text("now()")


class Geometry(sa.types.UserDefinedType):
    """Minimal PostGIS geometry type without requiring GeoAlchemy at runtime."""

    cache_ok = True

    def __init__(self, geometry_type: str, srid: int = 4326) -> None:
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **_: object) -> str:
        return f"geometry({self.geometry_type},{self.srid})"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(sa.String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    members: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    municipality_links: Mapped[list["OrganizationMunicipality"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list["DataSource"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    artifact_references: Mapped[list["ArtifactReference"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    external_subject: Mapped[str] = mapped_column(
        sa.String(200),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(sa.String(320))
    display_name: Mapped[str | None] = mapped_column(sa.String(200))
    locale: Mapped[str | None] = mapped_column(sa.String(32))
    timezone_name: Mapped[str | None] = mapped_column(sa.String(64))
    preferred_organization_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    preferred_municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    submitted_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="submitted_by_user",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user",
    )
    generated_reports: Mapped[list["Report"]] = relationship(
        back_populates="generated_by_user",
    )
    created_artifacts: Mapped[list["ArtifactReference"]] = relationship(
        back_populates="created_by_user",
    )


class Municipality(Base):
    __tablename__ = "municipalities"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(sa.String(160), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    country_code: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    region_code: Mapped[str | None] = mapped_column(sa.String(16))
    province_code: Mapped[str | None] = mapped_column(sa.String(16))
    city_code: Mapped[str | None] = mapped_column(sa.String(32))
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization_links: Mapped[list["OrganizationMunicipality"]] = relationship(
        back_populates="municipality",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list["DataSource"]] = relationship(back_populates="municipality")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="municipality")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="municipality")
    reports: Mapped[list["Report"]] = relationship(back_populates="municipality")
    artifact_references: Mapped[list["ArtifactReference"]] = relationship(
        back_populates="municipality"
    )

    __table_args__ = (
        sa.UniqueConstraint("country_code", "city_code", name="uq_municipality_country_city"),
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        sa.String(60),
        nullable=False,
        server_default=sa.text("'analyst'"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )


class OrganizationMunicipality(Base):
    __tablename__ = "organization_municipalities"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(
        sa.String(60),
        nullable=False,
        server_default=sa.text("'restricted'"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="municipality_links")
    municipality: Mapped[Municipality] = relationship(back_populates="organization_links")

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "municipality_id", name="uq_org_municipality"),
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(sa.String(200))
    governance_status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'draft'"),
    )
    publication_tier: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'restricted'"),
    )
    refresh_frequency: Mapped[str | None] = mapped_column(sa.String(40))
    last_refresh_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    configuration_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="data_sources")
    municipality: Mapped[Municipality | None] = relationship(back_populates="data_sources")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")
    artifact_references: Mapped[list["ArtifactReference"]] = relationship(back_populates="source")

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "name", name="uq_data_source_org_name"),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'queued'"),
    )
    input_storage_uri: Mapped[str | None] = mapped_column(sa.Text())
    manifest_storage_uri: Mapped[str | None] = mapped_column(sa.Text())
    error_storage_uri: Mapped[str | None] = mapped_column(sa.Text())
    parameters_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    job_stats_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    queued_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="ingestion_jobs")
    municipality: Mapped[Municipality | None] = relationship(back_populates="ingestion_jobs")
    source: Mapped[DataSource | None] = relationship(back_populates="ingestion_jobs")
    submitted_by_user: Mapped[User | None] = relationship(back_populates="submitted_jobs")
    artifact_references: Mapped[list["ArtifactReference"]] = relationship(
        back_populates="ingestion_job"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    target_id: Mapped[str | None] = mapped_column(sa.String(200))
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'recorded'"),
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="audit_logs")
    municipality: Mapped[Municipality | None] = relationship(back_populates="audit_logs")
    user: Mapped[User | None] = relationship(back_populates="audit_logs")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'draft'"),
    )
    visibility_tier: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'restricted'"),
    )
    output_format: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'pdf'"),
    )
    file_storage_uri: Mapped[str | None] = mapped_column(sa.Text())
    parameters_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    summary_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    generated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="reports")
    municipality: Mapped[Municipality | None] = relationship(back_populates="reports")
    generated_by_user: Mapped[User | None] = relationship(back_populates="generated_reports")


class ArtifactReference(Base):
    __tablename__ = "artifact_references"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    ingestion_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_kind: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    artifact_name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    storage_uri: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    content_type: Mapped[str | None] = mapped_column(sa.String(160))
    publication_tier: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'restricted'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    lineage_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="artifact_references")
    municipality: Mapped[Municipality | None] = relationship(back_populates="artifact_references")
    source: Mapped[DataSource | None] = relationship(back_populates="artifact_references")
    ingestion_job: Mapped[IngestionJob | None] = relationship(back_populates="artifact_references")
    created_by_user: Mapped[User | None] = relationship(back_populates="created_artifacts")

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "storage_uri", name="uq_artifact_reference_org_uri"),
    )


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_run_id: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    model_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    prediction_task: Mapped[str | None] = mapped_column(sa.String(160))
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'published'"),
    )
    training_config_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    metrics_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    lineage_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    artifact_manifest_uri: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "external_run_id",
            name="uq_model_runs_org_municipality_external",
        ),
        sa.Index("ix_model_runs_org_municipality_status", "organization_id", "municipality_id", "status"),
    )


class CrashRecord(Base):
    __tablename__ = "crash_records"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_record_id: Mapped[str | None] = mapped_column(sa.String(240))
    occurred_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    occurred_year: Mapped[int | None] = mapped_column(sa.Integer())
    severity: Mapped[str | None] = mapped_column(sa.String(80))
    road_name: Mapped[str | None] = mapped_column(sa.String(240))
    raw_payload_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    canonical_payload_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object] = mapped_column(Geometry("POINT", 4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "external_record_id",
            name="uq_crash_records_org_municipality_external",
        ),
        sa.Index("ix_crash_records_org_municipality_year", "organization_id", "municipality_id", "occurred_year"),
        sa.Index("ix_crash_records_geom", "geom", postgresql_using="gist"),
    )


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    segment_external_id: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    road_name: Mapped[str | None] = mapped_column(sa.String(240))
    road_class: Mapped[str | None] = mapped_column(sa.String(120))
    speed_limit: Mapped[float | None] = mapped_column(sa.Numeric(8, 2))
    length_m: Mapped[float | None] = mapped_column(sa.Numeric(12, 3))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object] = mapped_column(Geometry("LINESTRING", 4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "segment_external_id",
            name="uq_road_segments_org_municipality_external",
        ),
        sa.Index("ix_road_segments_org_municipality", "organization_id", "municipality_id"),
        sa.Index("ix_road_segments_geom", "geom", postgresql_using="gist"),
    )


class RoadNode(Base):
    __tablename__ = "road_nodes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_external_id: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    node_type: Mapped[str | None] = mapped_column(sa.String(120))
    control_type: Mapped[str | None] = mapped_column(sa.String(120))
    signal_id: Mapped[str | None] = mapped_column(sa.String(160))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object] = mapped_column(Geometry("POINT", 4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "node_external_id",
            name="uq_road_nodes_org_municipality_external",
        ),
        sa.Index("ix_road_nodes_org_municipality", "organization_id", "municipality_id"),
        sa.Index("ix_road_nodes_geom", "geom", postgresql_using="gist"),
    )


class Crossing(Base):
    __tablename__ = "crossings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    crossing_external_id: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    crossing_type: Mapped[str | None] = mapped_column(sa.String(120))
    protection_type: Mapped[str | None] = mapped_column(sa.String(120))
    accessibility_score: Mapped[float | None] = mapped_column(sa.Numeric(8, 3))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object] = mapped_column(Geometry("POINT", 4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "crossing_external_id",
            name="uq_crossings_org_municipality_external",
        ),
        sa.Index("ix_crossings_org_municipality", "organization_id", "municipality_id"),
        sa.Index("ix_crossings_geom", "geom", postgresql_using="gist"),
    )


class MovementObject(Base):
    __tablename__ = "movement_objects"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    junction_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("road_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    movement_external_id: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    incoming_arm: Mapped[str | None] = mapped_column(sa.String(120))
    outgoing_arm: Mapped[str | None] = mapped_column(sa.String(120))
    movement_type: Mapped[str | None] = mapped_column(sa.String(120))
    signal_phase_status: Mapped[str | None] = mapped_column(sa.String(120))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object | None] = mapped_column(Geometry("LINESTRING", 4326))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "movement_external_id",
            name="uq_movement_objects_org_municipality_external",
        ),
        sa.Index("ix_movement_objects_org_municipality", "organization_id", "municipality_id"),
        sa.Index("ix_movement_objects_geom", "geom", postgresql_using="gist"),
    )


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    score_external_id: Mapped[str] = mapped_column(sa.String(260), nullable=False)
    object_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    object_external_id: Mapped[str] = mapped_column(sa.String(260), nullable=False)
    occurred_year: Mapped[int | None] = mapped_column(sa.Integer())
    risk_score: Mapped[float | None] = mapped_column(sa.Numeric(10, 4))
    score_band: Mapped[str | None] = mapped_column(sa.String(40))
    predicted_crashes: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    observed_crashes: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    severity_risk: Mapped[str | None] = mapped_column(sa.String(80))
    confidence: Mapped[str | None] = mapped_column(sa.String(80))
    explanation_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    __table_args__ = (
        sa.UniqueConstraint("model_run_id", "object_type", "object_external_id", name="uq_risk_scores_run_object"),
        sa.Index("ix_risk_scores_org_municipality_band", "organization_id", "municipality_id", "score_band"),
        sa.Index("ix_risk_scores_model_run_score", "model_run_id", "risk_score"),
    )


class PublicRiskTile(Base):
    __tablename__ = "public_risk_tiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tile_external_id: Mapped[str] = mapped_column(sa.String(260), nullable=False)
    occurred_year: Mapped[int | None] = mapped_column(sa.Integer())
    tile_size_m: Mapped[float | None] = mapped_column(sa.Numeric(12, 3))
    risk_score: Mapped[float | None] = mapped_column(sa.Numeric(10, 4))
    score_band: Mapped[str | None] = mapped_column(sa.String(40))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    geom: Mapped[object] = mapped_column(Geometry("POLYGON", 4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )

    __table_args__ = (
        sa.UniqueConstraint("model_run_id", "tile_external_id", name="uq_public_risk_tiles_run_external"),
        sa.Index("ix_public_risk_tiles_org_municipality_band", "organization_id", "municipality_id", "score_band"),
        sa.Index("ix_public_risk_tiles_model_run_score", "model_run_id", "risk_score"),
        sa.Index("ix_public_risk_tiles_geom", "geom", postgresql_using="gist"),
    )


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    scenario_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'draft'"),
    )
    parameters_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    baseline_score: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    projected_score: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    expected_benefit: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    confidence: Mapped[str | None] = mapped_column(sa.String(80))
    result_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_scenario_runs_org_status", "organization_id", "status"),
        sa.Index("ix_scenario_runs_org_municipality", "organization_id", "municipality_id"),
    )


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    municipality_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
        nullable=True,
    )
    scenario_run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("scenario_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_object_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    target_object_id: Mapped[str] = mapped_column(sa.String(260), nullable=False)
    intervention_type: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    cost_class: Mapped[str | None] = mapped_column(sa.String(80))
    expected_benefit: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    priority_score: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'candidate'"),
    )
    owner_subject: Mapped[str | None] = mapped_column(sa.String(200))
    planned_start_date: Mapped[date | None] = mapped_column(sa.Date())
    planned_completion_date: Mapped[date | None] = mapped_column(sa.Date())
    completed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text())
    source_kind: Mapped[str | None] = mapped_column(sa.String(120))
    properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=_utc_now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_interventions_org_status", "organization_id", "status"),
        sa.Index("ix_interventions_target", "target_object_type", "target_object_id"),
    )


__all__ = [
    "ArtifactReference",
    "AuditLog",
    "Base",
    "CrashRecord",
    "Crossing",
    "DataSource",
    "Geometry",
    "IngestionJob",
    "Intervention",
    "ModelRun",
    "Municipality",
    "MovementObject",
    "Organization",
    "OrganizationMembership",
    "OrganizationMunicipality",
    "PublicRiskTile",
    "Report",
    "RiskScore",
    "RoadNode",
    "RoadSegment",
    "ScenarioRun",
    "User",
]
