import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  contrastRatio,
  extractColorTokens,
  extractThemeTokens,
  hexToRgb,
  relativeLuminance,
} from "./contrast";

/**
 * WCAG AA contrast gate for the design-token palette (#177, extended for #178).
 *
 * Reads the real token hexes from `app/globals.css` so the gate tracks the
 * source of truth, then asserts AA (4.5:1 normal text) on every semantic text
 * pair that the design intends to render — for *every* theme (`light`, `dark`,
 * `high-contrast`), resolving each pair against that theme's own surfaces.
 * Known shortfalls are pinned with `it.fails` and a tracking reference (#169)
 * so they are visible, cannot silently regress, and auto-alert the moment the
 * token is fixed.
 */

const css = readFileSync(path.join(__dirname, "..", "app", "globals.css"), "utf8");
const designCss = readFileSync(path.join(__dirname, "..", "app", "signal-system.css"), "utf8");
const themes = extractThemeTokens(`${css}\n${designCss}`);
const tokens = themes.light;

function token(name: string): string {
  const value = tokens[name];
  if (!value) {
    throw new Error(`Token ${name} not found in globals.css`);
  }
  return value;
}

/** Composite a hex color at the given alpha over an opaque base hex. */
function composite(foreground: string, alpha: number, base: string): string {
  const fg = hexToRgb(foreground);
  const bg = hexToRgb(base);
  const blend = (f: number, b: number) => Math.round(f * alpha + b * (1 - alpha));
  const toHex = (value: number) => value.toString(16).padStart(2, "0");
  return `#${toHex(blend(fg.r, bg.r))}${toHex(blend(fg.g, bg.g))}${toHex(blend(fg.b, bg.b))}`;
}

const AA_NORMAL = 4.5;
const THEME_NAMES = ["light", "dark", "high-contrast"] as const;

// Pairs that must meet AA in every theme. Backgrounds are token names so each
// pair resolves against the active theme's own surfaces.
// [label, foreground token, background token].
const MUST_PASS: Array<[string, string, string]> = [
  ["ink on surface", "--color-ink", "--color-surface"],
  ["ink on app bg", "--color-ink", "--color-bg-app"],
  ["ink on raised surface", "--color-ink", "--color-surface-raised"],
  ["ink-secondary on surface", "--color-ink-secondary", "--color-surface"],
  ["ink-secondary on app bg", "--color-ink-secondary", "--color-bg-app"],
  ["ink-secondary on raised surface", "--color-ink-secondary", "--color-surface-raised"],
  ["ink-muted on surface", "--color-ink-muted", "--color-surface"],
  ["ink-muted on app bg", "--color-ink-muted", "--color-bg-app"],
  ["ink-muted on subtle surface", "--color-ink-muted", "--color-surface-subtle"],
  ["ink-muted on raised surface", "--color-ink-muted", "--color-surface-raised"],
  ["brand-primary on surface", "--color-brand-primary", "--color-surface"],
  ["brand-hover on surface", "--color-brand-hover", "--color-surface"],
  ["risk-minimal-ink on surface", "--color-risk-minimal-ink", "--color-surface"],
  ["risk-low-ink on surface", "--color-risk-low-ink", "--color-surface"],
  ["risk-moderate-ink on surface", "--color-risk-moderate-ink", "--color-surface"],
  ["risk-high-ink on surface", "--color-risk-high-ink", "--color-surface"],
  ["risk-very-high-ink on surface", "--color-risk-very-high-ink", "--color-surface"],
  ["status-info on surface", "--color-status-info", "--color-surface"],
  ["status-warning on surface", "--color-status-warning", "--color-surface"],
  ["status-danger on surface", "--color-status-danger", "--color-surface"],
  ["tier-public ink on fill", "--color-tier-public-ink", "--color-tier-public-fill"],
  ["tier-restricted ink on fill", "--color-tier-restricted-ink", "--color-tier-restricted-fill"],
  ["tier-internal ink on fill", "--color-tier-internal-ink", "--color-tier-internal-fill"],
];

// Status pills render the status color as text over that color composited on
// surface at its declared alpha (globals.css ~1034–1057). [label, color token, alpha].
const STATUS_PILLS: Array<[string, string, number]> = [
  ["info", "--color-status-info", 0.12],
  ["success", "--color-status-success", 0.15],
  ["warning", "--color-status-warning", 0.14],
  ["danger", "--color-status-danger", 0.12],
  // neutral pill uses an ink-based tint rather than its own color
];

