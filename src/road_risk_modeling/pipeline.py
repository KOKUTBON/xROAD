"""Default pipeline stages for the platform build-out."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PipelineStage:
    name: str
    objective: str
    output: str


DEFAULT_PIPELINE: tuple[PipelineStage, ...] = (
    PipelineStage(
        name="governance",
        objective="Verify rights, retention, and publication rules for each data source.",
        output="Data governance matrix",
    ),
    PipelineStage(
        name="ingestion",
        objective="Import source files and map them into a canonical crash schema.",
        output="Canonical crash table",
    ),
    PipelineStage(
        name="quality",
        objective="Detect invalid coordinates, duplicates, and schema inconsistencies.",
        output="Data quality report",
    ),
    PipelineStage(
        name="segmentation",
        objective="Build analysis segments from the road network.",
        output="Road segment table",
    ),
    PipelineStage(
        name="enrichment",
        objective="Attach weather, road, topology, and population features.",
        output="Segment feature store",
    ),
    PipelineStage(
        name="modeling",
        objective="Train and evaluate baseline frequency and severity models.",
        output="Versioned model artifacts",
    ),
    PipelineStage(
        name="serving",
        objective="Expose aggregated and scoped outputs to APIs and dashboards.",
        output="Prediction store and API contracts",
    ),
)


def pipeline_as_dicts() -> list[dict[str, str]]:
    return [asdict(stage) for stage in DEFAULT_PIPELINE]
