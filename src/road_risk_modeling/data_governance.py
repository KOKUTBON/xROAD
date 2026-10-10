"""Data governance and usage rights (Issue 01).

This module formalizes the per-field classification matrix, per-source
licensing register, retention rules, and public-map redaction policy
that the rest of the platform was implicitly relying on.

It complements `governance_interoperability.py`:

- `governance_interoperability` covers source-family-level governance,
  artifact-role policies, DATEX-II alignment, and mobility-data-space
  handoff patterns
- this module (`data_governance`) covers the more granular layer Issue
  01 calls out: which canonical fields are public, internal,
  restricted, or sensitive; which sources are usable under which
  license; what each source can be retained for; and what may appear
  in a public map

The executable entrypoint is `road-risk build-data-governance-bundle`
which materializes the four matrices + a markdown report under
`data/governance/data_governance_bundle/` by default.

Tracked by: docs/implementation-issues.md (Issue 01).
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DATA_GOVERNANCE_BUNDLE_VERSION = "data_governance_bundle_v1"
DATA_GOVERNANCE_BUNDLE_CONTRACT_VERSION = "data_governance_bundle_public_v1"

DEFAULT_DATA_GOVERNANCE_OUTPUT_DIR = Path("data/governance/data_governance_bundle")


# ---------------------------------------------------------------------
# Classification labels
# ---------------------------------------------------------------------


CLASSIFICATION_PUBLIC = "public"
CLASSIFICATION_INTERNAL = "internal"
CLASSIFICATION_RESTRICTED = "restricted"
CLASSIFICATION_SENSITIVE = "sensitive"

CLASSIFICATION_LEVELS: tuple[str, ...] = (
    CLASSIFICATION_PUBLIC,
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_RESTRICTED,
    CLASSIFICATION_SENSITIVE,
)


@dataclass(slots=True)
class FieldClassification:
    field_name: str
    record_kind: str
    classification: str
    rationale: str
    publishable_in_aggregate: bool = False
    aggregation_floor: int | None = None
    role_visibility: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "record_kind": self.record_kind,
            "classification": self.classification,
            "rationale": self.rationale,
            "publishable_in_aggregate": bool(self.publishable_in_aggregate),
            "aggregation_floor": self.aggregation_floor,
            "role_visibility": list(self.role_visibility),
        }


# Field classification matrix for the canonical crash record (#2). The
# `record_kind` discriminator leaves room for future canonical
# entities (segments, junctions, scenarios) without needing a second
# table.
CANONICAL_CRASH_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="crash_id",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Synthetic identifier; safe internally, never published row-level.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source_system",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Identifies which adapter ingested the row; lineage metadata, not published.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source_record_id",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Original source identifier; some providers consider it a contractual key.",
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source_unique_key",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Provider-specific composite key; treated as restricted under provider terms.",
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source_member",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Internal archive member identifier (ZIP member); lineage metadata, not published.",
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source_row_number",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Row number in the source artifact; lineage metadata, not published.",
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_at",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Exact timestamp is rarely needed in public surfaces; risks identifying individuals.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_year",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Year of crash is safely publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_month",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Month-of-year is publicly publishable; monthly seasonal profiles are common in reports.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_day",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Day-of-month at row level combined with location risks re-identification.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_hour",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Hour-of-day is internal at row level but publishable in aggregate hourly profiles.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_minute",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Minute-of-hour adds re-identification risk; aggregate-only.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="timestamp_precision",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Tag describing temporal precision of the original record; metadata, not published.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="country_code",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Country code is publicly publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="region_code",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="ISTAT/NUTS region code is publicly publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="province_code",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="ISTAT province code is publicly publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="city_code",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="ISTAT city code is publicly publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="city_name",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Municipality name is publicly publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="latitude",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Row-level coordinates can re-identify involved parties. Publish only as aggregated "
            "tiles or segment-level summaries."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="longitude",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Row-level coordinates can re-identify involved parties. Publish only as aggregated "
            "tiles or segment-level summaries."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="road_segment_id",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Segment linkage is internal modeling state; segment-level aggregates are public.",
        publishable_in_aggregate=True,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="roadway_type",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Coarse roadway category (urban, extraurban, ramp) is publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="intersection_type",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Coarse intersection category (junction, ramp, mid-block) is publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="weather_code",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Weather at row level can interact with timestamp for re-identification.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="light_condition",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Light condition at row level joined with timestamp is identifying.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="fatalities",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Casualty counts at row level are sensitive to victims and families. Publish only "
            "via aggregated severity bands."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="injuries",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Same as fatalities: aggregate-only publication.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="severity_level",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Severity band is internal at row level but publishable as a per-segment summary.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="extra",
        record_kind="canonical_crash",
        classification=CLASSIFICATION_SENSITIVE,
        rationale=(
            "Free-form provider metadata can include personal narratives, vehicle plates, or "
            "victim notes. Never publish row-level; redact before any analyst export."
        ),
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
)


# Segment-score record (per-segment public + analyst published outputs).
SEGMENT_SCORE_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="segment_score_id",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Synthetic, prediction-run-scoped key; safe to publish for routing UI back into the API.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="segment_id",
        record_kind="segment_score",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Raw OSM-derived segment identifier; available to authenticated roles for joins, "
            "but not exposed on the public surface where the score_id alone is sufficient."
        ),
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="prediction_run_label",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Lineage tag pointing the consumer at the run that produced the score; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="prediction_task",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Modeling task label (frequency / severity); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_year",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Year the score covers; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="public_score_band",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Banded categorical score (very_high / high / ...); explicitly designed for public surfaces.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="public_score_index",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="0-100 normalized index; explicitly designed for public surfaces.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="score_decile",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Decile rank; publishable as a coarse summary.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="predicted_crash_count",
        record_kind="segment_score",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Model-predicted segment-year crash count; aggregable into public summaries but not "
            "published row-level alongside the banded score."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="observed_crash_count",
        record_kind="segment_score",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Per-segment observed crash counts inherit the canonical-crash restriction; surface "
            "only via banded scores or aggregate summaries that respect a five-row floor."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="prediction_column",
        record_kind="segment_score",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Source column name in the prediction store (e.g. `predicted_crash_count`); "
            "analyst CSV metadata, never published."
        ),
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="score_percentile",
        record_kind="segment_score",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Cohort percentile rank; analyst-only sort metadata, never published.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="score_rank_desc",
        record_kind="segment_score",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Descending rank within the cohort; analyst-only sort metadata, never published.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="segment_length_m",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Geometric length; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="name",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Street name; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="highway",
        record_kind="segment_score",
        classification=CLASSIFICATION_PUBLIC,
        rationale="OSM highway category; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
)


# Score-tile record (aggregated H3-style public score tiles).
SCORE_TILE_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="tile_score_id",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Synthetic tile identifier; safe to publish for UI routing back into the API.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_year",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Year the tile aggregate covers; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="prediction_run_label",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Lineage tag pointing to the prediction run; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="prediction_task",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Modeling task label (frequency / severity); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_size_m",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Tile edge length in metres; metadata, publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_segment_count",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale=(
            "Aggregation count; publishable for tiles meeting the five-row aggregation floor "
            "policy enforced upstream."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_mean_public_score_index",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Tile-level mean of the banded public-score index; explicitly designed for public surfaces.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_max_public_score_index",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Tile-level max of the banded public-score index; designed for public surfaces.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_public_score_band",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Banded categorical tile score (very_high / high / ...); designed for public surfaces.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="tile_score_decile",
        record_kind="score_tile",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Decile rank within the tile cohort; publishable as a coarse summary.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
)


# Node-year metric record (per-junction / per-crossing aggregates).
NODE_YEAR_METRIC_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="junction_id",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Junction identifier (municipal or OSM-derived); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="node_object_id",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Synthetic node object id; publishable for routing UI back to the API.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="node_role",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Coarse role (signal, crossing, approach, etc.); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="object_type",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Coarse object type; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="signal_type",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Signal type label; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="name",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Junction / crossing name; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="segment_id",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Linked segment id; available to authenticated roles for joins, not publicly surfaced.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="occurred_year",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Year the rollup covers; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="crash_count",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Per-node-year crash counts inherit the canonical-crash restriction; publish only "
            "above the five-row aggregation floor."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="injury_crash_count",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Casualty-bearing per-node counts; aggregate-only.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="fatal_crash_count",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Fatal-bearing per-node counts; aggregate-only.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="injuries_total",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Injury totals per node; aggregate-only.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="fatalities_total",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_RESTRICTED,
        rationale="Fatality totals per node; aggregate-only.",
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="nearest_segment_distance_m",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Quality-control distance metric; useful for analysts, not for public consumers.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="mean_node_match_distance_m",
        record_kind="node_year_metric",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Quality-control distance metric; useful for analysts, not for public consumers.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
)


# Crossing priority record (Bari crossing VRU exposure layer).
#
# The crossing-priority artifact carries 75 fields per crossing,
# combining identity, categorical/banded priority indices, modeling
# internals (movement-arm resolution, geometric bearings, parent
# linkage), and crash counts. Writing 75 full FieldClassification
# constructors would dominate the file, so three small helper
# factories below collapse each entry to one line.
#
# Default-deny invariant: a downstream caller of `_apply_matrix_filter`
# with role='public' drops any field whose role_visibility excludes
# 'public'. role='analyst' keeps every field in this matrix because
# every internal / restricted entry below explicitly lists 'analyst'
# in role_visibility.


_CROSSING_PUBLIC_ROLES: tuple[str, ...] = (
    "public", "municipality_viewer", "analyst", "data_operator", "admin",
)
_CROSSING_INTERNAL_ROLES: tuple[str, ...] = (
    "analyst", "data_operator", "admin",
)


def _public_crossing_field(name: str, rationale: str) -> FieldClassification:
    return FieldClassification(
        field_name=name,
        record_kind="crossing_priority",
        classification=CLASSIFICATION_PUBLIC,
        rationale=rationale,
        publishable_in_aggregate=True,
        role_visibility=_CROSSING_PUBLIC_ROLES,
    )


def _internal_crossing_field(name: str, rationale: str) -> FieldClassification:
    return FieldClassification(
        field_name=name,
        record_kind="crossing_priority",
        classification=CLASSIFICATION_INTERNAL,
        rationale=rationale,
        publishable_in_aggregate=False,
        role_visibility=_CROSSING_INTERNAL_ROLES,
    )


def _restricted_crossing_field(name: str, rationale: str) -> FieldClassification:
    return FieldClassification(
        field_name=name,
        record_kind="crossing_priority",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=rationale,
        publishable_in_aggregate=True,
        aggregation_floor=5,
        role_visibility=_CROSSING_INTERNAL_ROLES,
    )


CROSSING_PRIORITY_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    # Identity & location ---------------------------------------------------
    _public_crossing_field("crossing_id", "Synthetic crossing identifier; publishable for routing back to the API."),
    _public_crossing_field("crossing_name", "Crossing display name; publishable."),
    _public_crossing_field("node_object_id", "Synthetic node object id; publishable."),
    _public_crossing_field("junction_id", "Parent junction identifier; publishable."),
    _public_crossing_field("object_type", "Coarse object type label; publishable."),
    _public_crossing_field("node_role", "Coarse node role (crossing, approach, etc.); publishable."),
    _public_crossing_field("corridor_label", "Human-readable corridor label; publishable."),
    _public_crossing_field("name", "Junction / crossing name; publishable."),
    # Banded priority scores ------------------------------------------------
    _public_crossing_field("public_score_index", "Banded public-score index; explicitly designed for public surfaces."),
    _public_crossing_field("pedestrian_crossing_priority_rank", "Pedestrian-priority rank; publishable as a coarse summary."),
    _public_crossing_field("pedestrian_crossing_priority_score", "Pedestrian-priority composite score; publishable."),
    _public_crossing_field("ageing_crossing_priority_rank", "Ageing-population priority rank; publishable."),
    _public_crossing_field("ageing_crossing_priority_score", "Ageing-population priority composite score; publishable."),
    _public_crossing_field("ageing_user_exposure_index", "Banded ageing-user exposure index; publishable."),
    # Categorical state ----------------------------------------------------
    _public_crossing_field("control_state", "Coarse control state (controlled, uncontrolled, signalized, ...); publishable."),
    _public_crossing_field("control_detail", "Free-text control detail label; publishable."),
    _public_crossing_field("crossing_protection_state", "Coarse protection-state category; publishable."),
    _public_crossing_field("phase_priority_group", "Phase priority group label; publishable."),
    _public_crossing_field("priority_rule", "Priority rule label; publishable."),
    _public_crossing_field("maneuver_complexity", "Maneuver complexity label; publishable."),
    # Roadway attributes ---------------------------------------------------
    _public_crossing_field("maxspeed_kph", "Posted speed limit; publishable."),
    _public_crossing_field("lanes_count", "Lane count; publishable."),
    _public_crossing_field("road_class_label", "OSM road class label; publishable."),
    _public_crossing_field("road_class_rank", "Coarse road-class rank; publishable."),
    _public_crossing_field("segment_label", "Underlying segment label; publishable."),
    _public_crossing_field("segment_name", "Underlying segment name; publishable."),
    _public_crossing_field("segment_highway", "Underlying segment highway class; publishable."),
    _public_crossing_field("segment_ref", "Underlying segment reference label; publishable."),
    _public_crossing_field("segment_score_id", "Linked segment-score id; publishable for routing back into the segment_score surface."),
    # Banded exposure indices ----------------------------------------------
    _public_crossing_field("crossing_barrier_index", "Banded barrier index; publishable."),
    _public_crossing_field("crossing_continuity_gap_index", "Banded continuity-gap index; publishable."),
    _public_crossing_field("crossing_protection_gap_index", "Banded protection-gap index; publishable."),
    _public_crossing_field("micromobility_corridor_index", "Banded micromobility corridor index; publishable."),
    _public_crossing_field("retail_frontage_index", "Banded retail frontage index; publishable."),
    _public_crossing_field("school_frontage_index", "Banded school frontage index; publishable."),
    _public_crossing_field("transit_access_index", "Banded transit-access index; publishable."),
    # Aggregate counts -----------------------------------------------------
    _public_crossing_field("same_corridor_crossing_count", "Crossings on same corridor; aggregate publishable."),
    _public_crossing_field("same_corridor_protected_crossing_count", "Protected crossings on same corridor; aggregate publishable."),
    _public_crossing_field("same_segment_crossing_count", "Crossings on same segment; aggregate publishable."),
    _public_crossing_field("same_segment_protected_crossing_count", "Protected crossings on same segment; aggregate publishable."),
    # VRU bundle lineage ---------------------------------------------------
    _public_crossing_field("vru_exposure_bundle_version", "Lineage tag for VRU exposure bundle; publishable."),
    _public_crossing_field("vru_exposure_layer_kind", "VRU exposure layer kind; publishable."),
    _public_crossing_field("vru_exposure_source", "VRU exposure source label; publishable."),
    # Crash counts (sensitive) ---------------------------------------------
    _restricted_crossing_field(
        "observed_crash_count",
        "Per-crossing observed crash count; aggregate-only and analyst-visible at row level.",
    ),
    _internal_crossing_field(
        "predicted_crash_count",
        "Model-predicted per-crossing crash count; analyst-visible at row level, not published.",
    ),
    # Internal modeling lineage --------------------------------------------
    _internal_crossing_field("segment_id", "Raw OSM segment id; analyst-only join key."),
    _internal_crossing_field("source_system", "Adapter identifier; lineage metadata, analyst-only."),
    _internal_crossing_field("parent_object_id", "Parent object id; lineage metadata."),
    _internal_crossing_field("parent_object_type", "Parent object type label; lineage metadata."),
    _internal_crossing_field("movement_source_parent_object_id", "Movement source parent id; lineage metadata."),
    _internal_crossing_field("movement_source_zone_id", "Movement source zone id; lineage metadata."),
    _internal_crossing_field("movement_source_zone_type", "Movement source zone type; lineage metadata."),
    _internal_crossing_field("segment_junction", "Segment junction tag; modeling lineage."),
    _internal_crossing_field("approach_node_ref", "Approach node reference; modeling lineage."),
    # Internal movement details --------------------------------------------
    _internal_crossing_field("incoming_arm_id", "Incoming-arm identifier; movement-modeling internals."),
    _internal_crossing_field("outgoing_arm_id", "Outgoing-arm identifier; movement-modeling internals."),
    _internal_crossing_field("incoming_bearing_deg", "Incoming-arm bearing in degrees; movement-modeling internals."),
    _internal_crossing_field("outgoing_bearing_deg", "Outgoing-arm bearing in degrees; movement-modeling internals."),
    _internal_crossing_field("incoming_compass", "Incoming-arm compass direction; movement-modeling internals."),
    _internal_crossing_field("outgoing_compass", "Outgoing-arm compass direction; movement-modeling internals."),
    _internal_crossing_field("candidate_target_arm_catalog", "Candidate target-arm catalog; movement-modeling internals."),
    _internal_crossing_field("candidate_target_arm_count", "Candidate target-arm count; movement-modeling internals."),
    _internal_crossing_field("movement_arm_count", "Movement arm count; modeling internal."),
    _internal_crossing_field("movement_family", "Movement family label; modeling internal."),
    _internal_crossing_field("movement_resolution_method", "Movement resolution method; modeling internal."),
    _internal_crossing_field("movement_resolution_state", "Movement resolution state; modeling internal."),
    _internal_crossing_field("movement_role", "Movement role; modeling internal."),
    _internal_crossing_field("movement_turn", "Movement turn category; modeling internal."),
    _internal_crossing_field("movement_target_continuity_flags", "Movement target continuity flags; modeling internal."),
    _internal_crossing_field("movement_target_heading_delta_deg", "Movement target heading delta; modeling internal."),
    _internal_crossing_field("movement_target_rank", "Movement target rank; modeling internal."),
    _internal_crossing_field("movement_target_score", "Movement target score; modeling internal."),
    _internal_crossing_field("roundabout_component_role", "Roundabout component role; modeling internal."),
    _internal_crossing_field("signal_priority_variant", "Signal priority variant label; modeling internal."),
    _internal_crossing_field("turn_path_class", "Turn-path class label; modeling internal."),
)


# Scenario record (scenario_countermeasures output).
SCENARIO_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="scenario_id",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Synthetic scenario id; publishable for routing UI back to the API.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="scenario_rank",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Ranking position within a city scenario bundle; analyst-only because the rank "
            "leaks the relative ordering of other scenarios that may not be publishable in "
            "their own right."
        ),
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="intervention_code",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Intervention archetype code; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="title",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Qualitative scenario title (e.g. 'Reduce operating speeds on Tangenziale di Bari'); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="target_context_label",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Human-readable target context (corridor, junction label); publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="target_context_key",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Machine-readable target context key; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="expected_relative_reduction",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Expected percent reduction; explicitly designed for public intervention briefs.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="expected_crash_reduction",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Absolute expected crash reduction; published only as a banded value on public briefs, "
            "exact value available to analysts."
        ),
        publishable_in_aggregate=True,
        aggregation_floor=1,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="expected_crash_reduction_low",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Low-end of expected reduction confidence band; analyst-only.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="expected_crash_reduction_high",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="High-end of expected reduction confidence band; analyst-only.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="baseline_predicted_crash_total",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Baseline predicted total used in the counterfactual; analyst-only.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="counterfactual_predicted_crash_total",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Counterfactual predicted total; analyst-only.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="linked_segment_count",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Count of segments touched by the scenario; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="target_asset_count",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Count of target assets; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="target_asset_types",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="List of target asset type labels; publishable.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="linked_segment_score_ids",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Linked segment-score id list; analyst-only, exposes per-segment lineage.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="affected_assets",
        record_kind="scenario",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Affected asset list with per-asset segment ids; analyst-only.",
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="assumptions",
        record_kind="scenario",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Free-text assumption list; publishable for intervention briefs.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
)


# Report record (operational report metadata, surfaced via reports/).
#
# A report record has two distinct surfaces:
#   - The public listing (`list_public_reports`) for reports promoted to
#     `visibility_tier="public"` + `status="published"`. Only fields with
#     `public` in their role_visibility flow through. The repository layer
#     pre-filters to publishable reports, so any field reaching the
#     filter here is from an already-public report.
#   - The authenticated listing (`list_report_history`) for any report
#     in an organization. Internal-classified fields flow through to
#     analyst/data_operator/admin roles; `file_storage_uri` is
#     `restricted` to data_operator/admin only.
REPORT_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="report_id",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Synthetic report id (UUID). Publishable on the public listing for "
            "routing UI back to the public download endpoint; the id is opaque "
            "and reveals no PII."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="organization_id",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Organization scope. Deliberately NOT public-visible: the public "
            "listing is scoped by city, never by org, so leaking org ids "
            "through the listing payload would let an outside reader correlate "
            "publicly-published reports back to their producing organization."
        ),
        publishable_in_aggregate=False,
        role_visibility=("municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="title",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Report title. Public-visible because the title is what the public "
            "listing displays as a row label."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="report_type",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Report type tag. Public-visible so the listing can filter / group by type.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="output_format",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale="File output format (pdf, xlsx, csv, md). Public-visible so the listing shows the download type.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="visibility_tier",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Visibility tier of the report itself. Public-visible because for any "
            "report appearing on the public listing the tier is by definition `public`."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="status",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Report generation status. Public-visible because for any report "
            "appearing on the public listing the status is by definition `published`."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="file_storage_uri",
        record_kind="report",
        classification=CLASSIFICATION_RESTRICTED,
        rationale=(
            "Storage URI for the generated report file. Restricted because the URI "
            "can leak the object-store layout if surfaced beyond the report owners. "
            "Analyst callers receive a temporary presigned URL via the `access` block "
            "of the download endpoint, never the raw URI."
        ),
        publishable_in_aggregate=False,
        role_visibility=("data_operator", "admin"),
    ),
    FieldClassification(
        field_name="created_at",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Creation timestamp; authenticated roles only. The public listing "
            "uses `published_at` / `generated_at` for time labels instead, since "
            "`created_at` reveals an internal scheduling artefact (draft creation)."
        ),
        publishable_in_aggregate=False,
        role_visibility=("municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="generated_at",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Generation timestamp. Public-visible so the listing can show 'as of' / freshness.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    # --- Fields previously emitted by `_serialize_report` without classification ---
    FieldClassification(
        field_name="city_key",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "City scope of the report. Public-visible because the public listing "
            "is already scoped by city (the URL contains the city key)."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="audience",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Intended-audience tag (e.g. 'executive', 'operations'). Internal "
            "because it reflects authoring choices that aren't part of the public "
            "report contract."
        ),
        publishable_in_aggregate=False,
        role_visibility=("municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="summary",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Free-form report summary dict that may include municipality references "
            "and review-state hints. Authenticated roles only."
        ),
        publishable_in_aggregate=False,
        role_visibility=("municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="review_state",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Editorial review state derived from `status`. Internal because it "
            "reveals the in-progress editorial workflow."
        ),
        publishable_in_aggregate=False,
        role_visibility=("municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="publication_state",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Derived publication state (public / published_internal / archived / "
            "not_published). Public-visible because for any report on the public "
            "listing the state is by definition `public`."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="download_state",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Whether the report file is ready for download. Public-visible so the "
            "listing can show 'available' vs 'pending'."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="lifecycle_actions",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Hints which mutation actions the caller could take (review, publish, "
            "archive). Internal AND restricted to roles that can actually mutate: "
            "analyst, data_operator, admin. NOT visible to municipality_viewer or "
            "public because the actions imply mutation rights they don't have."
        ),
        publishable_in_aggregate=False,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="published_at",
        record_kind="report",
        classification=CLASSIFICATION_INTERNAL,
        rationale=(
            "Publication timestamp. Public-visible because for any report on the "
            "public listing the publication has by definition happened."
        ),
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
)


# Aggregate registry indexed by record_kind.
RECORD_KIND_CLASSIFICATIONS: dict[str, tuple[FieldClassification, ...]] = {
    "canonical_crash": CANONICAL_CRASH_FIELD_CLASSIFICATIONS,
    "segment_score": SEGMENT_SCORE_FIELD_CLASSIFICATIONS,
    "score_tile": SCORE_TILE_FIELD_CLASSIFICATIONS,
    "node_year_metric": NODE_YEAR_METRIC_FIELD_CLASSIFICATIONS,
    "crossing_priority": CROSSING_PRIORITY_FIELD_CLASSIFICATIONS,
    "scenario": SCENARIO_FIELD_CLASSIFICATIONS,
    "report": REPORT_FIELD_CLASSIFICATIONS,
}


# Flat tuple over every registered record-kind classification, for
# downstream consumers (e.g. CSV materializer) that want one stream.
ALL_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = tuple(
    entry
    for entries in RECORD_KIND_CLASSIFICATIONS.values()
    for entry in entries
)


# ---------------------------------------------------------------------
# Source licensing register
# ---------------------------------------------------------------------


@dataclass(slots=True)
class SourceLicense:
    source_family_id: str
    source_name: str
    provider: str
    license_id: str
    license_name: str
    license_url: str
    attribution_required: bool
    attribution_text: str | None
    share_alike: bool
    commercial_use: str
    redistribution: str
    terms_summary: str
    publication_status: str
    legal_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_family_id": self.source_family_id,
            "source_name": self.source_name,
            "provider": self.provider,
            "license_id": self.license_id,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "attribution_required": bool(self.attribution_required),
            "attribution_text": self.attribution_text,
            "share_alike": bool(self.share_alike),
            "commercial_use": self.commercial_use,
            "redistribution": self.redistribution,
            "terms_summary": self.terms_summary,
            "publication_status": self.publication_status,
            "legal_status": self.legal_status,
        }


SOURCE_LICENSING_REGISTER: tuple[SourceLicense, ...] = (
    SourceLicense(
        source_family_id="bari_open_data_crashes",
        source_name="Comune di Bari crashes open data",
        provider="Comune di Bari",
        license_id="cc-by-4.0",
        license_name="Creative Commons Attribution 4.0 International",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution_required=True,
        attribution_text="Comune di Bari - Dati Aperti",
        share_alike=False,
        commercial_use="allowed_with_attribution",
        redistribution="allowed_with_attribution",
        terms_summary=(
            "Bari municipal open data published under CC-BY 4.0. Row-level redistribution "
            "requires attribution; derived public statistics can be redistributed under the "
            "same notice."
        ),
        publication_status="public_source_with_restricted_row_level_reuse_review",
        legal_status="approved",
    ),
    SourceLicense(
        source_family_id="puglia_cleaned_crashes",
        source_name="Puglia cleaned legacy crash dataset",
        provider="Internal legacy archive",
        license_id="internal-archive-v1",
        license_name="Internal research-only archive",
        license_url="docs/legacy-assets.md",
        attribution_required=False,
        attribution_text=None,
        share_alike=False,
        commercial_use="not_permitted",
        redistribution="internal_only",
        terms_summary=(
            "Legacy ZIP archive provided for internal research only. Do not republish raw rows; "
            "publish only governance-cleared statistical summaries."
        ),
        publication_status="internal_only",
        legal_status="approved_internal",
    ),
    SourceLicense(
        source_family_id="osm_road_network",
        source_name="OpenStreetMap road network extracts",
        provider="OpenStreetMap contributors",
        license_id="odbl-1.0",
        license_name="Open Database License 1.0",
        license_url="https://opendatacommons.org/licenses/odbl/1-0/",
        attribution_required=True,
        attribution_text="© OpenStreetMap contributors",
        share_alike=True,
        commercial_use="allowed_with_attribution_and_share_alike",
        redistribution="allowed_with_attribution_and_share_alike",
        terms_summary=(
            "OSM data is ODbL 1.0. Derived databases must preserve attribution and may trigger "
            "share-alike obligations; check before publishing enriched derivatives."
        ),
        publication_status="public_source_with_share_alike_review",
        legal_status="approved",
    ),
    SourceLicense(
        source_family_id="motorized_exposure_connector_v1",
        source_name="Motor-flow connector (floating-car + counter)",
        provider="Provider or municipal traffic office (per connector)",
        license_id="provider-specific",
        license_name="Provider-specific contract",
        license_url="data/planning/exposure_connector_intake/source_rights_matrix.csv",
        attribution_required=False,
        attribution_text=None,
        share_alike=False,
        commercial_use="provider_review_required",
        redistribution="restricted_input_public_summary_only",
        terms_summary=(
            "Motor-flow connector inputs are restricted under per-provider contracts. Only "
            "approved aggregates may surface publicly; row-level redistribution is prohibited."
        ),
        publication_status="restricted_input_public_summary_only",
        legal_status="pending_provider_terms",
    ),
    SourceLicense(
        source_family_id="observed_speed_connector_v1",
        source_name="Observed-speed connector (probe + fixed counter)",
        provider="Provider or municipal traffic office (per connector)",
        license_id="provider-specific",
        license_name="Provider-specific contract",
        license_url="data/planning/exposure_connector_intake/source_rights_matrix.csv",
        attribution_required=False,
        attribution_text=None,
        share_alike=False,
        commercial_use="provider_review_required",
        redistribution="restricted_input_public_summary_only",
        terms_summary=(
            "Observed-speed inputs follow the same provider-contract pattern as motor flow. "
            "Public surfaces expose only governance-approved aggregates."
        ),
        publication_status="restricted_input_public_summary_only",
        legal_status="pending_provider_terms",
    ),
    SourceLicense(
        source_family_id="bari_signal_phase_provider_data",
        source_name="Bari signal-phase provider stage / controller / mapping data",
        provider="Municipal traffic office",
        license_id="municipal-stage-plan-v1",
        license_name="Municipal stage-plan delivery (per request)",
        license_url="data/planning/signal_phase_requests/bari/signal_phase_request_pack.manifest.json",
        attribution_required=False,
        attribution_text=None,
        share_alike=False,
        commercial_use="not_permitted",
        redistribution="restricted_input_public_derivatives_only",
        terms_summary=(
            "Signal-phase data is delivered per request under municipal terms. Only mapped "
            "derivatives may surface; raw stage / controller files stay restricted."
        ),
        publication_status="restricted_input_public_derivatives_only",
        legal_status="approved_per_request",
    ),
    SourceLicense(
        source_family_id="datex_ii_live_event_feed",
        source_name="DATEX-II live traffic / event feed (planned)",
        provider="National or regional traffic operator",
        license_id="datex-ii-provider-terms",
        license_name="DATEX-II provider terms",
        license_url="https://www.datex2.eu/",
        attribution_required=False,
        attribution_text=None,
        share_alike=False,
        commercial_use="provider_review_required",
        redistribution="restricted_input_public_event_summary_optional",
        terms_summary=(
            "DATEX-II inputs follow the operator's published terms; only event summaries (not "
            "raw situation messages) are eligible for public-map exposure."
        ),
        publication_status="restricted_input_public_event_summary_optional",
        legal_status="pending_operator_terms",
    ),
)


# ---------------------------------------------------------------------
# Retention rules
# ---------------------------------------------------------------------


@dataclass(slots=True)
class RetentionRule:
    data_class: str
    retention_target: str
    rationale: str
    deletion_trigger: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_class": self.data_class,
            "retention_target": self.retention_target,
            "rationale": self.rationale,
            "deletion_trigger": self.deletion_trigger,
        }


RETENTION_RULES: tuple[RetentionRule, ...] = (
    RetentionRule(
        data_class="canonical_crash_rows",
        retention_target="indefinite_with_quality_review",
        rationale=(
            "Canonical crash rows underpin every long-horizon transferability run; the row "
            "set is small and not personally identifying after extra-field redaction."
        ),
        deletion_trigger="explicit governance request or upstream-source revocation",
    ),
    RetentionRule(
        data_class="provider_raw_exports",
        retention_target="purge_after_normalization",
        rationale=(
            "Provider raw exports are kept only long enough to validate normalization; once "
            "canonical rows pass curation, the raw exports are purged."
        ),
        deletion_trigger="successful curation run + 30 days quarantine window",
    ),
    RetentionRule(
        data_class="motor_flow_observations",
        retention_target="provider_terms_or_24_months_max",
        rationale="Motor-flow inputs follow provider contracts; default cap is 24 months.",
        deletion_trigger="provider terms reached or 24 months whichever is earlier",
    ),
    RetentionRule(
        data_class="observed_speed_observations",
        retention_target="provider_terms_or_24_months_max",
        rationale="Observed-speed inputs follow provider contracts; default cap is 24 months.",
        deletion_trigger="provider terms reached or 24 months whichever is earlier",
    ),
    RetentionRule(
        data_class="signal_phase_provider_data",
        retention_target="while_plan_is_current",
        rationale="Stage plans and controller events are useful only while the control plan is live.",
        deletion_trigger="plan supersession or 12 months of inactivity",
    ),
    RetentionRule(
        data_class="published_artifacts",
        retention_target="indefinite_with_lineage",
        rationale="Published artifacts must be reproducible; retention is tied to lineage records.",
        deletion_trigger="lineage broken or upstream artifact retracted",
    ),
    RetentionRule(
        data_class="audit_logs",
        retention_target="24_months",
        rationale="Audit logs balance forensic needs against minimization principles.",
        deletion_trigger="rolling 24-month window",
    ),
    RetentionRule(
        data_class="ingestion_job_records",
        retention_target="indefinite_with_aggregation_after_24_months",
        rationale="Job records support reproducibility; older entries can be rolled up into monthly aggregates.",
        deletion_trigger="rolling 24-month detail window; aggregation thereafter",
    ),
)


# ---------------------------------------------------------------------
# Public-map redaction policy
# ---------------------------------------------------------------------


@dataclass(slots=True)
class PublicMapPolicy:
    surface_id: str
    surface_label: str
    minimum_aggregation_floor: int
    publishable_fields: tuple[str, ...]
    redacted_fields: tuple[str, ...]
    notes: str
    # Discriminator: which record kind from RECORD_KIND_CLASSIFICATIONS
    # this policy is anchored to. When the kind is registered in the
    # matrix, cross-policy invariants in tests fire to ensure the
    # policy's classification of any matrix-known field is consistent
    # with the matrix entry. Policies for aggregations that do not
    # cleanly map to a single record kind (e.g. score tiles, which
    # aggregate segments) declare a record_kind that is not in the
    # matrix; the cross-policy invariant skips them until that kind is
    # registered.
    record_kind: str = "canonical_crash"

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_label": self.surface_label,
            "minimum_aggregation_floor": self.minimum_aggregation_floor,
            "publishable_fields": list(self.publishable_fields),
            "redacted_fields": list(self.redacted_fields),
            "notes": self.notes,
            "record_kind": self.record_kind,
        }

    @property
    def is_matrix_tracked(self) -> bool:
        """True iff this policy's record_kind is registered in the matrix."""
        return self.record_kind in RECORD_KIND_CLASSIFICATIONS


