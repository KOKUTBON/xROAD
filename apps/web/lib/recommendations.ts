export type Recommendation = {
  recommendation_id: string;
  segment_label?: string | null;
  countermeasure_name: string;
  object_type: string;
  benefit_cost_ratio: number;
  expected_annual_crashes_prevented: number;
  expected_annual_crashes_prevented_low?: number | null;
  expected_annual_crashes_prevented_high?: number | null;
  effect_ratio_low: number;
  effect_ratio_central: number;
  effect_ratio_high: number;
  cost_band: string;
  evidence_source: string;
  evidence_ref?: string | null;
  contributing_factors: Array<{ label: string; value?: string | number | null }>;
  review_state: "proposed" | "engineer_reviewed" | "approved" | "rejected";
  geometry: GeoJSON.Geometry;
};

export function priorityColor(recommendation: Pick<Recommendation, "benefit_cost_ratio">): string {
  if (recommendation.benefit_cost_ratio >= 5) return "#b42318";
  if (recommendation.benefit_cost_ratio >= 2) return "#d97706";
  return "#2563eb";
}

export function canReviewRecommendations(roles: string[]): boolean {
  return roles.some((role) => ["traffic_engineer", "admin", "super_admin"].includes(role));
}

export function reductionIntervalLabel(recommendation: Recommendation): string {
  const central = recommendation.expected_annual_crashes_prevented.toFixed(2);
  const low = recommendation.expected_annual_crashes_prevented_low;
  const high = recommendation.expected_annual_crashes_prevented_high;
  return low == null || high == null
    ? `${central} crashes/year`
    : `${central} crashes/year (${low.toFixed(2)}–${high.toFixed(2)})`;
}
