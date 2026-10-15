"use client";

import { apiFetch } from "@/lib/demo-api";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { KpiStrip, WorkspacePage } from "@/components/layout";
import { usePlatformSession } from "@/components/session-provider";
import {
  DataTable,
  EmptyState,
  ErrorState,
  GroupedList,
  GroupedRow,
  LoadingState,
  MetricCard,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import {
  MEMBERSHIP_ROLE_OPTIONS,
  MEMBERSHIP_STATUS_OPTIONS,
  MUNICIPALITY_ACCESS_LEVEL_OPTIONS,
  MUNICIPALITY_LINK_STATUS_OPTIONS,
  accessGuardrailWarnings,
  buildMembershipUpdatePayload,
  buildMunicipalityAccessPayload,
  buildUserLinkPayload,
  type MembershipUpdateForm,
  type MunicipalityAccessForm,
  type UserLinkForm,
} from "@/lib/admin-access";
import {
  GOVERNANCE_STATUS_OPTIONS,
  PUBLICATION_TIER_OPTIONS,
  REFRESH_FREQUENCY_OPTIONS,
  SOURCE_STATUS_OPTIONS,
  buildCreateDataSourcePayload,
  buildUpdateDataSourcePayload,
  governanceFormWarnings,
  type DataSourceCreateForm,
  type DataSourcePolicyForm,
} from "@/lib/admin-control";
import { getClientApiBaseUrl } from "@/lib/api-client";

const API_BASE_URL = getClientApiBaseUrl();

const DEFAULT_CREATE_FORM: DataSourceCreateForm = {
  name: "",
  source_type: "crash_feed",
  provider_name: "",
  governance_status: "draft",
  publication_tier: "restricted",
  refresh_frequency: "monthly",
};

const DEFAULT_POLICY_FORM: DataSourcePolicyForm = {
  source_id: "",
  governance_status: "draft",
  publication_tier: "restricted",
  refresh_frequency: "monthly",
  status: "active",
  decision_note: "",
};

const DEFAULT_USER_LINK_FORM: UserLinkForm = {
  subject: "",
  email: "",
  display_name: "",
  role: "analyst",
  status: "active",
  decision_note: "",
};

const DEFAULT_MEMBERSHIP_FORM: MembershipUpdateForm = {
  membership_id: "",
  role: "analyst",
  status: "active",
  decision_note: "",
};

const DEFAULT_MUNICIPALITY_FORM: MunicipalityAccessForm = {
  municipality_id: "",
  access_level: "restricted",
  status: "active",
  decision_note: "",
};

type GovernanceTotals = {
  data_source_count?: number;
  by_governance_status?: Record<string, number>;
  by_publication_tier?: Record<string, number>;
};

type GovernanceRow = {
  id: string;
  name: string;
  source_type: string;
  provider_name?: string | null;
  governance_status: string;
  publication_tier: string;
  refresh_frequency?: string | null;
  municipality_id?: string | null;
  status?: string | null;
  updated_at?: string | null;
};

type IngestionOverview = {
  total: number;
  by_status: Record<string, number>;
  recent_jobs: Array<{
    id: string;
    job_type: string;
    status: string;
    created_at?: string | null;
  }>;
};

type ArtifactOverview = {
  total: number;
  by_publication_tier: Record<string, number>;
};

type AutomationEntry = {
  name: string;
  task?: string | null;
  schedule?: { kind: string; value: number | string } | null;
  options?: Record<string, unknown> | null;
};

type AutomationsRoster = {
  scheduler_available: boolean;
  entries: AutomationEntry[];
  entry_count: number;
};

type MembershipRow = {
  membership_id: string;
  role: string;
  status: string;
  user: {
    subject?: string | null;
    email?: string | null;
    display_name?: string | null;
  };
};

type MunicipalityLinkRow = {
  link_id?: string;
  municipality_id: string;
  access_level: string;
  status: string;
};

type UserRosterTotals = {
  membership_count?: number;
  by_role?: Record<string, number>;
  municipality_link_count?: number;
};

type ControlCenterPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  generated_at: string;
  ingestion_overview: IngestionOverview;
  artifact_overview: ArtifactOverview;
  governance_matrix: {
    rows: GovernanceRow[];
    totals: GovernanceTotals;
  };
  automations: AutomationsRoster;
  user_roster: {
    totals: UserRosterTotals;
    memberships: MembershipRow[];
    municipality_links: MunicipalityLinkRow[];
  };
  recent_audit: {
    limit: number;
    entries: Array<{
      id: string;
      event_type?: string | null;
      actor_subject?: string | null;
      resource_kind?: string | null;
      resource_id?: string | null;
      created_at?: string | null;
    }>;
  };
};

