"""PostGIS product domain tables for v1 serving.

Revision ID: 9f2b6a1c4d8e
Revises: 1d2c3b4a5e6f
Create Date: 2026-05-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9f2b6a1c4d8e"
down_revision = "1d2c3b4a5e6f"
branch_labels = None
depends_on = None


class Geometry(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, geometry_type: str, srid: int = 4326) -> None:
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **_: object) -> str:
        return f"geometry({self.geometry_type},{self.srid})"


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _org_column(*, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column(
        "organization_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete=ondelete),
        nullable=False,
    )


def _municipality_column(*, nullable: bool = False, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column(
        "municipality_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("municipalities.id", ondelete=ondelete),
        nullable=nullable,
    )


def _jsonb(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))


def upgrade() -> None:
    op.create_table(
        "model_runs",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("external_run_id", sa.String(length=200), nullable=False),
        sa.Column("model_type", sa.String(length=120), nullable=False),
        sa.Column("prediction_task", sa.String(length=160)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'published'")),
        _jsonb("training_config_json"),
        _jsonb("metrics_json"),
        _jsonb("lineage_json"),
        sa.Column("artifact_manifest_uri", sa.Text()),
        _created_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "external_run_id",
            name="uq_model_runs_org_municipality_external",
        ),
    )
    op.create_index("ix_model_runs_org_municipality_status", "model_runs", ["organization_id", "municipality_id", "status"])

    op.create_table(
        "crash_records",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="SET NULL")),
        sa.Column("external_record_id", sa.String(length=240)),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("occurred_year", sa.Integer()),
        sa.Column("severity", sa.String(length=80)),
        sa.Column("road_name", sa.String(length=240)),
        _jsonb("raw_payload_json"),
        _jsonb("canonical_payload_json"),
        sa.Column("geom", Geometry("POINT", 4326), nullable=False),
        _created_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "external_record_id",
            name="uq_crash_records_org_municipality_external",
        ),
    )
    op.create_index("ix_crash_records_org_municipality_year", "crash_records", ["organization_id", "municipality_id", "occurred_year"])
    op.create_index("ix_crash_records_geom", "crash_records", ["geom"], postgresql_using="gist")

    op.create_table(
        "road_segments",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("segment_external_id", sa.String(length=240), nullable=False),
        sa.Column("road_name", sa.String(length=240)),
        sa.Column("road_class", sa.String(length=120)),
        sa.Column("speed_limit", sa.Numeric(8, 2)),
        sa.Column("length_m", sa.Numeric(12, 3)),
        _jsonb("properties_json"),
        sa.Column("geom", Geometry("LINESTRING", 4326), nullable=False),
        _created_at(),
        _updated_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "segment_external_id",
            name="uq_road_segments_org_municipality_external",
        ),
    )
    op.create_index("ix_road_segments_org_municipality", "road_segments", ["organization_id", "municipality_id"])
    op.create_index("ix_road_segments_geom", "road_segments", ["geom"], postgresql_using="gist")

    op.create_table(
        "road_nodes",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("node_external_id", sa.String(length=240), nullable=False),
        sa.Column("node_type", sa.String(length=120)),
        sa.Column("control_type", sa.String(length=120)),
        sa.Column("signal_id", sa.String(length=160)),
        _jsonb("properties_json"),
        sa.Column("geom", Geometry("POINT", 4326), nullable=False),
        _created_at(),
        _updated_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "node_external_id",
            name="uq_road_nodes_org_municipality_external",
        ),
    )
    op.create_index("ix_road_nodes_org_municipality", "road_nodes", ["organization_id", "municipality_id"])
    op.create_index("ix_road_nodes_geom", "road_nodes", ["geom"], postgresql_using="gist")

    op.create_table(
        "crossings",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("crossing_external_id", sa.String(length=240), nullable=False),
        sa.Column("crossing_type", sa.String(length=120)),
        sa.Column("protection_type", sa.String(length=120)),
        sa.Column("accessibility_score", sa.Numeric(8, 3)),
        _jsonb("properties_json"),
        sa.Column("geom", Geometry("POINT", 4326), nullable=False),
        _created_at(),
        _updated_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "crossing_external_id",
            name="uq_crossings_org_municipality_external",
        ),
    )
    op.create_index("ix_crossings_org_municipality", "crossings", ["organization_id", "municipality_id"])
    op.create_index("ix_crossings_geom", "crossings", ["geom"], postgresql_using="gist")

    op.create_table(
        "movement_objects",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("junction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("road_nodes.id", ondelete="SET NULL")),
        sa.Column("movement_external_id", sa.String(length=240), nullable=False),
        sa.Column("incoming_arm", sa.String(length=120)),
        sa.Column("outgoing_arm", sa.String(length=120)),
        sa.Column("movement_type", sa.String(length=120)),
        sa.Column("signal_phase_status", sa.String(length=120)),
        _jsonb("properties_json"),
        sa.Column("geom", Geometry("LINESTRING", 4326)),
        _created_at(),
        sa.UniqueConstraint(
            "organization_id",
            "municipality_id",
            "movement_external_id",
            name="uq_movement_objects_org_municipality_external",
        ),
    )
    op.create_index("ix_movement_objects_org_municipality", "movement_objects", ["organization_id", "municipality_id"])
    op.create_index("ix_movement_objects_geom", "movement_objects", ["geom"], postgresql_using="gist")

    op.create_table(
        "risk_scores",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("model_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score_external_id", sa.String(length=260), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_external_id", sa.String(length=260), nullable=False),
        sa.Column("occurred_year", sa.Integer()),
        sa.Column("risk_score", sa.Numeric(10, 4)),
        sa.Column("score_band", sa.String(length=40)),
        sa.Column("predicted_crashes", sa.Numeric(12, 4)),
        sa.Column("observed_crashes", sa.Numeric(12, 4)),
        sa.Column("severity_risk", sa.String(length=80)),
        sa.Column("confidence", sa.String(length=80)),
        _jsonb("explanation_json"),
        _jsonb("properties_json"),
        _created_at(),
        sa.UniqueConstraint("model_run_id", "object_type", "object_external_id", name="uq_risk_scores_run_object"),
    )
    op.create_index("ix_risk_scores_org_municipality_band", "risk_scores", ["organization_id", "municipality_id", "score_band"])
    op.create_index("ix_risk_scores_model_run_score", "risk_scores", ["model_run_id", "risk_score"])

    op.create_table(
        "public_risk_tiles",
        _uuid_pk(),
        _org_column(),
        _municipality_column(),
        sa.Column("model_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tile_external_id", sa.String(length=260), nullable=False),
        sa.Column("occurred_year", sa.Integer()),
        sa.Column("tile_size_m", sa.Numeric(12, 3)),
        sa.Column("risk_score", sa.Numeric(10, 4)),
        sa.Column("score_band", sa.String(length=40)),
        _jsonb("properties_json"),
        sa.Column("geom", Geometry("POLYGON", 4326), nullable=False),
        _created_at(),
        sa.UniqueConstraint("model_run_id", "tile_external_id", name="uq_public_risk_tiles_run_external"),
    )
    op.create_index("ix_public_risk_tiles_org_municipality_band", "public_risk_tiles", ["organization_id", "municipality_id", "score_band"])
    op.create_index("ix_public_risk_tiles_model_run_score", "public_risk_tiles", ["model_run_id", "risk_score"])
    op.create_index("ix_public_risk_tiles_geom", "public_risk_tiles", ["geom"], postgresql_using="gist")

    op.create_table(
        "scenario_runs",
        _uuid_pk(),
        _org_column(),
        _municipality_column(nullable=True, ondelete="SET NULL"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("scenario_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'draft'")),
        _jsonb("parameters_json"),
        sa.Column("baseline_score", sa.Numeric(12, 4)),
        sa.Column("projected_score", sa.Numeric(12, 4)),
        sa.Column("expected_benefit", sa.Numeric(12, 4)),
        sa.Column("confidence", sa.String(length=80)),
        _jsonb("result_json"),
        _created_at(),
        _updated_at(),
    )
    op.create_index("ix_scenario_runs_org_status", "scenario_runs", ["organization_id", "status"])
    op.create_index("ix_scenario_runs_org_municipality", "scenario_runs", ["organization_id", "municipality_id"])

    op.create_table(
        "interventions",
        _uuid_pk(),
        _org_column(),
        _municipality_column(nullable=True, ondelete="SET NULL"),
        sa.Column("scenario_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_runs.id", ondelete="SET NULL")),
        sa.Column("target_object_type", sa.String(length=80), nullable=False),
        sa.Column("target_object_id", sa.String(length=260), nullable=False),
        sa.Column("intervention_type", sa.String(length=160), nullable=False),
        sa.Column("cost_class", sa.String(length=80)),
        sa.Column("expected_benefit", sa.Numeric(12, 4)),
        sa.Column("priority_score", sa.Numeric(12, 4)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("source_kind", sa.String(length=120)),
        _jsonb("properties_json"),
        _created_at(),
        _updated_at(),
    )
    op.create_index("ix_interventions_org_status", "interventions", ["organization_id", "status"])
    op.create_index("ix_interventions_target", "interventions", ["target_object_type", "target_object_id"])


def downgrade() -> None:
    op.drop_index("ix_interventions_target", table_name="interventions")
    op.drop_index("ix_interventions_org_status", table_name="interventions")
    op.drop_table("interventions")
    op.drop_index("ix_scenario_runs_org_municipality", table_name="scenario_runs")
    op.drop_index("ix_scenario_runs_org_status", table_name="scenario_runs")
    op.drop_table("scenario_runs")
    op.drop_index("ix_public_risk_tiles_geom", table_name="public_risk_tiles")
    op.drop_index("ix_public_risk_tiles_model_run_score", table_name="public_risk_tiles")
    op.drop_index("ix_public_risk_tiles_org_municipality_band", table_name="public_risk_tiles")
    op.drop_table("public_risk_tiles")
    op.drop_index("ix_risk_scores_model_run_score", table_name="risk_scores")
    op.drop_index("ix_risk_scores_org_municipality_band", table_name="risk_scores")
    op.drop_table("risk_scores")
    op.drop_index("ix_movement_objects_geom", table_name="movement_objects")
    op.drop_index("ix_movement_objects_org_municipality", table_name="movement_objects")
    op.drop_table("movement_objects")
    op.drop_index("ix_crossings_geom", table_name="crossings")
    op.drop_index("ix_crossings_org_municipality", table_name="crossings")
    op.drop_table("crossings")
    op.drop_index("ix_road_nodes_geom", table_name="road_nodes")
    op.drop_index("ix_road_nodes_org_municipality", table_name="road_nodes")
    op.drop_table("road_nodes")
    op.drop_index("ix_road_segments_geom", table_name="road_segments")
    op.drop_index("ix_road_segments_org_municipality", table_name="road_segments")
    op.drop_table("road_segments")
    op.drop_index("ix_crash_records_geom", table_name="crash_records")
    op.drop_index("ix_crash_records_org_municipality_year", table_name="crash_records")
    op.drop_table("crash_records")
    op.drop_index("ix_model_runs_org_municipality_status", table_name="model_runs")
    op.drop_table("model_runs")
