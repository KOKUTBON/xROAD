"""Infrastructure-change recommendation model.

Two-stage, evidence-constrained recommender:

1. **Risk stage (existing):** the published frequency/severity risk surfaces
   (``modeling.py`` + the NWRSA ranking per Directive 2019/1936) identify
   high-risk objects.
2. **Recommendation stage (this module):** for each high-risk object,
   enumerate applicable countermeasures from the CMF library —
   precondition matching guarantees a recommendation whose precondition check
   fails is never emitted — then score each candidate with a learned model
   (seeded gradient boosting on the intervention feature store) that predicts
   site-specific effectiveness as a *residual on top of the published CMF
   prior*. Shrinkage toward the prior scales with per-intervention training
   support, so sparse data cannot produce implausible effects, and the
   uncertainty interval **widens** (never vanishes) for cold-start cities.
3. **Ranking output:** expected annual crashes prevented with an uncertainty
   interval, severity-weighted social cost saved (EU VSL conventions), cost
   band, benefit-cost ratio, and the top contributing risk factors as the
   human-readable "why".

Deterministic, seeded training; artifacts carry lineage manifests. See
``docs/recommendation-model-card.md``.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .countermeasure_knowledge import (
    COUNTERMEASURE_KNOWLEDGE_VERSION,
    Countermeasure,
    load_countermeasure_library,
    select_applicable_countermeasures,
)
from .dashboard_summary import _resolve_reference_path
from .intervention_feature_store import (
    INTERVENTION_FEATURE_STORE_VERSION,
    build_city_records,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256

RECOMMENDATION_MODEL_VERSION = "recommendation_model_v1"
RECOMMENDATION_CONTRACT_VERSION = "recommendation_bundle_public_v1"

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECOMMENDATION_OUTPUT_DIR = _REPO_ROOT / "data" / "planning" / "recommendations"
DEFAULT_DASHBOARD_SUMMARY_PATH = _REPO_ROOT / "data" / "dashboard" / "dashboard_summary.json"

DEFAULT_SEED = 42

# --- EU appraisal conventions (documented in the model card) ---------------
# European Commission mobility-appraisal value of statistical life and injury
# unit costs (2023 price level, rounded), combined with Italian urban injury-
# crash severity shares into one severity-weighted social cost per crash.
EU_VSL_FATALITY_EUR = 4_300_000.0
EU_COST_SERIOUS_INJURY_EUR = 660_000.0
EU_COST_SLIGHT_INJURY_EUR = 25_000.0
CRASH_SEVERITY_SHARES = {"fatal": 0.02, "serious": 0.25, "slight": 0.73}
SOCIAL_COST_PER_CRASH_EUR = round(
    CRASH_SEVERITY_SHARES["fatal"] * EU_VSL_FATALITY_EUR
    + CRASH_SEVERITY_SHARES["serious"] * EU_COST_SERIOUS_INJURY_EUR
    + CRASH_SEVERITY_SHARES["slight"] * EU_COST_SLIGHT_INJURY_EUR,
    2,
)
# Indicative capital-cost midpoints per cost band and a 10-year appraisal
# horizon discounted at 3% (annuity factor).
COST_BAND_CAPITAL_EUR = {"low": 60_000.0, "medium": 450_000.0, "high": 2_500_000.0}
APPRAISAL_YEARS = 10
DISCOUNT_RATE = 0.03
ANNUITY_FACTOR = round((1 - (1 + DISCOUNT_RATE) ** -APPRAISAL_YEARS) / DISCOUNT_RATE, 4)

# Shrinkage: weight of the learned residual is n / (n + k) for n training
# rows of that intervention code; cold-start cities halve the weight and
# widen the interval.
_SHRINKAGE_K = 25.0
_COLD_START_WEIGHT_FACTOR = 0.5
_COLD_START_INTERVAL_WIDENING = 1.5
_RATIO_CLIP = (0.05, 1.5)

_NUMERIC_FEATURES: tuple[str, ...] = (
    "before_crash_density_per_km",
    "before_severity_density_per_km",
    "feature_maxspeed_numeric",
    "feature_lanes_numeric",
    "feature_segment_length_m",
    "feature_road_class_rank",
    "feature_sinuosity",
    "feature_node_degree_sum",
    "feature_exposure_proxy_index",
    "feature_exposure_policy_index",
    "feature_poi_any_count",
    "feature_building_any_count",
)

_FEATURE_LABELS = {
    "before_crash_density_per_km": "historical crash density",
    "before_severity_density_per_km": "historical severity density",
    "feature_maxspeed_numeric": "posted speed",
    "feature_lanes_numeric": "lane count",
    "feature_segment_length_m": "segment length",
    "feature_road_class_rank": "road class",
    "feature_sinuosity": "curvature",
    "feature_node_degree_sum": "junction connectivity",
    "feature_exposure_proxy_index": "traffic exposure",
    "feature_exposure_policy_index": "policy exposure index",
    "feature_poi_any_count": "activity destinations",
    "feature_building_any_count": "built-up density",
}


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _literal_tokens(value: Any) -> list[str]:
    """Flatten scalar-or-list-literal cells ("['50' '30']") into clean tokens."""
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return []
    tokens = [
        token
        for token in text.replace("[", " ").replace("]", " ").replace("'", " ").replace('"', " ").split()
        if token and token.lower() != "nan"
    ]
    return tokens


def _literal_max_numeric(value: Any) -> float | None:
    numbers = [
        number for number in (_to_float(token) for token in _literal_tokens(value)) if number is not None
    ]
    return max(numbers) if numbers else None


def _literal_text(value: Any) -> str | None:
    """Human-readable text from a scalar-or-list-literal cell, keeping inner spaces."""
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    if text.startswith("["):
        # Numpy-style list literals use spaces (not commas) between items.
        items = [item.strip(" []\"") for item in text.strip("[]").split("'")]
        items = [
            item
            for item in items
            if item and item.lower() != "nan" and any(ch.isalnum() for ch in item)
        ]
        if items:
            return " / ".join(dict.fromkeys(items))
        return None
    return text


def _load_sklearn_stack() -> tuple[Any, Any]:
    try:
        import numpy as np  # type: ignore
        from sklearn.ensemble import GradientBoostingRegressor  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - env guard
        raise RuntimeError(
            "Recommendation-model dependencies are required. Install ML extras with: "
            "python3 -m pip install -e '.[ml]'"
        ) from exc
    return np, GradientBoostingRegressor


def _prior_cmf_for_record(
    record: Mapping[str, Any],
    library: Sequence[Countermeasure],
) -> tuple[float, float, float]:
    """CMF prior (central, ci_low, ci_high) for one feature-store record."""
    countermeasure_id = record.get("countermeasure_id")
    if countermeasure_id:
        for countermeasure in library:
            if countermeasure.countermeasure_id == countermeasure_id:
                return countermeasure.cmf, countermeasure.cmf_ci_low, countermeasure.cmf_ci_high
    code = str(record.get("intervention_code") or "")
    matching = [c for c in library if c.intervention_code == code]
    if not matching:
        matching = list(library)
    cmfs = sorted(c.cmf for c in matching)
    central = cmfs[len(cmfs) // 2]
    return (
        central,
        min(c.cmf_ci_low for c in matching),
        max(c.cmf_ci_high for c in matching),
    )


@dataclass
class RecommendationModel:
    """Trained effectiveness model with its priors and calibration state."""

    seed: int
    feature_names: tuple[str, ...]
    intervention_codes: tuple[str, ...]
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    code_support: dict[str, int]
    residual_std: float
    training_cities: tuple[str, ...]
    feature_importances: dict[str, float]
    estimator: Any = field(repr=False)
    library: tuple[Countermeasure, ...] = field(repr=False, default=())

    def _vector(self, features: Mapping[str, Any], intervention_code: str) -> list[float]:
        row = []
        for name in self.feature_names:
            value = _to_float(features.get(name))
            if value is None:
                value = self.feature_means.get(name, 0.0)
            row.append(value)
        for code in self.intervention_codes:
            row.append(1.0 if code == intervention_code else 0.0)
        return row

    def predict_effect(
        self,
        *,
        features: Mapping[str, Any],
        intervention_code: str,
        prior_cmf: float,
        prior_ci: tuple[float, float],
        city_key: str,
    ) -> dict[str, Any]:
        """Site-specific effectiveness ratio, shrunk toward the CMF prior."""
        cold_start = city_key not in self.training_cities
        support = self.code_support.get(intervention_code, 0)
        weight = support / (support + _SHRINKAGE_K)
        if cold_start:
            weight *= _COLD_START_WEIGHT_FACTOR
        residual = float(
            self.estimator.predict([self._vector(features, intervention_code)])[0]
        )
        log_ratio = math.log(max(prior_cmf, _RATIO_CLIP[0])) + weight * residual
        central = math.exp(log_ratio)
        # The prior CI is the plausibility envelope: sparse data can move the
        # estimate within (a slightly relaxed) envelope but never outside it.
        central = max(prior_ci[0] * 0.8, min(prior_ci[1] * 1.2, central))
        central = max(_RATIO_CLIP[0], min(_RATIO_CLIP[1], central))

        widen = _COLD_START_INTERVAL_WIDENING if cold_start else 1.0
        spread = 1.96 * max(self.residual_std, 0.05) * widen
        low = max(_RATIO_CLIP[0], min(central, prior_ci[0]) * math.exp(-spread * 0.5))
        high = min(_RATIO_CLIP[1], max(central, prior_ci[1]) * math.exp(spread * 0.5))
        return {
            "effect_ratio_central": round(central, 4),
            "effect_ratio_low": round(low, 4),
            "effect_ratio_high": round(high, 4),
            "prior_cmf": round(prior_cmf, 4),
            "shrinkage_weight": round(weight, 4),
            "cold_start": cold_start,
        }

    def top_risk_factors(self, features: Mapping[str, Any], limit: int = 3) -> list[dict[str, Any]]:
        """Human-readable 'why': importance-weighted deviation from the mean."""
        contributions: list[tuple[float, str, float]] = []
        for name in self.feature_names:
            value = _to_float(features.get(name))
            if value is None:
                continue
            std = self.feature_stds.get(name) or 1.0
            z_score = (value - self.feature_means.get(name, 0.0)) / std
            weight = self.feature_importances.get(name, 0.0)
            contributions.append((abs(z_score) * weight, name, z_score))
        contributions.sort(reverse=True)
        factors = []
        for score, name, z_score in contributions[:limit]:
            factors.append(
                {
                    "feature": name,
                    "label": _FEATURE_LABELS.get(name, name),
                    "direction": "above" if z_score >= 0 else "below",
                    "z_score": round(z_score, 3),
                    "contribution": round(score, 4),
                }
            )
        return factors


def _training_rows(
    records: Sequence[Mapping[str, Any]],
    library: Sequence[Countermeasure],
    splits: set[str],
) -> tuple[list[list[float]], list[float], list[str], list[str]]:
    """Vectors, residual targets, codes, and cities for the requested splits."""
    vectors: list[list[float]] = []
    targets: list[float] = []
    codes: list[str] = []
    cities: list[str] = []
    for record in records:
        if str(record.get("temporal_split")) not in splits:
            continue
        ratio = _to_float(record.get("outcome_crash_density_ratio"))
        if ratio is None or ratio <= 0:
            continue
        ratio = max(_RATIO_CLIP[0], min(2.0, ratio))
        prior, _, _ = _prior_cmf_for_record(record, library)
        targets.append(math.log(ratio) - math.log(max(prior, _RATIO_CLIP[0])))
        vectors.append([_to_float(record.get(name)) or 0.0 for name in _NUMERIC_FEATURES])
        codes.append(str(record.get("intervention_code")))
        cities.append(str(record.get("city_key")))
    return vectors, targets, codes, cities


def train_recommendation_model(
    records: Sequence[Mapping[str, Any]],
    *,
    library: Sequence[Countermeasure] | None = None,
    seed: int = DEFAULT_SEED,
) -> RecommendationModel:
    """Deterministic, seeded training on AI-02 feature-store records."""
    np, GradientBoostingRegressor = _load_sklearn_stack()
    library = tuple(library) if library is not None else load_countermeasure_library()

    train_vectors, train_targets, train_codes, train_cities = _training_rows(
        records, library, {"train"}
    )
    if len(train_vectors) < 10:
        raise RuntimeError("Not enough training rows to fit the recommendation model.")
    validation_vectors, validation_targets, validation_codes, _ = _training_rows(
        records, library, {"validation"}
    )

    intervention_codes = tuple(sorted(set(train_codes)))
    matrix = np.asarray(train_vectors, dtype=float)
    means = {
        name: float(np.mean(matrix[:, index])) for index, name in enumerate(_NUMERIC_FEATURES)
    }
    stds = {
        name: float(np.std(matrix[:, index])) or 1.0
        for index, name in enumerate(_NUMERIC_FEATURES)
    }

    def _with_one_hot(vectors: list[list[float]], codes: list[str]) -> Any:
        rows = []
        for vector, code in zip(vectors, codes):
            rows.append(
                list(vector) + [1.0 if code == candidate else 0.0 for candidate in intervention_codes]
            )
        return np.asarray(rows, dtype=float)

    estimator = GradientBoostingRegressor(
        random_state=seed, n_estimators=200, max_depth=3, learning_rate=0.05
    )
    estimator.fit(_with_one_hot(train_vectors, train_codes), np.asarray(train_targets))

    if validation_vectors:
        predictions = estimator.predict(_with_one_hot(validation_vectors, validation_codes))
        residual_std = float(
            np.std(np.asarray(validation_targets) - predictions)
        )
    else:
        predictions = estimator.predict(_with_one_hot(train_vectors, train_codes))
        residual_std = float(np.std(np.asarray(train_targets) - predictions))

    code_support: dict[str, int] = {}
    for code in train_codes:
        code_support[code] = code_support.get(code, 0) + 1
    importances = {
        name: float(value)
        for name, value in zip(_NUMERIC_FEATURES, estimator.feature_importances_)
    }

    return RecommendationModel(
        seed=seed,
        feature_names=_NUMERIC_FEATURES,
        intervention_codes=intervention_codes,
        feature_means=means,
        feature_stds=stds,
        code_support=code_support,
        residual_std=max(residual_std, 0.02),
        training_cities=tuple(sorted(set(train_cities))),
        feature_importances=importances,
        estimator=estimator,
        library=library,
    )


def evaluate_against_cmf_prior(
    model: RecommendationModel,
    records: Sequence[Mapping[str, Any]],
    *,
    split: str = "test",
) -> dict[str, Any]:
    """Held-out comparison against the CMF-prior-only baseline (MAE on ratio)."""
    model_errors: list[float] = []
    prior_errors: list[float] = []
    for record in records:
        if str(record.get("temporal_split")) != split:
            continue
        ratio = _to_float(record.get("outcome_crash_density_ratio"))
        if ratio is None or ratio <= 0:
            continue
        prior, ci_low, ci_high = _prior_cmf_for_record(record, model.library)
        features = {name: record.get(name) for name in model.feature_names}
        prediction = model.predict_effect(
            features=features,
            intervention_code=str(record.get("intervention_code")),
            prior_cmf=prior,
            prior_ci=(ci_low, ci_high),
            city_key=str(record.get("city_key")),
        )
        model_errors.append(abs(prediction["effect_ratio_central"] - ratio))
        prior_errors.append(abs(prior - ratio))
    if not model_errors:
        raise RuntimeError(f"No evaluable records in split {split!r}.")
    model_mae = sum(model_errors) / len(model_errors)
    prior_mae = sum(prior_errors) / len(prior_errors)
    return {
        "split": split,
        "evaluated_records": len(model_errors),
        "model_mae": round(model_mae, 6),
        "cmf_prior_baseline_mae": round(prior_mae, 6),
        "beats_prior_baseline": model_mae <= prior_mae,
    }


def _economics(
    *,
    baseline_annual_crashes: float,
    effect: Mapping[str, Any],
    cost_band: str,
) -> dict[str, Any]:
    prevented_central = baseline_annual_crashes * (1.0 - float(effect["effect_ratio_central"]))
    prevented_low = baseline_annual_crashes * (1.0 - float(effect["effect_ratio_high"]))
    prevented_high = baseline_annual_crashes * (1.0 - float(effect["effect_ratio_low"]))
    annual_benefit = prevented_central * SOCIAL_COST_PER_CRASH_EUR
    capital_cost = COST_BAND_CAPITAL_EUR.get(cost_band, COST_BAND_CAPITAL_EUR["medium"])
    discounted_benefit = annual_benefit * ANNUITY_FACTOR
    return {
        "expected_annual_crashes_prevented": round(prevented_central, 6),
        "expected_annual_crashes_prevented_low": round(max(0.0, prevented_low), 6),
        "expected_annual_crashes_prevented_high": round(prevented_high, 6),
        "annual_social_benefit_eur": round(annual_benefit, 2),
        "discounted_social_benefit_eur": round(discounted_benefit, 2),
        "capital_cost_eur": capital_cost,
        "benefit_cost_ratio": round(discounted_benefit / capital_cost, 4) if capital_cost else None,
    }


def _candidate_site_features(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map an analyst segment row onto the CMF precondition vocabulary."""
    features: dict[str, Any] = {"object_type": "segment", "area_type": "urban"}
    maxspeed = _to_float(row.get("maxspeed_numeric")) or _literal_max_numeric(row.get("maxspeed"))
    if maxspeed is not None:
        features["maxspeed"] = maxspeed
    lanes = _to_float(row.get("lanes_numeric")) or _literal_max_numeric(row.get("lanes"))
    if lanes is not None:
        features["lane_count"] = lanes
    length = _to_float(row.get("segment_length_m"))
    if length is not None:
        features["segment_length_m"] = length
    highway = (_literal_text(row.get("highway")) or "").lower().split(" / ")[0]
    if highway:
        features["road_class"] = highway
    return features


