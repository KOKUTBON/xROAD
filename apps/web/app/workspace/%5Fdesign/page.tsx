"use client";

import { useState } from "react";
import type { CSSProperties } from "react";

import {
  Badge,
  BodyText,
  Breadcrumbs,
  Button,
  CheckboxField,
  DataTable,
  DisplayText,
  GroupedList,
  GroupedRow,
  Heading,
  MonoText,
  NavChip,
  Panel,
  RadioField,
  SegmentedControl,
  SelectField,
  StatusPill,
  Tabs,
  TextInput,
  TextareaField,
  ToggleField,
  Tooltip,
} from "@/components/ui";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Pagination,
  Skeleton,
  Stepper,
} from "@/components/ui";
import { PlusIcon, RefreshIcon, WORKSPACE_ICON_NAMES, WorkspaceIcon } from "@/components/icons";
import { Drawer, Modal, ToastProvider, useToast } from "@/components/overlays";
import { MapLegend } from "@/components/map-legend";

function ToastDemo() {
  const { notify } = useToast();
  return (
    <div className="chip-row">
      <Button onClick={() => notify({ title: "Saved view", detail: "Your filter was saved.", tone: "success" })} variant="secondary">
        Success toast
      </Button>
      <Button onClick={() => notify({ title: "Source is stale", detail: "Last refresh 9 days ago.", tone: "warning" })} variant="ghost">
        Warning toast
      </Button>
    </div>
  );
}
import { BarChart, DeltaBar, Donut, Histogram, Sparkline, TrendLine } from "@/components/charts";
import { CompareView, KpiCard, Timeline } from "@/components/composites";
import { DetailRail, KpiStrip, WorkSurface, WorkspacePage } from "@/components/layout";

const tableRows = [
  { city: "Bari", band: "Very high", score: 92, status: "review" },
  { city: "Lecce", band: "High", score: 81, status: "planned" },
  { city: "Taranto", band: "Moderate", score: 64, status: "monitor" },
  { city: "Foggia", band: "Low", score: 39, status: "monitor" },
  { city: "Brindisi", band: "High", score: 77, status: "queued" },
];

const brandRamps = [
  {
    label: "Asphalt",
    tokens: ["--asphalt-950", "--asphalt-900", "--asphalt-850", "--asphalt-800", "--asphalt-700", "--asphalt-600", "--asphalt-line"],
  },
  {
    label: "Road signal",
    tokens: ["--signal-amber-deep", "--signal-amber", "--signal-amber-hi", "--signal-red", "--signal-green", "--signal-blue", "--lane-white"],
  },
  {
    label: "Risk ramp (Cividis)",
    tokens: [
      "--color-risk-minimal-fill",
      "--color-risk-low-fill",
      "--color-risk-moderate-fill",
      "--color-risk-high-fill",
      "--color-risk-very-high-fill",
    ],
  },
];

