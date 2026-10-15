import { describe, expect, it } from "vitest";

import {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_BCP47,
  MESSAGES,
  formatDate,
  formatNumber,
  isLocale,
  localeInitScript,
} from "./i18n";

describe("i18n", () => {
  it("ships English and Italian plus European extensions", () => {
    expect(LOCALES).toContain("en");
    expect(LOCALES).toContain("it");
    expect(LOCALES).toContain("fr");
    expect(LOCALES).toContain("es");
    expect(LOCALES).toContain("de");
    expect(DEFAULT_LOCALE).toBe("en");
  });

  it("validates locales", () => {
    expect(isLocale("it")).toBe(true);
    expect(isLocale("fr")).toBe(true);
    expect(isLocale("es")).toBe(true);
    expect(isLocale("de")).toBe(true);
    expect(isLocale("xx")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });

  it("keeps every locale dictionary in sync with English keys", () => {
    const englishKeys = Object.keys(MESSAGES.en).sort();
    for (const locale of LOCALES) {
      expect(Object.keys(MESSAGES[locale]).sort()).toEqual(englishKeys);
    }
  });

  it("formats numbers per locale", () => {
    expect(formatNumber("en", 1234567.89)).toBe("1,234,567.89");
    expect(formatNumber("it", 1234567.89)).toBe("1.234.567,89");
  });

  it("formats dates per locale", () => {
    const date = new Date(Date.UTC(2026, 5, 17));
    // Both render a localized medium date; they must differ in wording/order.
    const en = formatDate("en", date, { dateStyle: "long", timeZone: "UTC" });
    const it = formatDate("it", date, { dateStyle: "long", timeZone: "UTC" });
    expect(en).toContain("2026");
    expect(it).toContain("2026");
    expect(it.toLowerCase()).toContain("giugno");
  });

  it("init script sets <html lang> to the BCP-47 default and is try-guarded", () => {
    const script = localeInitScript();
    expect(script).toContain(LOCALE_BCP47[DEFAULT_LOCALE]);
    expect(script).toContain("try");
    expect(script).toContain("data-locale");
  });
});
