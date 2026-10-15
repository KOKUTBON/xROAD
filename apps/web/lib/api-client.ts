import { STATIC_DEMO, publicAsset } from "./demo-mode";
export const DEFAULT_BACKEND_API_BASE_URL = "http://localhost:8000";

export function getClientApiBaseUrl(): string {
  if (STATIC_DEMO) {
    const origin = typeof window !== "undefined" ? window.location.origin : "http://demo.local";
    return `${origin}${publicAsset("/api/backend")}`;
  }
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (configured) {
    return configured;
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api/backend`;
  }
  return "http://localhost:3000/api/backend";
}

export function getServerBackendApiBaseUrl(): string {
  const configured =
    process.env.ROAD_RISK_WEB_API_BASE_URL ||
    DEFAULT_BACKEND_API_BASE_URL;
  if (configured.startsWith("/")) {
    return DEFAULT_BACKEND_API_BASE_URL;
  }
  return configured.replace(/\/$/, "");
}
