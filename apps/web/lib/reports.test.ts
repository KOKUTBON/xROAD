import { describe, expect, it } from "vitest";

import {
  buildReportGenerationPayload,
  buildReportLifecyclePayload,
  defaultVisibilityForReport,
  reportLifecycleActionLabel,
} from "./reports";

describe("report helpers", () => {
  it("builds report generation payloads with explicit visibility and auto dispatch", () => {
    expect(
      buildReportGenerationPayload({
        organizationId: "org-1",
        cityKey: "bari",
        reportType: "public_transparency",
        outputFormat: "pdf",
        visibilityTier: "public",
      }),
    ).toEqual({
      organization_id: "org-1",
      city_key: "bari",
      report_type: "public_transparency",
      output_format: "pdf",
      visibility_tier: "public",
      dispatch_mode: "auto",
      title: undefined,
    });
  });

  it("builds lifecycle payloads without empty optional fields", () => {
    expect(
      buildReportLifecyclePayload({
        organizationId: "org-1",
        action: "review",
        visibilityTier: "",
        note: "",
      }),
    ).toEqual({
      organization_id: "org-1",
      action: "review",
      visibility_tier: undefined,
      note: undefined,
    });
  });

  it("keeps public transparency reports public by default", () => {
    expect(defaultVisibilityForReport("public_transparency")).toBe("public");
    expect(defaultVisibilityForReport("technical_hotspot")).toBe("restricted");
  });

  it("labels lifecycle actions for operator buttons", () => {
    expect(reportLifecycleActionLabel("review")).toBe("Mark reviewed");
    expect(reportLifecycleActionLabel("publish")).toBe("Publish public");
    expect(reportLifecycleActionLabel("unknown")).toBe("unknown");
  });
});
