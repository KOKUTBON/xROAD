"""Adapter for the cleaned legacy Puglia crash CSV."""

from __future__ import annotations

from road_risk_modeling.canonical_schema import CanonicalCrashRecord
from road_risk_modeling.jurisdictions import IstatJurisdictionLookups
from road_risk_modeling.legacy_zip import CsvMemberRow

PUGLIA_BOUNDS = {
    "min_latitude": 39.4,
    "max_latitude": 42.5,
    "min_longitude": 14.8,
    "max_longitude": 18.8,
}


ROADWAY_TYPE_BY_LOCINC = {
    "1": "intersection",
    "2": "roundabout",
    "3": "intersection",
    "4": "intersection",
    "5": "intersection",
    "6": "level_crossing",
    "7": "straight",
    "8": "curve",
    "9": "straight",
    "11": "straight",
    "12": "straight",
}

INTERSECTION_TYPE_BY_LOCINC = {
    "1": "intersection",
    "2": "roundabout",
    "3": "intersection",
    "4": "intersection",
    "5": "intersection",
    "6": "level_crossing",
    "7": "non_intersection",
    "8": "non_intersection",
    "9": "non_intersection",
    "11": "non_intersection",
    "12": "non_intersection",
}


def _parse_int(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    return int(float(text))


def _parse_float(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    return float(text)


def _severity_level(fatalities: int, injuries: int) -> str:
    if fatalities > 0:
        return "fatal"
    if injuries > 0:
        return "injury"
    return "no_injury"


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
        PUGLIA_BOUNDS["min_latitude"] <= latitude <= PUGLIA_BOUNDS["max_latitude"]
        and PUGLIA_BOUNDS["min_longitude"] <= longitude <= PUGLIA_BOUNDS["max_longitude"]
    ):
        flags.append("coordinates_outside_expected_jurisdiction_bounds")

    return flags


def map_puglia_cleaned_row(
    csv_row: CsvMemberRow,
    jurisdiction_lookups: IstatJurisdictionLookups | None = None,
) -> CanonicalCrashRecord:
    row = csv_row.data
    fatalities = _parse_int(row.get("MORTI")) or 0
    injuries = _parse_int(row.get("FERITI")) or 0
    year = _parse_int(row.get("ANNO"))
    latitude = _parse_float(row.get("YCOORD_ACI"))
    longitude = _parse_float(row.get("XCOORD_ACI"))
    location_code = (row.get("LOCINC") or "").strip()
    province_code = row.get("PROV") or None
    city_code = row.get("COMUNE") or None
    province_name = jurisdiction_lookups.province_name_for(province_code) if jurisdiction_lookups else None
    city_name = (
        jurisdiction_lookups.municipality_name_for(province_code, city_code)
        if jurisdiction_lookups
        else None
    )
    quality_flags = _coordinate_quality_flags(latitude, longitude)

    if csv_row.repaired:
        quality_flags.append("repaired_unquoted_commas")
    if not row.get("CODICE"):
        quality_flags.append("missing_road_code")
    if not row.get("NOMESTR"):
        quality_flags.append("missing_road_name_code")

    record_id = row.get("NREC") or f"row-{csv_row.row_number}"
    source_unique_key = f"{year}:{record_id}" if year is not None else record_id

    return CanonicalCrashRecord(
        crash_id=f"it-puglia-{source_unique_key}",
        source_system="legacy_puglia_cleaned_csv",
        source_record_id=row.get("NREC") or None,
        source_unique_key=source_unique_key,
        source_member=csv_row.member,
        source_row_number=csv_row.row_number,
        occurred_at=None,
        occurred_year=year,
        occurred_month=None,
        occurred_day=None,
        occurred_hour=None,
        occurred_minute=None,
        timestamp_precision="year",
        country_code="IT",
        region_code="PUGLIA",
        province_code=province_code,
        city_code=city_code,
        city_name=city_name,
        latitude=latitude,
        longitude=longitude,
        road_segment_id=None,
        roadway_type=ROADWAY_TYPE_BY_LOCINC.get(location_code),
        intersection_type=INTERSECTION_TYPE_BY_LOCINC.get(location_code),
        weather_code=row.get("METEO") or None,
        light_condition=None,
        fatalities=fatalities,
        injuries=injuries,
        severity_level=_severity_level(fatalities, injuries),
        quality_flags=tuple(sorted(set(quality_flags))),
        extra={
            "legacy_codes": {
                "orgril": row.get("ORGRIL") or None,
                "locinc": row.get("LOCINC") or None,
                "nomestr": row.get("NOMESTR") or None,
                "tipost": row.get("TIPOST") or None,
                "pavim": row.get("PAVIM") or None,
                "intnin": row.get("INTNIN") or None,
                "fondost": row.get("FONDOST") or None,
                "segnal": row.get("SEGNAL") or None,
                "meteo": row.get("METEO") or None,
                "natinc": row.get("NATINC") or None,
                "tipoveia": row.get("TIPOVEIA") or None,
                "tipoveib": row.get("TIPOVEIB") or None,
                "tipoveic": row.get("TIPOVEIC") or None,
            },
            "legacy_location": {
                "road_description": row.get("DESCRIZIONE1") or None,
                "road_code": row.get("CODICE") or None,
                "km": _parse_float(row.get("KM")),
                "meters": _parse_float(row.get("METRI")),
                "segment_marker": _parse_float(row.get("TRONCO")),
            },
            "legacy_outcomes": {
                "mor24h": _parse_int(row.get("MOR24H")),
                "mor30g": _parse_int(row.get("MOR30G")),
            },
            "jurisdiction": {
                "province_name": province_name,
            },
        },
    )
