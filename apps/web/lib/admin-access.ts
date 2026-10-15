export const MEMBERSHIP_ROLE_OPTIONS = [
  "municipality_viewer",
  "analyst",
  "data_operator",
  "traffic_engineer",
  "admin",
  "super_admin",
] as const;
export const MEMBERSHIP_STATUS_OPTIONS = ["active", "inactive", "suspended"] as const;
export const MUNICIPALITY_ACCESS_LEVEL_OPTIONS = ["restricted", "internal", "full"] as const;
export const MUNICIPALITY_LINK_STATUS_OPTIONS = ["active", "inactive"] as const;

export type UserLinkForm = {
  subject: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  decision_note: string;
};

export type MembershipUpdateForm = {
  membership_id: string;
  role: string;
  status: string;
  decision_note: string;
};

export type MunicipalityAccessForm = {
  municipality_id: string;
  access_level: string;
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

export function buildUserLinkPayload(
  organizationId: string,
  form: UserLinkForm,
): Record<string, unknown> {
  return {
    organization_id: requireText(organizationId, "organization_id"),
    subject: requireText(form.subject, "subject"),
    email: cleanOptional(form.email),
    display_name: cleanOptional(form.display_name),
    role: requireText(form.role, "role"),
    status: requireText(form.status, "status"),
    decision_note: cleanOptional(form.decision_note) ?? "Linked from admin access workflow.",
  };
}

export function buildMembershipUpdatePayload(
  organizationId: string,
  form: MembershipUpdateForm,
): { membershipId: string; body: Record<string, unknown> } {
  return {
    membershipId: requireText(form.membership_id, "membership_id"),
    body: {
      organization_id: requireText(organizationId, "organization_id"),
      role: requireText(form.role, "role"),
      status: requireText(form.status, "status"),
      decision_note: cleanOptional(form.decision_note) ?? "Updated from admin access workflow.",
    },
  };
}

export function buildMunicipalityAccessPayload(
  organizationId: string,
  form: MunicipalityAccessForm,
): Record<string, unknown> {
  return {
    organization_id: requireText(organizationId, "organization_id"),
    municipality_id: requireText(form.municipality_id, "municipality_id"),
    access_level: requireText(form.access_level, "access_level"),
    status: requireText(form.status, "status"),
    decision_note: cleanOptional(form.decision_note) ?? "Assigned from admin access workflow.",
  };
}

export function accessGuardrailWarnings(form: Pick<MembershipUpdateForm, "role" | "status">): string[] {
  const warnings: string[] = [];
  if (form.role !== "admin" && form.role !== "super_admin") {
    warnings.push("Demoting an admin removes their admin workspace access after the next auth refresh.");
  }
  if (form.status !== "active") {
    warnings.push("Inactive or suspended memberships are removed from active access reviews.");
  }
  return warnings;
}
