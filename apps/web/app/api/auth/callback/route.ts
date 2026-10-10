import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  ID_TOKEN_COOKIE,
  OIDC_NONCE_COOKIE,
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  sanitizeReturnTo,
  publicRequestOrigin,
} from "@/lib/auth-session";

interface OidcCallbackConfig {
  clientId: string;
  clientSecret?: string;
  redirectUri: string;
  tokenEndpoint: string;
}

interface TokenPayload {
  access_token?: string;
  expires_in?: number;
  id_token?: string;
}

function keycloakEndpoint(issuer: string, leaf: string): string {
  return `${issuer.replace(/\/$/, "")}/protocol/openid-connect/${leaf}`;
}

function callbackConfig(origin: string): OidcCallbackConfig | null {
  const issuer = process.env.ROAD_RISK_WEB_OIDC_ISSUER || process.env.NEXT_PUBLIC_OIDC_ISSUER;
  const clientId =
    process.env.ROAD_RISK_WEB_OIDC_CLIENT_ID || process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
  const tokenEndpoint =
    process.env.ROAD_RISK_WEB_OIDC_TOKEN_ENDPOINT ||
    (issuer ? keycloakEndpoint(issuer, "token") : undefined);
  if (!clientId || !tokenEndpoint) {
    return null;
  }
  return {
    clientId,
    clientSecret: process.env.ROAD_RISK_WEB_OIDC_CLIENT_SECRET,
    redirectUri: process.env.ROAD_RISK_WEB_OIDC_REDIRECT_URI || `${origin}/api/auth/callback`,
    tokenEndpoint,
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

function clearHandshakeCookies(response: NextResponse): void {
  response.cookies.delete(OIDC_STATE_COOKIE);
  response.cookies.delete(OIDC_NONCE_COOKIE);
  response.cookies.delete(OIDC_RETURN_TO_COOKIE);
}

function loginRedirect(request: NextRequest, error: string): NextResponse {
  const response = NextResponse.redirect(new URL(`/login?authError=${error}`, publicRequestOrigin(request.url)));
  clearHandshakeCookies(response);
  return response;
}

export async function GET(request: NextRequest) {
  const expectedState = request.cookies.get(OIDC_STATE_COOKIE)?.value;
  const state = request.nextUrl.searchParams.get("state");
  const code = request.nextUrl.searchParams.get("code");
  const returnTo = sanitizeReturnTo(request.cookies.get(OIDC_RETURN_TO_COOKIE)?.value);
  const config = callbackConfig(publicRequestOrigin(request.url));

  if (!config) {
    return loginRedirect(request, "missing_oidc_config");
  }
  if (!expectedState || state !== expectedState || !code) {
    return loginRedirect(request, "invalid_oidc_state");
  }

  const tokenRequest = new URLSearchParams({
    client_id: config.clientId,
    code,
    grant_type: "authorization_code",
    redirect_uri: config.redirectUri,
  });
  if (config.clientSecret) {
    tokenRequest.set("client_secret", config.clientSecret);
  }

  const tokenResponse = await fetch(config.tokenEndpoint, {
    body: tokenRequest,
    cache: "no-store",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    method: "POST",
  });
  if (!tokenResponse.ok) {
    return loginRedirect(request, "token_exchange_failed");
  }

  const tokenPayload = (await tokenResponse.json()) as TokenPayload;
  if (!tokenPayload.access_token) {
    return loginRedirect(request, "missing_access_token");
  }

  const maxAge = Math.max(60, Math.min(Number(tokenPayload.expires_in ?? 3600), 12 * 60 * 60));
  const response = NextResponse.redirect(new URL(returnTo, publicRequestOrigin(request.url)));
  response.cookies.set(ACCESS_TOKEN_COOKIE, tokenPayload.access_token, authCookieOptions(maxAge));
  if (tokenPayload.id_token) {
    response.cookies.set(ID_TOKEN_COOKIE, tokenPayload.id_token, authCookieOptions(maxAge));
  }
  clearHandshakeCookies(response);
  return response;
}
