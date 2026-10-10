"""Scientific-excellence benchmark: RF vs SPF vs Empirical Bayes.

Horizon Europe's *Excellence* criterion expects novelty validated to a
publishable standard: a formal protocol with uncertainty, calibration, spatial
cross-validation, and comparison against the **recognised** crash-prediction
baselines used in road-safety science — the **Safety Performance Function
(SPF)** and the **Highway Safety Manual Empirical Bayes (EB)** method.

This module evaluates four estimators of segment-year crash frequency on a
temporal holdout:

- ``naive_mean`` — global mean rate (floor).
- ``spf_poisson`` — a Safety Performance Function: a Poisson GLM of crash count
  on exposure/road features (the workhorse of the Highway Safety Manual).
- ``empirical_bayes`` — the HSM EB estimator combining the SPF prediction with
  the site's observed prior-year history, weighted by the estimated
  negative-binomial overdispersion.
- ``random_forest_poisson`` — the platform's model.

For each estimator it reports mean Poisson deviance, MAE, RMSE, and top-5%
crash capture, with **bootstrap 95% confidence intervals** on the headline
deviance, a **calibration** decile table, and a **spatial (grouped) cross-
validation** deviance to guard against spatial leakage. Outputs are written with
a lineage contract so the benchmark is openly reproducible.


"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .modeling import (
    TARGET_COLUMN,
    _artifact_reference,
    _build_lineage_contract,
    _load_ml_stack,
    _sha256,
)

SCIENTIFIC_BENCHMARK_VERSION = "scientific_benchmark_v1"
SCIENTIFIC_BENCHMARK_CONTRACT_VERSION = "scientific_benchmark_public_v1"

# Exposure / road-design features an SPF is conventionally built on. Missing
# columns are tolerated (the SPF simply uses what is present).
SPF_FEATURES = [
    "segment_length_m",
    "exposure_proxy_index",
    "road_class_rank",
    "maxspeed_numeric",
    "lanes_numeric",
    "width_numeric",
    "node_degree_max",
]

ESTIMATOR_LABELS = [
    "naive_mean",
    "spf_poisson",
    "empirical_bayes",
    "random_forest_poisson",
]


def _load_frame(path: Path, pd: Any) -> Any:
    frame = pd.read_csv(path)
    if "segment_id" not in frame.columns or "occurred_year" not in frame.columns:
        raise RuntimeError("Dataset must contain segment_id and occurred_year columns.")
    if TARGET_COLUMN not in frame.columns:
        raise RuntimeError(f"Dataset must contain {TARGET_COLUMN} column.")
    frame[TARGET_COLUMN] = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce").fillna(0.0)
    return frame


def _available_features(frame: Any) -> list[str]:
    return [column for column in SPF_FEATURES if column in frame.columns]


def _feature_matrix(frame: Any, features: list[str], np: Any, pd: Any) -> Any:
    if not features:
        return np.zeros((len(frame), 1), dtype=float)
    matrix = frame[features].apply(lambda col: pd.to_numeric(col, errors="coerce"))
    medians = matrix.median(numeric_only=True)
    matrix = matrix.fillna(medians).fillna(0.0)
    return matrix.to_numpy(dtype=float)


def _prior_year_counts(frame: Any, pd: Any) -> Any:
    """Observed prior-year crash count per row (0 if no prior observation)."""
    working = frame[["segment_id", "occurred_year", TARGET_COLUMN]].copy()
    working = working.sort_values(["segment_id", "occurred_year"])
    working["prior"] = working.groupby("segment_id")[TARGET_COLUMN].shift(1).fillna(0.0)
    return working["prior"]


def _top_5pct_share(predictions: Any, actuals: Any, np: Any) -> float:
    order = np.argsort(-np.asarray(predictions, dtype=float))
    top_k = max(1, len(order) // 20)
    total = float(np.asarray(actuals, dtype=float).sum())
    if total <= 0:
        return 0.0
    captured = float(np.asarray(actuals, dtype=float)[order[:top_k]].sum())
    return captured / total


def _metric_block(
    predictions: Any,
    actuals: Any,
    np: Any,
    mae: Any,
    mpd: Any,
    rmse: Any,
) -> dict[str, float]:
    pred = np.clip(np.asarray(predictions, dtype=float), 0.0, None)
    act = np.asarray(actuals, dtype=float)
    return {
        "mean_poisson_deviance": float(mpd(act, pred + 1e-9)),
        "mae": float(mae(act, pred)),
        "rmse": float(rmse(act, pred)),
        "top_5pct_crash_share": float(_top_5pct_share(pred, act, np)),
        "prediction_sum": float(pred.sum()),
    }


def _estimate_overdispersion(mu: Any, y: Any, np: Any) -> float:
    """Method-of-moments NB overdispersion alpha (Var = mu + alpha*mu^2).

    Returns a small positive alpha; the EB weight is w = 1 / (1 + alpha*mu).
    """
    mu = np.clip(np.asarray(mu, dtype=float), 1e-6, None)
    y = np.asarray(y, dtype=float)
    numerator = np.mean((y - mu) ** 2 - mu)
    denominator = np.mean(mu**2)
    if denominator <= 0:
        return 0.0
    return float(max(numerator / denominator, 0.0))


def _fit_spf(x_train: Any, y_train: Any, PoissonRegressor: Any, StandardScaler: Any, np: Any):
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x_train)
    model = PoissonRegressor(alpha=1e-3, max_iter=1000)
    model.fit(x_scaled, np.asarray(y_train, dtype=float))
    return model, scaler


def _spf_predict(model: Any, scaler: Any, x: Any) -> Any:
    return model.predict(scaler.transform(x))


def _bootstrap_deviance_ci(
    predictions: Any,
    actuals: Any,
    np: Any,
    mpd: Any,
    iterations: int = 500,
    seed: int = 1234,
) -> dict[str, float]:
    pred = np.clip(np.asarray(predictions, dtype=float), 0.0, None) + 1e-9
    act = np.asarray(actuals, dtype=float)
    n = len(act)
    rng = np.random.default_rng(seed)
    samples = np.empty(iterations, dtype=float)
    for i in range(iterations):
        idx = rng.integers(0, n, size=n)
        samples[i] = mpd(act[idx], pred[idx])
    return {
        "mean": float(samples.mean()),
        "ci95_low": float(np.percentile(samples, 2.5)),
        "ci95_high": float(np.percentile(samples, 97.5)),
        "bootstrap_iterations": iterations,
    }


def _calibration_table(predictions: Any, actuals: Any, np: Any, bins: int = 10) -> list[dict[str, float]]:
    pred = np.clip(np.asarray(predictions, dtype=float), 0.0, None)
    act = np.asarray(actuals, dtype=float)
    order = np.argsort(pred)
    rows: list[dict[str, float]] = []
    chunks = np.array_split(order, bins)
    for index, chunk in enumerate(chunks):
        if len(chunk) == 0:
            continue
        rows.append(
            {
                "decile": index + 1,
                "mean_predicted": float(pred[chunk].mean()),
                "mean_observed": float(act[chunk].mean()),
                "count": int(len(chunk)),
            }
        )
    return rows


def _spatial_blocks(segment_ids: Any, np: Any, folds: int) -> Any:
    """Deterministically assign each segment to a spatial block by hashing its
    id, so cross-validation holds out whole blocks (guards spatial leakage)."""
    import hashlib

    def _block(value: str) -> int:
        digest = hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()
        return int(digest[:8], 16) % folds

    return np.asarray([_block(value) for value in segment_ids], dtype=int)


def _predict_all(
    *,
    train: Any,
    test: Any,
    features: list[str],
    stack: tuple[Any, ...],
    rf_n_estimators: int,
) -> dict[str, Any]:
    (
        _joblib,
        np,
        pd,
        _ColumnTransformer,
        _RFC,
        RandomForestRegressor,
        _SimpleImputer,
        _LogReg,
        _ap,
        _brier,
        _ll,
        PoissonRegressor,
        _mae,
        _mpd,
        _rmse,
        _roc,
        _Pipeline,
        _OneHot,
        StandardScaler,
    ) = stack

    x_train = _feature_matrix(train, features, np, pd)
    x_test = _feature_matrix(test, features, np, pd)
    y_train = train[TARGET_COLUMN].to_numpy(dtype=float)

    predictions: dict[str, Any] = {}

    # Naive mean.
    predictions["naive_mean"] = np.full(len(test), float(y_train.mean()))

    # SPF (Poisson GLM).
    spf_model, spf_scaler = _fit_spf(x_train, y_train, PoissonRegressor, StandardScaler, np)
    spf_train_mu = _spf_predict(spf_model, spf_scaler, x_train)
    spf_test_mu = _spf_predict(spf_model, spf_scaler, x_test)
    predictions["spf_poisson"] = spf_test_mu

    # Empirical Bayes (HSM): combine SPF mean with observed prior-year history.
    alpha = _estimate_overdispersion(spf_train_mu, y_train, np)
    prior_test = test["_prior_year_count"].to_numpy(dtype=float)
    weight = 1.0 / (1.0 + alpha * np.clip(spf_test_mu, 0.0, None))
    predictions["empirical_bayes"] = weight * spf_test_mu + (1.0 - weight) * prior_test

    # Platform model: RF Poisson on the same exposure features.
    rf = RandomForestRegressor(
        n_estimators=rf_n_estimators,
        criterion="poisson",
        random_state=0,
        n_jobs=1,
    )
    rf.fit(x_train, y_train)
    predictions["random_forest_poisson"] = rf.predict(x_test)

    return {"predictions": predictions, "spf_alpha": alpha}


def run_scientific_benchmark(
    *,
    datasets: list[tuple[str, str | Path]],
    output_dir: str | Path,
    holdout_year: int,
    rf_n_estimators: int = 200,
    bootstrap_iterations: int = 500,
    spatial_folds: int = 5,
) -> dict[str, Any]:
    stack = _load_ml_stack()
    (
        _joblib,
        np,
        pd,
        *_rest,
    ) = stack
    mae = stack[12]
    mpd = stack[13]
    rmse = stack[14]

    if len(datasets) < 1:
        raise RuntimeError("At least one labeled dataset is required.")

    inputs = [(label, Path(path)) for label, path in datasets]
    frames = []
    for label, path in inputs:
        frame = _load_frame(path, pd)
        frame = frame.copy()
        frame["segment_id"] = frame["segment_id"].astype(str).map(lambda value, lbl=label: f"{lbl}::{value}")
        frames.append(frame)
    pooled = pd.concat(frames, ignore_index=True)
    pooled["_prior_year_count"] = _prior_year_counts(pooled, pd).to_numpy()

    features = _available_features(pooled)
    if not features:
        raise RuntimeError("No SPF exposure features present in the datasets.")

    train = pooled[pooled["occurred_year"] < holdout_year].reset_index(drop=True)
    test = pooled[pooled["occurred_year"] == holdout_year].reset_index(drop=True)
    if len(train) == 0 or len(test) == 0:
        raise RuntimeError("Temporal holdout produced an empty train or test split.")

    holdout = _predict_all(
        train=train, test=test, features=features, stack=stack, rf_n_estimators=rf_n_estimators
    )
    actuals = test[TARGET_COLUMN].to_numpy(dtype=float)

    estimator_results: dict[str, Any] = {}
    for label in ESTIMATOR_LABELS:
        preds = holdout["predictions"][label]
        estimator_results[label] = {
            "metrics": _metric_block(preds, actuals, np, mae, mpd, rmse),
            "deviance_ci": _bootstrap_deviance_ci(
                preds, actuals, np, mpd, iterations=bootstrap_iterations
            ),
            "calibration": _calibration_table(preds, actuals, np),
        }

    # Spatial (grouped) cross-validation across the full pooled table.
    blocks = _spatial_blocks(pooled["segment_id"].to_numpy(), np, spatial_folds)
    spatial_scores: dict[str, list[float]] = {label: [] for label in ESTIMATOR_LABELS}
    for fold in range(spatial_folds):
        cv_train = pooled[blocks != fold].reset_index(drop=True)
        cv_test = pooled[blocks == fold].reset_index(drop=True)
        if len(cv_train) == 0 or len(cv_test) == 0:
            continue
        fold_pred = _predict_all(
            train=cv_train,
            test=cv_test,
            features=features,
            stack=stack,
            rf_n_estimators=rf_n_estimators,
        )
        cv_actuals = cv_test[TARGET_COLUMN].to_numpy(dtype=float)
        for label in ESTIMATOR_LABELS:
            block = _metric_block(fold_pred["predictions"][label], cv_actuals, np, mae, mpd, rmse)
            spatial_scores[label].append(block["mean_poisson_deviance"])

    spatial_summary = {
        label: {
            "mean_poisson_deviance_mean": float(np.mean(scores)) if scores else None,
            "mean_poisson_deviance_std": float(np.std(scores)) if scores else None,
            "fold_count": len(scores),
        }
        for label, scores in spatial_scores.items()
    }

    # Rank estimators by holdout deviance and identify the platform model's standing.
    ranking = sorted(
        ESTIMATOR_LABELS,
        key=lambda label: estimator_results[label]["metrics"]["mean_poisson_deviance"],
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    metrics_path = output_root / "scientific_benchmark.metrics.json"
    report_path = output_root / "scientific_benchmark.md"
    manifest_path = output_root / "scientific_benchmark.manifest.json"

    payload = {
        "scientific_benchmark_version": SCIENTIFIC_BENCHMARK_VERSION,
        "holdout_year": holdout_year,
        "random_forest_n_estimators": rf_n_estimators,
        "spf_features": features,
        "spf_overdispersion_alpha": holdout["spf_alpha"],
        "dataset_inputs": [
            {"label": label, "path": str(path), "sha256": _sha256(path)} for label, path in inputs
        ],
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_crash_total": float(actuals.sum()),
        "estimators": estimator_results,
        "spatial_cross_validation": spatial_summary,
        "holdout_ranking_by_deviance": ranking,
        # Wall-clock timings are intentionally excluded from the public demo
        # artifact so that reproducibility checks compare scientific results,
        # not machine-dependent execution time.
        "profiling": {"runtime_seconds": None},
        "lineage": _build_lineage_contract(
            run_record_path=metrics_path,
            upstream_inputs=[
                _artifact_reference("benchmark_dataset", path, _sha256(path)) for _, path in inputs
            ],
            publishable_outputs=[
                _artifact_reference("scientific_benchmark_metrics", metrics_path, None),
            ],
        ),
    }
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")

    manifest = {
        "scientific_benchmark_version": SCIENTIFIC_BENCHMARK_VERSION,
        "contract": {
            "resource_name": "scientific_benchmark",
            "public_contract_version": SCIENTIFIC_BENCHMARK_CONTRACT_VERSION,
        },
        "outputs": {
            "metrics_path": str(metrics_path),
            "metrics_sha256": _sha256(metrics_path),
            "report_path": str(report_path),
            "report_sha256": _sha256(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "metrics_path": str(metrics_path),
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
        "holdout_ranking_by_deviance": ranking,
    }


def _fmt(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Scientific Benchmark: Platform vs SPF vs Empirical Bayes",
        "",
        f"- holdout year: `{payload['holdout_year']}`",
        f"- test rows: `{payload['test_rows']}` (crash total `{_fmt(payload['test_crash_total'], 1)}`)",
        f"- SPF features: `{', '.join(payload['spf_features'])}`",
        f"- SPF overdispersion alpha: `{_fmt(payload['spf_overdispersion_alpha'])}`",
        "",
        "## Holdout performance (mean Poisson deviance, lower is better)",
        "",
        "| Estimator | Deviance | 95% CI | MAE | Top-5% capture |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label in ESTIMATOR_LABELS:
        result = payload["estimators"][label]
        metrics = result["metrics"]
        ci = result["deviance_ci"]
        lines.append(
            f"| `{label}` | {_fmt(metrics['mean_poisson_deviance'])} | "
            f"[{_fmt(ci['ci95_low'])}, {_fmt(ci['ci95_high'])}] | "
            f"{_fmt(metrics['mae'])} | {_fmt(metrics['top_5pct_crash_share'])} |"
        )
    best = payload["holdout_ranking_by_deviance"][0]
    lines.extend(
        [
            "",
            f"**Best estimator by holdout deviance: `{best}`.**",
            "",
            "## Spatial cross-validation (grouped by segment block)",
            "",
            "| Estimator | Mean deviance | Std | Folds |",
            "| --- | --- | --- | --- |",
        ]
    )
    for label in ESTIMATOR_LABELS:
        spatial = payload["spatial_cross_validation"][label]
        lines.append(
            f"| `{label}` | {_fmt(spatial['mean_poisson_deviance_mean'])} | "
            f"{_fmt(spatial['mean_poisson_deviance_std'])} | {spatial['fold_count']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The SPF (Poisson GLM) and HSM Empirical Bayes estimators are the "
            "recognised road-safety baselines. Reporting the platform model "
            "against them with bootstrap confidence intervals, calibration, and "
            "spatial cross-validation is the publishable-standard protocol the "
            "Excellence criterion expects.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"
