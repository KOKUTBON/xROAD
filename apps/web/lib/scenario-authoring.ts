export interface ScenarioDraftFormState {
  name: string;
  interventionCode: string;
  targetContextKey: string;
  targetContextLabel: string;
  baselinePredictedCrashTotal: string;
  expectedRelativeReduction: string;
  costClass: string;
  uncertainty: string;
  assumptionsText: string;
}

export interface ScenarioDraftPayload {
  organization_id: string;
  city_key: string;
  name: string;
  intervention_code: string;
  target_context_key?: string;
  target_context_label?: string;
  target_asset_ids: string[];
  parameters: Record<string, number>;
  assumptions: string[];
  cost_class: string;
  uncertainty: string;
}

export interface ScenarioRunSummary {
  name?: string | null;
  baseline_predicted_crash_total?: number | null;
  counterfactual_predicted_crash_total?: number | null;
  expected_crash_reduction?: number | null;
  expected_relative_reduction?: number | null;
  confidence?: string | null;
}

export function parseAssumptionsText(value: string): string[] {
  return value
    .split(/\n|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function numericParameter(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function buildScenarioDraftPayload({
  organizationId,
  cityKey,
  form,
}: {
  organizationId: string;
  cityKey: string;
  form: ScenarioDraftFormState;
}): ScenarioDraftPayload {
  const parameters: Record<string, number> = {};
  const baseline = numericParameter(form.baselinePredictedCrashTotal);
  const expectedReduction = numericParameter(form.expectedRelativeReduction);
  if (baseline !== null) parameters.baseline_predicted_crash_total = baseline;
  if (expectedReduction !== null) parameters.expected_relative_reduction = expectedReduction;

  return {
    organization_id: organizationId,
    city_key: cityKey,
    name: form.name.trim(),
    intervention_code: form.interventionCode.trim(),
    target_context_key: form.targetContextKey.trim() || undefined,
    target_context_label: form.targetContextLabel.trim() || undefined,
    target_asset_ids: [],
    parameters,
    assumptions: parseAssumptionsText(form.assumptionsText),
    cost_class: form.costClass,
    uncertainty: form.uncertainty,
  };
}

export function summarizeBeforeAfter(run: ScenarioRunSummary | null | undefined): string {
  if (!run) return "No run yet";
  const baseline = run.baseline_predicted_crash_total;
  const counterfactual = run.counterfactual_predicted_crash_total;
  const reduction = run.expected_crash_reduction;
  if (baseline === null || baseline === undefined || counterfactual === null || counterfactual === undefined) {
    return "Run completed without before/after totals";
  }
  const percent = run.expected_relative_reduction === null || run.expected_relative_reduction === undefined
    ? "n/a"
    : `${(run.expected_relative_reduction * 100).toFixed(1)}%`;
  return `${baseline.toFixed(2)} -> ${counterfactual.toFixed(2)} crashes/year (${(reduction ?? 0).toFixed(2)} avoided, ${percent})`;
}
