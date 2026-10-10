// Shared baseline scenario model (#167 audit, #184 capture runner).
//
// Single source of truth for the demo personas, routes, viewports, and the
// `persona × route × viewport` capture matrix. Both `smoke-routes.mjs` (server
// reachability + guardrail smoke, manifest writer) and the Playwright capture
// runner (`e2e/baseline-capture.spec.ts`) import from here so the manifest and
// the screenshots can never describe different scenario sets.

import path from "node:path";

export const DEFAULT_BASE_URL = "http://localhost:3000";
export const DEFAULT_OUTPUT_DIR = path.join("docs", "ui-baseline");

export const viewports = [
  { viewport: "desktop", width: 1440, height: 960 },
  { viewport: "mobile", width: 390, height: 844 },
];

// Capture each scenario in both themes so light/dark contrast is
// regression-guarded by the visual baselines (#260, UX 2.0).
export const themes = ["light", "dark"];

export const personas = [
  {
    id: "public",
    label: "Public visitor",
    roles: ["public"],
    topTasks: [
      "Inspect public risk tiles and safe corridor details.",
      "Open public reports and methodology-safe explanations.",
      "Confirm no restricted records are exposed.",
    ],
  },
  {
    id: "analyst_bari",
    label: "Bari analyst",
    roles: ["public", "municipality_viewer", "analyst"],
    topTasks: [
      "Filter internal risk layers and select high-priority places.",
      "Compare scenario benefits and treatment assumptions.",
      "Generate or review technical reports for Bari.",
    ],
  },
  {
    id: "admin_regional",
    label: "Regional admin",
    roles: [
      "public",
      "municipality_viewer",
      "analyst",
      "data_operator",
      "traffic_engineer",
      "admin",
    ],
    topTasks: [
      "Review publication tiers, source governance, and audit posture.",
      "Register uploads and approve or reject ingestion jobs.",
      "Validate automation, health, and release-readiness evidence.",
    ],
  },
  {
    id: "traffic_engineer_bari",
    label: "Bari traffic engineer",
    roles: ["public", "municipality_viewer", "analyst", "traffic_engineer"],
    topTasks: [
      "Review VRU priorities, signal coverage, and ready actions.",
      "Investigate map hotspots that affect signal-phase work.",
      "Track degraded operational states and holds.",
    ],
  },
];

export const routes = [
  {
    route: "/",
    area: "public",
    accessArea: "public",
    audience: "Citizens and public stakeholders",
    primaryTask: "Filter public risk tiles, inspect a safe detail panel, and open public reports.",
    layoutPattern: "public-map",
    requiredStates: ["loading", "empty", "error", "degraded"],
  },
  {
    route: "/login",
    area: "auth",
    accessArea: "public",
    audience: "All authenticated municipal users",
    primaryTask: "Enter through the municipal identity provider or a non-production demo profile.",
    layoutPattern: "dashboard",
    requiredStates: ["error", "no-access"],
  },
  {
    route: "/workspace",
    area: "executive",
    accessArea: "internal",
    audience: "Municipal viewers and operators",
    primaryTask: "Understand scope, available product areas, and the next workflow to open.",
    layoutPattern: "workspace-overview",
    requiredStates: ["no-access"],
  },
  {
    route: "/workspace/executive",
    area: "executive",
    accessArea: "internal",
    audience: "Mayors, directors, and department leads",
    primaryTask: "Review safety burden, priority investments, budget impact, and monthly posture.",
    layoutPattern: "dashboard",
    requiredStates: ["no-access", "degraded"],
  },
  {
    route: "/workspace/analyst",
    area: "analyst",
    accessArea: "analyst",
    audience: "Mobility analysts and planners",
    primaryTask: "Filter internal risk layers, select features, and triage high-priority places.",
    layoutPattern: "map-workbench",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/scenarios",
    area: "analyst",
    accessArea: "analyst",
    audience: "Planners and intervention portfolio owners",
    primaryTask: "Compare countermeasures, ranked scenarios, portfolios, and treatment assumptions.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/operations",
    area: "traffic",
    accessArea: "traffic_engineering",
    audience: "Traffic engineers and VRU planners",
    primaryTask: "Review VRU priorities, signal coverage, ready actions, and holds.",
    layoutPattern: "operations-board",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/reports",
    area: "executive",
    accessArea: "internal",
    audience: "Executives, analysts, and report publishers",
    primaryTask: "Generate, review, download, and publish executive or technical reports.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/admin",
    area: "admin",
    accessArea: "admin",
    audience: "Data operators, admins, and governance reviewers",
    primaryTask: "Review data sources, ingestion jobs, publication tiers, members, and audit posture.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/uploads",
    area: "admin",
    accessArea: "data_operations",
    audience: "Data operators, admins, and ingestion reviewers",
    primaryTask: "Register files, map schemas, upload to object storage, validate payloads, and approve or reject jobs.",
    layoutPattern: "table-workbench",
    requiredStates: ["loading", "empty", "error", "no-access", "degraded"],
  },
  {
    route: "/workspace/automation",
    area: "admin",
    accessArea: "admin",
    audience: "Platform admins and operations owners",
    primaryTask: "Review schedules, runs, notifications, and request manual refreshes.",
    layoutPattern: "operations-board",
    requiredStates: ["loading", "empty", "error", "no-access"],
  },
  {
    route: "/workspace/system-health",
    area: "admin",
    accessArea: "admin",
    audience: "Platform owners and release managers",
    primaryTask: "Track readiness evidence, operational checks, smoke tests, and promotion gates.",
    layoutPattern: "operations-board",
    requiredStates: ["no-access", "degraded"],
  },
  {
    route: "/workspace/_design",
    area: "admin",
    accessArea: "internal",
    audience: "Design-system reviewers and frontend engineers",
    primaryTask: "Review P0 components, interaction states, density, and token usage.",
    layoutPattern: "dashboard",
    requiredStates: ["no-access"],
  },
];

export const accessByArea = {
  public: ["public"],
  internal: ["municipality_viewer", "analyst", "data_operator", "traffic_engineer", "admin", "super_admin"],
  analyst: ["analyst", "traffic_engineer", "admin", "super_admin"],
  traffic_engineering: ["traffic_engineer", "admin", "super_admin"],
  data_operations: ["data_operator", "admin", "super_admin"],
  admin: ["admin", "super_admin"],
};

export function canAccessRoute(persona, route) {
  return accessByArea[route.accessArea].some((role) => persona.roles.includes(role));
}

export function captureSlug(route, persona, viewport, theme = "light") {
  const routeSlug = route.route === "/" ? "home" : route.route.replace(/^\//, "").replace(/\//g, "__");
  return `${persona.id}__${viewport.viewport}__${theme}__${routeSlug}`;
}

export function scenarioFor(
  route,
  persona,
  viewport,
  theme = "light",
  baseUrl = DEFAULT_BASE_URL,
  outputDir = DEFAULT_OUTPUT_DIR,
) {
  const slug = captureSlug(route, persona, viewport, theme);
  return {
    id: slug,
    route: route.route,
    url: new URL(route.route, baseUrl).toString(),
    viewport,
    theme,
    persona: {
      id: persona.id,
      label: persona.label,
      roles: persona.roles,
      topTasks: persona.topTasks,
    },
    contract: {
      area: route.area,
      audience: route.audience,
      primaryTask: route.primaryTask,
      layoutPattern: route.layoutPattern,
      requiredStates: route.requiredStates,
    },
    expectedAccess: canAccessRoute(persona, route) ? "allowed" : "no-access",
    screenshotPath: path.join(outputDir, "screenshots", `${slug}.png`),
  };
}

export function allScenarios(baseUrl = DEFAULT_BASE_URL, outputDir = DEFAULT_OUTPUT_DIR) {
  return personas.flatMap((persona) =>
    viewports.flatMap((viewport) =>
      themes.flatMap((theme) =>
        routes.map((route) => scenarioFor(route, persona, viewport, theme, baseUrl, outputDir)),
      ),
    ),
  );
}

export function buildManifest(results, baseUrl = DEFAULT_BASE_URL, outputDir = DEFAULT_OUTPUT_DIR) {
  const scenarios = allScenarios(baseUrl, outputDir);
  return {
    generatedAt: new Date().toISOString(),
    baseUrl,
    scenarioCount: scenarios.length,
    routeCount: routes.length,
    viewportCount: viewports.length,
    personaCount: personas.length,
    themeCount: themes.length,
    notes: [
      "Run this smoke with NEXT_PUBLIC_ENABLE_DEMO_AUTH=true or WEB_SMOKE_DEMO_AUTH=true for local demo review.",
      "screenshotPath records the required capture target for browser automation or manual QA.",
      "The default smoke validates server reachability and protected-route guardrails without requiring a browser dependency.",
      "Run `npm run baseline:capture` (Playwright) to fulfil every screenshotPath from this manifest.",
    ],
    smokeResults: results,
    scenarios,
  };
}
