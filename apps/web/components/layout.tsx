import { type CSSProperties, type ReactNode } from "react";

/**
 * Layout-zoning scaffolds (#182). One predictable skeleton so every screen
 * places features in the same zones instead of hand-rolled per-page markup:
 *
 *   header → KPI strip → filters → work surface (+ optional detail rail) → states
 *
 * Density (`comfortable` | `compact`) switches spacing tokens only, via a
 * `data-density` attribute the CSS reads. Routes compose these; they should not
 * add new top-level page CSS.
 */

export type Density = "comfortable" | "compact";

export function WorkspacePage({
  density = "comfortable",
  header,
  kpis,
  filters,
  detail,
  children,
}: {
  density?: Density;
  header?: ReactNode;
  kpis?: ReactNode;
  filters?: ReactNode;
  detail?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="ws-page" data-density={density}>
      {header ? <div className="ws-zone ws-zone-header">{header}</div> : null}
      {kpis ? <div className="ws-zone ws-zone-kpis">{kpis}</div> : null}
      {filters ? <div className="ws-zone ws-zone-filters">{filters}</div> : null}
      <div className={`ws-body${detail ? " ws-body-with-detail" : ""}`}>
        <div className="ws-zone ws-zone-work">{children}</div>
        {detail ? <aside className="ws-zone ws-zone-detail">{detail}</aside> : null}
      </div>
    </div>
  );
}

/** Responsive auto-fit strip for KPI cards. `min` controls the smallest column. */
export function KpiStrip({ children, min = "220px" }: { children: ReactNode; min?: string }) {
  return (
    <div className="ws-kpi-strip" style={{ "--ws-kpi-min": min } as CSSProperties}>
      {children}
    </div>
  );
}

/**
 * The primary work area.
 * - `single`: one column.
 * - `split`: two equal columns (e.g. table + chart) collapsing on small screens.
 * - `map-rail`: a wide map/work column + a narrower side column.
 */
export function WorkSurface({
  variant = "single",
  children,
}: {
  variant?: "single" | "split" | "map-rail";
  children: ReactNode;
}) {
  return <div className={`ws-surface ws-surface-${variant}`}>{children}</div>;
}

/** Sticky inspect panel that lives in the right detail zone. */
export function DetailRail({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="ws-detail-rail">
      {title ? <h3 className="ws-detail-rail-title">{title}</h3> : null}
      {children}
    </div>
  );
}

/** A 12-column responsive grid for ad-hoc zone composition. `span` per child via `<GridCell>`. */
export function PageGrid({ children, gap = "var(--space-4)" }: { children: ReactNode; gap?: string }) {
  return (
    <div className="ws-grid" style={{ "--ws-grid-gap": gap } as CSSProperties}>
      {children}
    </div>
  );
}

export function GridCell({ span = 12, children }: { span?: number; children: ReactNode }) {
  return (
    <div className="ws-grid-cell" style={{ "--ws-grid-span": span } as CSSProperties}>
      {children}
    </div>
  );
}