PUBLIC_MAP_POLICIES: tuple[PublicMapPolicy, ...] = (
    PublicMapPolicy(
        surface_id="public_segment_score_map",
        surface_label="Public segment-score map",
        minimum_aggregation_floor=5,
        record_kind="segment_score",
        publishable_fields=(
            "segment_score_id",
            "public_score_index",
            "public_score_band",
            "occurred_year",
            "prediction_run_label",
            "prediction_task",
            "score_decile",
            "segment_length_m",
            "name",
            "highway",
        ),
        redacted_fields=(
            "segment_id",
            "predicted_crash_count",
            "observed_crash_count",
        ),
        notes=(
            "Segment-level scoring uses banded indices and the synthetic "
            "segment_score_id, never the raw OSM segment_id or row-level "
            "crash counts. Geometry stays public via the published "
            "GeoJSON, but contributing row metadata does not."
        ),
    ),
    PublicMapPolicy(
        surface_id="public_score_tiles",
        surface_label="Public score tiles",
        minimum_aggregation_floor=5,
        record_kind="score_tile",
        publishable_fields=(
            "tile_score_id",
            "occurred_year",
            "prediction_run_label",
            "prediction_task",
            "tile_size_m",
            "tile_segment_count",
            "tile_mean_public_score_index",
            "tile_max_public_score_index",
            "tile_public_score_band",
            "tile_score_decile",
        ),
        redacted_fields=(
            # Defensive watch list of fields that would be sensitive if
            # they ever appeared in the tile artifact. None of them is
            # currently in the score_tile matrix, so the cross-policy
            # invariant does not enforce them - but they are kept here
            # so future code that generates new tile properties cannot
            # silently surface raw row-level data.
            "segment_ids",
            "crash_counts",
            "fatalities",
            "injuries",
            "latitude",
            "longitude",
        ),
        notes=(
            "Tile aggregations enforce a five-crash floor; below that they emit a 'low_volume' "
            "band rather than a numeric score. The 10-field publishable list is the exact "
            "intersection of the score_tile matrix and the current tile artifact contract; the "
            "redacted list is a forward-looking watch list of fields that would be sensitive "
            "if a future tile generator surfaced them."
        ),
    ),
    PublicMapPolicy(
        surface_id="public_intervention_brief",
        surface_label="Public intervention brief",
        minimum_aggregation_floor=5,
        record_kind="scenario",
        publishable_fields=(
            "scenario_id",
            "intervention_code",
            "title",
            "target_context_label",
            "expected_relative_reduction",
        ),
        redacted_fields=(
            "linked_segment_score_ids",
            "affected_assets",
            "expected_crash_reduction",
            "expected_crash_reduction_low",
            "expected_crash_reduction_high",
            "baseline_predicted_crash_total",
            "counterfactual_predicted_crash_total",
        ),
        notes=(
            "Public briefs share the qualitative recommendation and a banded expected "
            "relative reduction; the absolute crash-reduction figure and its confidence "
            "interval, plus the underlying scenario asset list, stay analyst-only."
        ),
    ),
)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def field_classification_for(
    field_name: str, *, record_kind: str = "canonical_crash",
) -> FieldClassification:
    """Return the classification for one canonical field.

    Looks up the field in the registered record-kind matrix. Raises
    `KeyError` if the field is not registered; callers should catch +
    report rather than silently default to "public".
    """
    entries = RECORD_KIND_CLASSIFICATIONS.get(record_kind)
    if entries is None:
        raise KeyError(
            f"Unknown record_kind '{record_kind}'. "
            f"Known kinds: {sorted(RECORD_KIND_CLASSIFICATIONS.keys())}"
        )
    for entry in entries:
        if entry.field_name == field_name:
            return entry
    raise KeyError(
        f"No data-governance classification registered for {record_kind}.{field_name}"
    )


