"use client";

import { apiFetch } from "@/lib/demo-api";

import { useEffect, useMemo, useState } from "react";

import { usePlatformSession } from "@/components/session-provider";
import {
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingState,
  MetricCard,
  NavChip,
  PageHeader,
  Panel,
  StatusPill,
  Stepper,
  WarningState,
} from "@/components/ui";
import { KpiStrip, WorkspacePage } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";
import {
  buildDefaultFieldMapping,
  detectCsvSchema,
  detectJsonSchema,
  detectUploadFormat,
  missingMappedColumns,
  unsupportedSchemaDetection,
  uploadDecisionForStatus,
  uploadLifecycleStep,
  UPLOAD_LIFECYCLE_STEPS,
  type UploadSchemaDetection,
} from "@/lib/upload-center";

const API_BASE_URL = getClientApiBaseUrl();

type UploadCenterSource = {
  source_id: string;
  name: string;
  source_type: string;
  provider_name?: string | null;
  governance_status: string;
  publication_tier: string;
  status: string;
  municipality_id?: string | null;
  required_columns: string[];
  supported_formats: string[];
  upload_enabled: boolean;
  blocked_reason?: string | null;
};

type UploadCenterJob = {
  job_id: string;
  organization_id: string;
  municipality_id?: string | null;
  source_id?: string | null;
  job_type: string;
  status: string;
  source_name?: string | null;
  validation_outcome?: string | null;
  execution_status?: string | null;
  execution_engine?: string | null;
  output_artifact_count?: number | null;
  error_count?: number | null;
  manifest_storage_uri?: string | null;
  error_storage_uri?: string | null;
};

type UploadCenterSnapshot = {
  contract_version: string;
  organization_id: string;
  municipality_id?: string | null;
  supported_formats: string[];
  sources: UploadCenterSource[];
  jobs: UploadCenterJob[];
};

type WorkflowState = {
  can_validate?: boolean;
  can_approve?: boolean;
  can_reject?: boolean;
  can_run?: boolean;
  can_retry?: boolean;
  can_cancel?: boolean;
  required_next_action?: string;
};

type IngestionJobDetail = {
  job_id: string;
  status: string;
  source?: UploadCenterSource | null;
  parameters?: Record<string, unknown>;
  stats?: Record<string, unknown>;
  workflow?: WorkflowState;
  input_storage_uri?: string | null;
  manifest_storage_uri?: string | null;
  error_storage_uri?: string | null;
};

type ManifestPayload = {
  manifest?: {
    governance?: {
      status?: string;
      checks?: Array<{ check: string; status: string; message: string }>;
    };
    schema?: {
      format?: string;
      detected_columns?: string[];
      missing_required_columns?: string[];
      field_mapping?: Record<string, string>;
      delimiter?: string;
    };
    quality?: {
      invalid_coordinate_count?: number;
      duplicate_row_count?: number;
    };
    stats?: {
      validation_status?: string;
      validation_outcome?: string;
      scanned_row_count?: number;
      accepted_preview_rows?: number;
      rejected_preview_rows?: number;
      invalid_coordinate_count?: number;
      duplicate_row_count?: number;
      error_count?: number;
    };
    preview_rows?: Array<{ row_number?: number | null; values?: Record<string, unknown> }>;
  } | null;
};

type ErrorPayload = {
  error_summary?: {
    error_count?: number;
    missing_required_columns?: string[];
    invalid_coordinate_count?: number;
    duplicate_row_count?: number;
  } | null;
  row_errors?: Array<{
    row_number?: number | null;
    error_code?: string;
    message?: string;
    missing_required_columns?: string[];
  }> | null;
};

type LogPayload = {
  log?: {
    log_lines?: string[];
  } | null;
};

function statusTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "validated_ready" || status === "queued" || status === "completed" || status === "approved") {
    return "success";
  }
  if (status === "running") return "info";
  if (
    status === "validated_with_errors" ||
    status === "manual_review_required" ||
    status === "manual_review" ||
    status === "cancelled" ||
    status === "draft"
  ) {
    return "warning";
  }
  if (status === "failed" || status === "validation_failed" || status === "rejected" || status === "blocked") {
    return "danger";
  }
  return "neutral";
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(url, {
    cache: "no-store",
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

function rowsFromPreview(
  rows: Array<{ row_number?: number | null; values?: Record<string, unknown> }>,
): string[][] {
  return rows.slice(0, 8).map((row) => [
    String(row.row_number ?? "n/a"),
    Object.entries(row.values ?? {})
      .slice(0, 6)
      .map(([key, value]) => `${key}: ${String(value ?? "")}`)
      .join(" · "),
  ]);
}

function rowsFromErrors(rows: NonNullable<ErrorPayload["row_errors"]>): string[][] {
  return rows.slice(0, 10).map((row) => [
    String(row.row_number ?? "schema"),
    row.error_code ?? "validation_error",
    row.message ?? "Validation issue",
    row.missing_required_columns?.join(", ") ?? "—",
  ]);
}

function jobRows(jobs: UploadCenterJob[]): string[][] {
  return jobs.slice(0, 10).map((job) => [
    job.source_name ?? job.job_type,
    job.status,
    job.execution_status ?? job.validation_outcome ?? "—",
    job.output_artifact_count == null ? "—" : String(job.output_artifact_count),
    job.error_count == null ? "—" : String(job.error_count),
  ]);
}

export function UploadCenter() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId;
  const municipalityId = session.selectedMunicipalityId;
  const [snapshot, setSnapshot] = useState<UploadCenterSnapshot | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [schema, setSchema] = useState<UploadSchemaDetection | null>(null);
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({});
  const [activeJob, setActiveJob] = useState<IngestionJobDetail | null>(null);
  const [manifest, setManifest] = useState<ManifestPayload | null>(null);
  const [errors, setErrors] = useState<ErrorPayload | null>(null);
  const [logs, setLogs] = useState<LogPayload | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSource = useMemo(
    () => snapshot?.sources.find((source) => source.source_id === selectedSourceId) ?? null,
    [selectedSourceId, snapshot],
  );
  const missingRequiredMappings = useMemo(
    () => missingMappedColumns(selectedSource?.required_columns ?? [], fieldMapping),
    [fieldMapping, selectedSource],
  );

  async function refreshSnapshot() {
    if (!organizationId) {
      setSnapshot(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_BASE_URL}/v1/ingestion-jobs/upload-center`);
      url.searchParams.set("organization_id", organizationId);
      if (municipalityId) {
        url.searchParams.set("municipality_id", municipalityId);
      }
      const payload = await fetchJson<UploadCenterSnapshot>(url.toString());
      setSnapshot(payload);
      setSelectedSourceId((current) => {
        if (current && payload.sources.some((source) => source.source_id === current)) {
          return current;
        }
        return payload.sources.find((source) => source.upload_enabled)?.source_id ?? payload.sources[0]?.source_id ?? "";
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload center unavailable");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshSnapshot();
  }, [organizationId, municipalityId]);

  useEffect(() => {
    if (!selectedSource || !schema) {
      setFieldMapping({});
      return;
    }
    setFieldMapping(buildDefaultFieldMapping(selectedSource.required_columns, schema.detectedColumns));
  }, [schema, selectedSource]);

  async function loadJobArtifacts(job: IngestionJobDetail) {
    if (!organizationId) return;
    setManifest(null);
    setErrors(null);
    setLogs(null);
    if (job.manifest_storage_uri) {
      const manifestPayload = await fetchJson<ManifestPayload>(
        `${API_BASE_URL}/v1/ingestion-jobs/${job.job_id}/manifest?organization_id=${encodeURIComponent(
          organizationId,
        )}`,
      );
      setManifest(manifestPayload);
    }
    if (job.error_storage_uri) {
      const errorPayload = await fetchJson<ErrorPayload>(
        `${API_BASE_URL}/v1/ingestion-jobs/${job.job_id}/errors?organization_id=${encodeURIComponent(
          organizationId,
        )}`,
      );
      setErrors(errorPayload);
    }
    const logPayload = await fetchJson<LogPayload>(
      `${API_BASE_URL}/v1/ingestion-jobs/${job.job_id}/logs?organization_id=${encodeURIComponent(
        organizationId,
      )}`,
    ).catch(() => null);
    if (logPayload) {
      setLogs(logPayload);
    }
  }

  async function handleFileChange(file: File | null) {
    setSelectedFile(file);
    setSchema(null);
    setManifest(null);
    setErrors(null);
    setLogs(null);
    setActiveJob(null);
    if (!file) return;
    const format = detectUploadFormat(file.name, file.type);
    if (format === "csv") {
      setSchema(detectCsvSchema(await file.text()));
    } else if (format === "json" || format === "geojson") {
      setSchema(detectJsonSchema(await file.text(), format));
    } else {
      setSchema(unsupportedSchemaDetection(format));
    }
  }

  async function registerUploadAndValidate() {
    if (!organizationId || !selectedSource || !selectedFile || !schema) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const registerPayload = await fetchJson<{
        job_id: string;
        upload_url: string;
        input_storage_uri?: string | null;
      }>(`${API_BASE_URL}/v1/ingestion-jobs/uploads`, {
        body: JSON.stringify({
          organization_id: organizationId,
          municipality_id: municipalityId,
          source_id: selectedSource.source_id,
          filename: selectedFile.name,
          content_type: selectedFile.type || undefined,
          parameters: {
            browser_upload_center: true,
            detected_format: schema.format,
            detected_columns: schema.detectedColumns,
            field_mapping: fieldMapping,
          },
        }),
        method: "POST",
      });

      const uploadResponse = await apiFetch(registerPayload.upload_url, {
        body: selectedFile,
        headers: selectedFile.type ? { "content-type": selectedFile.type } : undefined,
        method: "PUT",
      });
      if (!uploadResponse.ok) {
        throw new Error(`Object-storage upload failed (${uploadResponse.status}).`);
      }

      const validatePayload = await fetchJson<{ job: IngestionJobDetail }>(
        `${API_BASE_URL}/v1/ingestion-jobs/${registerPayload.job_id}/validate`,
        {
          body: JSON.stringify({ organization_id: organizationId }),
          method: "POST",
        },
      );
      setActiveJob(validatePayload.job);
      await loadJobArtifacts(validatePayload.job);
      await refreshSnapshot();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload validation failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function loadRecentJob(jobId: string) {
    if (!organizationId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const detail = await fetchJson<{ job: IngestionJobDetail }>(
        `${API_BASE_URL}/v1/ingestion-jobs/${jobId}?organization_id=${encodeURIComponent(organizationId)}`,
      );
      setActiveJob(detail.job);
      await loadJobArtifacts(detail.job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load ingestion job");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitDecision(decision: "approve" | "reject") {
    if (!organizationId || !activeJob) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await fetchJson<{ job: IngestionJobDetail }>(
        `${API_BASE_URL}/v1/ingestion-jobs/${activeJob.job_id}/${decision}`,
        {
          body: JSON.stringify({
            organization_id: organizationId,
            decision_note: decisionNote || undefined,
          }),
          method: "POST",
        },
      );
      setActiveJob(payload.job);
      await refreshSnapshot();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${decision} ingestion job`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runIngestionExecution(dispatchMode: "auto" | "inline" = "auto") {
    if (!organizationId || !activeJob) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await fetchJson<{ job: IngestionJobDetail }>(
        `${API_BASE_URL}/v1/ingestion-jobs/${activeJob.job_id}/run`,
        {
          body: JSON.stringify({
            organization_id: organizationId,
            dispatch_mode: dispatchMode,
          }),
          method: "POST",
        },
      );
      setActiveJob(payload.job);
      await loadJobArtifacts(payload.job);
      await refreshSnapshot();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run ingestion worker");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitExecutionAction(action: "retry" | "cancel") {
    if (!organizationId || !activeJob) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await fetchJson<{ job: IngestionJobDetail }>(
        `${API_BASE_URL}/v1/ingestion-jobs/${activeJob.job_id}/${action}`,
        {
          body: JSON.stringify({
            organization_id: organizationId,
            decision_note: decisionNote || undefined,
          }),
          method: "POST",
        },
      );
      setActiveJob(payload.job);
      await loadJobArtifacts(payload.job);
      await refreshSnapshot();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${action} ingestion job`);
    } finally {
      setIsSubmitting(false);
    }
  }

  const fallbackDecision = uploadDecisionForStatus(activeJob?.status ?? "");
  const canRunUpload =
    Boolean(selectedFile && schema?.isSupported && selectedSource?.upload_enabled) &&
    (schema?.requiresManualReview || missingRequiredMappings.length === 0);
  const manifestStats = manifest?.manifest?.stats;
  const manifestSchema = manifest?.manifest?.schema;
  const quality = manifest?.manifest?.quality;

  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Upload center"
          title="Register, validate, review, and approve governed municipal data uploads."
          description="Data operators can select a governed source, map incoming fields, upload to object storage, validate evidence, approve execution, and run or retry the ingestion worker."
          actions={
            <button className="ghost-button" onClick={() => void refreshSnapshot()} type="button">
              Refresh upload center
            </button>
          }
          meta={
            <>
              <StatusPill label="Data-operator workflow" tone="success" />
              <StatusPill label="Governance gated" tone="warning" />
              <NavChip>CSV · GeoJSON · JSON · ZIP</NavChip>
            </>
          }
        />
      }
      kpis={
        <KpiStrip>
          <MetricCard label="Sources" value={snapshot?.sources.length ?? 0} footnote="Governed upload targets" />
          <MetricCard
            label="Recent jobs"
            value={snapshot?.jobs.length ?? 0}
            footnote="Latest validation and decision states"
            tone="teal"
          />
          <MetricCard
            label="Accepted rows"
            value={manifestStats?.accepted_preview_rows ?? "n/a"}
            footnote="Current validation preview"
          />
          <MetricCard
            label="Rejected rows"
            value={manifestStats?.rejected_preview_rows ?? "n/a"}
            footnote="Schema, row, coordinate, or duplicate issues"
            tone="rust"
          />
        </KpiStrip>
      }
    >
      {!organizationId ? (
        <EmptyState
          title="Choose an organization"
          detail="Use the workspace selector before registering uploads or reviewing ingestion jobs."
        />
      ) : null}

      {isLoading ? (
        <LoadingState
          title="Loading upload center"
          detail="Fetching governed sources and recent ingestion jobs for this organization."
        />
      ) : null}

      {error ? <ErrorState detail={error} /> : null}

      {activeJob ? (
        <Panel
          title="Ingestion lifecycle"
          detail="Where the active upload sits in the governed Upload → Validate → Approve → Run → Complete flow."
          accent="slate"
        >
          <div className="chip-row">
            <StatusPill label={`status: ${activeJob.status}`} tone={statusTone(activeJob.status)} />
            {activeJob.job_id ? <NavChip>{activeJob.job_id}</NavChip> : null}
            {fallbackDecision.requiredNextAction ? (
              <NavChip>next: {fallbackDecision.requiredNextAction.replace(/_/g, " ")}</NavChip>
            ) : null}
          </div>
          <Stepper steps={UPLOAD_LIFECYCLE_STEPS} current={uploadLifecycleStep(activeJob.status)} />
        </Panel>
      ) : null}

      <Panel
        title="1. Select source and file"
        detail="The source controls required fields, publication tier, governance checks, and validation limits."
        accent="teal"
      >
        <FilterBar
          summary={
            selectedSource ? (
              <>
                <StatusPill
                  label={`governance: ${selectedSource.governance_status}`}
                  tone={statusTone(selectedSource.governance_status)}
                />
                <StatusPill
                  label={`tier: ${selectedSource.publication_tier}`}
                  tone={selectedSource.publication_tier === "public" ? "success" : "warning"}
                />
                <NavChip>{selectedSource.source_type}</NavChip>
              </>
            ) : null
          }
        >
          <label>
            <span>Data source</span>
            <select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
              {(snapshot?.sources ?? []).map((source) => (
                <option key={source.source_id} value={source.source_id}>
                  {source.name} · {source.source_type}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Upload file</span>
            <input
              className="file-input"
              onChange={(event) => void handleFileChange(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>
        </FilterBar>

        {selectedSource?.blocked_reason ? (
          <WarningState title="Source requires attention" detail={selectedSource.blocked_reason} />
        ) : null}

        {schema ? (
          <div className="upload-schema-card">
            <div>
              <strong>{schema.format.toUpperCase()} detection</strong>
              <p>{schema.message}</p>
            </div>
            <div className="chip-row">
              <StatusPill label={schema.isSupported ? "Supported" : "Unsupported"} tone={schema.isSupported ? "success" : "danger"} />
              {schema.requiresManualReview ? <StatusPill label="Manual review required" tone="warning" /> : null}
              {schema.delimiter ? <NavChip>delimiter: {schema.delimiter === "\t" ? "tab" : schema.delimiter}</NavChip> : null}
            </div>
          </div>
        ) : null}
      </Panel>

      <Panel
        title="2. Map schema fields"
        detail="Required canonical fields can be mapped to source-specific incoming columns before validation."
        accent="slate"
      >
        {selectedSource && selectedSource.required_columns.length > 0 && schema?.detectedColumns.length ? (
          <div className="mapping-grid">
            {selectedSource.required_columns.map((column) => (
              <label key={column}>
                <span>{column}</span>
                <select
                  value={fieldMapping[column] ?? ""}
                  onChange={(event) =>
                    setFieldMapping((current) => ({ ...current, [column]: event.target.value }))
                  }
                >
                  <option value="">Not mapped</option>
                  {schema.detectedColumns.map((detectedColumn) => (
                    <option key={detectedColumn} value={detectedColumn}>
                      {detectedColumn}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Schema mapping will appear after file selection"
            detail="CSV, JSON, and GeoJSON uploads expose detected fields. ZIP archives are routed to manual validation review."
          />
        )}
        {missingRequiredMappings.length > 0 && !schema?.requiresManualReview ? (
          <WarningState
            title="Required mappings missing"
            detail={`Map these fields before upload validation: ${missingRequiredMappings.join(", ")}.`}
          />
        ) : null}
        <div className="upload-actions">
          <button
            className="primary-button"
            disabled={!canRunUpload || isSubmitting}
            onClick={() => void registerUploadAndValidate()}
            type="button"
          >
            Register, upload, and validate
          </button>
          <small>
            The browser uploads the selected file to the presigned object-storage URL before the API
            validates the stored payload.
          </small>
        </div>
      </Panel>

      <div className="content-grid">
        <Panel
          title="Recent ingestion jobs"
          detail="Open a job to inspect manifest, errors, logs, and decision state."
          accent="rust"
        >
          <DataTable
            columns={["Source", "Status", "Outcome", "Outputs", "Errors"]}
            rows={jobRows(snapshot?.jobs ?? [])}
          />
          <div className="recent-job-buttons">
            {(snapshot?.jobs ?? []).slice(0, 8).map((job) => (
              <button
                className="ghost-button"
                key={job.job_id}
                onClick={() => void loadRecentJob(job.job_id)}
                type="button"
              >
                Open {job.source_name ?? job.job_type}
              </button>
            ))}
          </div>
        </Panel>

        <Panel
          title="Validation and execution"
          detail="Approve clean or reviewed jobs, then run the worker or manage retry/cancel actions."
          accent="teal"
        >
          {activeJob ? (
            <div className="decision-stack">
              <div className="chip-row">
                <StatusPill label={activeJob.status} tone={statusTone(activeJob.status)} />
                <NavChip>{activeJob.workflow?.required_next_action ?? fallbackDecision.requiredNextAction}</NavChip>
              </div>
              <label>
                <span>Decision note</span>
                <textarea
                  onChange={(event) => setDecisionNote(event.target.value)}
                  placeholder="Optional reviewer note for audit and handoff."
                  value={decisionNote}
                />
              </label>
              <div className="hero-actions">
                <button
                  className="primary-button"
                  disabled={!(activeJob.workflow?.can_approve ?? fallbackDecision.canApprove) || isSubmitting}
                  onClick={() => void submitDecision("approve")}
                  type="button"
                >
                  Approve for queue
                </button>
                <button
                  className="ghost-button"
                  disabled={!(activeJob.workflow?.can_reject ?? fallbackDecision.canReject) || isSubmitting}
                  onClick={() => void submitDecision("reject")}
                  type="button"
                >
                  Reject job
                </button>
              </div>
              <div className="hero-actions">
                <button
                  className="primary-button"
                  disabled={!(activeJob.workflow?.can_run ?? fallbackDecision.canRun) || isSubmitting}
                  onClick={() => void runIngestionExecution("auto")}
                  type="button"
                >
                  Run ingestion worker
                </button>
                <button
                  className="ghost-button"
                  disabled={!(activeJob.workflow?.can_retry ?? fallbackDecision.canRetry) || isSubmitting}
                  onClick={() => void submitExecutionAction("retry")}
                  type="button"
                >
                  Retry job
                </button>
                <button
                  className="ghost-button"
                  disabled={!(activeJob.workflow?.can_cancel ?? fallbackDecision.canCancel) || isSubmitting}
                  onClick={() => void submitExecutionAction("cancel")}
                  type="button"
                >
                  Cancel job
                </button>
              </div>
            </div>
          ) : (
            <EmptyState
              title="No validation selected"
              detail="Run a new upload validation or open a recent job to review operator actions."
            />
          )}
        </Panel>
      </div>

      <Panel
        title="Validation results"
        detail="Review schema, governance, row errors, generated manifest evidence, and logs before approving."
        accent="slate"
      >
        <div className="metrics-grid">
          <MetricCard label="Scanned rows" value={manifestStats?.scanned_row_count ?? "n/a"} />
          <MetricCard label="Errors" value={manifestStats?.error_count ?? errors?.error_summary?.error_count ?? "n/a"} tone="rust" />
          <MetricCard
            label="Invalid coordinates"
            value={quality?.invalid_coordinate_count ?? manifestStats?.invalid_coordinate_count ?? "n/a"}
          />
          <MetricCard
            label="Duplicates"
            value={quality?.duplicate_row_count ?? manifestStats?.duplicate_row_count ?? "n/a"}
          />
        </div>
        <div className="content-grid">
          <Panel title="Governance warnings" detail="Source-rights and publication-tier validation." accent="rust">
            <DataTable
              columns={["Check", "Status", "Message"]}
              rows={(manifest?.manifest?.governance?.checks ?? []).map((check) => [
                check.check,
                check.status,
                check.message,
              ])}
            />
          </Panel>
          <Panel title="Detected schema" detail="Auto-detected fields and required-field mapping." accent="teal">
            <DataTable
              columns={["Item", "Value"]}
              rows={[
                ["Format", manifestSchema?.format ?? schema?.format ?? "n/a"],
                ["Detected columns", (manifestSchema?.detected_columns ?? schema?.detectedColumns ?? []).join(", ") || "—"],
                [
                  "Missing columns",
                  (manifestSchema?.missing_required_columns ?? errors?.error_summary?.missing_required_columns ?? []).join(", ") ||
                    "—",
                ],
                [
                  "Field mapping",
                  Object.entries(manifestSchema?.field_mapping ?? fieldMapping)
                    .map(([key, value]) => `${key} -> ${value || "not mapped"}`)
                    .join(", ") || "—",
                ],
              ]}
            />
          </Panel>
        </div>
        <Panel title="Preview rows" detail="First rows returned by validation preview.">
          <DataTable columns={["Row", "Values"]} rows={rowsFromPreview(manifest?.manifest?.preview_rows ?? [])} />
        </Panel>
        <Panel title="Errors and logs" detail="Rejected rows, schema problems, generated manifest status, and validation log lines." accent="rust">
          <DataTable columns={["Row", "Code", "Message", "Columns"]} rows={rowsFromErrors(errors?.row_errors ?? [])} />
          <div className="log-lines">
            {(logs?.log?.log_lines ?? []).map((line) => (
              <code key={line}>{line}</code>
            ))}
          </div>
        </Panel>
      </Panel>
    </WorkspacePage>
  );
}
