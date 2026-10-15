"""Historical weather adapters and canonical crash-weather joins (WX-01)."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import urlopen

from .data_governance import (
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_PUBLIC,
    FieldClassification,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


WEATHER_INGESTION_VERSION = "weather_ingestion_v1"
WEATHER_CONTRACT_VERSION = "canonical_weather_observation_v1"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation",
    "snow_depth",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
)

SOURCE_ATTRIBUTIONS = {
    "open_meteo": {
        "license": "CC-BY-4.0",
        "attribution": "Open-Meteo.com Weather API; underlying model sources apply.",
        "url": "https://open-meteo.com/en/license",
    },
    "era5_land": {
        "license": "CC-BY-4.0",
        "attribution": "Copernicus Climate Change Service / ECMWF ERA5-Land.",
        "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land",
        "doi": "10.24381/cds.e2161bac",
    },
    "istat_crash_field": {
        "license": "source-dataset terms",
        "attribution": "ISTAT road-accident microdata weather field.",
        "url": "https://www.istat.it/",
    },
}

WEATHER_FIELD_CLASSIFICATIONS = (
    FieldClassification(
        field_name="observed_at_utc",
        record_kind="weather_observation",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Hourly provider timestamp is internal join data.",
        publishable_in_aggregate=True,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="condition",
        record_kind="weather_observation",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Coarse non-personal weather condition is safe in aggregate.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="grid_cell_id",
        record_kind="weather_observation",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Provider grid linkage is internal analytical state.",
        publishable_in_aggregate=True,
        role_visibility=("analyst", "data_operator", "admin"),
    ),
)


@dataclass(frozen=True)
class WeatherObservation:
    weather_observation_id: str
    grid_cell_id: str
    latitude: float
    longitude: float
    observed_at_utc: str
    temperature_c: float | None
    precipitation_mm: float | None
    snow_depth_m: float | None
    wind_speed_kph: float | None
    wind_gust_kph: float | None
    provider_weather_code: str | None
    condition: str
    source: str
    spatial_resolution: str
    temporal_resolution: str
    quality_flags: tuple[str, ...]


def _float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def classify_weather(
    *,
    precipitation_mm: float | None,
    temperature_c: float | None,
    snow_depth_m: float | None,
    wind_speed_kph: float | None,
    provider_code: Any = None,
) -> str:
    code = int(float(provider_code)) if _float(provider_code) is not None else None
    if (snow_depth_m or 0) > 0 or code in {71, 73, 75, 77, 85, 86}:
        return "snow_ice"
    if (temperature_c is not None and temperature_c <= 0) and (precipitation_mm or 0) > 0:
        return "freezing"
    if (precipitation_mm or 0) >= 0.1 or (code is not None and 51 <= code <= 67):
        return "wet"
    if (wind_speed_kph or 0) >= 40:
        return "high_wind"
    if code in {45, 48}:
        return "fog"
    if code in {1, 2, 3}:
        return "cloudy"
    return "clear"


def build_open_meteo_url(
    *,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    model: str = "era5_land",
) -> str:
    return OPEN_METEO_ARCHIVE_URL + "?" + urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(OPEN_METEO_HOURLY_VARIABLES),
            "models": model,
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
        }
    )


def fetch_open_meteo(
    *,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    cache_dir: str | Path = "cache/weather/open_meteo",
    model: str = "era5_land",
) -> tuple[dict[str, Any], Path]:
    url = build_open_meteo_url(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        model=model,
    )
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if not cache_path.exists():
        try:
            with urlopen(url, timeout=120) as response:  # nosec B310 # URL built from fixed HTTPS Open-Meteo endpoint
                payload = json.load(response)
        except URLError as exc:
            raise RuntimeError(
                "Open-Meteo fetch failed. Configure the host CA certificate bundle "
                "or supply a verified cached response with --weather-json; TLS "
                "verification is not disabled."
            ) from exc
        cache_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return json.loads(cache_path.read_text(encoding="utf-8")), cache_path


def parse_open_meteo_payload(
    payload: Mapping[str, Any],
    *,
    source: str = "open_meteo",
    model: str = "era5_land",
) -> list[WeatherObservation]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping) or not isinstance(hourly.get("time"), list):
        raise RuntimeError("Open-Meteo payload does not contain hourly time arrays.")
    latitude = float(payload["latitude"])
    longitude = float(payload["longitude"])
    grid_id = f"{source}:{model}:{latitude:.4f}:{longitude:.4f}"
    times = hourly["time"]
    rows = []
    for index, timestamp in enumerate(times):
        def value(name: str) -> Any:
            values = hourly.get(name)
            return values[index] if isinstance(values, list) and index < len(values) else None

        temperature = _float(value("temperature_2m"))
        precipitation = _float(value("precipitation"))
        snow_depth = _float(value("snow_depth"))
        wind_speed = _float(value("wind_speed_10m"))
        wind_gust = _float(value("wind_gusts_10m"))
        provider_code = value("weather_code")
        observed_at = _iso_utc(str(timestamp))
        observation_id = hashlib.sha256(
            f"{grid_id}:{observed_at}".encode()
        ).hexdigest()[:20]
        rows.append(
            WeatherObservation(
                weather_observation_id=f"wx:{observation_id}",
                grid_cell_id=grid_id,
                latitude=latitude,
                longitude=longitude,
                observed_at_utc=observed_at,
                temperature_c=temperature,
                precipitation_mm=precipitation,
                snow_depth_m=snow_depth,
                wind_speed_kph=wind_speed,
                wind_gust_kph=wind_gust,
                provider_weather_code=str(provider_code) if provider_code is not None else None,
                condition=classify_weather(
                    precipitation_mm=precipitation,
                    temperature_c=temperature,
                    snow_depth_m=snow_depth,
                    wind_speed_kph=wind_speed,
                    provider_code=provider_code,
                ),
                source=source,
                spatial_resolution="provider_grid",
                temporal_resolution="hour",
                quality_flags=("reanalysis", "provider_grid_centroid"),
            )
        )
    return rows


def build_era5_land_request(*, year: int, month: int, area: Sequence[float]) -> dict[str, Any]:
    """CDS request payload; retrieval is delegated to credentialed cdsapi deployments."""
    return {
        "dataset": "reanalysis-era5-land",
        "request": {
            "variable": [
                "2m_temperature",
                "total_precipitation",
                "snow_depth",
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
            ],
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{day:02d}" for day in range(1, 32)],
            "time": [f"{hour:02d}:00" for hour in range(24)],
            "area": list(area),
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        "attribution": SOURCE_ATTRIBUTIONS["era5_land"],
    }


def parse_era5_records(
    records: Iterable[Mapping[str, Any]],
) -> list[WeatherObservation]:
    """Normalize point rows extracted from CDS NetCDF/CSV into the canonical schema."""
    observations = []
    for record in records:
        latitude = float(record["latitude"])
        longitude = float(record["longitude"])
        observed_at = _iso_utc(str(record["valid_time"]))
        temperature_kelvin = _float(record.get("t2m"))
        temperature = (
            temperature_kelvin - 273.15 if temperature_kelvin is not None else None
        )
        precipitation_m = _float(record.get("tp"))
        precipitation = (
            precipitation_m * 1000 if precipitation_m is not None else None
        )
        u_wind = _float(record.get("u10"))
        v_wind = _float(record.get("v10"))
        wind_speed = (
            math.sqrt(u_wind**2 + v_wind**2) * 3.6
            if u_wind is not None and v_wind is not None
            else None
        )
        snow_depth = _float(record.get("sd"))
        grid_id = f"era5_land:{latitude:.4f}:{longitude:.4f}"
        observation_id = hashlib.sha256(
            f"{grid_id}:{observed_at}".encode()
        ).hexdigest()[:20]
        observations.append(
            WeatherObservation(
                weather_observation_id=f"wx:{observation_id}",
                grid_cell_id=grid_id,
                latitude=latitude,
                longitude=longitude,
                observed_at_utc=observed_at,
                temperature_c=round(temperature, 6) if temperature is not None else None,
                precipitation_mm=round(precipitation, 6)
                if precipitation is not None
                else None,
                snow_depth_m=snow_depth,
                wind_speed_kph=round(wind_speed, 6) if wind_speed is not None else None,
                wind_gust_kph=None,
                provider_weather_code=None,
                condition=classify_weather(
                    precipitation_mm=precipitation,
                    temperature_c=temperature,
                    snow_depth_m=snow_depth,
                    wind_speed_kph=wind_speed,
                ),
                source="era5_land",
                spatial_resolution="0.1_degree",
                temporal_resolution="hour",
                quality_flags=("reanalysis", "cds_extracted"),
            )
        )
    return observations


def harmonize_official_weather(value: Any) -> str | None:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return None
    if any(token in text for token in ("piogg", "rain", "bagnato")):
        return "wet"
    if any(token in text for token in ("neve", "snow", "ghiaccio")):
        return "snow_ice"
    if any(token in text for token in ("nebb", "fog")):
        return "fog"
    if any(token in text for token in ("vento", "wind")):
        return "high_wind"
    if any(token in text for token in ("nuvol", "cloud", "coperto")):
        return "cloudy"
    if any(token in text for token in ("seren", "clear", "sole")):
        return "clear"
    return "other"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def join_crashes_to_weather(
    crashes: Iterable[Mapping[str, Any]],
    observations: Sequence[WeatherObservation],
) -> list[dict[str, Any]]:
    indexed = [
        (observation, datetime.fromisoformat(observation.observed_at_utc))
        for observation in observations
    ]
    results = []
    for crash in crashes:
        timestamp_value = crash.get("occurred_at")
        latitude = _float(crash.get("latitude"))
        longitude = _float(crash.get("longitude"))
        if not timestamp_value or latitude is None or longitude is None:
            results.append(
                {
                    **dict(crash),
                    "weather_join_status": "insufficient_data",
                    "weather_join_precision": None,
                }
            )
            continue
        crash_time = datetime.fromisoformat(str(timestamp_value).replace("Z", "+00:00"))
        if crash_time.tzinfo is None:
            crash_time = crash_time.replace(tzinfo=UTC)
        day_precision = (
            crash.get("occurred_hour") is None
            or str(crash.get("timestamp_precision") or "").startswith("date_only")
        )
        candidates = [
            (observation, weather_time)
            for observation, weather_time in indexed
            if weather_time.date() == crash_time.date()
            if day_precision or abs((weather_time - crash_time).total_seconds()) <= 5400
        ]
        if not candidates:
            results.append(
                {
                    **dict(crash),
                    "weather_join_status": "not_matched",
                    "weather_join_precision": "day" if day_precision else "hour",
                }
            )
            continue
        if day_precision:
            ranked = sorted(
                candidates,
                key=lambda pair: (
                    _distance_km(latitude, longitude, pair[0].latitude, pair[0].longitude),
                    abs(pair[1].hour - 12),
                ),
            )
            precision = "date_noon_proxy"
        else:
            ranked = sorted(
                candidates,
                key=lambda pair: (
                    abs((pair[1] - crash_time).total_seconds()),
                    _distance_km(latitude, longitude, pair[0].latitude, pair[0].longitude),
                ),
            )
            precision = "nearest_hour"
        weather, weather_time = ranked[0]
        official = harmonize_official_weather(crash.get("weather_code"))
        agreement = official == weather.condition if official and official != "other" else None
        results.append(
            {
                **dict(crash),
                **{f"weather_{key}": value for key, value in asdict(weather).items()},
                "weather_join_status": "matched",
                "weather_join_precision": precision,
                "weather_time_delta_minutes": round(
                    abs((weather_time - crash_time).total_seconds()) / 60, 1
                ),
                "weather_grid_distance_km": round(
                    _distance_km(latitude, longitude, weather.latitude, weather.longitude), 3
                ),
                "official_weather_condition": official,
                "weather_condition_agreement": agreement,
            }
        )
    return results


def build_condition_hour_exposure(
    crashes: Iterable[Mapping[str, Any]],
    observations: Sequence[WeatherObservation],
) -> list[dict[str, Any]]:
    segment_years = {
        (str(row.get("segment_id")), int(row.get("occurred_year")))
        for row in crashes
        if row.get("segment_id") and row.get("occurred_year")
    }
    by_year: dict[int, list[WeatherObservation]] = {}
    for observation in observations:
        year = datetime.fromisoformat(observation.observed_at_utc).year
        by_year.setdefault(year, []).append(observation)
    rows = []
    for segment_id, year in sorted(segment_years):
        year_rows = by_year.get(year, [])
        counts = {
            "wet_hours": sum(row.condition == "wet" for row in year_rows),
            "freezing_hours": sum(row.condition in {"freezing", "snow_ice"} for row in year_rows),
            "high_wind_hours": sum(row.condition == "high_wind" for row in year_rows),
            "fog_hours": sum(row.condition == "fog" for row in year_rows),
            "observed_weather_hours": len(year_rows),
        }
        rows.append({"segment_id": segment_id, "occurred_year": year, **counts})
    return rows


def agreement_report(joined_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    comparable = [
        row for row in joined_rows if row.get("weather_condition_agreement") is not None
    ]
    agreements = sum(bool(row["weather_condition_agreement"]) for row in comparable)
    return {
        "comparable_crash_count": len(comparable),
        "agreement_count": agreements,
        "agreement_rate": round(agreements / len(comparable), 6) if comparable else None,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_weather_join_bundle(
    *,
    crashes: list[dict[str, Any]],
    observations: Sequence[WeatherObservation],
    output_dir: str | Path,
    crash_source_path: str | Path,
    weather_source_path: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    joined = join_crashes_to_weather(crashes, observations)
    exposures = build_condition_hour_exposure(crashes, observations)
    agreement = agreement_report(joined)
    joined_path = output / "crash_weather_join.csv"
    exposure_path = output / "condition_hour_exposure.csv"
    agreement_path = output / "weather_agreement.json"
    manifest_path = output / "weather_join.manifest.json"
    _write_csv(joined_path, joined)
    _write_csv(exposure_path, exposures)
    agreement_path.write_text(json.dumps(agreement, indent=2, sort_keys=True), encoding="utf-8")
    crash_path = Path(crash_source_path)
    weather_path = Path(weather_source_path)
    manifest = {
        "weather_ingestion_version": WEATHER_INGESTION_VERSION,
        "contract_version": WEATHER_CONTRACT_VERSION,
        "licenses": SOURCE_ATTRIBUTIONS,
        "governance": [classification.to_dict() for classification in WEATHER_FIELD_CLASSIFICATIONS],
        "stats": {
            "crash_count": len(crashes),
            "matched_crash_count": sum(row.get("weather_join_status") == "matched" for row in joined),
            "weather_observation_count": len(observations),
            "exposure_row_count": len(exposures),
            **agreement,
        },
        "outputs": {
            "crash_weather_join_path": str(joined_path),
            "crash_weather_join_sha256": _sha256(joined_path),
            "condition_hour_exposure_path": str(exposure_path),
            "condition_hour_exposure_sha256": _sha256(exposure_path),
            "agreement_report_path": str(agreement_path),
            "agreement_report_sha256": _sha256(agreement_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("canonical_crashes", crash_path, _sha256(crash_path)),
                _artifact_reference("historical_weather", weather_path, _sha256(weather_path)),
            ],
            publishable_outputs=[
                _artifact_reference("condition_hour_exposure_csv", exposure_path, _sha256(exposure_path)),
            ],
            supporting_outputs=[
                _artifact_reference("crash_weather_join_csv", joined_path, _sha256(joined_path)),
                _artifact_reference("weather_agreement_json", agreement_path, _sha256(agreement_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {**manifest["outputs"], "manifest_path": str(manifest_path), "stats": manifest["stats"]}