def classifications_for_record_kind(record_kind: str) -> tuple[FieldClassification, ...]:
    """Return every classification for one record kind.

    Raises `KeyError` if the record kind is not registered.
    """
    try:
        return RECORD_KIND_CLASSIFICATIONS[record_kind]
    except KeyError as exc:
        raise KeyError(
            f"Unknown record_kind '{record_kind}'. "
            f"Known kinds: {sorted(RECORD_KIND_CLASSIFICATIONS.keys())}"
        ) from exc


def is_field_publishable_for_role(
    field_name: str, *, record_kind: str, role: str,
) -> bool:
    """Return True iff the field's `role_visibility` includes `role`.

    Raises `KeyError` if the field is not registered, so callers cannot
    silently get a default "publishable" answer for an unknown field.
    """
    classification = field_classification_for(field_name, record_kind=record_kind)
    return role in classification.role_visibility


def publishable_fields_for_role(record_kind: str, role: str) -> tuple[str, ...]:
    """Return every field of `record_kind` whose `role_visibility` includes `role`."""
    return tuple(
        entry.field_name
        for entry in classifications_for_record_kind(record_kind)
        if role in entry.role_visibility
    )


def licenses_by_publication_status(*statuses: str) -> tuple[SourceLicense, ...]:
    selected = set(statuses)
    return tuple(s for s in SOURCE_LICENSING_REGISTER if s.publication_status in selected)


