"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { ContrastIcon, MoonIcon, SunIcon } from "@/components/icons";
import { DEFAULT_THEME, isTheme, THEME_LABELS, THEME_STORAGE_KEY, THEMES, type Theme } from "@/lib/theme";

const ThemeContext = createContext({
  theme: DEFAULT_THEME as Theme,
  hasExplicitChoice: false,
  setTheme: (_theme: Theme) => {},
});

function readAppliedTheme(): Theme {
  if (typeof document === "undefined") {
    return DEFAULT_THEME;
  }
  const applied = document.documentElement.getAttribute("data-theme");
  return isTheme(applied) ? applied : DEFAULT_THEME;
}

/**
 * Daylight, night-operations, and high-contrast appearances. The no-flash
 * init script in <head> applies the stored (or OS-preferred) theme before
 * hydration; this provider adopts it and persists explicit choices.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [hasExplicitChoice, setHasExplicitChoice] = useState(false);

  useEffect(() => {
    setThemeState(readAppliedTheme());
    try {
      setHasExplicitChoice(isTheme(localStorage.getItem(THEME_STORAGE_KEY)));
    } catch {
      setHasExplicitChoice(false);
    }
  }, []);

  const setTheme = useCallback((next: Theme) => {
    document.documentElement.setAttribute("data-theme", next);
    setThemeState(next);
    setHasExplicitChoice(true);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage may be blocked; the choice still applies for this visit.
    }
  }, []);

  return <ThemeContext.Provider value={{ theme, hasExplicitChoice, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}

const THEME_ICONS: Record<Theme, typeof SunIcon> = {
  light: SunIcon,
  dark: MoonIcon,
  "high-contrast": ContrastIcon,
};

/** Three-way appearance switch: Daylight, Night ops, High contrast. */
export function ThemeToggle({ onDark = false }: { onDark?: boolean }) {
  const { theme, setTheme } = useTheme();
  return (
    <div aria-label="Appearance" className={`theme-toggle${onDark ? " theme-toggle-dark" : ""}`} role="group">
      {THEMES.map((name) => {
        const Glyph = THEME_ICONS[name];
        return (
          <button
            aria-label={`${THEME_LABELS[name]} appearance`}
            aria-pressed={theme === name}
            key={name}
            onClick={() => setTheme(name)}
            title={THEME_LABELS[name]}
            type="button"
          >
            <Glyph size={16} />
          </button>
        );
      })}
    </div>
  );
}
