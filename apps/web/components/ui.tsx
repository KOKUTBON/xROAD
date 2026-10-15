"use client";

import {
  useId,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { AlertTriangleIcon, InboxIcon } from "@/components/icons";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";
type ButtonVariant =
  | "primary"
  | "secondary"
  | "tertiary"
  | "destructive"
  // Legacy aliases kept for back-compat: `ghost` -> tertiary, `danger` -> destructive.
  | "ghost"
  | "danger";
type ButtonSize = "sm" | "md" | "lg";
type Density = "comfortable" | "compact";

export function DisplayText({ children }: { children: ReactNode }) {
  return <h1 className="type-display">{children}</h1>;
}

export function Heading({
  level = 2,
  children,
}: {
  level?: 1 | 2 | 3;
  children: ReactNode;
}) {
  const Tag = `h${level}` as const;
  return <Tag className={`type-heading type-heading-${level}`}>{children}</Tag>;
}

export function BodyText({
  children,
  size = "body",
}: {
  children: ReactNode;
  size?: "body" | "small";
}) {
  return <p className={`type-body type-body-${size}`}>{children}</p>;
}

export function MonoText({ children }: { children: ReactNode }) {
  return <code className="type-mono">{children}</code>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow">{children}</div>;
}

export function Button({
  children,
  className = "",
  icon,
  iconOnly = false,
  isLoading = false,
  size = "md",
  variant = "secondary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  /** Render a square icon button. Provide an accessible name via aria-label. */
  iconOnly?: boolean;
  isLoading?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
}) {
  const classes = [
    "ui-button",
    `ui-button-${variant}`,
    `ui-button-${size}`,
    iconOnly ? "ui-button-icon-only" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      {...props}
      className={classes}
      disabled={props.disabled || isLoading}
      type={props.type ?? "button"}
    >
      {isLoading ? <span className="ui-spinner" aria-hidden="true" /> : icon ? <span className="ui-button-icon">{icon}</span> : null}
      {iconOnly ? null : <span>{children}</span>}
    </button>
  );
}

export function SegmentedControl<T extends string>({
  ariaLabel,
  onChange,
  options,
  value,
}: {
  ariaLabel?: string;
  onChange: (value: T) => void;
  options: { value: T; label: ReactNode }[];
  value: T;
}) {
  return (
    <div aria-label={ariaLabel} className="ui-segmented" role="radiogroup">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            aria-checked={active}
            className={active ? "ui-segment ui-segment-active" : "ui-segment"}
            key={option.value}
            onClick={() => onChange(option.value)}
            role="radio"
            type="button"
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return <span className={`ui-badge ui-badge-${tone}`}>{children}</span>;
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="ui-tag">{children}</span>;
}

function FieldShell({
  children,
  error,
  help,
  id,
  label,
}: {
  children: ReactNode;
  error?: string;
  help?: string;
  id: string;
  label: string;
}) {
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <label className={`ui-field${error ? " ui-field-error" : ""}`} htmlFor={id}>
      <span>{label}</span>
      {children}
      {help ? <small id={helpId}>{help}</small> : null}
      {error ? <strong id={errorId}>{error}</strong> : null}
    </label>
  );
}

export function TextInput({
  error,
  help,
  label,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  error?: string;
  help?: string;
  label: string;
}) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return (
    <FieldShell error={error} help={help} id={inputId} label={label}>
      <input
        {...props}
        aria-describedby={[help ? `${inputId}-help` : "", error ? `${inputId}-error` : ""].filter(Boolean).join(" ") || undefined}
        aria-invalid={Boolean(error)}
        id={inputId}
      />
    </FieldShell>
  );
}