type DataSourceWritePayload = {
  operation: string;
  data_source: GovernanceRow;
  policy_evaluation: {
    warnings: string[];
    blocks_ingestion: boolean;
    public_artifact_review_required: boolean;
  };
};

type AccessWritePayload = {
  operation: string;
  membership?: MembershipRow;
  municipality_link?: MunicipalityLinkRow;
};

/** "validated_ready" -> "Validated ready" for grouped-list row labels. */
function humanizeStatus(status: string): string {
  const spaced = status.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function tonePillForGovernance(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "approved":
      return "success";
    case "draft":
      return "warning";
    case "blocked":
    case "revoked":
      return "danger";
    default:
      return "neutral";
  }
}

function toneForJobStatus(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "validated_ready") return "success";
  if (status === "running" || status === "queued") return "info";
  if (status === "validated_with_errors" || status === "manual_review_required") return "warning";
  if (status === "failed" || status === "validation_failed") return "danger";
  return "neutral";
}

function describeSchedule(entry: AutomationEntry): string {
  const schedule = entry.schedule;
  if (!schedule) return "n/a";
  if (schedule.kind === "interval_seconds" && typeof schedule.value === "number") {
    if (schedule.value % 60 === 0 && schedule.value >= 60) {
      return `every ${schedule.value / 60} min`;
    }
    return `every ${schedule.value} s`;
  }
  return String(schedule.value);
}

async function fetchControlCenter(organizationId: string): Promise<ControlCenterPayload> {
  const url = new URL(`${API_BASE_URL}/v1/admin/control-center`);
  url.searchParams.set("organization_id", organizationId);
  const response = await apiFetch(url.toString(), { cache: "no-store", credentials: "include" });
  if (!response.ok) {
    throw new Error(`Control-center request failed (${response.status})`);
  }
  return (await response.json()) as ControlCenterPayload;
}

