import { STATIC_DEMO } from "./demo-mode";
import type { InstitutionConfig } from "./institution";
import { institutionRouteEnabled } from "./institution-product";

export type PlatformRole =
  | "public"
  | "municipality_viewer"
  | "analyst"
  | "data_operator"
  | "traffic_engineer"
  | "admin"
  | "super_admin";

export type ShellArea =
  | "public"
  | "internal"
  | "executive"
  | "reports"
  | "analyst"
  | "traffic_engineering"
  | "data_operations"
  | "admin"
  | "system_health";
export type SessionMode = "public" | "demo" | "live";

export interface OrganizationOption {
  id: string;
  name: string;
  shortLabel: string;
  municipalityIds: string[];
}

export interface MunicipalityOption {
  id: string;
  name: string;
  regionLabel: string;
  coverageLabel: string;
}

export interface ScopeCatalog {
  organizations: OrganizationOption[];
  municipalities: MunicipalityOption[];
}

export interface PlatformSession {
  mode: SessionMode;
  provider: string;
  authEnabled: boolean;
  subject: string | null;
  displayName: string;
  assignedRoles: PlatformRole[];
  roles: PlatformRole[];
  organizationIds: string[];
  municipalityIds: string[];
  selectedOrganizationId: string | null;
  selectedMunicipalityId: string | null;
  scopeCatalog?: ScopeCatalog;
}

export interface DemoProfile {
  id: string;
  label: string;
  description: string;
  session: PlatformSession;
}

export interface ApiAuthSnapshot {
  scope_catalog?: ScopeCatalog;
  auth_enabled: boolean;
  provider: string;
  subject: string | null;
  assigned_roles: string[];
  roles: string[];
  organization_ids: string[];
  municipality_ids: string[];
}

export interface NavItem {
  href: string;
  label: string;
  detail: string;
  area: ShellArea;
  groupId: ProductAreaId;
  workflow: string;
  status: "live" | "planned" | "restricted";
}

export type ProductAreaId =
  | "public"
  | "executive"
  | "analyst"
  | "traffic"
  | "admin";

export interface ProductArea {
  id: ProductAreaId;
  label: string;
  audience: string;
  mission: string;
}

export interface NavGroup extends ProductArea {
  items: NavItem[];
}

export interface DashboardPreview {
  cityCount: number;
  highRiskCorridorCount: number;
  interventionCandidateCount: number;
  monthlyRefreshCadence: string;
  signalCoverageLabel: string;
  trackedCities: string[];
}

export interface RouteExperienceContract {
  route: string;
  area: ProductAreaId | "auth";
  audience: string;
  primaryTask: string;
  layoutPattern: "public-map" | "workspace-overview" | "dashboard" | "map-workbench" | "table-workbench" | "operations-board";
  requiredStates: Array<"loading" | "empty" | "error" | "no-access" | "degraded">;
}

const ALL_ROLES: PlatformRole[] = [
  "public",
  "municipality_viewer",
  "analyst",
  "data_operator",
  "traffic_engineer",
  "admin",
  "super_admin",
];

const INTERNAL_ROLES: PlatformRole[] = [
  "municipality_viewer",
  "analyst",
  "data_operator",
  "traffic_engineer",
  "admin",
  "super_admin",
];

const ANALYST_ROLES: PlatformRole[] = [
  "analyst",
  "traffic_engineer",
  "admin",
  "super_admin",
];

const TRAFFIC_ENGINEERING_ROLES: PlatformRole[] = [
  "traffic_engineer",
  "admin",
  "super_admin",
];

const DATA_OPERATIONS_ROLES: PlatformRole[] = ["data_operator", "admin", "super_admin"];

const ADMIN_ROLES: PlatformRole[] = ["admin", "super_admin"];

export const PRODUCT_AREAS: ProductArea[] = [
  {
    id: "public",
    label: "Public transparency",
    audience: "Citizens, elected officials, public stakeholders",
    mission: "Explain risk, trends, interventions, and methodology without exposing restricted data.",
  },
  {
    id: "executive",
    label: "Executive control",
    audience: "Mayors, directors, department leads",
    mission: "Summarize burden, budget impact, intervention progress, and monthly reporting.",
  },
  {
    id: "analyst",
    label: "Analysis desk",
    audience: "Mobility analysts, consultants, planners",
    mission: "Explore hotspots, map layers, explanations, scenarios, and intervention portfolios.",
  },
  {
    id: "traffic",
    label: "Traffic engineering",
    audience: "Signal engineers, VRU planners, operations teams",
    mission: "Operate VRU, signal-phase, coverage, and validation workflows with clear status.",
  },
  {
    id: "admin",
    label: "Administration",
    audience: "Data operators, admins, platform owners",
    mission: "Govern data sources, ingestion jobs, automations, users, health, and publication policy.",
  },
];