export function SelectField({
  children,
  error,
  help,
  label,
  id,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  error?: string;
  help?: string;
  label: string;
}) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return (
    <FieldShell error={error} help={help} id={inputId} label={label}>
      <select
        {...props}
        aria-describedby={[help ? `${inputId}-help` : "", error ? `${inputId}-error` : ""].filter(Boolean).join(" ") || undefined}
        aria-invalid={Boolean(error)}
        id={inputId}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export function TextareaField({
  error,
  help,
  label,
  id,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: string;
  help?: string;
  label: string;
}) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return (
    <FieldShell error={error} help={help} id={inputId} label={label}>
      <textarea
        {...props}
        aria-describedby={[help ? `${inputId}-help` : "", error ? `${inputId}-error` : ""].filter(Boolean).join(" ") || undefined}
        aria-invalid={Boolean(error)}
        id={inputId}
      />
    </FieldShell>
  );
}

export function CheckboxField({
  checked,
  disabled,
  help,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  help?: string;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="ui-choice">
      <input
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      <span>
        <strong>{label}</strong>
        {help ? <small>{help}</small> : null}
      </span>
    </label>
  );
}

export function RadioField({
  checked,
  disabled,
  help,
  label,
  name,
  onChange,
  value,
}: {
  checked: boolean;
  disabled?: boolean;
  help?: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="ui-choice">
      <input
        checked={checked}
        disabled={disabled}
        name={name}
        onChange={() => onChange(value)}
        type="radio"
        value={value}
      />
      <span>
        <strong>{label}</strong>
        {help ? <small>{help}</small> : null}
      </span>
    </label>
  );
}

