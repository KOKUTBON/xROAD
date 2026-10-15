import type { ScoreBand } from "./risk-map";

/**
 * Canonical risk-ramp legend (#180 / #172).
 *
 * The single ordered source for how the risk ramp is explained in the UI:
 * sequential by lightness (minimal → very high, never green), each entry paired
 * with its design token (not a raw hex) and a one-word meaning. The MapLibre
 * paint reads the same band colors from `semantic-colors`, so the legend and
 * the map can never disagree on order or meaning.
 */

export type RiskBand = ScoreBand | "minimal";

export interface RiskLegendEntry {
  band: RiskBand;
  label: string;
  meaning: string;
  /** Design-token CSS variable for the band fill — keeps the legend token-bound. */
  cssVar: string;
}

export const RISK_LEGEND: RiskLegendEntry[] = [
  { band: "minimal", label: "Minimal", meaning: "Below action threshold", cssVar: "var(--color-risk-minimal-fill)" },
  { band: "low", label: "Low", meaning: "Monitored", cssVar: "var(--color-risk-low-fill)" },
  { band: "moderate", label: "Moderate", meaning: "Watch", cssVar: "var(--color-risk-moderate-fill)" },
  { band: "high", label: "High", meaning: "Priority", cssVar: "var(--color-risk-high-fill)" },
  { band: "very_high", label: "Very high", meaning: "Urgent", cssVar: "var(--color-risk-very-high-fill)" },
];

/** Legend entry for a band, defaulting to "minimal" for null/unknown. */
export function legendEntryForBand(band: ScoreBand | null | undefined): RiskLegendEntry {
  return RISK_LEGEND.find((entry) => entry.band === (band ?? "minimal")) ?? RISK_LEGEND[0];
}
