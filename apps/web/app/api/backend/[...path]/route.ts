import { NextResponse, type NextRequest } from "next/server";

import { getServerBackendApiBaseUrl } from "@/lib/api-client";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-session";

function backendUrl(request: NextRequest, path: string[]): string {
  const url = new URL(`/${path.join("/")}`, getServerBackendApiBaseUrl());
  url.search = request.nextUrl.search;
  return url.toString();
}

function proxiedHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cookie");
  headers.delete("connection");
  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;
  if (token && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${token}`);
  }
  return headers;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const method = request.method.toUpperCase();
  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(backendUrl(request, path), {
    body: method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    headers: proxiedHeaders(request),
    method,
    redirect: "manual",
    signal: AbortSignal.timeout(30_000),
  });
  } catch {
    return NextResponse.json({ detail: "The backend is unavailable. Check the API service and retry." }, { status: 502 });
  }

  const responseHeaders = new Headers(upstreamResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  return new NextResponse(upstreamResponse.body, {
    headers: responseHeaders,
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