export const ORGANIZATIONS: OrganizationOption[] = STATIC_DEMO ? [{
  id: "org-tirana-demo", name: "Tirana Road Safety Demo", shortLabel: "Tirana Demo", municipalityIds: ["tirana"],
}] : [
  {
    id: "org-bari-mobility",
    name: "Bari Mobility Intelligence Office",
    shortLabel: "Bari Mobility",
    municipalityIds: ["bari", "modugno"],
  },
  {
    id: "org-puglia-safety-lab",
    name: "Puglia Regional Safety Lab",
    shortLabel: "Puglia Lab",
    municipalityIds: ["bari", "brindisi", "lecce", "taranto", "foggia"],
  },
  {
    id: "org-municipal-ops",
    name: "Municipal Operations Control Center",
    shortLabel: "Ops Center",
    municipalityIds: ["bari", "brindisi", "lecce"],
  },
];

export const MUNICIPALITIES: MunicipalityOption[] = STATIC_DEMO ? [{
  id: "tirana", name: "Tirana", regionLabel: "Albania", coverageLabel: "synthetic demo",
}] : [
  { id: "bari", name: "Bari", regionLabel: "Puglia", coverageLabel: "live pilot" },
  { id: "brindisi", name: "Brindisi", regionLabel: "Puglia", coverageLabel: "benchmark ready" },
  { id: "foggia", name: "Foggia", regionLabel: "Puglia", coverageLabel: "transfer benchmark" },
  { id: "lecce", name: "Lecce", regionLabel: "Puglia", coverageLabel: "transfer benchmark" },
  { id: "modugno", name: "Modugno", regionLabel: "Puglia", coverageLabel: "neighbor scope" },
  { id: "taranto", name: "Taranto", regionLabel: "Puglia", coverageLabel: "transfer benchmark" },
];

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Public map",
    detail: "Citizen-facing overview and transparent risk narrative.",
    area: "public",
    groupId: "public",
    workflow: "Inspect public risk, trends, interventions, and methodology.",
    status: "live",
  },
  {
    href: "/workspace",
    label: "Operations overview",
    detail: "Municipal command center for daily safety operations.",
    area: "internal",
    groupId: "executive",
    workflow: "Start from one operational cockpit before entering specialist work.",
    status: "live",
  },
  {
    href: "/workspace/executive",
    label: "Executive board",
    detail: "KPIs, budget impact, priority map, and before/after narrative.",
    area: "executive",
    groupId: "executive",
    workflow: "Brief decision makers on risk burden, benefits, and delivery progress.",
    status: "live",
  },
  {
    href: "/workspace/reports",
    label: "Reports",
    detail: "Executive KPIs, report history, and export workflows.",
    area: "reports",
    groupId: "executive",
    workflow: "Generate, review, download, and publish internal or public reports.",
    status: "live",
  },
  {
    href: "/workspace/analyst",
    label: "Analyst desk",
    detail: "Map, hotspot, and scenario entry points for technical operators.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Investigate hotspots and inspect scored segments, junctions, and crossings.",
    status: "live",
  },
  {
    href: "/workspace/scenarios",
    label: "Scenario planner",
    detail: "Generated scenarios, intervention library, and ranked portfolios.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Compare interventions, expected benefits, and portfolio composition.",
    status: "live",
  },
  {
    href: "/workspace/proposed-changes",
    label: "Proposed changes",
    detail: "AI-ranked infrastructure treatments with engineer review and approval.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Inspect recommendation evidence, approve treatments, and export an action plan.",
    status: "live",
  },
  {
    href: "/workspace/siting-advisor",
    label: "Siting advisor",
    detail: "Standards-cited candidate sites for schools, parks, and institutions.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Request a siting analysis, inspect compliance, and export a municipal brief.",
    status: "live",
  },
  {
    href: "/workspace/climate",
    label: "Climate resilience",
    detail: "Map of where extreme weather most degrades road-network safety.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Identify climate-hazard exposure and infrastructure resilience across the network.",
    status: "live",
  },
  {
    href: "/workspace/research",
    label: "Research & Benchmarks",
    detail: "Exposure-normalized panel models, statistical baselines vs GBDT, and validation curves.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Evaluate exposure offsets, spatial-temporal splits, and Top-k capture curves.",
    status: "live",
  },
  {
    href: "/workspace/digital-twin",
    label: "Digital Twin & 3D Simulation",
    detail: "Interactive 3D microscopic multi-agent simulation and geometric countermeasure appraisal.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Simulate multi-agent vehicle & VRU trajectories, visualize TTC conflict cones, and test redesigns.",
    status: "live",
  },
  {
    href: "/workspace/forensics",
    label: "Forensic Reconstruction",
    detail: "Micro-second telemetry synchronization, momentum conservation, and counterfactual playback.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Reconstruct pre-crash multi-agent dynamics, evaluate driver PRT, and test AEB avoidance.",
    status: "live",
  },
  {
    href: "/workspace/tmc-playbooks",
    label: "TMC Playbook Automation",
    detail: "Real-time incident detection, 5-tier multi-modal actuation, and EU AI Act Article 14 governance.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Monitor active traffic threats, evaluate 5-tier actuation plans, and execute 1-click sovereign response.",
    status: "live",
  },
  {
    href: "/workspace/connected-fleets",
    label: "Connected Fleets & C-V2X",
    detail: "In-Vehicle Information (ISO 19321), PC5 Sidelink Mode 4, 5G Uu Geo-MQTT, and digital cockpit HMI.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Monitor connected vehicle fleet telemetry, test C-V2X direct radio, and simulate digital cockpit alerts.",
    status: "live",
  },
  {
    href: "/workspace/incident-coordination",
    label: "Multi-Incident Coordination",
    detail: "LWR shockwave spillover dynamics, detour clash detection, and capacity-constrained flow split optimization.",
    area: "analyst",
    groupId: "analyst",
    workflow: "Resolve cascading traffic conflicts, predict queue reach times, and optimize multi-corridor diversions.",
    status: "live",
  },
  {
    href: "/workspace/operations",
    label: "Traffic engineering",
    detail: "Operational VRU priorities and signal-phase coverage workflows.",
    area: "traffic_engineering",
    groupId: "traffic",
    workflow: "Validate VRU priorities, signal coverage, and request/action workflows.",
    status: "restricted",
  },
  {
    href: "/workspace/admin",
    label: "Admin control",
    detail: "Governance, data sources, uploads, and scheduling surfaces.",
    area: "admin",
    groupId: "admin",
    workflow: "Review sources, ingestion jobs, governance status, and user scope.",
    status: "live",
  },
  {
    href: "/workspace/uploads",
    label: "Upload center",
    detail: "Register files, map schemas, validate payloads, and approve ingestion jobs.",
    area: "data_operations",
    groupId: "admin",
    workflow: "Upload governed crash, traffic, speed, signal, and geospatial files.",
    status: "live",
  },
  {
    href: "/workspace/automation",
    label: "Automation",
    detail: "Scheduled refresh, run history, and notification controls.",
    area: "admin",
    groupId: "admin",
    workflow: "Manage recurring refreshes, stale-source alerts, and notification routing.",
    status: "live",
  },
  {
    href: "/workspace/system-health",
    label: "System health",
    detail: "Readiness, observability, release blockers, and smoke-test status.",
    area: "system_health",
    groupId: "admin",
    workflow: "Confirm deployability, monitoring, backups, and acceptance blockers.",
    status: "restricted",
  },
];

