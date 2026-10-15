import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME,
  THEMES,
  THEME_LABELS,
  THEME_STORAGE_KEY,
  isTheme,
  themeInitScript,
} from "./theme";

/**
 * Theme model guards (#178). The no-flash init script and the persisted choice
 * share constants with the runtime provider and the CSS `data-theme` blocks, so
 * these tests pin the contract that keeps them in sync.
 */
describe("theme model", () => {
  it("ships exactly the three documented themes", () => {
    expect([...THEMES]).toEqual(["light", "dark", "high-contrast"]);
  });

  it("labels every theme", () => {
    for (const name of THEMES) {
      expect(THEME_LABELS[name]).toBeTruthy();
    }
  });

  it("defaults to a real theme", () => {
    expect(isTheme(DEFAULT_THEME)).toBe(true);
  });

  it("recognizes only valid theme names", () => {
    expect(isTheme("dark")).toBe(true);
    expect(isTheme("high-contrast")).toBe(true);
    expect(isTheme("sepia")).toBe(false);
    expect(isTheme(null)).toBe(false);
    expect(isTheme(undefined)).toBe(false);
  });
});

describe("themeInitScript", () => {
  const script = themeInitScript();

  it("references the persistence key and every theme", () => {
    expect(script).toContain(THEME_STORAGE_KEY);
    for (const name of THEMES) {
      expect(script).toContain(name);
    }
  });

  it("guards against a locked-down localStorage", () => {
    expect(script).toContain("try");
    expect(script).toContain("catch");
  });

  it("falls back to the system color-scheme preference", () => {
    expect(script).toContain("prefers-color-scheme: dark");
  });

  it("runs without throwing in a DOM-less context", () => {
    // The script reads `localStorage`/`matchMedia`; both are absent here, so the
    // try/catch must keep it from throwing. We eval it against a stub document.
    const setAttribute = (name: string, value: string) => {
      lastApplied = { name, value };
    };
    let lastApplied: { name: string; value: string } | null = null;
    const sandbox = {
      document: { documentElement: { setAttribute } },
      localStorage: undefined,
      window: undefined,
    };
    const run = new Function(
      "document",
      "localStorage",
      "window",
      script,
    ) as (d: unknown, l: unknown, w: unknown) => void;
    expect(() => run(sandbox.document, sandbox.localStorage, sandbox.window)).not.toThrow();
    expect(lastApplied).toEqual({ name: "data-theme", value: DEFAULT_THEME });
  });
});
