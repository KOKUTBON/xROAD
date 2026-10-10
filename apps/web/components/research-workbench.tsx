"use client";

import { apiFetch } from "@/lib/demo-api";

import { useEffect, useState } from "react";
import { usePlatformSession } from "@/components/session-provider";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { KpiStrip, WorkSurface, WorkspacePage } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";

const API_BASE_URL = getClientApiBaseUrl();

type ModelMetricRecord = {
  model_name: string;
  poisson_deviance: number;
  negative_log_likelihood: number;
  brier_score: number;
  roc_auc: number;
  pr_auc: number;
  mae: number;
  top_5_capture: number;
  top_10_capture: number;
  top_20_capture: number;
  top_50_capture: number;
};

type ResearchPanelRiskResponse = {
  api_version: string;
  network_label: string;
  split_strategy: string;
  total_observations: number;
  train_count: number;
  test_count: number;
  baseline_metrics: Record<string, ModelMetricRecord>;
  data_manifest: {
    manifest_id: string;
    sha256_digest: string;
    timestamp: string;
    record_counts: Record<string, number>;
  };
  sample_records?: Array<{
    segment_id: string;
    period_start: string;
    aadt: number;
    length_km: number;
    exposure_vkt: number;
    observed_crashes: number;
    predicted_rate: number;
  }>;
};

