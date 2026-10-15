"""Scenario planner and intervention workflow service.

This service is the API-side reader for the scenario countermeasure
bundles produced by `road_risk_modeling.scenario_countermeasures`.
It exposes:

- the intervention library (catalogue of treatment archetypes)
- a city-level scenario catalog (one entry per generated bundle)
- a single city's full scenario bundle (rankings + portfolio rankings
  + planning brief summary)
- one scenario detail (with affected assets, assumptions, expected
  reductions)
- the portfolio rankings for a city
- an organization-scoped scenario workspace for draft/run/history
  authoring.

"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.api.settings import ApiSettings
from road_risk_modeling.data_governance import publishable_fields_for_role


SCENARIO_PLANNER_DEFAULT_ROLE = "analyst"

# Per-field coercers run after matrix projection so the API surface
# carries normalized list / dict shapes regardless of what the raw
# scenario JSON contained. Only list-shaped scenario fields need
# coercion - scalars pass through untouched.
_SCENARIO_FIELD_COERCERS: dict[str, Any] = {
    "target_asset_types": lambda v: list(v or []),
    "linked_segment_score_ids": lambda v: list(v or []),
    "affected_assets": lambda v: list(v or []),
    "assumptions": lambda v: list(v or []),
}


SCENARIO_PLANNER_CATALOG_CONTRACT_VERSION = "scenario_planner_catalog_v1"
SCENARIO_PLANNER_BUNDLE_CONTRACT_VERSION = "scenario_planner_bundle_v1"
SCENARIO_PLANNER_DETAIL_CONTRACT_VERSION = "scenario_planner_detail_v1"
SCENARIO_PLANNER_LIBRARY_CONTRACT_VERSION = "scenario_planner_library_v1"
SCENARIO_PLANNER_PORTFOLIO_CONTRACT_VERSION = "scenario_planner_portfolio_v1"
SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION = "scenario_planner_workspace_v1"
SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION = "scenario_planner_draft_v1"
SCENARIO_PLANNER_RUN_CONTRACT_VERSION = "scenario_planner_run_v1"

DEFAULT_SCENARIO_INDEX_RELATIVE_PATH = Path(
    "data/planning/scenario_countermeasures/scenario_countermeasure_index.json"
)
DEFAULT_INTERVENTION_LIBRARY_RELATIVE_PATH = Path(
    "data/planning/scenario_countermeasures/intervention_library.json"
)
DEFAULT_SCENARIO_WORKSPACE_RELATIVE_PATH = Path("data/runtime/scenario_workspace/scenarios.json")


class ScenarioPlannerError(RuntimeError):
    """Raised when a scenario planner request cannot be resolved."""


def _resolve_path(path_value: Path, *, root_dir: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return (root_dir / path_value).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ScenarioPlannerError(f"Missing scenario artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_index_path(settings: ApiSettings) -> Path:
    return _resolve_path(DEFAULT_SCENARIO_INDEX_RELATIVE_PATH, root_dir=settings.root_dir)


def _intervention_library_path(settings: ApiSettings) -> Path:
    return _resolve_path(DEFAULT_INTERVENTION_LIBRARY_RELATIVE_PATH, root_dir=settings.root_dir)


def _scenario_workspace_path(settings: ApiSettings) -> Path:
    return _resolve_path(settings.scenario_workspace_path, root_dir=settings.root_dir)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _coerce_float(value: Any, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, *, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _bundle_entry_for_city(index_payload: dict[str, Any], city_key: str) -> dict[str, Any]:
    for entry in index_payload.get("scenario_bundles") or []:
        if entry.get("city_key") == city_key:
            return entry
    available = sorted({entry.get("city_key") for entry in index_payload.get("scenario_bundles") or []})
    raise ScenarioPlannerError(
        f"City '{city_key}' is not registered in the scenario countermeasure index. "
        f"Available: {available}"
    )


def _load_city_bundle(settings: ApiSettings, *, city_key: str) -> dict[str, Any]:
    index_payload = _load_json(_scenario_index_path(settings))
    entry = _bundle_entry_for_city(index_payload, city_key)
    bundle_path = _resolve_path(
        Path(str(entry.get("scenario_bundle_path"))),
        root_dir=settings.root_dir,
    )
    return _load_json(bundle_path)


def _load_workspace(settings: ApiSettings) -> dict[str, Any]:
    path = _scenario_workspace_path(settings)
    if not path.is_file():
        return {
            "contract_version": SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION,
            "drafts": [],
            "runs": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ScenarioPlannerError(f"Scenario workspace must be a JSON object: {path}")
    payload.setdefault("contract_version", SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION)
    payload.setdefault("drafts", [])
    payload.setdefault("runs", [])
    if not isinstance(payload["drafts"], list) or not isinstance(payload["runs"], list):
        raise ScenarioPlannerError(f"Scenario workspace drafts/runs must be lists: {path}")
    return payload


def _write_workspace(settings: ApiSettings, payload: dict[str, Any]) -> None:
    path = _scenario_workspace_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["contract_version"] = SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _workspace_index(workspace: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = workspace.get(key) or []
    return [row for row in rows if isinstance(row, dict)]


def _intervention_by_code(settings: ApiSettings, intervention_code: str) -> dict[str, Any]:
    library = build_intervention_library(settings)
    for intervention in library.get("interventions") or []:
        if intervention.get("intervention_code") == intervention_code:
            return intervention
    raise ScenarioPlannerError(f"Intervention '{intervention_code}' is not registered in the intervention library.")


def _matching_generated_scenario(
    settings: ApiSettings,
    *,
    city_key: str,
    intervention_code: str,
    target_context_key: str | None = None,
) -> dict[str, Any] | None:
    try:
        bundle = _load_city_bundle(settings, city_key=city_key)
    except ScenarioPlannerError:
        raise
    scenarios = [row for row in bundle.get("scenario_rankings") or [] if isinstance(row, dict)]
    if target_context_key:
        for scenario in scenarios:
            if (
                scenario.get("intervention_code") == intervention_code
                and scenario.get("target_context_key") == target_context_key
            ):
                return scenario
    for scenario in scenarios:
        if scenario.get("intervention_code") == intervention_code:
            return scenario
    return scenarios[0] if scenarios else None


def _draft_summary_row(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "scenario_draft_id": draft.get("scenario_draft_id"),
        "organization_id": draft.get("organization_id"),
        "city_key": draft.get("city_key"),
        "name": draft.get("name"),
        "intervention_code": draft.get("intervention_code"),
        "target_context_key": draft.get("target_context_key"),
        "target_context_label": draft.get("target_context_label"),
        "target_asset_count": len(draft.get("target_asset_ids") or []),
        "cost_class": draft.get("cost_class"),
        "uncertainty": draft.get("uncertainty"),
        "status": draft.get("status"),
        "latest_run_id": draft.get("latest_run_id"),
        "validation": dict(draft.get("validation") or {}),
        "created_at_utc": draft.get("created_at_utc"),
        "updated_at_utc": draft.get("updated_at_utc"),
    }


def _run_summary_row(run: dict[str, Any]) -> dict[str, Any]:
    before_after = dict(run.get("before_after") or {})
    return {
        "contract_version": SCENARIO_PLANNER_RUN_CONTRACT_VERSION,
        "scenario_run_id": run.get("scenario_run_id"),
        "scenario_draft_id": run.get("scenario_draft_id"),
        "organization_id": run.get("organization_id"),
        "city_key": run.get("city_key"),
        "name": run.get("name"),
        "intervention_code": run.get("intervention_code"),
        "status": run.get("status"),
        "baseline_predicted_crash_total": before_after.get("baseline_predicted_crash_total"),
        "counterfactual_predicted_crash_total": before_after.get("counterfactual_predicted_crash_total"),
        "expected_crash_reduction": before_after.get("expected_crash_reduction"),
        "expected_relative_reduction": before_after.get("expected_relative_reduction"),
        "confidence": run.get("confidence"),
        "completed_at_utc": run.get("completed_at_utc"),
    }


def _find_draft(workspace: dict[str, Any], *, organization_id: str, scenario_draft_id: str) -> tuple[int, dict[str, Any]]:
    for index, draft in enumerate(_workspace_index(workspace, "drafts")):
        if draft.get("scenario_draft_id") == scenario_draft_id:
            if draft.get("organization_id") != organization_id:
                raise ScenarioPlannerError("Scenario draft is outside the requested organization scope.")
            return index, draft
    raise ScenarioPlannerError(f"Scenario draft '{scenario_draft_id}' was not found.")


def _build_validation(
    settings: ApiSettings,
    *,
    draft: dict[str, Any],
    intervention: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not _coerce_string(draft.get("organization_id")):
        errors.append("organization_id is required.")
    if not _coerce_string(draft.get("city_key")):
        errors.append("city_key is required.")
    if not _coerce_string(draft.get("name")):
        errors.append("Scenario name is required.")
    intervention_code = _coerce_string(draft.get("intervention_code"))
    if not intervention_code:
        errors.append("intervention_code is required.")
    if not (
        _coerce_string(draft.get("target_context_key"))
        or _coerce_string(draft.get("target_context_label"))
        or _coerce_string_list(draft.get("target_asset_ids"))
    ):
        errors.append("Select a target context or provide at least one target asset id.")

    try:
        _load_city_bundle(settings, city_key=str(draft.get("city_key")))
    except ScenarioPlannerError as exc:
        errors.append(str(exc))

    if intervention is None and intervention_code:
        try:
            intervention = _intervention_by_code(settings, intervention_code)
        except ScenarioPlannerError as exc:
            errors.append(str(exc))

    parameters = dict(draft.get("parameters") or {})
    baseline = _coerce_float(parameters.get("baseline_predicted_crash_total"))
    if baseline is not None and baseline <= 0:
        errors.append("baseline_predicted_crash_total must be greater than zero when provided.")
    relative_reduction = _coerce_float(parameters.get("expected_relative_reduction"))
    if relative_reduction is not None and not 0 <= relative_reduction <= 0.95:
        errors.append("expected_relative_reduction must be between 0 and 0.95.")

    if intervention is not None:
        supported_asset_types = intervention.get("supported_asset_types") or []
        target_asset_types = draft.get("target_asset_types") or []
        if supported_asset_types and target_asset_types:
            unsupported = sorted(set(target_asset_types) - set(supported_asset_types))
            if unsupported:
                warnings.append(
                    "Target asset types are outside the intervention library support: "
                    + ", ".join(unsupported)
                )
    if not parameters.get("baseline_predicted_crash_total"):
        warnings.append("Baseline crash total will be inferred from the generated city scenario bundle.")
    if not parameters.get("expected_relative_reduction"):
        warnings.append("Expected reduction will use the intervention library central effect.")

    return {
        "status": "valid" if not errors else "needs_input",
        "errors": errors,
        "warnings": warnings,
    }


def _defaulted_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    name: str,
    intervention_code: str,
    target_context_key: str | None,
    target_context_label: str | None,
    target_asset_ids: list[str],
    parameters: dict[str, Any],
    assumptions: list[str],
    cost_class: str,
    uncertainty: str,
    actor_subject: str | None,
) -> dict[str, Any]:
    intervention = _intervention_by_code(settings, intervention_code)
    baseline = _matching_generated_scenario(
        settings,
        city_key=city_key,
        intervention_code=intervention_code,
        target_context_key=target_context_key,
    )
    merged_parameters = dict(parameters)
    if baseline and "baseline_predicted_crash_total" not in merged_parameters:
        merged_parameters["baseline_predicted_crash_total"] = baseline.get("baseline_predicted_crash_total")
    bounds = dict(intervention.get("baseline_reduction_bounds") or {})
    if "expected_relative_reduction" not in merged_parameters:
        merged_parameters["expected_relative_reduction"] = bounds.get("central")
    now = _utc_now()
    draft = {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "scenario_draft_id": f"draft:{uuid4().hex}",
        "organization_id": organization_id,
        "city_key": city_key,
        "name": name,
        "intervention_code": intervention_code,
        "target_context_key": target_context_key or (baseline or {}).get("target_context_key"),
        "target_context_label": target_context_label or (baseline or {}).get("target_context_label"),
        "target_asset_ids": target_asset_ids,
        "target_asset_types": list((baseline or {}).get("target_asset_types") or intervention.get("supported_asset_types") or []),
        "parameters": merged_parameters,
        "assumptions": assumptions or list(intervention.get("default_assumptions") or []),
        "cost_class": cost_class,
        "uncertainty": uncertainty,
        "status": "draft",
        "latest_run_id": None,
        "created_by": actor_subject,
        "updated_by": actor_subject,
        "created_at_utc": now,
        "updated_at_utc": now,
        "baseline_reference": {
            "scenario_id": (baseline or {}).get("scenario_id"),
            "title": (baseline or {}).get("title"),
            "target_context_key": (baseline or {}).get("target_context_key"),
            "target_context_label": (baseline or {}).get("target_context_label"),
            "baseline_predicted_crash_total": (baseline or {}).get("baseline_predicted_crash_total"),
            "expected_relative_reduction": (baseline or {}).get("expected_relative_reduction"),
        },
    }
    draft["validation"] = _build_validation(settings, draft=draft, intervention=intervention)
    return draft


def _scenario_record_for_role(scenario: dict[str, Any], role: str) -> dict[str, Any]:
    """Project a scenario dict through the `scenario` matrix for `role`.

    The publishable field set is read from the `scenario` record-kind
    classification matrix in `road_risk_modeling.data_governance`. Any
    field on the input scenario that is not classified for `role` is
    default-denied; any field that IS classified for `role` is carried
    through (and list-shaped fields are normalized via
    `_SCENARIO_FIELD_COERCERS`).

    The current consumers all gate behind `ROLE_ANALYST`, so the
    default role is "analyst". A future public mirror of these
    endpoints can call this with role="public" and inherit the
    same default-deny gate for free.
    """
    publishable = set(publishable_fields_for_role("scenario", role))
    row: dict[str, Any] = {}
    for field_name in publishable:
        raw = scenario.get(field_name)
        coerce = _SCENARIO_FIELD_COERCERS.get(field_name)
        if coerce is not None:
            row[field_name] = coerce(raw)
        else:
            row[field_name] = raw
    return row


def _scenario_summary_row(
    scenario: dict[str, Any], *, role: str = SCENARIO_PLANNER_DEFAULT_ROLE,
) -> dict[str, Any]:
    """Back-compat wrapper around `_scenario_record_for_role` for the summary surface.

    Drops the analyst-extra "detail" fields (assumptions, affected_assets,
    linked_segment_score_ids) so the row matches the pre-matrix summary
    contract. `build_scenario_detail` re-adds those for its own surface.
    """
    full = _scenario_record_for_role(scenario, role)
    return {k: v for k, v in full.items() if k not in _SCENARIO_DETAIL_EXTRA_FIELDS}


# Detail-only fields kept out of the summary row but included in the
# full scenario record. They are still matrix-classified and gated by
# `_scenario_record_for_role`; this list only controls which classified
# fields the summary table on the bundle surface omits.
_SCENARIO_DETAIL_EXTRA_FIELDS: frozenset[str] = frozenset({
    "assumptions",
    "affected_assets",
    "linked_segment_score_ids",
})


def _scenario_redaction_policy_meta(role: str) -> dict[str, Any]:
    """Return the redaction-policy descriptor attached to scenario responses.

    Downstream clients can use this to confirm which matrix entry
    governed the response. Mirrors the `redaction_policy` block emitted
    by `road_risk_modeling.published_queries.query_published_resource`.
    """
    return {
        "record_kind": "scenario",
        "role": role,
        "publishable_fields": sorted(publishable_fields_for_role("scenario", role)),
    }


def _portfolio_summary_row(portfolio: dict[str, Any]) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio.get("portfolio_id"),
        "portfolio_rank": portfolio.get("portfolio_rank"),
        "portfolio_note": portfolio.get("portfolio_note"),
        "scenario_ids": list(portfolio.get("scenario_ids") or []),
        "scenario_titles": list(portfolio.get("scenario_titles") or []),
        "scenario_count": portfolio.get("scenario_count"),
        "distinct_segment_count": portfolio.get("distinct_segment_count"),
        "overlap_segment_count": portfolio.get("overlap_segment_count"),
        "expected_crash_reduction": portfolio.get("expected_crash_reduction"),
        "expected_relative_reduction": portfolio.get("expected_relative_reduction"),
        "baseline_predicted_crash_total": portfolio.get("baseline_predicted_crash_total"),
        "counterfactual_predicted_crash_total": portfolio.get("counterfactual_predicted_crash_total"),
    }


def _intervention_summary_row(intervention: dict[str, Any]) -> dict[str, Any]:
    return {
        "intervention_code": intervention.get("intervention_code"),
        "label": intervention.get("label"),
        "category": intervention.get("category"),
        "description": intervention.get("description"),
        "supported_asset_types": list(intervention.get("supported_asset_types") or []),
        "baseline_reduction_bounds": dict(intervention.get("baseline_reduction_bounds") or {}),
        "default_assumptions": list(intervention.get("default_assumptions") or []),
        "rule_summary": list(intervention.get("rule_summary") or []),
    }


def build_scenario_catalog(settings: ApiSettings) -> dict[str, Any]:
    """Return the catalog of available scenario bundles, one per city.

    For each city entry the catalog includes:

    - scenario_count, portfolio_count
    - the planning_brief_summary (top scenario, top portfolio)
    - the prediction-run label that the bundle was built against
    """
    index_path = _scenario_index_path(settings)
    index_payload = _load_json(index_path)
    cities: list[dict[str, Any]] = []
    for entry in index_payload.get("scenario_bundles") or []:
        try:
            bundle_path = _resolve_path(
                Path(str(entry.get("scenario_bundle_path"))),
                root_dir=settings.root_dir,
            )
            bundle = _load_json(bundle_path)
        except ScenarioPlannerError:
            bundle = {}
        cities.append(
            {
                "city_key": entry.get("city_key"),
                "display_name": entry.get("display_name"),
                "prediction_run_label": entry.get("prediction_run_label"),
                "scenario_bundle_path": entry.get("scenario_bundle_path"),
                "scenario_count": len(bundle.get("scenario_rankings") or []),
                "portfolio_count": len(bundle.get("portfolio_rankings") or []),
                "planning_brief_summary": dict(bundle.get("planning_brief_summary") or {}),
            }
        )
    stats = dict(index_payload.get("stats") or {})
    return {
        "contract_version": SCENARIO_PLANNER_CATALOG_CONTRACT_VERSION,
        "scenario_index_path": str(index_path),
        "generated_at_utc": index_payload.get("generated_at_utc"),
        "stats": {
            "library_intervention_count": stats.get("library_intervention_count"),
            "scenario_bundle_count": stats.get("scenario_bundle_count"),
            "city_count": len(cities),
        },
        "cities": cities,
    }


def build_intervention_library(settings: ApiSettings) -> dict[str, Any]:
    """Return the intervention library (treatment archetypes catalog)."""
    library_path = _intervention_library_path(settings)
    payload = _load_json(library_path)
    interventions = [_intervention_summary_row(item) for item in payload.get("interventions") or []]
    return {
        "contract_version": SCENARIO_PLANNER_LIBRARY_CONTRACT_VERSION,
        "intervention_library_path": str(library_path),
        "intervention_library_version": payload.get("intervention_library_version"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "intervention_count": len(interventions),
        "interventions": interventions,
    }


def build_city_scenario_bundle(
    settings: ApiSettings,
    *,
    city_key: str,
    scenario_limit: int | None = None,
    portfolio_limit: int | None = None,
    role: str = SCENARIO_PLANNER_DEFAULT_ROLE,
) -> dict[str, Any]:
    """Return the full scenario bundle for one city.

    `role` selects which entries of the `scenario` classification matrix
    are publishable. Defaults to `"analyst"` because every scenario
    endpoint is currently analyst-gated; passing `"public"` here would
    default-deny every internal field for a future public mirror.
    """
    bundle = _load_city_bundle(settings, city_key=city_key)
    scenarios = [_scenario_summary_row(s, role=role) for s in bundle.get("scenario_rankings") or []]
    portfolios = [_portfolio_summary_row(p) for p in bundle.get("portfolio_rankings") or []]
    if scenario_limit is not None:
        scenarios = scenarios[: max(scenario_limit, 0)]
    if portfolio_limit is not None:
        portfolios = portfolios[: max(portfolio_limit, 0)]
    return {
        "contract_version": SCENARIO_PLANNER_BUNDLE_CONTRACT_VERSION,
        "city": {
            "city_key": bundle.get("city_key"),
            "display_name": bundle.get("display_name"),
            "prediction_run_label": bundle.get("prediction_run_label"),
        },
        "generated_at_utc": bundle.get("generated_at_utc"),
        "planning_brief_summary": dict(bundle.get("planning_brief_summary") or {}),
        "totals": {
            "scenario_count": len(bundle.get("scenario_rankings") or []),
            "portfolio_count": len(bundle.get("portfolio_rankings") or []),
        },
        "scenarios": scenarios,
        "portfolios": portfolios,
        "redaction_policy": _scenario_redaction_policy_meta(role),
    }


def build_portfolio_rankings(
    settings: ApiSettings,
    *,
    city_key: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return only the portfolio rankings (no per-scenario assets)."""
    bundle = _load_city_bundle(settings, city_key=city_key)
    portfolios = [_portfolio_summary_row(p) for p in bundle.get("portfolio_rankings") or []]
    if limit is not None:
        portfolios = portfolios[: max(limit, 0)]
    return {
        "contract_version": SCENARIO_PLANNER_PORTFOLIO_CONTRACT_VERSION,
        "city": {
            "city_key": bundle.get("city_key"),
            "display_name": bundle.get("display_name"),
        },
        "totals": {
            "portfolio_count": len(bundle.get("portfolio_rankings") or []),
        },
        "portfolios": portfolios,
    }


