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

function keycloakEndpoint(issuer: string, leaf: string): string {
  return `${issuer.replace(/\/$/, "")}/protocol/openid-connect/${leaf}`;
}

function logoutEndpoint(): string | null {
  const issuer = process.env.ROAD_RISK_WEB_OIDC_ISSUER || process.env.NEXT_PUBLIC_OIDC_ISSUER;
  return (
    process.env.ROAD_RISK_WEB_OIDC_LOGOUT_ENDPOINT ||
    (issuer ? keycloakEndpoint(issuer, "logout") : null)
  );
}

function clearAuthCookies(response: NextResponse): void {
  response.cookies.delete(ACCESS_TOKEN_COOKIE);
  response.cookies.delete(ID_TOKEN_COOKIE);
  response.cookies.delete(OIDC_STATE_COOKIE);
  response.cookies.delete(OIDC_NONCE_COOKIE);
  response.cookies.delete(OIDC_RETURN_TO_COOKIE);
}

export async function GET(request: NextRequest) {
  const returnTo = sanitizeReturnTo(request.nextUrl.searchParams.get("returnTo"), "/");
  const postLogoutUrl = new URL(returnTo, publicRequestOrigin(request.url));
  const idToken = request.cookies.get(ID_TOKEN_COOKIE)?.value;
  const endpoint = logoutEndpoint();

  let target = postLogoutUrl;
  if (endpoint) {
    target = new URL(endpoint);
    target.searchParams.set("post_logout_redirect_uri", postLogoutUrl.toString());
    if (idToken) {
      target.searchParams.set("id_token_hint", idToken);
    }
  }

  const response = NextResponse.redirect(target);
  clearAuthCookies(response);
  return response;
}