def recommend_for_site(
    model: RecommendationModel,
    *,
    site_features: Mapping[str, Any],
    model_features: Mapping[str, Any],
    baseline_annual_crashes: float,
    city_key: str,
) -> list[dict[str, Any]]:
    """Ranked, precondition-guaranteed recommendations for one object.

    Candidates come exclusively from ``select_applicable_countermeasures``, so
    a recommendation whose precondition check fails is never emitted.
    """
    recommendations: list[dict[str, Any]] = []
    for countermeasure in select_applicable_countermeasures(
        site_features, countermeasures=model.library
    ):
        code = countermeasure.intervention_code or countermeasure.category
        effect = model.predict_effect(
            features=model_features,
            intervention_code=code,
            prior_cmf=countermeasure.cmf,
            prior_ci=(countermeasure.cmf_ci_low, countermeasure.cmf_ci_high),
            city_key=city_key,
        )
        economics = _economics(
            baseline_annual_crashes=baseline_annual_crashes,
            effect=effect,
            cost_band=countermeasure.cost_band,
        )
        recommendations.append(
            {
                "countermeasure_id": countermeasure.countermeasure_id,
                "countermeasure_name": countermeasure.name,
                "intervention_code": code,
                "category": countermeasure.category,
                "cost_band": countermeasure.cost_band,
                "lead_time_months": countermeasure.lead_time_months,
                "evidence_source": countermeasure.source,
                "evidence_ref": countermeasure.source_ref,
                **effect,
                **economics,
                "top_risk_factors": model.top_risk_factors(model_features),
            }
        )
    recommendations.sort(
        key=lambda item: (
            -float(item["expected_annual_crashes_prevented"]),
            -float(item["benefit_cost_ratio"] or 0.0),
            str(item["countermeasure_id"]),
        )
    )
    return recommendations


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_network_recommendations(
    *,
    city_key: str = "bari",
    dashboard_summary_path: str | Path = DEFAULT_DASHBOARD_SUMMARY_PATH,
    feature_store_inputs: Mapping[str, str | Path] | None = None,
    output_dir: str | Path = DEFAULT_RECOMMENDATION_OUTPUT_DIR,
    top_n: int = 20,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Bari-style demo: top-N network recommendations with BCR.

    Exports GeoJSON + a CSV brief compatible with the intervention-briefs
    format, a model-metrics JSON (including the CMF-prior baseline
    comparison), and a lineage manifest.
    """
    from .intervention_feature_store import DEFAULT_CITY_DATASETS

    inputs = {
        city: Path(path)
        for city, path in (feature_store_inputs or DEFAULT_CITY_DATASETS).items()
        if Path(path).exists()
    }
    library = load_countermeasure_library()
    records: list[dict[str, Any]] = []
    for record_city, path in sorted(inputs.items()):
        records.extend(
            build_city_records(city_key=record_city, rows=_load_csv_rows(path), library=library)
        )
    model = train_recommendation_model(records, library=library, seed=seed)
    evaluation = evaluate_against_cmf_prior(model, records)

    summary_path = Path(dashboard_summary_path)
    summary = _load_json(summary_path)
    run_record = next(
        (
            record
            for record in summary.get("published_runs", [])
            if str(record.get("city_key")) == city_key
        ),
        None,
    )
    if run_record is None:
        raise RuntimeError(f"No published run for city {city_key!r} in {summary_path}.")
    segment_manifest_path = _resolve_reference_path(
        str(run_record["segment_scores"]["manifest_path"]), anchor_path=summary_path
    )
    segment_manifest = _load_json(segment_manifest_path)
    analyst_rows = _load_csv_rows(
        _resolve_reference_path(
            str(segment_manifest["outputs"]["analyst_csv_path"]),
            anchor_path=segment_manifest_path,
        )
    )
    public_geojson_path = _resolve_reference_path(
        str(segment_manifest["outputs"]["public_geojson_path"]),
        anchor_path=segment_manifest_path,
    )
    geometry_by_score_id = {
        str((feature.get("properties") or {}).get("segment_score_id")): feature.get("geometry")
        for feature in _load_json(public_geojson_path).get("features", [])
    }

    # Risk stage: highest-scored published segments are the candidate sites.
    ranked_sites = sorted(
        (row for row in analyst_rows if _to_float(row.get("predicted_crash_count"))),
        key=lambda row: -(_to_float(row.get("public_score_index")) or 0.0),
    )[: top_n * 8]

    site_recommendations: list[dict[str, Any]] = []
    for row in ranked_sites:
        model_features = {
            "before_crash_density_per_km": _to_float(row.get("crash_density_per_km")),
            "feature_maxspeed_numeric": _to_float(row.get("maxspeed_numeric"))
            or _literal_max_numeric(row.get("maxspeed")),
            "feature_lanes_numeric": _to_float(row.get("lanes_numeric"))
            or _literal_max_numeric(row.get("lanes")),
            "feature_segment_length_m": _to_float(row.get("segment_length_m")),
            "feature_road_class_rank": _to_float(row.get("road_class_rank")),
            "feature_sinuosity": _to_float(row.get("sinuosity")),
            "feature_node_degree_sum": _to_float(row.get("node_degree_sum")),
            "feature_exposure_proxy_index": _to_float(row.get("exposure_proxy_index")),
            "feature_exposure_policy_index": _to_float(row.get("exposure_policy_index")),
            "feature_poi_any_count": _to_float(row.get("poi_any_count")),
            "feature_building_any_count": _to_float(row.get("building_any_count")),
        }
        candidates = recommend_for_site(
            model,
            site_features=_candidate_site_features(row),
            model_features=model_features,
            baseline_annual_crashes=_to_float(row.get("predicted_crash_count")) or 0.0,
            city_key=city_key,
        )
        if not candidates:
            continue
        best = candidates[0]
        site_recommendations.append(
            {
                "segment_score_id": str(row.get("segment_score_id")),
                "segment_id": row.get("segment_id"),
                "segment_label": _literal_text(row.get("name"))
                or _literal_text(row.get("highway"))
                or str(row.get("segment_id")),
                "city_key": city_key,
                "public_score_index": _to_float(row.get("public_score_index")),
                "public_score_band": row.get("public_score_band"),
                "baseline_predicted_annual_crashes": _to_float(row.get("predicted_crash_count")),
                **best,
                "alternative_countermeasure_ids": [
                    candidate["countermeasure_id"] for candidate in candidates[1:4]
                ],
            }
        )

    site_recommendations.sort(
        key=lambda item: (
            -float(item["expected_annual_crashes_prevented"]),
            -float(item["benefit_cost_ratio"] or 0.0),
            str(item["segment_score_id"]),
        )
    )
    top_recommendations = site_recommendations[:top_n]
    for rank, recommendation in enumerate(top_recommendations, start=1):
        recommendation["recommendation_rank"] = rank

    output_root = Path(output_dir) / city_key
    output_root.mkdir(parents=True, exist_ok=True)

    csv_path = output_root / "network_recommendations.csv"
    csv_columns = [
        "recommendation_rank",
        "segment_score_id",
        "segment_id",
        "segment_label",
        "city_key",
        "public_score_index",
        "public_score_band",
        "baseline_predicted_annual_crashes",
        "countermeasure_id",
        "countermeasure_name",
        "intervention_code",
        "category",
        "cost_band",
        "lead_time_months",
        "effect_ratio_central",
        "effect_ratio_low",
        "effect_ratio_high",
        "prior_cmf",
        "shrinkage_weight",
        "cold_start",
        "expected_annual_crashes_prevented",
        "expected_annual_crashes_prevented_low",
        "expected_annual_crashes_prevented_high",
        "annual_social_benefit_eur",
        "discounted_social_benefit_eur",
        "capital_cost_eur",
        "benefit_cost_ratio",
        "evidence_source",
        "evidence_ref",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(top_recommendations)

    geojson_path = output_root / "network_recommendations.geojson"
    geojson_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": geometry_by_score_id.get(recommendation["segment_score_id"]),
                "properties": {
                    key: value
                    for key, value in recommendation.items()
                    if key not in {"top_risk_factors"}
                },
            }
            for recommendation in top_recommendations
        ],
    }
    geojson_path.write_text(json.dumps(geojson_payload, indent=2), encoding="utf-8")

    metrics_path = output_root / "recommendation_model_metrics.json"
    metrics_payload = {
        "recommendation_model_version": RECOMMENDATION_MODEL_VERSION,
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "intervention_feature_store_version": INTERVENTION_FEATURE_STORE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "seed": seed,
        "training": {
            "training_cities": list(model.training_cities),
            "code_support": model.code_support,
            "residual_std": round(model.residual_std, 6),
            "feature_importances": {
                name: round(value, 6) for name, value in model.feature_importances.items()
            },
        },
        "baseline_comparison": evaluation,
        "economics": {
            "social_cost_per_crash_eur": SOCIAL_COST_PER_CRASH_EUR,
            "eu_vsl_fatality_eur": EU_VSL_FATALITY_EUR,
            "appraisal_years": APPRAISAL_YEARS,
            "discount_rate": DISCOUNT_RATE,
            "cost_band_capital_eur": COST_BAND_CAPITAL_EUR,
        },
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest_path = output_root / "network_recommendations.manifest.json"
    manifest = {
        "recommendation_model_version": RECOMMENDATION_MODEL_VERSION,
        "inputs": {
            "dashboard_summary_path": str(summary_path),
            "dashboard_summary_sha256": _sha256(summary_path),
            "city_key": city_key,
            "feature_store_inputs": {
                record_city: str(path) for record_city, path in sorted(inputs.items())
            },
        },
        "outputs": {
            "recommendations_csv_path": str(csv_path),
            "recommendations_csv_sha256": _sha256(csv_path),
            "recommendations_geojson_path": str(geojson_path),
            "recommendations_geojson_sha256": _sha256(geojson_path),
            "model_metrics_path": str(metrics_path),
            "model_metrics_sha256": _sha256(metrics_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "network_recommendations",
            "public_contract_version": RECOMMENDATION_CONTRACT_VERSION,
            "recommendation_model_version": RECOMMENDATION_MODEL_VERSION,
            "intervention_brief_compatibility": "intervention_brief_v1",
        },
        "stats": {
            "recommendation_count": len(top_recommendations),
            "candidate_site_count": len(ranked_sites),
            "beats_prior_baseline": evaluation["beats_prior_baseline"],
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("dashboard_summary_json", summary_path, _sha256(summary_path)),
                *[
                    _artifact_reference(f"segment_year_metrics_{record_city}", path, _sha256(path))
                    for record_city, path in sorted(inputs.items())
                ],
            ],
            publishable_outputs=[
                _artifact_reference("network_recommendations_csv", csv_path, _sha256(csv_path)),
                _artifact_reference(
                    "network_recommendations_geojson", geojson_path, _sha256(geojson_path)
                ),
            ],
            supporting_outputs=[
                _artifact_reference("recommendation_model_metrics", metrics_path, _sha256(metrics_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "recommendation_model_version": RECOMMENDATION_MODEL_VERSION,
        "city_key": city_key,
        "recommendations_csv_path": str(csv_path),
        "recommendations_geojson_path": str(geojson_path),
        "model_metrics_path": str(metrics_path),
        "manifest_path": str(manifest_path),
        "recommendation_count": len(top_recommendations),
        "baseline_comparison": evaluation,
        "top_recommendations": top_recommendations,
    }
