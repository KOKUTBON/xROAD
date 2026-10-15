"""Source adapters for jurisdiction-specific crash data."""

from __future__ import annotations

from .baac_fr_csv import aggregate_baac_casualties, map_baac_caracteristiques_row
from .bari_open_data_csv import map_bari_open_data_row
from .declarative_adapter import (
    DeclarativeCrashAdapter,
    DeclarativeSchemaMapping,
    UK_STATS19_PRESET,
    US_MMUCC_PRESET,
    ingest_declarative_dataset,
)
from .puglia_cleaned_csv import map_puglia_cleaned_row

__all__ = [
    "aggregate_baac_casualties",
    "DeclarativeCrashAdapter",
    "DeclarativeSchemaMapping",
    "ingest_declarative_dataset",
    "map_baac_caracteristiques_row",
    "map_bari_open_data_row",
    "map_puglia_cleaned_row",
    "UK_STATS19_PRESET",
    "US_MMUCC_PRESET",
]
