"use client";

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
  PageHeader,
  Panel,
} from "@/components/ui";
import { getClientApiBaseUrl } from "@/lib/api-client";

const API_BASE_URL = getClientApiBaseUrl();

type ScheduleEntry = {
  name: string;
  task?: string | null;
  schedule?: { kind: string; value: number | string } | null;
  base_schedule?: { kind: string; value: number | string } | null;
  options?: Record<string, unknown> | null;
  paused: boolean;
  policy?: {
    policy_kind?: string;
    description?: string;
    notification_triggers?: string[];
  };
  notification_channels?: string[];
  configuration_source?: string;
};

type RunRow = {
  job_id: string;
  job_type: string;
  status: string;
  municipality_id?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
};

type NotificationRow = {
  id: string;
  action?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  status?: string | null;
  created_at?: string | null;
};

type StaleSourceRow = {
  source_id: string;
  name?: string | null;
  source_type?: string | null;
  refresh_frequency?: string | null;
  last_refresh_at?: string | null;
  severity?: string | null;
};

type OverviewPayload = {
  api_version: string;
  contract_version: string;
  organization_id: string;
  generated_at: string;
  schedules: {
    scheduler_available: boolean;
    entry_count: number;
    paused_count: number;
    entries: ScheduleEntry[];
  };
  runs: {
    limit: number;
    totals: { total: number; by_status: Record<string, number>; by_job_type: Record<string, number> };
    rows: RunRow[];
  };
  notifications: {
    limit: number;
    totals: { total: number; by_action: Record<string, number> };
    rows: NotificationRow[];
  };
  stale_sources?: {
    totals: { source_count: number; stale_count: number };
    stale_sources: StaleSourceRow[];
  };
};

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(input, { cache: "no-store", credentials: "include", ...init });
  if (!response.ok) {
    throw new Error(`${input} -> HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

async function triggerManualRefresh(organizationId: string): Promise<unknown> {
  const response = await apiFetch(`${API_BASE_URL}/v1/automation/runs/trigger`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ organization_id: organizationId }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Manual trigger failed (${response.status})`);
  }
  return await response.json();
}