def public_map_redactable_fields() -> set[str]:
    """Union of every field redacted from at least one public surface."""
    redacted: set[str] = set()
    for policy in PUBLIC_MAP_POLICIES:
        redacted.update(policy.redacted_fields)
    return redacted


def field_classification_index() -> dict[str, FieldClassification]:
    """Quick lookup keyed by `{record_kind}.{field_name}` across every record kind."""
    return {
        f"{entry.record_kind}.{entry.field_name}": entry
        for entry in ALL_FIELD_CLASSIFICATIONS
    }


def record_kind_index() -> dict[str, dict[str, FieldClassification]]:
    """Nested index: record_kind -> field_name -> FieldClassification."""
    return {
        record_kind: {entry.field_name: entry for entry in entries}
        for record_kind, entries in RECORD_KIND_CLASSIFICATIONS.items()
    }


def license_register_index() -> dict[str, SourceLicense]:
    return {entry.source_family_id: entry for entry in SOURCE_LICENSING_REGISTER}


# ---------------------------------------------------------------------
# Bundle output
# ---------------------------------------------------------------------


def _csv_string(values: Iterable[Any]) -> str:
    return ";".join(str(v) for v in values)


def _now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            normalized = {key: row.get(key, "") for key in fieldnames}
            writer.writerow(normalized)


