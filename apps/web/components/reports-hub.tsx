"use client";

import { apiFetch } from "@/lib/demo-api";

import { useEffect, useMemo, useState } from "react";

import { usePlatformSession } from "@/components/session-provider";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Eyebrow,
  FilterBar,
  LoadingState,
  MetricCard,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { RefreshIcon } from "@/components/icons";
import { KpiStrip, WorkspacePage } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";
import { canAccessArea } from "@/lib/platform-shell";
import {
  buildReportGenerationPayload,
  buildReportLifecyclePayload,
  defaultVisibilityForReport,
  reportLifecycleActionLabel,
} from "@/lib/reports";

const API_BASE_URL = getClientApiBaseUrl();

type ReportTemplate = {
  report_type: string;
  label: string;
  audience: string;
  description: string;
  required_role: string;
  supported_formats: string[];
  default_format: string;
};

type ExecutiveOverview = {
  city: { city_key?: string | null; display_name?: string | null; prediction_run_label?: string | null };
  kpis: Record<string, string | number | null>;
  budget_impact: Record<string, string | number | null>;
  priority_areas: {
    top_corridors: Array<Record<string, string | number | null>>;
    top_actions: Array<Record<string, string | number | null>>;
  };
  reporting_context: {
    signal_summary?: Record<string, string | number | null>;
  };
};

type ReportHistoryRow = {
  report_id: string;
  title: string;
  report_type: string;
  status: string;
  visibility_tier: string;
  output_format: string;
  city_key?: string | null;
  download_state: string;
  publication_state?: string | null;
  review_state?: string | null;
  lifecycle_actions?: string[];
  created_at?: string | null;
  generated_at?: string | null;
  published_at?: string | null;
};

type ReportingOverviewPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  selected_city_key: string;
  city_catalog: Array<{
    city_key: string;
    display_name: string;
    prediction_run_label: string;
    occurred_years: number[];
  }>;
  executive_overview: ExecutiveOverview;
  report_templates: ReportTemplate[];
  report_history: {
    rows: ReportHistoryRow[];
  };
};

type DownloadPayload = {
  access: {
    download_url: string;
  };
};

type LifecyclePayload = {
  report?: ReportHistoryRow;
};

type GenerateReportPayload = {
  dispatch_mode: string;
  persistence_mode?: string;
  report?: {
    status?: string;
    download_state?: string;
  };
};

