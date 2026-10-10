/**
 * Lightweight, dependency-free internationalisation for the web app.
 *
 * EU public-sector tools must support multilingual UI for a credible
 * multi-country deployment. Rather than pull in a full i18n framework, this
 * mirrors the existing theme pattern: a small dictionary, a `<html lang>`
 * no-flash init script, locale-aware `Intl` formatters, and a React context
 * (`components/locale-provider.tsx`). New strings are added to the dictionaries
 * below and read with `useTranslations()`.
 *
 * Locales supported: English (`en`), Italian (`it`), French (`fr`),
 * Spanish (`es`), and German (`de`).
 */

export const LOCALES = ["en", "it", "fr", "es", "de"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

/** localStorage key holding the user's explicit locale choice. */
export const LOCALE_STORAGE_KEY = "road-risk-web-locale-v1";

/** Native-language labels for the locale switcher (endonyms). */
export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  it: "Italiano",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
};

/** BCP-47 tags used for `Intl` formatting and the `<html lang>` attribute. */
export const LOCALE_BCP47: Record<Locale, string> = {
  en: "en-GB",
  it: "it-IT",
  fr: "fr-FR",
  es: "es-ES",
  de: "de-DE",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/** Dictionary keys translated for the shell chrome. Extend incrementally. */
export interface Messages {
  "shell.search": string;
  "shell.refresh": string;
  "shell.theme": string;
  "shell.language": string;
  "shell.collapse": string;
  "shell.openNav": string;
  "shell.closeNav": string;
  "shell.org": string;
  "shell.city": string;
  "shell.workspace": string;
  "shell.signIn": string;
  "shell.signOut": string;
  "env.live": string;
  "env.demo": string;
  "env.public": string;
}

export const MESSAGES: Record<Locale, Messages> = {
  en: {
    "shell.search": "Search",
    "shell.refresh": "Refresh",
    "shell.theme": "Theme",
    "shell.language": "Language",
    "shell.collapse": "Collapse",
    "shell.openNav": "Open navigation",
    "shell.closeNav": "Close navigation",
    "shell.org": "Org",
    "shell.city": "City",
    "shell.workspace": "Workspace",
    "shell.signIn": "Sign in",
    "shell.signOut": "Sign out",
    "env.live": "Live",
    "env.demo": "Demo",
    "env.public": "Public",
  },
  it: {
    "shell.search": "Cerca",
    "shell.refresh": "Aggiorna",
    "shell.theme": "Tema",
    "shell.language": "Lingua",
    "shell.collapse": "Comprimi",
    "shell.openNav": "Apri navigazione",
    "shell.closeNav": "Chiudi navigazione",
    "shell.org": "Ente",
    "shell.city": "Città",
    "shell.workspace": "Area di lavoro",
    "shell.signIn": "Accedi",
    "shell.signOut": "Esci",
    "env.live": "Attivo",
    "env.demo": "Demo",
    "env.public": "Pubblico",
  },
  fr: {
    "shell.search": "Rechercher",
    "shell.refresh": "Actualiser",
    "shell.theme": "Thème",
    "shell.language": "Langue",
    "shell.collapse": "Réduire",
    "shell.openNav": "Ouvrir le menu",
    "shell.closeNav": "Fermer le menu",
    "shell.org": "Institution",
    "shell.city": "Ville",
    "shell.workspace": "Espace de travail",
    "shell.signIn": "Connexion",
    "shell.signOut": "Déconnexion",
    "env.live": "En direct",
    "env.demo": "Démo",
    "env.public": "Public",
  },
  es: {
    "shell.search": "Buscar",
    "shell.refresh": "Actualizar",
    "shell.theme": "Tema",
    "shell.language": "Idioma",
    "shell.collapse": "Contraer",
    "shell.openNav": "Abrir navegación",
    "shell.closeNav": "Cerrar navegación",
    "shell.org": "Entidad",
    "shell.city": "Ciudad",
    "shell.workspace": "Área de trabajo",
    "shell.signIn": "Iniciar sesión",
    "shell.signOut": "Cerrar sesión",
    "env.live": "En vivo",
    "env.demo": "Demo",
    "env.public": "Público",
  },
  de: {
    "shell.search": "Suchen",
    "shell.refresh": "Aktualisieren",
    "shell.theme": "Design",
    "shell.language": "Sprache",
    "shell.collapse": "Einklappen",
    "shell.openNav": "Navigation öffnen",
    "shell.closeNav": "Navigation schließen",
    "shell.org": "Organisation",
    "shell.city": "Stadt",
    "shell.workspace": "Arbeitsbereich",
    "shell.signIn": "Anmelden",
    "shell.signOut": "Abmelden",
    "env.live": "Live",
    "env.demo": "Demo",
    "env.public": "Öffentlich",
  },
};

/** Locale-aware number formatting. */
export function formatNumber(
  locale: Locale,
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(LOCALE_BCP47[locale], options).format(value);
}

/** Locale-aware date formatting. */
export function formatDate(
  locale: Locale,
  value: Date | number | string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(LOCALE_BCP47[locale], options).format(date);
}

/**
 * Blocking script injected in `<head>` that applies the persisted locale to
 * `<html lang>` before hydration. Dependency-free and `try`-guarded so a
 * locked-down `localStorage` never breaks first paint.
 */
export function localeInitScript(): string {
  return `(function(){try{var k=${JSON.stringify(
    LOCALE_STORAGE_KEY,
  )};var l=localStorage.getItem(k);var valid=${JSON.stringify(
    LOCALES,
  )};var map=${JSON.stringify(LOCALE_BCP47)};if(valid.indexOf(l)===-1){l=${JSON.stringify(
    DEFAULT_LOCALE,
  )};}document.documentElement.setAttribute("lang",map[l]||${JSON.stringify(
    LOCALE_BCP47[DEFAULT_LOCALE],
  )});document.documentElement.setAttribute("data-locale",l);}catch(e){document.documentElement.setAttribute("lang",${JSON.stringify(
    LOCALE_BCP47[DEFAULT_LOCALE],
  )});}})();`;
}