def build_scenario_detail(
    settings: ApiSettings,
    *,
    city_key: str,
    scenario_id: str,
    role: str = SCENARIO_PLANNER_DEFAULT_ROLE,
) -> dict[str, Any]:
    """Return one scenario's full detail block.

    The detail keeps the analyst-relevant context: affected assets,
    assumptions, expected reductions, the linked segment-score ids.
    All fields are projected through `publishable_fields_for_role`
    against the `scenario` record-kind matrix so a future role with a
    narrower visibility (e.g. `"public"`) automatically gets the
    internal-only fields default-denied.
    """
    bundle = _load_city_bundle(settings, city_key=city_key)
    scenarios = bundle.get("scenario_rankings") or []
    match: dict[str, Any] | None = None
    for scenario in scenarios:
        if scenario.get("scenario_id") == scenario_id:
            match = scenario
            break
    if match is None:
        raise ScenarioPlannerError(
            f"Scenario '{scenario_id}' not found in bundle for city '{city_key}'."
        )
    return {
        "contract_version": SCENARIO_PLANNER_DETAIL_CONTRACT_VERSION,
        "city": {
            "city_key": bundle.get("city_key"),
            "display_name": bundle.get("display_name"),
            "prediction_run_label": bundle.get("prediction_run_label"),
        },
        "scenario": _scenario_record_for_role(match, role),
        "redaction_policy": _scenario_redaction_policy_meta(role),
    }


