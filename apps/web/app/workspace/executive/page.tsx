import { AreaGate } from "@/components/platform-shell";
import {
  DataTable,
  NavChip,
  PageHeader,
  Panel,
  StatusPill,
  WorkflowCard,
} from "@/components/ui";
import { CompareView, KpiCard, Timeline } from "@/components/composites";
import { KpiStrip, WorkSurface, WorkspacePage } from "@/components/layout";

const executiveWorkflows = [
  {
    label: "Safety overview",
    audience: "Mayor and directors",
    outcome: "Track very-high-risk corridors, expected crash burden, and confidence in one view.",
    route: "/workspace/executive",
  },
  {
    label: "Budget impact",
    audience: "Finance and mobility leadership",
    outcome: "Compare intervention benefit, cost class, and delivery status before funding decisions.",
    route: "/workspace/scenarios",
  },
  {
    label: "Monthly report",
    audience: "Executive office",
    outcome: "Open the latest generated safety overview and publish approved public extracts.",
    route: "/workspace/reports",
  },
];

function ExecutiveDashboard() {
  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Executive dashboard"
          title="Decision-ready safety posture for municipal leadership."
          description="A concise operating board for risk burden, priority investments, intervention delivery, data coverage, and before/after progress."
          meta={
            <>
              <StatusPill label="Executive summary" tone="success" />
              <StatusPill label="Governance-aware exports" tone="warning" />
              <NavChip>Monthly briefing route</NavChip>
            </>
          }
        />
      }
      kpis={
        <KpiStrip>
          <KpiCard
          confidence="high"
          delta={{ value: 2, goodDirection: "down", label: "vs last month" }}
          freshness="Updated with the monthly refresh bundle"
          label="Very-high corridors"
          series={[18, 17, 17, 16, 15, 14]}
          seriesTone="risk-high"
          value={14}
        />
        <KpiCard
          confidence="high"
          delta={{ value: 3.1, goodDirection: "down", label: "vs last year" }}
          freshness="Predicted yearly crashes"
          label="Expected burden"
          series={[54, 52, 50, 49, 48, 47.2]}
          seriesTone="brand"
          value="47.2"
        />
        <KpiCard
          confidence="medium"
          delta={{ value: 4, goodDirection: "up", label: "new movements" }}
          freshness="Provider-covered movements"
          label="Signal coverage"
          series={[36, 38, 40, 41, 43, 44]}
          value={44}
        />
          <KpiCard
            confidence="medium"
            freshness="Release baseline summary"
            label="Model confidence"
            target="High"
            value="Med-high"
          />
        </KpiStrip>
      }
    >
      <WorkSurface variant="split">
        <Panel
          title="Executive workflow"
          detail="Built for short briefings and funding decisions, not technical exploration."
          accent="teal"
        >
          <div className="workflow-grid">
            {executiveWorkflows.map((workflow) => (
              <WorkflowCard key={workflow.label} {...workflow} />
            ))}
          </div>
        </Panel>

        <Panel
          title="Priority investment board"
          detail="A compact version of the intervention portfolio for decision makers."
          accent="rust"
        >
          <DataTable
            columns={["Priority", "Intervention", "Expected benefit", "Cost", "Status"]}
            rows={[
              ["1", "Raised crossings on top VRU corridor", "High", "Medium", "Plan review"],
              ["2", "Signal timing review at incomplete phase nodes", "Medium-high", "Low", "Engineering"],
              ["3", "Speed-calming package on high-risk arterials", "High", "Medium-high", "Funding"],
              ["4", "Public transparency report refresh", "Medium", "Low", "Ready"],
            ]}
          />
        </Panel>

        <Panel
          title="Before / after impact"
          detail="Expected crashes per intervention, before and after the planned works. Reductions show in green."
          accent="teal"
        >
          <CompareView
            description="Predicted yearly crashes before and after each priority intervention."
            items={[
              { label: "Raised crossings", before: 24, after: 17 },
              { label: "Signal retiming", before: 16, after: 12 },
              { label: "Speed calming", before: 20, after: 14 },
            ]}
            title="Predicted crashes before vs after"
            unit=""
          />
        </Panel>
      </WorkSurface>

      <Panel
        title="Monthly briefing delivery"
        detail="Lifecycle of this month's executive safety report from draft to public publication."
        accent="slate"
      >
        <Timeline
          caption="The public extract is gated on governance approval before publication."
          steps={[
            { label: "Draft", state: "done", detail: "Generated from the refresh bundle" },
            { label: "Validated", state: "done", detail: "Analyst sign-off" },
            { label: "Approved", state: "current", detail: "Governance review" },
            { label: "Published", state: "pending", detail: "Public extract" },
          ]}
        />
      </Panel>
    </WorkspacePage>
  );
}

export default function ExecutivePage() {
  return (
    <AreaGate area="executive">
      <ExecutiveDashboard />
    </AreaGate>
  );
}
