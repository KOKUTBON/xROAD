import {
  DataTable,
  MetricCard,
  NavChip,
  PageHeader,
  Panel,
  StatusPill,
  WarningState,
  WorkflowCard,
} from "@/components/ui";
import { KpiStrip, WorkSurface, WorkspacePage } from "@/components/layout";
import {
  PRIMARY_WORKFLOWS,
  PRODUCT_AREAS,
  ROUTE_EXPERIENCE_CONTRACTS,
} from "@/lib/platform-shell";

export default function WorkspaceOverviewPage() {
  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Operations overview"
          title="Municipal safety control room for daily decisions."
          description="Start with scope, freshness, risk burden, and workflow status. From here, public, executive, analyst, traffic-engineering, reporting, and admin tasks have predictable routes and shared UI patterns."
          meta={
            <>
              <StatusPill label="Role-aware navigation" tone="success" />
              <StatusPill label="Map-first workflows" tone="success" />
              <NavChip>Shared municipal workspace</NavChip>
            </>
          }
        />
      }
      kpis={
        <KpiStrip>
          <MetricCard
            label="Product areas"
            value={PRODUCT_AREAS.length}
            footnote="Public, executive, analyst, traffic, and admin."
            tone="teal"
          />
          <MetricCard
            label="Primary workflows"
            value={PRIMARY_WORKFLOWS.length}
            footnote="Public risk, hotspot, reports, ingestion, governance."
          />
          <MetricCard
            label="V1 routes"
            value={ROUTE_EXPERIENCE_CONTRACTS.length}
            footnote="Every route has an audience, task, layout, and clear state handling."
            tone="rust"
          />
        </KpiStrip>
      }
    >
      <WorkSurface variant="split">
        <Panel
          title="Product areas"
          detail="Each area has one audience, one purpose, and predictable route groups."
          accent="teal"
        >
          <div className="workflow-grid">
            {PRODUCT_AREAS.map((area) => (
              <WorkflowCard
                key={area.id}
                audience={area.audience}
                label={area.label}
                outcome={area.mission}
              />
            ))}
          </div>
        </Panel>

        <Panel
          title="Route experience matrix"
          detail="Each route has an audience, primary task, layout pattern, and required states."
          accent="slate"
        >
          <DataTable
            columns={["Route", "Audience", "Primary task", "Pattern", "States"]}
            rows={ROUTE_EXPERIENCE_CONTRACTS.map((route) => [
              route.route,
              route.audience,
              route.primaryTask,
              route.layoutPattern,
              route.requiredStates.join(", "),
            ])}
          />
        </Panel>
      </WorkSurface>

      <WarningState
        title="Operator guidance"
        detail="Use the left-to-right flow of scope, filters, map or table, and detail panels before exporting or publishing any safety decision."
      />
    </WorkspacePage>
  );
}