export default function DesignGalleryPage() {
  const [checked, setChecked] = useState(true);
  const [radio, setRadio] = useState("analyst");
  const [toggle, setToggle] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [basemap, setBasemap] = useState<"streets" | "satellite">("streets");

  return (
    <section className="workspace-grid">
      <Breadcrumbs
        items={[
          { href: "/workspace", label: "Workspace" },
          { label: "Design gallery" },
        ]}
      />
      <div className="workspace-title">
        <Heading level={1}>Component gallery</Heading>
        <BodyText>
          P0 components and states for the UX 1.1 design-system foundation.
        </BodyText>
        <div className="chip-row">
          <StatusPill label="Keyboard focusable" tone="success" />
          <StatusPill label="Token-bound" tone="info" />
          <NavChip>Issue #171</NavChip>
        </div>
      </div>

      <Panel
        title="Signal colour tokens"
        detail="Asphalt ground, retroreflective signal amber, and the unchanged Cividis risk ramp, mapped into theme-aware semantic aliases. Hazard red is reserved for danger and very-high-risk beacons."
        accent="teal"
      >
        <div className="brand-token-gallery">
          {brandRamps.map((ramp) => (
            <section className="brand-token-ramp" key={ramp.label}>
              <Heading level={3}>{ramp.label}</Heading>
              <div className="brand-token-swatches">
                {ramp.tokens.map((token) => {
                  return (
                    <div className="brand-token-swatch" key={token}>
                      <span
                        aria-hidden="true"
                        className="brand-token-chip"
                        style={{ "--token-swatch": `var(${token})` } as CSSProperties}
                      />
                      <code>{token.replace(/^--(color-)?/, "")}</code>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
        <div className="brand-semantic-row">
          {[
            ["Brand action", "--color-brand-primary"],
            ["Accent", "--color-accent"],
            ["Information", "--color-status-info"],
            ["Success", "--color-status-success"],
            ["Warning", "--color-status-warning"],
            ["Danger", "--color-status-danger"],
          ].map(([label, token]) => (
            <div className="brand-semantic-token" key={token}>
              <span
                aria-hidden="true"
                className="brand-token-chip"
                style={{ "--token-swatch": `var(${token})` } as CSSProperties}
              />
              <BodyText size="small">{label}</BodyText>
              <code>{token}</code>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Signal icon set"
        detail="Road-semantic glyphs on a 24px grid with a 1.75 stroke and a tonal sign-plate fill. Each workspace destination has its own meaning."
      >
        <div className="icon-gallery">
          {WORKSPACE_ICON_NAMES.map((name) => (
            <figure key={name}>
              <WorkspaceIcon name={name} size={28} />
              <figcaption>{name}</figcaption>
            </figure>
          ))}
        </div>
      </Panel>

      <Panel
        title="Button & control system (#251)"
        detail="One token-driven hierarchy — primary / secondary / tertiary / destructive, with icon and small sizes. Pill geometry, keyboard-visible focus ring, subtle hover tint, and a ~0.97 active press that honors reduced-motion."
        accent="teal"
      >
        <div className="gallery-stack">
          <div className="chip-row">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="tertiary">Tertiary</Button>
            <Button variant="destructive">Destructive</Button>
          </div>
          <div className="chip-row">
            <Button size="sm" variant="primary">Small</Button>
            <Button aria-label="Add" iconOnly icon={<PlusIcon />} variant="secondary" />
            <Button aria-label="Add" size="sm" iconOnly icon={<PlusIcon size={16} />} variant="tertiary" />
            <Button isLoading variant="primary">Saving</Button>
            <Button disabled variant="secondary">Disabled</Button>
            <Tooltip content="Tooltips are visible on hover and keyboard focus.">
              <Button variant="tertiary">Tooltip target</Button>
            </Tooltip>
          </div>
          <SegmentedControl
            ariaLabel="Basemap"
            onChange={setBasemap}
            options={[
              { value: "streets", label: "Streets" },
              { value: "satellite", label: "Satellite" },
            ]}
            value={basemap}
          />
          <div className="chip-row">
            <Badge tone="neutral">Neutral</Badge>
            <Badge tone="info">Info</Badge>
            <Badge tone="success">Success</Badge>
            <Badge tone="warning">Warning</Badge>
            <Badge tone="danger">Danger</Badge>
          </div>
        </div>
      </Panel>

      <Panel title="Field set" detail="Labels, help, errors, disabled states, and binary controls." accent="slate">
        <div className="field-gallery-grid">
          <TextInput help="Used for city, corridor, or saved-view labels." label="Text input" placeholder="Bari corridor review" />
          <TextInput error="A saved view name is required." label="Error input" placeholder="Required" />
          <SelectField help="Native select with label and help text." label="Select">
            <option>Public</option>
            <option>Internal</option>
            <option>Restricted</option>
          </SelectField>
          <TextareaField help="Supports longer operator notes." label="Textarea" placeholder="Add review notes" />
          <CheckboxField checked={checked} help="Show governed draft rows in the table." label="Include draft data" onChange={setChecked} />
          <RadioField checked={radio === "analyst"} help="Analyst can inspect internal risk layers." label="Analyst" name="role" onChange={setRadio} value="analyst" />
          <RadioField checked={radio === "admin"} help="Admin can manage governance and users." label="Admin" name="role" onChange={setRadio} value="admin" />
          <ToggleField checked={toggle} label="Compact density" onChange={setToggle} />
        </div>
      </Panel>

      <Panel
        title="Card & grouped list (#255)"
        detail="One card primitive (this panel) with header / body / footer slots, plus a Settings-style grouped list — inset rows with dividers, a leading icon, a label, and a trailing value or control."
        accent="teal"
        actions={<Button size="sm" variant="tertiary">Edit</Button>}
        footer={<Button size="sm" variant="primary">Save changes</Button>}
      >
        <GroupedList ariaLabel="Governance status breakdown">
          <GroupedRow
            icon={<span className="ui-status-dot ui-status-dot-success" />}
            label="Approved"
            detail="Published to the public tier"
            value={12}
          />
          <GroupedRow
            icon={<span className="ui-status-dot ui-status-dot-warning" />}
            label="Draft"
            detail="Awaiting governance review"
            value={3}
          />
          <GroupedRow
            icon={<span className="ui-status-dot ui-status-dot-danger" />}
            label="Blocked"
            detail="Failed a policy check"
            value={1}
          />
          <GroupedRow
            label="Public visibility"
            detail="Show approved sources on the public map"
            control={<ToggleField checked={toggle} label="Visible" onChange={setToggle} />}
          />
        </GroupedList>
      </Panel>

      <Panel title="Tabs and data table v2" detail="Sortable table, row selection, density toggle, column visibility, pagination, skeleton, empty, and CSV export." accent="rust">
        <Tabs
          items={[
            {
              label: "Data",
              value: "data",
              content: (
                <DataTable
                  columns={[
                    { field: "city", header: "City" },
                    { field: "band", header: "Band" },
                    { field: "score", header: "Score" },
                    { field: "status", header: "Status" },
                  ]}
                  pageSize={3}
                  rows={tableRows}
                  selectable
                />
              ),
            },
            {
              label: "Loading",
              value: "loading",
              content: <DataTable columns={["City", "Band", "Score"]} isLoading rows={[]} />,
            },
            {
              label: "Empty",
              value: "empty",
              content: <DataTable columns={["City", "Band", "Score"]} emptyMessage="No matching rows for this filter." rows={[]} />,
            },
          ]}
        />
      </Panel>

      <Panel title="Risk legend (#180 / #172)" detail="Token-bound risk ramp, sequential by lightness, paired with labels and meanings." accent="rust">
        <div className="gallery-grid">
          <MapLegend orientation="horizontal" title="Risk band" />
          <MapLegend orientation="vertical" showMeaning title="Risk band" />
        </div>
      </Panel>

      <Panel
        title="Async states (#258)"
        detail="One visual style for every in-between state: a skeleton while loading, a tasteful empty state (icon + message + action), and a recoverable error state with retry — all reduced-motion aware."
        accent="slate"
      >
        <div className="gallery-stack">
          <div className="gallery-stack">
            <Skeleton height="1.25rem" width="55%" />
            <Skeleton height="1rem" width="85%" />
            <Skeleton height="1rem" width="70%" />
          </div>
          <EmptyState
            title="No saved views yet"
            detail="Save a filtered map or table to pin it here for the whole team."
            action={<Button size="sm" variant="secondary">Create a saved view</Button>}
          />
          <ErrorState
            detail="The corridor model could not be reached. Check the connection and try again."
            action={
              <Button icon={<RefreshIcon size={16} />} size="sm" variant="secondary">
                Retry
              </Button>
            }
          />
          <LoadingState />
        </div>
      </Panel>

      <Panel title="P1 components (#172)" detail="Modal, Drawer, Toast, Pagination, Skeleton, Stepper — overlays close on Escape and backdrop click." accent="slate">
        <div className="gallery-stack">
          <div className="chip-row">
            <Button onClick={() => setModalOpen(true)} variant="primary">Open modal</Button>
            <Button onClick={() => setDrawerOpen(true)} variant="secondary">Open drawer</Button>
          </div>
          <ToastProvider>
            <ToastDemo />
          </ToastProvider>
          <Stepper
            current={1}
            steps={[
              { label: "Register", detail: "Upload file" },
              { label: "Map schema", detail: "Match fields" },
              { label: "Validate", detail: "Run checks" },
              { label: "Approve", detail: "Commit job" },
            ]}
          />
          <div className="gallery-stack">
            <Skeleton height="1.25rem" width="60%" />
            <Skeleton height="1rem" width="90%" />
            <Skeleton height="1rem" width="75%" />
          </div>
          <Pagination onChange={setPage} page={page} pageCount={5} />
        </div>
        <Modal
          footer={<Button onClick={() => setModalOpen(false)} variant="primary">Done</Button>}
          onClose={() => setModalOpen(false)}
          open={modalOpen}
          title="Confirm publication"
        >
          <BodyText>Publishing promotes this report to the public transparency portal.</BodyText>
        </Modal>
        <Drawer onClose={() => setDrawerOpen(false)} open={drawerOpen} side="right" title="Feature inspector">
          <BodyText size="small">Drawer is the inspect surface for map and table selections.</BodyText>
        </Drawer>
      </Panel>

      <Panel title="Layout zoning (#182)" detail="WorkspacePage zones + density modes. Routes compose these instead of bespoke page CSS." accent="teal">
        <div className="gallery-stack">
          <BodyText size="small">Compact density · map-rail work surface with a sticky detail rail</BodyText>
          <WorkspacePage
            density="compact"
            header={<Heading level={3}>Page header zone</Heading>}
            kpis={
              <KpiStrip min="160px">
                <KpiCard confidence="high" label="Corridors" value={14} />
                <KpiCard confidence="medium" label="Coverage" value={44} />
                <KpiCard confidence="high" label="Burden" value="47.2" />
              </KpiStrip>
            }
            detail={
              <DetailRail title="Inspect">
                <BodyText size="small">Selected feature details live in the sticky right rail.</BodyText>
                <MapLegend orientation="vertical" showMeaning={false} title="Risk band" />
              </DetailRail>
            }
          >
            <WorkSurface variant="single">
              <DataTable
                columns={["City", "Band", "Score"]}
                rows={tableRows.map((row) => [row.city, row.band, String(row.score)])}
              />
            </WorkSurface>
          </WorkspacePage>
        </div>
      </Panel>

      <Panel
        title="Typography scale (#250)"
        detail="Libre Baskerville carries institutional headings; the system sans retains dashboard density; EB Garamond is reserved for formal long-form surfaces. All serif files are self-hosted Latin/Latin-ext WOFF2 with swap rendering."
        accent="slate"
      >
        <div className="gallery-stack">
          <DisplayText>Display — 38px</DisplayText>
          <Heading level={1}>Title — heading level 1</Heading>
          <Heading level={2}>Headline — heading level 2</Heading>
          <Heading level={3}>Subhead — heading level 3</Heading>
          <BodyText>Body — the default reading size for prose and form values.</BodyText>
          <BodyText size="small">Callout / small — dense table and metadata surfaces.</BodyText>
          <p className="type-serif-body">
            Formal report body — evidence, limitations, and recommendations set for sustained reading.
          </p>
          <MonoText>run_registry.manifest.json</MonoText>
          <BodyText>
            Tabular numerals keep columns aligned: <span className="tabular-nums">1,204.07</span>{" "}
            vs <span className="tabular-nums">9,860.31</span>.
          </BodyText>
        </div>
      </Panel>

      <Panel
        title="Chart kit (#179)"
        detail="Token-bound SVG charts: each has a title/description and a visually-hidden data table for screen readers."
        accent="teal"
      >
        <div className="gallery-grid">
          <div>
            <BodyText size="small">Sparkline</BodyText>
            <Sparkline title="Expected burden trend" values={[52, 49, 47, 48, 44, 41]} />
          </div>
          <div>
            <BodyText size="small">Donut — risk band mix</BodyText>
            <Donut
              centerLabel="14 hi"
              description="Distribution of corridors across risk bands."
              segments={[
                { label: "Minimal", value: 8 },
                { label: "Low", value: 12 },
                { label: "Moderate", value: 9 },
                { label: "High", value: 10 },
                { label: "Very high", value: 4 },
              ]}
              title="Corridors by risk band"
            />
          </div>
        </div>
        <TrendLine
          caption="Predicted yearly crashes for Bari vs the regional benchmark."
          description="Two-series yearly trend; Bari trends below the benchmark from 2024."
          referenceBand={{ from: 40, to: 48, label: "Target range" }}
          series={[
            { label: "Bari", values: [58, 54, 50, 47, 44], tone: "brand" },
            { label: "Benchmark", values: [60, 59, 57, 56, 55], tone: "neutral" },
          ]}
          title="Predicted yearly crashes"
          xLabels={["2021", "2022", "2023", "2024", "2025"]}
        />
        <div className="gallery-grid">
          <BarChart
            bars={[
              { label: "Junctions", value: 26, tone: "risk-high" },
              { label: "Segments", value: 18, tone: "risk-moderate" },
              { label: "Crossings", value: 11, tone: "risk-low" },
            ]}
            description="Count of high-priority places by feature type."
            title="High-priority places by type"
          />
          <DeltaBar
            description="Before/after expected crashes per scenario; reductions are shown in green."
            items={[
              { label: "Signal retiming", before: 24, after: 18 },
              { label: "Raised crossing", before: 16, after: 11 },
              { label: "Road diet", before: 20, after: 21 },
            ]}
            title="Scenario before/after"
          />
        </div>
        <Histogram
          bins={[
            { label: "0–20", count: 4 },
            { label: "20–40", count: 9 },
            { label: "40–60", count: 14 },
            { label: "60–80", count: 7 },
            { label: "80+", count: 3 },
          ]}
          description="Distribution of segment risk scores across bins."
          title="Risk score distribution"
        />
      </Panel>

      <Panel
        title="Analytical composites (#181)"
        detail="KPI card with sparkline + delta + confidence, before/after CompareView, and lifecycle Timeline."
        accent="rust"
      >
        <div className="metrics-grid">
          <KpiCard
            confidence="high"
            delta={{ value: 3.1, goodDirection: "down", label: "vs last year" }}
            freshness="Predicted yearly crashes"
            label="Expected burden"
            series={[54, 52, 50, 49, 48, 47.2]}
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
        </div>
        <CompareView
          description="Predicted yearly crashes before and after each intervention."
          items={[
            { label: "Raised crossings", before: 24, after: 17 },
            { label: "Signal retiming", before: 16, after: 12 },
            { label: "Road diet", before: 20, after: 21 },
          ]}
          title="Before vs after by intervention"
        />
        <Timeline
          caption="Report lifecycle from draft to public publication."
          steps={[
            { label: "Draft", state: "done" },
            { label: "Validated", state: "done" },
            { label: "Approved", state: "current" },
            { label: "Published", state: "pending" },
          ]}
        />
      </Panel>
    </section>
  );
}
