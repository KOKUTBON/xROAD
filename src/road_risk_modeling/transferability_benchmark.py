"""Build reusable summaries across transferability benchmark runs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


TRANSFERABILITY_BENCHMARK_VERSION = "transferability_benchmark_v1"
TRANSFERABILITY_BENCHMARK_CONTRACT_VERSION = "transferability_benchmark_public_v1"

ALL_MODES = (
    "within_jurisdiction_temporal",
    "cross_jurisdiction_temporal",
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
)
STRICT_TRANSFER_MODES = (
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
)
CROSS_CITY_MODES = (
    "cross_jurisdiction_temporal",
    *STRICT_TRANSFER_MODES,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present) / float(len(present))


def _humanize_label(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value).replace("_", " ").split())


def _format_metric(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _format_share(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100.0:.2f}%"


def _format_runtime(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}s"


def _stack_key(dataset_labels: list[str]) -> str:
    return "__".join(dataset_labels)


def _stack_display_name(dataset_labels: list[str]) -> str:
    return " + ".join(_humanize_label(label) for label in dataset_labels)


def _mode_jurisdictions(payload: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    mode_payload = payload.get(mode, {})
    jurisdictions: list[dict[str, Any]] = []
    if not isinstance(mode_payload, dict):
        return jurisdictions
    for label, metrics in sorted(mode_payload.items()):
        rf_metrics = metrics.get("random_forest_poisson_metrics", {})
        jurisdictions.append(
            {
                "label": label,
                "display_name": _humanize_label(label),
                "mean_poisson_deviance": _safe_float(rf_metrics.get("mean_poisson_deviance")),
                "top_5pct_crash_share": _safe_float(rf_metrics.get("top_5pct_crash_share")),
                "test_rows": metrics.get("test_rows"),
                "test_crash_total": metrics.get("test_crash_total"),
                "train_jurisdictions": list(metrics.get("train_jurisdictions") or []),
            }
        )
    return jurisdictions


def _mode_summary(payload: dict[str, Any], mode: str) -> dict[str, Any]:
    jurisdictions = _mode_jurisdictions(payload, mode)
    return {
        "mode": mode,
        "mode_display_name": _humanize_label(mode),
        "target_count": len(jurisdictions),
        "average_mean_poisson_deviance": _mean(
            [entry["mean_poisson_deviance"] for entry in jurisdictions]
        ),
        "average_top_5pct_crash_share": _mean(
            [entry["top_5pct_crash_share"] for entry in jurisdictions]
        ),
        "jurisdictions": jurisdictions,
    }


def _compose_run_summary(
    *,
    metrics_paths: list[str],
    dataset_labels: list[str],
    holdout_year: int | None,
    random_forest_n_estimators: int | None,
    requested_modes: list[str],
    runtime_seconds: float | None,
    mode_summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    requested_mode_order = [mode for mode in ALL_MODES if mode in requested_modes]
    return {
        "metrics_paths": metrics_paths,
        "metrics_path": metrics_paths[0],
        "stack_key": _stack_key(dataset_labels),
        "stack_display_name": _stack_display_name(dataset_labels),
        "dataset_labels": dataset_labels,
        "dataset_count": len(dataset_labels),
        "holdout_year": holdout_year,
        "random_forest_n_estimators": random_forest_n_estimators,
        "requested_modes": requested_mode_order,
        "runtime_seconds": runtime_seconds,
        "mode_summaries": mode_summaries,
        "within_city_average_mean_poisson_deviance": mode_summaries["within_jurisdiction_temporal"][
            "average_mean_poisson_deviance"
        ],
        "within_city_average_top_5pct_crash_share": mode_summaries["within_jurisdiction_temporal"][
            "average_top_5pct_crash_share"
        ],
        "cross_city_average_mean_poisson_deviance": _mean(
            [
                mode_summaries[mode]["average_mean_poisson_deviance"]
                for mode in CROSS_CITY_MODES
            ]
        ),
        "cross_city_average_top_5pct_crash_share": _mean(
            [
                mode_summaries[mode]["average_top_5pct_crash_share"]
                for mode in CROSS_CITY_MODES
            ]
        ),
        "strict_transfer_average_mean_poisson_deviance": _mean(
            [
                mode_summaries[mode]["average_mean_poisson_deviance"]
                for mode in STRICT_TRANSFER_MODES
            ]
        ),
        "strict_transfer_average_top_5pct_crash_share": _mean(
            [
                mode_summaries[mode]["average_top_5pct_crash_share"]
                for mode in STRICT_TRANSFER_MODES
            ]
        ),
    }


def _summarize_run_file(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    dataset_labels = [
        str(item.get("label"))
        for item in payload.get("dataset_inputs", [])
        if item.get("label")
    ]
    mode_summaries = {mode: _mode_summary(payload, mode) for mode in ALL_MODES}
    runtime_seconds = _safe_float(payload.get("profiling", {}).get("runtime_seconds"))
    return _compose_run_summary(
        metrics_paths=[str(path)],
        dataset_labels=dataset_labels,
        holdout_year=payload.get("holdout_year"),
        random_forest_n_estimators=payload.get("random_forest_n_estimators"),
        requested_modes=list(payload.get("requested_modes") or []),
        runtime_seconds=runtime_seconds,
        mode_summaries=mode_summaries,
    )


def _merge_mode_summaries(parts: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    jurisdictions_by_label: dict[str, dict[str, Any]] = {}
    for part in parts:
        for jurisdiction in part["mode_summaries"][mode]["jurisdictions"]:
            jurisdictions_by_label[jurisdiction["label"]] = jurisdiction
    jurisdictions = [jurisdictions_by_label[label] for label in sorted(jurisdictions_by_label)]
    return {
        "mode": mode,
        "mode_display_name": _humanize_label(mode),
        "target_count": len(jurisdictions),
        "average_mean_poisson_deviance": _mean(
            [entry["mean_poisson_deviance"] for entry in jurisdictions]
        ),
        "average_top_5pct_crash_share": _mean(
            [entry["top_5pct_crash_share"] for entry in jurisdictions]
        ),
        "jurisdictions": jurisdictions,
    }


def _mode_count(run: dict[str, Any]) -> int:
    return len([mode for mode in run["requested_modes"] if mode in ALL_MODES])


def _select_mode_covering_runs(group: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    ordered_group = sorted(
        group,
        key=lambda item: (-_mode_count(item), item["metrics_path"]),
    )
    selected_runs: list[dict[str, Any]] = []
    mode_owners: dict[str, dict[str, Any]] = {}
    for run in ordered_group:
        contributed = False
        for mode in run["requested_modes"]:
            if mode not in ALL_MODES or mode in mode_owners:
                continue
            mode_owners[mode] = run
            contributed = True
        if contributed:
            selected_runs.append(run)
    return selected_runs, mode_owners


def _merge_runs(raw_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int | None, int | None], list[dict[str, Any]]] = {}
    for run in raw_runs:
        key = (
            run["stack_key"],
            run["random_forest_n_estimators"],
            run["holdout_year"],
        )
        grouped.setdefault(key, []).append(run)

    merged: list[dict[str, Any]] = []
    for group in grouped.values():
        selected_runs, mode_owners = _select_mode_covering_runs(group)
        first = min(selected_runs, key=lambda item: item["metrics_path"])
        requested_modes = [
            mode
            for mode in ALL_MODES
            if mode in mode_owners
        ]
        runtime_values = [
            item["runtime_seconds"]
            for item in selected_runs
            if item["runtime_seconds"] is not None
        ]
        mode_summaries = {
            mode: _merge_mode_summaries([mode_owners[mode]], mode) if mode in mode_owners else _merge_mode_summaries([], mode)
            for mode in ALL_MODES
        }
        merged.append(
            _compose_run_summary(
                metrics_paths=[path for item in selected_runs for path in item["metrics_paths"]],
                dataset_labels=first["dataset_labels"],
                holdout_year=first["holdout_year"],
                random_forest_n_estimators=first["random_forest_n_estimators"],
                requested_modes=requested_modes,
                runtime_seconds=sum(runtime_values) if runtime_values else None,
                mode_summaries=mode_summaries,
            )
        )
    return merged


def _flatten_target_rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        for mode in ALL_MODES:
            for jurisdiction in run["mode_summaries"][mode]["jurisdictions"]:
                rows.append(
                    {
                        "stack_key": run["stack_key"],
                        "stack_display_name": run["stack_display_name"],
                        "dataset_count": run["dataset_count"],
                        "holdout_year": run["holdout_year"],
                        "random_forest_n_estimators": run["random_forest_n_estimators"],
                        "runtime_seconds": run["runtime_seconds"],
                        "mode": mode,
                        "mode_display_name": _humanize_label(mode),
                        "target_jurisdiction": jurisdiction["label"],
                        "target_display_name": jurisdiction["display_name"],
                        "mean_poisson_deviance": jurisdiction["mean_poisson_deviance"],
                        "top_5pct_crash_share": jurisdiction["top_5pct_crash_share"],
                        "test_rows": jurisdiction["test_rows"],
                        "test_crash_total": jurisdiction["test_crash_total"],
                        "train_jurisdictions": " | ".join(jurisdiction["train_jurisdictions"]),
                    }
                )
    return rows


def _run_metric_lookup(run: dict[str, Any], mode: str) -> dict[str, dict[str, Any]]:
    return {
        entry["label"]: entry
        for entry in run["mode_summaries"][mode]["jurisdictions"]
    }


def _compare_mode_between_runs(
    left: dict[str, Any],
    right: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    left_lookup = _run_metric_lookup(left, mode)
    right_lookup = _run_metric_lookup(right, mode)
    common_targets = sorted(set(left_lookup) & set(right_lookup))
    if not common_targets:
        return {
            "mode": mode,
            "common_target_count": 0,
            "common_targets": [],
            "left_average_mean_poisson_deviance": None,
            "right_average_mean_poisson_deviance": None,
            "mean_poisson_deviance_delta": None,
            "left_average_top_5pct_crash_share": None,
            "right_average_top_5pct_crash_share": None,
            "top_5pct_crash_share_delta": None,
        }
    left_deviances = [left_lookup[target]["mean_poisson_deviance"] for target in common_targets]
    right_deviances = [right_lookup[target]["mean_poisson_deviance"] for target in common_targets]
    left_shares = [left_lookup[target]["top_5pct_crash_share"] for target in common_targets]
    right_shares = [right_lookup[target]["top_5pct_crash_share"] for target in common_targets]
    left_average_deviance = _mean(left_deviances)
    right_average_deviance = _mean(right_deviances)
    left_average_share = _mean(left_shares)
    right_average_share = _mean(right_shares)
    return {
        "mode": mode,
        "common_target_count": len(common_targets),
        "common_targets": common_targets,
        "left_average_mean_poisson_deviance": left_average_deviance,
        "right_average_mean_poisson_deviance": right_average_deviance,
        "mean_poisson_deviance_delta": (
            right_average_deviance - left_average_deviance
            if left_average_deviance is not None and right_average_deviance is not None
            else None
        ),
        "left_average_top_5pct_crash_share": left_average_share,
        "right_average_top_5pct_crash_share": right_average_share,
        "top_5pct_crash_share_delta": (
            right_average_share - left_average_share
            if left_average_share is not None and right_average_share is not None
            else None
        ),
    }


def _build_stack_comparisons(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_budget: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        budget = int(run["random_forest_n_estimators"])
        by_budget.setdefault(budget, []).append(run)

    comparisons: list[dict[str, Any]] = []
    for budget, budget_runs in sorted(by_budget.items()):
        ordered_runs = sorted(
            budget_runs,
            key=lambda record: (record["dataset_count"], record["stack_display_name"]),
        )
        for left, right in zip(ordered_runs, ordered_runs[1:]):
            comparisons.append(
                {
                    "random_forest_n_estimators": budget,
                    "from_stack_key": left["stack_key"],
                    "from_stack_display_name": left["stack_display_name"],
                    "to_stack_key": right["stack_key"],
                    "to_stack_display_name": right["stack_display_name"],
                    "from_dataset_count": left["dataset_count"],
                    "to_dataset_count": right["dataset_count"],
                    "added_targets": [
                        label for label in right["dataset_labels"] if label not in left["dataset_labels"]
                    ],
                    "mode_comparisons": {
                        mode: _compare_mode_between_runs(left, right, mode)
                        for mode in ALL_MODES
                    },
                }
            )
    return comparisons


def _common_modes(left: dict[str, Any], right: dict[str, Any], modes: tuple[str, ...]) -> list[str]:
    return [
        mode
        for mode in modes
        if left["mode_summaries"][mode]["target_count"] > 0 and right["mode_summaries"][mode]["target_count"] > 0
    ]


def _average_mode_metric(run: dict[str, Any], modes: list[str], field: str) -> float | None:
    return _mean([run["mode_summaries"][mode][field] for mode in modes])


def _candidate_budget_score(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, float]:
    common_cross_city_modes = _common_modes(baseline, candidate, CROSS_CITY_MODES)
    common_strict_modes = _common_modes(baseline, candidate, STRICT_TRANSFER_MODES)
    baseline_cross_city = _average_mode_metric(
        baseline,
        common_cross_city_modes,
        "average_mean_poisson_deviance",
    )
    candidate_cross_city = _average_mode_metric(
        candidate,
        common_cross_city_modes,
        "average_mean_poisson_deviance",
    )
    baseline_strict = _average_mode_metric(
        baseline,
        common_strict_modes,
        "average_mean_poisson_deviance",
    )
    candidate_strict = _average_mode_metric(
        candidate,
        common_strict_modes,
        "average_mean_poisson_deviance",
    )
    baseline_top_share = _average_mode_metric(
        baseline,
        common_cross_city_modes,
        "average_top_5pct_crash_share",
    )
    candidate_top_share = _average_mode_metric(
        candidate,
        common_cross_city_modes,
        "average_top_5pct_crash_share",
    )
    runtime_multiplier = None
    if baseline["runtime_seconds"] and candidate["runtime_seconds"]:
        runtime_multiplier = candidate["runtime_seconds"] / baseline["runtime_seconds"]
    cross_city_gain = None
    if baseline_cross_city is not None and candidate_cross_city is not None:
        cross_city_gain = (
            baseline_cross_city
            - candidate_cross_city
        )
    strict_gain = None
    if baseline_strict is not None and candidate_strict is not None:
        strict_gain = (
            baseline_strict
            - candidate_strict
        )
    top_share_gain = None
    if baseline_top_share is not None and candidate_top_share is not None:
        top_share_gain = (
            candidate_top_share
            - baseline_top_share
        )
    quality_gain = max(
        [
            value
            for value in (cross_city_gain, strict_gain, top_share_gain)
            if value is not None
        ]
        or [0.0]
    )
    acceptable = runtime_multiplier is None or runtime_multiplier <= 3.0
    material = quality_gain >= 0.01
    return acceptable and material, quality_gain


def _build_budget_profiles(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_stack: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_stack.setdefault(run["stack_key"], []).append(run)

    profiles: list[dict[str, Any]] = []
    for stack_key, stack_runs in sorted(by_stack.items()):
        ordered_runs = sorted(
            stack_runs,
            key=lambda record: int(record["random_forest_n_estimators"]),
        )
        baseline = ordered_runs[0]
        recommended = baseline
        best_gain = 0.0
        comparisons: list[dict[str, Any]] = []
        for run in ordered_runs[1:]:
            common_cross_city_modes = _common_modes(baseline, run, CROSS_CITY_MODES)
            common_strict_modes = _common_modes(baseline, run, STRICT_TRANSFER_MODES)
            baseline_cross_city = _average_mode_metric(
                baseline,
                common_cross_city_modes,
                "average_mean_poisson_deviance",
            )
            run_cross_city = _average_mode_metric(
                run,
                common_cross_city_modes,
                "average_mean_poisson_deviance",
            )
            baseline_strict = _average_mode_metric(
                baseline,
                common_strict_modes,
                "average_mean_poisson_deviance",
            )
            run_strict = _average_mode_metric(
                run,
                common_strict_modes,
                "average_mean_poisson_deviance",
            )
            baseline_top_share = _average_mode_metric(
                baseline,
                common_cross_city_modes,
                "average_top_5pct_crash_share",
            )
            run_top_share = _average_mode_metric(
                run,
                common_cross_city_modes,
                "average_top_5pct_crash_share",
            )
            runtime_multiplier = None
            if baseline["runtime_seconds"] and run["runtime_seconds"]:
                runtime_multiplier = run["runtime_seconds"] / baseline["runtime_seconds"]
            cross_city_deviance_delta = None
            if baseline_cross_city is not None and run_cross_city is not None:
                cross_city_deviance_delta = (
                    run_cross_city
                    - baseline_cross_city
                )
            strict_deviance_delta = None
            if baseline_strict is not None and run_strict is not None:
                strict_deviance_delta = (
                    run_strict
                    - baseline_strict
                )
            top_share_delta = None
            if baseline_top_share is not None and run_top_share is not None:
                top_share_delta = (
                    run_top_share
                    - baseline_top_share
                )
            acceptable, quality_gain = _candidate_budget_score(baseline, run)
            status = "not_worth_cost"
            if acceptable and quality_gain > best_gain:
                recommended = run
                best_gain = quality_gain
                status = "recommended_candidate"
            comparisons.append(
                {
                    "candidate_budget": run["random_forest_n_estimators"],
                    "common_cross_city_modes": common_cross_city_modes,
                    "candidate_runtime_seconds": run["runtime_seconds"],
                    "runtime_multiplier_vs_baseline": runtime_multiplier,
                    "cross_city_mean_poisson_deviance_delta": cross_city_deviance_delta,
                    "strict_transfer_mean_poisson_deviance_delta": strict_deviance_delta,
                    "cross_city_top_5pct_crash_share_delta": top_share_delta,
                    "status": status,
                }
            )

        if recommended is baseline:
            rationale = (
                f"Kept rf{baseline['random_forest_n_estimators']} because heavier budgets did not deliver "
                "enough cross-city quality improvement relative to runtime."
                if comparisons
                else f"Kept rf{baseline['random_forest_n_estimators']} because it is the only profiled budget."
            )
        else:
            rationale = (
                f"Promoted rf{recommended['random_forest_n_estimators']} because it improved cross-city quality "
                "without exceeding the runtime guardrail."
            )

        profiles.append(
            {
                "stack_key": stack_key,
                "stack_display_name": baseline["stack_display_name"],
                "dataset_labels": baseline["dataset_labels"],
                "baseline_budget": baseline["random_forest_n_estimators"],
                "recommended_budget": recommended["random_forest_n_estimators"],
                "baseline_runtime_seconds": baseline["runtime_seconds"],
                "recommended_runtime_seconds": recommended["runtime_seconds"],
                "baseline_cross_city_average_mean_poisson_deviance": baseline[
                    "cross_city_average_mean_poisson_deviance"
                ],
                "recommended_cross_city_average_mean_poisson_deviance": recommended[
                    "cross_city_average_mean_poisson_deviance"
                ],
                "rationale": rationale,
                "comparisons": comparisons,
            }
        )
    return profiles


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_run_rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        rows.append(
            {
                "stack_key": run["stack_key"],
                "stack_display_name": run["stack_display_name"],
                "dataset_labels": " | ".join(run["dataset_labels"]),
                "dataset_count": run["dataset_count"],
                "holdout_year": run["holdout_year"],
                "random_forest_n_estimators": run["random_forest_n_estimators"],
                "runtime_seconds": run["runtime_seconds"],
                "within_city_average_mean_poisson_deviance": run["within_city_average_mean_poisson_deviance"],
                "within_city_average_top_5pct_crash_share": run["within_city_average_top_5pct_crash_share"],
                "cross_city_average_mean_poisson_deviance": run["cross_city_average_mean_poisson_deviance"],
                "cross_city_average_top_5pct_crash_share": run["cross_city_average_top_5pct_crash_share"],
                "strict_transfer_average_mean_poisson_deviance": run[
                    "strict_transfer_average_mean_poisson_deviance"
                ],
                "strict_transfer_average_top_5pct_crash_share": run[
                    "strict_transfer_average_top_5pct_crash_share"
                ],
                "metrics_paths": " | ".join(run["metrics_paths"]),
            }
        )
    return rows


def _build_markdown_report(
    *,
    benchmark_label: str,
    runs: list[dict[str, Any]],
    stack_comparisons: list[dict[str, Any]],
    budget_profiles: list[dict[str, Any]],
) -> str:
    lines = [f"# {benchmark_label}", ""]
    if runs:
        featured_run = max(
            runs,
            key=lambda record: (
                record["dataset_count"],
                len(record["requested_modes"]),
            ),
        )
        largest_stack_profile = next(
            (
                profile
                for profile in budget_profiles
                if profile["stack_key"] == featured_run["stack_key"]
            ),
            None,
        )
        if largest_stack_profile is not None:
            featured_run = next(
                (
                    run
                    for run in runs
                    if run["stack_key"] == featured_run["stack_key"]
                    and run["random_forest_n_estimators"]
                    == largest_stack_profile["recommended_budget"]
                ),
                featured_run,
            )
        lines.extend(
            [
                "## Coverage",
                "",
                f"- profiled runs: `{len(runs)}`",
                f"- largest stack: `{featured_run['stack_display_name']}` (`{featured_run['dataset_count']}` municipalities)",
                f"- largest-stack budget: `rf{featured_run['random_forest_n_estimators']}`",
                f"- largest-stack runtime: `{_format_runtime(featured_run['runtime_seconds'])}`",
                "",
                "## Within-City and Cross-Year",
                "",
                f"- largest-stack within-city temporal mean deviance: `{_format_metric(featured_run['within_city_average_mean_poisson_deviance'])}`",
                f"- largest-stack within-city top-5% crash capture: `{_format_share(featured_run['within_city_average_top_5pct_crash_share'])}`",
                "",
                "## Cross-City",
                "",
                f"- largest-stack average cross-city deviance across temporal, cold-start, and history-free modes: `{_format_metric(featured_run['cross_city_average_mean_poisson_deviance'])}`",
                f"- largest-stack average cross-city top-5% crash capture: `{_format_share(featured_run['cross_city_average_top_5pct_crash_share'])}`",
                f"- largest-stack strict-transfer deviance average: `{_format_metric(featured_run['strict_transfer_average_mean_poisson_deviance'])}`",
                "",
            ]
        )

    if stack_comparisons:
        first_comparison = stack_comparisons[0]
        temporal = first_comparison["mode_comparisons"]["cross_jurisdiction_temporal"]
        lines.extend(
            [
                "## Stack Expansion",
                "",
                f"- compared `rf{first_comparison['random_forest_n_estimators']}` stacks from `{first_comparison['from_dataset_count']}` to `{first_comparison['to_dataset_count']}` municipalities",
                f"- added targets: `{', '.join(_humanize_label(label) for label in first_comparison['added_targets']) or 'none'}`",
                f"- common-target temporal deviance delta: `{_format_metric(temporal['mean_poisson_deviance_delta'])}`",
                f"- common-target temporal top-5% delta: `{_format_share(temporal['top_5pct_crash_share_delta'])}`",
                "",
            ]
        )

    if budget_profiles:
        lines.append("## Budget Decision")
        lines.append("")
        for profile in budget_profiles:
            lines.append(
                f"- `{profile['stack_display_name']}`: recommended `rf{profile['recommended_budget']}`. {profile['rationale']}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_transferability_benchmark_bundle(
    *,
    transferability_metrics_paths: list[str | Path],
    output_dir: str | Path = "data/reporting/transferability_benchmark",
    benchmark_label: str | None = None,
) -> dict[str, Any]:
    metric_inputs = [Path(path) for path in transferability_metrics_paths]
    if not metric_inputs:
        raise RuntimeError("At least one transferability metrics JSON path is required.")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    report_json_path = output_root / "transferability_benchmark.json"
    report_md_path = output_root / "transferability_benchmark.md"
    runs_csv_path = output_root / "transferability_benchmark_runs.csv"
    targets_csv_path = output_root / "transferability_benchmark_targets.csv"
    manifest_path = output_root / "transferability_benchmark.manifest.json"

    runs = sorted(
        _merge_runs([_summarize_run_file(path) for path in metric_inputs]),
        key=lambda record: (
            record["dataset_count"],
            int(record["random_forest_n_estimators"]),
            record["stack_display_name"],
        ),
    )
    run_rows = _build_run_rows(runs)
    target_rows = _flatten_target_rows(runs)
    stack_comparisons = _build_stack_comparisons(runs)
    budget_profiles = _build_budget_profiles(runs)

    benchmark_label = benchmark_label or "Transferability Benchmark Bundle"

    payload = {
        "transferability_benchmark_version": TRANSFERABILITY_BENCHMARK_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "benchmark_label": benchmark_label,
        "runs": runs,
        "within_city_reporting": [
            {
                "stack_key": run["stack_key"],
                "stack_display_name": run["stack_display_name"],
                "random_forest_n_estimators": run["random_forest_n_estimators"],
                "holdout_year": run["holdout_year"],
                "average_mean_poisson_deviance": run["within_city_average_mean_poisson_deviance"],
                "average_top_5pct_crash_share": run["within_city_average_top_5pct_crash_share"],
                "jurisdictions": run["mode_summaries"]["within_jurisdiction_temporal"]["jurisdictions"],
            }
            for run in runs
        ],
        "cross_year_reporting": [
            {
                "stack_key": run["stack_key"],
                "stack_display_name": run["stack_display_name"],
                "random_forest_n_estimators": run["random_forest_n_estimators"],
                "holdout_year": run["holdout_year"],
                "temporal_holdout_average_mean_poisson_deviance": run[
                    "within_city_average_mean_poisson_deviance"
                ],
                "temporal_holdout_average_top_5pct_crash_share": run[
                    "within_city_average_top_5pct_crash_share"
                ],
            }
            for run in runs
        ],
        "cross_city_reporting": [
            {
                "stack_key": run["stack_key"],
                "stack_display_name": run["stack_display_name"],
                "random_forest_n_estimators": run["random_forest_n_estimators"],
                "holdout_year": run["holdout_year"],
                "mode": mode,
                "average_mean_poisson_deviance": run["mode_summaries"][mode][
                    "average_mean_poisson_deviance"
                ],
                "average_top_5pct_crash_share": run["mode_summaries"][mode][
                    "average_top_5pct_crash_share"
                ],
                "jurisdictions": run["mode_summaries"][mode]["jurisdictions"],
            }
            for run in runs
            for mode in CROSS_CITY_MODES
        ],
        "stack_comparisons": stack_comparisons,
        "budget_profiles": budget_profiles,
        "stats": {
            "input_run_count": len(runs),
            "stack_count": len({run["stack_key"] for run in runs}),
            "budget_count": len({run["random_forest_n_estimators"] for run in runs}),
            "largest_stack_dataset_count": max((run["dataset_count"] for run in runs), default=0),
            "target_row_count": len(target_rows),
        },
    }

    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(
        _build_markdown_report(
            benchmark_label=benchmark_label,
            runs=runs,
            stack_comparisons=stack_comparisons,
            budget_profiles=budget_profiles,
        ),
        encoding="utf-8",
    )
    _write_csv(runs_csv_path, run_rows)
    _write_csv(targets_csv_path, target_rows)

    manifest = {
        "transferability_benchmark_version": TRANSFERABILITY_BENCHMARK_VERSION,
        "contract": {
            "resource_name": "transferability_benchmark",
            "public_contract_version": TRANSFERABILITY_BENCHMARK_CONTRACT_VERSION,
        },
        "inputs": {
            "transferability_metrics_paths": [str(path) for path in metric_inputs],
        },
        "outputs": {
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "runs_csv_path": str(runs_csv_path),
            "runs_csv_sha256": _sha256(runs_csv_path),
            "targets_csv_path": str(targets_csv_path),
            "targets_csv_sha256": _sha256(targets_csv_path),
            "manifest_path": str(manifest_path),
        },
        "stats": payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "transferability_metrics",
                    path,
                    _sha256(path),
                )
                for path in metric_inputs
            ],
            publishable_outputs=[
                _artifact_reference(
                    "transferability_benchmark_json",
                    report_json_path,
                    _sha256(report_json_path),
                ),
                _artifact_reference(
                    "transferability_benchmark_markdown",
                    report_md_path,
                    _sha256(report_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "transferability_benchmark_runs_csv",
                    runs_csv_path,
                    _sha256(runs_csv_path),
                ),
                _artifact_reference(
                    "transferability_benchmark_targets_csv",
                    targets_csv_path,
                    _sha256(targets_csv_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "transferability_benchmark_version": TRANSFERABILITY_BENCHMARK_VERSION,
        "stats": payload["stats"],
    }