def create_scenario_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    name: str,
    intervention_code: str,
    target_context_key: str | None = None,
    target_context_label: str | None = None,
    target_asset_ids: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
    assumptions: list[str] | None = None,
    cost_class: str = "medium",
    uncertainty: str = "medium",
    actor_subject: str | None = None,
) -> dict[str, Any]:
    """Create and persist an organization-scoped scenario draft."""
    resolved_organization_id = _coerce_string(organization_id)
    resolved_city_key = _coerce_string(city_key)
    resolved_name = _coerce_string(name)
    resolved_intervention_code = _coerce_string(intervention_code)
    if not resolved_organization_id or not resolved_city_key or not resolved_name or not resolved_intervention_code:
        raise ScenarioPlannerError("organization_id, city_key, name, and intervention_code are required.")

    draft = _defaulted_draft(
        settings,
        organization_id=resolved_organization_id,
        city_key=resolved_city_key,
        name=resolved_name,
        intervention_code=resolved_intervention_code,
        target_context_key=_coerce_string(target_context_key),
        target_context_label=_coerce_string(target_context_label),
        target_asset_ids=_coerce_string_list(target_asset_ids),
        parameters=dict(parameters or {}),
        assumptions=_coerce_string_list(assumptions),
        cost_class=_coerce_string(cost_class) or "medium",
        uncertainty=_coerce_string(uncertainty) or "medium",
        actor_subject=actor_subject,
    )
    if draft["validation"]["status"] != "valid":
        draft["status"] = "needs_input"

    workspace = _load_workspace(settings)
    workspace.setdefault("drafts", []).append(draft)
    _write_workspace(settings, workspace)
    return {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "draft": draft,
    }


