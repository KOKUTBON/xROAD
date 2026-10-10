import { describe, expect, it } from "vitest";
import { DEFAULT_INSTITUTION_CONFIG } from "./institution";
import { institutionRouteEnabled, moduleForRoute } from "./institution-product";
import { applySessionContext, buildNavigation, DEMO_PROFILES, sessionFromApiSnapshot, sessionMunicipalities, sessionOrganizations } from "./platform-shell";

const institution = { ...DEFAULT_INSTITUTION_CONFIG, deployment: { schema_version: 1, profile: "police", enabled_modules: ["administration", "risk_analysis", "reporting", "forensics"] as const, revision: "test" } };
const config = { ...institution, deployment: { ...institution.deployment, enabled_modules: [...institution.deployment.enabled_modules] } };
const snapshot = {
  auth_enabled: true, provider: "institution-idp", subject: "analyst-a", assigned_roles: ["analyst"], roles: ["analyst"],
  organization_ids: ["agency-a"], municipality_ids: ["city-a"],
  scope_catalog: {
    organizations: [{ id: "agency-a", name: "Agency A", shortLabel: "Agency", municipalityIds: ["city-a", "city-b"] }],
    municipalities: [{ id: "city-a", name: "City A", regionLabel: "Region", coverageLabel: "awaiting data" }, { id: "city-b", name: "City B", regionLabel: "Region", coverageLabel: "awaiting data" }],
  },
};

describe("institution product configuration", () => {
  it("filters navigation by both module selection and role", () => {
    const session = { ...DEMO_PROFILES[2].session, roles: ["super_admin"] as const };
    const nav = buildNavigation({ ...session, roles: [...session.roles] }, config);
    expect(nav.some((item) => item.href === "/workspace/forensics")).toBe(true);
    expect(nav.some((item) => item.href === "/workspace/scenarios")).toBe(false);
    expect(nav.some((item) => item.href === "/")).toBe(false);
    expect(buildNavigation(sessionFromApiSnapshot(snapshot), config).some((item) => item.href === "/workspace/admin")).toBe(false);
  });
  it("checks nested routes with exact boundaries", () => {
    expect(institutionRouteEnabled(config, "/workspace/scenarios/draft/1")).toBe(false);
    expect(moduleForRoute("/workspace/scenarios-extra")).toBeUndefined();
    expect(institutionRouteEnabled(config, "/workspace")).toBe(true);
  });
  it("uses configured institutions instead of sample Bari organizations", () => {
    const session = sessionFromApiSnapshot(snapshot);
    expect(session.selectedOrganizationId).toBe("agency-a");
    expect(session.selectedMunicipalityId).toBe("city-a");
    expect(sessionOrganizations(session).map((row) => row.id)).toEqual(["agency-a"]);
    expect(sessionMunicipalities(session).map((row) => row.id)).toEqual(["city-a"]);
  });
  it("cannot switch to an unassigned city through its organization's larger scope", () => {
    const session = sessionFromApiSnapshot(snapshot);
    expect(applySessionContext(session, "agency-a", "city-b").selectedMunicipalityId).toBe("city-a");
  });
  it("does not grant sample or default access when live claims/catalogs are empty", () => {
    const noCatalog = sessionFromApiSnapshot({ ...snapshot, scope_catalog: undefined });
    expect(noCatalog.selectedOrganizationId).toBeNull();
    expect(noCatalog.selectedMunicipalityId).toBeNull();
    const noAssignment = sessionFromApiSnapshot({ ...snapshot, organization_ids: [], municipality_ids: [] });
    expect(sessionOrganizations(noAssignment)).toEqual([]);
    expect(sessionMunicipalities(noAssignment)).toEqual([]);
  });
  it("keeps explicit development demos available", () => {
    expect(sessionMunicipalities(DEMO_PROFILES[1].session).length).toBeGreaterThan(0);
  });
});
