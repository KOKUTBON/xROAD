import { describe, expect, it } from "vitest";

import {
  buildPortfolioCreateFromRunPayload,
  buildPortfolioStatusUpdatePayload,
  summarizePortfolioRow,
} from "./intervention-portfolio";

describe("intervention portfolio helpers", () => {
  it("builds a scenario-run portfolio create payload", () => {
    expect(
      buildPortfolioCreateFromRunPayload({
        organizationId: "org-1",
        cityKey: "bari",
        scenarioRunId: "run:abc",
        ownerSubject: "analyst-1",
      }),
    ).toEqual({
      organization_id: "org-1",
      city_key: "bari",
      scenario_run_id: "run:abc",
      status: "shortlisted",
      owner_subject: "analyst-1",
    });
  });

  it("builds a status update payload", () => {
    expect(
      buildPortfolioStatusUpdatePayload({
        organizationId: "org-1",
        status: "planned",
        notes: "Ready for engineering review",
      }),
    ).toEqual({
      organization_id: "org-1",
      status: "planned",
      owner_subject: undefined,
      notes: "Ready for engineering review",
    });
  });

  it("summarizes rankable portfolio rows", () => {
    expect(
      summarizePortfolioRow({
        target_label: "Tangenziale",
        intervention_type: "speed_management",
        status: "planned",
        expected_benefit: 7.0452,
        priority_score: 3.5226,
      }),
    ).toContain("Tangenziale · speed_management · planned");
  });
});