def _classification_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in ALL_FIELD_CLASSIFICATIONS:
        row = entry.to_dict()
        row["role_visibility"] = _csv_string(row.get("role_visibility") or [])
        rows.append(row)
    return rows


def _license_csv_rows() -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in SOURCE_LICENSING_REGISTER]


def _retention_csv_rows() -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in RETENTION_RULES]


def _public_map_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in PUBLIC_MAP_POLICIES:
        row = entry.to_dict()
        row["publishable_fields"] = _csv_string(row.get("publishable_fields") or [])
        row["redacted_fields"] = _csv_string(row.get("redacted_fields") or [])
        rows.append(row)
    return rows


def _markdown_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Data Governance Bundle")
    lines.append("")
    lines.append(
        f"Generated at: `{payload.get('generated_at_utc', 'unknown')}` "
        f"(bundle `{payload.get('data_governance_bundle_version')}`)"
    )
    lines.append("")
    lines.append("## Classification matrix totals")
    totals = payload.get("stats", {})
    lines.append(f"- field rows: `{totals.get('field_classification_count', 0)}`")
    lines.append(f"- source licenses: `{totals.get('source_license_count', 0)}`")
    lines.append(f"- retention rules: `{totals.get('retention_rule_count', 0)}`")
    lines.append(f"- public-map policies: `{totals.get('public_map_policy_count', 0)}`")
    lines.append("")
    lines.append("## Per-class field counts")
    for klass, count in (totals.get("field_classification_by_class") or {}).items():
        lines.append(f"- `{klass}`: {count}")
    lines.append("")
    lines.append("## Per-record-kind field counts")
    for record_kind, count in (totals.get("field_classification_by_record_kind") or {}).items():
        lines.append(f"- `{record_kind}`: {count}")
    lines.append("")
    lines.append("## Sources by publication status")
    for status, count in (totals.get("sources_by_publication_status") or {}).items():
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## Public-map surfaces")
    for surface in payload.get("public_map_policies", []):
        lines.append(f"- `{surface['surface_id']}`: floor `{surface['minimum_aggregation_floor']}`")
    lines.append("")
    lines.append(
        "See `docs/data-governance.md` for the canonical narrative description of these "
        "matrices and their downstream contracts."
    )
    lines.append("")
    return "\n".join(lines)


