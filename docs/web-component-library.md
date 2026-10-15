# Web Component Library

The P0 component library lives in `apps/web/components/ui.tsx`, with styling in `apps/web/app/globals.css`.

## Gallery

The component gallery route is:

```text
/workspace/_design
```

Implementation note: the App Router folder is `apps/web/app/workspace/%5Fdesign` because Next.js treats literal `_folder` names as private folders.

## P0 Components

| Component | Coverage |
| --- | --- |
| `Button` | primary, secondary, ghost, danger, sizes, loading, disabled, optional icon |
| `Badge`, `Tag`, `StatusPill` | token-bound semantic tones |
| Field set | `TextInput`, `SelectField`, `TextareaField`, `CheckboxField`, `RadioField`, `ToggleField` with label/help/error/disabled support |
| `Tabs` | keyboard-focusable native buttons with selected state |
| `Tooltip` | hover and focus-visible content |
| `Breadcrumbs` | ordered breadcrumb nav with current-page state |
| `DataTable` v2 | sortable columns, sticky header, density toggle, row selection, loading skeleton, empty state, pagination, column visibility, CSV export |

## Compatibility

`DataTable` remains compatible with the original shape:

```tsx
<DataTable columns={["City", "Band"]} rows={[["Bari", "High"]]} />
```

It also accepts structured columns and object rows:

```tsx
<DataTable
  columns={[{ field: "city", header: "City" }]}
  rows={[{ city: "Bari" }]}
  selectable
/>
```

## Review Rules

- New screens should use `Button`, field components, badges, and `DataTable` instead of raw controls.
- Component states should be visible in `/workspace/_design` before use in route migrations.
- Table columns must have stable field ids when object rows are used.