def update_scenario_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_draft_id: str,
    updates: dict[str, Any],
    actor_subject: str | None = None,
) -> dict[str, Any]:
    """Update editable draft fields and persist the revised validation state."""
    workspace = _load_workspace(settings)
    index, draft = _find_draft(
        workspace,
        organization_id=organization_id,
        scenario_draft_id=scenario_draft_id,
    )
    editable_scalar_fields = {
        "city_key",
        "name",
        "intervention_code",
        "target_context_key",
        "target_context_label",
        "cost_class",
        "uncertainty",
        "status",
    }
    for key in editable_scalar_fields:
        if key in updates:
            draft[key] = _coerce_string(updates[key])
    if "target_asset_ids" in updates:
        draft["target_asset_ids"] = _coerce_string_list(updates.get("target_asset_ids"))
    if "target_asset_types" in updates:
        draft["target_asset_types"] = _coerce_string_list(updates.get("target_asset_types"))
    if "parameters" in updates and updates["parameters"] is not None:
        draft["parameters"] = dict(updates["parameters"])
    if "assumptions" in updates and updates["assumptions"] is not None:
        draft["assumptions"] = _coerce_string_list(updates.get("assumptions"))

    intervention_code = _coerce_string(draft.get("intervention_code"))
    intervention = _intervention_by_code(settings, intervention_code) if intervention_code else None
    draft["validation"] = _build_validation(settings, draft=draft, intervention=intervention)
    draft["updated_by"] = actor_subject
    draft["updated_at_utc"] = _utc_now()
    workspace["drafts"][index] = draft
    _write_workspace(settings, workspace)
    return {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "draft": draft,
    }


