export type ComplianceResult = {
  rule_id: string;
  status: "pass" | "fail" | "insufficient_data";
  severity: "mandatory" | "advisory";
  citation: string;
  source_url: string;
  description: string;
};

export type SitingCandidate = {
  candidate_id: string;
  rank: number;
  suitability_score: number;
  served_population_estimate: number;
  access_route_risk_percentile: number;
  geometry: GeoJSON.Geometry;
  compliance: {
    overall_status: string;
    results: ComplianceResult[];
  };
  companion_interventions: Array<{ countermeasure_id: string; reason: string }>;
};

export function suitabilityColor(score: number): string {
  if (score >= 0.75) return "#18794e";
  if (score >= 0.6) return "#d97706";
  return "#b42318";
}

export function riskColor(percentile: number): string {
  if (percentile >= 80) return "#b42318";
  if (percentile >= 50) return "#d97706";
  return "#2563eb";
}

export function complianceSummary(results: ComplianceResult[]): string {
  const passed = results.filter((row) => row.status === "pass").length;
  const warnings = results.filter(
    (row) => row.severity === "advisory" && row.status !== "pass",
  ).length;
  return `${passed}/${results.length} rules passed · ${warnings} advisory warnings`;
}
