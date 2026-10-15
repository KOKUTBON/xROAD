"use client";

import { apiFetch } from "@/lib/demo-api";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import { CompareView } from "@/components/composites";
import { KpiStrip, WorkspacePage } from "@/components/layout";
import { usePlatformSession } from "@/components/session-provider";
import {
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingState,
  MetricCard,
  NoAccessState,
  PageHeader,
  Panel,
  Stepper,
} from "@/components/ui";
import { getClientApiBaseUrl } from "@/lib/api-client";
import {
  buildPortfolioCreateFromRunPayload,
  buildPortfolioStatusUpdatePayload,
  summarizePortfolioRow,
} from "@/lib/intervention-portfolio";
import { canAccessArea } from "@/lib/platform-shell";
import {
  buildScenarioDraftPayload,
  summarizeBeforeAfter,
  type ScenarioDraftFormState,
} from "@/lib/scenario-authoring";

const API_BASE_URL = getClientApiBaseUrl();

type CatalogCity = {
  city_key: string;
  display_name?: string | null;
  prediction_run_label?: string | null;
  scenario_count: number;
  portfolio_count: number;
  planning_brief_summary?: {
    recommended_scenario?: {
      scenario_id?: string | null;
      title?: string | null;
      intervention_code?: string | null;
      expected_crash_reduction?: number | null;
      expected_relative_reduction?: number | null;
    } | null;
    recommended_portfolio?: {
      portfolio_id?: string | null;
      title?: string | null;
      expected_crash_reduction?: number | null;
      expected_relative_reduction?: number | null;
    } | null;
  } | null;
};

type CatalogPayload = {
  api_version: string;
  contract_version: string;
  generated_at_utc?: string | null;
  stats?: {
    library_intervention_count?: number | null;
    scenario_bundle_count?: number | null;
    city_count?: number | null;
  } | null;
  cities: CatalogCity[];
};

type InterventionRow = {
  intervention_code?: string | null;
  label?: string | null;
  category?: string | null;
  description?: string | null;
  supported_asset_types: string[];
  baseline_reduction_bounds: { low?: number; central?: number; high?: number };
  default_assumptions: string[];
  rule_summary: string[];
};

type InterventionLibraryPayload = {
  api_version: string;
  contract_version: string;
  intervention_count: number;
  interventions: InterventionRow[];
};

type ScenarioSummary = {
  scenario_id?: string | null;
  scenario_rank?: number | null;
  intervention_code?: string | null;
  title?: string | null;
  target_context_key?: string | null;
  target_context_label?: string | null;
  linked_segment_count?: number | null;
  target_asset_count?: number | null;
  expected_crash_reduction?: number | null;
  expected_relative_reduction?: number | null;
  baseline_predicted_crash_total?: number | null;
  counterfactual_predicted_crash_total?: number | null;
};

type PortfolioSummary = {
  portfolio_id?: string | null;
  portfolio_rank?: number | null;
  scenario_titles: string[];
  scenario_count?: number | null;
  distinct_segment_count?: number | null;
  overlap_segment_count?: number | null;
  expected_crash_reduction?: number | null;
  expected_relative_reduction?: number | null;
};

type CityBundlePayload = {
  api_version: string;
  contract_version: string;
  city: { city_key?: string | null; display_name?: string | null; prediction_run_label?: string | null };
  generated_at_utc?: string | null;
  planning_brief_summary?: CatalogCity["planning_brief_summary"];
  totals?: { scenario_count?: number; portfolio_count?: number };
  scenarios: ScenarioSummary[];
  portfolios: PortfolioSummary[];
};

type ScenarioDraftSummary = {
  scenario_draft_id?: string | null;
  city_key?: string | null;
  name?: string | null;
  intervention_code?: string | null;
  target_context_label?: string | null;
  cost_class?: string | null;
  uncertainty?: string | null;
  status?: string | null;
  latest_run_id?: string | null;
  validation?: { status?: string | null; errors?: string[]; warnings?: string[] } | null;
  updated_at_utc?: string | null;
  latest_run?: ScenarioRunSummary | null;
};

type ScenarioRunSummary = {
  scenario_run_id?: string | null;
  scenario_draft_id?: string | null;
  city_key?: string | null;
  name?: string | null;
  intervention_code?: string | null;
  status?: string | null;
  baseline_predicted_crash_total?: number | null;
  counterfactual_predicted_crash_total?: number | null;
  expected_crash_reduction?: number | null;
  expected_relative_reduction?: number | null;
  confidence?: string | null;
  completed_at_utc?: string | null;
};

type ScenarioDraftsPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  city_key?: string | null;
  draft_count: number;
  drafts: ScenarioDraftSummary[];
};

type ScenarioRunsPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  city_key?: string | null;
  run_count: number;
  runs: ScenarioRunSummary[];
};

type ScenarioDraftCreateResponse = {
  api_version: string;
  draft: { scenario_draft_id?: string | null; name?: string | null };
};

type ScenarioRunResponse = {
  api_version: string;
  run: ScenarioRunSummary;
};

type InterventionPortfolioRow = {
  intervention_id: string;
  city_key?: string | null;
  scenario_run_id?: string | null;
  target_object_id?: string | null;
  target_label?: string | null;
  intervention_type?: string | null;
  cost_class?: string | null;
  expected_benefit?: number | null;
  priority_score?: number | null;
  status?: string | null;
  owner_subject?: string | null;
  planned_completion_date?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  monitoring?: {
    status?: string | null;
    expected_crash_reduction?: number | null;
    after_observed_crashes?: number | null;
  } | null;
};

type InterventionPortfolioPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  city_key?: string | null;
  availability: string;
  unavailable_reason?: string | null;
  totals: {
    portfolio_count: number;
    expected_benefit?: number | null;
    by_status: Record<string, number>;
  };
  rows: InterventionPortfolioRow[];
};

type InterventionPortfolioWriteResponse = {
  api_version: string;
  operation: string;
  portfolio_item: InterventionPortfolioRow;
};

