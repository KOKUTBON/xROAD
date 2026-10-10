export interface ReportGenerationInput {
  organizationId: string;
  cityKey: string;
  reportType: string;
  outputFormat: string;
  visibilityTier: string;
  dispatchMode?: string;
  title?: string | null;
}

export interface ReportLifecycleInput {
  organizationId: string;
  action: string;
  visibilityTier?: string | null;
  note?: string | null;
}

export function buildReportGenerationPayload(input: ReportGenerationInput) {
  return {
    organization_id: input.organizationId,
    city_key: input.cityKey,
    report_type: input.reportType,
    output_format: input.outputFormat,
    visibility_tier: input.visibilityTier,
    dispatch_mode: input.dispatchMode ?? "auto",
    title: input.title || undefined,
  };
}

export function buildReportLifecyclePayload(input: ReportLifecycleInput) {
  return {
    organization_id: input.organizationId,
    action: input.action,
    visibility_tier: input.visibilityTier || undefined,
    note: input.note || undefined,
  };
}

export function defaultVisibilityForReport(reportType: string): string {
  return reportType === "public_transparency" ? "public" : "restricted";
}

export function reportLifecycleActionLabel(action: string): string {
  switch (action) {
    case "review":
      return "Mark reviewed";
    case "publish":
      return "Publish public";
    case "unpublish":
      return "Unpublish";
    case "archive":
      return "Archive";
    case "reopen":
      return "Reopen";
    default:
      return action;
  }
}