type PublicReportsPayload = {
  api_version: string;
  contract_version: string;
  city_key: string;
  availability: string;
  rows: ReportHistoryRow[];
};

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(input, {
    cache: "no-store",
    credentials: "include",
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${input} -> HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function formatValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return value;
}

function reportAccessGranted(requiredRole: string, roles: string[]): boolean {
  if (requiredRole === "municipality_viewer") return roles.length > 0 && roles.some((role) => role !== "public");
  if (requiredRole === "analyst") return roles.includes("analyst") || roles.includes("traffic_engineer") || roles.includes("admin") || roles.includes("super_admin");
  if (requiredRole === "data_operator") return roles.includes("data_operator") || roles.includes("admin") || roles.includes("super_admin");
  if (requiredRole === "admin") return roles.includes("admin") || roles.includes("super_admin");
  return roles.includes(requiredRole);
}

function reportLifecycleAllowed(action: string, roles: string[]): boolean {
  if (["publish", "unpublish", "archive"].includes(action)) {
    return roles.includes("admin") || roles.includes("super_admin");
  }
  if (["review", "reopen", "fail"].includes(action)) {
    return roles.includes("analyst") || roles.includes("data_operator") || roles.includes("admin") || roles.includes("super_admin");
  }
  return false;
}

export function ReportsHub() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId;
  const defaultCityKey = session.selectedMunicipalityId ?? null;
  const hasInternalAccess = canAccessArea(session, "internal");

  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(defaultCityKey);
  const [payload, setPayload] = useState<ReportingOverviewPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formatByReport, setFormatByReport] = useState<Record<string, string>>({});
  const [visibilityByReport, setVisibilityByReport] = useState<Record<string, string>>({});
  const [actionNote, setActionNote] = useState<string | null>(null);
  const [pendingReportType, setPendingReportType] = useState<string | null>(null);
  const [pendingLifecycleReportId, setPendingLifecycleReportId] = useState<string | null>(null);
  // Bumped by the error-state retry to re-run the overview fetch (#258).
  const [reloadToken, setReloadToken] = useState(0);

  const [isDossierGenerating, setIsDossierGenerating] = useState<boolean>(false);
  const [dossierResult, setDossierResult] = useState<{
    executive_kpis?: Record<string, string | number>;
    markdown_dossier?: string;
    pdf_base64?: string;
    data_manifest?: {
      manifest_id: string;
      sha256_digest: string;
      timestamp: string;
      record_counts: Record<string, number>;
    };
  } | null>(null);

  async function onGenerateMinisterialDossier() {
    if (!organizationId) return;
    setIsDossierGenerating(true);
    setActionNote(null);
    try {
      const cityName = payload?.executive_overview.city.display_name || selectedCityKey || "Metropolitan Area";
      const res = await apiFetch(`${API_BASE_URL}/v1/reporting/ministerial-dossier`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          organization_id: organizationId,
          network_label: `${selectedCityKey || "metropolitan"}_safety_dossier`,
          jurisdiction_name: `${cityName} Metropolitan Area`,
          ministry_authority: "Department of Transportation / Road Safety Authority",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setDossierResult(data);
      setActionNote("Safety Dossier generated successfully with vector PDF/A.");
    } catch (err) {
      setActionNote(err instanceof Error ? err.message : "Failed to compile safety dossier");
    } finally {
      setIsDossierGenerating(false);
    }
  }

  function downloadDossierPdf() {
    if (!dossierResult?.pdf_base64) return;
    const binary = atob(dossierResult.pdf_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedCityKey || "metropolitan"}_safety_dossier.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadDossierMarkdown() {
    if (!dossierResult?.markdown_dossier) return;
    const blob = new Blob([dossierResult.markdown_dossier], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedCityKey || "metropolitan"}_safety_dossier.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    if (!selectedCityKey && defaultCityKey) {
      setSelectedCityKey(defaultCityKey);
    }
  }, [defaultCityKey, selectedCityKey]);

  useEffect(() => {
    if (!organizationId || !hasInternalAccess) {
      setPayload(null);
      return;
    }
    const cityKey = selectedCityKey ?? defaultCityKey;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    const url = new URL(`${API_BASE_URL}/v1/reports/overview`);
    url.searchParams.set("organization_id", organizationId);
    if (cityKey) url.searchParams.set("city_key", cityKey);
    fetchJson<ReportingOverviewPayload>(url.toString())
      .then((nextPayload) => {
        if (cancelled) return;
        setPayload(nextPayload);
        setSelectedCityKey(nextPayload.selected_city_key);
        setFormatByReport((current) => {
          const updated = { ...current };
          for (const template of nextPayload.report_templates) {
            updated[template.report_type] = updated[template.report_type] ?? template.default_format;
          }
          return updated;
        });
        setVisibilityByReport((current) => {
          const updated = { ...current };
          for (const template of nextPayload.report_templates) {
            updated[template.report_type] = updated[template.report_type] ?? defaultVisibilityForReport(template.report_type);
          }
          return updated;
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [defaultCityKey, hasInternalAccess, organizationId, selectedCityKey, reloadToken]);

  const corridorRows = useMemo(() => {
    const rows = payload?.executive_overview.priority_areas.top_corridors ?? [];
    return rows.map((row) => [
      formatValue(row.corridor_label),
      formatValue(row.predicted_crash_total),
      formatValue(row.max_public_score_index),
      formatValue(row.lead_segment),
    ]);
  }, [payload]);

  const actionRows = useMemo(() => {
    const rows = payload?.executive_overview.priority_areas.top_actions ?? [];
    return rows.map((row) => [
      formatValue(row.priority),
      formatValue(row.title),
      formatValue(row.rationale),
    ]);
  }, [payload]);

  const historyRows = useMemo(() => {
    const rows = payload?.report_history.rows ?? [];
    return rows.map((row) => [
      row.title,
      row.report_type,
      `${row.output_format} · ${row.visibility_tier}`,
      `${row.status} · ${row.review_state ?? "review"}`,
      `${row.publication_state ?? "not_published"} · ${row.download_state}`,
      row.published_at ?? row.generated_at ?? row.created_at ?? "—",
    ]);
  }, [payload]);

  async function refreshReports(cityKey = selectedCityKey) {
    if (!organizationId || !cityKey) return;
    const url = new URL(`${API_BASE_URL}/v1/reports/overview`);
    url.searchParams.set("organization_id", organizationId);
    url.searchParams.set("city_key", cityKey);
    const refreshed = await fetchJson<ReportingOverviewPayload>(url.toString());
    setPayload(refreshed);
  }

  async function onGenerateReport(template: ReportTemplate) {
    if (!organizationId || !selectedCityKey) return;
    setPendingReportType(template.report_type);
    setActionNote(null);
    try {
      const response = await fetchJson<GenerateReportPayload>(`${API_BASE_URL}/v1/reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildReportGenerationPayload({
            organizationId,
            cityKey: selectedCityKey,
            reportType: template.report_type,
            outputFormat: formatByReport[template.report_type] ?? template.default_format,
            visibilityTier: visibilityByReport[template.report_type] ?? defaultVisibilityForReport(template.report_type),
          }),
        ),
      });
      if (response.persistence_mode === "transient" || response.report?.download_state === "not_persisted") {
        setActionNote(`Generated ${template.label.toLowerCase()} locally without report-history persistence.`);
      } else if (response.dispatch_mode === "inline") {
        setActionNote(`Generated ${template.label.toLowerCase()}.`);
      } else {
        setActionNote(`Queued ${template.label.toLowerCase()}.`);
      }
      await refreshReports(selectedCityKey);
    } catch (err) {
      setActionNote(err instanceof Error ? err.message : "Could not generate report");
    } finally {
      setPendingReportType(null);
    }
  }

  async function onLifecycle(report: ReportHistoryRow, action: string) {
    if (!organizationId) return;
    setPendingLifecycleReportId(report.report_id);
    setActionNote(null);
    try {
      await fetchJson<LifecyclePayload>(`${API_BASE_URL}/v1/reports/${encodeURIComponent(report.report_id)}/lifecycle`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildReportLifecyclePayload({
            organizationId,
            action,
            visibilityTier: action === "publish" ? "public" : undefined,
            note: `${reportLifecycleActionLabel(action)} from reports workspace`,
          }),
        ),
      });
      setActionNote(`${reportLifecycleActionLabel(action)} completed for ${report.title}.`);
      await refreshReports();
    } catch (err) {
      setActionNote(err instanceof Error ? err.message : "Could not update report lifecycle");
    } finally {
      setPendingLifecycleReportId(null);
    }
  }

  async function onDownload(reportId: string) {
    if (!organizationId) return;
    try {
      const url = new URL(`${API_BASE_URL}/v1/reports/${encodeURIComponent(reportId)}/download`);
      url.searchParams.set("organization_id", organizationId);
      const response = await fetchJson<DownloadPayload>(url.toString());
      window.open(response.access.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setActionNote(err instanceof Error ? err.message : "Could not open download");
    }
  }

  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Reports"
          title="Generate, review, download, and publish road-safety reports."
          description="Choose a city, select the report audience and format, then use the history table to verify what is ready for internal review or public publication."
          meta={
            <>
              <StatusPill label="Report generation" tone="success" />
              <StatusPill label="Governance-aware publishing" tone="warning" />
            </>
          }
        />
      }
    >

      {!organizationId && (
        <EmptyState
          title="Choose an organization"
          detail="Use the workspace switcher to select the organization whose reports should be generated or reviewed."
        />
      )}

      {organizationId && (
        <>
          <FilterBar
            summary={
              <>
                <span>City selection updates KPIs, report templates, and export history together.</span>
              </>
            }
          >
            <label>
              <span>Reporting city</span>
              <select
                value={selectedCityKey ?? ""}
                onChange={(event) => setSelectedCityKey(event.target.value || null)}
              >
                {(payload?.city_catalog ?? []).map((city) => (
                  <option key={city.city_key} value={city.city_key}>
                    {city.display_name}
                  </option>
                ))}
              </select>
            </label>
          </FilterBar>

          <KpiStrip>
            <MetricCard
              label="Predicted crash burden"
              value={formatValue(payload?.executive_overview.kpis.predicted_crash_total ?? (isLoading ? "…" : "—"))}
              footnote={payload?.executive_overview.city.display_name ?? "Selected city"}
              tone="slate"
            />
            <MetricCard
              label="Very-high-risk tiles"
              value={formatValue(payload?.executive_overview.kpis.very_high_risk_tiles ?? (isLoading ? "…" : "—"))}
              footnote="Published tile layer"
              tone="rust"
            />
            <MetricCard
              label="Portfolio benefit"
              value={formatValue(payload?.executive_overview.kpis.expected_portfolio_reduction ?? (isLoading ? "…" : "—"))}
              footnote="Expected crash reduction"
              tone="teal"
            />
            <MetricCard
              label="Model confidence"
              value={formatValue(payload?.executive_overview.kpis.model_confidence ?? (isLoading ? "…" : "—"))}
              footnote="Transferability-derived label"
              tone="slate"
            />
          </KpiStrip>

          {isLoading ? (
            <LoadingState
              title="Loading report center"
              detail="Preparing KPIs, report templates, priority corridors, and export history."
            />
          ) : null}

          {error ? (
            <ErrorState
              action={
                <Button
                  icon={<RefreshIcon size={16} />}
                  onClick={() => setReloadToken((token) => token + 1)}
                  variant="secondary"
                >
                  Retry
                </Button>
              }
              detail={`The reporting center could not load this city. ${error}`}
            />
          ) : null}

          {actionNote && (
            <Panel title="Report action" detail={actionNote} accent="teal">
              <p>The history table below refreshes after each generation request.</p>
            </Panel>
          )}

          <Panel
            title="Executive budget impact"
            detail="Top portfolio recommendation and current signal-readiness context."
            accent="slate"
          >
            <DataTable
              columns={["Portfolio", "Crash reduction", "Relative reduction", "Signal coverage"]}
              rows={[
                [
                  formatValue(payload?.executive_overview.budget_impact.recommended_portfolio_title),
                  formatValue(payload?.executive_overview.budget_impact.expected_crash_reduction),
                  formatValue(payload?.executive_overview.budget_impact.expected_relative_reduction),
                  formatValue(payload?.executive_overview.reporting_context.signal_summary?.movements_with_provider_data),
                ],
              ]}
            />
          </Panel>

          <Panel
            title="Sovereign Ministerial Safety Dossier"
            detail="Native vector PDF/A compilation and Markdown briefing with SHA-256 cryptographic provenance."
            accent="teal"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <p className="type-body">
                Compiles multi-tier jurisdictional metrics, AASHTO HSM Empirical Bayes high-risk corridors, iRAP 1–5 Star Ratings, C-ITS V2X dispatch plans, and EU AI Act compliance evidence into a formal executive dossier.
              </p>
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                <Button
                  variant="primary"
                  onClick={onGenerateMinisterialDossier}
                  disabled={isDossierGenerating}
                >
                  {isDossierGenerating ? "Compiling Vector Dossier..." : "Compile Sovereign Ministerial Dossier"}
                </Button>
                {dossierResult && (
                  <>
                    <Button variant="secondary" onClick={downloadDossierPdf}>
                      Download Official PDF/A (.pdf)
                    </Button>
                    <Button variant="tertiary" onClick={downloadDossierMarkdown}>
                      Download Markdown Brief (.md)
                    </Button>
                  </>
                )}
              </div>

              {dossierResult && (
                <div style={{ marginTop: "0.5rem", padding: "1rem", borderRadius: "8px", background: "var(--surface-overlay)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", marginBottom: "1rem" }}>
                    <div>
                      <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>High-Risk Corridors</span>
                      <div className="type-heading-3">{String(dossierResult.executive_kpis?.total_high_risk_corridors ?? "—")}</div>
                    </div>
                    <div>
                      <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>Expected Crash Reduction</span>
                      <div className="type-heading-3">{String(dossierResult.executive_kpis?.expected_annual_crash_reduction ?? "—")}</div>
                    </div>
                    <div>
                      <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>CIP Capital Budget</span>
                      <div className="type-heading-3">{String(dossierResult.executive_kpis?.total_capital_investment_eur ?? "—")}</div>
                    </div>
                    <div>
                      <span className="type-body-small" style={{ color: "var(--text-secondary)" }}>Target 4 Compliance</span>
                      <div className="type-heading-3">{String(dossierResult.executive_kpis?.target_4_star_compliance ?? "—")}</div>
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem" }}>
                    <div className="type-body-small">
                      <strong style={{ color: "var(--tone-success-text)" }}>✓ Cryptographic SHA-256 Provenance Manifest:</strong>{" "}
                      <code style={{ fontSize: "0.8rem", background: "var(--surface-sunken)", padding: "2px 6px", borderRadius: "4px" }}>
                        {dossierResult.data_manifest?.sha256_digest || "—"}
                      </code>
                    </div>
                    <div className="type-body-small" style={{ color: "var(--text-secondary)" }}>
                      Manifest ID: {dossierResult.data_manifest?.manifest_id || "—"} · Standard: ISO 19005-1 / PDF/A-1b Vector Format
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Panel>

          <div className="profile-grid">
            {(payload?.report_templates ?? []).map((template) => {
              const allowed = reportAccessGranted(template.required_role, session.roles);
              return (
                <Panel
                  key={template.report_type}
                  title={template.label}
                  detail={template.description}
                  accent={template.audience === "executive" ? "teal" : "rust"}
                >
                  <div className="chip-row">
                    <StatusPill label={template.audience} tone="neutral" />
                    <StatusPill label={`needs ${template.required_role}`} tone={allowed ? "success" : "warning"} />
                  </div>
                  <label>
                    <span>Format</span>
                    <select
                      value={formatByReport[template.report_type] ?? template.default_format}
                      onChange={(event) =>
                        setFormatByReport((current) => ({
                          ...current,
                          [template.report_type]: event.target.value,
                        }))
                      }
                    >
                      {template.supported_formats.map((format) => (
                        <option key={format} value={format}>
                          {format}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Visibility</span>
                    <select
                      value={visibilityByReport[template.report_type] ?? defaultVisibilityForReport(template.report_type)}
                      onChange={(event) =>
                        setVisibilityByReport((current) => ({
                          ...current,
                          [template.report_type]: event.target.value,
                        }))
                      }
                    >
                      <option value="restricted">restricted</option>
                      <option value="internal">internal</option>
                      <option value="analyst_only">analyst_only</option>
                      {template.report_type === "public_transparency" ? <option value="public">public</option> : null}
                    </select>
                  </label>
                  <div className="hero-actions">
                    <button
                      type="button"
                      className="primary-button"
                      disabled={!allowed || pendingReportType === template.report_type}
                      onClick={() => void onGenerateReport(template)}
                    >
                      {pendingReportType === template.report_type ? "Generating…" : "Generate"}
                    </button>
                  </div>
                </Panel>
              );
            })}
          </div>

          <Panel
            title="Priority corridors"
            detail="Executive view of the highest-risk corridors and their lead segments."
            accent="slate"
          >
            <DataTable
              columns={["Corridor", "Predicted crashes", "Score index", "Lead segment"]}
              rows={corridorRows}
            />
          </Panel>

          <Panel
            title="Recommended actions"
            detail="Top recommended actions from the intervention brief / scenario bundle."
            accent="rust"
          >
            <DataTable columns={["Priority", "Title", "Rationale"]} rows={actionRows} />
          </Panel>

          <Panel
            title="Report history"
            detail="Generated exports, review state, publication tier, and governed download state."
            accent="slate"
          >
            <DataTable columns={["Title", "Type", "Format / Tier", "Lifecycle", "Publication / Download", "Latest"]} rows={historyRows} />
            <div className="hero-actions">
              {(payload?.report_history.rows ?? []).map((row) => (
                <button
                  key={row.report_id}
                  type="button"
                  className="ghost-button"
                  disabled={row.download_state !== "ready"}
                  onClick={() => void onDownload(row.report_id)}
                >
                  {row.download_state === "ready" ? `Download ${row.title}` : `${row.title} pending`}
                </button>
              ))}
            </div>
            <div className="hero-actions">
              {(payload?.report_history.rows ?? []).flatMap((row) =>
                (row.lifecycle_actions ?? []).map((action) => (
                  <button
                    key={`${row.report_id}-${action}`}
                    type="button"
                    className={action === "publish" ? "primary-button" : "ghost-button"}
                    disabled={pendingLifecycleReportId === row.report_id || !reportLifecycleAllowed(action, session.roles)}
                    onClick={() => void onLifecycle(row, action)}
                  >
                    {pendingLifecycleReportId === row.report_id
                      ? "Updating…"
                      : `${reportLifecycleActionLabel(action)} ${row.title}`}
                  </button>
                )),
              )}
            </div>
          </Panel>
        </>
      )}
    </WorkspacePage>
  );
}

export function PublicReportsPanel() {
  const [cities, setCities] = useState<Array<{ city_key: string; display_name: string }>>([]);
  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(null);
  const [payload, setPayload] = useState<PublicReportsPayload | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJson<{ cities: Array<{ city_key: string; display_name: string }> }>(`${API_BASE_URL}/v1/public/cities`)
      .then((response) => {
        if (cancelled) return;
        setCities(response.cities);
        setSelectedCityKey((current) => current ?? response.cities[0]?.city_key ?? null);
      })
      .catch((err) => {
        if (!cancelled) setNote(err instanceof Error ? err.message : "Could not load public city list");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCityKey) return;
    let cancelled = false;
    fetchJson<PublicReportsPayload>(`${API_BASE_URL}/v1/public/cities/${encodeURIComponent(selectedCityKey)}/reports`)
      .then((response) => {
        if (!cancelled) setPayload(response);
      })
      .catch((err) => {
        if (!cancelled) setNote(err instanceof Error ? err.message : "Could not load public reports");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCityKey]);

  async function onPublicDownload(reportId: string) {
    if (!selectedCityKey) return;
    try {
      const response = await fetchJson<DownloadPayload>(
        `${API_BASE_URL}/v1/public/cities/${encodeURIComponent(selectedCityKey)}/reports/${encodeURIComponent(reportId)}/download`,
      );
      window.open(response.access.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Could not open public report");
    }
  }

  const publicRows = (payload?.rows ?? []).map((row) => [
    row.title,
    row.output_format,
    row.status,
    row.published_at ?? row.generated_at ?? "—",
  ]);

  return (
    <Panel
      title="Public reports"
      detail="Published transparency reports available without exposing restricted crash records."
      accent="teal"
    >
      <label>
        <span>City</span>
        <select value={selectedCityKey ?? ""} onChange={(event) => setSelectedCityKey(event.target.value || null)}>
          {cities.map((city) => (
            <option key={city.city_key} value={city.city_key}>
              {city.display_name}
            </option>
          ))}
        </select>
      </label>
      <DataTable columns={["Report", "Format", "Status", "Published"]} rows={publicRows} />
      <div className="hero-actions">
        {(payload?.rows ?? []).map((row) => (
          <button
            key={row.report_id}
            type="button"
            className="ghost-button"
            disabled={row.download_state !== "ready"}
            onClick={() => void onPublicDownload(row.report_id)}
          >
            {row.download_state === "ready" ? `Download ${row.title}` : `${row.title} pending`}
          </button>
        ))}
      </div>
      {note ? <p>{note}</p> : null}
    </Panel>
  );
}
