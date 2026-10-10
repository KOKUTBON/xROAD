export interface PortfolioCreateFromRunInput {
  organizationId: string;
  cityKey: string;
  scenarioRunId: string;
  ownerSubject?: string | null;
}

export interface PortfolioStatusUpdateInput {
  organizationId: string;
  status: string;
  ownerSubject?: string | null;
  notes?: string;
}

export interface PortfolioRowSummary {
  target_label?: string | null;
  target_object_id?: string | null;
  intervention_type?: string | null;
  status?: string | null;
  expected_benefit?: number | null;
  priority_score?: number | null;
}

export function buildPortfolioCreateFromRunPayload(input: PortfolioCreateFromRunInput) {
  return {
    organization_id: input.organizationId,
    city_key: input.cityKey,
    scenario_run_id: input.scenarioRunId,
    status: "shortlisted",
    owner_subject: input.ownerSubject ?? undefined,
  };
}

export function buildPortfolioStatusUpdatePayload(input: PortfolioStatusUpdateInput) {
  return {
    organization_id: input.organizationId,
    status: input.status,
    owner_subject: input.ownerSubject ?? undefined,
    notes: input.notes || undefined,
  };
}

export function summarizePortfolioRow(row: PortfolioRowSummary): string {
  const target = row.target_label || row.target_object_id || "Target";
  const benefit = row.expected_benefit === null || row.expected_benefit === undefined
    ? "n/a"
    : row.expected_benefit.toFixed(2);
  const priority = row.priority_score === null || row.priority_score === undefined
    ? "n/a"
    : row.priority_score.toFixed(2);
  return `${target} · ${row.intervention_type ?? "intervention"} · ${row.status ?? "candidate"} · benefit ${benefit} · priority ${priority}`;
}
