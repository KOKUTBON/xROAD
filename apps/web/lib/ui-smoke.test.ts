import { describe, expect, test } from "vitest";

import { PRIMARY_WORKFLOWS, ROUTE_EXPERIENCE_CONTRACTS } from "./platform-shell";
import { BROWSER_SMOKE_ROUTES } from "./ui-smoke";

describe("browser smoke route contract", () => {
  test("all v1 product routes require desktop and mobile checks", () => {
    expect(BROWSER_SMOKE_ROUTES.map((route) => route.route)).toEqual([
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

    for (const route of BROWSER_SMOKE_ROUTES) {
      expect(route.requiredViewports).toEqual(["desktop", "mobile"]);
    }
  });

  test("smoke routes match the route experience contract", () => {
    expect(BROWSER_SMOKE_ROUTES.map((route) => route.route)).toEqual(
      ROUTE_EXPERIENCE_CONTRACTS.map((route) => route.route),
    );
  });

  test("primary workflows are represented in the smoke matrix", () => {
    const smokeWorkflows = new Set(BROWSER_SMOKE_ROUTES.map((route) => route.workflow));
    for (const workflow of PRIMARY_WORKFLOWS) {
      if (workflow.id === "governance-review") {
        expect(smokeWorkflows.has("ingestion-and-governance-review")).toBe(true);
      } else if (workflow.id === "ingestion-status-review") {
        expect(smokeWorkflows.has("ingestion-and-governance-review")).toBe(true);
      } else {
        expect(smokeWorkflows.has(workflow.id)).toBe(true);
      }
    }
  });
});
