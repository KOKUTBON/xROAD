import { describe, expect, it } from "vitest";

import { riskBandColors } from "./semantic-colors";
import { legendEntryForBand, RISK_LEGEND, type RiskBand } from "./risk-legend";

describe("risk legend", () => {
  it("is ordered by ascending severity (minimal → very high)", () => {
    expect(RISK_LEGEND.map((entry) => entry.band)).toEqual([
      "minimal",
      "low",
      "moderate",
      "high",
      "very_high",
    ]);
  });

  it("covers every band that semantic-colors defines", () => {
    const legendBands = new Set<RiskBand>(RISK_LEGEND.map((entry) => entry.band));
    for (const band of Object.keys(riskBandColors) as RiskBand[]) {
      expect(legendBands.has(band)).toBe(true);
    }
  });

  it("binds every entry to a design token (no raw hex)", () => {
    for (const entry of RISK_LEGEND) {
      expect(entry.cssVar).toMatch(/^var\(--color-risk-[a-z-]+-fill\)$/);
    }
  });

  it("never uses green wording in the ramp (green is reserved for positive change)", () => {
    for (const entry of RISK_LEGEND) {
      expect(entry.label.toLowerCase()).not.toContain("green");
    }
  });

  it("maps null/unknown bands to the minimal entry", () => {
    expect(legendEntryForBand(null).band).toBe("minimal");
    expect(legendEntryForBand(undefined).band).toBe("minimal");
    expect(legendEntryForBand("high").label).toBe("High");
  });
});
