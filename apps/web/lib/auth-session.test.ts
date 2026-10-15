import { afterEach, describe, expect, test, vi } from "vitest";

import {
  isJwtExpired,
  parseJwtClaims,
  requiredRolesForPath,
  rolesFromClaims,
  routeAccessFromClaims,
  sanitizeReturnTo,
} from "./auth-session";

function tokenFor(payload: Record<string, unknown>): string {
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `header.${encoded}.signature`;
}

describe("production web auth session helpers", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test("sanitizes return targets to same-origin application paths", () => {
    expect(sanitizeReturnTo("/workspace/analyst")).toBe("/workspace/analyst");
    expect(sanitizeReturnTo("https://evil.example/workspace")).toBe("/workspace");
    expect(sanitizeReturnTo("//evil.example/workspace")).toBe("/workspace");
    expect(sanitizeReturnTo("/api/auth/callback")).toBe("/workspace");
  });

  test("extracts and expands Keycloak-compatible roles from JWT claims", () => {
    const claims = parseJwtClaims(
      tokenFor({
        exp: 4_102_444_800,
        realm_access: { roles: ["admin"] },
      }),
    );

    expect(rolesFromClaims(claims)).toEqual([
      "admin",
      "traffic_engineer",
      "data_operator",
      "analyst",
      "municipality_viewer",
      "public",
    ]);
  });

  test("honors route-level role policies for workspace surfaces", () => {
    const analystClaims = parseJwtClaims(
      tokenFor({
        exp: 4_102_444_800,
        realm_access: { roles: ["analyst"] },
      }),
    );

    expect(requiredRolesForPath("/workspace/admin")).toEqual(["admin", "super_admin"]);
    expect(requiredRolesForPath("/workspace/uploads")).toEqual([
      "data_operator",
      "admin",
      "super_admin",
    ]);
    expect(routeAccessFromClaims("/workspace/analyst", analystClaims).allowed).toBe(true);
    expect(routeAccessFromClaims("/workspace/admin", analystClaims)).toMatchObject({
      allowed: false,
      hasInternalAccess: true,
    });
  });

  test("treats expired or malformed tokens as unauthenticated", () => {
    vi.setSystemTime(new Date("2026-05-27T12:00:00Z"));
    expect(isJwtExpired(parseJwtClaims(tokenFor({ exp: 1 })))).toBe(true);
    expect(isJwtExpired(parseJwtClaims("not-a-jwt"))).toBe(true);
  });
});