export const PRIMARY_WORKFLOWS = [
  {
    id: "public-risk-inspection",
    label: "Public risk inspection",
    route: "/",
    audience: "Public user",
    outcome: "Find high-risk areas, understand trend context, and download a public report.",
  },
  {
    id: "analyst-hotspot-inspection",
    label: "Analyst hotspot inspection",
    route: "/workspace/analyst",
    audience: "Analyst",
    outcome: "Filter the map, inspect a segment or crossing, and identify recommended actions.",
  },
  {
    id: "report-generation",
    label: "Report generation",
    route: "/workspace/reports",
    audience: "Executive or analyst",
    outcome: "Generate monthly, technical, VRU, scenario, governance, or transparency reports.",
  },
  {
    id: "ingestion-status-review",
    label: "Ingestion status review",
    route: "/workspace/uploads",
    audience: "Data operator or admin",
    outcome: "Register an upload, map fields, run validation, review errors, and approve or reject the job.",
  },
  {
    id: "governance-review",
    label: "Governance review",
    route: "/workspace/admin",
    audience: "Admin or legal reviewer",
    outcome: "Approve source publication tiers and confirm public/private access posture.",
  },
];

export const ROUTE_EXPERIENCE_CONTRACTS: RouteExperienceContract[] = [
  {
    route: "/",
    area: "public",
    audience: "Citizens and public stakeholders",
    primaryTask: "Filter public risk tiles, inspect a safe detail panel, and open public reports.",
    layoutPattern: "public-map",
    requiredStates: ["loading", "empty", "error", "degraded"],
  },
  {
    route: "/login",
    area: "auth",
    audience: "All authenticated municipal users",
    primaryTask: "Enter through the municipal identity provider or a non-production demo profile.",
    layoutPattern: "dashboard",
    requiredStates: ["error", "no-access"],
  },
  {
    route: "/workspace",
    area: "executive",
    audience: "Municipal viewers and operators",
    primaryTask: "Understand scope, available product areas, and the next workflow to open.",
    layoutPattern: "workspace-overview",
    requiredStates: ["no-access"],
  },
  {
    route: "/workspace/executive",
    area: "executive",
    audience: "Mayors, directors, and department leads",
    primaryTask: "Review safety burden, priority investments, budget impact, and monthly posture.",
    layoutPattern: "dashboard",
    requiredStates: ["no-access", "degraded"],
  },
  {
    route: "/workspace/analyst",
    area: "analyst",
    audience: "Mobility analysts and planners",
    primaryTask: "Filter internal risk layers, select features, and triage high-priority places.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/scenarios",
    area: "analyst",
    audience: "Planners and intervention portfolio owners",
    primaryTask: "Compare countermeasures, ranked scenarios, portfolios, and treatment assumptions.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/proposed-changes",
    area: "analyst",
    audience: "Analysts, traffic engineers, and municipal approvers",
    primaryTask: "Map, review, approve, and export evidence-backed infrastructure recommendations.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/siting-advisor",
    area: "analyst",
    audience: "Municipal planners, analysts, and infrastructure teams",
    primaryTask: "Request, inspect, compare, and export standards-cited facility siting options.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/research",
    area: "analyst",
    audience: "Safety researchers, data scientists, and econometricians",
    primaryTask: "Evaluate exposure offsets, Poisson/NB baselines vs GBDT, and Top-k capture curves.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/digital-twin",
    area: "analyst",
    audience: "Traffic engineers, safety researchers, and urban designers",
    primaryTask: "Simulate multi-agent trajectories, visualize 3D TTC conflicts, and test junction redesigns.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/forensics",
    area: "analyst",
    audience: "Accident investigators, forensic engineers, and judicial authorities",
    primaryTask: "Synchronize pre-crash telemetry, analyze driver PRT, and simulate counterfactual AEB.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/tmc-playbooks",
    area: "analyst",
    audience: "Traffic Management Center operators, emergency dispatchers, and highway patrol commanders",
    primaryTask: "Monitor incidents, verify VSL/VMS/C-ITS/MDS actuation tiers, and execute HITL playbooks.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/connected-fleets",
    area: "analyst",
    audience: "Fleet managers, autonomous vehicle engineers, and C-ITS operators",
    primaryTask: "Inspect ISO 19321 IVI messages, monitor PC5/Uu C-V2X radio envelopes, and test cockpit HMI.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/incident-coordination",
    area: "analyst",
    audience: "TMC operations commanders, corridor network managers, and incident dispatchers",
    primaryTask: "Assess LWR shockwave propagation, intercept detour clashes, and deploy balanced diversion flow splits.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/operations",
    area: "traffic",
    audience: "Traffic engineers and VRU planners",
    primaryTask: "Review VRU priorities, signal coverage, ready actions, and holds.",
    layoutPattern: "operations-board",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/reports",
    area: "executive",
    audience: "Executives, analysts, and report publishers",
    primaryTask: "Generate, review, download, and publish executive or technical reports.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/admin",
    area: "admin",
    audience: "Data operators, admins, and governance reviewers",
    primaryTask: "Review data sources, ingestion jobs, publication tiers, members, and audit posture.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/uploads",
    area: "admin",
    audience: "Data operators, admins, and ingestion reviewers",
    primaryTask: "Register files, map schemas, upload to object storage, validate payloads, and approve or reject jobs.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/automation",
    area: "admin",
    audience: "Platform admins and operations owners",
    primaryTask: "Review schedules, runs, notifications, and request manual refreshes.",
    layoutPattern: "operations-board",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/system-health",
    area: "admin",
    audience: "Platform owners and release managers",
    primaryTask: "Track readiness evidence, operational checks, smoke tests, and promotion gates.",
    layoutPattern: "operations-board",
    requiredStates: ["no-access", "degraded"],
  },
];

