"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useInstitution } from "@/components/institution-provider";

import {
  DEFAULT_LOCALE,
  LOCALE_BCP47,
  LOCALE_STORAGE_KEY,
  MESSAGES,
  formatDate as formatDateFor,
  formatNumber as formatNumberFor,
  isLocale,
  type Locale,
  type Messages,
} from "@/lib/i18n";

interface LocaleContextValue {
  /** The active locale. Mirrors `<html data-locale>`. */
  locale: Locale;
  setLocale: (locale: Locale) => void;
  /** Translate a dictionary key for the active locale. */
  t: (key: keyof Messages) => string;
  /** Locale-aware number formatting bound to the active locale. */
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
  /** Locale-aware date formatting bound to the active locale. */
  formatDate: (value: Date | number | string, options?: Intl.DateTimeFormatOptions) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function currentDocumentLocale(): Locale {
  if (typeof document === "undefined") {
    return DEFAULT_LOCALE;
  }
  const value = document.documentElement.getAttribute("data-locale");
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  // Seed from the attribute the no-flash script already set, so client state
  // matches what is painted and SSR markup stays stable.
  const { config, isLoaded } = useInstitution();
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(currentDocumentLocale());
  }, []);

  useEffect(() => {
    if (!isLoaded || !isLocale(config.default_language)) return;
    let stored: string | null = null;
    try { stored = window.localStorage.getItem(LOCALE_STORAGE_KEY); } catch { /* Storage is optional. */ }
    const next = isLocale(stored) ? stored : config.default_language;
    setLocaleState(next);
    document.documentElement.setAttribute("lang", LOCALE_BCP47[next]);
    document.documentElement.setAttribute("data-locale", next);
  }, [isLoaded, config.default_language]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    document.documentElement.setAttribute("lang", LOCALE_BCP47[next]);
    document.documentElement.setAttribute("data-locale", next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // Persistence is best-effort; the in-memory choice still applies.
    }
  }, []);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key) => MESSAGES[locale][key] ?? MESSAGES[DEFAULT_LOCALE][key] ?? key,
      formatNumber: (input, options) => formatNumberFor(locale, input, options),
      formatDate: (input, options) => formatDateFor(locale, input, options),
    }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

function useLocaleContext(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error("useLocale/useTranslations must be used within a LocaleProvider");
  }
  return context;
}

export function useLocale(): LocaleContextValue {
  return useLocaleContext();
}

/** Convenience hook returning just the translate function. */
export function useTranslations(): LocaleContextValue["t"] {
  return useLocaleContext().t;
}
