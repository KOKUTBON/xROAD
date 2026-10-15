import { describe, expect, it } from "vitest";

import {
  DEFAULT_INSTITUTION_CONFIG,
  computeHoverColor,
  computeTintColor,
  fetchInstitutionConfig,
  formatLocalizedDistance,
  formatLocalizedSpeed,
  hexToRgb,
} from "./institution";

describe("institution white-labeling", () => {
  it("converts hex to RGB correctly", () => {
    expect(hexToRgb("#ffffff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(hexToRgb("#000000")).toEqual({ r: 0, g: 0, b: 0 });
    expect(hexToRgb("#4B2A8C")).toEqual({ r: 75, g: 42, b: 140 });
    expect(hexToRgb("#fff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(hexToRgb("invalid")).toBeNull();
  });

  it("computes valid hover and tint colors", () => {
    const primary = "#0055A5"; // French Cerema Blue
    const hover = computeHoverColor(primary);
    const tint = computeTintColor(primary);

    expect(hover).toMatch(/^#[0-9a-f]{6}$/i);
    expect(tint).toMatch(/^#[0-9a-f]{6}$/i);
    expect(hover).not.toBe(primary);
    expect(tint).not.toBe(primary);
  });

  it("has valid default institutional configuration", () => {
    expect(DEFAULT_INSTITUTION_CONFIG.brand_name).toBe("xROAD");
    expect(DEFAULT_INSTITUTION_CONFIG.units.distance).toBe("km");
    expect(DEFAULT_INSTITUTION_CONFIG.units.speed).toBe("km/h");
    expect(DEFAULT_INSTITUTION_CONFIG.units.currency).toBe("EUR");
    expect(DEFAULT_INSTITUTION_CONFIG.driving_side).toBe("right");
  });

  it("formats distances according to unit preferences (km vs miles)", () => {
    expect(formatLocalizedDistance(500, "km")).toBe("500 m");
    expect(formatLocalizedDistance(2500, "km")).toBe("2.50 km");

    // UK / US miles preference
    expect(formatLocalizedDistance(50, "miles")).toBe("164 ft");
    expect(formatLocalizedDistance(1609.34, "miles")).toBe("1.00 mi");
  });

  it("formats speeds according to unit preferences (km/h vs mph)", () => {
    expect(formatLocalizedSpeed(50, "km/h")).toBe("50 km/h");
    expect(formatLocalizedSpeed(100, "mph")).toBe("62 mph");
    expect(formatLocalizedSpeed(50, "mph")).toBe("31 mph");
  });

  it("falls back to default config when API is unreachable", async () => {
    const config = await fetchInstitutionConfig();
    expect(config).toBeDefined();
    expect(config.brand_name).toBeDefined();
  });
});
