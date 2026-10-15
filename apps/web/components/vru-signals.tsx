"use client";

import { STATIC_DEMO } from "@/lib/demo-mode";

import { apiFetch } from "@/lib/demo-api";

import { useEffect, useMemo, useState } from "react";

import { KpiStrip, WorkspacePage } from "@/components/layout";
import { usePlatformSession } from "@/components/session-provider";
import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  NoAccessState,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { getClientApiBaseUrl } from "@/lib/api-client";
import { canAccessArea } from "@/lib/platform-shell";
import {
  capabilityRows,
  isUnsupportedOperationsCity,
  releaseBoundaryRows,
  shouldFetchSignalPhase,
  shouldFetchVru,
  type TrafficOperationsCapabilitiesPayload,
} from "@/lib/traffic-operations";

const API_BASE_URL = getClientApiBaseUrl();
const DEFAULT_CITY_KEY = STATIC_DEMO ? "tirana" : "bari";

type VruHighlights = {
  top_pedestrian_segment?: Record<string, unknown> | null;
  top_cyclist_segment?: Record<string, unknown> | null;
  top_crossing_candidate?: Record<string, unknown> | null;
};

type VruSummaryPayload = {
  api_version: string;
  contract_version: string;
  city: { city_key?: string; display_name?: string };
  layer_status?: string | null;
  generated_at_utc?: string | null;
  stats?: Record<string, number | undefined>;
  planning_highlights: VruHighlights;
};

type VruCorridorRow = {
  corridor_label?: string | null;
  crossing_count?: number | null;
  protected_crossing_gap_count?: number | null;
  micromobility_corridor_segment_count?: number | null;
  micromobility_gap_score?: number | null;
  predicted_crash_total?: number | null;
};

type VruCorridorsPayload = {
  api_version: string;
  contract_version: string;
  corridor_count: number;
  corridors: VruCorridorRow[];
};

type SignalPhaseOverviewPayload = {
  api_version: string;
  contract_version: string;
  city: { city_key?: string };
  coverage: {
    summary: Record<string, number | undefined>;
  };
  target_count: number;
  targets_summary: Record<string, number | undefined>;
  operator_board: {
    totals: { ready_count: number; hold_count: number };
    ready_queue_head: Array<{
      junction_id?: string | null;
      action_category?: string | null;
      due_date?: string | null;
      due_now?: string | null;
      action_summary?: string | null;
    }>;
    hold_queue_head: Array<{
      junction_id?: string | null;
      handoff_status?: string | null;
      action_summary?: string | null;
    }>;
  };
};

