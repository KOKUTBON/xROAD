"""Rolling forecast risk surfaces and threshold alerts (WX-03)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .weather_ingestion import classify_weather
from .weather_risk_model import WeatherRiskModel


FORECAST_RISK_VERSION = "forecast_risk_v1"
FORECAST_HORIZON_HOURS = 72
FORECAST_RETENTION_HOURS = 96
ALERT_THRESHOLD = 75.0


def parse_open_meteo_forecast(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping) or not isinstance(hourly.get("time"), list):
        raise RuntimeError("Forecast payload has no hourly time axis.")
    rows = []
    for index, timestamp in enumerate(hourly["time"][:FORECAST_HORIZON_HOURS]):
        def value(name: str) -> Any:
            values = hourly.get(name)
            return values[index] if isinstance(values, list) and index < len(values) else None

        precipitation = value("precipitation")
        temperature = value("temperature_2m")
        snow_depth = value("snow_depth")
        wind_speed = value("wind_speed_10m")
        rows.append(
            {
                "forecast_at_utc": datetime.fromisoformat(
                    str(timestamp).replace("Z", "+00:00")
                ).replace(tzinfo=UTC).isoformat(),
                "temperature_c": temperature,
                "precipitation_mm": precipitation,
                "snow_depth_m": snow_depth,
                "wind_speed_kph": wind_speed,
                "condition": classify_weather(
                    precipitation_mm=float(precipitation or 0),
                    temperature_c=float(temperature) if temperature is not None else None,
                    snow_depth_m=float(snow_depth or 0),
                    wind_speed_kph=float(wind_speed or 0),
                    provider_code=value("weather_code"),
                ),
                "ensemble_spread": float(value("temperature_2m_spread") or 0),
            }
        )
    return rows


def _band(score: float) -> str:
    if score >= 75:
        return "severe"
    if score >= 50:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


def build_forecast_risk_surface(
    model: WeatherRiskModel,
    *,
    segments: Sequence[Mapping[str, Any]],
    forecast: Sequence[Mapping[str, Any]],
    generated_at_utc: str,
) -> list[dict[str, Any]]:
    generated = datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00"))
    rows = []
    for hour_index, weather in enumerate(forecast[:FORECAST_HORIZON_HOURS]):
        condition = str(weather.get("condition") or "clear")
        # WX-02 uses freezing/snow as the same operational snow-ice family.
        model_condition = "snow_ice" if condition == "freezing" else condition
        if model_condition == "cloudy":
            model_condition = "clear"
        for segment in segments:
            prediction = model.condition_multiplier(segment, condition=model_condition)
            baseline = float(segment.get("baseline_risk_score") or 20.0)
            score = min(100.0, baseline * prediction["multiplier"])
            spread = float(weather.get("ensemble_spread") or 0)
            confidence = max(0.2, min(0.95, 0.9 - spread / 20))
            rows.append(
                {
                    "segment_id": str(segment.get("segment_id")),
                    "forecast_at_utc": weather["forecast_at_utc"],
                    "lead_hours": round(
                        (
                            datetime.fromisoformat(
                                str(weather["forecast_at_utc"]).replace("Z", "+00:00")
                            )
                            - generated
                        ).total_seconds()
                        / 3600,
                        1,
                    ),
                    "condition": condition,
                    "temperature_c": weather.get("temperature_c"),
                    "precipitation_mm": weather.get("precipitation_mm"),
                    "wind_speed_kph": weather.get("wind_speed_kph"),
                    "risk_score": round(score, 2),
                    "risk_band": _band(score),
                    "risk_multiplier": prediction["multiplier"],
                    "risk_multiplier_low": prediction["multiplier_low"],
                    "risk_multiplier_high": prediction["multiplier_high"],
                    "model_confidence": round(confidence, 3),
                    "forecast_generated_at_utc": generated_at_utc,
                    "latitude": segment.get("latitude"),
                    "longitude": segment.get("longitude"),
                    "bridge": segment.get("bridge"),
                    "tunnel": segment.get("tunnel"),
                    "advisory_only": True,
                }
            )
    return rows


def build_weather_alerts(
    risk_rows: Sequence[Mapping[str, Any]],
    *,
    organization_id: str,
    threshold: float = ALERT_THRESHOLD,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in risk_rows:
        if float(row.get("risk_score") or 0) < threshold:
            continue
        key = (str(row["forecast_at_utc"]), str(row["condition"]))
        grouped.setdefault(key, []).append(row)
    alerts = []
    for (forecast_at, condition), rows in sorted(grouped.items()):
        segments = sorted(str(row["segment_id"]) for row in rows)
        confidence = min(float(row.get("model_confidence") or 0) for row in rows)
        alerts.append(
            {
                "alert_id": f"weather:{organization_id}:{forecast_at}:{condition}",
                "organization_id": organization_id,
                "action": "weather_risk.threshold_exceeded",
                "severity": "critical" if max(float(row["risk_score"]) for row in rows) >= 90 else "warning",
                "forecast_at_utc": forecast_at,
                "condition": condition,
                "segment_count": len(segments),
                "segment_ids": segments,
                "maximum_risk_score": max(float(row["risk_score"]) for row in rows),
                "minimum_model_confidence": confidence,
                "message": (
                    f"{len(segments)} road sections enter elevated risk bands "
                    f"during the forecast {condition} window. This is a network "
                    "risk band, not a prediction of an individual crash."
                ),
                "delivery_channels": ["automation_inbox", "email_outbox", "webhook"],
            }
        )
    return alerts


def readiness_rows(risk_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in risk_rows:
        if not (
            str(row.get("bridge") or "").lower() in {"1", "true", "yes"}
            or str(row.get("tunnel") or "").lower() in {"1", "true", "yes"}
        ):
            continue
        if row.get("condition") not in {"snow_ice", "freezing", "wet", "high_wind"}:
            continue
        current = latest.get(str(row["segment_id"]))
        if current is None or float(row["risk_score"]) > float(current["risk_score"]):
            latest[str(row["segment_id"])] = dict(row)
    return sorted(latest.values(), key=lambda row: (-float(row["risk_score"]), row["segment_id"]))


def build_forecast_risk_bundle(
    model: WeatherRiskModel,
    *,
    segments: Sequence[Mapping[str, Any]],
    forecast: Sequence[Mapping[str, Any]],
    organization_id: str,
    generated_at_utc: str,
    output_dir: str | Path,
    forecast_source_path: str | Path,
    model_source_path: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = build_forecast_risk_surface(
        model, segments=segments, forecast=forecast, generated_at_utc=generated_at_utc
    )
    alerts = build_weather_alerts(rows, organization_id=organization_id)
    readiness = readiness_rows(rows)
    surface_path = output / "forecast_risk_surface.geojson"
    alerts_path = output / "weather_alerts.json"
    readiness_path = output / "storm_readiness.json"
    manifest_path = output / "forecast_risk.manifest.json"
    surface_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [row["longitude"], row["latitude"]],
                        },
                        "properties": {
                            key: value
                            for key, value in row.items()
                            if key not in {"latitude", "longitude"}
                        },
                    }
                    for row in rows
                    if row.get("latitude") is not None and row.get("longitude") is not None
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    alerts_path.write_text(json.dumps({"alerts": alerts}, indent=2, sort_keys=True), encoding="utf-8")
    readiness_path.write_text(
        json.dumps({"readiness_rows": readiness}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    forecast_path = Path(forecast_source_path)
    model_path = Path(model_source_path)
    manifest = {
        "forecast_risk_version": FORECAST_RISK_VERSION,
        "generated_at_utc": generated_at_utc,
        "horizon_hours": FORECAST_HORIZON_HOURS,
        "retention_hours": FORECAST_RETENTION_HOURS,
        "stats": {
            "risk_row_count": len(rows),
            "alert_count": len(alerts),
            "readiness_asset_count": len(readiness),
        },
        "honesty": {
            "output_kind": "network_risk_band",
            "individual_crash_prediction": False,
            "forecast_uncertainty_exposed": True,
        },
        "outputs": {
            "surface_path": str(surface_path),
            "surface_sha256": _sha256(surface_path),
            "alerts_path": str(alerts_path),
            "alerts_sha256": _sha256(alerts_path),
            "readiness_path": str(readiness_path),
            "readiness_sha256": _sha256(readiness_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("weather_forecast", forecast_path, _sha256(forecast_path)),
                _artifact_reference("weather_risk_model", model_path, _sha256(model_path)),
            ],
            publishable_outputs=[
                _artifact_reference("forecast_risk_surface", surface_path, _sha256(surface_path))
            ],
            supporting_outputs=[
                _artifact_reference("weather_alerts", alerts_path, _sha256(alerts_path)),
                _artifact_reference("storm_readiness", readiness_path, _sha256(readiness_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {**manifest["outputs"], "manifest_path": str(manifest_path), "stats": manifest["stats"]}
