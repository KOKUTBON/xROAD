"""Canonical entities for cross-jurisdiction crash modeling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CanonicalCrashRecord:
    crash_id: str
    source_system: str
    source_record_id: str | None
    source_unique_key: str | None
    source_member: str | None
    source_row_number: int | None
    occurred_at: datetime | None
    occurred_year: int | None
    occurred_month: int | None
    occurred_day: int | None
    occurred_hour: int | None
    occurred_minute: int | None
    timestamp_precision: str | None
    country_code: str
    region_code: str | None
    province_code: str | None
    city_code: str | None
    city_name: str | None
    latitude: float | None
    longitude: float | None
    road_segment_id: str | None
    roadway_type: str | None
    intersection_type: str | None
    weather_code: str | None
    light_condition: str | None
    fatalities: int
    injuries: int
    severity_level: str | None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["occurred_at"] = self.occurred_at.isoformat() if self.occurred_at else None
        payload["quality_flags"] = list(self.quality_flags)
        return payload


TRANSFERABILITY_PRINCIPLES: tuple[str, ...] = (
    "Model on canonical entities rather than jurisdiction-specific column names.",
    "Keep crash frequency and crash severity as separate tasks.",
    "Use grouped and time-aware validation to measure transferability.",
    "Treat exposure and data quality as first-class modeling inputs.",
)
