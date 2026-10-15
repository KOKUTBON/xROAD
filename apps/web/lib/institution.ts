import { apiFetch } from "./demo-api";
/**
 * Multi-tenant white-label institutional configuration and dynamic theming.
 *
 * Supports country- and institution-specific deployments (Ministries of Transport,
 * municipal traffic authorities, police precincts, concessionaires).
 * Dynamically adapts brand colors, logos, unit conventions, and localization.
 */

import type { InstitutionDeployment } from "./institution-product";

import { getClientApiBaseUrl } from "./api-client";

export interface UnitPreferences {
  distance: "km" | "miles";
  speed: "km/h" | "mph";
  currency: string;
}

export interface InstitutionConfig {
  tenant_id: string;
  institution_name: string;
  brand_name: string;
  brand_primary_color: string;
  brand_logo_url: string;
  portal_subtitle: string;
  country_code: string;
  default_language: string;
  driving_side: "right" | "left";
  units: UnitPreferences;
  administrative_tier: string;
  deployment?: InstitutionDeployment;
  configuration_status?: "unavailable";
}

export const DEFAULT_INSTITUTION_CONFIG: InstitutionConfig = {
  tenant_id: "default",
  institution_name: "xROAD Road Safety Analytics",
  brand_name: "xROAD",
  brand_primary_color: "#4B2A8C",
  brand_logo_url: "/brand/road-accidents-risk-modeling-icon.svg",
  portal_subtitle: "Open road-safety analytics for reproducible risk screening",
  country_code: "IT",
  default_language: "en",
  driving_side: "right",
  units: {
    distance: "km",
    speed: "km/h",
    currency: "EUR",
  },
  administrative_tier: "region",
};

/** Convert 3- or 6-digit hex color to RGB tuple. */
export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const clean = hex.replace(/^#/, "").trim();
  if (clean.length === 3) {
    const r = parseInt(clean[0] + clean[0], 16);
    const g = parseInt(clean[1] + clean[1], 16);
    const b = parseInt(clean[2] + clean[2], 16);
    return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
  }
  if (clean.length === 6) {
    const r = parseInt(clean.substring(0, 2), 16);
    const g = parseInt(clean.substring(2, 4), 16);
    const b = parseInt(clean.substring(4, 6), 16);
    return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
  }
  return null;
}

/** Compute hover color by darkening primary hex. */
export function computeHoverColor(hex: string, darkenFactor = 0.85): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return hex;
  const r = Math.max(0, Math.min(255, Math.round(rgb.r * darkenFactor)));
  const g = Math.max(0, Math.min(255, Math.round(rgb.g * darkenFactor)));
  const b = Math.max(0, Math.min(255, Math.round(rgb.b * darkenFactor)));
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

/** Compute pastel tint by blending primary hex with white. */
export function computeTintColor(hex: string, tintFactor = 0.92): string {
  const rgb = hexToRgb(hex);
  if (!rgb) return "#F5F5F7";
  const r = Math.round(rgb.r * (1 - tintFactor) + 255 * tintFactor);
  const g = Math.round(rgb.g * (1 - tintFactor) + 255 * tintFactor);
  const b = Math.round(rgb.b * (1 - tintFactor) + 255 * tintFactor);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

/**
 * Apply dynamic white-label brand colors directly to CSS custom properties.
 * Injects `--color-brand-primary`, `--color-brand-hover`, `--color-brand-tint`,
 * and `--rgb-brand-primary` on `document.documentElement`.
 */
export function applyBrandTheme(primaryHex: string): void {
  if (typeof document === "undefined") return;

  const rgb = hexToRgb(primaryHex);
  if (!rgb) return;

  const hover = computeHoverColor(primaryHex);
  const tint = computeTintColor(primaryHex);

  const root = document.documentElement;
  root.style.setProperty("--color-brand-primary", primaryHex);
  root.style.setProperty("--color-brand-hover", hover);
  root.style.setProperty("--color-brand-tint", tint);
  root.style.setProperty("--rgb-brand-primary", `${rgb.r} ${rgb.g} ${rgb.b}`);
}

/** Fetch public institutional branding configuration from API. */
export async function fetchInstitutionConfig(
  signal?: AbortSignal,
): Promise<InstitutionConfig> {
  const baseUrl = getClientApiBaseUrl();
  const url = `${baseUrl}/v1/public/institution-config`;

  try {
    const res = await apiFetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
    if (!res.ok) {
      return { ...DEFAULT_INSTITUTION_CONFIG, configuration_status: "unavailable" };
    }
    const data = await res.json();
    return {
      ...DEFAULT_INSTITUTION_CONFIG,
      ...data,
      units: {
        ...DEFAULT_INSTITUTION_CONFIG.units,
        ...(data.units || {}),
      },
    };
  } catch {
    return { ...DEFAULT_INSTITUTION_CONFIG, configuration_status: "unavailable" };
  }
}

/** Convert meters to localized distance string (km or miles). */
export function formatLocalizedDistance(
  meters: number,
  unitPreference: "km" | "miles" = "km",
): string {
  if (unitPreference === "miles") {
    const miles = meters * 0.000621371;
    if (miles < 0.1) {
      const feet = Math.round(meters * 3.28084);
      return `${feet} ft`;
    }
    return `${miles.toFixed(2)} mi`;
  }
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(2)} km`;
}

/** Convert km/h to localized speed string (km/h or mph). */
export function formatLocalizedSpeed(
  kmh: number,
  unitPreference: "km/h" | "mph" = "km/h",
): string {
  if (unitPreference === "mph") {
    const mph = Math.round(kmh * 0.621371);
    return `${mph} mph`;
  }
  return `${Math.round(kmh)} km/h`;
}
