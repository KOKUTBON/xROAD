import { describe, expect, test } from "vitest";

import {
  buildCreateDataSourcePayload,
  buildUpdateDataSourcePayload,
  governanceFormWarnings,
  type DataSourceCreateForm,
  type DataSourcePolicyForm,
} from "./admin-control";

describe("admin governance data-source forms", () => {
  test("buildCreateDataSourcePayload trims text and carries default audit note", () => {
    const form: DataSourceCreateForm = {
      name: " Bari crash feed ",
      source_type: " crash_feed ",
      provider_name: " Comune di Bari ",
      governance_status: "approved",
      publication_tier: "public",
      refresh_frequency: "weekly",
    };

    expect(buildCreateDataSourcePayload(" org-1 ", form)).toEqual({
      organization_id: "org-1",
      name: "Bari crash feed",
      source_type: "crash_feed",
      provider_name: "Comune di Bari",
      governance_status: "approved",
      publication_tier: "public",
      refresh_frequency: "weekly",
      configuration: {},
      decision_note: "Created from admin governance workflow.",
    });
  });

  test("buildUpdateDataSourcePayload separates URL source id from request body", () => {
    const form: DataSourcePolicyForm = {
      source_id: " source-1 ",
      governance_status: "blocked",
      publication_tier: "restricted",
      refresh_frequency: "manual",
      status: "archived",
      decision_note: " Superseded by new provider contract. ",
    };

    expect(buildUpdateDataSourcePayload("org-1", form)).toEqual({
      sourceId: "source-1",
      body: {
        organization_id: "org-1",
        governance_status: "blocked",
        publication_tier: "restricted",
        refresh_frequency: "manual",
        status: "archived",
        decision_note: "Superseded by new provider contract.",
      },
    });
  });

  test("governanceFormWarnings flags risky publication and blocked ingestion states", () => {
    expect(
      governanceFormWarnings({
        governance_status: "draft",
        publication_tier: "public",
        status: "active",
      }),
    ).toEqual(["Public publication should be approved before citizens can see derived artifacts."]);

    expect(
      governanceFormWarnings({
        governance_status: "revoked",
        publication_tier: "restricted",
        status: "archived",
      }),
    ).toEqual(["This setting blocks new ingestion use for the selected source."]);
  });
});
