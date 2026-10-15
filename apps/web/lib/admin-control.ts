export const GOVERNANCE_STATUS_OPTIONS = ["draft", "needs_review", "approved", "blocked", "revoked"] as const;
export const PUBLICATION_TIER_OPTIONS = ["restricted", "internal", "public"] as const;
export const REFRESH_FREQUENCY_OPTIONS = ["manual", "daily", "weekly", "monthly", "quarterly", "event_driven"] as const;
export const SOURCE_STATUS_OPTIONS = ["active", "archived"] as const;

export type DataSourceCreateForm = {
  name: string;
  source_type: string;
  provider_name: string;
  governance_status: string;
  publication_tier: string;
  refresh_frequency: string;
};

export type DataSourcePolicyForm = {
  source_id: string;
  governance_status: string;
  publication_tier: string;
  refresh_frequency: string;
  status: string;
  decision_note: string;
};

function cleanOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function requireText(value: string, fieldName: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${fieldName} is required.`);
  }
  return trimmed;
}

export function buildCreateDataSourcePayload(
  organizationId: string,
  form: DataSourceCreateForm,
): Record<string, unknown> {
  return {
    organization_id: requireText(organizationId, "organization_id"),
    name: requireText(form.name, "name"),
    source_type: requireText(form.source_type, "source_type"),
    provider_name: cleanOptional(form.provider_name),
    governance_status: requireText(form.governance_status, "governance_status"),
    publication_tier: requireText(form.publication_tier, "publication_tier"),
    refresh_frequency: cleanOptional(form.refresh_frequency),
    configuration: {},
    decision_note: "Created from admin governance workflow.",
  };
}

export function buildUpdateDataSourcePayload(
  organizationId: string,
  form: DataSourcePolicyForm,
): { sourceId: string; body: Record<string, unknown> } {
  const sourceId = requireText(form.source_id, "source_id");
  return {
    sourceId,
    body: {
      organization_id: requireText(organizationId, "organization_id"),
      governance_status: requireText(form.governance_status, "governance_status"),
      publication_tier: requireText(form.publication_tier, "publication_tier"),
      refresh_frequency: cleanOptional(form.refresh_frequency),
      status: requireText(form.status, "status"),
      decision_note: cleanOptional(form.decision_note) ?? "Updated from admin governance workflow.",
    },
  };
}

export function governanceFormWarnings(form: Pick<DataSourcePolicyForm, "governance_status" | "publication_tier" | "status">): string[] {
  const warnings: string[] = [];
  if (form.publication_tier === "public" && form.governance_status !== "approved") {
    warnings.push("Public publication should be approved before citizens can see derived artifacts.");
  }
  if (form.status === "archived" || form.governance_status === "blocked" || form.governance_status === "revoked") {
    warnings.push("This setting blocks new ingestion use for the selected source.");
  }
  return warnings;
}
