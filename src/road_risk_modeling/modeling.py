"""Baseline modeling for segment-level crash frequency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .connector_observation_schema import OBSERVED_CONNECTOR_NUMERIC_COLUMNS
from .exposure_policy import BUILT_ENV_COUNT_COLUMNS, EXPOSURE_MODEL_NUMERIC_COLUMNS, POI_COUNT_COLUMNS


BASE_NUMERIC_FEATURES = [
    "occurred_year",
    "segment_length_m",
    "lanes_numeric",
    "maxspeed_numeric",
    "width_numeric",
    "node_degree_u",
    "node_degree_v",
    "node_degree_min",
    "node_degree_max",
    "node_degree_sum",
    "is_dead_end",
    "is_intersection_connector",
    "straight_distance_m",
    "sinuosity",
    "road_class_rank",
    "segment_name_present",
    *POI_COUNT_COLUMNS,
    *BUILT_ENV_COUNT_COLUMNS,
    "exposure_proxy_index",
    *OBSERVED_CONNECTOR_NUMERIC_COLUMNS,
    *EXPOSURE_MODEL_NUMERIC_COLUMNS,
]

TEMPORAL_HISTORY_FEATURES = [
    "segment_observed_year_index",
    "prior_year_crash_count",
    "prior_year_fatal_crash_count",
    "prior_year_injury_crash_count",
    "prior_year_fatalities_total",
    "prior_year_injuries_total",
    "prior_year_mean_match_distance_m",
    "prior_total_crash_count",
    "prior_total_fatalities_total",
    "prior_total_injuries_total",
    "prior_3y_crash_sum",
    "prior_3y_crash_mean",
    "prior_3y_fatalities_sum",
    "prior_3y_injuries_sum",
    "has_prior_crash",
]

NUMERIC_FEATURES = BASE_NUMERIC_FEATURES + TEMPORAL_HISTORY_FEATURES

CATEGORICAL_FEATURES = [
    "highway",
    "oneway",
    "ref",
    "bridge",
    "junction",
    "access",
    "tunnel",
    "is_roundabout",
    "bearing_bin",
]

TARGET_COLUMN = "crash_count"
MISSING_CATEGORY_TOKEN = "__missing__"  # nosec B105 # missing-category sentinel, not a credential
SEVERITY_LABEL_COLUMN = "is_fatal_crash"
TRAINING_CONFIG_VERSION = "training_config_v1"
LINEAGE_CONTRACT_VERSION = "artifact_lineage_v1"

SEVERITY_NUMERIC_FEATURES = [
    "occurred_year",
    "match_distance_m",
    "segment_length_m",
    "lanes_numeric",
    "maxspeed_numeric",
    "width_numeric",
    "node_degree_u",
    "node_degree_v",
    "node_degree_min",
    "node_degree_max",
    "node_degree_sum",
    "is_dead_end",
    "is_intersection_connector",
    "straight_distance_m",
    "sinuosity",
    "road_class_rank",
    "segment_name_present",
    *POI_COUNT_COLUMNS,
    *BUILT_ENV_COUNT_COLUMNS,
    "exposure_proxy_index",
    *OBSERVED_CONNECTOR_NUMERIC_COLUMNS,
    *EXPOSURE_MODEL_NUMERIC_COLUMNS,
] + TEMPORAL_HISTORY_FEATURES

SEVERITY_CATEGORICAL_FEATURES = [
    "weather_code",
    "roadway_type",
    "intersection_type",
    "legacy_locinc",
    "legacy_nomestr",
    "legacy_fondost",
    "legacy_intnin",
    "legacy_natinc",
    "legacy_orgril",
    "legacy_pavim",
    "legacy_segnal",
    "legacy_tipost",
    "legacy_tipoveia",
    "legacy_tipoveib",
    "legacy_tipoveic",
    "legacy_road_code",
] + CATEGORICAL_FEATURES

SEVERITY_SEGMENT_CONTEXT_COLUMNS = list(
    dict.fromkeys(
        [
            "segment_length_m",
            *[column for column in BASE_NUMERIC_FEATURES if column != "occurred_year"],
            *CATEGORICAL_FEATURES,
            *TEMPORAL_HISTORY_FEATURES,
        ]
    )
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_reference(role: str, path: Path, sha256: str | None = None) -> dict[str, str]:
    reference = {
        "role": role,
        "path": str(path),
    }
    if sha256 is not None:
        reference["sha256"] = sha256
    return reference


def _build_lineage_contract(
    *,
    run_record_path: Path,
    upstream_inputs: list[dict[str, str]],
    publishable_outputs: list[dict[str, str]],
    supporting_outputs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "lineage_contract_version": LINEAGE_CONTRACT_VERSION,
        "run_record": _artifact_reference("run_metrics", run_record_path),
        "upstream_inputs": upstream_inputs,
        "publishable_outputs": publishable_outputs,
        "supporting_outputs": supporting_outputs or [],
    }


def _write_metrics_payload(metrics: dict[str, Any], metrics_path: Path) -> str:
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    metrics_sha256 = _sha256(metrics_path)
    metrics.setdefault("outputs", {})["metrics_sha256"] = metrics_sha256
    lineage = metrics.get("lineage")
    if isinstance(lineage, dict):
        run_record = lineage.get("run_record")
        if isinstance(run_record, dict):
            run_record["sha256"] = metrics_sha256
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return metrics_sha256


def _load_ml_stack() -> tuple[Any, ...]:
    try:
        import joblib  # type: ignore
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        from sklearn.compose import ColumnTransformer  # type: ignore
        from sklearn.ensemble import RandomForestClassifier  # type: ignore
        from sklearn.ensemble import RandomForestRegressor  # type: ignore
        from sklearn.impute import SimpleImputer  # type: ignore
        from sklearn.linear_model import LogisticRegression  # type: ignore
        from sklearn.linear_model import PoissonRegressor  # type: ignore
        from sklearn.metrics import average_precision_score, brier_score_loss, log_loss  # type: ignore
        from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, root_mean_squared_error  # type: ignore
        from sklearn.metrics import roc_auc_score  # type: ignore
        from sklearn.pipeline import Pipeline  # type: ignore
        from sklearn.preprocessing import OneHotEncoder  # type: ignore
        from sklearn.preprocessing import StandardScaler  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Modeling dependencies are required. Install ML extras with: "
            "python3 -m pip install -e '.[ml]'"
        ) from exc
    return (
        joblib,
        np,
        pd,
        ColumnTransformer,
        RandomForestClassifier,
        RandomForestRegressor,
        SimpleImputer,
        LogisticRegression,
        average_precision_score,
        brier_score_loss,
        log_loss,
        PoissonRegressor,
        mean_absolute_error,
        mean_poisson_deviance,
        root_mean_squared_error,
        roc_auc_score,
        Pipeline,
        OneHotEncoder,
        StandardScaler,
    )


def _add_temporal_history_features(frame: Any, pd: Any) -> Any:
    if "segment_id" not in frame.columns or "occurred_year" not in frame.columns:
        raise RuntimeError("Aggregate table must contain segment_id and occurred_year columns.")

    working = frame.copy()
    required_history_sources = [
        TARGET_COLUMN,
        "fatal_crash_count",
        "injury_crash_count",
        "fatalities_total",
        "injuries_total",
        "mean_match_distance_m",
    ]
    for column in required_history_sources:
        if column not in working.columns:
            working[column] = 0.0
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)

    working["occurred_year"] = pd.to_numeric(working["occurred_year"], errors="coerce")
    if working["occurred_year"].isna().any():
        raise RuntimeError("Aggregate table contains rows with invalid occurred_year values.")
    working["occurred_year"] = working["occurred_year"].astype(int)

    working = working.sort_values(["segment_id", "occurred_year"]).copy()
    grouped = working.groupby("segment_id", sort=False)

    working["segment_observed_year_index"] = grouped.cumcount()
    working["prior_year_crash_count"] = grouped[TARGET_COLUMN].shift(1).fillna(0.0)
    working["prior_year_fatal_crash_count"] = grouped["fatal_crash_count"].shift(1).fillna(0.0)
    working["prior_year_injury_crash_count"] = grouped["injury_crash_count"].shift(1).fillna(0.0)
    working["prior_year_fatalities_total"] = grouped["fatalities_total"].shift(1).fillna(0.0)
    working["prior_year_injuries_total"] = grouped["injuries_total"].shift(1).fillna(0.0)
    working["prior_year_mean_match_distance_m"] = grouped["mean_match_distance_m"].shift(1).fillna(0.0)

    working["prior_total_crash_count"] = (grouped[TARGET_COLUMN].cumsum() - working[TARGET_COLUMN]).clip(lower=0.0)
    working["prior_total_fatalities_total"] = (
        grouped["fatalities_total"].cumsum() - working["fatalities_total"]
    ).clip(lower=0.0)
    working["prior_total_injuries_total"] = (
        grouped["injuries_total"].cumsum() - working["injuries_total"]
    ).clip(lower=0.0)

    working["prior_3y_crash_sum"] = grouped[TARGET_COLUMN].transform(
        lambda series: series.shift(1).rolling(window=3, min_periods=1).sum()
    ).fillna(0.0)
    working["prior_3y_crash_mean"] = grouped[TARGET_COLUMN].transform(
        lambda series: series.shift(1).rolling(window=3, min_periods=1).mean()
    ).fillna(0.0)
    working["prior_3y_fatalities_sum"] = grouped["fatalities_total"].transform(
        lambda series: series.shift(1).rolling(window=3, min_periods=1).sum()
    ).fillna(0.0)
    working["prior_3y_injuries_sum"] = grouped["injuries_total"].transform(
        lambda series: series.shift(1).rolling(window=3, min_periods=1).sum()
    ).fillna(0.0)
    working["has_prior_crash"] = (working["prior_total_crash_count"] > 0.0).astype(int)

    return working.sort_index()


def _normalize_categorical_column(series: Any) -> Any:
    return (
        series.fillna(MISSING_CATEGORY_TOKEN)
        .astype(str)
        .replace({"": MISSING_CATEGORY_TOKEN, "nan": MISSING_CATEGORY_TOKEN, "None": MISSING_CATEGORY_TOKEN})
    )


def _prune_training_feature_columns(
    frame: Any,
    numeric_features: list[str],
    categorical_features: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    usable_numeric: list[str] = []
    dropped_numeric: list[str] = []
    for column in numeric_features:
        if column in frame.columns and frame[column].notna().any():
            usable_numeric.append(column)
        else:
            dropped_numeric.append(column)

    usable_categorical: list[str] = []
    dropped_categorical: list[str] = []
    for column in categorical_features:
        if column in frame.columns and frame[column].notna().any():
            usable_categorical.append(column)
        else:
            dropped_categorical.append(column)

    if not usable_numeric and not usable_categorical:
        raise RuntimeError("Training split does not contain any usable model features.")

    return usable_numeric, usable_categorical, dropped_numeric, dropped_categorical


def _expand_legacy_context(frame: Any, pd: Any) -> Any:
    if "extra" not in frame.columns:
        return frame

    working = frame.copy()
    legacy_rows = []
    for extra in working["extra"]:
        payload = extra if isinstance(extra, dict) else {}
        codes = payload.get("legacy_codes") or {}
        location = payload.get("legacy_location") or {}
        legacy_rows.append(
            {
                "legacy_locinc": codes.get("locinc"),
                "legacy_nomestr": codes.get("nomestr"),
                "legacy_fondost": codes.get("fondost"),
                "legacy_intnin": codes.get("intnin"),
                "legacy_natinc": codes.get("natinc"),
                "legacy_orgril": codes.get("orgril"),
                "legacy_pavim": codes.get("pavim"),
                "legacy_segnal": codes.get("segnal"),
                "legacy_tipost": codes.get("tipost"),
                "legacy_tipoveia": codes.get("tipoveia"),
                "legacy_tipoveib": codes.get("tipoveib"),
                "legacy_tipoveic": codes.get("tipoveic"),
                "legacy_road_code": location.get("road_code"),
            }
        )
    legacy_frame = pd.DataFrame(legacy_rows, index=working.index)
    for column in legacy_frame.columns:
        working[column] = legacy_frame[column]
    return working


def _evaluate_predictions(
    predictions: Any,
    actuals: Any,
    np: Any,
    mean_absolute_error: Any,
    mean_poisson_deviance: Any,
    root_mean_squared_error: Any,
    top_5pct_crash_share: float,
) -> dict[str, float]:
    clipped = np.clip(np.asarray(predictions, dtype=float), 0.0, None)
    return {
        "mae": float(mean_absolute_error(actuals, clipped)),
        "rmse": float(root_mean_squared_error(actuals, clipped)),
        "mean_poisson_deviance": float(mean_poisson_deviance(actuals, clipped + 1e-9)),
        "prediction_sum": float(clipped.sum()),
        "top_5pct_crash_share": float(top_5pct_crash_share),
    }


def _evaluate_classifier_probabilities(
    probabilities: Any,
    actuals: Any,
    np: Any,
    average_precision_score: Any,
    brier_score_loss: Any,
    log_loss: Any,
    roc_auc_score: Any,
    top_fraction: float = 0.05,
) -> dict[str, float]:
    probs = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1.0 - 1e-9)
    labels = np.asarray(actuals, dtype=int)

    ranked_indices = np.argsort(-probs)
    positive_total = int(labels.sum())

    metrics = {
        "roc_auc": float(roc_auc_score(labels, probs)),
        "average_precision": float(average_precision_score(labels, probs)),
        "brier_score": float(brier_score_loss(labels, probs)),
        "log_loss": float(log_loss(labels, probs)),
        "predicted_positive_mean": float(probs.mean()),
        "actual_positive_rate": float(labels.mean()),
        "positive_count": positive_total,
    }
    for fraction, label in [(top_fraction, "top_5pct"), (0.10, "top_10pct"), (0.20, "top_20pct")]:
        top_k = max(1, int(len(labels) * fraction))
        top_labels = labels[ranked_indices[:top_k]]
        positive_in_top = int(top_labels.sum())
        metrics[f"{label}_fatal_recall"] = float(positive_in_top / positive_total) if positive_total else 0.0
        metrics[f"{label}_fatal_precision"] = float(positive_in_top / top_k) if top_k else 0.0
        metrics[f"{label}_sample_size"] = top_k
    return metrics


def train_frequency_baseline(
    aggregate_csv_path: str | Path,
    output_dir: str | Path,
    holdout_year: int | None = None,
) -> dict[str, Any]:
    (
        joblib,
        np,
        pd,
        ColumnTransformer,
        _RandomForestClassifier,
        RandomForestRegressor,
        SimpleImputer,
        _LogisticRegression,
        _average_precision_score,
        _brier_score_loss,
        _log_loss,
        PoissonRegressor,
        mean_absolute_error,
        mean_poisson_deviance,
        root_mean_squared_error,
        _roc_auc_score,
        Pipeline,
        OneHotEncoder,
        StandardScaler,
    ) = _load_ml_stack()

    input_path = Path(aggregate_csv_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    model_path = output_root / "frequency_baseline.joblib"
    predictions_path = output_root / "holdout_predictions.csv"
    metrics_path = output_root / "frequency_baseline.metrics.json"

    frame = pd.read_csv(input_path, low_memory=False)
    frame = _add_temporal_history_features(frame, pd)

    if holdout_year is None:
        holdout_year = int(frame["occurred_year"].max())

    available_numeric = [column for column in NUMERIC_FEATURES if column in frame.columns]
    available_categorical = [column for column in CATEGORICAL_FEATURES if column in frame.columns]
    feature_columns = available_numeric + available_categorical

    for column in available_numeric + [TARGET_COLUMN]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[TARGET_COLUMN].isna().any():
        raise RuntimeError("Aggregate table contains invalid crash_count values.")
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].fillna(0.0)
    for column in available_categorical:
        frame[column] = _normalize_categorical_column(frame[column])

    train_frame = frame.loc[frame["occurred_year"] < holdout_year].copy()
    test_frame = frame.loc[frame["occurred_year"] == holdout_year].copy()
    if train_frame.empty or test_frame.empty:
        raise RuntimeError(f"Could not form train/test split for holdout year {holdout_year}.")

    available_numeric, available_categorical, dropped_numeric, dropped_categorical = _prune_training_feature_columns(
        train_frame,
        available_numeric,
        available_categorical,
    )
    feature_columns = available_numeric + available_categorical
    temporal_history_columns = [column for column in TEMPORAL_HISTORY_FEATURES if column in frame.columns]

    linear_poisson_config = {
        "alpha": 50.0,
        "max_iter": 500,
    }
    random_forest_poisson_config = {
        "criterion": "poisson",
        "min_samples_leaf": 5,
        "n_estimators": 300,
        "random_state": 42,
    }

    X_train = train_frame[feature_columns]
    y_train = train_frame[TARGET_COLUMN]
    X_test = test_frame[feature_columns]
    y_test = test_frame[TARGET_COLUMN]

    def _build_preprocessor() -> Any:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        categorical_transformer = Pipeline(
            steps=[
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, available_numeric),
                ("categorical", categorical_transformer, available_categorical),
            ]
        )

    linear_model = Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            ("regressor", PoissonRegressor(**linear_poisson_config)),
        ]
    )
    tree_model = Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            (
                "regressor",
                RandomForestRegressor(**random_forest_poisson_config, n_jobs=-1),
            ),
        ]
    )

    linear_model.fit(X_train, y_train)
    tree_model.fit(X_train, y_train)

    linear_predictions = np.clip(linear_model.predict(X_test), 0.0, None)
    tree_predictions = np.clip(tree_model.predict(X_test), 0.0, None)
    naive_prediction = np.repeat(float(y_train.mean()), len(y_test))
    last_year_prediction = np.clip(test_frame["prior_year_crash_count"].to_numpy(dtype=float), 0.0, None)

    test_frame = test_frame.copy()
    test_frame["linear_poisson_prediction"] = linear_predictions
    test_frame["random_forest_poisson_prediction"] = tree_predictions
    test_frame["last_year_baseline_prediction"] = last_year_prediction
    test_frame["naive_mean_prediction"] = naive_prediction
    test_frame.sort_values(by="random_forest_poisson_prediction", ascending=False).to_csv(predictions_path, index=False)

    joblib.dump(
        {
            "linear_poisson": linear_model,
            "random_forest_poisson": tree_model,
            "feature_columns": feature_columns,
            "numeric_features": available_numeric,
            "categorical_features": available_categorical,
            "dropped_numeric_features": dropped_numeric,
            "dropped_categorical_features": dropped_categorical,
            "temporal_history_features": temporal_history_columns,
            "holdout_year": holdout_year,
        },
        model_path,
    )

    def _top_share(prediction_column: str) -> float:
        top_k = max(1, len(test_frame) // 20)
        ranked = test_frame.sort_values(by=prediction_column, ascending=False)
        top_predicted = ranked.head(top_k)
        total_crashes = float(y_test.sum())
        return float(top_predicted[TARGET_COLUMN].sum()) / total_crashes if total_crashes > 0 else 0.0

    metrics = {
        "input_path": str(input_path),
        "input_sha256": _sha256(input_path),
        "holdout_year": holdout_year,
        "feature_columns": feature_columns,
        "numeric_features": available_numeric,
        "categorical_features": available_categorical,
        "dropped_numeric_features": dropped_numeric,
        "dropped_categorical_features": dropped_categorical,
        "temporal_history_features": temporal_history_columns,
        "training_config": {
            "training_config_version": TRAINING_CONFIG_VERSION,
            "task": "segment_frequency_baseline",
            "split_strategy": "temporal_holdout_year",
            "target_column": TARGET_COLUMN,
            "holdout_year": holdout_year,
            "input_artifacts": [
                _artifact_reference(
                    "aggregate_segment_year_metrics",
                    input_path,
                    _sha256(input_path),
                )
            ],
            "feature_inventory": {
                "numeric_features": available_numeric,
                "categorical_features": available_categorical,
                "temporal_history_features": temporal_history_columns,
                "dropped_numeric_features": dropped_numeric,
                "dropped_categorical_features": dropped_categorical,
            },
            "estimators": {
                "linear_poisson": linear_poisson_config,
                "random_forest_poisson": random_forest_poisson_config,
                "last_year_baseline": {"feature": "prior_year_crash_count"},
                "naive_mean_baseline": {"strategy": "train_mean"},
            },
        },
        "train_rows": int(len(train_frame)),
        "test_rows": int(len(test_frame)),
        "train_crash_total": int(y_train.sum()),
        "test_crash_total": int(y_test.sum()),
        "linear_poisson_metrics": _evaluate_predictions(
            linear_predictions,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share("linear_poisson_prediction"),
        ),
        "random_forest_poisson_metrics": _evaluate_predictions(
            tree_predictions,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share("random_forest_poisson_prediction"),
        ),
        "last_year_baseline_metrics": _evaluate_predictions(
            last_year_prediction,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share("last_year_baseline_prediction"),
        ),
        "naive_mean_metrics": _evaluate_predictions(
            naive_prediction,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share("naive_mean_prediction"),
        ),
        "outputs": {
            "model_path": str(model_path),
            "model_sha256": _sha256(model_path),
            "predictions_path": str(predictions_path),
            "predictions_sha256": _sha256(predictions_path),
            "metrics_path": str(metrics_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=metrics_path,
            upstream_inputs=[
                _artifact_reference(
                    "aggregate_segment_year_metrics",
                    input_path,
                    _sha256(input_path),
                )
            ],
            publishable_outputs=[
                _artifact_reference(
                    "holdout_segment_predictions",
                    predictions_path,
                    _sha256(predictions_path),
                )
            ],
            supporting_outputs=[
                _artifact_reference(
                    "model_bundle",
                    model_path,
                    _sha256(model_path),
                )
            ],
        ),
    }
    metrics_sha256 = _write_metrics_payload(metrics, metrics_path)

    return {
        "metrics_path": str(metrics_path),
        "metrics_sha256": metrics_sha256,
        "holdout_year": holdout_year,
        "linear_poisson_metrics": metrics["linear_poisson_metrics"],
        "random_forest_poisson_metrics": metrics["random_forest_poisson_metrics"],
        "last_year_baseline_metrics": metrics["last_year_baseline_metrics"],
        "naive_mean_metrics": metrics["naive_mean_metrics"],
    }


def train_severity_baseline(
    matched_path: str | Path,
    aggregate_csv_path: str | Path,
    output_dir: str | Path,
    holdout_year: int | None = None,
) -> dict[str, Any]:
    (
        joblib,
        np,
        pd,
        ColumnTransformer,
        RandomForestClassifier,
        _RandomForestRegressor,
        SimpleImputer,
        LogisticRegression,
        average_precision_score,
        brier_score_loss,
        log_loss,
        _PoissonRegressor,
        _mean_absolute_error,
        _mean_poisson_deviance,
        _root_mean_squared_error,
        roc_auc_score,
        Pipeline,
        OneHotEncoder,
        StandardScaler,
    ) = _load_ml_stack()

    matched_input = Path(matched_path)
    aggregate_input = Path(aggregate_csv_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    model_path = output_root / "severity_baseline.joblib"
    predictions_path = output_root / "holdout_severity_predictions.csv"
    metrics_path = output_root / "severity_baseline.metrics.json"

    matched_frame = pd.read_json(matched_input, lines=True)
    matched_frame = _expand_legacy_context(matched_frame, pd)
    aggregate_frame = pd.read_csv(aggregate_input, low_memory=False)
    aggregate_frame = _add_temporal_history_features(aggregate_frame, pd)

    if holdout_year is None:
        holdout_year = int(matched_frame["occurred_year"].max())

    segment_feature_columns = ["segment_id", "occurred_year"] + [
        column for column in SEVERITY_SEGMENT_CONTEXT_COLUMNS if column in aggregate_frame.columns
    ]
    segment_features = aggregate_frame[segment_feature_columns].drop_duplicates(
        subset=["segment_id", "occurred_year"],
        keep="last",
    )

    frame = matched_frame.merge(segment_features, on=["segment_id", "occurred_year"], how="left")
    frame[SEVERITY_LABEL_COLUMN] = (
        (frame["severity_level"] == "fatal")
        | (pd.to_numeric(frame["fatalities"], errors="coerce").fillna(0) > 0)
    ).astype(int)

    available_numeric = [column for column in SEVERITY_NUMERIC_FEATURES if column in frame.columns]
    available_categorical = [column for column in SEVERITY_CATEGORICAL_FEATURES if column in frame.columns]
    feature_columns = available_numeric + available_categorical

    for column in available_numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in available_categorical:
        frame[column] = _normalize_categorical_column(frame[column])

    train_frame = frame.loc[frame["occurred_year"] < holdout_year].copy()
    test_frame = frame.loc[frame["occurred_year"] == holdout_year].copy()
    if train_frame.empty or test_frame.empty:
        raise RuntimeError(f"Could not form train/test split for holdout year {holdout_year}.")

    available_numeric, available_categorical, dropped_numeric, dropped_categorical = _prune_training_feature_columns(
        train_frame,
        available_numeric,
        available_categorical,
    )
    feature_columns = available_numeric + available_categorical
    temporal_history_columns = [column for column in TEMPORAL_HISTORY_FEATURES if column in frame.columns]

    logistic_regression_config = {
        "class_weight": "balanced",
        "max_iter": 1000,
        "random_state": 42,
        "solver": "liblinear",
    }
    random_forest_classifier_config = {
        "class_weight": "balanced_subsample",
        "criterion": "log_loss",
        "min_samples_leaf": 5,
        "n_estimators": 400,
        "random_state": 42,
    }

    y_train = train_frame[SEVERITY_LABEL_COLUMN].astype(int)
    y_test = test_frame[SEVERITY_LABEL_COLUMN].astype(int)
    if int(y_train.sum()) == 0 or int(y_train.sum()) == int(len(y_train)):
        raise RuntimeError("Training split must contain both fatal and non-fatal crashes.")
    if int(y_test.sum()) == 0 or int(y_test.sum()) == int(len(y_test)):
        raise RuntimeError("Holdout split must contain both fatal and non-fatal crashes.")

    X_train = train_frame[feature_columns]
    X_test = test_frame[feature_columns]

    def _build_preprocessor() -> Any:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        categorical_transformer = Pipeline(
            steps=[
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("numeric", numeric_transformer, available_numeric),
                ("categorical", categorical_transformer, available_categorical),
            ]
        )

    logistic_model = Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            (
                "classifier",
                LogisticRegression(**logistic_regression_config),
            ),
        ]
    )
    forest_model = Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            (
                "classifier",
                RandomForestClassifier(**random_forest_classifier_config, n_jobs=-1),
            ),
        ]
    )

    logistic_model.fit(X_train, y_train)
    forest_model.fit(X_train, y_train)

    logistic_probabilities = logistic_model.predict_proba(X_test)[:, 1]
    forest_probabilities = forest_model.predict_proba(X_test)[:, 1]
    naive_probability = np.repeat(float(y_train.mean()), len(y_test))
    prior_probability = (
        test_frame["prior_total_fatalities_total"].fillna(0.0)
        / test_frame["prior_total_crash_count"].replace(0, np.nan)
    ).fillna(0.0).to_numpy(dtype=float)

    test_frame = test_frame.copy()
    test_frame["logistic_fatal_probability"] = logistic_probabilities
    test_frame["random_forest_fatal_probability"] = forest_probabilities
    test_frame["prior_segment_fatality_probability"] = prior_probability
    test_frame["naive_fatal_probability"] = naive_probability
    test_frame.sort_values(by="random_forest_fatal_probability", ascending=False).to_csv(predictions_path, index=False)

    joblib.dump(
        {
            "logistic_regression": logistic_model,
            "random_forest_classifier": forest_model,
            "feature_columns": feature_columns,
            "numeric_features": available_numeric,
            "categorical_features": available_categorical,
            "dropped_numeric_features": dropped_numeric,
            "dropped_categorical_features": dropped_categorical,
            "label_column": SEVERITY_LABEL_COLUMN,
            "holdout_year": holdout_year,
        },
        model_path,
    )

    metrics = {
        "matched_input_path": str(matched_input),
        "matched_input_sha256": _sha256(matched_input),
        "aggregate_input_path": str(aggregate_input),
        "aggregate_input_sha256": _sha256(aggregate_input),
        "holdout_year": holdout_year,
        "feature_columns": feature_columns,
        "numeric_features": available_numeric,
        "categorical_features": available_categorical,
        "dropped_numeric_features": dropped_numeric,
        "dropped_categorical_features": dropped_categorical,
        "training_config": {
            "training_config_version": TRAINING_CONFIG_VERSION,
            "task": "crash_severity_baseline",
            "split_strategy": "temporal_holdout_year",
            "label_column": SEVERITY_LABEL_COLUMN,
            "label_definition": "fatal crash if severity_level == 'fatal' or fatalities > 0",
            "holdout_year": holdout_year,
            "input_artifacts": [
                _artifact_reference(
                    "matched_crash_records",
                    matched_input,
                    _sha256(matched_input),
                ),
                _artifact_reference(
                    "aggregate_segment_year_metrics",
                    aggregate_input,
                    _sha256(aggregate_input),
                ),
            ],
            "feature_inventory": {
                "numeric_features": available_numeric,
                "categorical_features": available_categorical,
                "temporal_history_features": temporal_history_columns,
                "dropped_numeric_features": dropped_numeric,
                "dropped_categorical_features": dropped_categorical,
            },
            "estimators": {
                "logistic_regression": logistic_regression_config,
                "random_forest_classifier": random_forest_classifier_config,
                "prior_segment_fatality_baseline": {
                    "numerator": "prior_total_fatalities_total",
                    "denominator": "prior_total_crash_count",
                },
                "naive_fatal_rate_baseline": {"strategy": "train_positive_rate"},
            },
        },
        "train_rows": int(len(train_frame)),
        "test_rows": int(len(test_frame)),
        "train_fatal_count": int(y_train.sum()),
        "test_fatal_count": int(y_test.sum()),
        "train_positive_rate": float(y_train.mean()),
        "test_positive_rate": float(y_test.mean()),
        "logistic_regression_metrics": _evaluate_classifier_probabilities(
            logistic_probabilities,
            y_test,
            np,
            average_precision_score,
            brier_score_loss,
            log_loss,
            roc_auc_score,
        ),
        "random_forest_classifier_metrics": _evaluate_classifier_probabilities(
            forest_probabilities,
            y_test,
            np,
            average_precision_score,
            brier_score_loss,
            log_loss,
            roc_auc_score,
        ),
        "prior_segment_fatality_metrics": _evaluate_classifier_probabilities(
            prior_probability,
            y_test,
            np,
            average_precision_score,
            brier_score_loss,
            log_loss,
            roc_auc_score,
        ),
        "naive_fatal_rate_metrics": _evaluate_classifier_probabilities(
            naive_probability,
            y_test,
            np,
            average_precision_score,
            brier_score_loss,
            log_loss,
            roc_auc_score,
        ),
        "outputs": {
            "model_path": str(model_path),
            "model_sha256": _sha256(model_path),
            "predictions_path": str(predictions_path),
            "predictions_sha256": _sha256(predictions_path),
            "metrics_path": str(metrics_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=metrics_path,
            upstream_inputs=[
                _artifact_reference(
                    "matched_crash_records",
                    matched_input,
                    _sha256(matched_input),
                ),
                _artifact_reference(
                    "aggregate_segment_year_metrics",
                    aggregate_input,
                    _sha256(aggregate_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "holdout_crash_severity_predictions",
                    predictions_path,
                    _sha256(predictions_path),
                )
            ],
            supporting_outputs=[
                _artifact_reference(
                    "model_bundle",
                    model_path,
                    _sha256(model_path),
                )
            ],
        ),
    }
    metrics_sha256 = _write_metrics_payload(metrics, metrics_path)

    return {
        "metrics_path": str(metrics_path),
        "metrics_sha256": metrics_sha256,
        "holdout_year": holdout_year,
        "logistic_regression_metrics": metrics["logistic_regression_metrics"],
        "random_forest_classifier_metrics": metrics["random_forest_classifier_metrics"],
        "prior_segment_fatality_metrics": metrics["prior_segment_fatality_metrics"],
        "naive_fatal_rate_metrics": metrics["naive_fatal_rate_metrics"],
    }
