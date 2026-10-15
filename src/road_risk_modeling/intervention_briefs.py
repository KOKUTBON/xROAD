"""Build exportable intervention briefs from the dashboard summary artifact."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


INTERVENTION_BRIEF_VERSION = "intervention_brief_v1"
INTERVENTION_BRIEF_CONTRACT_VERSION = "intervention_brief_public_v1"
INTERVENTION_BRIEF_BUNDLE_VERSION = "intervention_brief_bundle_v1"
DEFAULT_SCENARIO_BUNDLE_ROOT = Path("data/planning/scenario_countermeasures")


def _load_dashboard_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("published_runs"), list):
        raise RuntimeError("Dashboard summary JSON must include a top-level 'published_runs' list.")
    if not isinstance(payload.get("intervention_shortlists"), list):
        raise RuntimeError("Dashboard summary JSON must include a top-level 'intervention_shortlists' list.")
    return payload


def _find_by_key(records: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for record in records:
        if str(record.get(key)) == value:
            return record
    return None


def _load_optional_scenario_bundle(
    *,
    scenario_bundle_root: Path | None,
    prediction_run_label: str,
) -> dict[str, Any] | None:
    if scenario_bundle_root is None:
        return None
    bundle_path = scenario_bundle_root / prediction_run_label / "scenario_bundle.json"
    if not bundle_path.exists():
        return None
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["_scenario_bundle_path"] = str(bundle_path)
    return payload


def _concentration_profile(top_5_share: float | None) -> dict[str, str]:
    value = float(top_5_share or 0.0)
    if value >= 0.45:
        return {
            "code": "very_concentrated",
            "label": "Very concentrated",
            "interpretation": "A small share of segments captures a large share of observed crashes.",
        }
    if value >= 0.35:
        return {
            "code": "concentrated",
            "label": "Concentrated",
            "interpretation": "Corridor-focused interventions should be efficient before broader area screening.",
        }
    if value >= 0.25:
        return {
            "code": "moderate",
            "label": "Moderate",
            "interpretation": "Targeted corridors matter, but the risk surface is not confined to only a handful of links.",
        }
    return {
        "code": "diffuse",
        "label": "Diffuse",
        "interpretation": "The risk surface is spread more broadly and should be paired with area-wide treatment review.",
    }


def _transfer_profile(cold_start_gap: float | None) -> dict[str, str]:
    value = float(cold_start_gap or 0.0)
    if value >= 0.08:
        return {
            "code": "high_local_dependency",
            "label": "High local-history dependency",
            "interpretation": "Temporal local history materially improves fit, so peer-city transfer should be validated carefully on the ground.",
        }
    if value >= 0.03:
        return {
            "code": "moderate_local_dependency",
            "label": "Moderate local-history dependency",
            "interpretation": "Peer-city transfer is useful, but local crash history still improves prioritization materially.",
        }
    return {
        "code": "stable_transfer",
        "label": "Relatively stable transfer",
        "interpretation": "Cross-city context remains comparatively usable even when local history is removed.",
    }


def _surface_profile(tiles_very_high: int | None) -> dict[str, str]:
    value = int(tiles_very_high or 0)
    if value >= 180:
        return {
            "code": "broad_hotspot_surface",
            "label": "Broad hotspot surface",
            "interpretation": "Many very-high tiles are active, so corridor work should be paired with municipality-scale hotspot management.",
        }
    if value >= 135:
        return {
            "code": "elevated_hotspot_surface",
            "label": "Elevated hotspot surface",
            "interpretation": "The municipality has a meaningful hotspot footprint, but prioritization can still stay selective.",
        }
    return {
        "code": "contained_hotspot_surface",
        "label": "Contained hotspot surface",
        "interpretation": "Very-high hotspots are comparatively concentrated and easier to triage into a shorter list.",
    }


def _safe_percent(value: float | None) -> str:
    return f"{float(value or 0.0) * 100:.1f}%"


def _metric_or_na(value: Any, *, decimals: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{decimals}f}"


def _recommended_actions(
    *,
    display_name: str,
    top_corridor: dict[str, Any] | None,
    top_tile: dict[str, Any] | None,
    concentration: dict[str, str],
    transfer: dict[str, str],
    surface: dict[str, str],
    cold_start_gap: float | None,
    scenario_bundle: dict[str, Any] | None,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if scenario_bundle is not None:
        recommended_portfolio = (scenario_bundle.get("planning_brief_summary") or {}).get(
            "recommended_portfolio",
            {},
        )
        portfolio_title = str(recommended_portfolio.get("title") or "recommended countermeasure portfolio")
        portfolio_delta = float(recommended_portfolio.get("expected_crash_reduction") or 0.0)
        actions.append(
            {
                "priority": "1",
                "code": "recommended_countermeasure_portfolio",
                "title": portfolio_title,
                "rationale": (
                    f"Scenario engine output estimates a central reduction of {portfolio_delta:.2f} predicted crashes "
                    "for the current published shortlist."
                ),
            }
        )
    if top_corridor is not None:
        actions.append(
            {
                "priority": "2" if actions else "1",
                "code": "corridor_field_review",
                "title": f"Review the leading corridor: {top_corridor['corridor_label']}",
                "rationale": (
                    f"{top_corridor['corridor_label']} carries "
                    f"{float(top_corridor.get('predicted_crash_total') or 0.0):.2f} predicted crashes "
                    f"across {int(top_corridor.get('segment_count') or 0)} high-scored segments."
                ),
            }
        )
    if top_tile is not None:
        actions.append(
            {
                "priority": "3" if len(actions) >= 2 else str(len(actions) + 1),
                "code": "hotspot_tile_review",
                "title": f"Inspect hotspot tile {top_tile['tile_score_id']}",
                "rationale": (
                    f"The top tile contains {int(top_tile.get('tile_very_high_band_segment_count') or 0)} "
                    f"very-high segments and {int(top_tile.get('intersection_segment_count') or 0)} "
                    "intersecting scored segments."
                ),
            }
        )
    actions.append(
        {
            "priority": str(len(actions) + 1),
            "code": "transferability_posture",
            "title": transfer["label"],
            "rationale": (
                f"{transfer['interpretation']} Current cold-start gap vs temporal deviance: "
                f"{_metric_or_na(cold_start_gap, decimals=3)}."
            ),
        }
    )
    actions.append(
        {
            "priority": str(len(actions) + 1),
            "code": "portfolio_posture",
            "title": f"{concentration['label']} risk with a {surface['label'].lower()}",
            "rationale": f"{concentration['interpretation']} {surface['interpretation']}",
        }
    )
    if not actions:
        actions.append(
            {
                "priority": "1",
                "code": "no_shortlist_data",
                "title": f"Prepare first shortlist review for {display_name}",
                "rationale": "No corridor or hotspot shortlist could be derived from the current dashboard summary.",
            }
        )
    return actions


def _brief_payload(
    *,
    dashboard_summary_path: Path,
    run_record: dict[str, Any],
    priority_record: dict[str, Any] | None,
    transfer_record: dict[str, Any] | None,
    shortlist_record: dict[str, Any] | None,
    scenario_bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    segment_scores = run_record.get("segment_scores", {})
    score_tiles = run_record.get("score_tiles", {})
    metrics_by_mode = (transfer_record or {}).get("metrics_by_mode", {})
    temporal = metrics_by_mode.get("cross_jurisdiction_temporal", {})
    cold_start = metrics_by_mode.get("cross_jurisdiction_cold_start", {})
    history_free = metrics_by_mode.get("cross_jurisdiction_history_free", {})

    cold_start_gap = (priority_record or {}).get("cold_start_gap_vs_temporal")
    concentration = _concentration_profile((priority_record or {}).get("top_5pct_observed_crash_share"))
    transfer = _transfer_profile(cold_start_gap)
    surface = _surface_profile((priority_record or {}).get("tiles_very_high"))
    top_corridor = ((shortlist_record or {}).get("top_corridors") or [None])[0]
    top_tile = ((shortlist_record or {}).get("hotspot_tiles") or [None])[0]
    recommended_actions = _recommended_actions(
        display_name=run_record["display_name"],
        top_corridor=top_corridor,
        top_tile=top_tile,
        concentration=concentration,
        transfer=transfer,
        surface=surface,
        cold_start_gap=cold_start_gap,
        scenario_bundle=scenario_bundle,
    )

    payload = {
        "intervention_brief_version": INTERVENTION_BRIEF_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_dashboard_summary_path": str(dashboard_summary_path),
        "city_key": run_record["city_key"],
        "display_name": run_record["display_name"],
        "prediction_run_label": run_record["prediction_run_label"],
        "holdout_years": run_record.get("occurred_years", []),
        "overview": {
            "observed_crash_total": segment_scores.get("observed_crash_total"),
            "predicted_crash_total": segment_scores.get("predicted_crash_total"),
            "segment_score_rows": segment_scores.get("segment_score_rows"),
            "tile_rows": score_tiles.get("tile_rows"),
            "tiles_very_high": (priority_record or {}).get("tiles_very_high"),
            "tiles_high_or_very_high": (priority_record or {}).get("tiles_high_or_very_high"),
            "top_5pct_observed_crash_share": (priority_record or {}).get("top_5pct_observed_crash_share"),
        },
        "transferability": {
            "temporal_deviance": temporal.get("mean_poisson_deviance"),
            "cold_start_deviance": cold_start.get("mean_poisson_deviance"),
            "history_free_deviance": history_free.get("mean_poisson_deviance"),
            "cold_start_gap_vs_temporal": cold_start_gap,
            "history_free_gap_vs_temporal": (priority_record or {}).get("history_free_gap_vs_temporal"),
        },
        "planning_profile": {
            "concentration": concentration,
            "transferability": transfer,
            "surface_intensity": surface,
        },
        "recommended_actions": recommended_actions,
        "shortlist": {
            "top_corridors": (shortlist_record or {}).get("top_corridors", []),
            "hotspot_tiles": (shortlist_record or {}).get("hotspot_tiles", []),
        },
    }
    if scenario_bundle is not None:
        payload["scenario_countermeasures"] = {
            "source_bundle_path": scenario_bundle.get("_scenario_bundle_path"),
            "scenario_count": len(scenario_bundle.get("scenario_rankings", [])),
            "portfolio_count": len(scenario_bundle.get("portfolio_rankings", [])),
            "top_scenarios": list(scenario_bundle.get("scenario_rankings", []))[:3],
            "top_portfolios": list(scenario_bundle.get("portfolio_rankings", []))[:3],
            "recommended_summary": scenario_bundle.get("planning_brief_summary", {}),
        }
    return payload


def _brief_markdown(brief: dict[str, Any]) -> str:
    overview = brief["overview"]
    transferability = brief["transferability"]
    profile = brief["planning_profile"]
    corridors = brief["shortlist"]["top_corridors"]
    tiles = brief["shortlist"]["hotspot_tiles"]

    lines = [
        f"# {brief['display_name']} Intervention Brief",
        "",
        f"- Run label: `{brief['prediction_run_label']}`",
        f"- Holdout years: {', '.join(str(year) for year in brief.get('holdout_years', [])) or 'n/a'}",
        f"- Generated: `{brief['generated_at_utc']}`",
        "",
        "## Summary",
        "",
        f"- Observed crashes in published holdout surface: `{overview.get('observed_crash_total')}`",
        f"- Predicted crashes in published holdout surface: `{_metric_or_na(overview.get('predicted_crash_total'), decimals=3)}`",
        f"- Very-high tiles: `{overview.get('tiles_very_high')}`",
        f"- Top-5 observed crash share: `{_safe_percent(overview.get('top_5pct_observed_crash_share'))}`",
        f"- Temporal deviance: `{_metric_or_na(transferability.get('temporal_deviance'))}`",
        f"- Cold-start deviance: `{_metric_or_na(transferability.get('cold_start_deviance'))}`",
        f"- History-free deviance: `{_metric_or_na(transferability.get('history_free_deviance'))}`",
        "",
        "## Planning Profile",
        "",
        f"- Concentration: **{profile['concentration']['label']}**. {profile['concentration']['interpretation']}",
        f"- Transferability: **{profile['transferability']['label']}**. {profile['transferability']['interpretation']}",
        f"- Surface intensity: **{profile['surface_intensity']['label']}**. {profile['surface_intensity']['interpretation']}",
        "",
        "## Recommended Actions",
        "",
    ]
    for action in brief["recommended_actions"]:
        lines.append(f"1. **{action['title']}**. {action['rationale']}")

    lines.extend(["", "## Priority Corridors", ""])
    if corridors:
        for corridor in corridors[:3]:
            lines.extend(
                [
                    f"### {corridor['corridor_label']}",
                    "",
                    f"- Predicted crashes: `{_metric_or_na(corridor.get('predicted_crash_total'), decimals=2)}`",
                    f"- High or very-high segments: `{corridor.get('segment_count')}`",
                    f"- Maximum public score: `{_metric_or_na(corridor.get('max_public_score_index'), decimals=1)}`",
                    "- Supporting segments:",
                ]
            )
            top_segments = corridor.get("top_segments", [])
            for segment in top_segments[:5]:
                lines.append(
                    f"  - `{segment.get('segment_score_id')}` | {segment.get('public_score_band')} | "
                    f"score {segment.get('public_score_index')} | "
                    f"predicted {segment.get('predicted_crash_count')}"
                )
            lines.append("")
    else:
        lines.extend(["No corridor shortlist is available.", ""])

    lines.extend(["## Hotspot Tiles", ""])
    if tiles:
        for tile in tiles[:3]:
            lines.extend(
                [
                    f"### {tile['tile_score_id']}",
                    "",
                    f"- Very-high segments in tile: `{tile.get('tile_very_high_band_segment_count')}`",
                    f"- Intersecting scored segments: `{tile.get('intersection_segment_count')}`",
                    f"- Maximum tile score: `{_metric_or_na(tile.get('tile_max_public_score_index'), decimals=1)}`",
                    "- Supporting segments:",
                ]
            )
            top_segments = tile.get("top_segments", [])
            for segment in top_segments[:5]:
                lines.append(
                    f"  - `{segment.get('segment_score_id')}` | {segment.get('public_score_band')} | "
                    f"score {segment.get('public_score_index')} | "
                    f"predicted {segment.get('predicted_crash_count')}"
                )
            lines.append("")
    else:
        lines.extend(["No hotspot-tile shortlist is available.", ""])

    scenario_countermeasures = brief.get("scenario_countermeasures")
    if isinstance(scenario_countermeasures, dict):
        lines.extend(["## Scenario Countermeasures", ""])
        for scenario in scenario_countermeasures.get("top_scenarios", [])[:3]:
            lines.append(
                f"1. **{scenario.get('title')}**. Expected reduction "
                f"`{_metric_or_na(scenario.get('expected_crash_reduction'), decimals=2)}` across "
                f"`{scenario.get('linked_segment_count')}` linked segments."
            )
        top_portfolios = scenario_countermeasures.get("top_portfolios", [])
        if top_portfolios:
            lines.extend(["", "### Top Portfolios", ""])
            for portfolio in top_portfolios[:3]:
                title = "; ".join(portfolio.get("scenario_titles", []))
                lines.append(
                    f"1. **{title}**. Expected reduction "
                    f"`{_metric_or_na(portfolio.get('expected_crash_reduction'), decimals=2)}` across "
                    f"`{portfolio.get('distinct_segment_count')}` distinct segments."
                )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_intervention_briefs(
    *,
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
    output_dir: str | Path = "data/intervention_briefs",
    prediction_run_labels: list[str] | None = None,
    scenario_bundle_root: str | Path | None = DEFAULT_SCENARIO_BUNDLE_ROOT,
) -> dict[str, Any]:
    dashboard_summary_input = Path(dashboard_summary_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    scenario_bundle_root_path = Path(scenario_bundle_root) if scenario_bundle_root is not None else None

    summary = _load_dashboard_summary(dashboard_summary_input)
    published_runs = list(summary.get("published_runs", []))
    if prediction_run_labels:
        wanted = {str(label) for label in prediction_run_labels}
        published_runs = [
            record
            for record in published_runs
            if str(record.get("prediction_run_label")) in wanted
        ]
    if not published_runs:
        raise RuntimeError("No published runs matched the requested intervention-brief filters.")

    intervention_priority = list(summary.get("intervention_priority", []))
    transferability_matrix = list(summary.get("transferability_matrix", []))
    intervention_shortlists = list(summary.get("intervention_shortlists", []))

    brief_outputs: list[dict[str, Any]] = []
    for run_record in published_runs:
        prediction_run_label = str(run_record["prediction_run_label"])
        run_output_dir = output_root / prediction_run_label
        run_output_dir.mkdir(parents=True, exist_ok=True)
        brief_json_path = run_output_dir / "intervention_brief.json"
        brief_markdown_path = run_output_dir / "intervention_brief.md"
        manifest_path = run_output_dir / "intervention_brief.manifest.json"

        priority_record = _find_by_key(intervention_priority, "prediction_run_label", prediction_run_label)
        transfer_record = _find_by_key(transferability_matrix, "city_key", str(run_record["city_key"]))
        shortlist_record = _find_by_key(intervention_shortlists, "prediction_run_label", prediction_run_label)
        scenario_bundle = _load_optional_scenario_bundle(
            scenario_bundle_root=scenario_bundle_root_path,
            prediction_run_label=prediction_run_label,
        )

        brief = _brief_payload(
            dashboard_summary_path=dashboard_summary_input,
            run_record=run_record,
            priority_record=priority_record,
            transfer_record=transfer_record,
            shortlist_record=shortlist_record,
            scenario_bundle=scenario_bundle,
        )
        brief_json_path.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")
        brief_markdown_path.write_text(_brief_markdown(brief), encoding="utf-8")

        upstream_inputs = [
            _artifact_reference(
                "dashboard_summary_json",
                dashboard_summary_input,
                _sha256(dashboard_summary_input),
            ),
        ]
        for manifest_ref in (
            run_record.get("segment_scores", {}).get("manifest_path"),
            run_record.get("score_tiles", {}).get("manifest_path"),
        ):
            if manifest_ref:
                manifest_path_ref = Path(str(manifest_ref))
                if manifest_path_ref.exists():
                    upstream_inputs.append(
                        _artifact_reference(
                            "published_serving_manifest",
                            manifest_path_ref,
                            _sha256(manifest_path_ref),
                        )
                    )
        if scenario_bundle is not None and scenario_bundle.get("_scenario_bundle_path"):
            scenario_bundle_path = Path(str(scenario_bundle["_scenario_bundle_path"]))
            upstream_inputs.append(
                _artifact_reference(
                    "scenario_countermeasure_bundle",
                    scenario_bundle_path,
                    _sha256(scenario_bundle_path),
                )
            )

        manifest = {
            "intervention_brief_version": INTERVENTION_BRIEF_VERSION,
            "inputs": {
                "dashboard_summary_path": str(dashboard_summary_input),
                "dashboard_summary_sha256": _sha256(dashboard_summary_input),
                "prediction_run_label": prediction_run_label,
            },
            "outputs": {
                "brief_json_path": str(brief_json_path),
                "brief_json_sha256": _sha256(brief_json_path),
                "brief_markdown_path": str(brief_markdown_path),
                "brief_markdown_sha256": _sha256(brief_markdown_path),
                "manifest_path": str(manifest_path),
            },
            "contract": {
                "resource_name": "intervention_brief",
                "public_contract_version": INTERVENTION_BRIEF_CONTRACT_VERSION,
                "intervention_brief_version": INTERVENTION_BRIEF_VERSION,
            },
            "stats": {
                "display_name": brief["display_name"],
                "prediction_run_label": prediction_run_label,
                "top_corridor_count": len(brief["shortlist"]["top_corridors"]),
                "hotspot_tile_count": len(brief["shortlist"]["hotspot_tiles"]),
                "recommended_action_count": len(brief["recommended_actions"]),
                "observed_crash_total": brief["overview"]["observed_crash_total"],
                "tiles_very_high": brief["overview"]["tiles_very_high"],
            },
            "lineage": _build_lineage_contract(
                run_record_path=manifest_path,
                upstream_inputs=upstream_inputs,
                publishable_outputs=[
                    _artifact_reference(
                        "intervention_brief_json",
                        brief_json_path,
                        _sha256(brief_json_path),
                    ),
                    _artifact_reference(
                        "intervention_brief_markdown",
                        brief_markdown_path,
                        _sha256(brief_markdown_path),
                    ),
                ],
                supporting_outputs=[],
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        brief_outputs.append(
            {
                "display_name": brief["display_name"],
                "prediction_run_label": prediction_run_label,
                "manifest_path": str(manifest_path),
                "brief_json_path": str(brief_json_path),
                "brief_markdown_path": str(brief_markdown_path),
            }
        )

    return {
        "intervention_brief_bundle_version": INTERVENTION_BRIEF_BUNDLE_VERSION,
        "dashboard_summary_path": str(dashboard_summary_input),
        "brief_count": len(brief_outputs),
        "briefs": sorted(brief_outputs, key=lambda item: str(item["display_name"])),
    }
