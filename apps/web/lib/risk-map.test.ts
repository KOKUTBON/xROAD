import { describe, expect, test } from "vitest";

import {
  featureIdentifier,
  featureLabel,
  formatCompactNumber,
  indexSegmentDetails,
  resolvePreferredCity,
} from "./risk-map";

describe("risk map helpers", () => {
  test("preferred municipality selects the matching city when available", () => {
    const selected = resolvePreferredCity(
      [
        {
          city_key: "bari",
          display_name: "Bari",
          prediction_run_label: "run-a",
          prediction_task: "segment_frequency_baseline",
          occurred_years: [2021],
          segment_score_rows: 10,
          tile_rows: 3,
          tile_size_m: 500,
          supports_junction_layer: true,
          supports_crossing_layer: true,
        },
        {
          city_key: "taranto",
          display_name: "Taranto",
          prediction_run_label: "run-b",
          prediction_task: "segment_frequency_baseline",
          occurred_years: [2021],
          segment_score_rows: 12,
          tile_rows: 4,
          tile_size_m: 500,
          supports_junction_layer: false,
          supports_crossing_layer: false,
        },
      ],
      "taranto",
    );

    expect(selected).toBe("taranto");
  });

  test("segment detail rows are indexed by score id", () => {
    const details = indexSegmentDetails([
      { segment_score_id: "run:1", segment_id: "s-1", public_score_band: "very_high" },
      { segment_score_id: "run:2", segment_id: "s-2", public_score_band: "high" },
    ]);

    expect(Object.keys(details)).toEqual(["run:1", "run:2"]);
    expect(details["run:2"].segment_id).toBe("s-2");
  });

  test("feature labels and identifiers fall back across supported property sets", () => {
    const segmentFeature = {
      type: "Feature" as const,
      geometry: { type: "LineString", coordinates: [] },
      properties: {
        segment_score_id: "run:1",
        segment_name: "Via Demo",
      },
    };
    const tileFeature = {
      type: "Feature" as const,
      geometry: { type: "Polygon", coordinates: [] },
      properties: {
        tile_score_id: "tile:1",
      },
    };

    expect(featureIdentifier(segmentFeature)).toBe("run:1");
    expect(featureLabel(segmentFeature)).toBe("Via Demo");
    expect(featureIdentifier(tileFeature)).toBe("tile:1");
    expect(featureLabel(tileFeature)).toBe("tile:1");
  });

  test("compact formatting keeps UI metrics readable", () => {
    expect(formatCompactNumber(13769)).toBe("13.8K");
    expect(formatCompactNumber("96.412")).toBe("96.4");
    expect(formatCompactNumber(null)).toBe("n/a");
  });
});
