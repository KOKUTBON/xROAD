import { describe, expect, test } from "vitest";

import {
  buildRiskMapSearchParams,
  normalizeScoreBandFilter,
  parseLayerVisibility,
  serializeLayerVisibility,
} from "./map-state";

describe("risk map URL and layer state", () => {
  test("normalizes score-band filters with a safe fallback", () => {
    expect(normalizeScoreBandFilter("very_high", "high")).toBe("very_high");
    expect(normalizeScoreBandFilter("all", "high")).toBe("all");
    expect(normalizeScoreBandFilter("critical", "high")).toBe("high");
    expect(normalizeScoreBandFilter(null, "moderate")).toBe("moderate");
  });

  test("parses and serializes analyst layer visibility", () => {
    const fallback = { segments: true, junctions: true, crossings: false };

    expect(parseLayerVisibility("segments,crossings,unknown", fallback)).toEqual({
      segments: true,
      junctions: false,
      crossings: true,
    });
    expect(parseLayerVisibility("", fallback)).toEqual(fallback);
    expect(
      serializeLayerVisibility({ segments: true, junctions: false, crossings: true }),
    ).toBe("segments,crossings");
  });

  test("builds stable shareable search params", () => {
    expect(
      buildRiskMapSearchParams("city=bari&year=2021", {
        band: "very_high",
        feature: "tile:7",
        year: null,
      }),
    ).toBe("?band=very_high&city=bari&feature=tile%3A7");
  });
});
