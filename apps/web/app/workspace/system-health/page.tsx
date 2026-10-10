import { KpiStrip, WorkspacePage } from "@/components/layout";
import { AreaGate } from "@/components/platform-shell";
import {
  DataTable,
  MetricCard,
  NavChip,
  PageHeader,
  Panel,
  StatusPill,
  WarningState,
} from "@/components/ui";

function SystemHealthDashboard() {
  return (
    <WorkspacePage
      density="compact"
      header={
        <PageHeader
          eyebrow="System health"
          title="Release readiness, observability, and operational guardrails."
          description="A focused admin surface for the checks that decide whether the platform can be promoted from feature-complete to municipal production-ready."
          meta={
            <>
              <StatusPill label="Operational readiness" tone="warning" />
              <StatusPill label="Evidence required" tone="warning" />
              <NavChip>Runbooks and smoke checks</NavChip>
            </>
          }
        />
      }
      kpis={
        <KpiStrip>
          <MetricCard label="Readiness gates" value="7" footnote="UI, API, data, jobs, security, backup, deployment" tone="rust" />
          <MetricCard label="CI baseline" value="Passing" footnote="Python and frontend checks" tone="teal" />
          <MetricCard label="Staging smoke" value="Required" footnote="Desktop and mobile route proof" />
          <MetricCard label="Runbooks" value="Required" footnote="Deploy, rollback, backup, restore" />
        </KpiStrip>
      }
    >
      <div className="content-grid">
        <Panel
          title="Acceptance gates"
          detail="The system-health route turns the release checklist into an admin-facing status model."
          accent="slate"
        >
          <DataTable
            columns={["Gate", "Status", "Owner", "Release impact"]}
            rows={[
              ["Professional UI", "Ready for smoke review", "Product", "Required for user acceptance"],
              ["Staging deployability", "Evidence required", "Operations", "Required for production promotion"],
              ["Repository hygiene", "Evidence required", "Engineering", "Required for reproducibility"],
              ["Governance access", "Implemented", "Security", "Verify in staging"],
            ]}
          />
        </Panel>

        <Panel
          title="Operational checks"
          detail="These checks mirror the release-acceptance document and runbook."
          accent="teal"
        >
          <DataTable
            columns={["Check", "Expected result"]}
            rows={[
              ["API health and OpenAPI", "Healthy, documented, role-gated"],
              ["PostGIS migrations", "Empty database migrates to head"],
              ["Object storage", "Uploads and report files persist"],
              ["Workers and scheduler", "Jobs execute and status transitions are visible"],
              ["Backups", "Postgres and object-store backup scripts pass rehearsal"],
            ]}
          />
        </Panel>
      </div>

      <WarningState
        title="Promotion requires evidence"
        detail="Do not promote a municipal environment until smoke checks, monitoring, backups, and rollback rehearsals have been recorded for that environment."
        tone="danger"
      />
    </WorkspacePage>
  );
}

export default function SystemHealthPage() {
  return (
    <AreaGate area="system_health">
      <SystemHealthDashboard />
    </AreaGate>
  );
}
