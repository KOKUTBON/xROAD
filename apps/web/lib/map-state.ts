import type { ScoreBandFilter } from "./risk-map";

export type AnalystLayerKey = "segments" | "junctions" | "crossings";

export const ANALYST_LAYER_KEYS: AnalystLayerKey[] = ["segments", "junctions", "crossings"];

export function normalizeScoreBandFilter(
  value: string | null | undefined,
  fallback: ScoreBandFilter,
): ScoreBandFilter {
  if (
    value === "all" ||
    value === "low" ||
    value === "moderate" ||
    value === "high" ||
    value === "very_high"
  ) {
    return value;
  }
  return fallback;
}

export function parseLayerVisibility(
  rawValue: string | null | undefined,
  fallback: Record<AnalystLayerKey, boolean>,
): Record<AnalystLayerKey, boolean> {
  if (!rawValue) {
    return { ...fallback };
  }
  const visible = new Set(
    rawValue
      .split(",")
      .map((value) => value.trim())
      .filter((value): value is AnalystLayerKey =>
        ANALYST_LAYER_KEYS.includes(value as AnalystLayerKey),
      ),
  );
  if (visible.size === 0) {
    return { ...fallback };
  }
  return {
    segments: visible.has("segments"),
    junctions: visible.has("junctions"),
    crossings: visible.has("crossings"),
  };
}

export function serializeLayerVisibility(
  visibility: Record<AnalystLayerKey, boolean>,
): string {
  return ANALYST_LAYER_KEYS.filter((key) => visibility[key]).join(",");
}

export interface RiskMapSearchUpdates {
  city?: string | null;
  year?: number | string | null;
  band?: ScoreBandFilter | null;
  feature?: string | null;
  layers?: string | null;
}

export function buildRiskMapSearchParams(
  currentSearch: string | URLSearchParams,
  updates: RiskMapSearchUpdates,
): string {
  const params =
    typeof currentSearch === "string"
      ? new URLSearchParams(currentSearch)
      : new URLSearchParams(currentSearch.toString());

  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === undefined || value === "") {
      params.delete(key);
    } else {
      params.set(key, String(value));
    }
  }

  params.sort();
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}
