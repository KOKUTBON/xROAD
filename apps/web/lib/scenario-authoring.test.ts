import { describe, expect, it } from "vitest";

import {
  buildScenarioDraftPayload,
  parseAssumptionsText,
  summarizeBeforeAfter,
} from "./scenario-authoring";

describe("scenario authoring helpers", () => {
  it("splits assumptions by lines and semicolons", () => {
    expect(parseAssumptionsText("Speed limit approved\nWorks funded;Police support")).toEqual([
      "Speed limit approved",
      "Works funded",
      "Police support",
    ]);
  });

  it("builds a clean draft payload with numeric parameters", () => {
    const payload = buildScenarioDraftPayload({
      organizationId: "org-1",
      cityKey: "bari",
      form: {
        name: "  Speed package ",
        interventionCode: " speed_management ",
        targetContextKey: "top_corridor",
        targetContextLabel: "Tangenziale",
        baselinePredictedCrashTotal: "39.14",
        expectedRelativeReduction: "0.28",
        costClass: "medium",
        uncertainty: "medium-high",
        assumptionsText: "Signs approved",
      },
    });

    expect(payload.name).toBe("Speed package");
    expect(payload.intervention_code).toBe("speed_management");
    expect(payload.parameters).toEqual({
      baseline_predicted_crash_total: 39.14,
      expected_relative_reduction: 0.28,
    });
    expect(payload.assumptions).toEqual(["Signs approved"]);
  });

  it("summarizes before and after totals for run history", () => {
    expect(
      summarizeBeforeAfter({
        baseline_predicted_crash_total: 39.14,
        counterfactual_predicted_crash_total: 28.18,
        expected_crash_reduction: 10.96,
        expected_relative_reduction: 0.28,
      }),
    ).toContain("39.14 -> 28.18 crashes/year");
  });
});
