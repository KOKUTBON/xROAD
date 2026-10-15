"""Declarative Ingestion Adapter for country- and jurisdiction-agnostic crash data.

Allows institutions in any country (e.g. UK DfT, US NHTSA, Spain DGT, Germany Destatis,
or local municipalities) to map arbitrary CSV/tabular crash datasets into
CanonicalCrashRecord using declarative YAML/JSON/TOML mapping schemas without writing
bespoke Python adapters.

Features:
- Flexible timestamp parsing (ISO 8601, custom format, split date/time, or split year/month/day/hour)
- Universal Coordinate Reference System (CRS) re-projection (e.g. EPSG:27700 British National Grid,
  EPSG:2154 French Lambert-93, EPSG:3003 Italian Monte Mario, EPSG:2227 US State Plane -> EPSG:4326 WGS84)
- Severity resolution (direct fatality/injury count columns, binary flags, or code-list crosswalks like KABCO/MAIS)
- Code-list crosswalks for intersection, roadway, lighting, and weather
- Outlier detection against bounding boxes and data-quality flagging
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
import tomllib

from road_risk_modeling.canonical_schema import CanonicalCrashRecord


@dataclass(slots=True)
class DateTimeMappingConfig:
    """Configures date and time extraction from tabular columns."""

    datetime_column: str | None = None
    datetime_format: str | None = None  # e.g. "%Y-%m-%d %H:%M:%S"
    date_column: str | None = None
    date_format: str | None = None  # e.g. "%d/%m/%Y" or "%Y-%m-%d"
    time_column: str | None = None
    time_format: str | None = None  # e.g. "%H:%M" or "%H:%M:%S"
    year_column: str | None = None
    month_column: str | None = None
    day_column: str | None = None
    hour_column: str | None = None
    minute_column: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DateTimeMappingConfig:
        return cls(
            datetime_column=data.get("datetime_column"),
            datetime_format=data.get("datetime_format"),
            date_column=data.get("date_column"),
            date_format=data.get("date_format"),
            time_column=data.get("time_column"),
            time_format=data.get("time_format"),
            year_column=data.get("year_column"),
            month_column=data.get("month_column"),
            day_column=data.get("day_column"),
            hour_column=data.get("hour_column"),
            minute_column=data.get("minute_column"),
        )


@dataclass(slots=True)
class SpatialMappingConfig:
    """Configures coordinates extraction and CRS reprojection."""

    latitude_column: str | None = None
    longitude_column: str | None = None
    x_column: str | None = None  # Projected easting / X
    y_column: str | None = None  # Projected northing / Y
    native_crs: str = "EPSG:4326"
    bounding_box: tuple[float, float, float, float] | None = None  # (min_lon, min_lat, max_lon, max_lat)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SpatialMappingConfig:
        bbox = data.get("bounding_box")
        bounding_box = tuple(float(x) for x in bbox) if bbox and len(bbox) == 4 else None
        return cls(
            latitude_column=data.get("latitude_column"),
            longitude_column=data.get("longitude_column"),
            x_column=data.get("x_column"),
            y_column=data.get("y_column"),
            native_crs=str(data.get("native_crs") or "EPSG:4326"),
            bounding_box=bounding_box,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class SeverityMappingConfig:
    """Configures fatality, injury, and severity classification extraction."""

    fatalities_column: str | None = None
    injuries_column: str | None = None
    severity_column: str | None = None
    # Code-list crosswalk e.g. {"1": {"fatalities": 1, "injuries": 0, "severity_level": "fatal"}}
    severity_crosswalk: dict[str, dict[str, Any]] = field(default_factory=dict)
    default_severity_level: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SeverityMappingConfig:
        return cls(
            fatalities_column=data.get("fatalities_column"),
            injuries_column=data.get("injuries_column"),
            severity_column=data.get("severity_column"),
            severity_crosswalk=dict(data.get("severity_crosswalk") or {}),
            default_severity_level=data.get("default_severity_level"),
        )


@dataclass(slots=True)
class AdministrativeMappingConfig:
    """Configures regional administrative codes and names."""

    region_column: str | None = None
    province_column: str | None = None
    city_code_column: str | None = None
    city_name_column: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdministrativeMappingConfig:
        return cls(
            region_column=data.get("region_column"),
            province_column=data.get("province_column"),
            city_code_column=data.get("city_code_column"),
            city_name_column=data.get("city_name_column"),
        )


@dataclass(slots=True)
class CodeListCrosswalkConfig:
    """Mapping for categorical road/environmental attributes."""

    column: str
    mapping: dict[str, str] = field(default_factory=dict)
    default: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CodeListCrosswalkConfig:
        return cls(
            column=str(data["column"]),
            mapping={str(k): str(v) for k, v in (data.get("mapping") or {}).items()},
            default=data.get("default"),
        )


@dataclass(slots=True)
class DeclarativeSchemaMapping:
    """Complete declarative schema mapping specification."""

    schema_id: str
    country_code: str
    source_system: str
    id_column: str
    datetime_mapping: DateTimeMappingConfig = field(default_factory=DateTimeMappingConfig)
    spatial_mapping: SpatialMappingConfig = field(default_factory=SpatialMappingConfig)
    severity_mapping: SeverityMappingConfig = field(default_factory=SeverityMappingConfig)
    administrative_mapping: AdministrativeMappingConfig = field(default_factory=AdministrativeMappingConfig)
    roadway_type_crosswalk: CodeListCrosswalkConfig | None = None
    intersection_type_crosswalk: CodeListCrosswalkConfig | None = None
    weather_crosswalk: CodeListCrosswalkConfig | None = None
    light_condition_crosswalk: CodeListCrosswalkConfig | None = None
    extra_columns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DeclarativeSchemaMapping:
        roadway = data.get("roadway_type_crosswalk")
        intersection = data.get("intersection_type_crosswalk")
        weather = data.get("weather_crosswalk")
        light = data.get("light_condition_crosswalk")

        return cls(
            schema_id=str(data.get("schema_id") or "generic_declarative"),
            country_code=str(data.get("country_code") or "XX").upper(),
            source_system=str(data.get("source_system") or "declarative_csv"),
            id_column=str(data.get("id_column") or "id"),
            datetime_mapping=DateTimeMappingConfig.from_dict(data.get("datetime_mapping") or {}),
            spatial_mapping=SpatialMappingConfig.from_dict(data.get("spatial_mapping") or {}),
            severity_mapping=SeverityMappingConfig.from_dict(data.get("severity_mapping") or {}),
            administrative_mapping=AdministrativeMappingConfig.from_dict(data.get("administrative_mapping") or {}),
            roadway_type_crosswalk=CodeListCrosswalkConfig.from_dict(roadway) if roadway else None,
            intersection_type_crosswalk=CodeListCrosswalkConfig.from_dict(intersection) if intersection else None,
            weather_crosswalk=CodeListCrosswalkConfig.from_dict(weather) if weather else None,
            light_condition_crosswalk=CodeListCrosswalkConfig.from_dict(light) if light else None,
            extra_columns=tuple(data.get("extra_columns") or ()),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> DeclarativeSchemaMapping:
        config_path = Path(path)
        content = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() == ".json":
            return cls.from_dict(json.loads(content))
        if config_path.suffix.lower() in (".toml", ".tml"):
            with config_path.open("rb") as handle:
                return cls.from_dict(tomllib.load(handle))
        try:
            return cls.from_dict(json.loads(content))
        except Exception:
            with config_path.open("rb") as handle:
                return cls.from_dict(tomllib.load(handle))


class CoordinateTransformer:
    """Helper to transform arbitrary projected coordinates into WGS84 (EPSG:4326)."""

    def __init__(self, source_crs: str, target_crs: str = "EPSG:4326") -> None:
        self.source_crs = source_crs.strip().upper()
        self.target_crs = target_crs.strip().upper()
        self.is_identity = self.source_crs in ("EPSG:4326", "WGS84", "CRS84", "4326")
        self._transformer = None
        if not self.is_identity:
            try:
                import pyproj

                self._transformer = pyproj.Transformer.from_crs(
                    self.source_crs, self.target_crs, always_xy=True
                )
            except Exception:
                self._transformer = None

    def transform(self, x: float, y: float) -> tuple[float, float]:
        """Convert x, y to (longitude, latitude)."""
        if self.is_identity or self._transformer is None:
            return x, y
        lon, lat = self._transformer.transform(x, y)
        return float(lon), float(lat)


def _coerce_clean_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _coerce_int_val(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).strip().replace(",", ".")))
    except (ValueError, TypeError):
        return None


def _coerce_float_val(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None


class DeclarativeCrashAdapter:
    """Adapter that transforms tabular records into CanonicalCrashRecord per declarative mapping."""

    def __init__(self, mapping: DeclarativeSchemaMapping) -> None:
        self.mapping = mapping
        self.transformer = CoordinateTransformer(mapping.spatial_mapping.native_crs)

    def _parse_timestamp(
        self, row: Mapping[str, Any]
    ) -> tuple[datetime | None, int | None, int | None, int | None, int | None, int | None, str | None, list[str]]:
        dt_cfg = self.mapping.datetime_mapping
        flags: list[str] = []

        # 1. Full datetime column
        if dt_cfg.datetime_column and dt_cfg.datetime_column in row:
            raw_val = _coerce_clean_str(row.get(dt_cfg.datetime_column))
            if raw_val:
                try:
                    if dt_cfg.datetime_format:
                        dt = datetime.strptime(raw_val, dt_cfg.datetime_format)
                    else:
                        dt = datetime.fromisoformat(raw_val)
                    return dt, dt.year, dt.month, dt.day, dt.hour, dt.minute, "minute", flags
                except Exception:
                    flags.append("datetime_parse_failed")

        # 2. Date and Time separate columns
        if dt_cfg.date_column and dt_cfg.date_column in row:
            raw_date = _coerce_clean_str(row.get(dt_cfg.date_column))
            raw_time = _coerce_clean_str(row.get(dt_cfg.time_column)) if dt_cfg.time_column else None
            if raw_date:
                dt_str = f"{raw_date} {raw_time}" if raw_time else raw_date
                fmt = f"{dt_cfg.date_format or '%Y-%m-%d'} {dt_cfg.time_format or '%H:%M'}" if raw_time else (dt_cfg.date_format or "%Y-%m-%d")
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    precision = "minute" if raw_time else "day"
                    return dt, dt.year, dt.month, dt.day, dt.hour, dt.minute, precision, flags
                except Exception:
                    # Try ISO fallback
                    try:
                        dt = datetime.fromisoformat(raw_date)
                        return dt, dt.year, dt.month, dt.day, None, None, "day", flags
                    except Exception:
                        flags.append("date_parse_failed")

        # 3. Explicit discrete year/month/day/hour/minute columns
        year = _coerce_int_val(row.get(dt_cfg.year_column)) if dt_cfg.year_column else None
        month = _coerce_int_val(row.get(dt_cfg.month_column)) if dt_cfg.month_column else None
        day = _coerce_int_val(row.get(dt_cfg.day_column)) if dt_cfg.day_column else None
        hour = _coerce_int_val(row.get(dt_cfg.hour_column)) if dt_cfg.hour_column else None
        minute = _coerce_int_val(row.get(dt_cfg.minute_column)) if dt_cfg.minute_column else None

        if year:
            try:
                dt = datetime(year, month or 1, day or 1, hour or 0, minute or 0)
                precision = "minute" if (hour is not None and minute is not None) else ("day" if day else "year")
                return dt, year, month, day, hour, minute, precision, flags
            except Exception:
                flags.append("discrete_datetime_invalid")
                return None, year, month, day, hour, minute, "year", flags

        flags.append("timestamp_missing")
        return None, None, None, None, None, None, None, flags

    def _parse_coordinates(
        self, row: Mapping[str, Any]
    ) -> tuple[float | None, float | None, list[str]]:
        sp_cfg = self.mapping.spatial_mapping
        flags: list[str] = []

        # Check for X/Y projected columns first if defined
        if sp_cfg.x_column and sp_cfg.y_column:
            x_val = _coerce_float_val(row.get(sp_cfg.x_column))
            y_val = _coerce_float_val(row.get(sp_cfg.y_column))
            if x_val is not None and y_val is not None:
                lon, lat = self.transformer.transform(x_val, y_val)
                # Check bounding box
                if sp_cfg.bounding_box:
                    min_lon, min_lat, max_lon, max_lat = sp_cfg.bounding_box
                    if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                        flags.append("coordinates_outside_bounds")
                return lat, lon, flags

        # Check for direct latitude and longitude
        lat_val = _coerce_float_val(row.get(sp_cfg.latitude_column)) if sp_cfg.latitude_column else None
        lon_val = _coerce_float_val(row.get(sp_cfg.longitude_column)) if sp_cfg.longitude_column else None

        if lat_val is not None and lon_val is not None:
            if not self.transformer.is_identity:
                lon_val, lat_val = self.transformer.transform(lon_val, lat_val)
            if sp_cfg.bounding_box:
                min_lon, min_lat, max_lon, max_lat = sp_cfg.bounding_box
                if not (min_lon <= lon_val <= max_lon and min_lat <= lat_val <= max_lat):
                    flags.append("coordinates_outside_bounds")
            return lat_val, lon_val, flags

        flags.append("coordinates_missing")
        return None, None, flags

    def _parse_severity(
        self, row: Mapping[str, Any]
    ) -> tuple[int, int, str | None, list[str]]:
        sev_cfg = self.mapping.severity_mapping
        flags: list[str] = []

        fatalities = 0
        injuries = 0
        severity_level = sev_cfg.default_severity_level

        # If a crosswalk is provided for a coded severity column
        if sev_cfg.severity_column and sev_cfg.severity_crosswalk:
            raw_code = _coerce_clean_str(row.get(sev_cfg.severity_column))
            if raw_code and raw_code in sev_cfg.severity_crosswalk:
                entry = sev_cfg.severity_crosswalk[raw_code]
                fatalities = int(entry.get("fatalities", 0))
                injuries = int(entry.get("injuries", 0))
                severity_level = entry.get("severity_level", severity_level)
            else:
                flags.append("unmapped_severity_code")

        # Explicit columns override or supplement
        if sev_cfg.fatalities_column and sev_cfg.fatalities_column in row:
            f_val = _coerce_int_val(row.get(sev_cfg.fatalities_column))
            if f_val is not None:
                fatalities = f_val

        if sev_cfg.injuries_column and sev_cfg.injuries_column in row:
            i_val = _coerce_int_val(row.get(sev_cfg.injuries_column))
            if i_val is not None:
                injuries = i_val

        if severity_level is None:
            if fatalities > 0:
                severity_level = "fatal"
            elif injuries > 0:
                severity_level = "injury"
            else:
                severity_level = "property_only"

        return fatalities, injuries, severity_level, flags

    def _map_attribute(self, row: Mapping[str, Any], crosswalk: CodeListCrosswalkConfig | None) -> tuple[str | None, list[str]]:
        if not crosswalk or crosswalk.column not in row:
            return None, []
        raw = _coerce_clean_str(row.get(crosswalk.column))
        if not raw:
            return crosswalk.default, []
        if raw in crosswalk.mapping:
            return crosswalk.mapping[raw], []
        return crosswalk.default or raw, ["unmapped_code_list_value"]

    def map_row(
        self,
        row: Mapping[str, Any],
        source_row_number: int | None = None,
        source_member: str | None = None,
    ) -> CanonicalCrashRecord:
        """Transform a raw dictionary row into CanonicalCrashRecord."""
        quality_flags: list[str] = []

        # Identifier
        raw_id = _coerce_clean_str(row.get(self.mapping.id_column))
        if not raw_id:
            raw_id = f"row_{source_row_number or 0}"
            quality_flags.append("generated_identifier")

        crash_id = f"{self.mapping.source_system}:{raw_id}"

        # Temporal
        dt, year, month, day, hour, minute, precision, dt_flags = self._parse_timestamp(row)
        quality_flags.extend(dt_flags)

        # Spatial
        lat, lon, sp_flags = self._parse_coordinates(row)
        quality_flags.extend(sp_flags)

        # Severity
        fatalities, injuries, severity_level, sev_flags = self._parse_severity(row)
        quality_flags.extend(sev_flags)

        # Administrative
        adm_cfg = self.mapping.administrative_mapping
        region = _coerce_clean_str(row.get(adm_cfg.region_column)) if adm_cfg.region_column else None
        province = _coerce_clean_str(row.get(adm_cfg.province_column)) if adm_cfg.province_column else None
        city_code = _coerce_clean_str(row.get(adm_cfg.city_code_column)) if adm_cfg.city_code_column else None
        city_name = _coerce_clean_str(row.get(adm_cfg.city_name_column)) if adm_cfg.city_name_column else None

        # Crosswalks
        roadway_type, rw_flags = self._map_attribute(row, self.mapping.roadway_type_crosswalk)
        quality_flags.extend(rw_flags)

        intersection_type, ix_flags = self._map_attribute(row, self.mapping.intersection_type_crosswalk)
        quality_flags.extend(ix_flags)

        weather_code, wx_flags = self._map_attribute(row, self.mapping.weather_crosswalk)
        quality_flags.extend(wx_flags)

        light_condition, lt_flags = self._map_attribute(row, self.mapping.light_condition_crosswalk)
        quality_flags.extend(lt_flags)

        # Extra preserved metadata
        extra: dict[str, Any] = {}
        for col in self.mapping.extra_columns:
            if col in row:
                extra[col] = row[col]

        return CanonicalCrashRecord(
            crash_id=crash_id,
            source_system=self.mapping.source_system,
            source_record_id=raw_id,
            source_unique_key=f"{self.mapping.country_code}:{raw_id}",
            source_member=source_member,
            source_row_number=source_row_number,
            occurred_at=dt,
            occurred_year=year,
            occurred_month=month,
            occurred_day=day,
            occurred_hour=hour,
            occurred_minute=minute,
            timestamp_precision=precision,
            country_code=self.mapping.country_code,
            region_code=region,
            province_code=province,
            city_code=city_code,
            city_name=city_name,
            latitude=lat,
            longitude=lon,
            road_segment_id=None,
            roadway_type=roadway_type,
            intersection_type=intersection_type,
            weather_code=weather_code,
            light_condition=light_condition,
            fatalities=fatalities,
            injuries=injuries,
            severity_level=severity_level,
            quality_flags=tuple(dict.fromkeys(quality_flags)),  # deduplicated
            extra=extra,
        )

    def ingest_csv(
        self,
        csv_path: str | Path,
        limit: int | None = None,
        encoding: str = "utf-8",
    ) -> list[CanonicalCrashRecord]:
        """Ingest all rows from a CSV file into canonical records."""
        path = Path(csv_path)
        records: list[CanonicalCrashRecord] = []

        with path.open(mode="r", encoding=encoding, errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader, start=1):
                records.append(self.map_row(row, source_row_number=idx, source_member=path.name))
                if limit and len(records) >= limit:
                    break

        return records


# Pre-configured International Schema Presets
UK_STATS19_PRESET = DeclarativeSchemaMapping(
    schema_id="stats19_uk",
    country_code="GB",
    source_system="dft_stats19",
    id_column="collision_reference",
    datetime_mapping=DateTimeMappingConfig(
        date_column="date",
        date_format="%d/%m/%Y",
        time_column="time",
        time_format="%H:%M",
    ),
    spatial_mapping=SpatialMappingConfig(
        x_column="location_easting_osgr",
        y_column="location_northing_osgr",
        native_crs="EPSG:27700",  # British National Grid
        bounding_box=(-8.5, 49.8, 1.8, 60.9),
    ),
    severity_mapping=SeverityMappingConfig(
        severity_column="collision_severity",
        severity_crosswalk={
            "1": {"fatalities": 1, "injuries": 0, "severity_level": "fatal"},
            "2": {"fatalities": 0, "injuries": 1, "severity_level": "serious"},
            "3": {"fatalities": 0, "injuries": 1, "severity_level": "slight"},
        },
    ),
    roadway_type_crosswalk=CodeListCrosswalkConfig(
        column="road_type",
        mapping={
            "1": "roundabout",
            "2": "one_way",
            "3": "dual_carriageway",
            "6": "single_carriageway",
        },
    ),
    light_condition_crosswalk=CodeListCrosswalkConfig(
        column="light_conditions",
        mapping={
            "1": "daylight",
            "4": "darkness_lights_lit",
            "5": "darkness_lights_unlit",
            "6": "darkness_no_lights",
        },
    ),
)

US_MMUCC_PRESET = DeclarativeSchemaMapping(
    schema_id="mmucc_us",
    country_code="US",
    source_system="nhtsa_mmucc",
    id_column="crash_id",
    datetime_mapping=DateTimeMappingConfig(
        datetime_column="crash_date",
        datetime_format="%Y-%m-%d %H:%M:%S",
    ),
    spatial_mapping=SpatialMappingConfig(
        latitude_column="latitude",
        longitude_column="longitude",
        native_crs="EPSG:4326",
    ),
    severity_mapping=SeverityMappingConfig(
        fatalities_column="fatal_count",
        injuries_column="injury_count",
    ),
)


def ingest_declarative_dataset(
    csv_path: str | Path,
    mapping_config: DeclarativeSchemaMapping | str | Path,
    output_dir: str | Path = "data/staging",
    limit: int | None = None,
) -> dict[str, Any]:
    """Ingest a CSV dataset into canonical JSONL and manifest per declarative mapping."""
    if isinstance(mapping_config, (str, Path)):
        mapping = DeclarativeSchemaMapping.from_file(mapping_config)
    else:
        mapping = mapping_config

    adapter = DeclarativeCrashAdapter(mapping)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_filename = f"{mapping.schema_id}_canonical.jsonl"
    manifest_filename = f"{mapping.schema_id}_canonical.manifest.json"
    records_path = output_root / records_filename
    manifest_path = output_root / manifest_filename

    total_records = 0
    fatalities_total = 0
    injuries_total = 0
    severity_counts: dict[str, int] = {}
    quality_flag_counts: dict[str, int] = {}
    coordinate_completeness = 0

    with (
        Path(csv_path).open("r", encoding="utf-8", errors="replace", newline="") as handle,
        records_path.open("w", encoding="utf-8") as out_handle,
    ):
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=1):
            if limit is not None and total_records >= limit:
                break
            record = adapter.map_row(row, source_row_number=idx, source_member=Path(csv_path).name)
            out_handle.write(json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")

            total_records += 1
            fatalities_total += record.fatalities
            injuries_total += record.injuries
            sev = record.severity_level or "unknown"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            if record.latitude is not None and record.longitude is not None:
                coordinate_completeness += 1
            for flag in record.quality_flags:
                quality_flag_counts[flag] = quality_flag_counts.get(flag, 0) + 1

    manifest = {
        "contract": {
            "resource_name": "canonical_crashes",
            "schema_id": mapping.schema_id,
            "country_code": mapping.country_code,
            "source_system": mapping.source_system,
        },
        "outputs": {
            "records_path": str(records_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "total_records": total_records,
            "fatalities_total": fatalities_total,
            "injuries_total": injuries_total,
            "coordinate_completeness": coordinate_completeness,
            "coordinate_completeness_ratio": round(coordinate_completeness / total_records, 4) if total_records else 0.0,
            "severity_counts": severity_counts,
            "quality_flag_counts": quality_flag_counts,
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest

