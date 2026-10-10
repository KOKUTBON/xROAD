import { describe, expect, test } from "vitest";

import {
  DEMO_PROFILES,
  PRIMARY_WORKFLOWS,
  PRODUCT_AREAS,
  ROUTE_EXPERIENCE_CONTRACTS,
  applySessionContext,
  buildNavigation,
  buildNavigationGroups,
  canAccessArea,
  normalizeDashboardPreview,
  resolveDefaultRoute,
  sessionFromApiSnapshot,
  type PlatformSession,
} from "./platform-shell";

describe("platform shell permissions", () => {
  test("public visitors stay on public routes", () => {
    const session = DEMO_PROFILES[0].session;

    expect(canAccessArea(session, "public")).toBe(true);
    expect(canAccessArea(session, "internal")).toBe(false);
    expect(resolveDefaultRoute(session)).toBe("/");
    expect(buildNavigation(session).map((item) => item.href)).toEqual(["/"]);
    expect(buildNavigationGroups(session).map((group) => group.id)).toEqual(["public"]);
  });

  test("analyst sessions unlock internal and analyst areas", () => {
    const session = DEMO_PROFILES[1].session;

    expect(canAccessArea(session, "internal")).toBe(true);
    expect(canAccessArea(session, "analyst")).toBe(true);
    expect(canAccessArea(session, "traffic_engineering")).toBe(false);
    expect(canAccessArea(session, "data_operations")).toBe(false);
    expect(canAccessArea(session, "admin")).toBe(false);
    expect(resolveDefaultRoute(session)).toBe("/workspace/analyst");
    expect(buildNavigation(session).map((item) => item.href)).toEqual([
      "/",
      "/workspace",
      "/workspace/executive",
      "/workspace/reports",
      "/workspace/analyst",
      "/workspace/scenarios",
      "/workspace/proposed-changes",
      "/workspace/siting-advisor",
      "/workspace/climate",
      "/workspace/research",
      "/workspace/digital-twin",
      "/workspace/forensics",
      "/workspace/tmc-playbooks",
      "/workspace/connected-fleets",
      "/workspace/incident-coordination",
    ]);
  });

  test("admin sessions unlock the full shell", () => {
    const session = DEMO_PROFILES[2].session;

    expect(canAccessArea(session, "admin")).toBe(true);
    expect(buildNavigation(session).map((item) => item.href)).toEqual([
      "/",
      "/workspace",
      "/workspace/executive",
      "/workspace/reports",
      "/workspace/analyst",
      "/workspace/scenarios",
      "/workspace/proposed-changes",
      "/workspace/siting-advisor",
      "/workspace/climate",
      "/workspace/research",
      "/workspace/digital-twin",
      "/workspace/forensics",
      "/workspace/tmc-playbooks",
      "/workspace/connected-fleets",
      "/workspace/incident-coordination",
      "/workspace/operations",
      "/workspace/admin",
      "/workspace/uploads",
      "/workspace/automation",
      "/workspace/system-health",
    ]);
  });

  test("data operators can use upload workflows without admin control access", () => {
    const session: PlatformSession = {
      ...DEMO_PROFILES[0].session,
      mode: "demo" as const,
      roles: ["public", "municipality_viewer", "data_operator"],
      organizationIds: ["org-puglia-safety-lab"],
      municipalityIds: ["bari"],
      selectedOrganizationId: "org-puglia-safety-lab",
      selectedMunicipalityId: "bari",
    };

    expect(canAccessArea(session, "data_operations")).toBe(true);
    expect(canAccessArea(session, "admin")).toBe(false);
    expect(buildNavigation(session).map((item) => item.href)).toEqual([
      "/",
      "/workspace",
      "/workspace/executive",
      "/workspace/reports",
      "/workspace/uploads",
    ]);
  });

  test("traffic engineer sessions default to operational workflows", () => {
    const session = DEMO_PROFILES[3].session;

    expect(canAccessArea(session, "traffic_engineering")).toBe(true);
    expect(canAccessArea(session, "analyst")).toBe(true);
    expect(canAccessArea(session, "data_operations")).toBe(false);
    expect(canAccessArea(session, "admin")).toBe(false);
    expect(resolveDefaultRoute(session)).toBe("/workspace/operations");
    expect(buildNavigationGroups(session).map((group) => group.id)).toEqual([
      "public",
      "executive",
      "analyst",
      "traffic",
    ]);
  });
});

describe("platform shell information architecture", () => {
  test("product areas cover the release sitemap groups", () => {
    expect(PRODUCT_AREAS.map((area) => area.id)).toEqual([
      "public",
      "executive",
      "analyst",
      "traffic",
      "admin",
    ]);
  });

  test("primary workflows cover top municipal tasks", () => {
    expect(PRIMARY_WORKFLOWS.map((workflow) => workflow.id)).toEqual([
      "public-risk-inspection",
      "analyst-hotspot-inspection",
      "report-generation",
      "ingestion-status-review",
      "governance-review",
    ]);
  });

  test("route experience contracts cover every v1 route and required state", () => {
    expect(ROUTE_EXPERIENCE_CONTRACTS.map((route) => route.route)).toEqual([
      "/",
      "/login",
      "/workspace",
      "/workspace/executive",
      "/workspace/analyst",
      "/workspace/scenarios",
      "/workspace/proposed-changes",
      "/workspace/siting-advisor",
      "/workspace/research",
      "/workspace/digital-twin",
      "/workspace/forensics",
      "/workspace/tmc-playbooks",
      "/workspace/connected-fleets",
      "/workspace/incident-coordination",
      "/workspace/operations",
      "/workspace/reports",
      "/workspace/admin",
      "/workspace/uploads",
      "/workspace/automation",
      "/workspace/system-health",
    ]);

    for (const route of ROUTE_EXPERIENCE_CONTRACTS) {
      expect(route.audience.length).toBeGreaterThan(8);
      expect(route.primaryTask.length).toBeGreaterThan(24);
      expect(route.requiredStates.length).toBeGreaterThan(0);
    }
  });
});

describe("platform shell context", () => {
  test("context selection is clamped to the allowed organization and municipality scope", () => {
    const session = DEMO_PROFILES[1].session;
    const next = applySessionContext(session, "org-bari-mobility", "modugno");

    expect(next.selectedOrganizationId).toBe("org-bari-mobility");
    expect(next.selectedMunicipalityId).toBe("modugno");

    const invalid = applySessionContext(session, "org-puglia-safety-lab", "lecce");
    expect(invalid.selectedOrganizationId).toBe("org-bari-mobility");
    expect(invalid.selectedMunicipalityId).toBe("bari");
  });
});

describe("platform shell data normalization", () => {
  test("api auth snapshots become live sessions", () => {
    const session = sessionFromApiSnapshot({
      auth_enabled: true,
      provider: "keycloak",
      subject: "admin.demo",
      assigned_roles: ["admin"],
      roles: ["public", "municipality_viewer", "analyst", "admin"],
      organization_ids: ["org-puglia-safety-lab"],
      municipality_ids: ["bari", "lecce"],
      scope_catalog: {
        organizations: [{ id: "org-puglia-safety-lab", name: "Puglia", shortLabel: "Puglia", municipalityIds: ["bari", "lecce"] }],
        municipalities: [{ id: "bari", name: "Bari", regionLabel: "Puglia", coverageLabel: "pilot" }, { id: "lecce", name: "Lecce", regionLabel: "Puglia", coverageLabel: "pilot" }],
      },
    });

    expect(session.mode).toBe("live");
    expect(session.provider).toBe("keycloak");
    expect(session.selectedOrganizationId).toBe("org-puglia-safety-lab");
    expect(session.selectedMunicipalityId).toBe("bari");
  });

  test("dashboard preview falls back cleanly when payloads are partial", () => {
    const preview = normalizeDashboardPreview({
      summary: {
        published_runs: [
          { municipality_name: "Bari" },
          { municipality_name: "Taranto" },
        ],
        intervention_candidate_count: 31,
      },
    });

    expect(preview.cityCount).toBe(2);
    expect(preview.interventionCandidateCount).toBe(31);
    expect(preview.trackedCities).toEqual(["Bari", "Taranto"]);
  });
});
