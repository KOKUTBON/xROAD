"""Adapter for the French BAAC open crash dataset (second Member State).

BAAC = *Base Annuelle des Accidents Corporels de la circulation*, published
yearly on data.gouv.fr under the Etalab *Licence Ouverte 2.0*. It is the
canonical French national crash register and the source France reports to the
EU **CARE** database, so it is the natural second-Member-State dataset for
demonstrating cross-border transferability.

A BAAC year ships as four linked CSV files keyed on ``Num_Acc``:

- ``caracteristiques-YYYY.csv`` — one row per accident (date, time, place,
  lighting, weather, intersection, urban/rural flag, lat/long since 2019).
- ``lieux-YYYY.csv`` — road characteristics (road category, surface, etc.).
- ``usagers-YYYY.csv`` — one row per person, carrying the ``grav`` severity.
- ``vehicules-YYYY.csv`` — one row per vehicle.

The platform models at the **accident level** with aggregate casualty counts
(the same altitude as the Bari/Puglia adapters), so this adapter maps the
``caracteristiques`` row and folds in fatality/injury counts aggregated from the
``usagers`` file. Person- and vehicle-level rows are intentionally not retained,
consistent with the data-minimisation stance in ``docs/ethics/``.

Code-list references (DSR/ONISR BAAC documentation):

- ``agg``: 1 = hors agglomération (rural), 2 = en agglomération (urban)
- ``int``: 1 hors intersection, 2 X, 3 T, 4 Y, 5 >4 branches, 6 giratoire,
  7 place, 8 passage à niveau, 9 autre
- ``atm``: atmospheric conditions (1 normale … 9 autre)
- ``lum``: 1 plein jour, 2 crépuscule/aube, 3 nuit sans éclairage,
  4 nuit éclairage non allumé, 5 nuit éclairage allumé
- ``grav``: 1 indemne, 2 tué, 3 blessé hospitalisé, 4 blessé léger
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Iterable, Mapping

from road_risk_modeling.canonical_schema import CanonicalCrashRecord


# Metropolitan France bounding box (overseas départements fall outside and are
# flagged rather than silently dropped).
FRANCE_BOUNDS = {
    "min_latitude": 41.0,
    "max_latitude": 51.6,
    "min_longitude": -5.5,
    "max_longitude": 9.8,
}

# grav code -> outcome bucket used for accident-level aggregation.
GRAV_KILLED = "2"
GRAV_INJURED = {"3", "4"}

ROADWAY_TYPE_BY_INT = {
    "1": "non_intersection",
    "2": "intersection",
    "3": "intersection",
    "4": "intersection",
    "5": "intersection",
    "6": "roundabout",
    "7": "intersection",
    "8": "level_crossing",
    "9": "non_intersection",
}

INTERSECTION_TYPE_BY_INT = {
    "1": "non_intersection",
    "2": "intersection",
    "3": "intersection",
    "4": "intersection",
    "5": "intersection",
    "6": "roundabout",
    "7": "intersection",
    "8": "level_crossing",
    "9": "non_intersection",
}

LIGHT_CONDITION_BY_LUM = {
    "1": "daylight",
    "2": "dawn_or_dusk",
    "3": "night_no_lighting",
    "4": "night_lighting_off",
    "5": "night_lighting_on",
}

AREA_BY_AGG = {
    "1": "rural",
    "2": "urban",
}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("﻿", "").strip().split())
    return text or None


def _select_value(row: Mapping[str, str | None], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in row:
            value = _clean_text(row.get(candidate))
            if value is not None:
                return value
    return None


def _normalize_code(value: str | None) -> str | None:
    """BAAC codes can arrive as ``"2"``, ``" 2 "`` or ``"2.0"`` depending on
    the export tooling; normalise to a bare integer string."""
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def _parse_date(row: Mapping[str, str | None]) -> datetime | None:
    year = _normalize_code(_select_value(row, "an"))
    month = _normalize_code(_select_value(row, "mois"))
    day = _normalize_code(_select_value(row, "jour"))
    if year is None or month is None or day is None:
        return None
    year_int = int(year)
    # BAAC years before 2019 are stored as two digits (e.g. ``18`` for 2018).
    if year_int < 100:
        year_int += 2000
    try:
        return datetime(year_int, int(month), int(day))
    except ValueError:
        return None


def _parse_time(value: str | None) -> tuple[int | None, int | None]:
    text = _clean_text(value)
    if not text:
        return (None, None)
    # Recent BAAC: "HH:MM". Legacy BAAC: zero-padded "HHMM" integer.
    if ":" in text:
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return (parsed.hour, parsed.minute)
        return (None, None)
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return (None, None)
    padded = digits.zfill(4)[-4:]
    hour, minute = int(padded[:2]), int(padded[2:])
    if hour > 23 or minute > 59:
        return (None, None)
    return (hour, minute)


def _parse_coordinate(value: str | None) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    # BAAC uses comma as the decimal separator.
    normalized = text.replace(",", ".")
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    if parsed == 0.0:
        return None
    return parsed


def _coordinate_quality_flags(latitude: float | None, longitude: float | None) -> list[str]:
    flags: list[str] = []
    if latitude is None or longitude is None:
        flags.append("missing_coordinates")
        return flags
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        flags.append("invalid_coordinates")
        return flags
    if not (
        FRANCE_BOUNDS["min_latitude"] <= latitude <= FRANCE_BOUNDS["max_latitude"]
        and FRANCE_BOUNDS["min_longitude"] <= longitude <= FRANCE_BOUNDS["max_longitude"]
    ):
        flags.append("coordinates_outside_metropolitan_france_bounds")
    return flags


def _fingerprint_row(row: Mapping[str, str | None]) -> str:
    payload = json.dumps(dict(sorted((key, value) for key, value in row.items())), ensure_ascii=True)
    return hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _severity_level(fatalities: int, injuries: int) -> str:
    if fatalities > 0:
        return "fatal"
    if injuries > 0:
        return "injury"
    return "no_injury"


def aggregate_baac_casualties(
    usager_rows: Iterable[Mapping[str, str | None]],
) -> dict[str, dict[str, int]]:
    """Fold the per-person ``usagers`` file into accident-level casualty counts.

    Returns a mapping ``Num_Acc -> {"fatalities": int, "injuries": int}``.
    ``grav == 2`` (tué) counts as a fatality; ``grav in {3, 4}`` (blessé) counts
    as an injury; ``grav == 1`` (indemne / unharmed) is ignored.
    """
    counts: dict[str, dict[str, int]] = {}
    for row in usager_rows:
        accident_id = _normalize_code(_select_value(row, "Num_Acc", "num_acc"))
        if accident_id is None:
            continue
        bucket = counts.setdefault(accident_id, {"fatalities": 0, "injuries": 0})
        grav = _normalize_code(_select_value(row, "grav"))
        if grav == GRAV_KILLED:
            bucket["fatalities"] += 1
        elif grav in GRAV_INJURED:
            bucket["injuries"] += 1
    return counts


def map_baac_caracteristiques_row(
    row: Mapping[str, str | None],
    *,
    source_name: str,
    source_row_number: int,
    casualties_by_accident: Mapping[str, Mapping[str, int]] | None = None,
    source_year: int | None = None,
) -> CanonicalCrashRecord:
    accident_id = _normalize_code(_select_value(row, "Num_Acc", "num_acc"))
    occurred_date = _parse_date(row)
    occurred_hour, occurred_minute = _parse_time(_select_value(row, "hrmn"))

    occurred_at = None
    timestamp_precision = "day"
    if occurred_date is not None and occurred_hour is not None and occurred_minute is not None:
        occurred_at = occurred_date.replace(hour=occurred_hour, minute=occurred_minute)
        timestamp_precision = "minute"
    elif occurred_date is not None:
        occurred_at = occurred_date

    occurred_year = occurred_date.year if occurred_date else source_year
    latitude = _parse_coordinate(_select_value(row, "lat"))
    longitude = _parse_coordinate(_select_value(row, "long", "lon"))

    department_code = _select_value(row, "dep")
    commune_code = _select_value(row, "com")
    agg_code = _normalize_code(_select_value(row, "agg"))
    int_code = _normalize_code(_select_value(row, "int"))
    weather_code = _normalize_code(_select_value(row, "atm"))
    light_code = _normalize_code(_select_value(row, "lum"))
    area_type = AREA_BY_AGG.get(agg_code or "")

    casualties: Mapping[str, int] = {}
    if casualties_by_accident is not None and accident_id is not None:
        casualties = casualties_by_accident.get(accident_id, {}) or {}
    fatalities = int(casualties.get("fatalities", 0))
    injuries = int(casualties.get("injuries", 0))
    casualties_available = bool(casualties)

    quality_flags = _coordinate_quality_flags(latitude, longitude)
    if occurred_date is None:
        quality_flags.append("missing_occurrence_date")
    if occurred_hour is None or occurred_minute is None:
        quality_flags.append("missing_occurrence_time")
    if not casualties_available:
        quality_flags.append("casualty_counts_unavailable")
    if source_year is not None and occurred_year is not None and source_year != occurred_year:
        quality_flags.append("source_year_mismatch")

    fingerprint = accident_id or _fingerprint_row(row)
    source_unique_key = f"{occurred_year or 'unknown'}:{fingerprint}"

    return CanonicalCrashRecord(
        crash_id=f"fr-baac-{source_unique_key}",
        source_system="fr_baac_caracteristiques_csv",
        source_record_id=accident_id or f"row-{source_row_number}",
        source_unique_key=source_unique_key,
        source_member=source_name,
        source_row_number=source_row_number,
        occurred_at=occurred_at,
        occurred_year=occurred_year,
        occurred_month=occurred_date.month if occurred_date else None,
        occurred_day=occurred_date.day if occurred_date else None,
        occurred_hour=occurred_hour,
        occurred_minute=occurred_minute,
        timestamp_precision=timestamp_precision,
        country_code="FR",
        region_code=None,
        province_code=department_code,
        city_code=commune_code,
        city_name=None,
        latitude=latitude,
        longitude=longitude,
        road_segment_id=None,
        roadway_type=ROADWAY_TYPE_BY_INT.get(int_code or ""),
        intersection_type=INTERSECTION_TYPE_BY_INT.get(int_code or ""),
        weather_code=weather_code,
        light_condition=LIGHT_CONDITION_BY_LUM.get(light_code or ""),
        fatalities=fatalities,
        injuries=injuries,
        severity_level=_severity_level(fatalities, injuries) if casualties_available else None,
        quality_flags=tuple(sorted(set(quality_flags))),
        extra={
            "fr_baac": {
                "source_year": source_year,
                "department_code": department_code,
                "commune_code": commune_code,
                "area_type": area_type,
                "agg_code": agg_code,
                "intersection_code": int_code,
                "atmospheric_code": weather_code,
                "lighting_code": light_code,
                "collision_code": _normalize_code(_select_value(row, "col")),
                "casualty_counts_available": casualties_available,
                "casualty_source": "usagers_file_grav_aggregation",
            }
        },
    )