export const DEFAULT_DASHBOARD_PREVIEW: DashboardPreview = STATIC_DEMO ? {
  cityCount: 1, highRiskCorridorCount: 2, interventionCandidateCount: 2,
  monthlyRefreshCadence: "static demo snapshot", signalCoverageLabel: "illustrative signal coverage", trackedCities: ["Tirana"],
} : {
  cityCount: 5,
  highRiskCorridorCount: 14,
  interventionCandidateCount: 26,
  monthlyRefreshCadence: "monthly refresh bundle",
  signalCoverageLabel: "44 provider-covered movements",
  trackedCities: ["Bari", "Brindisi", "Foggia", "Lecce", "Taranto"],
};

function baseSession(
  mode: SessionMode,
  overrides: Partial<PlatformSession> = {},
): PlatformSession {
  return {
    mode,
    provider: "demo-shell",
    authEnabled: mode !== "public",
    subject: null,
    displayName: "Public user",
    assignedRoles: ["public"],
    roles: ["public"],
    organizationIds: [],
    municipalityIds: [],
    selectedOrganizationId: null,
    selectedMunicipalityId: null,
    ...overrides,
  };
}

export const DEMO_PROFILES: DemoProfile[] = STATIC_DEMO ? [
  { id: "public", label: "Public visitor", description: "Explore the synthetic Tirana map.", session: baseSession("public") },
  ...[
    { id: "analyst_tirana", label: "Analyst for Tirana", role: "analyst", roles: ["public", "municipality_viewer", "analyst"] },
    { id: "admin_tirana", label: "Demo admin", role: "admin", roles: ["public", "municipality_viewer", "analyst", "data_operator", "traffic_engineer", "admin"] },
    { id: "traffic_engineer_tirana", label: "Traffic engineer", role: "traffic_engineer", roles: ["public", "municipality_viewer", "analyst", "traffic_engineer"] },
  ].map((profile) => ({
    id: profile.id, label: profile.label, description: "Synthetic Tirana workspace; no institutional account.",
    session: baseSession("demo", {
      provider: "static-demo", authEnabled: true, subject: `demo-${profile.role}`, displayName: profile.label,
      assignedRoles: [profile.role as PlatformRole], roles: profile.roles as PlatformRole[],
      organizationIds: ["org-tirana-demo"], municipalityIds: ["tirana"],
      selectedOrganizationId: "org-tirana-demo", selectedMunicipalityId: "tirana",
    }),
  })),
] : [
  {
    id: "public",
    label: "Public visitor",
    description: "Citizen-facing risk map, reports, and methodology pages.",
    session: baseSession("public"),
  },
  {
    id: "analyst_bari",
    label: "Analyst for Bari",
    description: "Internal explorer with Bari municipal scope and technical views.",
    session: baseSession("demo", {
      provider: "demo-oidc",
      authEnabled: true,
      subject: "analyst.bari",
      displayName: "Bari Analyst",
      assignedRoles: ["analyst"],
      roles: ["public", "municipality_viewer", "analyst"],
      organizationIds: ["org-bari-mobility"],
      municipalityIds: ["bari", "modugno"],
      selectedOrganizationId: "org-bari-mobility",
      selectedMunicipalityId: "bari",
    }),
  },
  {
    id: "admin_regional",
    label: "Regional admin",
    description: "Governance, upload, and scheduling shell across multiple cities.",
    session: baseSession("demo", {
      provider: "demo-oidc",
      authEnabled: true,
      subject: "admin.regional",
      displayName: "Regional Admin",
      assignedRoles: ["admin"],
      roles: [
        "public",
        "municipality_viewer",
        "analyst",
        "data_operator",
        "traffic_engineer",
        "admin",
      ],
      organizationIds: ["org-puglia-safety-lab"],
      municipalityIds: ["bari", "brindisi", "lecce", "taranto", "foggia"],
      selectedOrganizationId: "org-puglia-safety-lab",
      selectedMunicipalityId: "bari",
    }),
  },
  {
    id: "traffic_engineer_bari",
    label: "Traffic engineer",
    description: "Signal-phase, VRU, and operational validation workflows for Bari.",
    session: baseSession("demo", {
      provider: "demo-oidc",
      authEnabled: true,
      subject: "engineer.bari",
      displayName: "Bari Traffic Engineer",
      assignedRoles: ["traffic_engineer"],
      roles: ["public", "municipality_viewer", "traffic_engineer"],
      organizationIds: ["org-bari-mobility"],
      municipalityIds: ["bari", "modugno"],
      selectedOrganizationId: "org-bari-mobility",
      selectedMunicipalityId: "bari",
    }),
  },
];

function uniq(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

export function canAccessArea(session: PlatformSession, area: ShellArea): boolean {
  if (area === "public") {
    return true;
  }
  if (area === "internal" || area === "executive" || area === "reports") {
    return session.roles.some((role) => INTERNAL_ROLES.includes(role));
  }
  if (area === "analyst") {
    return session.roles.some((role) => ANALYST_ROLES.includes(role));
  }
  if (area === "traffic_engineering") {
    return session.roles.some((role) => TRAFFIC_ENGINEERING_ROLES.includes(role));
  }
  if (area === "data_operations") {
    return session.roles.some((role) => DATA_OPERATIONS_ROLES.includes(role));
  }
  return session.roles.some((role) => ADMIN_ROLES.includes(role));
}

export function resolveDefaultRoute(session: PlatformSession, institution?: InstitutionConfig): string {
  if (canAccessArea(session, "admin")) {
    return "/workspace/admin";
  }
  if (canAccessArea(session, "traffic_engineering") && (!institution || institutionRouteEnabled(institution, "/workspace/operations"))) {
    return "/workspace/operations";
  }
  if (canAccessArea(session, "analyst") && (!institution || institutionRouteEnabled(institution, "/workspace/analyst"))) {
    return "/workspace/analyst";
  }
  if (canAccessArea(session, "internal")) {
    return "/workspace";
  }
  return "/";
}

export function buildNavigation(session: PlatformSession, institution?: InstitutionConfig): NavItem[] {
  return NAV_ITEMS.filter((item) => canAccessArea(session, item.area) && (!institution || institutionRouteEnabled(institution, item.href)));
}

export function buildNavigationGroups(session: PlatformSession, institution?: InstitutionConfig): NavGroup[] {
  const visibleItems = buildNavigation(session, institution);
  return PRODUCT_AREAS.map((area) => ({
    ...area,
    items: visibleItems.filter((item) => item.groupId === area.id),
  })).filter((group) => group.items.length > 0);
}

function catalogFor(session: PlatformSession): ScopeCatalog {
  if (session.scopeCatalog) return session.scopeCatalog;
  // Sample institutions belong only to explicit demos/public development.
  if (session.mode === "live") return { organizations: [], municipalities: [] };
  return { organizations: ORGANIZATIONS, municipalities: MUNICIPALITIES };
}

export function sessionOrganizations(session: PlatformSession): OrganizationOption[] {
  const organizations = catalogFor(session).organizations;
  if (session.roles.includes("super_admin") || session.mode !== "live" && session.organizationIds.length === 0) return organizations;
  return organizations.filter((organization) => session.organizationIds.includes(organization.id));
}

export function sessionMunicipalities(session: PlatformSession): MunicipalityOption[] {
  const organizations = sessionOrganizations(session);
  const linked = new Set(organizations.flatMap((organization) => organization.municipalityIds));
  return catalogFor(session).municipalities.filter((municipality) => linked.has(municipality.id) && (session.roles.includes("super_admin") || session.mode !== "live" && session.municipalityIds.length === 0 || session.municipalityIds.includes(municipality.id)));
}

export function applySessionContext(session: PlatformSession, organizationId: string | null, municipalityId: string | null): PlatformSession {
  const organizations = sessionOrganizations(session);
  const selectedOrganization = organizations.find((organization) => organization.id === organizationId) ?? organizations[0];
  const municipalities = sessionMunicipalities(session).filter((municipality) => selectedOrganization?.municipalityIds.includes(municipality.id));
  const selectedMunicipality = municipalities.find((municipality) => municipality.id === municipalityId) ?? municipalities[0];
  return { ...session, selectedOrganizationId: selectedOrganization?.id ?? null, selectedMunicipalityId: selectedMunicipality?.id ?? null };
}

export function normalizeDashboardPreview(payload: unknown): DashboardPreview {
  if (!payload || typeof payload !== "object") {
    return DEFAULT_DASHBOARD_PREVIEW;
  }

  const summary = "summary" in payload && typeof payload.summary === "object" ? payload.summary : payload;
  const publishedRuns =
    summary && typeof summary === "object" && Array.isArray((summary as Record<string, unknown>).published_runs)
      ? ((summary as Record<string, unknown>).published_runs as Array<Record<string, unknown>>)
      : [];

  const trackedCities = uniq(
    publishedRuns
      .map((row) => String(row.municipality_name ?? row.city_name ?? row.city ?? "").trim())
      .filter(Boolean),
  );

  const interventionCandidateCount =
    summary && typeof summary === "object"
      ? Number((summary as Record<string, unknown>).intervention_candidate_count ?? DEFAULT_DASHBOARD_PREVIEW.interventionCandidateCount)
      : DEFAULT_DASHBOARD_PREVIEW.interventionCandidateCount;

  return {
    cityCount: trackedCities.length || DEFAULT_DASHBOARD_PREVIEW.cityCount,
    highRiskCorridorCount:
      summary && typeof summary === "object"
        ? Number((summary as Record<string, unknown>).high_risk_corridor_count ?? DEFAULT_DASHBOARD_PREVIEW.highRiskCorridorCount)
        : DEFAULT_DASHBOARD_PREVIEW.highRiskCorridorCount,
    interventionCandidateCount,
    monthlyRefreshCadence:
      summary && typeof summary === "object"
        ? String((summary as Record<string, unknown>).refresh_cadence_label ?? DEFAULT_DASHBOARD_PREVIEW.monthlyRefreshCadence)
        : DEFAULT_DASHBOARD_PREVIEW.monthlyRefreshCadence,
    signalCoverageLabel:
      summary && typeof summary === "object"
        ? String((summary as Record<string, unknown>).signal_coverage_label ?? DEFAULT_DASHBOARD_PREVIEW.signalCoverageLabel)
        : DEFAULT_DASHBOARD_PREVIEW.signalCoverageLabel,
    trackedCities: trackedCities.length > 0 ? trackedCities : DEFAULT_DASHBOARD_PREVIEW.trackedCities,
  };
}

export function sessionFromApiSnapshot(snapshot: ApiAuthSnapshot): PlatformSession {
  const assignedRoles = uniq(snapshot.assigned_roles).filter((role): role is PlatformRole =>
    ALL_ROLES.includes(role as PlatformRole),
  );
  const roles = uniq(snapshot.roles).filter((role): role is PlatformRole =>
    ALL_ROLES.includes(role as PlatformRole),
  );

  const liveSession = baseSession(snapshot.subject ? "live" : "public", {
    provider: snapshot.provider || "api",
    authEnabled: snapshot.auth_enabled,
    subject: snapshot.subject,
    displayName: snapshot.subject ?? "Public user",
    assignedRoles: assignedRoles.length > 0 ? assignedRoles : ["public"],
    roles: roles.length > 0 ? roles : ["public"],
    organizationIds: uniq(snapshot.organization_ids),
    municipalityIds: uniq(snapshot.municipality_ids),
    scopeCatalog: snapshot.scope_catalog ?? { organizations: [], municipalities: [] },
  });

  return applySessionContext(liveSession, liveSession.organizationIds[0] ?? null, liveSession.municipalityIds[0] ?? null);
}
