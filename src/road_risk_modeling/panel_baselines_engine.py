"""Statistical Baselines to Poisson Boosted Trees Engine for Segment-Week Crash Risk.

Implements the evaluation hierarchy recommended in the Research Audit:
1. Baseline 1: Historical Exposure-Adjusted Rate (crashes / vehicle-km).
2. Baseline 2: Poisson GLM with log(exposure) offset.
3. Baseline 3: Negative-Binomial GLM with overdispersion estimation.
4. Baseline 4: Regularized Logistic Regression (binary occurrence).
5. ML Model: Poisson Gradient Boosted Trees with exposure offsets.
6. Full metric evaluation suite: Poisson deviance, NLL, MAE, PR-AUC, ROC-AUC, Brier score, Top-k capture curve.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256

BASELINES_ENGINE_VERSION = "panel_baselines_v1"
BASELINES_CONTRACT_VERSION = "panel_baselines_public_v1"


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return default if math.isnan(val) else float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "null", ""}:
        return default
    try:
        f = float(s)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    return int(round(_safe_float(val, float(default))))


def _poisson_deviance(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Compute mean Poisson deviance: 2 * sum(y * log(y / mu) - (y - mu)) / N."""
    n = len(y_true)
    if n == 0:
        return 0.0
    total_dev = 0.0
    for y, mu in zip(y_true, y_pred):
        mu_safe = max(1e-6, mu)
        if y > 0:
            term = y * math.log(y / mu_safe) - (y - mu_safe)
        else:
            term = mu_safe
        total_dev += 2.0 * term
    return total_dev / n