def validate_scenario_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_draft_id: str,
) -> dict[str, Any]:
    """Return the current validation result for a draft."""
    workspace = _load_workspace(settings)
    _, draft = _find_draft(
        workspace,
        organization_id=organization_id,
        scenario_draft_id=scenario_draft_id,
    )
    intervention_code = _coerce_string(draft.get("intervention_code"))
    intervention = _intervention_by_code(settings, intervention_code) if intervention_code else None
    validation = _build_validation(settings, draft=draft, intervention=intervention)
    return {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "scenario_draft_id": scenario_draft_id,
        "organization_id": organization_id,
        "validation": validation,
    }


def list_scenario_drafts(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str | None = None,
) -> dict[str, Any]:
    """List organization-scoped scenario drafts with latest-run summaries."""
    workspace = _load_workspace(settings)
    drafts = [
        draft
        for draft in _workspace_index(workspace, "drafts")
        if draft.get("organization_id") == organization_id
        and (city_key is None or draft.get("city_key") == city_key)
    ]
    runs_by_id = {
        run.get("scenario_run_id"): _run_summary_row(run)
        for run in _workspace_index(workspace, "runs")
        if run.get("organization_id") == organization_id
    }
    rows = []
    for draft in sorted(drafts, key=lambda row: str(row.get("updated_at_utc") or ""), reverse=True):
        row = _draft_summary_row(draft)
        latest_run_id = row.get("latest_run_id")
        row["latest_run"] = runs_by_id.get(latest_run_id)
        rows.append(row)
    return {
        "contract_version": SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "draft_count": len(rows),
        "drafts": rows,
    }