export function ToggleField({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      aria-pressed={checked}
      className={`ui-toggle${checked ? " ui-toggle-on" : ""}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      type="button"
    >
      <span aria-hidden="true" />
      {label}
    </button>
  );
}

export function Tabs({
  defaultValue,
  items,
}: {
  defaultValue?: string;
  items: Array<{ content: ReactNode; label: string; value: string }>;
}) {
  const [active, setActive] = useState(defaultValue ?? items[0]?.value ?? "");
  const activeItem = items.find((item) => item.value === active) ?? items[0];
  return (
    <div className="ui-tabs">
      <div className="ui-tab-list" role="tablist">
        {items.map((item) => (
          <button
            aria-selected={item.value === active}
            className={item.value === active ? "ui-tab ui-tab-active" : "ui-tab"}
            key={item.value}
            onClick={() => setActive(item.value)}
            role="tab"
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="ui-tab-panel" role="tabpanel">
        {activeItem?.content}
      </div>
    </div>
  );
}

export function Tooltip({
  children,
  content,
}: {
  children: ReactNode;
  content: string;
}) {
  return (
    <span className="ui-tooltip">
      {children}
      <span role="tooltip">{content}</span>
    </span>
  );
}

export function Breadcrumbs({
  items,
}: {
  items: Array<{ href?: string; label: string }>;
}) {
  return (
    <nav aria-label="Breadcrumb" className="ui-breadcrumbs">
      <ol>
        {items.map((item, index) => (
          <li key={`${item.label}:${index}`}>
            {item.href ? <a href={item.href}>{item.label}</a> : <span aria-current="page">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <section className="page-header">
      <div className="page-header-copy">
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2>{title}</h2>
        <p>{description}</p>
        {meta ? <div className="chip-row">{meta}</div> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </section>
  );
}

/**
 * Card primitive (#255). One elevated surface — token-driven border/radius/
 * background per theme, consistent internal padding — with header / body /
 * footer slots. `actions` sit top-right of the header; `footer` is a divided
 * trailing slot (e.g. for a primary action or summary). Every summary/list
 * surface should compose this rather than hand-rolling a card.
 */
export function Panel({
  title,
  detail,
  children,
  actions,
  footer,
  accent = "slate",
}: {
  title: string;
  detail?: string;
  children: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  accent?: "slate" | "teal" | "rust";
}) {
  return (
    <section className={`panel panel-${accent}`}>
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          {detail ? <p>{detail}</p> : null}
        </div>
        {actions ? <div className="panel-header-actions">{actions}</div> : null}
      </div>
      {children}
      {footer ? <div className="panel-footer">{footer}</div> : null}
    </section>
  );
}

/**
 * Grouped list (#255). An Apple System-Settings–style inset list: rows with
 * dividers, each with an optional leading icon, a label (+ optional detail),
 * and a trailing value and/or control. Use for settings, governance, scope,
 * and status-breakdown surfaces so they all read the same.
 */
export function GroupedList({
  children,
  ariaLabel,
}: {
  children: ReactNode;
  ariaLabel?: string;
}) {
  return (
    <ul aria-label={ariaLabel} className="ui-grouped-list" role="list">
      {children}
    </ul>
  );
}

export function GroupedRow({
  icon,
  label,
  detail,
  value,
  control,
}: {
  icon?: ReactNode;
  label: ReactNode;
  detail?: ReactNode;
  value?: ReactNode;
  control?: ReactNode;
}) {
  return (
    <li className="ui-grouped-row">
      {icon ? (
        <span aria-hidden="true" className="ui-grouped-row-icon">
          {icon}
        </span>
      ) : null}
      <span className="ui-grouped-row-text">
        <span className="ui-grouped-row-label">{label}</span>
        {detail ? <span className="ui-grouped-row-detail">{detail}</span> : null}
      </span>
      {value != null ? <span className="ui-grouped-row-value">{value}</span> : null}
      {control ?? null}
    </li>
  );
}

export function FilterBar({
  children,
  summary,
}: {
  children: ReactNode;
  summary?: ReactNode;
}) {
  return (
    <section className="filter-bar" aria-label="View filters">
      <div className="filter-controls">{children}</div>
      {summary ? <div className="filter-summary">{summary}</div> : null}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  footnote,
  tone = "slate",
}: {
  label: string;
  value: string | number;
  footnote?: string;
  tone?: "slate" | "teal" | "rust";
}) {
  return (
    <div className={`metric-card metric-card-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {footnote ? <small>{footnote}</small> : null}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
  icon,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <section className="state-panel state-empty" role="status">
      <span className="state-icon" aria-hidden="true">
        {icon ?? <InboxIcon size={20} />}
      </span>
      <strong>{title}</strong>
      <p>{detail}</p>
      {action ? <div className="hero-actions">{action}</div> : null}
    </section>
  );
}

export function LoadingState({
  title = "Loading view",
  detail = "The workspace is preparing the latest available data for this view.",
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <section className="state-panel state-loading" role="status" aria-live="polite">
      <strong>{title}</strong>
      <p>{detail}</p>
      <span className="state-loader" aria-hidden="true" />
    </section>
  );
}

export function ErrorState({
  title = "Data unavailable",
  detail,
  action,
}: {
  title?: string;
  detail: string;
  /** Optional recovery control, e.g. a retry button. */
  action?: ReactNode;
}) {
  return (
    <section className="state-panel state-error" role="alert">
      <span className="state-icon state-icon-danger" aria-hidden="true">
        <AlertTriangleIcon size={20} />
      </span>
      <strong>{title}</strong>
      <p>{detail}</p>
      {action ? <div className="hero-actions">{action}</div> : null}
    </section>
  );
}

export function NoAccessState({
  title = "Access required",
  detail,
  action,
}: {
  title?: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <section className="state-panel state-no-access" role="status">
      <h2 className="state-title">{title}</h2>
      <p>{detail}</p>
      {action ? <div className="hero-actions">{action}</div> : null}
    </section>
  );
}

export function StatusPill({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: Tone;
}) {
  return <span className={`status-pill status-${tone}`}>{label}</span>;
}

export function NavChip({ children }: { children: ReactNode }) {
  return <span className="nav-chip">{children}</span>;
}

export function WorkflowCard({
  label,
  outcome,
  route,
  audience,
}: {
  label: string;
  outcome: string;
  route?: string;
  audience?: string;
}) {
  return (
    <article className="workflow-card">
      <div>
        {audience ? <span>{audience}</span> : null}
        <strong>{label}</strong>
      </div>
      <p>{outcome}</p>
      {route ? <small>{route}</small> : null}
    </article>
  );
}

export function WarningState({
  title,
  detail,
  tone = "warning",
}: {
  title: string;
  detail: string;
  tone?: "warning" | "danger";
}) {
  return (
    <div className={`warning-state warning-state-${tone}`} role="status">
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export interface DataTableColumn {
  field: string;
  header: string;
  hidden?: boolean;
}

function normalizeColumns(columns: string[] | DataTableColumn[]): DataTableColumn[] {
  return columns.map((column) =>
    typeof column === "string" ? { field: column, header: column } : column,
  );
}

function normalizeRows(
  rows: string[][] | Array<Record<string, string | number | null | undefined>>,
  columns: DataTableColumn[],
): string[][] {
  return rows.map((row) => {
    if (Array.isArray(row)) {
      return row.map((cell) => String(cell ?? ""));
    }
    return columns.map((column) => String(row[column.field] ?? ""));
  });
}

function downloadCsv(columns: DataTableColumn[], rows: string[][]): void {
  const escapeCell = (value: string) => `"${value.replaceAll('"', '""')}"`;
  const csv = [
    columns.map((column) => escapeCell(column.header)).join(","),
    ...rows.map((row) => row.map(escapeCell).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "road-risk-table.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function DataTable({
  columns,
  rows,
  emptyMessage = "No rows available.",
  isLoading = false,
  pageSize = 8,
  selectable = false,
  showControls = true,
}: {
  columns: string[] | DataTableColumn[];
  rows: string[][] | Array<Record<string, string | number | null | undefined>>;
  emptyMessage?: string;
  isLoading?: boolean;
  pageSize?: number;
  selectable?: boolean;
  showControls?: boolean;
}) {
  const normalizedColumns = useMemo(() => normalizeColumns(columns), [columns]);
  const normalizedRows = useMemo(() => normalizeRows(rows, normalizedColumns), [rows, normalizedColumns]);
  const [density, setDensity] = useState<Density>("comfortable");
  const [page, setPage] = useState(0);
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [sort, setSort] = useState<{ column: number; direction: "asc" | "desc" } | null>(null);
  const [hiddenColumns, setHiddenColumns] = useState<Set<number>>(
    () => new Set(normalizedColumns.flatMap((column, index) => (column.hidden ? [index] : []))),
  );

  const visibleColumns = normalizedColumns
    .map((column, index) => ({ column, index }))
    .filter(({ index }) => !hiddenColumns.has(index));

  const sortedRows = useMemo(() => {
    if (!sort) {
      return normalizedRows.map((row, index) => ({ row, index }));
    }
    return normalizedRows
      .map((row, index) => ({ row, index }))
      .sort((left, right) => {
        const leftValue = left.row[sort.column] ?? "";
        const rightValue = right.row[sort.column] ?? "";
        const result = leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: "base" });
        return sort.direction === "asc" ? result : -result;
      });
  }, [normalizedRows, sort]);

  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = sortedRows.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  function toggleSort(index: number) {
    setSort((current) => {
      if (!current || current.column !== index) {
        return { column: index, direction: "asc" };
      }
      if (current.direction === "asc") {
        return { column: index, direction: "desc" };
      }
      return null;
    });
  }

  function toggleRow(index: number) {
    setSelectedRows((current) => {
      const next = new Set(current);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  return (
    <div className={`table-shell data-table data-table-${density}`}>
      {showControls ? (
        <div className="data-table-controls">
          <div className="chip-row">
            <Button size="sm" variant="ghost" onClick={() => setDensity(density === "comfortable" ? "compact" : "comfortable")}>
              {density === "comfortable" ? "Compact" : "Comfortable"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => downloadCsv(normalizedColumns, normalizedRows)}>
              Export CSV
            </Button>
          </div>
          <details className="data-table-columns">
            <summary>Columns</summary>
            {normalizedColumns.map((column, index) => (
              <CheckboxField
                checked={!hiddenColumns.has(index)}
                key={column.field}
                label={column.header}
                onChange={(checked) =>
                  setHiddenColumns((current) => {
                    const next = new Set(current);
                    if (checked) {
                      next.delete(index);
                    } else {
                      next.add(index);
                    }
                    return next;
                  })
                }
              />
            ))}
          </details>
        </div>
      ) : null}

      <table>
        <thead>
          <tr>
            {selectable ? <th aria-label="Row selection" /> : null}
            {visibleColumns.map(({ column, index }) => (
              <th
                aria-sort={
                  sort?.column === index ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
                }
                key={column.field}
              >
                <button
                  aria-label={`Sort by ${column.header}`}
                  className="data-table-sort"
                  onClick={() => toggleSort(index)}
                  type="button"
                >
                  {column.header}
                  {sort?.column === index ? <span aria-hidden="true">{sort.direction === "asc" ? " ↑" : " ↓"}</span> : null}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? Array.from({ length: Math.min(pageSize, 4) }).map((_, rowIndex) => (
                <tr key={`skeleton-${rowIndex}`}>
                  {selectable ? <td><span className="data-table-skeleton" /></td> : null}
                  {visibleColumns.map(({ column }) => (
                    <td key={`${rowIndex}:${column.field}`}><span className="data-table-skeleton" /></td>
                  ))}
                </tr>
              ))
            : pageRows.map(({ row, index }) => (
                <tr className={selectedRows.has(index) ? "data-table-row-selected" : ""} key={`${index}:${row.join("|")}`}>
                  {selectable ? (
                    <td>
                      <input
                        aria-label={`Select row ${index + 1}`}
                        checked={selectedRows.has(index)}
                        onChange={() => toggleRow(index)}
                        type="checkbox"
                      />
                    </td>
                  ) : null}
                  {visibleColumns.map(({ index: columnIndex }) => (
                    <td key={`${index}:${columnIndex}`}>{row[columnIndex]}</td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>

      {!isLoading && normalizedRows.length === 0 ? (
        <div className="data-table-empty" role="status">{emptyMessage}</div>
      ) : null}
      {showControls ? (
        <div className="data-table-footer">
          <span>{selectedRows.size > 0 ? `${selectedRows.size} selected` : `${normalizedRows.length} rows`}</span>
          <div className="chip-row">
            <Button disabled={currentPage === 0} size="sm" variant="ghost" onClick={() => setPage((value) => Math.max(0, value - 1))}>
              Previous
            </Button>
            <span>Page {currentPage + 1} of {pageCount}</span>
            <Button disabled={currentPage >= pageCount - 1} size="sm" variant="ghost" onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function Skeleton({
  width = "100%",
  height = "1rem",
  radius = "var(--radius-sm)",
}: {
  width?: string;
  height?: string;
  radius?: string;
}) {
  return <span aria-hidden="true" className="skeleton" style={{ width, height, borderRadius: radius }} />;
}

export function Pagination({
  page,
  pageCount,
  onChange,
}: {
  page: number;
  pageCount: number;
  onChange: (page: number) => void;
}) {
  const safeCount = Math.max(1, pageCount);
  const current = Math.min(Math.max(0, page), safeCount - 1);
  return (
    <nav aria-label="Pagination" className="pagination">
      <Button disabled={current === 0} onClick={() => onChange(current - 1)} size="sm" variant="ghost">
        Previous
      </Button>
      <span className="pagination-status">
        Page {current + 1} of {safeCount}
      </span>
      <Button disabled={current >= safeCount - 1} onClick={() => onChange(current + 1)} size="sm" variant="ghost">
        Next
      </Button>
    </nav>
  );
}

export interface StepperStep {
  label: string;
  detail?: string;
}

export function Stepper({ steps, current }: { steps: StepperStep[]; current: number }) {
  return (
    <ol className="stepper">
      {steps.map((step, index) => {
        const state = index < current ? "done" : index === current ? "current" : "pending";
        return (
          <li aria-current={state === "current" ? "step" : undefined} className={`stepper-step stepper-${state}`} key={step.label}>
            <span aria-hidden="true" className="stepper-index">
              {state === "done" ? "✓" : index + 1}
            </span>
            <span className="stepper-copy">
              <span className="stepper-label">{step.label}</span>
              {step.detail ? <span className="stepper-detail">{step.detail}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
