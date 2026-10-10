import { describe, expect, it } from "vitest";

import {
  type ClimateFeature,
  climateRiskBand,
  climateRiskColor,
  filterByHazard,
  hazardLabel,
  summarizeClimate,
} from "./climate-overlay";

function feature(score: number, hazard: ClimateFeature["properties"]["dominant_hazard"]): ClimateFeature {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [16.8, 41.1] },
    properties: {
      segment_id: `s-${score}`,
      climate_risk_score: score,
      dominant_hazard: hazard,
      weather_conditioned_multiplier: 1,
    },
  };
}

describe("climate-overlay", () => {
  it("maps scores to ordered risk bands", () => {
    expect(climateRiskBand(0).id).toBe("low");
    expect(climateRiskBand(24).id).toBe("low");
    expect(climateRiskBand(25).id).toBe("moderate");
    expect(climateRiskBand(60).id).toBe("high");
    expect(climateRiskBand(90).id).toBe("severe");
  });

  it("gives distinct colours per band", () => {
    const colors = new Set([
      climateRiskColor(10),
      climateRiskColor(40),
      climateRiskColor(60),
      climateRiskColor(90),
    ]);
    expect(colors.size).toBe(4);
  });

  it("labels hazards and handles null", () => {
    expect(hazardLabel("snow_ice")).toBe("Snow / ice");
    expect(hazardLabel(null)).toBe("—");
  });

  it("summarizes a collection", () => {
    const features = [
      feature(10, "flood"),
      feature(60, "flood"),
      feature(80, "wind"),
      feature(30, null),
    ];
    const summary = summarizeClimate(features);
    expect(summary.total).toBe(4);
    expect(summary.maxScore).toBe(80);
    expect(summary.highRisk).toBe(2); // 60 and 80
    expect(summary.byHazard.flood).toBe(2);
    expect(summary.byHazard.wind).toBe(1);
    expect(summary.byBand.low).toBe(1);
    expect(summary.byBand.severe).toBe(1);
  });

  it("filters by dominant hazard", () => {
    const features = [feature(10, "flood"), feature(20, "wind"), feature(30, "flood")];
    expect(filterByHazard(features, null)).toHaveLength(3);
    expect(filterByHazard(features, "flood")).toHaveLength(2);
  });
});