async function controlSchedule(
  organizationId: string,
  scheduleName: string,
  action: string,
  scheduleSeconds?: number,
): Promise<unknown> {
  return fetchJson(`${API_BASE_URL}/v1/automation/schedules/${encodeURIComponent(scheduleName)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      organization_id: organizationId,
      action,
      schedule_seconds: scheduleSeconds,
      notification_channels: ["email_outbox", "webhook"],
    }),
  });
}

async function deliverNotifications(organizationId: string): Promise<unknown> {
  return fetchJson(`${API_BASE_URL}/v1/automation/notifications/deliver`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      organization_id: organizationId,
      dry_run: true,
      email_recipients: ["ops@example.gov"],
      limit: 25,
    }),
  });
}

function describeSchedule(entry: ScheduleEntry): string {
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

export function AutomationControls() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId;
  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerState, setTriggerState] = useState<"idle" | "pending" | "success" | "error">("idle");
  const [triggerNote, setTriggerNote] = useState<string | null>(null);
  const [scheduleActionId, setScheduleActionId] = useState<string | null>(null);
  const [deliveryState, setDeliveryState] = useState<"idle" | "pending" | "success" | "error">("idle");

  const loadOverview = (orgId: string) => {
    setIsLoading(true);
    setError(null);
    fetchJson<OverviewPayload>(
      `${API_BASE_URL}/v1/automation/overview?organization_id=${encodeURIComponent(orgId)}`,
    )
      .then((next) => setOverview(next))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unknown error"))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    if (!organizationId) {
      setOverview(null);
      return;
    }
    loadOverview(organizationId);
  }, [organizationId]);

  const onTrigger = async () => {
    if (!organizationId) return;
    setTriggerState("pending");
    setTriggerNote(null);
    try {
      await triggerManualRefresh(organizationId);
      setTriggerState("success");
      setTriggerNote("Manual refresh queued.");
      loadOverview(organizationId);
    } catch (err) {
      setTriggerState("error");
      setTriggerNote(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const onScheduleAction = async (entry: ScheduleEntry, action: string) => {
    if (!organizationId) return;
    setScheduleActionId(entry.name);
    setTriggerNote(null);
    try {
      await controlSchedule(
        organizationId,
        entry.name,
        action,
        action === "update" ? 86_400 : undefined,
      );
      setTriggerNote(`${entry.name} ${action} applied.`);
      loadOverview(organizationId);
    } catch (err) {
      setTriggerNote(err instanceof Error ? err.message : "Unknown schedule action error");
    } finally {
      setScheduleActionId(null);
    }
  };

  const onDeliverNotifications = async () => {
    if (!organizationId) return;
    setDeliveryState("pending");
    setTriggerNote(null);
    try {
      await deliverNotifications(organizationId);
      setDeliveryState("success");
      setTriggerNote("Notification delivery dry-run recorded.");
      loadOverview(organizationId);
    } catch (err) {
      setDeliveryState("error");
      setTriggerNote(err instanceof Error ? err.message : "Unknown notification delivery error");
    }
  };

  const scheduleRows = useMemo(() => {
    if (!overview) return [] as string[][];
    return overview.schedules.entries.map((entry) => [
      entry.name,
      entry.policy?.policy_kind ?? entry.task ?? "—",
      describeSchedule(entry),
      entry.paused ? "paused" : "active",
      entry.configuration_source ?? "environment",
      (entry.notification_channels ?? []).join(", ") || "—",
    ]);
  }, [overview]);

  const runRows = useMemo(() => {
    if (!overview) return [] as string[][];
    return overview.runs.rows.map((row) => [
      row.job_type,
      row.status,
      row.created_at ?? "—",
      row.finished_at ?? "—",
    ]);
  }, [overview]);

  const notificationRows = useMemo(() => {
    if (!overview) return [] as string[][];
    return overview.notifications.rows.map((row) => [
      row.action ?? "—",
      row.target_type ?? "—",
      row.status ?? "—",
      row.created_at ?? "—",
    ]);
  }, [overview]);

  const staleRows = useMemo(() => {
    if (!overview?.stale_sources) return [] as string[][];
    return overview.stale_sources.stale_sources.map((row) => [
      row.name ?? row.source_id,
      row.source_type ?? "—",
      row.refresh_frequency ?? "—",
      row.last_refresh_at ?? "never",
      row.severity ?? "stale",
    ]);
  }, [overview]);

  return (
    <WorkspacePage
      density="compact"
      header={
        <PageHeader
          eyebrow="Automation"
          title="Keep data refreshes, health checks, and notifications operating on schedule."
          description="Admins can verify scheduled refreshes, recent automation runs, notification activity, and manually request a refresh when data needs to be updated outside the normal cadence."
        />
      }
      kpis={
        organizationId ? (
          <KpiStrip>
            <MetricCard
              label="Schedules"
              value={String(overview?.schedules.entry_count ?? (isLoading ? "…" : "—"))}
              footnote={
                overview
                  ? `${overview.schedules.paused_count} paused`
                  : "Loading beat schedule…"
              }
            />
            <MetricCard
              label="Automation runs"
              value={String(overview?.runs.totals.total ?? (isLoading ? "…" : 0))}
              footnote="Within the most recent window"
            />
            <MetricCard
              label="Notifications"
              value={String(overview?.notifications.totals.total ?? (isLoading ? "…" : 0))}
              footnote="Audit-log-derived events"
            />
            <MetricCard
              label="Stale sources"
              value={String(overview?.stale_sources?.totals.stale_count ?? (isLoading ? "…" : 0))}
              footnote={`${overview?.stale_sources?.totals.source_count ?? 0} governed sources`}
              tone="rust"
            />
            <MetricCard
              label="Scheduler"
              value={overview?.schedules.scheduler_available ? "ready" : "unavailable"}
              footnote="services.scheduler beat schedule"
            />
          </KpiStrip>
        ) : null
      }
    >
      {!organizationId && (
        <EmptyState
          title="Choose an organization"
          detail="Use the workspace switcher to select the organization whose automation schedule should be reviewed."
        />
      )}

      {organizationId && (
        <>
          {isLoading ? (
            <LoadingState
              title="Loading automation center"
              detail="Preparing schedules, recent runs, and notification activity."
            />
          ) : null}

          {error ? (
            <ErrorState detail={`The automation center could not load this organization. ${error}`} />
          ) : null}

          <Panel
            title="Manual refresh"
            detail="Request an immediate refresh for this organization when the normal schedule cannot wait."
            accent="slate"
          >
            <button
              type="button"
              onClick={onTrigger}
              disabled={triggerState === "pending"}
              className="automation-trigger-button"
            >
              {triggerState === "pending" ? "Queueing…" : "Trigger manual refresh"}
            </button>
            {triggerNote && (
              <p className={`automation-trigger-note automation-trigger-${triggerState}`}>
                {triggerNote}
              </p>
            )}
          </Panel>

          <Panel
            title="Schedules"
            detail="Recurring refreshes and maintenance checks. Pause/resume/update writes are persisted as audit-log-backed v1 controls over environment-backed cadences."
            accent="slate"
          >
            <DataTable columns={["Name", "Policy", "Cadence", "State", "Source", "Channels"]} rows={scheduleRows} />
            <div className="hero-actions">
              {(overview?.schedules.entries ?? []).map((entry) => (
                <button
                  key={`${entry.name}-${entry.paused ? "resume" : "pause"}`}
                  type="button"
                  className="ghost-button"
                  disabled={scheduleActionId === entry.name}
                  onClick={() => void onScheduleAction(entry, entry.paused ? "resume" : "pause")}
                >
                  {entry.paused ? `Resume ${entry.name}` : `Pause ${entry.name}`}
                </button>
              ))}
              {(overview?.schedules.entries ?? []).slice(0, 3).map((entry) => (
                <button
                  key={`${entry.name}-update`}
                  type="button"
                  className="ghost-button"
                  disabled={scheduleActionId === entry.name}
                  onClick={() => void onScheduleAction(entry, "update")}
                >
                  Set daily cadence for {entry.name}
                </button>
              ))}
            </div>
          </Panel>

          <Panel
            title="Recent automation runs"
            detail="Recent scheduled and manual refresh activity."
            accent="rust"
          >
            <DataTable
              columns={["Job type", "Status", "Created", "Finished"]}
              rows={runRows}
            />
          </Panel>

          <Panel
            title="Notifications"
            detail="Audit-log events relevant to ops. Delivery dry-run records configured email/webhook channels without sending external messages."
            accent="slate"
          >
            <DataTable
              columns={["Event", "Target type", "Status", "Created"]}
              rows={notificationRows}
            />
            <button
              type="button"
              onClick={onDeliverNotifications}
              disabled={deliveryState === "pending"}
              className="automation-trigger-button"
            >
              {deliveryState === "pending" ? "Recording delivery…" : "Run notification delivery dry-run"}
            </button>
          </Panel>

          <Panel
            title="Stale data sources"
            detail="Refresh-policy breaches derived from configured source cadence and last refresh time."
            accent="rust"
          >
            <DataTable
              columns={["Source", "Type", "Policy", "Last refresh", "Severity"]}
              rows={staleRows}
            />
          </Panel>
        </>
      )}
    </WorkspacePage>
  );
}
