import { NextResponse, type NextRequest } from "next/server";

import { getServerBackendApiBaseUrl } from "@/lib/api-client";
import {
  ACCESS_TOKEN_COOKIE,
  isDemoAuthEnabled,
  isJwtExpired,
  parseJwtClaims,
  routeAccessFromRoles,
  sanitizeReturnTo,
  publicRequestOrigin,
} from "@/lib/auth-session";

function redirectToLogin(request: NextRequest, reason: string): NextResponse {
  const loginUrl = new URL("/login", publicRequestOrigin(request.url));
  loginUrl.searchParams.set("returnTo", sanitizeReturnTo(request.nextUrl.pathname));
  loginUrl.searchParams.set("authError", reason);
  return NextResponse.redirect(loginUrl);
}

async function validateSession(token: string): Promise<string[] | null> {
  try {
    const response = await fetch(`${getServerBackendApiBaseUrl()}/v1/auth/me`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
        authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as {
      roles?: string[];
      subject?: string | null;
    };
    if (!payload.subject || !Array.isArray(payload.roles)) {
      return null;
    }
    return payload.roles;
  } catch {
    return null;
  }
}

export async function proxy(request: NextRequest) {
  if (isDemoAuthEnabled()) {
    return NextResponse.next();
  }

  const pathname = request.nextUrl.pathname;
  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;

  if (!token) {
    return redirectToLogin(request, "missing_session");
  }

  const claims = parseJwtClaims(token);
  if (isJwtExpired(claims)) {
    const response = redirectToLogin(request, "expired_session");
    response.cookies.delete(ACCESS_TOKEN_COOKIE);
    return response;
  }

  const roles = await validateSession(token);
  if (!roles) {
    const response = redirectToLogin(request, "invalid_session");
    response.cookies.delete(ACCESS_TOKEN_COOKIE);
    return response;
  }

  const access = routeAccessFromRoles(pathname, roles);
  if (access.allowed) {
    return NextResponse.next();
  }

  if (access.hasInternalAccess) {
    const fallbackUrl = new URL("/workspace", publicRequestOrigin(request.url));
    fallbackUrl.searchParams.set("accessDenied", pathname);
    fallbackUrl.searchParams.set("requiredRoles", access.requiredRoles.join(","));
    return NextResponse.redirect(fallbackUrl);
  }

  const loginUrl = new URL("/login", publicRequestOrigin(request.url));
  loginUrl.searchParams.set("returnTo", sanitizeReturnTo(pathname));
  loginUrl.searchParams.set("authError", "insufficient_role");
  loginUrl.searchParams.set("requiredRoles", access.requiredRoles.join(","));
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/workspace/:path*"],
};
