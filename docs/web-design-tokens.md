# Web Design Tokens

The web token source is split by runtime:

- CSS variables in `apps/web/app/globals.css` under `:root, [data-theme="light"]`.
- TypeScript constants in `apps/web/lib/design-tokens.ts`.

The CSS variables are the rendering source of truth. The TypeScript map mirrors the same values for future charts, maps, and design-gallery examples.

The legacy static dashboard in `dashboard/styles.css` is not part of the Next.js bundle, so it cannot import `apps/web/app/globals.css` directly. Its root variables are intentionally mirrored to this same neutral/teal foundation and should only change when the web token source changes.

## Foundation Colors

| Token | Value | Use |
| --- | --- | --- |
| `--color-bg-app` | `#F7F8FA` | App background. |
| `--color-surface` | `#FFFFFF` | Panels, cards, tables, controls. |
| `--color-surface-subtle` | `#F1F4F7` | Hovers, wells, map fallback canvas. |
| `--color-border` | `#E2E8F0` | Standard dividers and control borders. |
| `--color-border-strong` | `#CBD5E1` | Strong dividers and selected outlines. |
| `--color-ink` | `#0F172A` | Primary text. |
| `--color-ink-secondary` | `#475569` | Secondary text and labels. |
| `--color-ink-muted` | `#64748B` | Captions and quiet metadata. |
| `--color-brand-primary` | `#0F766E` | Brand, active nav, primary emphasis. |
| `--color-brand-hover` | `#115E59` | Brand hover/pressed states. |
| `--color-brand-tint` | `#F0FDFA` | Selected rows and subtle active backgrounds. |
| `--color-accent` | `#C2410C` | Sparse secondary emphasis. |

## Status And Provisional Risk Colors

Status colors are available now for pills and operational states, including risk bands, publication tiers, confidence levels, and positive-change semantics.

| Token group | Tokens |
| --- | --- |
| Status | `--color-status-neutral`, `--color-status-info`, `--color-status-success`, `--color-status-warning`, `--color-status-danger` |
| Risk fills | `--color-risk-minimal-fill`, `--color-risk-low-fill`, `--color-risk-moderate-fill`, `--color-risk-high-fill`, `--color-risk-very-high-fill` |

## Layout Tokens

| Group | Tokens |
| --- | --- |
| Spacing | `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-6` 24px, `--space-8` 32px, `--space-12` 48px |
| Radius | `--radius-sm` 6px, `--radius-md` 8px, `--radius-lg` 12px |
| Elevation | `--shadow-sm`, `--shadow-md`, `--shadow-lg` |
| Type | `--font-display`, `--font-body`, `--font-mono`; `--type-display`, `--type-h1`, `--type-h2`, `--type-h3`, `--type-body`, `--type-body-sm`, `--type-label`, `--type-mono` |

## Typography

`apps/web/app/layout.tsx` loads IBM Plex Sans and IBM Plex Mono through `next/font/google`, exposing `--font-plex-sans` and `--font-plex-mono` on the document body. CSS maps those loaded variables to `--font-display`, `--font-body`, and `--font-mono`.

Shared primitives in `apps/web/components/ui.tsx`:

- `DisplayText` -> `--type-display`
- `Heading` levels 1/2/3 -> `--type-h1`, `--type-h2`, `--type-h3`
- `BodyText` -> `--type-body` / `--type-body-sm`
- `MonoText` -> `--type-mono`

The legacy static dashboard mirrors the same family names and type-scale variables because it is outside the Next.js bundle.

## Elevation, Motion & Focus (UX 2.0, #249)

The Apple-grade refinement added foundation tokens:

- **Elevation:** `--color-surface-raised` is the third surface step (popovers, menus, floating cards) above `--color-bg-app` (canvas) and `--color-surface` (card). In **dark** mode the three are a deliberate **neutral, near-black elevated ramp** (`#0C0E13` → `#161A22` → `#252A35`) rather than the former flat navy; in light/high-contrast the lift is carried by shadow so the raised surface stays white.
- **Motion:** `--duration-fast|base|slow` (120/200/320 ms) and `--ease-standard` / `--ease-emphasized`. Theme-agnostic, declared in the base block, inherited by every theme.
- **Focus:** `--color-focus-ring` (brand-tinted, resolves per theme).
- **Theme cross-fade:** flipping `data-theme` eases `background-color` / `border-color` / `color` together over `--duration-base`; fully disabled under `prefers-reduced-motion`. `color-scheme` is set per theme so native controls match.

Every text/surface pair — including the new `--color-surface-raised` and `--color-surface-subtle` pairs — is held to WCAG AA across **all three** themes by the gate in `lib/contrast.test.ts`.

## Compatibility Aliases

Legacy aliases such as `--bg`, `--panel`, `--ink`, `--teal`, `--rust`, `--shadow`, and `--radius-xl` remain in `globals.css` so existing components can migrate incrementally. New CSS should use the explicit `--color-*`, `--space-*`, `--radius-*`, and `--shadow-*` tokens directly.

## Rules

- Do not add raw color literals to component CSS. Add a token first, then reference it.
- Do not reintroduce body gradient washes or glass blur.
- Use neutral surfaces by default; use brand and accent colors only for state, action, or semantic meaning.
- Keep letter spacing non-negative. Use size, weight, and hierarchy instead of compressed tracking.
- Do not set component-level raw `font-family` or `font-size`; use the type tokens or shared type primitives.