async function fetchJson<T>(input: string): Promise<T> {
  const response = await apiFetch(input, { cache: "no-store", credentials: "include" });
  if (!response.ok) {
    throw new Error(`${input} -> HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

async function sendJson<T>(input: string, method: "POST" | "PATCH", body: unknown): Promise<T> {
  const response = await apiFetch(input, {
    method,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${input} -> HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(2);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function initialDraftForm(): ScenarioDraftFormState {
  return {
    name: "",
    interventionCode: "",
    targetContextKey: "top_corridor",
    targetContextLabel: "",
    baselinePredictedCrashTotal: "",
    expectedRelativeReduction: "",
    costClass: "medium",
    uncertainty: "medium",
    assumptionsText: "",
  };
}

/** Scenario authoring flow surfaced as a Stepper (#175). */
const SCENARIO_AUTHORING_STEPS = [
  { label: "Author draft", detail: "Define the treatment, target, baseline, and assumptions" },
  { label: "Run before/after", detail: "Execute the counterfactual and store expected benefit" },
  { label: "Add to portfolio", detail: "Promote a completed run into the managed portfolio" },
];

export function ScenarioPlanner() {
  const { session } = usePlatformSession();
  const hasAnalystAccess = canAccessArea(session, "analyst");
  const organizationId = session.selectedOrganizationId ?? session.organizationIds[0] ?? null;

  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [library, setLibrary] = useState<InterventionLibraryPayload | null>(null);
  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(null);
  const [bundle, setBundle] = useState<CityBundlePayload | null>(null);
  const [draftsPayload, setDraftsPayload] = useState<ScenarioDraftsPayload | null>(null);
  const [runsPayload, setRunsPayload] = useState<ScenarioRunsPayload | null>(null);
  const [portfolioPayload, setPortfolioPayload] = useState<InterventionPortfolioPayload | null>(null);
  const [draftForm, setDraftForm] = useState<ScenarioDraftFormState>(() => initialDraftForm());
  const [isLoading, setIsLoading] = useState(false);
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [portfolioMessage, setPortfolioMessage] = useState<string | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasAnalystAccess) return;
    let cancelled = false;
    setError(null);
    Promise.all([
      fetchJson<CatalogPayload>(`${API_BASE_URL}/v1/scenarios/catalog`),
      fetchJson<InterventionLibraryPayload>(`${API_BASE_URL}/v1/scenarios/intervention-library`),
    ])
      .then(([catalogPayload, libraryPayload]) => {
        if (cancelled) return;
        setCatalog(catalogPayload);
        setLibrary(libraryPayload);
        if (!selectedCityKey && catalogPayload.cities.length > 0) {
          setSelectedCityKey(catalogPayload.cities[0].city_key);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnalystAccess]);

  useEffect(() => {
    if (!selectedCityKey) {
      setBundle(null);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchJson<CityBundlePayload>(
      `${API_BASE_URL}/v1/scenarios/cities/${encodeURIComponent(selectedCityKey)}`,
    )
      .then((next) => {
        if (!cancelled) setBundle(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCityKey]);

  useEffect(() => {
    if (!bundle || !library || library.interventions.length === 0) return;
    const topScenario = bundle.scenarios[0];
    const topInterventionCode = topScenario?.intervention_code ?? library.interventions[0]?.intervention_code ?? "";
    setDraftForm((current) => {
      if (current.name || current.interventionCode) return current;
      const intervention = library.interventions.find((row) => row.intervention_code === topInterventionCode);
      return {
        name: topScenario?.title ? `${topScenario.title} - draft` : "New safety intervention scenario",
        interventionCode: topInterventionCode,
        targetContextKey: topScenario?.target_context_key ?? "top_corridor",
        targetContextLabel: topScenario?.target_context_label ?? "",
        baselinePredictedCrashTotal: topScenario?.baseline_predicted_crash_total?.toFixed(2) ?? "",
        expectedRelativeReduction: topScenario?.expected_relative_reduction?.toFixed(3)
          ?? intervention?.baseline_reduction_bounds.central?.toString()
          ?? "",
        costClass: "medium",
        uncertainty: "medium",
        assumptionsText: intervention?.default_assumptions.join("\n") ?? "",
      };
    });
  }, [bundle, library]);

  useEffect(() => {
    if (!hasAnalystAccess || !organizationId || !selectedCityKey) {
      setDraftsPayload(null);
      setRunsPayload(null);
      setPortfolioPayload(null);
      return;
    }
    let cancelled = false;
    setIsWorkspaceLoading(true);
    setActionError(null);
    const params = new URLSearchParams({ organization_id: organizationId, city_key: selectedCityKey });
    Promise.all([
      fetchJson<ScenarioDraftsPayload>(`${API_BASE_URL}/v1/scenarios/drafts?${params.toString()}`),
      fetchJson<ScenarioRunsPayload>(`${API_BASE_URL}/v1/scenarios/runs?${params.toString()}`),
    ])
      .then(([drafts, runs]) => {
        if (cancelled) return;
        setDraftsPayload(drafts);
        setRunsPayload(runs);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setActionError(err instanceof Error ? err.message : "Unknown workspace error");
        }
      })
      .finally(() => {
        if (!cancelled) setIsWorkspaceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasAnalystAccess, organizationId, selectedCityKey]);

  useEffect(() => {
    if (!hasAnalystAccess || !organizationId || !selectedCityKey) {
      setPortfolioPayload(null);
      return;
    }
    let cancelled = false;
    setPortfolioError(null);
    const params = new URLSearchParams({ organization_id: organizationId, city_key: selectedCityKey });
    fetchJson<InterventionPortfolioPayload>(`${API_BASE_URL}/v1/interventions/portfolio?${params.toString()}`)
      .then((next) => {
        if (!cancelled) setPortfolioPayload(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) setPortfolioError(err instanceof Error ? err.message : "Unknown portfolio error");
      });
    return () => {
      cancelled = true;
    };
  }, [hasAnalystAccess, organizationId, selectedCityKey]);

  const scenarioRows = useMemo(() => {
    if (!bundle) return [] as string[][];
    return bundle.scenarios.slice(0, 50).map((scenario) => [
      String(scenario.scenario_rank ?? "—"),
      scenario.title ?? "—",
      scenario.intervention_code ?? "—",
      scenario.target_context_label ?? "—",
      formatNumber(scenario.expected_crash_reduction),
      formatPercent(scenario.expected_relative_reduction),
      String(scenario.linked_segment_count ?? "—"),
    ]);
  }, [bundle]);

  const managedPortfolioRows = useMemo(() => {
    if (!bundle) return [] as string[][];
    return bundle.portfolios.slice(0, 25).map((portfolio) => [
      String(portfolio.portfolio_rank ?? "—"),
      String(portfolio.scenario_count ?? portfolio.scenario_titles.length ?? "—"),
      formatNumber(portfolio.expected_crash_reduction),
      formatPercent(portfolio.expected_relative_reduction),
      String(portfolio.distinct_segment_count ?? "—"),
      portfolio.scenario_titles.join("; "),
    ]);
  }, [bundle]);

  const interventionRows = useMemo(() => {
    if (!library) return [] as string[][];
    return library.interventions.map((row) => [
      row.label ?? row.intervention_code ?? "—",
      row.category ?? "—",
      row.supported_asset_types.join(", "),
      formatPercent(row.baseline_reduction_bounds.central),
      `${formatPercent(row.baseline_reduction_bounds.low)} – ${formatPercent(row.baseline_reduction_bounds.high)}`,
    ]);
  }, [library]);

  const draftRows = useMemo(() => {
    return (draftsPayload?.drafts ?? []).slice(0, 20).map((draft) => [
      draft.name ?? "—",
      draft.intervention_code ?? "—",
      draft.status ?? "—",
      draft.validation?.status ?? "—",
      draft.latest_run ? summarizeBeforeAfter(draft.latest_run) : "No run yet",
      draft.updated_at_utc ?? "—",
    ]);
  }, [draftsPayload]);

  const runRows = useMemo(() => {
    return (runsPayload?.runs ?? []).slice(0, 20).map((run) => [
      run.name ?? "—",
      run.intervention_code ?? "—",
      run.status ?? "—",
      formatNumber(run.expected_crash_reduction),
      formatPercent(run.expected_relative_reduction),
      run.confidence ?? "—",
      run.completed_at_utc ?? "—",
    ]);
  }, [runsPayload]);

  const beforeAfterItems = useMemo(() => {
    return (runsPayload?.runs ?? [])
      .filter(
        (run) =>
          run.baseline_predicted_crash_total != null &&
          run.counterfactual_predicted_crash_total != null,
      )
      .slice(0, 6)
      .map((run) => ({
        label: run.name ?? run.intervention_code ?? "Run",
        before: run.baseline_predicted_crash_total as number,
        after: run.counterfactual_predicted_crash_total as number,
      }));
  }, [runsPayload]);

  // Authoring flow position: drafts exist -> step 1, runs exist -> step 2.
  const authoringStep =
    (runsPayload?.run_count ?? 0) > 0 ? 2 : (draftsPayload?.draft_count ?? 0) > 0 ? 1 : 0;

  const portfolioRows = useMemo(() => {
    return (portfolioPayload?.rows ?? []).slice(0, 25).map((row) => [
      row.target_label ?? row.target_object_id ?? "—",
      row.intervention_type ?? "—",
      row.status ?? "—",
      row.cost_class ?? "—",
      formatNumber(row.expected_benefit),
      formatNumber(row.priority_score),
      row.owner_subject ?? "—",
      row.monitoring?.status ?? "—",
    ]);
  }, [portfolioPayload]);

  async function refreshWorkspace() {
    if (!organizationId || !selectedCityKey) return;
    const params = new URLSearchParams({ organization_id: organizationId, city_key: selectedCityKey });
    const [drafts, runs] = await Promise.all([
      fetchJson<ScenarioDraftsPayload>(`${API_BASE_URL}/v1/scenarios/drafts?${params.toString()}`),
      fetchJson<ScenarioRunsPayload>(`${API_BASE_URL}/v1/scenarios/runs?${params.toString()}`),
    ]);
    setDraftsPayload(drafts);
    setRunsPayload(runs);
  }

  async function refreshPortfolio() {
    if (!organizationId || !selectedCityKey) return;
    const params = new URLSearchParams({ organization_id: organizationId, city_key: selectedCityKey });
    const next = await fetchJson<InterventionPortfolioPayload>(
      `${API_BASE_URL}/v1/interventions/portfolio?${params.toString()}`,
    );
    setPortfolioPayload(next);
  }

  async function submitScenarioDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId || !selectedCityKey) {
      setActionError("Select an organization and city before creating a scenario.");
      return;
    }
    setIsMutating(true);
    setActionMessage(null);
    setActionError(null);
    try {
      const draftResponse = await sendJson<ScenarioDraftCreateResponse>(
        `${API_BASE_URL}/v1/scenarios/drafts`,
        "POST",
        buildScenarioDraftPayload({
          organizationId,
          cityKey: selectedCityKey,
          form: draftForm,
        }),
      );
      const draftId = draftResponse.draft.scenario_draft_id;
      if (!draftId) {
        throw new Error("Created draft did not return an id.");
      }
      const runResponse = await sendJson<ScenarioRunResponse>(
        `${API_BASE_URL}/v1/scenarios/drafts/${encodeURIComponent(draftId)}/run`,
        "POST",
        { organization_id: organizationId },
      );
      setActionMessage(`Scenario created and run completed. ${summarizeBeforeAfter(runResponse.run)}`);
      await refreshWorkspace();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Scenario run failed.");
    } finally {
      setIsMutating(false);
    }
  }

  async function addRunToPortfolio(runId: string | null | undefined) {
    if (!runId || !organizationId || !selectedCityKey) return;
    setIsMutating(true);
    setPortfolioMessage(null);
    setPortfolioError(null);
    try {
      const response = await sendJson<InterventionPortfolioWriteResponse>(
        `${API_BASE_URL}/v1/interventions/portfolio`,
        "POST",
        buildPortfolioCreateFromRunPayload({
          organizationId,
          cityKey: selectedCityKey,
          scenarioRunId: runId,
          ownerSubject: session.subject,
        }),
      );
      setPortfolioMessage(`Added to portfolio. ${summarizePortfolioRow(response.portfolio_item)}`);
      await refreshPortfolio();
    } catch (err: unknown) {
      setPortfolioError(err instanceof Error ? err.message : "Portfolio add failed.");
    } finally {
      setIsMutating(false);
    }
  }

  async function updatePortfolioStatus(row: InterventionPortfolioRow, status: string) {
    if (!organizationId || !row.intervention_id) return;
    setIsMutating(true);
    setPortfolioMessage(null);
    setPortfolioError(null);
    try {
      const response = await sendJson<InterventionPortfolioWriteResponse>(
        `${API_BASE_URL}/v1/interventions/portfolio/${encodeURIComponent(row.intervention_id)}`,
        "PATCH",
        buildPortfolioStatusUpdatePayload({
          organizationId,
          status,
          ownerSubject: row.owner_subject ?? session.subject,
          notes: status === "planned" ? "Moved from shortlist into the planned municipal portfolio." : undefined,
        }),
      );
      setPortfolioMessage(`Portfolio updated. ${summarizePortfolioRow(response.portfolio_item)}`);
      await refreshPortfolio();
    } catch (err: unknown) {
      setPortfolioError(err instanceof Error ? err.message : "Portfolio update failed.");
    } finally {
      setIsMutating(false);
    }
  }

  async function removePortfolioItem(row: InterventionPortfolioRow) {
    if (!organizationId || !row.intervention_id) return;
    setIsMutating(true);
    setPortfolioMessage(null);
    setPortfolioError(null);
    try {
      const response = await sendJson<InterventionPortfolioWriteResponse>(
        `${API_BASE_URL}/v1/interventions/portfolio/${encodeURIComponent(row.intervention_id)}/remove`,
        "POST",
        { organization_id: organizationId, reason: "Removed from browser portfolio review." },
      );
      setPortfolioMessage(`Portfolio ${response.operation}.`);
      await refreshPortfolio();
    } catch (err: unknown) {
      setPortfolioError(err instanceof Error ? err.message : "Portfolio removal failed.");
    } finally {
      setIsMutating(false);
    }
  }

  async function rerunDraft(draftId: string | null | undefined) {
    if (!draftId || !organizationId) return;
    setIsMutating(true);
    setActionMessage(null);
    setActionError(null);
    try {
      const runResponse = await sendJson<ScenarioRunResponse>(
        `${API_BASE_URL}/v1/scenarios/drafts/${encodeURIComponent(draftId)}/run`,
        "POST",
        { organization_id: organizationId },
      );
      setActionMessage(`Scenario re-run completed. ${summarizeBeforeAfter(runResponse.run)}`);
      await refreshWorkspace();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Scenario re-run failed.");
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <WorkspacePage
      density="compact"
      header={
        <PageHeader
          eyebrow="Scenario planner"
          title="Compare countermeasures, expected benefits, portfolios, and treatment assumptions."
          description="Pick a city to review ranked scenarios, combined portfolios, and the intervention library planners use to prepare a defensible safety program."
        />
      }
      kpis={
        hasAnalystAccess ? (
          <KpiStrip>
            <MetricCard
              label="Scenario bundles"
              value={String(catalog?.stats?.scenario_bundle_count ?? "—")}
              footnote="Across all available cities"
            />
            <MetricCard
              label="Cities"
              value={String(catalog?.stats?.city_count ?? "—")}
              footnote="Cities with generated scenarios"
            />
            <MetricCard
              label="Interventions"
              value={String(catalog?.stats?.library_intervention_count ?? "—")}
              footnote="Treatment archetypes"
            />
            <MetricCard
              label="Scenarios in view"
              value={String(bundle?.totals?.scenario_count ?? (isLoading ? "…" : "—"))}
              footnote={bundle?.city.display_name ?? "Pick a city below"}
            />
          </KpiStrip>
        ) : null
      }
    >
      {!hasAnalystAccess && (
        <NoAccessState
          title="Analyst access required"
          detail="Scenario rankings and portfolio details are available to analysts, traffic engineers, admins, and super admins."
        />
      )}

      {hasAnalystAccess && (
        <>
          {isLoading ? (
            <LoadingState
              title="Loading scenario bundle"
              detail="Preparing city scenarios, ranked portfolios, and intervention assumptions."
            />
          ) : null}

          {error ? (
            <ErrorState detail={`The scenario planner could not load this selection. ${error}`} />
          ) : null}

          <FilterBar
            summary={
              <>
                <span>Pick a city to synchronize scenario, portfolio, and treatment tables.</span>
              </>
            }
          >
              {(catalog?.cities ?? []).map((city) => {
                const isSelected = selectedCityKey === city.city_key;
                return (
                  <button
                    key={`city-${city.city_key}`}
                    type="button"
                    onClick={() => {
                      setSelectedCityKey(city.city_key);
                      setDraftForm(initialDraftForm());
                    }}
                    className={`scenario-city-chip${isSelected ? " scenario-city-chip-selected" : ""}`}
                    aria-pressed={isSelected}
                  >
                    {(city.display_name ?? city.city_key) + ` (${city.scenario_count})`}
                  </button>
                );
              })}
          </FilterBar>

          {organizationId ? null : (
            <ErrorState detail="No organization scope is selected. Scenario authoring requires an organization-scoped session." />
          )}

          {actionMessage ? (
            <div className="warning-state">
              <strong>Scenario workflow updated</strong>
              <p>{actionMessage}</p>
            </div>
          ) : null}

          {actionError ? (
            <div className="warning-state warning-state-danger">
              <strong>Scenario workflow failed</strong>
              <p>{actionError}</p>
            </div>
          ) : null}

          {portfolioMessage ? (
            <div className="warning-state">
              <strong>Portfolio workflow updated</strong>
              <p>{portfolioMessage}</p>
            </div>
          ) : null}

          {portfolioError ? (
            <div className="warning-state warning-state-danger">
              <strong>Portfolio workflow failed</strong>
              <p>{portfolioError}</p>
            </div>
          ) : null}

          {(catalog?.cities ?? []).length === 0 && !isLoading && !error ? (
            <EmptyState
              title="No scenario bundles available"
              detail="No city has a generated scenario bundle yet. Run the planning pipeline before using this planner."
            />
          ) : null}

          <Panel
            title="Authoring flow"
            detail="Author a draft, run the before/after counterfactual, then promote a completed run into the managed portfolio."
            accent="slate"
          >
            <Stepper steps={SCENARIO_AUTHORING_STEPS} current={authoringStep} />
          </Panel>

          <Panel
            title="Author and run scenario"
            detail="Create an organization-scoped draft, execute a basic before/after run, and preserve history for reports or portfolios."
            accent="teal"
          >
            <div className="content-grid">
              <form className="governance-form" onSubmit={submitScenarioDraft}>
                <h4>Scenario draft</h4>
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={draftForm.name}
                    onChange={(event) => setDraftForm({ ...draftForm, name: event.target.value })}
                    placeholder="Reduce operating speeds on Tangenziale"
                  />
                </label>
                <label>
                  <span>Intervention</span>
                  <select
                    required
                    value={draftForm.interventionCode}
                    onChange={(event) => {
                      const selected = library?.interventions.find(
                        (row) => row.intervention_code === event.target.value,
                      );
                      setDraftForm({
                        ...draftForm,
                        interventionCode: event.target.value,
                        expectedRelativeReduction: selected?.baseline_reduction_bounds.central?.toString()
                          ?? draftForm.expectedRelativeReduction,
                        assumptionsText: selected?.default_assumptions.join("\n") ?? draftForm.assumptionsText,
                      });
                    }}
                  >
                    <option value="">Choose treatment</option>
                    {(library?.interventions ?? []).map((intervention) => (
                      <option
                        key={intervention.intervention_code ?? intervention.label ?? "intervention"}
                        value={intervention.intervention_code ?? ""}
                      >
                        {intervention.label ?? intervention.intervention_code}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Target key</span>
                  <input
                    value={draftForm.targetContextKey}
                    onChange={(event) => setDraftForm({ ...draftForm, targetContextKey: event.target.value })}
                    placeholder="top_corridor"
                  />
                </label>
                <label>
                  <span>Target label</span>
                  <input
                    required
                    value={draftForm.targetContextLabel}
                    onChange={(event) => setDraftForm({ ...draftForm, targetContextLabel: event.target.value })}
                    placeholder="High-Risk Highway Corridor"
                  />
                </label>
                <label>
                  <span>Baseline crashes/year</span>
                  <input
                    inputMode="decimal"
                    required
                    value={draftForm.baselinePredictedCrashTotal}
                    onChange={(event) => setDraftForm({ ...draftForm, baselinePredictedCrashTotal: event.target.value })}
                    placeholder="39.14"
                  />
                </label>
                <label>
                  <span>Expected reduction</span>
                  <input
                    inputMode="decimal"
                    required
                    value={draftForm.expectedRelativeReduction}
                    onChange={(event) => setDraftForm({ ...draftForm, expectedRelativeReduction: event.target.value })}
                    placeholder="0.28"
                  />
                </label>
                <label>
                  <span>Cost class</span>
                  <select
                    value={draftForm.costClass}
                    onChange={(event) => setDraftForm({ ...draftForm, costClass: event.target.value })}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                    <option value="capital">capital</option>
                  </select>
                </label>
                <label>
                  <span>Confidence</span>
                  <select
                    value={draftForm.uncertainty}
                    onChange={(event) => setDraftForm({ ...draftForm, uncertainty: event.target.value })}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="medium-high">medium-high</option>
                    <option value="high">high</option>
                  </select>
                </label>
                <label>
                  <span>Assumptions</span>
                  <textarea
                    value={draftForm.assumptionsText}
                    onChange={(event) => setDraftForm({ ...draftForm, assumptionsText: event.target.value })}
                    placeholder="One assumption per line."
                  />
                </label>
                <button
                  className="primary-button"
                  disabled={isMutating || !organizationId || !selectedCityKey}
                  type="submit"
                >
                  {isMutating ? "Running scenario..." : "Create draft and run"}
                </button>
              </form>

              <div className="scenario-authoring-summary">
                <h4>Before/after contract</h4>
                <p>
                  Runs store baseline crashes/year, counterfactual crashes/year, expected benefit,
                  confidence, assumptions, and the latest draft linkage for reporting.
                </p>
                <div className="scenario-before-after-grid">
                  <MetricCard
                    label="Drafts"
                    value={String(draftsPayload?.draft_count ?? (isWorkspaceLoading ? "…" : "0"))}
                    footnote={organizationId ?? "No organization"}
                  />
                  <MetricCard
                    label="Runs"
                    value={String(runsPayload?.run_count ?? (isWorkspaceLoading ? "…" : "0"))}
                    footnote={selectedCityKey ?? "No city"}
                    tone="teal"
                  />
                </div>
                <div className="scenario-action-row">
                  {(draftsPayload?.drafts ?? []).slice(0, 3).map((draft) => (
                    <button
                      className="ghost-button"
                      disabled={isMutating || !draft.scenario_draft_id}
                      key={draft.scenario_draft_id ?? draft.name ?? "draft"}
                      onClick={() => void rerunDraft(draft.scenario_draft_id)}
                      type="button"
                    >
                      Re-run {draft.name ?? "draft"}
                    </button>
                  ))}
                  {(runsPayload?.runs ?? []).slice(0, 3).map((run) => (
                    <button
                      className="primary-button"
                      disabled={isMutating || !run.scenario_run_id}
                      key={`portfolio-${run.scenario_run_id ?? run.name ?? "run"}`}
                      onClick={() => void addRunToPortfolio(run.scenario_run_id)}
                      type="button"
                    >
                      Add {run.name ?? "run"} to portfolio
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Panel>

          <Panel
            title="Scenario workspace history"
            detail="Organization-scoped drafts and completed runs, sorted with latest activity first."
            accent="slate"
          >
            <DataTable
              columns={["Draft", "Intervention", "Status", "Validation", "Latest before/after", "Updated"]}
              rows={draftRows}
            />
          </Panel>

          <Panel
            title="Run history"
            detail="Completed before/after executions available to downstream reporting and portfolio workflows."
            accent="rust"
          >
            <DataTable
              columns={["Run", "Intervention", "Status", "Δ crashes", "Δ %", "Confidence", "Completed"]}
              rows={runRows}
            />
          </Panel>

          {beforeAfterItems.length > 0 ? (
            <Panel
              title="Before vs after"
              detail="Predicted crashes per year before and after each completed scenario run. Reductions show in green."
              accent="teal"
            >
              <CompareView
                title="Predicted crashes before vs after"
                description="Baseline versus counterfactual predicted crashes for recent runs."
                items={beforeAfterItems}
                unit=""
              />
            </Panel>
          ) : null}

          <Panel
            title="Managed intervention portfolio"
            detail="Prioritized municipal intervention lifecycle with owner, status, cost/benefit, report export, and monitoring placeholders."
            accent="teal"
          >
            <div className="scenario-before-after-grid">
              <MetricCard
                label="Portfolio rows"
                value={String(portfolioPayload?.totals.portfolio_count ?? "0")}
                footnote={portfolioPayload?.availability ?? "not loaded"}
              />
              <MetricCard
                label="Expected benefit"
                value={formatNumber(portfolioPayload?.totals.expected_benefit)}
                footnote="Avoided crashes/year estimate"
                tone="teal"
              />
              <MetricCard
                label="Status mix"
                value={Object.keys(portfolioPayload?.totals.by_status ?? {}).length}
                footnote={Object.entries(portfolioPayload?.totals.by_status ?? {})
                  .map(([status, count]) => `${status}: ${count}`)
                  .join(" · ") || "No statuses yet"}
                tone="rust"
              />
            </div>
            {portfolioPayload?.availability === "degraded" ? (
              <div className="warning-state">
                <strong>Portfolio persistence unavailable</strong>
                <p>The portfolio API is reachable, but the operational database is unavailable.</p>
              </div>
            ) : null}
            <div className="scenario-action-row">
              {(portfolioPayload?.rows ?? []).slice(0, 3).map((row) => (
                <button
                  className="ghost-button"
                  disabled={isMutating}
                  key={`plan-${row.intervention_id}`}
                  onClick={() => void updatePortfolioStatus(row, "planned")}
                  type="button"
                >
                  Plan {row.target_label ?? row.target_object_id ?? "item"}
                </button>
              ))}
              {(portfolioPayload?.rows ?? []).slice(0, 3).map((row) => (
                <button
                  className="ghost-button"
                  disabled={isMutating}
                  key={`complete-${row.intervention_id}`}
                  onClick={() => void updatePortfolioStatus(row, "completed")}
                  type="button"
                >
                  Complete {row.target_label ?? row.target_object_id ?? "item"}
                </button>
              ))}
              {(portfolioPayload?.rows ?? []).slice(0, 3).map((row) => (
                <button
                  className="ghost-button"
                  disabled={isMutating}
                  key={`remove-${row.intervention_id}`}
                  onClick={() => void removePortfolioItem(row)}
                  type="button"
                >
                  Remove {row.target_label ?? row.target_object_id ?? "item"}
                </button>
              ))}
            </div>
            <DataTable
              columns={["Target", "Intervention", "Status", "Cost", "Benefit", "Priority", "Owner", "Monitoring"]}
              rows={managedPortfolioRows}
            />
          </Panel>

          <Panel
            title="Top scenarios"
            detail="Ranked by expected crash reduction. Top 50 shown."
            accent="slate"
          >
            <DataTable
              columns={["Rank", "Scenario", "Intervention", "Target", "Δ crashes", "Δ %", "Segments"]}
              rows={scenarioRows}
            />
          </Panel>

          <Panel
            title="Top portfolios"
            detail="Best combined scenario portfolios for the selected city."
            accent="rust"
          >
            <DataTable
              columns={["Rank", "Scenarios", "Δ crashes", "Δ %", "Segments", "Composition"]}
              rows={portfolioRows}
            />
          </Panel>

          <Panel
            title="Intervention library"
            detail="Treatment archetypes available to the scenario engine."
            accent="slate"
          >
            <DataTable
              columns={["Treatment", "Category", "Assets", "Central reduction", "Low – High"]}
              rows={interventionRows}
            />
          </Panel>
        </>
      )}
    </WorkspacePage>
  );
}
