"""Cross-jurisdiction transferability evaluation utilities."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .modeling import (
    CATEGORICAL_FEATURES,
    LINEAGE_CONTRACT_VERSION,
    NUMERIC_FEATURES,
    TEMPORAL_HISTORY_FEATURES,
    TARGET_COLUMN,
    TRAINING_CONFIG_VERSION,
    _add_temporal_history_features,
    _artifact_reference,
    _build_lineage_contract,
    _evaluate_predictions,
    _load_ml_stack,
    _normalize_categorical_column,
    _prune_training_feature_columns,
    _sha256,
    _write_metrics_payload,
)

EVALUATION_MODES = [
    "within_jurisdiction_temporal",
    "cross_jurisdiction_temporal",
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
]


def _build_preprocessor(
    available_numeric: list[str],
    available_categorical: list[str],
    ColumnTransformer: Any,
    SimpleImputer: Any,
    StandardScaler: Any,
    OneHotEncoder: Any,
    Pipeline: Any,
) -> Any:
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


def _top_share(frame: Any, prediction_column: str, target_column: str = TARGET_COLUMN) -> float:
    top_k = max(1, len(frame) // 20)
    ranked = frame.sort_values(by=prediction_column, ascending=False)
    top_predicted = ranked.head(top_k)
    total_crashes = float(frame[target_column].sum())
    return float(top_predicted[target_column].sum()) / total_crashes if total_crashes > 0 else 0.0


def _prepare_frequency_frame(frame: Any, label: str, pd: Any) -> Any:
    working = frame.copy()
    working["transfer_jurisdiction"] = label
    if "segment_id" not in working.columns:
        raise RuntimeError("Aggregate dataset must contain 'segment_id' column.")
    working["segment_id"] = working["segment_id"].astype(str).map(lambda value: f"{label}::{value}")
    working = _add_temporal_history_features(working, pd)

    for column in [*NUMERIC_FEATURES, TARGET_COLUMN]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    if TARGET_COLUMN not in working.columns:
        raise RuntimeError("Aggregate dataset must contain 'crash_count' column.")
    if working[TARGET_COLUMN].isna().any():
        raise RuntimeError("Aggregate dataset contains invalid crash_count values.")
    working[TARGET_COLUMN] = working[TARGET_COLUMN].fillna(0.0)

    for column in CATEGORICAL_FEATURES:
        if column in working.columns:
            working[column] = _normalize_categorical_column(working[column])
    return working


def _zero_temporal_history_features(frame: Any, temporal_columns: list[str]) -> Any:
    working = frame.copy()
    for column in temporal_columns:
        if column in working.columns:
            working[column] = 0.0
    return working


def _fit_and_score_frequency_models(
    train_frame: Any,
    test_frame: Any,
    available_numeric: list[str],
    available_categorical: list[str],
    np: Any,
    ColumnTransformer: Any,
    RandomForestRegressor: Any,
    SimpleImputer: Any,
    PoissonRegressor: Any,
    mean_absolute_error: Any,
    mean_poisson_deviance: Any,
    root_mean_squared_error: Any,
    Pipeline: Any,
    OneHotEncoder: Any,
    StandardScaler: Any,
    model_numeric_features: list[str] | None = None,
    model_categorical_features: list[str] | None = None,
    rf_n_estimators: int = 300,
) -> tuple[dict[str, Any], Any]:
    numeric_features = model_numeric_features if model_numeric_features is not None else available_numeric
    categorical_features = (
        model_categorical_features if model_categorical_features is not None else available_categorical
    )
    numeric_features, categorical_features, dropped_numeric, dropped_categorical = _prune_training_feature_columns(
        train_frame,
        numeric_features,
        categorical_features,
    )
    feature_columns = numeric_features + categorical_features
    X_train = train_frame[feature_columns]
    y_train = train_frame[TARGET_COLUMN]
    X_test = test_frame[feature_columns]
    y_test = test_frame[TARGET_COLUMN]

    linear_poisson_config = {
        "alpha": 50.0,
        "max_iter": 500,
    }
    random_forest_config = {
        "criterion": "poisson",
        "min_samples_leaf": 5,
        "n_estimators": rf_n_estimators,
        "random_state": 42,
    }

    linear_model = Pipeline(
        steps=[
            (
                "preprocessor",
                _build_preprocessor(
                    numeric_features,
                    categorical_features,
                    ColumnTransformer,
                    SimpleImputer,
                    StandardScaler,
                    OneHotEncoder,
                    Pipeline,
                ),
            ),
            ("regressor", PoissonRegressor(**linear_poisson_config)),
        ]
    )
    tree_model = Pipeline(
        steps=[
            (
                "preprocessor",
                _build_preprocessor(
                    numeric_features,
                    categorical_features,
                    ColumnTransformer,
                    SimpleImputer,
                    StandardScaler,
                    OneHotEncoder,
                    Pipeline,
                ),
            ),
            (
                "regressor",
                RandomForestRegressor(**random_forest_config, n_jobs=-1),
            ),
        ]
    )

    linear_model.fit(X_train, y_train)
    tree_model.fit(X_train, y_train)

    linear_predictions = np.clip(linear_model.predict(X_test), 0.0, None)
    tree_predictions = np.clip(tree_model.predict(X_test), 0.0, None)
    naive_prediction = np.repeat(float(y_train.mean()), len(y_test))
    last_year_prediction = np.clip(test_frame["prior_year_crash_count"].to_numpy(dtype=float), 0.0, None)

    scored_test = test_frame.copy()
    scored_test["linear_poisson_prediction"] = linear_predictions
    scored_test["random_forest_poisson_prediction"] = tree_predictions
    scored_test["naive_mean_prediction"] = naive_prediction
    scored_test["last_year_baseline_prediction"] = last_year_prediction

    metrics = {
        "model_numeric_features": numeric_features,
        "model_categorical_features": categorical_features,
        "model_feature_columns": feature_columns,
        "dropped_numeric_features": dropped_numeric,
        "dropped_categorical_features": dropped_categorical,
        "linear_poisson_config": linear_poisson_config,
        "random_forest_config": random_forest_config,
        "train_rows": int(len(train_frame)),
        "test_rows": int(len(scored_test)),
        "train_crash_total": int(y_train.sum()),
        "test_crash_total": int(y_test.sum()),
        "linear_poisson_metrics": _evaluate_predictions(
            linear_predictions,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share(scored_test, "linear_poisson_prediction"),
        ),
        "random_forest_poisson_metrics": _evaluate_predictions(
            tree_predictions,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share(scored_test, "random_forest_poisson_prediction"),
        ),
        "last_year_baseline_metrics": _evaluate_predictions(
            last_year_prediction,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share(scored_test, "last_year_baseline_prediction"),
        ),
        "naive_mean_metrics": _evaluate_predictions(
            naive_prediction,
            y_test,
            np,
            mean_absolute_error,
            mean_poisson_deviance,
            root_mean_squared_error,
            _top_share(scored_test, "naive_mean_prediction"),
        ),
    }
    return metrics, scored_test


def evaluate_frequency_transferability(
    datasets: list[tuple[str, str | Path]],
    output_dir: str | Path,
    holdout_year: int,
    rf_n_estimators: int = 300,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    started_at = perf_counter()
    if len(datasets) < 2:
        raise RuntimeError("At least two labeled aggregate datasets are required for transferability evaluation.")
    requested_modes = list(modes) if modes is not None else list(EVALUATION_MODES)
    invalid_modes = sorted(set(requested_modes) - set(EVALUATION_MODES))
    if invalid_modes:
        raise RuntimeError(
            "Unsupported transferability modes: "
            + ", ".join(invalid_modes)
            + ". Valid modes are: "
            + ", ".join(EVALUATION_MODES)
        )
    if not requested_modes:
        raise RuntimeError("At least one transferability evaluation mode must be selected.")

    (
        _joblib,
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

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    metrics_path = output_root / "frequency_transferability.metrics.json"
    predictions_path = output_root / "frequency_transferability_predictions.csv"

    prepared_frames: dict[str, Any] = {}
    dataset_inputs: list[dict[str, Any]] = []
    common_numeric: set[str] | None = None
    common_categorical: set[str] | None = None

    for label, dataset_path in datasets:
        input_path = Path(dataset_path)
        frame = pd.read_csv(input_path, low_memory=False)
        frame = _prepare_frequency_frame(frame, label=label, pd=pd)
        prepared_frames[label] = frame
        dataset_inputs.append(
            {
                "label": label,
                "path": str(input_path),
                "sha256": _sha256(input_path),
                "rows": int(len(frame)),
                "crash_total": int(frame[TARGET_COLUMN].sum()),
            }
        )
        current_numeric = {column for column in NUMERIC_FEATURES if column in frame.columns}
        current_categorical = {column for column in CATEGORICAL_FEATURES if column in frame.columns}
        common_numeric = current_numeric if common_numeric is None else common_numeric & current_numeric
        common_categorical = current_categorical if common_categorical is None else common_categorical & current_categorical

    available_numeric = sorted(common_numeric or set())
    available_categorical = sorted(common_categorical or set())
    feature_columns = available_numeric + available_categorical
    if not feature_columns:
        raise RuntimeError("No common frequency-model features were found across the provided datasets.")

    all_predictions: list[dict[str, Any]] = []
    within_jurisdiction: dict[str, Any] = {}
    cross_jurisdiction: dict[str, Any] = {}
    cross_jurisdiction_cold_start: dict[str, Any] = {}
    cross_jurisdiction_history_free: dict[str, Any] = {}
    available_temporal_history = [column for column in TEMPORAL_HISTORY_FEATURES if column in available_numeric]
    history_free_numeric_features = [column for column in available_numeric if column not in available_temporal_history]

    for target_label, target_frame in prepared_frames.items():
        within_train = target_frame.loc[target_frame["occurred_year"] < holdout_year].copy()
        within_test = target_frame.loc[target_frame["occurred_year"] == holdout_year].copy()
        if within_train.empty or within_test.empty:
            raise RuntimeError(f"Dataset '{target_label}' cannot form a within-jurisdiction split for {holdout_year}.")
        if "within_jurisdiction_temporal" in requested_modes:
            within_metrics, within_predictions = _fit_and_score_frequency_models(
                train_frame=within_train,
                test_frame=within_test,
                available_numeric=available_numeric,
                available_categorical=available_categorical,
                np=np,
                ColumnTransformer=ColumnTransformer,
                RandomForestRegressor=RandomForestRegressor,
                SimpleImputer=SimpleImputer,
                PoissonRegressor=PoissonRegressor,
                mean_absolute_error=mean_absolute_error,
                mean_poisson_deviance=mean_poisson_deviance,
                root_mean_squared_error=root_mean_squared_error,
                Pipeline=Pipeline,
                OneHotEncoder=OneHotEncoder,
                StandardScaler=StandardScaler,
                rf_n_estimators=rf_n_estimators,
            )
            within_metrics["train_jurisdictions"] = [target_label]
            within_metrics["test_jurisdiction"] = target_label
            within_jurisdiction[target_label] = within_metrics
            for row in within_predictions.to_dict(orient="records"):
                row["evaluation_mode"] = "within_jurisdiction_temporal"
                row["target_jurisdiction"] = target_label
                all_predictions.append(row)

        source_labels = [label for label in prepared_frames.keys() if label != target_label]
        cross_train_frames = [
            prepared_frames[label].loc[prepared_frames[label]["occurred_year"] < holdout_year].copy()
            for label in source_labels
        ]
        cross_train = pd.concat(cross_train_frames, ignore_index=True)
        cross_test = target_frame.loc[target_frame["occurred_year"] == holdout_year].copy()
        if cross_train.empty or cross_test.empty:
            raise RuntimeError(f"Dataset '{target_label}' cannot form a cross-jurisdiction split for {holdout_year}.")
        if "cross_jurisdiction_temporal" in requested_modes:
            cross_metrics, cross_predictions = _fit_and_score_frequency_models(
                train_frame=cross_train,
                test_frame=cross_test,
                available_numeric=available_numeric,
                available_categorical=available_categorical,
                np=np,
                ColumnTransformer=ColumnTransformer,
                RandomForestRegressor=RandomForestRegressor,
                SimpleImputer=SimpleImputer,
                PoissonRegressor=PoissonRegressor,
                mean_absolute_error=mean_absolute_error,
                mean_poisson_deviance=mean_poisson_deviance,
                root_mean_squared_error=root_mean_squared_error,
                Pipeline=Pipeline,
                OneHotEncoder=OneHotEncoder,
                StandardScaler=StandardScaler,
                rf_n_estimators=rf_n_estimators,
            )
            cross_metrics["train_jurisdictions"] = source_labels
            cross_metrics["test_jurisdiction"] = target_label
            cross_metrics["evaluation_note"] = (
                "Target holdout rows retain their own prior-year crash history features; "
                "this is transfer across jurisdictions with local temporal history available."
            )
            cross_jurisdiction[target_label] = cross_metrics
            for row in cross_predictions.to_dict(orient="records"):
                row["evaluation_mode"] = "cross_jurisdiction_temporal"
                row["target_jurisdiction"] = target_label
                all_predictions.append(row)

        if "cross_jurisdiction_cold_start" in requested_modes:
            cold_start_test = _zero_temporal_history_features(cross_test, available_temporal_history)
            cold_metrics, cold_predictions = _fit_and_score_frequency_models(
                train_frame=cross_train,
                test_frame=cold_start_test,
                available_numeric=available_numeric,
                available_categorical=available_categorical,
                np=np,
                ColumnTransformer=ColumnTransformer,
                RandomForestRegressor=RandomForestRegressor,
                SimpleImputer=SimpleImputer,
                PoissonRegressor=PoissonRegressor,
                mean_absolute_error=mean_absolute_error,
                mean_poisson_deviance=mean_poisson_deviance,
                root_mean_squared_error=root_mean_squared_error,
                Pipeline=Pipeline,
                OneHotEncoder=OneHotEncoder,
                StandardScaler=StandardScaler,
                rf_n_estimators=rf_n_estimators,
            )
            cold_metrics["train_jurisdictions"] = source_labels
            cold_metrics["test_jurisdiction"] = target_label
            cold_metrics["evaluation_note"] = (
                "Target holdout rows have temporal history features zeroed at test time. "
                "This approximates cold-start transfer without target-city crash history."
            )
            cold_metrics["zeroed_temporal_history_features"] = available_temporal_history
            cross_jurisdiction_cold_start[target_label] = cold_metrics
            for row in cold_predictions.to_dict(orient="records"):
                row["evaluation_mode"] = "cross_jurisdiction_cold_start"
                row["target_jurisdiction"] = target_label
                all_predictions.append(row)

        if "cross_jurisdiction_history_free" in requested_modes:
            history_free_metrics, history_free_predictions = _fit_and_score_frequency_models(
                train_frame=cross_train,
                test_frame=cross_test,
                available_numeric=available_numeric,
                available_categorical=available_categorical,
                np=np,
                ColumnTransformer=ColumnTransformer,
                RandomForestRegressor=RandomForestRegressor,
                SimpleImputer=SimpleImputer,
                PoissonRegressor=PoissonRegressor,
                mean_absolute_error=mean_absolute_error,
                mean_poisson_deviance=mean_poisson_deviance,
                root_mean_squared_error=root_mean_squared_error,
                Pipeline=Pipeline,
                OneHotEncoder=OneHotEncoder,
                StandardScaler=StandardScaler,
                model_numeric_features=history_free_numeric_features,
                model_categorical_features=available_categorical,
                rf_n_estimators=rf_n_estimators,
            )
            history_free_metrics["train_jurisdictions"] = source_labels
            history_free_metrics["test_jurisdiction"] = target_label
            history_free_metrics["evaluation_note"] = (
                "Models are trained and evaluated without temporal-history features. "
                "Reference baselines still include last-year predictions for comparison."
            )
            history_free_metrics["excluded_temporal_history_features"] = available_temporal_history
            cross_jurisdiction_history_free[target_label] = history_free_metrics
            for row in history_free_predictions.to_dict(orient="records"):
                row["evaluation_mode"] = "cross_jurisdiction_history_free"
                row["target_jurisdiction"] = target_label
                all_predictions.append(row)

    if all_predictions:
        fieldnames = sorted({key for row in all_predictions for key in row.keys()})
        with predictions_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_predictions)

    runtime_seconds = perf_counter() - started_at
    metrics = {
        "holdout_year": holdout_year,
        "dataset_inputs": dataset_inputs,
        "common_numeric_features": available_numeric,
        "common_categorical_features": available_categorical,
        "feature_columns": feature_columns,
        "random_forest_n_estimators": rf_n_estimators,
        "requested_modes": requested_modes,
        "profiling": {
            "runtime_seconds": round(runtime_seconds, 6),
            "dataset_count": len(dataset_inputs),
            "requested_mode_count": len(requested_modes),
            "target_jurisdiction_count": len(prepared_frames),
            "total_dataset_rows": int(sum(int(item["rows"]) for item in dataset_inputs)),
        },
        "training_config": {
            "training_config_version": TRAINING_CONFIG_VERSION,
            "task": "frequency_transferability_evaluation",
            "split_strategy": "leave_one_jurisdiction_out_temporal_holdout",
            "target_column": TARGET_COLUMN,
            "holdout_year": holdout_year,
            "requested_modes": requested_modes,
            "dataset_labels": [item["label"] for item in dataset_inputs],
            "input_artifacts": [
                _artifact_reference(
                    f"aggregate_segment_year_metrics:{item['label']}",
                    Path(item["path"]),
                    item["sha256"],
                )
                for item in dataset_inputs
            ],
            "feature_inventory": {
                "common_numeric_features": available_numeric,
                "common_categorical_features": available_categorical,
                "temporal_history_features": available_temporal_history,
                "history_free_numeric_features": history_free_numeric_features,
            },
            "estimators": {
                "linear_poisson": {
                    "alpha": 50.0,
                    "max_iter": 500,
                },
                "random_forest_poisson": {
                    "criterion": "poisson",
                    "min_samples_leaf": 5,
                    "n_estimators": rf_n_estimators,
                    "random_state": 42,
                },
            },
        },
        "within_jurisdiction_temporal": within_jurisdiction,
        "cross_jurisdiction_temporal": cross_jurisdiction,
        "cross_jurisdiction_cold_start": cross_jurisdiction_cold_start,
        "cross_jurisdiction_history_free": cross_jurisdiction_history_free,
        "outputs": {
            "metrics_path": str(metrics_path),
            "predictions_path": str(predictions_path),
            "predictions_sha256": _sha256(predictions_path),
        },
        "lineage": _build_lineage_contract(
            run_record_path=metrics_path,
            upstream_inputs=[
                _artifact_reference(
                    f"aggregate_segment_year_metrics:{item['label']}",
                    Path(item["path"]),
                    item["sha256"],
                )
                for item in dataset_inputs
            ],
            publishable_outputs=[
                _artifact_reference(
                    "transferability_predictions",
                    predictions_path,
                    _sha256(predictions_path),
                )
            ],
            supporting_outputs=[],
        ),
    }
    metrics_sha256 = _write_metrics_payload(metrics, metrics_path)

    return {
        "metrics_path": str(metrics_path),
        "metrics_sha256": metrics_sha256,
        "holdout_year": holdout_year,
        "random_forest_n_estimators": rf_n_estimators,
        "requested_modes": requested_modes,
        "within_jurisdiction_temporal": within_jurisdiction,
        "cross_jurisdiction_temporal": cross_jurisdiction,
        "cross_jurisdiction_cold_start": cross_jurisdiction_cold_start,
        "cross_jurisdiction_history_free": cross_jurisdiction_history_free,
    }