async function writeAdminDataSource<T>(
  url: string,
  method: "POST" | "PATCH",
  body: Record<string, unknown>,
): Promise<T> {
  const response = await apiFetch(url, {
    method,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Admin data-source write failed (${response.status})`);
  }
  return (await response.json()) as T;
}

async function writeAdminAccess<T>(
  url: string,
  method: "POST" | "PATCH",
  body: Record<string, unknown>,
): Promise<T> {
  const response = await apiFetch(url, {
    method,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Admin access write failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function AdminControlCenter() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId;
  const [payload, setPayload] = useState<ControlCenterPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<DataSourceCreateForm>(DEFAULT_CREATE_FORM);
  const [policyForm, setPolicyForm] = useState<DataSourcePolicyForm>(DEFAULT_POLICY_FORM);
  const [userLinkForm, setUserLinkForm] = useState<UserLinkForm>(DEFAULT_USER_LINK_FORM);
  const [membershipForm, setMembershipForm] = useState<MembershipUpdateForm>(DEFAULT_MEMBERSHIP_FORM);
  const [municipalityForm, setMunicipalityForm] = useState<MunicipalityAccessForm>(DEFAULT_MUNICIPALITY_FORM);

  useEffect(() => {
    if (!organizationId) {
      setPayload(null);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchControlCenter(organizationId)
      .then((nextPayload) => {
        if (!cancelled) {
          setPayload(nextPayload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [organizationId]);

  useEffect(() => {
    const firstSource = payload?.governance_matrix.rows[0];
    if (!firstSource || policyForm.source_id) return;
    setPolicyForm({
      source_id: firstSource.id,
      governance_status: firstSource.governance_status,
      publication_tier: firstSource.publication_tier,
      refresh_frequency: firstSource.refresh_frequency ?? "manual",
      status: firstSource.status ?? "active",
      decision_note: "",
    });
  }, [payload, policyForm.source_id]);

  useEffect(() => {
    const firstMembership = payload?.user_roster.memberships[0];
    if (!firstMembership || membershipForm.membership_id) return;
    setMembershipForm({
      membership_id: firstMembership.membership_id,
      role: firstMembership.role,
      status: firstMembership.status,
      decision_note: "",
    });
  }, [membershipForm.membership_id, payload]);

  useEffect(() => {
    const firstLink = payload?.user_roster.municipality_links[0];
    if (!firstLink || municipalityForm.municipality_id) return;
    setMunicipalityForm({
      municipality_id: firstLink.municipality_id,
      access_level: firstLink.access_level,
      status: firstLink.status,
      decision_note: "",
    });
  }, [municipalityForm.municipality_id, payload]);

  async function refreshControlCenter() {
    if (!organizationId) return;
    setPayload(await fetchControlCenter(organizationId));
  }

  async function submitCreateDataSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    setIsMutating(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const body = buildCreateDataSourcePayload(organizationId, createForm);
      const result = await writeAdminDataSource<DataSourceWritePayload>(
        `${API_BASE_URL}/v1/admin/data-sources`,
        "POST",
        body,
      );
      setActionMessage(`Created ${result.data_source.name}; ${result.policy_evaluation.warnings.length} warning(s).`);
      setCreateForm(DEFAULT_CREATE_FORM);
      await refreshControlCenter();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Unknown data-source creation error");
    } finally {
      setIsMutating(false);
    }
  }

  async function submitPolicyUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    setIsMutating(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const { sourceId, body } = buildUpdateDataSourcePayload(organizationId, policyForm);
      const result = await writeAdminDataSource<DataSourceWritePayload>(
        `${API_BASE_URL}/v1/admin/data-sources/${encodeURIComponent(sourceId)}`,
        "PATCH",
        body,
      );
      setActionMessage(`Updated ${result.data_source.name}; ${result.policy_evaluation.warnings.length} warning(s).`);
      await refreshControlCenter();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Unknown data-source policy error");
    } finally {
      setIsMutating(false);
    }
  }

  async function submitUserLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    setIsMutating(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const body = buildUserLinkPayload(organizationId, userLinkForm);
      const result = await writeAdminAccess<AccessWritePayload>(
        `${API_BASE_URL}/v1/admin/users/link`,
        "POST",
        body,
      );
      setActionMessage(`Recorded ${result.operation} for ${result.membership?.user.subject ?? userLinkForm.subject}.`);
      setUserLinkForm(DEFAULT_USER_LINK_FORM);
      await refreshControlCenter();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Unknown user-link error");
    } finally {
      setIsMutating(false);
    }
  }

  async function submitMembershipUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    setIsMutating(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const { membershipId, body } = buildMembershipUpdatePayload(organizationId, membershipForm);
      const result = await writeAdminAccess<AccessWritePayload>(
        `${API_BASE_URL}/v1/admin/memberships/${encodeURIComponent(membershipId)}`,
        "PATCH",
        body,
      );
      setActionMessage(`Updated membership role/status for ${result.membership?.user.subject ?? membershipId}.`);
      await refreshControlCenter();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Unknown membership update error");
    } finally {
      setIsMutating(false);
    }
  }

  async function submitMunicipalityAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationId) return;
    setIsMutating(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const body = buildMunicipalityAccessPayload(organizationId, municipalityForm);
      const result = await writeAdminAccess<AccessWritePayload>(
        `${API_BASE_URL}/v1/admin/municipality-access`,
        "POST",
        body,
      );
      setActionMessage(`Recorded municipality access for ${result.municipality_link?.municipality_id ?? municipalityForm.municipality_id}.`);
      await refreshControlCenter();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Unknown municipality access error");
    } finally {
      setIsMutating(false);
    }
  }

  const governanceRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.governance_matrix.rows.map((row) => [
      row.name,
      row.source_type,
      row.provider_name ?? "—",
      row.governance_status,
      row.publication_tier,
      row.refresh_frequency ?? "—",
      row.status ?? "active",
    ]);
  }, [payload]);

  const jobRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.ingestion_overview.recent_jobs.slice(0, 10).map((job) => [
      job.job_type,
      job.status,
      job.created_at ?? "—",
    ]);
  }, [payload]);

  const membershipRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.user_roster.memberships.slice(0, 20).map((membership) => [
      membership.user.display_name ?? membership.user.subject ?? "—",
      membership.role,
      membership.status,
      membership.user.email ?? "—",
    ]);
  }, [payload]);

  const municipalityRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.user_roster.municipality_links.slice(0, 20).map((link) => [
      link.municipality_id,
      link.access_level,
      link.status,
    ]);
  }, [payload]);

  const automationRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.automations.entries.map((entry) => [
      entry.name,
      entry.task ?? "—",
      describeSchedule(entry),
    ]);
  }, [payload]);

  const auditRows = useMemo(() => {
    if (!payload) return [] as string[][];
    return payload.recent_audit.entries.slice(0, 12).map((entry) => [
      entry.event_type ?? "—",
      entry.resource_kind ?? "—",
      entry.resource_id ?? "—",
      entry.actor_subject ?? "—",
      entry.created_at ?? "—",
    ]);
  }, [payload]);

  const policyWarnings = governanceFormWarnings(policyForm);
  const membershipWarnings = accessGuardrailWarnings(membershipForm);

  return (
    <WorkspacePage
      density="compact"
      header={
        <PageHeader
          eyebrow="Admin control"
          title="Govern data sources, ingestion readiness, automations, users, and publication posture."
          description="This control center gives admins one operational view of what can be published, what needs review, which jobs recently ran, and who has access to the selected organization."
          actions={
            <Link className="primary-button" href="/workspace/uploads">
              Open upload center
            </Link>
          }
        />
      }
      kpis={
        organizationId ? (
          <KpiStrip>
            <MetricCard
              label="Data sources"
              value={payload?.governance_matrix.totals.data_source_count ?? (isLoading ? "…" : 0)}
              tone="slate"
            />
            <MetricCard
              label="Ingestion jobs"
              value={payload?.ingestion_overview.total ?? (isLoading ? "…" : 0)}
              tone="slate"
            />
            <MetricCard
              label="Members"
              value={payload?.user_roster.totals.membership_count ?? (isLoading ? "…" : 0)}
              tone="slate"
            />
            <MetricCard
              label="Automations"
              value={payload?.automations.entry_count ?? (isLoading ? "…" : 0)}
              tone="slate"
            />
          </KpiStrip>
        ) : null
      }
    >
      {!organizationId && (
        <EmptyState
          title="Choose an organization"
          detail="Use the workspace switcher to select the organization whose governance, jobs, automations, and roster should be reviewed."
        />
      )}

      {organizationId && (
        <>
          {isLoading ? (
            <LoadingState
              title="Loading admin control center"
              detail="Preparing governance totals, recent ingestion jobs, automation schedules, and organization members."
            />
          ) : null}

          {error ? (
            <ErrorState detail={`The admin control center could not load this organization. ${error}`} />
          ) : null}

          {actionMessage ? (
            <div className="warning-state">
              <strong>Governance write recorded</strong>
              <p>{actionMessage}</p>
            </div>
          ) : null}

          {actionError ? (
            <div className="warning-state warning-state-danger">
              <strong>Governance write failed</strong>
              <p>{actionError}</p>
            </div>
          ) : null}

          <Panel
            title="Governed source actions"
            detail="Create sources and update approval, publication tier, refresh cadence, or archive state with audit history."
            accent="teal"
          >
            <div className="content-grid">
              <form className="governance-form" onSubmit={submitCreateDataSource}>
                <h4>Add source</h4>
                <label>
                  <span>Source name</span>
                  <input
                    required
                    value={createForm.name}
                    onChange={(event) => setCreateForm({ ...createForm, name: event.target.value })}
                    placeholder="Traffic safety crash feed"
                  />
                </label>
                <label>
                  <span>Source type</span>
                  <input
                    required
                    value={createForm.source_type}
                    onChange={(event) => setCreateForm({ ...createForm, source_type: event.target.value })}
                    placeholder="crash_feed"
                  />
                </label>
                <label>
                  <span>Provider</span>
                  <input
                    value={createForm.provider_name}
                    onChange={(event) => setCreateForm({ ...createForm, provider_name: event.target.value })}
                    placeholder="Department of Transportation"
                  />
                </label>
                <label>
                  <span>Governance</span>
                  <select
                    value={createForm.governance_status}
                    onChange={(event) => setCreateForm({ ...createForm, governance_status: event.target.value })}
                  >
                    {GOVERNANCE_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Publication tier</span>
                  <select
                    value={createForm.publication_tier}
                    onChange={(event) => setCreateForm({ ...createForm, publication_tier: event.target.value })}
                  >
                    {PUBLICATION_TIER_OPTIONS.map((tier) => (
                      <option key={tier} value={tier}>{tier}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Refresh</span>
                  <select
                    value={createForm.refresh_frequency}
                    onChange={(event) => setCreateForm({ ...createForm, refresh_frequency: event.target.value })}
                  >
                    {REFRESH_FREQUENCY_OPTIONS.map((frequency) => (
                      <option key={frequency} value={frequency}>{frequency}</option>
                    ))}
                  </select>
                </label>
                <button className="primary-button" disabled={isMutating} type="submit">
                  Add governed source
                </button>
              </form>

              <form className="governance-form" onSubmit={submitPolicyUpdate}>
                <h4>Update source policy</h4>
                <label>
                  <span>Source</span>
                  <select
                    required
                    value={policyForm.source_id}
                    onChange={(event) => {
                      const next = payload?.governance_matrix.rows.find((row) => row.id === event.target.value);
                      setPolicyForm({
                        source_id: event.target.value,
                        governance_status: next?.governance_status ?? "draft",
                        publication_tier: next?.publication_tier ?? "restricted",
                        refresh_frequency: next?.refresh_frequency ?? "manual",
                        status: next?.status ?? "active",
                        decision_note: "",
                      });
                    }}
                  >
                    <option value="">Choose source</option>
                    {(payload?.governance_matrix.rows ?? []).map((row) => (
                      <option key={row.id} value={row.id}>{row.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Governance</span>
                  <select
                    value={policyForm.governance_status}
                    onChange={(event) => setPolicyForm({ ...policyForm, governance_status: event.target.value })}
                  >
                    {GOVERNANCE_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Publication tier</span>
                  <select
                    value={policyForm.publication_tier}
                    onChange={(event) => setPolicyForm({ ...policyForm, publication_tier: event.target.value })}
                  >
                    {PUBLICATION_TIER_OPTIONS.map((tier) => (
                      <option key={tier} value={tier}>{tier}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Refresh</span>
                  <select
                    value={policyForm.refresh_frequency}
                    onChange={(event) => setPolicyForm({ ...policyForm, refresh_frequency: event.target.value })}
                  >
                    {REFRESH_FREQUENCY_OPTIONS.map((frequency) => (
                      <option key={frequency} value={frequency}>{frequency}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={policyForm.status}
                    onChange={(event) => setPolicyForm({ ...policyForm, status: event.target.value })}
                  >
                    {SOURCE_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Decision note</span>
                  <textarea
                    value={policyForm.decision_note}
                    onChange={(event) => setPolicyForm({ ...policyForm, decision_note: event.target.value })}
                    placeholder="Explain approval, block, publication-tier change, or archive decision."
                  />
                </label>
                {policyWarnings.length > 0 ? (
                  <div className="warning-state">
                    {policyWarnings.map((warning) => (
                      <p key={warning}>{warning}</p>
                    ))}
                  </div>
                ) : null}
                <button className="primary-button" disabled={isMutating || !policyForm.source_id} type="submit">
                  Record policy change
                </button>
              </form>
            </div>
          </Panel>

          <Panel
            title="User and access management"
            detail="Link OIDC identities, change organization roles/status, and assign municipality access with audit trails."
            accent="slate"
          >
            <div className="content-grid">
              <form className="governance-form" onSubmit={submitUserLink}>
                <h4>Link user</h4>
                <label>
                  <span>OIDC subject</span>
                  <input
                    required
                    value={userLinkForm.subject}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, subject: event.target.value })}
                    placeholder="keycloak|user-id"
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    value={userLinkForm.email}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, email: event.target.value })}
                    placeholder="planner@example.gov"
                  />
                </label>
                <label>
                  <span>Display name</span>
                  <input
                    value={userLinkForm.display_name}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, display_name: event.target.value })}
                    placeholder="Mobility Planner"
                  />
                </label>
                <label>
                  <span>Role</span>
                  <select
                    value={userLinkForm.role}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, role: event.target.value })}
                  >
                    {MEMBERSHIP_ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={userLinkForm.status}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, status: event.target.value })}
                  >
                    {MEMBERSHIP_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Decision note</span>
                  <textarea
                    value={userLinkForm.decision_note}
                    onChange={(event) => setUserLinkForm({ ...userLinkForm, decision_note: event.target.value })}
                    placeholder="Reference the request ticket, onboarding approval, or access review."
                  />
                </label>
                <button className="primary-button" disabled={isMutating} type="submit">
                  Link user
                </button>
              </form>

              <form className="governance-form" onSubmit={submitMembershipUpdate}>
                <h4>Update role/status</h4>
                <label>
                  <span>Membership</span>
                  <select
                    required
                    value={membershipForm.membership_id}
                    onChange={(event) => {
                      const next = payload?.user_roster.memberships.find(
                        (membership) => membership.membership_id === event.target.value,
                      );
                      setMembershipForm({
                        membership_id: event.target.value,
                        role: next?.role ?? "analyst",
                        status: next?.status ?? "active",
                        decision_note: "",
                      });
                    }}
                  >
                    <option value="">Choose membership</option>
                    {(payload?.user_roster.memberships ?? []).map((membership) => (
                      <option key={membership.membership_id} value={membership.membership_id}>
                        {membership.user.display_name ?? membership.user.subject ?? membership.membership_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Role</span>
                  <select
                    value={membershipForm.role}
                    onChange={(event) => setMembershipForm({ ...membershipForm, role: event.target.value })}
                  >
                    {MEMBERSHIP_ROLE_OPTIONS.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={membershipForm.status}
                    onChange={(event) => setMembershipForm({ ...membershipForm, status: event.target.value })}
                  >
                    {MEMBERSHIP_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Decision note</span>
                  <textarea
                    value={membershipForm.decision_note}
                    onChange={(event) => setMembershipForm({ ...membershipForm, decision_note: event.target.value })}
                    placeholder="Explain role change, access review result, or suspension reason."
                  />
                </label>
                {membershipWarnings.length > 0 ? (
                  <div className="warning-state">
                    {membershipWarnings.map((warning) => (
                      <p key={warning}>{warning}</p>
                    ))}
                  </div>
                ) : null}
                <button className="primary-button" disabled={isMutating || !membershipForm.membership_id} type="submit">
                  Record access change
                </button>
              </form>

              <form className="governance-form" onSubmit={submitMunicipalityAccess}>
                <h4>Assign municipality</h4>
                <label>
                  <span>Municipality id</span>
                  <input
                    required
                    value={municipalityForm.municipality_id}
                    onChange={(event) => setMunicipalityForm({ ...municipalityForm, municipality_id: event.target.value })}
                    placeholder="metropolitan_core"
                  />
                </label>
                <label>
                  <span>Access level</span>
                  <select
                    value={municipalityForm.access_level}
                    onChange={(event) => setMunicipalityForm({ ...municipalityForm, access_level: event.target.value })}
                  >
                    {MUNICIPALITY_ACCESS_LEVEL_OPTIONS.map((level) => (
                      <option key={level} value={level}>{level}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={municipalityForm.status}
                    onChange={(event) => setMunicipalityForm({ ...municipalityForm, status: event.target.value })}
                  >
                    {MUNICIPALITY_LINK_STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Decision note</span>
                  <textarea
                    value={municipalityForm.decision_note}
                    onChange={(event) => setMunicipalityForm({ ...municipalityForm, decision_note: event.target.value })}
                    placeholder="Explain municipal onboarding, scope expansion, or deactivation."
                  />
                </label>
                <button className="primary-button" disabled={isMutating} type="submit">
                  Assign municipality access
                </button>
              </form>
            </div>
          </Panel>

          <Panel
            title="Governance matrix"
            detail="Data-source publication tier and governance approval status."
            accent="slate"
          >
            {Object.keys(payload?.governance_matrix.totals.by_governance_status ?? {}).length > 0 ? (
              <GroupedList ariaLabel="Governance status breakdown">
                {Object.entries(payload?.governance_matrix.totals.by_governance_status ?? {}).map(
                  ([status, count]) => (
                    <GroupedRow
                      key={`gov-status-${status}`}
                      icon={<span className={`ui-status-dot ui-status-dot-${tonePillForGovernance(status)}`} />}
                      label={humanizeStatus(status)}
                      value={count}
                    />
                  ),
                )}
              </GroupedList>
            ) : null}
            <DataTable
              columns={["Source", "Type", "Provider", "Governance", "Tier", "Refresh", "Status"]}
              rows={governanceRows}
            />
          </Panel>

          <Panel
            title="Recent ingestion jobs"
            detail="Latest jobs across statuses so operators can see validation progress and failures quickly."
            accent="rust"
          >
            {Object.keys(payload?.ingestion_overview.by_status ?? {}).length > 0 ? (
              <GroupedList ariaLabel="Ingestion status breakdown">
                {Object.entries(payload?.ingestion_overview.by_status ?? {}).map(([status, count]) => (
                  <GroupedRow
                    key={`job-status-${status}`}
                    icon={<span className={`ui-status-dot ui-status-dot-${toneForJobStatus(status)}`} />}
                    label={humanizeStatus(status)}
                    value={count}
                  />
                ))}
              </GroupedList>
            ) : null}
            <DataTable columns={["Type", "Status", "Created"]} rows={jobRows} />
          </Panel>

          <Panel
            title="Automations roster"
            detail="Scheduled refreshes and maintenance jobs configured for this organization."
            accent="slate"
          >
            <div className="chip-row">
              <StatusPill
                label={`Scheduler ${payload?.automations.scheduler_available ? "ready" : "unavailable"}`}
                tone={payload?.automations.scheduler_available ? "success" : "neutral"}
              />
            </div>
            <DataTable columns={["Name", "Task", "Cadence"]} rows={automationRows} />
          </Panel>

          <Panel title="Organization members" detail="Memberships and roles for this organization.">
            <DataTable columns={["Member", "Role", "Status", "Email"]} rows={membershipRows} />
          </Panel>

          <Panel title="Municipality access" detail="Municipal scopes assigned to this organization.">
            <DataTable columns={["Municipality", "Access", "Status"]} rows={municipalityRows} />
          </Panel>

          <Panel
            title="Recent audit history"
            detail="Latest governance and platform audit records for this organization."
            accent="rust"
          >
            <DataTable columns={["Action", "Target", "Resource id", "Actor", "Created"]} rows={auditRows} />
          </Panel>
        </>
      )}
    </WorkspacePage>
  );
}
