import { describe, expect, it } from "vitest";

import { complianceSummary, riskColor, suitabilityColor } from "./siting-advisor";

describe("siting advisor presentation", () => {
  it("uses stable suitability and risk bands", () => {
    expect(suitabilityColor(0.8)).toBe("#18794e");
    expect(suitabilityColor(0.65)).toBe("#d97706");
    expect(riskColor(90)).toBe("#b42318");
    expect(riskColor(20)).toBe("#2563eb");
  });

  it("summarizes cited compliance without hiding warnings", () => {
    expect(
      complianceSummary([
        {
          rule_id: "one",
          status: "pass",
          severity: "mandatory",
          citation: "law",
          source_url: "https://example.test",
          description: "rule",
        },
        {
          rule_id: "two",
          status: "fail",
          severity: "advisory",
          citation: "guidance",
          source_url: "https://example.test",
          description: "rule",
        },
      ]),
    ).toBe("1/2 rules passed · 1 advisory warnings");
  });
});
