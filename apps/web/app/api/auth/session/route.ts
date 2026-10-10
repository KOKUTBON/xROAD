import { NextResponse, type NextRequest } from "next/server";

import { getServerBackendApiBaseUrl } from "@/lib/api-client";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-session";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;
  const headers = new Headers({ accept: "application/json" });
  if (token) {
    headers.set("authorization", `Bearer ${token}`);
  }

  try {
    const response = await fetch(`${getServerBackendApiBaseUrl()}/v1/auth/me`, {
      cache: "no-store",
      headers,
    });
    const payload = await response.json().catch(() => ({}));
    const nextResponse = NextResponse.json(payload, { status: response.status });
    if (response.status === 401) {
      nextResponse.cookies.delete(ACCESS_TOKEN_COOKIE);
    }
    return nextResponse;
  } catch {
    return NextResponse.json(
      { detail: "Backend auth service is unavailable." },
      { status: 503 },
    );
  }
}
