import { describe, expect, test } from "vitest";

import {
  accessGuardrailWarnings,
  buildMembershipUpdatePayload,
  buildMunicipalityAccessPayload,
  buildUserLinkPayload,
  type MembershipUpdateForm,
  type MunicipalityAccessForm,
  type UserLinkForm,
} from "./admin-access";

describe("admin access management forms", () => {
  test("buildUserLinkPayload trims OIDC subject and identity metadata", () => {
    const form: UserLinkForm = {
      subject: " oidc-user-1 ",
      email: " planner@example.test ",
      display_name: " Mobility Planner ",
      role: "analyst",
      status: "active",
      decision_note: " Approved onboarding. ",
    };

    expect(buildUserLinkPayload(" org-1 ", form)).toEqual({
      organization_id: "org-1",
      subject: "oidc-user-1",
      email: "planner@example.test",
      display_name: "Mobility Planner",
      role: "analyst",
      status: "active",
      decision_note: "Approved onboarding.",
    });
  });

  test("buildMembershipUpdatePayload separates membership id from body", () => {
    const form: MembershipUpdateForm = {
      membership_id: " membership-1 ",
      role: "data_operator",
      status: "suspended",
      decision_note: "",
    };

    expect(buildMembershipUpdatePayload("org-1", form)).toEqual({
      membershipId: "membership-1",
      body: {
        organization_id: "org-1",
        role: "data_operator",
        status: "suspended",
        decision_note: "Updated from admin access workflow.",
      },
    });
  });

  test("buildMunicipalityAccessPayload carries org-level municipal scope", () => {
    const form: MunicipalityAccessForm = {
      municipality_id: " bari ",
      access_level: "full",
      status: "active",
      decision_note: " Phase one deployment. ",
    };

    expect(buildMunicipalityAccessPayload("org-1", form)).toEqual({
      organization_id: "org-1",
      municipality_id: "bari",
      access_level: "full",
      status: "active",
      decision_note: "Phase one deployment.",
    });
  });

  test("accessGuardrailWarnings flags demotion and inactive status", () => {
    expect(accessGuardrailWarnings({ role: "analyst", status: "inactive" })).toEqual([
      "Demoting an admin removes their admin workspace access after the next auth refresh.",
      "Inactive or suspended memberships are removed from active access reviews.",
    ]);
    expect(accessGuardrailWarnings({ role: "admin", status: "active" })).toEqual([]);
  });
});
