/**
 * Climate-resilience map overlay helpers.
 *
 * Pure, dependency-free helpers for rendering the climate-risk GeoJSON surface
 * produced by `road_risk_modeling.climate_resilience` on the MapLibre map, so
 * authorities can see where extreme weather most degrades network safety
 *
 *
 * Kept free of React / MapLibre imports so the colour scale and summary logic
 * are unit-testable.
 */

export const HAZARD_KINDS = ["flood", "heat", "snow_ice", "wind"] as const;
export type HazardKind = (typeof HAZARD_KINDS)[number];

export interface ClimateFeatureProperties {
  segment_id: string;
  climate_risk_score: number;
  dominant_hazard: HazardKind | null;
  weather_conditioned_multiplier: number | null;
  forecast_at_utc?: string;
}

export interface ClimateFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: ClimateFeatureProperties;
}

export interface ClimateFeatureCollection {
  type: "FeatureCollection";
  features: ClimateFeature[];
}

/** Ordered risk bands (low → severe) used for the colour scale and legend. */
export const CLIMATE_RISK_BANDS = [
  { id: "low", label: "Low", min: 0, color: "#2f9e44" },
  { id: "moderate", label: "Moderate", min: 25, color: "#f0a202" },
  { id: "high", label: "High", min: 50, color: "#e8590c" },
  { id: "severe", label: "Severe", min: 75, color: "#c92a2a" },
] as const;

export type ClimateRiskBand = (typeof CLIMATE_RISK_BANDS)[number];
export type ClimateRiskBandId = ClimateRiskBand["id"];

export function climateRiskBand(score: number): ClimateRiskBand {
  let band: ClimateRiskBand = CLIMATE_RISK_BANDS[0];
  for (const candidate of CLIMATE_RISK_BANDS) {
    if (score >= candidate.min) {
      band = candidate;
    }
  }
  return band;
}

export function climateRiskColor(score: number): string {
  return climateRiskBand(score).color;
}

const HAZARD_LABELS: Record<HazardKind, string> = {
  flood: "Flood",
  heat: "Heat",
  snow_ice: "Snow / ice",
  wind: "Wind",
};

export function hazardLabel(kind: HazardKind | null): string {
  return kind ? HAZARD_LABELS[kind] : "—";
}

export interface ClimateSummary {
  total: number;
  meanScore: number;
  maxScore: number;
  highRisk: number;
  byHazard: Record<string, number>;
  byBand: Record<ClimateRiskBandId, number>;
}

export function summarizeClimate(features: ClimateFeature[]): ClimateSummary {
  const total = features.length;
  const byHazard: Record<string, number> = {};
  const byBand: Record<ClimateRiskBandId, number> = {
    low: 0,
    moderate: 0,
    high: 0,
    severe: 0,
  };
  let scoreSum = 0;
  let maxScore = 0;
  let highRisk = 0;
  for (const feature of features) {
    const score = feature.properties.climate_risk_score;
    scoreSum += score;
    maxScore = Math.max(maxScore, score);
    if (score >= 50) {
      highRisk += 1;
    }
    byBand[climateRiskBand(score).id] += 1;
    const hazard = feature.properties.dominant_hazard;
    if (hazard) {
      byHazard[hazard] = (byHazard[hazard] ?? 0) + 1;
    }
  }
  return {
    total,
    meanScore: total ? Math.round((scoreSum / total) * 100) / 100 : 0,
    maxScore,
    highRisk,
    byHazard,
    byBand,
  };
}

/** Filter a collection to a single dominant hazard (or all when null). */
export function filterByHazard(
  features: ClimateFeature[],
  hazard: HazardKind | null,
): ClimateFeature[] {
  if (hazard === null) {
    return features;
  }
  return features.filter((feature) => feature.properties.dominant_hazard === hazard);
}