async function fetchJson<T>(input: string): Promise<T> {
  const response = await apiFetch(input, { cache: "no-store", credentials: "include" });
  if (!response.ok) {
    throw new Error(`${input} -> HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(decimals);
}

function describeSegment(record: Record<string, unknown> | null | undefined): string {
  if (!record) return "—";
  const label = (record.segment_label as string | undefined) ?? (record.corridor_label as string | undefined);
  return label ?? (record.segment_id as string | undefined) ?? "—";
}

function describeCrossing(record: Record<string, unknown> | null | undefined): string {
  if (!record) return "—";
  return ((record.crossing_name as string | undefined) ??
    (record.corridor_label as string | undefined) ??
    (record.crossing_id as string | undefined)) ?? "—";
}

export function VruSignalsOperations({ cityKey = DEFAULT_CITY_KEY }: { cityKey?: string } = {}) {
  const { session } = usePlatformSession();
  const hasTrafficAccess = canAccessArea(session, "traffic_engineering");
  const activeCityKey = session.selectedMunicipalityId ?? cityKey;

  const [capabilities, setCapabilities] = useState<TrafficOperationsCapabilitiesPayload | null>(null);
  const [vruSummary, setVruSummary] = useState<VruSummaryPayload | null>(null);
  const [vruCorridors, setVruCorridors] = useState<VruCorridorsPayload | null>(null);
  const [signalOverview, setSignalOverview] = useState<SignalPhaseOverviewPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasTrafficAccess) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setCapabilities(null);
    setVruSummary(null);
    setVruCorridors(null);
    setSignalOverview(null);

    fetchJson<TrafficOperationsCapabilitiesPayload>(
      `${API_BASE_URL}/v1/traffic-operations/cities/${encodeURIComponent(activeCityKey)}/capabilities`,
    )
      .then(async (scope) => {
        if (cancelled) return;
        setCapabilities(scope);

        if (isUnsupportedOperationsCity(scope)) {
          return;
        }

        const fetchVru = shouldFetchVru(scope);
        const [summary, corridors, overview] = await Promise.all([
          fetchVru
            ? fetchJson<VruSummaryPayload>(
                `${API_BASE_URL}/v1/vru/cities/${encodeURIComponent(activeCityKey)}/summary`,
              )
            : Promise.resolve(null),
          fetchVru
            ? fetchJson<VruCorridorsPayload>(
                `${API_BASE_URL}/v1/vru/cities/${encodeURIComponent(activeCityKey)}/top-corridors?limit=15`,
              )
            : Promise.resolve(null),
          shouldFetchSignalPhase(scope)
            ? fetchJson<SignalPhaseOverviewPayload>(
                `${API_BASE_URL}/v1/signal-phase/cities/${encodeURIComponent(activeCityKey)}/overview`,
              )
            : Promise.resolve(null),
        ]);

        if (cancelled) return;
        setVruSummary(summary);
        setVruCorridors(corridors);
        setSignalOverview(overview);
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
  }, [activeCityKey, hasTrafficAccess]);

  const unsupportedCity = isUnsupportedOperationsCity(capabilities);
  const vruCapability = capabilities?.capabilities.find(
    (row) => row.capability_id === "vru_priority_intelligence",
  );
  const signalCapability = capabilities?.capabilities.find(
    (row) => row.capability_id === "signal_phase_operator_board",
  );

  const corridorRows = useMemo(() => {
    if (!vruCorridors) return [] as string[][];
    return vruCorridors.corridors.map((row) => [
      row.corridor_label ?? "—",
      String(row.crossing_count ?? "—"),
      String(row.protected_crossing_gap_count ?? "—"),
      String(row.micromobility_corridor_segment_count ?? "—"),
      formatNumber(row.micromobility_gap_score),
      formatNumber(row.predicted_crash_total),
    ]);
  }, [vruCorridors]);

  const readyRows = useMemo(() => {
    const queue = signalOverview?.operator_board.ready_queue_head ?? [];
    return queue.map((row) => [
      row.junction_id ?? "—",
      row.action_category ?? "—",
      row.due_date ?? "—",
      row.due_now ?? "—",
      row.action_summary ?? "—",
    ]);
  }, [signalOverview]);

  const holdRows = useMemo(() => {
    const queue = signalOverview?.operator_board.hold_queue_head ?? [];
    return queue.map((row) => [
      row.junction_id ?? "—",
      row.handoff_status ?? "—",
      row.action_summary ?? "—",
    ]);
  }, [signalOverview]);

  return (
    <WorkspacePage
      density="compact"
      header={
        <PageHeader
          eyebrow="Operations"
          title={`Traffic operations scope for ${activeCityKey}.`}
          description="Traffic engineers can review only the VRU and signal-phase workflows that are supported for the selected municipality, with preview and governance limits visible before any operational data is shown."
        />
      }
      kpis={
        hasTrafficAccess && !unsupportedCity ? (
          <KpiStrip>
            <MetricCard
              label="VRU segments"
              value={String(vruSummary?.stats?.segment_feature_count ?? (isLoading ? "…" : "—"))}
              footnote={vruCapability?.confidence_label ?? "Segments with VRU exposure features"}
            />
            <MetricCard
              label="VRU crossings"
              value={String(vruSummary?.stats?.crossing_feature_count ?? (isLoading ? "…" : "—"))}
              footnote={vruCapability?.governance_label ?? "Crossings with priority scoring"}
            />
            <MetricCard
              label="Signal coverage"
              value={String(
                signalOverview?.coverage.summary?.movements_with_provider_data ?? (isLoading ? "…" : "—"),
              )}
              footnote={signalCapability?.confidence_label ?? "Movements with provider data"}
            />
            <MetricCard
              label="Operator ready"
              value={String(signalOverview?.operator_board.totals.ready_count ?? (isLoading ? "…" : "—"))}
              footnote="Read-only preview; no send/writeback controls in v1.0"
            />
          </KpiStrip>
        ) : null
      }
    >
      {!hasTrafficAccess && (
        <NoAccessState
          title="Traffic operations access required"
          detail="VRU and signal-phase operations are restricted to traffic engineers, admins, and super admins."
        />
      )}

      {isLoading ? (
        <LoadingState
          title="Loading traffic operations"
          detail="Preparing VRU highlights, priority corridors, signal coverage, and operator queues."
        />
      ) : null}

      {error ? (
        <ErrorState detail={`The traffic operations board could not load this city. ${error}`} />
      ) : null}

      {hasTrafficAccess && capabilities && (
        <Panel
          title="Production scope and capability gates"
          detail={capabilities.production_scope.reason}
          accent={capabilities.production_scope.supported_for_v1 ? "teal" : "rust"}
        >
          <div className="chip-row">
            <StatusPill
              label={capabilities.production_scope.supported_for_v1 ? "v1.0 supported" : "not v1.0 supported"}
              tone={capabilities.production_scope.supported_for_v1 ? "success" : "warning"}
            />
            <StatusPill
              label={capabilities.feature_flags.signal_phase_preview_enabled ? "signal preview flag on" : "signal preview flag off"}
              tone={capabilities.feature_flags.signal_phase_preview_enabled ? "warning" : "neutral"}
            />
            <StatusPill label="signal write actions disabled" tone="warning" />
          </div>
          <DataTable
            columns={["Capability", "Status", "Release", "Gate", "Confidence", "Governance"]}
            rows={capabilityRows(capabilities)}
          />
        </Panel>
      )}

      {hasTrafficAccess && capabilities && (
        <Panel
          title="Release boundary"
          detail="What is included in v1.0, what is preview-only, and what remains deferred to v1.5."
          accent="slate"
        >
          <DataTable columns={["Scope", "Items"]} rows={releaseBoundaryRows(capabilities)} />
        </Panel>
      )}

      {hasTrafficAccess && unsupportedCity && capabilities && (
        <EmptyState
          title="Traffic operations are not enabled for this city"
          detail={capabilities.ui_policy.unsupported_message}
        />
      )}

      {hasTrafficAccess && !unsupportedCity && (
        <>
          {capabilities?.ui_policy.show_vru_panels && (
            <>
              <Panel
                title="VRU planning highlights"
                detail="Top-priority pedestrian segment, cyclist segment, and crossing candidate."
                accent="slate"
              >
                <DataTable
                  columns={["Surface", "Label", "Predicted crashes", "Public score / Priority"]}
                  rows={[
                    [
                      "Top pedestrian segment",
                      describeSegment(vruSummary?.planning_highlights.top_pedestrian_segment),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_pedestrian_segment as { predicted_crash_count?: number })
                          ?.predicted_crash_count,
                      ),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_pedestrian_segment as { public_score_index?: number })
                          ?.public_score_index,
                      ),
                    ],
                    [
                      "Top cyclist segment",
                      describeSegment(vruSummary?.planning_highlights.top_cyclist_segment),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_cyclist_segment as { predicted_crash_count?: number })
                          ?.predicted_crash_count,
                      ),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_cyclist_segment as { public_score_index?: number })
                          ?.public_score_index,
                      ),
                    ],
                    [
                      "Top crossing candidate",
                      describeCrossing(vruSummary?.planning_highlights.top_crossing_candidate),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_crossing_candidate as { predicted_crash_count?: number })
                          ?.predicted_crash_count,
                      ),
                      formatNumber(
                        (vruSummary?.planning_highlights.top_crossing_candidate as {
                          pedestrian_crossing_priority_score?: number;
                        })?.pedestrian_crossing_priority_score,
                      ),
                    ],
                  ]}
                />
              </Panel>

              <Panel
                title="Top VRU corridors"
                detail="Ranked by predicted-crash and micromobility-gap profile."
                accent="slate"
              >
                {corridorRows.length > 0 ? (
                  <DataTable
                    columns={[
                      "Corridor",
                      "Crossings",
                      "Protected gap",
                      "Mm. segments",
                      "Mm. gap score",
                      "Predicted crashes",
                    ]}
                    rows={corridorRows}
                  />
                ) : (
                  <EmptyState
                    title="No VRU corridor rows available"
                    detail="The city is supported, but the current artifact returned no corridor profiles."
                  />
                )}
              </Panel>
            </>
          )}

          {capabilities?.ui_policy.show_signal_operator_board && (
            <Panel
              title="Signal-phase operator board"
              detail={`Preview/read-only. Ready: ${signalOverview?.operator_board.totals.ready_count ?? "—"} • Holds: ${signalOverview?.operator_board.totals.hold_count ?? "—"}`}
              accent="rust"
            >
              {readyRows.length > 0 ? (
                <DataTable
                  columns={["Junction", "Action", "Due", "Due now", "Summary"]}
                  rows={readyRows}
                />
              ) : (
                <EmptyState
                  title="No signal-phase actions ready"
                  detail="The preview board is enabled, but there are no ready action rows for this city."
                />
              )}
            </Panel>
          )}

          {capabilities?.ui_policy.show_signal_operator_board && holdRows.length > 0 && (
            <Panel title="Signal-phase holds" detail="Outstanding preview holds waiting on the lifecycle." accent="rust">
              <DataTable columns={["Junction", "Handoff status", "Summary"]} rows={holdRows} />
            </Panel>
          )}
        </>
      )}
    </WorkspacePage>
  );
}
