export type ScoreBand = "low" | "moderate" | "high" | "very_high";
export type ScoreBandFilter = ScoreBand | "all";

export interface PublicCityRecord {
  city_key: string;
  display_name: string;
  prediction_run_label: string | null;
  prediction_task: string | null;
  occurred_years: number[];
  segment_score_rows: number | null;
  tile_rows: number | null;
  tile_size_m: number | null;
  supports_junction_layer: boolean;
  supports_crossing_layer: boolean;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates: unknown;
}

export interface GeoJsonFeature {
  type: "Feature";
  geometry: GeoJsonGeometry;
  properties: Record<string, unknown>;
}

export interface GeoJsonFeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

export interface PublishedMapResource {
  resource_name: string;
  view: string;
  contract_version: string | null;
  manifest_path: string;
  query: {
    occurred_year: number | null;
    min_score_band: ScoreBand | null;
    limit: number | null;
  };
  source_stats: Record<string, unknown>;
  stats: Record<string, unknown>;
  data: GeoJsonFeatureCollection;
}

export interface PublicRiskMapPayload {
  api_version: string;
  city: PublicCityRecord;
  filters: {
    occurred_year: number | null;
    min_score_band: ScoreBand | null;
    limit: number | null;
  };
  summary: Record<string, unknown>;
  map_resource: PublishedMapResource;
}

export interface InterventionShortlistPayload {
  api_version: string;
  city: PublicCityRecord;
  intervention_shortlist: {
    top_corridors: Array<Record<string, unknown>>;
    hotspot_tiles: Array<Record<string, unknown>>;
  };
}

export interface AnalystRiskMapPayload {
  api_version: string;
  city: PublicCityRecord;
  filters: {
    occurred_year: number | null;
    min_score_band: ScoreBand | null;
    limit: number | null;
    junction_limit: number | null;
    crossing_limit: number | null;
  };
  segment_layer: PublishedMapResource;
  segment_details: {
    contract_version: string | null;
    stats: Record<string, unknown>;
    rows: Array<Record<string, string>>;
  };
  support_layers: {
    junctions: {
      availability: string;
      reason?: string;
      stats: Record<string, unknown>;
      resolved_year?: number | null;
      data: GeoJsonFeatureCollection;
    };
    crossings: {
      availability: string;
      reason?: string;
      stats: Record<string, unknown>;
      ranking_field?: string;
      data: GeoJsonFeatureCollection;
    };
  };
}

export const SCORE_BAND_OPTIONS: Array<{ value: ScoreBandFilter; label: string }> = [
  { value: "all", label: "All bands" },
  { value: "high", label: "High +" },
  { value: "very_high", label: "Very high only" },
  { value: "moderate", label: "Moderate +" },
  { value: "low", label: "Low +" },
];

function coerceString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function resolvePreferredCity(
  cities: PublicCityRecord[],
  preferredMunicipalityId: string | null,
): string | null {
  if (cities.length === 0) {
    return null;
  }
  if (preferredMunicipalityId) {
    const matched = cities.find((city) => city.city_key === preferredMunicipalityId);
    if (matched) {
      return matched.city_key;
    }
  }
  return cities[0].city_key;
}

export function cityYears(city: PublicCityRecord | null): number[] {
  return city ? [...city.occurred_years].sort((left, right) => right - left) : [];
}

export function featureIdentifier(feature: GeoJsonFeature): string {
  return (
    coerceString(feature.properties.segment_score_id) ||
    coerceString(feature.properties.tile_score_id) ||
    coerceString(feature.properties.node_object_id) ||
    coerceString(feature.properties.crossing_id) ||
    coerceString(feature.properties.junction_id) ||
    JSON.stringify(feature.geometry)
  );
}

export function featureBand(feature: GeoJsonFeature): ScoreBand | null {
  const value =
    coerceString(feature.properties.public_score_band) ||
    coerceString(feature.properties.tile_public_score_band);
  if (value === "low" || value === "moderate" || value === "high" || value === "very_high") {
    return value;
  }
  return null;
}

export function featureLabel(feature: GeoJsonFeature): string {
  return (
    coerceString(feature.properties.segment_label) ||
    coerceString(feature.properties.segment_name) ||
    coerceString(feature.properties.crossing_name) ||
    coerceString(feature.properties.corridor_label) ||
    coerceString(feature.properties.name) ||
    coerceString(feature.properties.tile_score_id) ||
    coerceString(feature.properties.segment_id) ||
    coerceString(feature.properties.node_object_id) ||
    "Unnamed feature"
  );
}

export function indexSegmentDetails(
  rows: Array<Record<string, string>>,
): Record<string, Record<string, string>> {
  const entries = rows
    .map((row) => {
      const identifier = row.segment_score_id || row.segment_id;
      return identifier ? [identifier, row] : null;
    })
    .filter((entry): entry is [string, Record<string, string>] => entry !== null);
  return Object.fromEntries(entries);
}

export function formatCompactNumber(value: unknown): string {
  const numeric =
    typeof value === "number" ? value : typeof value === "string" ? Number.parseFloat(value) : Number.NaN;
  if (!Number.isFinite(numeric)) {
    return "n/a";
  }
  if (Math.abs(numeric) >= 1000) {
    return new Intl.NumberFormat("en-US", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(numeric);
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: numeric >= 100 ? 0 : 1,
  }).format(numeric);
}

export function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    return formatCompactNumber(value);
  }
  if (typeof value === "string") {
    const numeric = Number.parseFloat(value);
    if (!Number.isNaN(numeric) && value.trim() !== "") {
      return formatCompactNumber(numeric);
    }
    return value;
  }
  return JSON.stringify(value);
}
