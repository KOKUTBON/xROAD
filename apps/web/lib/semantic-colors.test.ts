import { describe, expect, test } from "vitest";

import {
  confidenceColors,
  contrastRatio,
  governanceTierColors,
  positiveChangeColor,
  relativeLuminance,
  riskBandColors,
  simulatedColorblindHex,
  statusColors,
} from "./semantic-colors";

const SURFACE = "#FFFFFF";
const AA_NORMAL_TEXT = 4.5;
const AA_NON_TEXT = 3;

describe("semantic color system", () => {
  test("Cividis risk ramp increases in lightness and never reserves green for risk", () => {
    const ordered = [
      riskBandColors.low.fill,
      riskBandColors.moderate.fill,
      riskBandColors.high.fill,
      riskBandColors.very_high.fill,
    ];
    const luminance = ordered.map(relativeLuminance);

    for (let index = 1; index < luminance.length; index += 1) {
      expect(luminance[index]).toBeGreaterThan(luminance[index - 1]);
    }
    expect(ordered).not.toContain(positiveChangeColor);
  });

  test("risk ramp remains ordered under common red-green colorblind simulations", () => {
    for (const mode of ["deuteranopia", "protanopia"] as const) {
      const luminance = [
        riskBandColors.low.fill,
        riskBandColors.moderate.fill,
        riskBandColors.high.fill,
        riskBandColors.very_high.fill,
      ].map((color) => relativeLuminance(simulatedColorblindHex(color, mode)));

      for (let index = 1; index < luminance.length; index += 1) {
        expect(luminance[index]).toBeGreaterThan(luminance[index - 1]);
      }
    }
  });

  test("semantic text inks meet WCAG AA on white surfaces", () => {
    const inks = [
      ...Object.values(riskBandColors).map((color) => color.ink),
      ...Object.values(statusColors).map((color) => color.ink),
      ...Object.values(governanceTierColors).map((color) => color.ink),
      ...Object.values(confidenceColors).map((color) => color.ink),
      positiveChangeColor,
    ];

    for (const ink of inks) {
      expect(contrastRatio(ink, SURFACE)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
    }
  });

  test("status and action fills meet non-text contrast against white", () => {
    const fills = [
      ...Object.values(statusColors).map((color) => color.fill),
      positiveChangeColor,
    ];

    for (const fill of fills) {
      expect(contrastRatio(fill, SURFACE)).toBeGreaterThanOrEqual(AA_NON_TEXT);
    }
  });
});
