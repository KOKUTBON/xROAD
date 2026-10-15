import { STATIC_DEMO } from "./demo-mode";
import type { PlatformRole } from "./platform-shell";

export const ACCESS_TOKEN_COOKIE = "road_risk_access_token";
export const ID_TOKEN_COOKIE = "road_risk_id_token";
export const OIDC_STATE_COOKIE = "road_risk_oidc_state";
export const OIDC_NONCE_COOKIE = "road_risk_oidc_nonce";
export const OIDC_RETURN_TO_COOKIE = "road_risk_oidc_return_to";

export const INTERNAL_ROLES: PlatformRole[] = [
  "municipality_viewer",
  "analyst",
  "data_operator",
  "traffic_engineer",
  "admin",
  "super_admin",
];

export const ANALYST_ROLES: PlatformRole[] = [
  "analyst",
  "traffic_engineer",
  "admin",
  "super_admin",
];

export const TRAFFIC_ENGINEERING_ROLES: PlatformRole[] = [
  "traffic_engineer",
  "admin",
  "super_admin",
];

export const DATA_OPERATIONS_ROLES: PlatformRole[] = ["data_operator", "admin", "super_admin"];

export const ADMIN_ROLES: PlatformRole[] = ["admin", "super_admin"];

export interface JwtClaims {
  exp?: number;
  roles?: string[];
  realm_access?: {
    roles?: string[];
  };
  resource_access?: Record<string, { roles?: string[] }>;
  [claim: string]: unknown;
}

export interface RouteAccessDecision {
  allowed: boolean;
  hasInternalAccess: boolean;
  requiredRoles: PlatformRole[];
}

function uniq(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function isPlatformRole(value: string): value is PlatformRole {
  return [
    "public",
    "municipality_viewer",
    "analyst",
    "data_operator",
    "traffic_engineer",
    "admin",
    "super_admin",
  ].includes(value);
}

function includeRoleTree(roles: Set<PlatformRole>, role: PlatformRole): void {
  roles.add(role);
  if (role === "municipality_viewer") {
    roles.add("public");
  }
  if (role === "analyst") {
    roles.add("municipality_viewer");
    roles.add("public");
  }
  if (role === "data_operator") {
    roles.add("municipality_viewer");
    roles.add("public");
  }
  if (role === "traffic_engineer") {
    roles.add("analyst");
    roles.add("municipality_viewer");
    roles.add("public");
  }
  if (role === "admin") {
    roles.add("traffic_engineer");
    roles.add("data_operator");
    roles.add("analyst");
    roles.add("municipality_viewer");
    roles.add("public");
  }
  if (role === "super_admin") {
    roles.add("admin");
    roles.add("traffic_engineer");
    roles.add("data_operator");
    roles.add("analyst");
    roles.add("municipality_viewer");
    roles.add("public");
  }
}

export function expandPlatformRoles(inputRoles: string[]): PlatformRole[] {
  const expanded = new Set<PlatformRole>();
  for (const role of inputRoles) {
    if (isPlatformRole(role)) {
      includeRoleTree(expanded, role);
    }
  }
  if (expanded.size === 0) {
    expanded.add("public");
  }
  return uniq(Array.from(expanded)).filter(isPlatformRole);
}

export function isDemoAuthEnabled(): boolean {
  const explicitDemo =
    process.env.NEXT_PUBLIC_AUTH_MODE === "demo" ||
    process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH === "true";
  return STATIC_DEMO || (explicitDemo && process.env.NODE_ENV !== "production");
}

export function sanitizeReturnTo(value: string | null | undefined, fallback = "/workspace"): string {
  if (!value) {
    return fallback;
  }
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/api/auth")) {
    return fallback;
  }
  return value;
}

export function parseJwtClaims(token: string | null | undefined): JwtClaims | null {
  if (!token) {
    return null;
  }
  const [, encodedPayload] = token.split(".");
  if (!encodedPayload) {
    return null;
  }
  try {
    const base64 = encodedPayload
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(encodedPayload.length / 4) * 4, "=");
    const binary = globalThis.atob(base64);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)) as JwtClaims;
  } catch {
    return null;
  }
}

export function isJwtExpired(claims: JwtClaims | null, skewSeconds = 30): boolean {
  if (!claims || typeof claims.exp !== "number") {
    return true;
  }
  return claims.exp <= Math.floor(Date.now() / 1000) + skewSeconds;
}

export function rolesFromClaims(claims: JwtClaims | null, clientId?: string): PlatformRole[] {
  if (!claims) {
    return ["public"];
  }
  const assigned = new Set<string>();
  if (Array.isArray(claims.roles)) {
    claims.roles.forEach((role) => assigned.add(role));
  }
  if (Array.isArray(claims.realm_access?.roles)) {
    claims.realm_access.roles.forEach((role) => assigned.add(role));
  }
  if (clientId && claims.resource_access?.[clientId]?.roles) {
    claims.resource_access[clientId].roles?.forEach((role) => assigned.add(role));
  }

  return expandPlatformRoles(Array.from(assigned));
}

export function requiredRolesForPath(pathname: string): PlatformRole[] {
  if (pathname.startsWith("/workspace/uploads")) {
    return DATA_OPERATIONS_ROLES;
  }
  if (
    pathname.startsWith("/workspace/admin") ||
    pathname.startsWith("/workspace/automation") ||
    pathname.startsWith("/workspace/system-health")
  ) {
    return ADMIN_ROLES;
  }
  if (pathname.startsWith("/workspace/operations")) {
    return TRAFFIC_ENGINEERING_ROLES;
  }
  if (pathname.startsWith("/workspace/analyst") || pathname.startsWith("/workspace/scenarios")) {
    return ANALYST_ROLES;
  }
  return INTERNAL_ROLES;
}

export function routeAccessFromClaims(
  pathname: string,
  claims: JwtClaims | null,
  clientId?: string,
): RouteAccessDecision {
  const roles = rolesFromClaims(claims, clientId);
  return routeAccessFromRoles(pathname, roles);
}

export function routeAccessFromRoles(
  pathname: string,
  inputRoles: string[],
): RouteAccessDecision {
  const roles = expandPlatformRoles(inputRoles);
  const requiredRoles = requiredRolesForPath(pathname);
  return {
    allowed: requiredRoles.some((role) => roles.includes(role)),
    hasInternalAccess: INTERNAL_ROLES.some((role) => roles.includes(role)),
    requiredRoles,
  };
}

/** Use the configured public origin for redirects behind the HTTPS gateway. */
export function publicRequestOrigin(requestUrl: string): string {
  return new URL(process.env.ROAD_RISK_PUBLIC_ORIGIN || requestUrl).origin;
}
