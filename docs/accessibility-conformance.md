# Accessibility Conformance Statement (EN 301 549 / WCAG 2.1 AA)

This is the accessibility conformance statement for the RARM web application
(`apps/web`). EU public-sector tools fall under the **Web Accessibility
Directive (EU) 2016/2102**, whose technical standard is **EN 301 549**, which in
turn adopts **WCAG 2.1 Level AA**.

## Conformance status

**Partially conformant** with WCAG 2.1 AA — the application is built and
continuously tested to AA, with the limitations noted below. "Partially
conformant" is the honest status because the interactive **risk map** (a
third-party canvas/WebGL component) cannot be fully expressed to assistive
technology and is mitigated rather than made natively conformant.

## Evidence base

| Mechanism | What it covers | Where |
| --- | --- | --- |
| **Automated axe-core A/AA gate** | Runs axe-core with tags `wcag2a, wcag2aa, wcag21a, wcag21aa` across **every route** (public home, login, and all internal workspace routes), under both desktop and mobile projects; **fails CI on any violation** | `apps/web/e2e/accessibility.spec.ts` |
| **Token contrast gate** | Pins the design-token palette so colour-contrast ratios cannot regress | `apps/web/lib/contrast.ts` (+ test) |
| **High-contrast theme** | A `high-contrast` `data-theme` variant for low-vision users | `apps/web/lib/theme.ts` |
| **Manual audit** | Keyboard, focus, landmarks, zoom (see below) | this document |

The automated gate is the primary continuous control; the manual audit covers
what automation cannot (keyboard flows, focus order, meaningful sequence).

## Manual audit summary

Checked against the WCAG 2.1 AA success criteria most relevant to this app:

- **Keyboard operability (2.1.1):** primary navigation, scope/theme/language
  switchers, command palette (⌘K), and forms are keyboard-reachable and
  operable. Selects use native `<select>` for full AT support.
- **Focus visible (2.4.7):** focus styling is preserved via the token system.
- **Landmarks & headings (1.3.1, 2.4.1):** `<header>`, `<nav aria-label>`,
  `<aside>`, `<main>` regions; breadcrumb uses `aria-current="page"`.
- **Name, role, value (4.1.2):** interactive controls carry `aria-label`s
  (now localised — see multilingual section).
- **Contrast (1.4.3):** enforced by the token contrast gate + high-contrast theme.
- **Language of page (3.1.1):** `<html lang>` is set and **updates with the
  locale switcher** (see below).
- **Reflow / zoom (1.4.10, 1.4.4):** responsive layout verified at mobile width
  and 200% zoom via the mobile Playwright project.

## Known limitations

| Limitation | WCAG ref | Mitigation |
| --- | --- | --- |
| Interactive **risk map** (MapLibre canvas/WebGL) is not fully expressible to screen readers | 1.1.1, 4.1.2 | The same data is available in **accessible tabular/report surfaces** (reports hub, analyst tables) and an **accessible map legend**; the map is an enhancement, not the only path to the data |
| Some deep analyst data-viz convey trend via colour | 1.4.1 | Paired with text/rank labels; high-contrast theme available |

These are tracked for incremental improvement; none blocks access to the
underlying information through an alternative conformant route.

## Multilingual readiness

A credible multi-country EU deployment needs multilingual UI. The app now ships
a dependency-free i18n layer (`apps/web/lib/i18n.ts`,
`apps/web/components/locale-provider.tsx`):

- **Languages:** English (`en`) and Italian (`it`, first pilot country),
  selectable from the utility-bar **language switcher**.
- **`<html lang>` correctness:** the locale switcher updates `<html lang>`
  (en-GB / it-IT) at runtime and a no-flash init script sets it before paint —
  satisfying WCAG **3.1.1 Language of Page** in both languages.
- **Locale-aware formatting:** `formatNumber` / `formatDate` use `Intl` with the
  active locale (BCP-47), so numbers, dates, and units render per locale.
- **Extensibility:** adding a pilot language is one entry in the `MESSAGES`
  dictionary; new strings are read via `useTranslations()`.

The shell chrome is fully localised; remaining deep-surface strings are
translated incrementally through the same `t()` API.

## Feedback and enforcement

Each deploying public body should publish this statement with a **feedback
contact** and the national enforcement-body escalation path, per the Web
Accessibility Directive. The platform provides the technical conformance; the
controller provides the deployment-specific contact details.

## Reproduce the automated evidence

```bash
cd apps/web
npm run e2e   # runs the axe A/AA gate across all routes (desktop + mobile)
```

> Note: CI is currently blocked on account billing, so the gate is run locally;
> it is wired to fail on any A/AA violation when CI is restored.
