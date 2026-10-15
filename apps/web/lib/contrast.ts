/**
 * WCAG 2.1 contrast utilities (#177 accessibility gate).
 *
 * Dependency-free relative-luminance + contrast-ratio math so the token
 * palette can be contrast-audited in the existing vitest harness without a
 * browser. Used by `contrast.test.ts` to enforce AA on every semantic text
 * pair declared in `app/globals.css`.
 */

export interface Rgb {
  r: number;
  g: number;
  b: number;
}

/** Parse a 3- or 6-digit hex color (with or without leading `#`) to 0–255 channels. */
export function hexToRgb(hex: string): Rgb {
  const normalized = hex.trim().replace(/^#/, "");
  const expanded =
    normalized.length === 3
      ? normalized
          .split("")
          .map((char) => char + char)
          .join("")
      : normalized;
  if (!/^[0-9a-fA-F]{6}$/.test(expanded)) {
    throw new Error(`Invalid hex color: ${hex}`);
  }
  return {
    r: parseInt(expanded.slice(0, 2), 16),
    g: parseInt(expanded.slice(2, 4), 16),
    b: parseInt(expanded.slice(4, 6), 16),
  };
}

function channelLuminance(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** WCAG relative luminance of an sRGB color. */
export function relativeLuminance(color: Rgb): number {
  return (
    0.2126 * channelLuminance(color.r) +
    0.7152 * channelLuminance(color.g) +
    0.0722 * channelLuminance(color.b)
  );
}

/** WCAG contrast ratio between two colors, from 1 (identical) to 21 (black on white). */
export function contrastRatio(foreground: string, background: string): number {
  const lf = relativeLuminance(hexToRgb(foreground));
  const lb = relativeLuminance(hexToRgb(background));
  const lighter = Math.max(lf, lb);
  const darker = Math.min(lf, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

export type WcagLevel = "AA" | "AAA";
export type TextSize = "normal" | "large";

/** WCAG minimum contrast threshold for text (AA: 4.5 normal / 3 large; AAA: 7 / 4.5). */
export function textThreshold(level: WcagLevel, size: TextSize): number {
  if (level === "AAA") {
    return size === "large" ? 4.5 : 7;
  }
  return size === "large" ? 3 : 4.5;
}

/** True when foreground/background meet the WCAG text threshold for the given level/size. */
export function meetsTextContrast(
  foreground: string,
  background: string,
  level: WcagLevel = "AA",
  size: TextSize = "normal",
): boolean {
  return contrastRatio(foreground, background) >= textThreshold(level, size);
}

/** Extract `--name: #hex;` custom properties from a CSS string into a token map. */
export function extractColorTokens(css: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const pattern = /(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(css)) !== null) {
    tokens[match[1]] = match[2];
  }
  return tokens;
}

/**
 * Extract color tokens grouped by theme (`light`, `dark`, `high-contrast`, …).
 *
 * Each top-level rule block is scanned; tokens land under every `data-theme`
 * name in that block's selector. The base `:root` block (no `data-theme`) seeds
 * `light` so light is the full palette and `dark`/`high-contrast` inherit any
 * tokens they don't override. Only flat declaration blocks are read, so nested
 * at-rules (e.g. `@media`) are skipped — fine, since theme tokens are flat.
 */
export function extractThemeTokens(css: string): Record<string, Record<string, string>> {
  const themes: Record<string, Record<string, string>> = {};
  const blockPattern = /([^{}]+)\{([^{}]*)\}/g;
  let block: RegExpExecArray | null;
  while ((block = blockPattern.exec(css)) !== null) {
    const selector = block[1];
    const body = block[2];
    const tokens = extractColorTokens(body);
    if (Object.keys(tokens).length === 0) {
      continue;
    }
    const names = [...selector.matchAll(/\[data-theme="([\w-]+)"\]/g)].map((m) => m[1]);
    const targets = names.length > 0 ? names : selector.includes(":root") ? ["light"] : [];
    for (const name of targets) {
      themes[name] = { ...(themes[name] ?? {}), ...tokens };
    }
  }
  // Dark / high-contrast override only what they redeclare; inherit the rest
  // from light so every gated token resolves in every theme.
  const base = themes.light ?? {};
  for (const name of Object.keys(themes)) {
    if (name !== "light") {
      themes[name] = { ...base, ...themes[name] };
    }
  }
  return themes;
}
