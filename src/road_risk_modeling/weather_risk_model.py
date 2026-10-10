"""Exposure-normalized weather-conditioned crash-risk model (WX-02)."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .climate_resilience import assess_climate_resilience
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


WEATHER_RISK_MODEL_VERSION = "weather_risk_model_v1"
CONDITIONS = ("clear", "wet", "freezing", "snow_ice", "high_wind", "fog", "heat")
NUMERIC_FEATURES = (
    "maxspeed_numeric",
    "sinuosity",
    "gradient_proxy",
    "road_class_rank",
    "junction_density",
    "lighting_quality",
)
BINARY_FEATURES = ("bridge", "tunnel", "anti_skid_surface")
DEFAULT_SEED = 42


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _binary(value: Any) -> float:
    return 1.0 if str(value or "").strip().lower() in {"1", "true", "yes"} else 0.0


def _load_stack() -> tuple[Any, Any]:
    try:
        import numpy as np  # type: ignore
        from sklearn.ensemble import GradientBoostingRegressor  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Weather-risk training requires the optional ml dependencies."
        ) from exc
    return np, GradientBoostingRegressor


def _base_features(row: Mapping[str, Any]) -> list[float]:
    return [
        *[_float(row.get(name)) for name in NUMERIC_FEATURES],
        *[_binary(row.get(name)) for name in BINARY_FEATURES],
    ]


def _vector(row: Mapping[str, Any], condition: str) -> list[float]:
    base = _base_features(row)
    condition_flags = [1.0 if condition == candidate else 0.0 for candidate in CONDITIONS]
    # Interactions make the learned weather sensitivity inspectable.
    interactions = [
        value * flag
        for flag in condition_flags[1:]
        for value in base
    ]
    return [*base, *condition_flags, *interactions]


@dataclass
class WeatherRiskModel:
    estimator: Any
    residual_std: float
    segment_effects: dict[str, float]
    segment_support: dict[str, int]
    city_effects: dict[str, float]
    city_support: dict[str, int]
    training_cities: tuple[str, ...]
    feature_importances: dict[str, float]
    seed: int = DEFAULT_SEED

    def predict_rate(
        self,
        row: Mapping[str, Any],
        *,
        condition: str,
    ) -> dict[str, Any]:
        if condition not in CONDITIONS:
            raise ValueError(f"Unsupported weather condition: {condition}")
        log_rate = float(self.estimator.predict([_vector(row, condition)])[0])
        segment_id = str(row.get("segment_id") or "")
        city_key = str(row.get("city_key") or "")
        segment_support = self.segment_support.get(segment_id, 0)
        city_support = self.city_support.get(city_key, 0)
        segment_weight = segment_support / (segment_support + 24.0)
        city_weight = city_support / (city_support + 50.0)
        log_rate += segment_weight * self.segment_effects.get(segment_id, 0.0)
        log_rate += city_weight * self.city_effects.get(city_key, 0.0)
        central = math.exp(log_rate)
        uncertainty = 1.96 * self.residual_std * (
            1.0 + 1.0 / math.sqrt(max(1, segment_support))
        )
        return {
            "crash_rate_per_hour": round(central, 9),
            "crash_rate_low": round(math.exp(log_rate - uncertainty), 9),
            "crash_rate_high": round(math.exp(log_rate + uncertainty), 9),
            "segment_pooling_weight": round(segment_weight, 6),
            "city_pooling_weight": round(city_weight, 6),
            "cold_start_city": city_key not in self.training_cities,
        }

    def condition_multiplier(
        self, row: Mapping[str, Any], *, condition: str
    ) -> dict[str, Any]:
        clear = self.predict_rate(row, condition="clear")
        target = self.predict_rate(row, condition=condition)
        denominator = max(clear["crash_rate_per_hour"], 1e-12)
        return {
            "condition": condition,
            "multiplier": round(target["crash_rate_per_hour"] / denominator, 6),
            "multiplier_low": round(target["crash_rate_low"] / clear["crash_rate_high"], 6),
            "multiplier_high": round(target["crash_rate_high"] / clear["crash_rate_low"], 6),
            **target,
        }


def train_weather_risk_model(
    rows: Sequence[Mapping[str, Any]],
    *,
    train_through_year: int = 2023,
    seed: int = DEFAULT_SEED,
) -> WeatherRiskModel:
    np, GradientBoostingRegressor = _load_stack()
    training = [
        row
        for row in rows
        if int(row.get("occurred_year") or 0) <= train_through_year
        and _float(row.get("condition_hours")) > 0
    ]
    if len(training) < 20:
        raise RuntimeError("At least 20 exposed segment-condition rows are required.")
    vectors = [_vector(row, str(row.get("condition") or "clear")) for row in training]
    targets = [
        math.log(
            max(
                (_float(row.get("severity_weighted_crash_count"), -1.0)
                 if row.get("severity_weighted_crash_count") is not None
                 else _float(row.get("crash_count")))
                / _float(row.get("condition_hours")),
                1e-8,
            )
        )
        for row in training
    ]
    weights = [max(1.0, _float(row.get("condition_hours"))) for row in training]
    estimator = GradientBoostingRegressor(
        random_state=seed,
        n_estimators=180,
        max_depth=2,
        learning_rate=0.04,
        loss="huber",
    )
    estimator.fit(np.asarray(vectors), np.asarray(targets), sample_weight=np.asarray(weights))
    raw_predictions = estimator.predict(np.asarray(vectors))
    residuals = np.asarray(targets) - raw_predictions
    residual_std = max(0.05, float(np.std(residuals)))

    segment_residuals: dict[str, list[float]] = {}
    city_residuals: dict[str, list[float]] = {}
    for row, residual in zip(training, residuals):
        segment_residuals.setdefault(str(row.get("segment_id") or ""), []).append(float(residual))
        city_residuals.setdefault(str(row.get("city_key") or ""), []).append(float(residual))
    segment_effects = {
        key: sum(values) / len(values) for key, values in segment_residuals.items()
    }
    city_effects = {
        key: sum(values) / len(values) for key, values in city_residuals.items()
    }
    feature_names = [
        *NUMERIC_FEATURES,
        *BINARY_FEATURES,
        *[f"condition_{condition}" for condition in CONDITIONS],
        *[
            f"{condition}_x_{feature}"
            for condition in CONDITIONS[1:]
            for feature in (*NUMERIC_FEATURES, *BINARY_FEATURES)
        ],
    ]
    return WeatherRiskModel(
        estimator=estimator,
        residual_std=residual_std,
        segment_effects=segment_effects,
        segment_support={key: len(values) for key, values in segment_residuals.items()},
        city_effects=city_effects,
        city_support={key: len(values) for key, values in city_residuals.items()},
        training_cities=tuple(sorted(city_residuals)),
        feature_importances={
            name: float(value)
            for name, value in zip(feature_names, estimator.feature_importances_)
        },
        seed=seed,
    )


def evaluate_weather_model(
    model: WeatherRiskModel,
    rows: Sequence[Mapping[str, Any]],
    *,
    test_from_year: int = 2024,
) -> dict[str, Any]:
    test = [
        row
        for row in rows
        if int(row.get("occurred_year") or 0) >= test_from_year
        and _float(row.get("condition_hours")) > 0
    ]
    if not test:
        raise RuntimeError("No temporal holdout rows are available.")
    training = [
        row
        for row in rows
        if int(row.get("occurred_year") or 0) < test_from_year
        and _float(row.get("condition_hours")) > 0
    ]
    global_rate = sum(_float(row.get("crash_count")) for row in training) / max(
        1.0, sum(_float(row.get("condition_hours")) for row in training)
    )
    model_errors = []
    heuristic_errors = []
    predicted_adverse = observed_adverse = predicted_total = observed_total = 0.0
    city_errors: dict[str, list[float]] = {}
    for row in test:
        hours = _float(row.get("condition_hours"))
        actual = _float(row.get("crash_count"))
        prediction = model.predict_rate(
            row, condition=str(row.get("condition") or "clear")
        )["crash_rate_per_hour"] * hours
        # Old heuristic has no exposure-conditioned interactions: one network rate.
        heuristic = global_rate * hours
        model_errors.append(abs(prediction - actual))
        heuristic_errors.append(abs(heuristic - actual))
        city_errors.setdefault(str(row.get("city_key") or "unknown"), []).append(
            abs(prediction - actual)
        )
        predicted_total += prediction
        observed_total += actual
        if str(row.get("condition")) != "clear":
            predicted_adverse += prediction
            observed_adverse += actual
    model_mae = sum(model_errors) / len(model_errors)
    heuristic_mae = sum(heuristic_errors) / len(heuristic_errors)
    return {
        "test_from_year": test_from_year,
        "evaluated_rows": len(test),
        "model_mae_crashes": round(model_mae, 6),
        "heuristic_mae_crashes": round(heuristic_mae, 6),
        "beats_heuristic": model_mae < heuristic_mae,
        "calibration": {
            "predicted_adverse_crash_share": round(predicted_adverse / predicted_total, 6)
            if predicted_total
            else None,
            "observed_adverse_crash_share": round(observed_adverse / observed_total, 6)
            if observed_total
            else None,
        },
        "transferability": {
            city: {"rows": len(errors), "mae_crashes": round(sum(errors) / len(errors), 6)}
            for city, errors in sorted(city_errors.items())
        },
    }


def model_derived_hazard_profile(
    model: WeatherRiskModel, row: Mapping[str, Any]
) -> dict[str, Any]:
    mapping = {
        "flood": "wet",
        "snow_ice": "snow_ice",
        "wind": "high_wind",
        "heat": "heat",
    }
    condition_multipliers = {
        condition: model.condition_multiplier(row, condition=condition)
        for condition in mapping.values()
    }
    excess = {
        hazard: max(0.0, condition_multipliers[condition]["multiplier"] - 1.0)
        for hazard, condition in mapping.items()
    }
    total = sum(excess.values())
    weights = (
        {hazard: value / total for hazard, value in excess.items()}
        if total > 0
        else {hazard: 0.25 for hazard in mapping}
    )
    maximum = max(condition_multipliers.values(), key=lambda item: item["multiplier"])
    return {
        "weather_model_multiplier": maximum["multiplier"],
        "weather_model_multiplier_low": maximum["multiplier_low"],
        "weather_model_multiplier_high": maximum["multiplier_high"],
        "weather_model_hazard_weights": {
            key: round(value, 6) for key, value in weights.items()
        },
        "weather_condition_multipliers": condition_multipliers,
        "weather_risk_model_version": WEATHER_RISK_MODEL_VERSION,
    }


def weather_countermeasures(profile: Mapping[str, Any]) -> list[dict[str, str]]:
    multipliers = profile.get("weather_condition_multipliers") or {}
    mapping = {
        "wet": ("CM-DRN-001", "Inspect drainage and surface-water conveyance."),
        "snow_ice": ("CM-SUR-001", "Prioritize anti-skid surfacing and winter treatment."),
        "fog": ("CM-LGT-001", "Assess adaptive lighting and delineation."),
        "high_wind": ("CM-WND-001", "Review exposed-section wind controls and warnings."),
    }
    return [
        {"countermeasure_id": code, "reason": reason}
        for condition, (code, reason) in mapping.items()
        if float((multipliers.get(condition) or {}).get("multiplier") or 1.0) >= 1.2
    ]


def build_weather_risk_model_bundle(
    *,
    training_rows_path: str | Path,
    segments_path: str | Path,
    hazards_path: str | Path,
    output_dir: str | Path,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Train, evaluate, register, and refresh a model-powered climate surface."""
    try:
        import joblib  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Artifact export requires joblib.") from exc
    training_path = Path(training_rows_path)
    segment_path = Path(segments_path)
    hazard_path = Path(hazards_path)
    with training_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with segment_path.open(encoding="utf-8", newline="") as handle:
        segments = list(csv.DictReader(handle))
    with hazard_path.open(encoding="utf-8", newline="") as handle:
        hazards = list(csv.DictReader(handle))
    model = train_weather_risk_model(rows, seed=seed)
    evaluation = evaluate_weather_model(model, rows)
    enriched = [
        {**segment, **model_derived_hazard_profile(model, segment)}
        for segment in segments
    ]
    scored = assess_climate_resilience(enriched, hazards)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]],
            },
            "properties": {
                key: value
                for key, value in row.items()
                if key not in {"latitude", "longitude", "per_hazard_component"}
            },
        }
        for row in scored
        if row.get("latitude") is not None and row.get("longitude") is not None
    ]
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "weather_risk_model.joblib"
    metrics_path = output / "weather_risk_model.metrics.json"
    surface_path = output / "climate_risk_surface.geojson"
    manifest_path = output / "weather_risk_model.manifest.json"
    joblib.dump(model, model_path)
    metrics = {
        "weather_risk_model_version": WEATHER_RISK_MODEL_VERSION,
        "seed": seed,
        "residual_std": model.residual_std,
        "training_cities": list(model.training_cities),
        "feature_importances": model.feature_importances,
        "evaluation": evaluation,
        "fallback_policy": (
            "Use climate_resilience heuristic_fallback only where no trained "
            "jurisdiction profile is available."
        ),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    surface_path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest = {
        "weather_risk_model_version": WEATHER_RISK_MODEL_VERSION,
        "contract": {
            "resource_name": "weather_risk_model",
            "model_artifact": "weather_risk_model.joblib",
            "climate_surface_contract": "climate_resilience_public_v1",
        },
        "metrics": evaluation,
        "outputs": {
            "model_path": str(model_path),
            "model_sha256": _sha256(model_path),
            "metrics_path": str(metrics_path),
            "metrics_sha256": _sha256(metrics_path),
            "climate_risk_surface_path": str(surface_path),
            "climate_risk_surface_sha256": _sha256(surface_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("weather_rate_training_rows", training_path, _sha256(training_path)),
                _artifact_reference("segment_features", segment_path, _sha256(segment_path)),
                _artifact_reference("climate_hazards", hazard_path, _sha256(hazard_path)),
            ],
            publishable_outputs=[
                _artifact_reference("climate_risk_surface_geojson", surface_path, _sha256(surface_path))
            ],
            supporting_outputs=[
                _artifact_reference("weather_risk_model_joblib", model_path, _sha256(model_path)),
                _artifact_reference("weather_risk_model_metrics", metrics_path, _sha256(metrics_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        **manifest["outputs"],
        "manifest_path": str(manifest_path),
        "evaluation": evaluation,
    }