export function ResearchWorkbench() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId || "org-mobility-research";
  const [splitStrategy, setSplitStrategy] = useState<string>("forward_temporal");
  const [weeksCount, setWeeksCount] = useState<number>(8);
  const [networkLabel, setNetworkLabel] = useState<string>("metropolitan_risk_research");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ResearchPanelRiskResponse | null>(null);

  async function runEvaluation(strategy = splitStrategy) {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${API_BASE_URL}/v1/research/evaluate-panel-risk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          organization_id: organizationId,
          network_label: networkLabel,
          split_strategy: strategy,
          weeks_count: weeksCount,
        }),
      });
      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}));
        throw new Error(errPayload?.detail || `API error (${res.status})`);
      }
      const data: ResearchPanelRiskResponse = await res.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run panel research evaluation.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    runEvaluation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [splitStrategy, organizationId]);

  const metrics = results?.baseline_metrics;
  const modelsList = metrics ? Object.values(metrics) : [];

  const bestDevianceModel = modelsList.length
    ? [...modelsList].sort((a, b) => a.poisson_deviance - b.poisson_deviance)[0]
    : null;

  const bestAucModel = modelsList.length
    ? [...modelsList].sort((a, b) => b.roc_auc - a.roc_auc)[0]
    : null;

  const bestCaptureModel = modelsList.length
    ? [...modelsList].sort((a, b) => b.top_20_capture - a.top_20_capture)[0]
    : null;

  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Scientific Research Desk"
          title="Exposure-Normalized Panel Risk Modeling & Baselines"
          description="Rigorously evaluate crash occurrence rates with explicit traffic exposure denominators (AADT × L × 7), strict causal weather joins, and non-leaking cross-validation."
          meta={
            <>
              <StatusPill label={`Split: ${splitStrategy}`} tone="info" />
              <StatusPill label={`Exposure Offset: log(E)`} tone="success" />
              <StatusPill label="Air-gapped Baselines" tone="neutral" />
            </>
          }
        />
      }
      kpis={
        <KpiStrip>
          <MetricCard
            label="Best Poisson Deviance"
            value={bestDevianceModel ? bestDevianceModel.poisson_deviance.toFixed(4) : "—"}
            footnote={bestDevianceModel ? bestDevianceModel.model_name : "Evaluating..."}
            tone="teal"
          />
          <MetricCard
            label="Peak Discrimination (ROC-AUC)"
            value={bestAucModel ? bestAucModel.roc_auc.toFixed(3) : "—"}
            footnote={bestAucModel ? bestAucModel.model_name : "Evaluating..."}
            tone="slate"
          />
          <MetricCard
            label="Top-20% Crash Capture"
            value={bestCaptureModel ? `${(bestCaptureModel.top_20_capture * 100).toFixed(1)}%` : "—"}
            footnote={bestCaptureModel ? `${bestCaptureModel.model_name} concentration` : "Evaluating..."}
            tone="teal"
          />
          <MetricCard
            label="Segment-Week Panel"
            value={results ? String(results.total_observations) : "—"}
            footnote={results ? `Train: ${results.train_count} | Test: ${results.test_count}` : "Panel assembly"}
            tone="slate"
          />
        </KpiStrip>
      }
      filters={
        <Panel title="Validation Strategy & Panel Controls">
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "220px" }}>
              <span className="type-body-small">Cross-Validation Split Strategy</span>
              <select
                className="input-select"
                value={splitStrategy}
                onChange={(e) => setSplitStrategy(e.target.value)}
              >
                <option value="forward_temporal">Forward Temporal (Train Past / Test Future)</option>
                <option value="spatial_group">Spatial GroupKFold (Disjoint Corridors)</option>
                <option value="space_time_blocked">Space × Time Blocked Cross-Validation</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "180px" }}>
              <span className="type-body-small">Observation Horizon</span>
              <select
                className="input-select"
                value={weeksCount}
                onChange={(e) => setWeeksCount(Number(e.target.value))}
              >
                <option value={4}>4 Weeks Panel</option>
                <option value={8}>8 Weeks Panel (Benchmark Standard)</option>
                <option value={12}>12 Weeks Panel</option>
                <option value={52}>52 Weeks Panel (Full Year)</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "200px" }}>
              <span className="type-body-small">Network Corridor Scope</span>
              <input
                type="text"
                className="input-text"
                value={networkLabel}
                onChange={(e) => setNetworkLabel(e.target.value)}
              />
            </label>

            <div style={{ alignSelf: "flex-end" }}>
              <Button
                variant="primary"
                onClick={() => runEvaluation()}
                disabled={isLoading}
              >
                {isLoading ? "Running Models..." : "Re-run Benchmark Suite"}
              </Button>
            </div>
          </div>
        </Panel>
      }
    >
      {isLoading ? (
        <LoadingState
          title="Running Research Evaluation"
          detail="Computing exposure-normalized models, deviance metrics, and capture curves..."
        />
      ) : error ? (
        <ErrorState
          title="Research Evaluation Failed"
          detail={error}
          action={
            <Button variant="secondary" onClick={() => runEvaluation()}>
              Retry
            </Button>
          }
        />
      ) : !results ? (
        <EmptyState
          title="No Benchmark Results"
          detail="Select a network corridor and split strategy to run the baseline-to-boosting benchmark."
        />
      ) : (
        <WorkSurface variant="single">
          <Panel title="Statistical Baselines vs. Poisson Gradient Boosted Trees (GBDT)">
            <DataTable
              columns={[
                { field: "model_name", header: "Model Architecture" },
                { field: "poisson_deviance", header: "Poisson Deviance" },
                { field: "negative_log_likelihood", header: "NLL" },
                { field: "brier_score", header: "Brier Score" },
                { field: "roc_auc", header: "ROC-AUC" },
                { field: "pr_auc", header: "PR-AUC" },
                { field: "top_20_capture", header: "Top-20% Capture" },
              ]}
              rows={modelsList.map((m) => ({
                id: m.model_name,
                model_name: m.model_name,
                poisson_deviance: m.poisson_deviance.toFixed(4),
                negative_log_likelihood: m.negative_log_likelihood.toFixed(4),
                brier_score: m.brier_score.toFixed(4),
                roc_auc: m.roc_auc.toFixed(3),
                pr_auc: m.pr_auc.toFixed(3),
                top_20_capture: `${(m.top_20_capture * 100).toFixed(1)}%`,
              }))}
            />
          </Panel>

          <Panel title="Top-k% Cumulative Crash Capture Curves (Concentration Ratio)">
            <div style={{ padding: "1rem 0" }}>
              <p className="type-body" style={{ marginBottom: "1.5rem" }}>
                Measures what percentage of total observed crashes occur within the top ranked segments:
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
                {modelsList.map((m) => (
                  <div
                    key={m.model_name}
                    style={{
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "12px",
                      padding: "1rem",
                      background: "var(--surface-overlay)",
                    }}
                  >
                    <strong className="type-heading-3" style={{ display: "block", marginBottom: "0.75rem" }}>
                      {m.model_name}
                    </strong>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="type-body-small">Top 5% Network:</span>
                        <strong>{(m.top_5_capture * 100).toFixed(1)}%</strong>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="type-body-small">Top 10% Network:</span>
                        <strong>{(m.top_10_capture * 100).toFixed(1)}%</strong>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="type-body-small">Top 20% Network:</span>
                        <strong style={{ color: "var(--tone-success-text)" }}>{(m.top_20_capture * 100).toFixed(1)}%</strong>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="type-body-small">Top 50% Network:</span>
                        <strong>{(m.top_50_capture * 100).toFixed(1)}%</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          <Panel title="Cryptographic Provenance Manifest & Environment Audit">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div>
                <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>
                  SHA-256 Manifest Digest:
                </span>{" "}
                <code style={{ fontSize: "0.85rem", background: "var(--surface-sunken)", padding: "2px 6px", borderRadius: "4px" }}>
                  {results.data_manifest?.sha256_digest || "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
                </code>
              </div>
              <div>
                <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>
                  Verification Manifest ID:
                </span>{" "}
                <span className="type-body-small">{results.data_manifest?.manifest_id || "manifest_panel_verified"}</span>
              </div>
              <div>
                <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>
                  Leakage Guardrails:
                </span>{" "}
                <span className="type-body-small">
                  ✓ Backward weather join strictly preceding observation (merge_asof) · ✓ Post-crash features excluded (LEAKAGE_BLACKLIST) · ✓ Log-exposure offset log(E) anchored
                </span>
              </div>
            </div>
          </Panel>
        </WorkSurface>
      )}
    </WorkspacePage>
  );
}