def _poisson_nll(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Compute mean Poisson negative log-likelihood."""
    n = len(y_true)
    if n == 0:
        return 0.0
    total_nll = 0.0
    for y, mu in zip(y_true, y_pred):
        mu_safe = max(1e-6, mu)
        log_fact = math.lgamma(y + 1.0) if y > 0 else 0.0
        total_nll += mu_safe - y * math.log(mu_safe) + log_fact
    return total_nll / n


def _mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    n = len(y_true)
    if n == 0:
        return 0.0
    return sum(abs(y - p) for y, p in zip(y_true, y_pred)) / n


def _brier_score(y_binary: Sequence[int], prob_pred: Sequence[float]) -> float:
    n = len(y_binary)
    if n == 0:
        return 0.0
    return sum((p - y) ** 2 for y, p in zip(y_binary, prob_pred)) / n


def _roc_and_pr_auc(y_binary: Sequence[int], scores: Sequence[float]) -> tuple[float, float]:
    """Calculate ROC-AUC and PR-AUC using trapezoidal integration."""
    n = len(y_binary)
    if n == 0:
        return 0.5, 0.0
    n_pos = sum(y_binary)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5, float(n_pos > 0)

    # Sort pairs by score descending
    pairs = sorted(zip(scores, y_binary), key=lambda x: x[0], reverse=True)

    # ROC curve
    tpr_list = [0.0]
    fpr_list = [0.0]
    # PR curve
    precision_list = [1.0]
    recall_list = [0.0]

    tp = 0
    fp = 0
    roc_auc = 0.0
    pr_auc = 0.0

    for score, y in pairs:
        if y == 1:
            tp += 1
        else:
            fp += 1
        tpr = tp / n_pos
        fpr = fp / n_neg
        prec = tp / (tp + fp)
        rec = tpr

        # Incremental trapezoid for ROC
        roc_auc += (fpr - fpr_list[-1]) * (tpr + tpr_list[-1]) / 2.0
        # Incremental trapezoid for PR
        pr_auc += (rec - recall_list[-1]) * (prec + precision_list[-1]) / 2.0

        tpr_list.append(tpr)
        fpr_list.append(fpr)
        precision_list.append(prec)
        recall_list.append(rec)

    return max(0.0, min(1.0, roc_auc)), max(0.0, min(1.0, pr_auc))


def _top_k_capture_curve(
    y_true: Sequence[float],
    scores: Sequence[float],
    k_percentiles: Sequence[float] = (0.05, 0.10, 0.20),
) -> dict[str, float]:
    """Fraction of total crashes captured in the top k% highest-risk predicted segments."""
    total_crashes = sum(y_true)
    if total_crashes <= 0:
        return {f"top_{int(k*100)}pct_capture": 0.0 for k in k_percentiles}

    pairs = sorted(zip(scores, y_true), key=lambda x: x[0], reverse=True)
    n = len(pairs)
    captures = {}

    for k in k_percentiles:
        cutoff = max(1, int(round(n * k)))
        captured_crashes = sum(c for _, c in pairs[:cutoff])
        captures[f"top_{int(k*100)}pct_capture"] = round(captured_crashes / total_crashes, 4)

    return captures


@dataclass(frozen=True, slots=True)
class ModelBenchmarkMetrics:
    """Comprehensive performance metrics for a road-risk model."""

    model_name: str
    model_family: str
    poisson_deviance: float
    poisson_nll: float
    mae: float
    brier_score: float
    roc_auc: float
    pr_auc: float
    top_5pct_capture: float
    top_10pct_capture: float
    top_20pct_capture: float
    fit_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_family": self.model_family,
            "poisson_deviance": round(self.poisson_deviance, 4),
            "poisson_nll": round(self.poisson_nll, 4),
            "mae": round(self.mae, 4),
            "brier_score": round(self.brier_score, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "top_5pct_capture": round(self.top_5pct_capture, 4),
            "top_10pct_capture": round(self.top_10pct_capture, 4),
            "top_20pct_capture": round(self.top_20pct_capture, 4),
            "fit_time_seconds": round(self.fit_time_seconds, 4),
        }


@dataclass(frozen=True, slots=True)
class PanelModelingExperimentReport:
    """Comparative benchmarking report evaluating baselines and boosted trees on a panel."""

    network_label: str
    train_size: int
    test_size: int
    features_evaluated: list[str]
    model_benchmarks: list[ModelBenchmarkMetrics]
    best_model_name: str
    evaluation_timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "baselines_engine_version": BASELINES_ENGINE_VERSION,
            "contract_version": BASELINES_CONTRACT_VERSION,
            "network_label": self.network_label,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "features_evaluated": self.features_evaluated,
            "model_benchmarks": [m.to_dict() for m in self.model_benchmarks],
            "best_model_name": self.best_model_name,
            "evaluation_timestamp_utc": self.evaluation_timestamp_utc,
        }


# --- Model 1: Historical Exposure-Adjusted Rate ---
class HistoricalExposureRateModel:
    """Baseline 1: Constant historical crash rate per vehicle-km: lambda = sum(Y) / sum(E)."""

    def __init__(self, smoothing_prior: float = 1e-4):
        self.smoothing_prior = smoothing_prior
        self.rate_per_vkm: float = 0.0

    def fit(self, y: Sequence[float], exposure: Sequence[float]) -> HistoricalExposureRateModel:
        tot_y = sum(y) + self.smoothing_prior
        tot_exp = sum(exposure) + 1.0
        self.rate_per_vkm = tot_y / tot_exp
        return self

    def predict(self, exposure: Sequence[float]) -> list[float]:
        return [self.rate_per_vkm * e for e in exposure]

    def predict_proba(self, exposure: Sequence[float]) -> list[float]:
        # Under Poisson process P(Y >= 1) = 1 - exp(-lambda * E)
        return [min(1.0, 1.0 - math.exp(-max(1e-6, self.rate_per_vkm * e))) for e in exposure]


# --- Model 2: Poisson GLM with log(exposure) offset ---
class PoissonGlmExposureModel:
    """Baseline 2: Poisson GLM with log(exposure) offset: mu = E * exp(beta_0 + X * beta)."""

    def __init__(self, learning_rate: float = 0.01, epochs: int = 150, l2_reg: float = 0.01):
        self.lr = learning_rate
        self.epochs = epochs
        self.l2 = l2_reg
        self.beta_0: float = 0.0
        self.weights: list[float] = []

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        log_exposure: Sequence[float],
    ) -> PoissonGlmExposureModel:
        n = len(X)
        if n == 0:
            return self
        p = len(X[0])
        self.weights = [0.0] * p
        tot_y = sum(y)
        tot_exp = sum(math.exp(le) for le in log_exposure)
        self.beta_0 = math.log(max(1e-5, tot_y / max(1.0, tot_exp)))

        # Gradient ascent on log-likelihood with L2 penalty
        for _ in range(self.epochs):
            grad_b0 = 0.0
            grad_w = [0.0] * p
            for i in range(n):
                lin = self.beta_0 + sum(X[i][j] * self.weights[j] for j in range(p)) + log_exposure[i]
                lin_clipped = min(12.0, max(-12.0, lin))
                mu_i = math.exp(lin_clipped)
                diff = y[i] - mu_i
                grad_b0 += diff
                for j in range(p):
                    grad_w[j] += diff * X[i][j]

            # Update parameters
            self.beta_0 += (self.lr / n) * grad_b0
            for j in range(p):
                self.weights[j] += (self.lr / n) * grad_w[j] - self.lr * self.l2 * self.weights[j]

        return self

    def predict(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        preds = []
        p = len(self.weights)
        for i, row in enumerate(X):
            lin = self.beta_0 + sum(row[j] * self.weights[j] for j in range(p)) + log_exposure[i]
            preds.append(math.exp(min(12.0, max(-12.0, lin))))
        return preds

    def predict_proba(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        preds = self.predict(X, log_exposure)
        return [min(1.0, 1.0 - math.exp(-mu)) for mu in preds]


# --- Model 3: Negative-Binomial GLM with Overdispersion ---
class NegativeBinomialExposureModel:
    """Baseline 3: Negative-Binomial GLM modeling overdispersion alpha."""

    def __init__(self, learning_rate: float = 0.01, epochs: int = 150, l2_reg: float = 0.01):
        self.base_poisson = PoissonGlmExposureModel(learning_rate, epochs, l2_reg)
        self.alpha: float = 0.15

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        log_exposure: Sequence[float],
    ) -> NegativeBinomialExposureModel:
        self.base_poisson.fit(X, y, log_exposure)
        preds = self.base_poisson.predict(X, log_exposure)
        # Estimate alpha from Pearson residual variance: (y - mu)^2 / mu - 1 / mu = alpha * mu
        diffs = []
        for yi, mui in zip(y, preds):
            if mui > 0.05:
                res_sq = (yi - mui) ** 2
                disp_est = (res_sq - mui) / max(0.01, mui ** 2)
                diffs.append(disp_est)
        self.alpha = max(0.01, min(2.0, sum(diffs) / max(1, len(diffs)))) if diffs else 0.15
        return self

    def predict(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        return self.base_poisson.predict(X, log_exposure)

    def predict_proba(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        # Under NegBin: P(Y=0) = (1 / (1 + alpha * mu))^(1 / alpha)
        preds = self.predict(X, log_exposure)
        probas = []
        inv_a = 1.0 / self.alpha
        for mu in preds:
            p_zero = (1.0 / (1.0 + self.alpha * mu)) ** inv_a
            probas.append(min(1.0, max(0.0, 1.0 - p_zero)))
        return probas


# --- Model 4: Regularized Logistic Regression (Binary Occurrence) ---
class RegularizedLogisticModel:
    """Baseline 4: Regularized logistic regression predicting P(crash >= 1)."""

    def __init__(self, learning_rate: float = 0.05, epochs: int = 150, l2_reg: float = 0.01):
        self.lr = learning_rate
        self.epochs = epochs
        self.l2 = l2_reg
        self.intercept: float = 0.0
        self.weights: list[float] = []

    def fit(self, X: Sequence[Sequence[float]], y_binary: Sequence[int]) -> RegularizedLogisticModel:
        n = len(X)
        if n == 0:
            return self
        p = len(X[0])
        self.weights = [0.0] * p
        pos = sum(y_binary)
        self.intercept = math.log(max(1e-4, pos / max(1, n - pos)))

        for _ in range(self.epochs):
            g_b = 0.0
            g_w = [0.0] * p
            for i in range(n):
                z = self.intercept + sum(X[i][j] * self.weights[j] for j in range(p))
                z_clip = min(12.0, max(-12.0, z))
                prob = 1.0 / (1.0 + math.exp(-z_clip))
                err = y_binary[i] - prob
                g_b += err
                for j in range(p):
                    g_w[j] += err * X[i][j]

            self.intercept += (self.lr / n) * g_b
            for j in range(p):
                self.weights[j] += (self.lr / n) * g_w[j] - self.lr * self.l2 * self.weights[j]
        return self

    def predict_proba(self, X: Sequence[Sequence[float]]) -> list[float]:
        p = len(self.weights)
        probs = []
        for row in X:
            z = self.intercept + sum(row[j] * self.weights[j] for j in range(p))
            z_clip = min(12.0, max(-12.0, z))
            probs.append(1.0 / (1.0 + math.exp(-z_clip)))
        return probs

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        # Return expected count approximated by probability
        return self.predict_proba(X)


# --- Model 5: Poisson Gradient Boosted Decision Tree (LightGBM/HistGB Pure Engine) ---
class DecisionStump:
    def __init__(self, feature_idx: int, threshold: float, left_val: float, right_val: float):
        self.feature_idx = feature_idx
        self.threshold = threshold
        self.left_val = left_val
        self.right_val = right_val

    def predict_val(self, x: Sequence[float]) -> float:
        return self.left_val if x[self.feature_idx] <= self.threshold else self.right_val


class PoissonGradientBoostedModel:
    """Poisson Gradient Boosted Trees: fits an additive ensemble under Poisson deviance with exposure offsets."""

    def __init__(self, n_estimators: int = 40, learning_rate: float = 0.08):
        self.n_estimators = n_estimators
        self.lr = learning_rate
        self.base_offset: float = 0.0
        self.trees: list[DecisionStump] = []

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        log_exposure: Sequence[float],
    ) -> PoissonGradientBoostedModel:
        n = len(X)
        if n == 0:
            return self
        p = len(X[0])
        tot_y = sum(y)
        tot_exp = sum(math.exp(le) for le in log_exposure)
        self.base_offset = math.log(max(1e-5, tot_y / max(1.0, tot_exp)))

        current_preds = [self.base_offset + le for le in log_exposure]

        for _ in range(self.n_estimators):
            # Compute negative gradients: -dL/dF = y - mu
            mus = [math.exp(min(12.0, max(-12.0, f))) for f in current_preds]
            residuals = [yi - mui for yi, mui in zip(y, mus)]

            # Greedy best stump search across features
            best_feat = 0
            best_thresh = 0.0
            best_gain = -1.0
            best_left_val = 0.0
            best_right_val = 0.0

            for j in range(p):
                vals = sorted(set(X[i][j] for i in range(n)))
                if len(vals) <= 1:
                    continue
                # Test candidate cut points
                for k in range(min(5, len(vals) - 1)):
                    idx = (k + 1) * len(vals) // (min(5, len(vals) - 1) + 1)
                    thresh = vals[idx]
                    left_mask = [X[i][j] <= thresh for i in range(n)]
                    left_g = sum(residuals[i] for i in range(n) if left_mask[i])
                    left_h = sum(mus[i] for i in range(n) if left_mask[i]) + 1e-4
                    right_g = sum(residuals[i] for i in range(n) if not left_mask[i])
                    right_h = sum(mus[i] for i in range(n) if not left_mask[i]) + 1e-4

                    gain = (left_g ** 2 / left_h) + (right_g ** 2 / right_h)
                    if gain > best_gain:
                        best_gain = gain
                        best_feat = j
                        best_thresh = thresh
                        best_left_val = left_g / left_h
                        best_right_val = right_g / right_h

            stump = DecisionStump(best_feat, best_thresh, best_left_val, best_right_val)
            self.trees.append(stump)

            # Update current predictions
            for i in range(n):
                update = stump.predict_val(X[i])
                current_preds[i] += self.lr * update

        return self

    def predict(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        preds = []
        for i, row in enumerate(X):
            f = self.base_offset + log_exposure[i]
            for tree in self.trees:
                f += self.lr * tree.predict_val(row)
            preds.append(math.exp(min(12.0, max(-12.0, f))))
        return preds

    def predict_proba(self, X: Sequence[Sequence[float]], log_exposure: Sequence[float]) -> list[float]:
        preds = self.predict(X, log_exposure)
        return [min(1.0, 1.0 - math.exp(-mu)) for mu in preds]


def evaluate_model_suite(
    X_train: Sequence[Sequence[float]],
    y_train: Sequence[float],
    exp_train: Sequence[float],
    X_test: Sequence[Sequence[float]],
    y_test: Sequence[float],
    exp_test: Sequence[float],
    feature_names: Sequence[str],
    network_label: str = "benchmark_network",
) -> PanelModelingExperimentReport:
    """Fit all 5 baselines & boosted trees, computing comparative deviance, NLL, and Top-k capture."""
    start_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_exp_train = [math.log(max(1.0, e)) for e in exp_train]
    log_exp_test = [math.log(max(1.0, e)) for e in exp_test]
    y_bin_train = [1 if y >= 1 else 0 for y in y_train]
    y_bin_test = [1 if y >= 1 else 0 for y in y_test]

    benchmarks: list[ModelBenchmarkMetrics] = []

    # 1. Historical Exposure Rate
    t0 = datetime.now(UTC)
    m_hist = HistoricalExposureRateModel().fit(y_train, exp_train)
    p_hist = m_hist.predict(exp_test)
    pb_hist = m_hist.predict_proba(exp_test)
    roc_hist, pr_hist = _roc_and_pr_auc(y_bin_test, pb_hist)
    cap_hist = _top_k_capture_curve(y_test, p_hist)
    t_hist = (datetime.now(UTC) - t0).total_seconds()
    benchmarks.append(
        ModelBenchmarkMetrics(
            model_name="Historical Exposure Rate",
            model_family="empirical_baseline",
            poisson_deviance=_poisson_deviance(y_test, p_hist),
            poisson_nll=_poisson_nll(y_test, p_hist),
            mae=_mae(y_test, p_hist),
            brier_score=_brier_score(y_bin_test, pb_hist),
            roc_auc=roc_hist,
            pr_auc=pr_hist,
            top_5pct_capture=cap_hist.get("top_5pct_capture", 0.0),
            top_10pct_capture=cap_hist.get("top_10pct_capture", 0.0),
            top_20pct_capture=cap_hist.get("top_20pct_capture", 0.0),
            fit_time_seconds=t_hist,
        )
    )

    # 2. Poisson GLM (with log(exposure) offset)
    t0 = datetime.now(UTC)
    m_glm = PoissonGlmExposureModel(epochs=120).fit(X_train, y_train, log_exp_train)
    p_glm = m_glm.predict(X_test, log_exp_test)
    pb_glm = m_glm.predict_proba(X_test, log_exp_test)
    roc_glm, pr_glm = _roc_and_pr_auc(y_bin_test, pb_glm)
    cap_glm = _top_k_capture_curve(y_test, p_glm)
    t_glm = (datetime.now(UTC) - t0).total_seconds()
    benchmarks.append(
        ModelBenchmarkMetrics(
            model_name="Poisson GLM (Exposure Offset)",
            model_family="generalized_linear_model",
            poisson_deviance=_poisson_deviance(y_test, p_glm),
            poisson_nll=_poisson_nll(y_test, p_glm),
            mae=_mae(y_test, p_glm),
            brier_score=_brier_score(y_bin_test, pb_glm),
            roc_auc=roc_glm,
            pr_auc=pr_glm,
            top_5pct_capture=cap_glm.get("top_5pct_capture", 0.0),
            top_10pct_capture=cap_glm.get("top_10pct_capture", 0.0),
            top_20pct_capture=cap_glm.get("top_20pct_capture", 0.0),
            fit_time_seconds=t_glm,
        )
    )

    # 3. Negative-Binomial GLM
    t0 = datetime.now(UTC)
    m_nb = NegativeBinomialExposureModel(epochs=120).fit(X_train, y_train, log_exp_train)
    p_nb = m_nb.predict(X_test, log_exp_test)
    pb_nb = m_nb.predict_proba(X_test, log_exp_test)
    roc_nb, pr_nb = _roc_and_pr_auc(y_bin_test, pb_nb)
    cap_nb = _top_k_capture_curve(y_test, p_nb)
    t_nb = (datetime.now(UTC) - t0).total_seconds()
    benchmarks.append(
        ModelBenchmarkMetrics(
            model_name="Negative-Binomial GLM (Exposure Offset)",
            model_family="generalized_linear_model",
            poisson_deviance=_poisson_deviance(y_test, p_nb),
            poisson_nll=_poisson_nll(y_test, p_nb),
            mae=_mae(y_test, p_nb),
            brier_score=_brier_score(y_bin_test, pb_nb),
            roc_auc=roc_nb,
            pr_auc=pr_nb,
            top_5pct_capture=cap_nb.get("top_5pct_capture", 0.0),
            top_10pct_capture=cap_nb.get("top_10pct_capture", 0.0),
            top_20pct_capture=cap_nb.get("top_20pct_capture", 0.0),
            fit_time_seconds=t_nb,
        )
    )

    # 4. Regularized Logistic Regression (Binary Occurrence)
    t0 = datetime.now(UTC)
    m_log = RegularizedLogisticModel(epochs=120).fit(X_train, y_bin_train)
    pb_log = m_log.predict_proba(X_test)
    p_log = m_log.predict(X_test)
    roc_log, pr_log = _roc_and_pr_auc(y_bin_test, pb_log)
    cap_log = _top_k_capture_curve(y_test, pb_log)
    t_log = (datetime.now(UTC) - t0).total_seconds()
    benchmarks.append(
        ModelBenchmarkMetrics(
            model_name="Regularized Logistic (Binary Occurrence)",
            model_family="logistic_regression",
            poisson_deviance=_poisson_deviance(y_test, p_log),
            poisson_nll=_poisson_nll(y_test, p_log),
            mae=_mae(y_test, p_log),
            brier_score=_brier_score(y_bin_test, pb_log),
            roc_auc=roc_log,
            pr_auc=pr_log,
            top_5pct_capture=cap_log.get("top_5pct_capture", 0.0),
            top_10pct_capture=cap_log.get("top_10pct_capture", 0.0),
            top_20pct_capture=cap_log.get("top_20pct_capture", 0.0),
            fit_time_seconds=t_log,
        )
    )

    # 5. Poisson Gradient Boosted Trees
    t0 = datetime.now(UTC)
    m_gbdt = PoissonGradientBoostedModel(n_estimators=35, learning_rate=0.08).fit(X_train, y_train, log_exp_train)
    p_gbdt = m_gbdt.predict(X_test, log_exp_test)
    pb_gbdt = m_gbdt.predict_proba(X_test, log_exp_test)
    roc_gbdt, pr_gbdt = _roc_and_pr_auc(y_bin_test, pb_gbdt)
    cap_gbdt = _top_k_capture_curve(y_test, p_gbdt)
    t_gbdt = (datetime.now(UTC) - t0).total_seconds()
    benchmarks.append(
        ModelBenchmarkMetrics(
            model_name="Poisson Gradient Boosted Trees (LightGBM/HistGB)",
            model_family="gradient_boosted_trees",
            poisson_deviance=_poisson_deviance(y_test, p_gbdt),
            poisson_nll=_poisson_nll(y_test, p_gbdt),
            mae=_mae(y_test, p_gbdt),
            brier_score=_brier_score(y_bin_test, pb_gbdt),
            roc_auc=roc_gbdt,
            pr_auc=pr_gbdt,
            top_5pct_capture=cap_gbdt.get("top_5pct_capture", 0.0),
            top_10pct_capture=cap_gbdt.get("top_10pct_capture", 0.0),
            top_20pct_capture=cap_gbdt.get("top_20pct_capture", 0.0),
            fit_time_seconds=t_gbdt,
        )
    )

    # Determine best model by lowest Poisson deviance
    best_m = min(benchmarks, key=lambda m: m.poisson_deviance).model_name

    return PanelModelingExperimentReport(
        network_label=network_label,
        train_size=len(X_train),
        test_size=len(X_test),
        features_evaluated=list(feature_names),
        model_benchmarks=benchmarks,
        best_model_name=best_m,
        evaluation_timestamp_utc=start_ts,
    )
