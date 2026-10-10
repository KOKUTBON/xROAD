import { NextResponse, type NextRequest } from "next/server";

import {
  OIDC_NONCE_COOKIE,
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  sanitizeReturnTo,
  publicRequestOrigin,
} from "@/lib/auth-session";

interface OidcLoginConfig {
  authorizationEndpoint: string;
  clientId: string;
  redirectUri: string;
  scope: string;
}

function keycloakEndpoint(issuer: string, leaf: string): string {
  return `${issuer.replace(/\/$/, "")}/protocol/openid-connect/${leaf}`;
}

function loginConfig(origin: string): OidcLoginConfig | null {
  const issuer = process.env.ROAD_RISK_WEB_OIDC_ISSUER || process.env.NEXT_PUBLIC_OIDC_ISSUER;
  const clientId =
    process.env.ROAD_RISK_WEB_OIDC_CLIENT_ID || process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  const authorizationEndpoint =
    process.env.ROAD_RISK_WEB_OIDC_AUTHORIZATION_ENDPOINT ||
    (issuer ? keycloakEndpoint(issuer, "auth") : undefined);
  if (!clientId || !authorizationEndpoint) {
    return null;
  }
  return {
    authorizationEndpoint,
    clientId,
    redirectUri: process.env.ROAD_RISK_WEB_OIDC_REDIRECT_URI || `${origin}/api/auth/callback`,
    scope: process.env.ROAD_RISK_WEB_OIDC_SCOPE || "openid profile email",
  };
}

function authCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    maxAge: maxAgeSeconds,
    path: "/",
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
  };
}

export async function GET(request: NextRequest) {
  const returnTo = sanitizeReturnTo(request.nextUrl.searchParams.get("returnTo"));
  const config = loginConfig(publicRequestOrigin(request.url));
  if (!config) {
    const loginUrl = new URL("/login", publicRequestOrigin(request.url));
    loginUrl.searchParams.set("authConfig", "missing");
    loginUrl.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(loginUrl);
  }

  const state = crypto.randomUUID();
  const nonce = crypto.randomUUID();
  const authorizationUrl = new URL(config.authorizationEndpoint);
  authorizationUrl.searchParams.set("client_id", config.clientId);
  authorizationUrl.searchParams.set("redirect_uri", config.redirectUri);
  authorizationUrl.searchParams.set("response_type", "code");
  authorizationUrl.searchParams.set("scope", config.scope);
  authorizationUrl.searchParams.set("state", state);
  authorizationUrl.searchParams.set("nonce", nonce);

  const response = NextResponse.redirect(authorizationUrl);
  response.cookies.set(OIDC_STATE_COOKIE, state, authCookieOptions(600));
  response.cookies.set(OIDC_NONCE_COOKIE, nonce, authCookieOptions(600));
  response.cookies.set(OIDC_RETURN_TO_COOKIE, returnTo, authCookieOptions(600));
  return response;
}
