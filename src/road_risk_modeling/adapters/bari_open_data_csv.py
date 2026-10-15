"""Adapter for Bari official open-data crash CSV exports."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Mapping

from road_risk_modeling.canonical_schema import CanonicalCrashRecord


BARI_BOUNDS = {
    "min_latitude": 40.95,
    "max_latitude": 41.20,
    "min_longitude": 16.70,
    "max_longitude": 17.15,
}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\ufeff", "").strip().split())
    return text or None


def _normalize_yes_no(value: str | None) -> bool | None:
    text = (_clean_text(value) or "").casefold()
    if not text:
        return None
    if text in {"si", "sì", "yes", "y", "true"}:
        return True
    if text in {"no", "n", "false"}:
        return False
    return None


def _parse_date(value: str | None) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    return datetime.strptime(text, "%d/%m/%Y")


def _parse_time(value: str | None) -> tuple[int | None, int | None]:
    text = _clean_text(value)
    if not text:
        return (None, None)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return (parsed.hour, parsed.minute)
    return (None, None)


def _scaled_coordinate_from_digits(value: str) -> float | None:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) < 3:
        return None
    scale = 10 ** (len(digits) - 2)
    return int(digits) / scale


def _parse_coordinate(value: str | None) -> float | None:
    text = _clean_text(value)
    if not text:
        return None

    normalized = text.replace(",", ".")
    if normalized.count(".") > 1:
        return _scaled_coordinate_from_digits(normalized)

    try:
        parsed = float(normalized)
    except ValueError:
        return _scaled_coordinate_from_digits(normalized)

    if parsed == 0:
        return None

    if -180.0 <= parsed <= 180.0:
        return parsed

    scaled = _scaled_coordinate_from_digits(normalized)
    return scaled if scaled is not None else parsed


def _coordinate_quality_flags(latitude: float | None, longitude: float | None) -> list[str]:
    flags: list[str] = []
    if latitude is None or longitude is None:
        flags.append("missing_coordinates")
        return flags

    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        flags.append("invalid_coordinates")
        return flags

    if not (35.0 <= latitude <= 48.0 and 6.0 <= longitude <= 19.0):
        flags.append("coordinates_outside_expected_country_bounds")

    if not (
        BARI_BOUNDS["min_latitude"] <= latitude <= BARI_BOUNDS["max_latitude"]
        and BARI_BOUNDS["min_longitude"] <= longitude <= BARI_BOUNDS["max_longitude"]
    ):
        flags.append("coordinates_outside_expected_jurisdiction_bounds")

    return flags


def _roadway_type(characteristics: str | None) -> str | None:
    text = (_clean_text(characteristics) or "").casefold()
    if not text:
        return None
    if "rotatoria" in text:
        return "roundabout"
    if "incrocio" in text or "intersezione" in text:
        return "intersection"
    if "rettilineo" in text:
        return "straight"
    if "curv" in text:
        return "curve"
    return "non_intersection"


def _intersection_type(characteristics: str | None) -> str | None:
    text = (_clean_text(characteristics) or "").casefold()
    if not text:
        return None
    if "rotatoria" in text:
        return "roundabout"
    if "incrocio" in text or "intersezione" in text:
        return "intersection"
    return "non_intersection"


def _time_of_day_bucket(hour: int | None) -> str | None:
    if hour is None:
        return None
    if hour < 6:
        return "overnight"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _fingerprint_row(row: Mapping[str, str | None]) -> str:
    payload = json.dumps(dict(sorted((key, value) for key, value in row.items())), ensure_ascii=True)
    return hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _select_value(row: Mapping[str, str | None], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in row:
            value = _clean_text(row.get(candidate))
            if value is not None:
                return value
    return None


def map_bari_open_data_row(
    row: Mapping[str, str | None],
    *,
    source_name: str,
    source_row_number: int,
    source_year: int | None = None,
) -> CanonicalCrashRecord:
    occurred_date = _parse_date(_select_value(row, "Data incidente"))
    dispatch_hour, dispatch_minute = _parse_time(_select_value(row, "Inviata ore", "Pattuglia inviata ore"))
    on_scene_time = _select_value(row, "Sul posto ore", "Pattuglia sul posto ore")

    occurred_at = None
    timestamp_precision = "day"
    if occurred_date is not None and dispatch_hour is not None and dispatch_minute is not None:
        occurred_at = occurred_date.replace(hour=dispatch_hour, minute=dispatch_minute)
        timestamp_precision = "date_dispatch_time_proxy"
    elif occurred_date is not None:
        occurred_at = occurred_date

    occurred_year = occurred_date.year if occurred_date else source_year
    latitude = _parse_coordinate(_select_value(row, "Latitudine", "lat"))
    longitude = _parse_coordinate(_select_value(row, "Longitudine", "lon"))
    injury_indicator = _normalize_yes_no(_select_value(row, "Incidente con lesioni"))
    property_damage_indicator = _normalize_yes_no(_select_value(row, "Danni a cose"))
    urban_indicator = _normalize_yes_no(_select_value(row, "Centro abitato"))
    characteristics = _select_value(row, "Caratteristiche della strada")
    weather = _select_value(row, "Condizioni meteo")
    traffic = _select_value(row, "Condizioni traffico")
    roadway_class = _select_value(row, "Tipo di strada")
    surface_state = _select_value(row, "Stato fondo stradale")
    pavement_type = _select_value(row, "Tipo pavimentazione")

    quality_flags = _coordinate_quality_flags(latitude, longitude)
    if dispatch_hour is None or dispatch_minute is None:
        quality_flags.append("missing_dispatch_time")
    if occurred_date is None:
        quality_flags.append("missing_occurrence_date")
    if source_year is not None and occurred_year is not None and source_year != occurred_year:
        quality_flags.append("source_year_mismatch")

    source_unique_key = f"{occurred_year or 'unknown'}:{_fingerprint_row(row)}"

    return CanonicalCrashRecord(
        crash_id=f"it-bari-open-data-{source_unique_key}",
        source_system="bari_open_data_ckan_csv",
        source_record_id=f"{source_year or 'unknown'}:row-{source_row_number}",
        source_unique_key=source_unique_key,
        source_member=source_name,
        source_row_number=source_row_number,
        occurred_at=occurred_at,
        occurred_year=occurred_year,
        occurred_month=occurred_date.month if occurred_date else None,
        occurred_day=occurred_date.day if occurred_date else None,
        occurred_hour=dispatch_hour,
        occurred_minute=dispatch_minute,
        timestamp_precision=timestamp_precision,
        country_code="IT",
        region_code="PUGLIA",
        province_code="072",
        city_code="006",
        city_name="Bari",
        latitude=latitude,
        longitude=longitude,
        road_segment_id=None,
        roadway_type=_roadway_type(characteristics),
        intersection_type=_intersection_type(characteristics),
        weather_code=weather,
        light_condition=None,
        fatalities=0,
        injuries=1 if injury_indicator else 0,
        severity_level="injury" if injury_indicator else "no_injury",
        quality_flags=tuple(sorted(set(quality_flags))),
        extra={
            "official_bari_open_data": {
                "source_year": source_year,
                "time_reference": "dispatch_time_proxy" if dispatch_hour is not None else "date_only",
                "dispatch_time_raw": _select_value(row, "Inviata ore", "Pattuglia inviata ore"),
                "on_scene_time_raw": on_scene_time,
                "time_of_day_bucket": _time_of_day_bucket(dispatch_hour),
                "urban_indicator": urban_indicator,
                "property_damage_indicator": property_damage_indicator,
                "injury_indicator": injury_indicator,
                "roadway_class": roadway_class,
                "roadway_characteristics": characteristics,
                "surface_state": surface_state,
                "pavement_type": pavement_type,
                "traffic_conditions": traffic,
                "fatality_count_available": False,
                "injury_count_is_binary_indicator": True,
            }
        },
    )
