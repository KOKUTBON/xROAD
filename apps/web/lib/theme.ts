/**
 * Theme model for the design-token themes (#178).
 *
 * The token palette in `app/globals.css` ships three `data-theme` variants:
 * `light` (default), `dark` (low-light operations rooms), and `high-contrast`
 * (low-vision accessibility). The active theme is stored as a `data-theme`
 * attribute on `<html>` and persisted in `localStorage` so it survives reloads
 * and is applied before first paint by `themeInitScript()`.
 */

export const THEMES = ["light", "dark", "high-contrast"] as const;

export type Theme = (typeof THEMES)[number];

export const DEFAULT_THEME: Theme = "light";

/** localStorage key holding the user's explicit theme choice. */
export const THEME_STORAGE_KEY = "road-risk-web-theme-v1";

export const THEME_LABELS: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  "high-contrast": "High contrast",
};

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/**
 * Blocking script injected in `<head>` that applies the persisted (or
 * system-preferred) theme to `<html>` before hydration, so there is no
 * flash of the wrong theme. Kept dependency-free and `try`-guarded so a
 * locked-down `localStorage` never breaks first paint.
 */
export function themeInitScript(): string {
  return `(function(){try{var k=${JSON.stringify(THEME_STORAGE_KEY)};var t=localStorage.getItem(k);var valid=${JSON.stringify(
    THEMES,
  )};if(valid.indexOf(t)===-1){t=(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)?"dark":${JSON.stringify(
    DEFAULT_THEME,
  )};}document.documentElement.setAttribute("data-theme",t);}catch(e){document.documentElement.setAttribute("data-theme",${JSON.stringify(
    DEFAULT_THEME,
  )});}})();`;
}