describe("contrast utilities", () => {
  it("computes the canonical black/white ratio as 21:1", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 1);
  });

  it("computes relative luminance bounds", () => {
    expect(relativeLuminance(hexToRgb("#000000"))).toBeCloseTo(0, 5);
    expect(relativeLuminance(hexToRgb("#FFFFFF"))).toBeCloseTo(1, 5);
  });

  it("expands shorthand hex", () => {
    expect(hexToRgb("#fff")).toEqual({ r: 255, g: 255, b: 255 });
  });
});

describe("design-token AA contrast gate (#177)", () => {
  it("extracts the effective palette tokens from the stylesheets", () => {
    expect(token("--color-brand-primary")).toBe("#8a4f00");
    expect(token("--brand-red-600")).toBe("#E02B20");
    expect(token("--color-status-danger")).toBe("#b42318");
    expect(token("--color-status-danger")).not.toBe(token("--brand-red-600"));
    expect(Object.keys(tokens).length).toBeGreaterThan(80);
  });

  it("declares the light, dark, and high-contrast themes", () => {
    for (const name of THEME_NAMES) {
      expect(themes[name], `theme ${name} missing from globals.css`).toBeDefined();
    }
  });

  describe.each(THEME_NAMES)("theme: %s", (themeName) => {
    const palette = themes[themeName];
    const get = (name: string): string => {
      const value = palette[name];
      if (!value) {
        throw new Error(`Token ${name} not found in theme ${themeName}`);
      }
      return value;
    };
    const surface = () => get("--color-surface");

    it.each(MUST_PASS)("%s meets WCAG AA (>= 4.5:1)", (_label, fg, bg) => {
      expect(contrastRatio(get(fg), get(bg))).toBeGreaterThanOrEqual(AA_NORMAL);
    });

    it.each(STATUS_PILLS)(
      "status-%s pill text meets AA over its tint (on surface and app bg)",
      (_label, colorToken, alpha) => {
        const color = get(colorToken);
        // Pills render on white panels AND on the slightly darker app canvas
        // (e.g. the public page-header). The composited tint must clear AA on
        // both bases — axe caught the warning pill failing only over app bg.
        for (const base of [surface(), get("--color-bg-app")]) {
          const tint = composite(color, alpha, base);
          expect(contrastRatio(color, tint)).toBeGreaterThanOrEqual(AA_NORMAL);
        }
      },
    );

    it("status-neutral pill text meets AA over its ink-based tint", () => {
      const tint = composite(get("--color-ink"), 0.08, surface());
      expect(contrastRatio(get("--color-status-neutral"), tint)).toBeGreaterThanOrEqual(AA_NORMAL);
    });
  });
});

/**
 * Risk-ramp single-source guard (F-3, #169).
 *
 * `dashboard/styles.css` declares the risk ramp under legacy names (`--gold`,
 * `--low`, …). Their hex values already match the ratified ramp in
 * `app/globals.css`, but the two declarations are physically separate and can
 * drift. Rather than risk a rename across the standalone dashboard, this test
 * fails CI the moment the two diverge — making the duplication safe until a
 * shared token file unifies them.
 */
describe("risk ramp single-source guard (#169)", () => {
  const dashboardCss = readFileSync(
    path.join(__dirname, "..", "..", "..", "dashboard", "styles.css"),
    "utf8",
  );
  const dashboardTokens = extractColorTokens(dashboardCss);

  // dashboard legacy name -> canonical ramp token
  const RAMP_SYNC: Array<[string, string]> = [
    ["--low", "--color-risk-minimal-fill"],
    ["--gold", "--color-risk-low-fill"],
    ["--moderate", "--color-risk-moderate-fill"],
    ["--high", "--color-risk-high-fill"],
    ["--very-high", "--color-risk-very-high-fill"],
  ];

  it.each(RAMP_SYNC)("dashboard %s matches the canonical %s", (legacy, canonical) => {
    expect(dashboardTokens[legacy]?.toUpperCase()).toBe(token(canonical).toUpperCase());
  });
});