def build_data_governance_bundle(
    *,
    output_dir: str | Path = DEFAULT_DATA_GOVERNANCE_OUTPUT_DIR,
) -> dict[str, Any]:
    """Materialize the four matrices + a markdown report under `output_dir`."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    classification_rows = _classification_csv_rows()
    license_rows = _license_csv_rows()
    retention_rows = _retention_csv_rows()
    public_map_rows = _public_map_csv_rows()

    _write_csv(output_root / "data_classification_matrix.csv", classification_rows)
    _write_csv(output_root / "source_licensing_register.csv", license_rows)
    _write_csv(output_root / "retention_rules.csv", retention_rows)
    _write_csv(output_root / "public_map_policy.csv", public_map_rows)

    by_class: dict[str, int] = {}
    for row in classification_rows:
        klass = row.get("classification") or "unspecified"
        by_class[klass] = by_class.get(klass, 0) + 1
    by_record_kind: dict[str, int] = {}
    for row in classification_rows:
        record_kind = row.get("record_kind") or "unspecified"
        by_record_kind[record_kind] = by_record_kind.get(record_kind, 0) + 1
    by_pub_status: dict[str, int] = {}
    for row in license_rows:
        status = row.get("publication_status") or "unspecified"
        by_pub_status[status] = by_pub_status.get(status, 0) + 1

    stats = {
        "field_classification_count": len(classification_rows),
        "source_license_count": len(license_rows),
        "retention_rule_count": len(retention_rows),
        "public_map_policy_count": len(public_map_rows),
        "field_classification_by_class": by_class,
        "field_classification_by_record_kind": by_record_kind,
        "sources_by_publication_status": by_pub_status,
    }

    payload: dict[str, Any] = {
        "data_governance_bundle_version": DATA_GOVERNANCE_BUNDLE_VERSION,
        "data_governance_bundle_contract_version": DATA_GOVERNANCE_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": _now_utc_iso(),
        "classification_levels": list(CLASSIFICATION_LEVELS),
        "record_kinds": sorted(RECORD_KIND_CLASSIFICATIONS.keys()),
        "field_classification_matrix": classification_rows,
        "source_licensing_register": license_rows,
        "retention_rules": retention_rows,
        "public_map_policies": public_map_rows,
        "stats": stats,
    }

    bundle_path = output_root / "data_governance_bundle.json"
    bundle_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8",
    )

    manifest_path = output_root / "data_governance_bundle.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data_governance_bundle_version": DATA_GOVERNANCE_BUNDLE_VERSION,
                "data_governance_bundle_contract_version": DATA_GOVERNANCE_BUNDLE_CONTRACT_VERSION,
                "generated_at_utc": payload["generated_at_utc"],
                "bundle_path": str(bundle_path),
                "data_classification_matrix_path": str(
                    output_root / "data_classification_matrix.csv"
                ),
                "source_licensing_register_path": str(
                    output_root / "source_licensing_register.csv"
                ),
                "retention_rules_path": str(output_root / "retention_rules.csv"),
                "public_map_policy_path": str(output_root / "public_map_policy.csv"),
                "report_path": str(output_root / "data_governance_bundle.md"),
                "stats": stats,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report_path = output_root / "data_governance_bundle.md"
    report_path.write_text(_markdown_report(payload), encoding="utf-8")

    return payload


__all__ = [
    "ALL_FIELD_CLASSIFICATIONS",
    "CANONICAL_CRASH_FIELD_CLASSIFICATIONS",
    "CROSSING_PRIORITY_FIELD_CLASSIFICATIONS",
    "CLASSIFICATION_INTERNAL",
    "CLASSIFICATION_LEVELS",
    "CLASSIFICATION_PUBLIC",
    "CLASSIFICATION_RESTRICTED",
    "CLASSIFICATION_SENSITIVE",
    "DATA_GOVERNANCE_BUNDLE_CONTRACT_VERSION",
    "DATA_GOVERNANCE_BUNDLE_VERSION",
    "DEFAULT_DATA_GOVERNANCE_OUTPUT_DIR",
    "FieldClassification",
    "NODE_YEAR_METRIC_FIELD_CLASSIFICATIONS",
    "PUBLIC_MAP_POLICIES",
    "PublicMapPolicy",
    "RECORD_KIND_CLASSIFICATIONS",
    "REPORT_FIELD_CLASSIFICATIONS",
    "RETENTION_RULES",
    "RetentionRule",
    "SCENARIO_FIELD_CLASSIFICATIONS",
    "SCORE_TILE_FIELD_CLASSIFICATIONS",
    "SEGMENT_SCORE_FIELD_CLASSIFICATIONS",
    "SOURCE_LICENSING_REGISTER",
    "SourceLicense",
    "build_data_governance_bundle",
    "classifications_for_record_kind",
    "field_classification_for",
    "field_classification_index",
    "is_field_publishable_for_role",
    "license_register_index",
    "licenses_by_publication_status",
    "public_map_redactable_fields",
    "publishable_fields_for_role",
    "record_kind_index",
]