def get_scenario_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_draft_id: str,
) -> dict[str, Any]:
    """Return one organization-scoped draft detail."""
    workspace = _load_workspace(settings)
    _, draft = _find_draft(
        workspace,
        organization_id=organization_id,
        scenario_draft_id=scenario_draft_id,
    )
    runs = [
        _run_summary_row(run)
        for run in _workspace_index(workspace, "runs")
        if run.get("organization_id") == organization_id
        and run.get("scenario_draft_id") == scenario_draft_id
    ]
    return {
        "contract_version": SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION,
        "draft": draft,
        "runs": sorted(runs, key=lambda row: str(row.get("completed_at_utc") or ""), reverse=True),
    }


def _compute_before_after(
    *,
    draft: dict[str, Any],
    intervention: dict[str, Any],
    parameter_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parameters = {**dict(draft.get("parameters") or {}), **dict(parameter_overrides or {})}
    bounds = dict(intervention.get("baseline_reduction_bounds") or {})
    central = _coerce_float(parameters.get("expected_relative_reduction"), default=_coerce_float(bounds.get("central"), default=0.0))
    low = _coerce_float(parameters.get("expected_relative_reduction_low"), default=_coerce_float(bounds.get("low"), default=central))
    high = _coerce_float(parameters.get("expected_relative_reduction_high"), default=_coerce_float(bounds.get("high"), default=central))
    baseline = _coerce_float(parameters.get("baseline_predicted_crash_total"), default=0.0)
    if baseline is None or baseline <= 0:
        raise ScenarioPlannerError("baseline_predicted_crash_total must be available before running a scenario.")
    if central is None:
        raise ScenarioPlannerError("expected_relative_reduction must be available before running a scenario.")

    central = _clamp(central, lower=0.0, upper=0.95)
    low = _clamp(low if low is not None else central, lower=0.0, upper=central)
    high = _clamp(high if high is not None else central, lower=central, upper=0.95)
    expected_reduction = baseline * central
    return {
        "baseline_predicted_crash_total": _round_metric(baseline),
        "counterfactual_predicted_crash_total": _round_metric(max(baseline - expected_reduction, 0.0)),
        "expected_crash_reduction": _round_metric(expected_reduction),
        "expected_crash_reduction_low": _round_metric(baseline * low),
        "expected_crash_reduction_high": _round_metric(baseline * high),
        "expected_relative_reduction": _round_metric(central),
        "expected_relative_reduction_low": _round_metric(low),
        "expected_relative_reduction_high": _round_metric(high),
    }


def run_scenario_draft(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_draft_id: str,
    parameter_overrides: dict[str, Any] | None = None,
    actor_subject: str | None = None,
) -> dict[str, Any]:
    """Execute a basic before/after run for a persisted draft."""
    workspace = _load_workspace(settings)
    index, draft = _find_draft(
        workspace,
        organization_id=organization_id,
        scenario_draft_id=scenario_draft_id,
    )
    intervention = _intervention_by_code(settings, str(draft.get("intervention_code")))
    validation = _build_validation(settings, draft=draft, intervention=intervention)
    if validation["status"] != "valid":
        raise ScenarioPlannerError("; ".join(validation["errors"]))

    now = _utc_now()
    before_after = _compute_before_after(
        draft=draft,
        intervention=intervention,
        parameter_overrides=parameter_overrides,
    )
    run = {
        "contract_version": SCENARIO_PLANNER_RUN_CONTRACT_VERSION,
        "scenario_run_id": f"run:{uuid4().hex}",
        "scenario_draft_id": scenario_draft_id,
        "organization_id": organization_id,
        "city_key": draft.get("city_key"),
        "name": draft.get("name"),
        "intervention_code": draft.get("intervention_code"),
        "status": "completed",
        "target": {
            "target_context_key": draft.get("target_context_key"),
            "target_context_label": draft.get("target_context_label"),
            "target_asset_ids": list(draft.get("target_asset_ids") or []),
            "target_asset_types": list(draft.get("target_asset_types") or []),
        },
        "intervention": intervention,
        "parameters": {**dict(draft.get("parameters") or {}), **dict(parameter_overrides or {})},
        "assumptions": list(draft.get("assumptions") or []),
        "cost_class": draft.get("cost_class"),
        "uncertainty": draft.get("uncertainty"),
        "confidence": draft.get("uncertainty") or "medium",
        "before_after": before_after,
        "baseline_reference": dict(draft.get("baseline_reference") or {}),
        "report_links": [],
        "portfolio_links": [],
        "started_at_utc": now,
        "completed_at_utc": now,
        "run_by": actor_subject,
    }
    draft["status"] = "completed"
    draft["latest_run_id"] = run["scenario_run_id"]
    draft["validation"] = validation
    draft["updated_by"] = actor_subject
    draft["updated_at_utc"] = now
    workspace["drafts"][index] = draft
    workspace.setdefault("runs", []).append(run)
    _write_workspace(settings, workspace)
    return {
        "contract_version": SCENARIO_PLANNER_RUN_CONTRACT_VERSION,
        "run": run,
        "draft": _draft_summary_row(draft),
    }


def list_scenario_runs(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str | None = None,
) -> dict[str, Any]:
    """List organization-scoped scenario run history."""
    workspace = _load_workspace(settings)
    runs = [
        _run_summary_row(run)
        for run in _workspace_index(workspace, "runs")
        if run.get("organization_id") == organization_id
        and (city_key is None or run.get("city_key") == city_key)
    ]
    runs = sorted(runs, key=lambda row: str(row.get("completed_at_utc") or ""), reverse=True)
    return {
        "contract_version": SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION,
        "organization_id": organization_id,
        "city_key": city_key,
        "run_count": len(runs),
        "runs": runs,
    }


def get_scenario_run(
    settings: ApiSettings,
    *,
    organization_id: str,
    scenario_run_id: str,
) -> dict[str, Any]:
    """Return one persisted scenario run from the workspace."""
    workspace = _load_workspace(settings)
    for run in _workspace_index(workspace, "runs"):
        if run.get("scenario_run_id") == scenario_run_id:
            if run.get("organization_id") != organization_id:
                raise ScenarioPlannerError("Scenario run is outside the requested organization scope.")
            return {
                "contract_version": SCENARIO_PLANNER_RUN_CONTRACT_VERSION,
                "run": run,
            }
    raise ScenarioPlannerError(f"Scenario run '{scenario_run_id}' was not found.")


@lru_cache(maxsize=4)
def _cached_intervention_library(library_path_str: str) -> dict[str, Any]:
    return _load_json(Path(library_path_str))


def reset_scenario_planner_cache() -> None:
    """Clear the intervention-library LRU cache (used by tests)."""
    _cached_intervention_library.cache_clear()


__all__ = [
    "DEFAULT_INTERVENTION_LIBRARY_RELATIVE_PATH",
    "DEFAULT_SCENARIO_INDEX_RELATIVE_PATH",
    "DEFAULT_SCENARIO_WORKSPACE_RELATIVE_PATH",
    "ScenarioPlannerError",
    "SCENARIO_PLANNER_BUNDLE_CONTRACT_VERSION",
    "SCENARIO_PLANNER_CATALOG_CONTRACT_VERSION",
    "SCENARIO_PLANNER_DETAIL_CONTRACT_VERSION",
    "SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION",
    "SCENARIO_PLANNER_LIBRARY_CONTRACT_VERSION",
    "SCENARIO_PLANNER_PORTFOLIO_CONTRACT_VERSION",
    "SCENARIO_PLANNER_RUN_CONTRACT_VERSION",
    "SCENARIO_PLANNER_WORKSPACE_CONTRACT_VERSION",
    "build_city_scenario_bundle",
    "build_intervention_library",
    "build_portfolio_rankings",
    "build_scenario_catalog",
    "build_scenario_detail",
    "create_scenario_draft",
    "get_scenario_run",
    "get_scenario_draft",
    "list_scenario_drafts",
    "list_scenario_runs",
    "reset_scenario_planner_cache",
    "run_scenario_draft",
    "update_scenario_draft",
    "validate_scenario_draft",
]
