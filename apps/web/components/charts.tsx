"use client";

import { type ReactNode, useId } from "react";

import {
  arcPath,
  areaPath,
  linePath,
  niceExtent,
  scale,
  segmentAngles,
  seriesPoints,
  ticks,
} from "@/lib/charts";

/**
 * Token-bound SVG chart kit (#179). Every chart:
 * - draws only with design tokens (risk ramp for severity, green reserved for
 *   positive change, status hues for workflow) — no raw hex;
 * - is accessible: `role="img"` with a title + description and a
 *   visually-hidden data-table fallback;
 * - scales responsively via viewBox (no fixed pixel width);
 * - inherits the global reduced-motion + focus rules from #177.
 */

export type ChartTone =
  | "brand"
  | "positive"
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "risk-minimal"
  | "risk-low"
  | "risk-moderate"
  | "risk-high"
  | "risk-very-high";

const TONE_VARS: Record<ChartTone, string> = {
  brand: "var(--color-brand-primary)",
  positive: "var(--color-positive-change)",
  neutral: "var(--color-status-neutral)",
  info: "var(--color-status-info)",
  success: "var(--color-status-success)",
  warning: "var(--color-status-warning)",
  danger: "var(--color-status-danger)",
  "risk-minimal": "var(--color-risk-minimal-fill)",
  "risk-low": "var(--color-risk-low-fill)",
  "risk-moderate": "var(--color-risk-moderate-fill)",
  "risk-high": "var(--color-risk-high-fill)",
  "risk-very-high": "var(--color-risk-very-high-fill)",
};

export function toneVar(tone: ChartTone): string {
  return TONE_VARS[tone];
}

function ChartFigure({
  title,
  description,
  viewBox,
  caption,
  table,
  children,
}: {
  title: string;
  description: string;
  viewBox: string;
  caption?: ReactNode;
  table: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <figure className="chart">
      <svg
        aria-labelledby={`${id}-title ${id}-desc`}
        className="chart-svg"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        viewBox={viewBox}
      >
        <title id={`${id}-title`}>{title}</title>
        <desc id={`${id}-desc`}>{description}</desc>
        {children}
      </svg>
      <div className="chart-sr-only">{table}</div>
      {caption ? <figcaption className="chart-caption">{caption}</figcaption> : null}
    </figure>
  );
}

function dataTable(columns: string[], rows: Array<Array<string | number>>): ReactNode {
  return (
    <table>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column}>{column}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index}>
            {row.map((cell, cellIndex) => (
              <td key={cellIndex}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Compact trend glyph — no axes. For KPI cards and inline cells. */
export function Sparkline({
  values,
  tone = "brand",
  title,
  width = 120,
  height = 36,
}: {
  values: number[];
  tone?: ChartTone;
  title: string;
  width?: number;
  height?: number;
}) {
  const domain = niceExtent(values);
  const points = seriesPoints(values, width, height, 3, domain);
  const color = toneVar(tone);
  return (
    <ChartFigure
      description={`Trend across ${values.length} points, from ${values[0] ?? 0} to ${values[values.length - 1] ?? 0}.`}
      table={dataTable(["Point", "Value"], values.map((value, index) => [index + 1, value]))}
      title={title}
      viewBox={`0 0 ${width} ${height}`}
    >
      <path d={areaPath(points, height - 3)} fill={color} opacity="0.12" />
      <path d={linePath(points)} fill="none" stroke={color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </ChartFigure>
  );
}

interface TrendSeries {
  label: string;
  values: number[];
  tone?: ChartTone;
}

/** Multi-series line chart with optional reference band and y ticks. */
export function TrendLine({
  series,
  xLabels,
  title,
  description,
  referenceBand,
  caption,
  height = 220,
  width = 460,
}: {
  series: TrendSeries[];
  xLabels: string[];
  title: string;
  description: string;
  referenceBand?: { from: number; to: number; label: string };
  caption?: ReactNode;
  height?: number;
  width?: number;
}) {
  const padding = 32;
  const allValues = series.flatMap((line) => line.values);
  const domain = niceExtent(allValues, true);
  const y = scale(domain, [height - padding, padding]);
  const yTicks = ticks(domain[0], domain[1], 4);

  return (
    <ChartFigure
      caption={caption}
      description={description}
      table={dataTable(
        ["Period", ...series.map((line) => line.label)],
        xLabels.map((label, index) => [label, ...series.map((line) => line.values[index] ?? "")]),
      )}
      title={title}
      viewBox={`0 0 ${width} ${height}`}
    >
      {yTicks.map((tick) => (
        <g key={tick}>
          <line
            className="chart-gridline"
            x1={padding}
            x2={width - padding}
            y1={y(tick)}
            y2={y(tick)}
          />
          <text className="chart-axis-label" x={padding - 6} y={y(tick) + 4} textAnchor="end">
            {tick}
          </text>
        </g>
      ))}
      {referenceBand ? (
        <rect
          fill="var(--color-brand-tint)"
          height={Math.abs(y(referenceBand.from) - y(referenceBand.to))}
          opacity="0.7"
          width={width - padding * 2}
          x={padding}
          y={Math.min(y(referenceBand.from), y(referenceBand.to))}
        />
      ) : null}
      {series.map((line) => {
        const points = seriesPoints(line.values, width, height, padding, domain);
        const color = toneVar(line.tone ?? "brand");
        return (
          <g key={line.label}>
            <path d={linePath(points)} fill="none" stroke={color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
            {points.map((point, index) => (
              <circle cx={point.x} cy={point.y} fill={color} key={index} r="3" />
            ))}
          </g>
        );
      })}
      {xLabels.map((label, index) => {
        const step = xLabels.length > 1 ? (width - padding * 2) / (xLabels.length - 1) : 0;
        return (
          <text className="chart-axis-label" key={label} textAnchor="middle" x={padding + index * step} y={height - 10}>
            {label}
          </text>
        );
      })}
    </ChartFigure>
  );
}

interface Bar {
  label: string;
  value: number;
  tone?: ChartTone;
}

/** Vertical bar chart. */
export function BarChart({
  bars,
  title,
  description,
  caption,
  unit = "",
  height = 200,
  width = 420,
}: {
  bars: Bar[];
  title: string;
  description: string;
  caption?: ReactNode;
  unit?: string;
  height?: number;
  width?: number;
}) {
  const padding = 28;
  const domain = niceExtent(bars.map((bar) => bar.value), true);
  const y = scale(domain, [height - padding, padding]);
  const baseline = y(Math.max(0, domain[0]));
  const slot = (width - padding * 2) / Math.max(1, bars.length);
  const barWidth = slot * 0.6;

  return (
    <ChartFigure
      caption={caption}
      description={description}
      table={dataTable(["Category", "Value"], bars.map((bar) => [bar.label, `${bar.value}${unit}`]))}
      title={title}
      viewBox={`0 0 ${width} ${height}`}
    >
      <line stroke="var(--color-border-strong)" strokeWidth="1" x1={padding} x2={width - padding} y1={baseline} y2={baseline} />
      {bars.map((bar, index) => {
        const top = y(bar.value);
        const x = padding + index * slot + (slot - barWidth) / 2;
        return (
          <g key={bar.label}>
            <rect
              fill={toneVar(bar.tone ?? "brand")}
              height={Math.abs(baseline - top)}
              rx="3"
              width={barWidth}
              x={x}
              y={Math.min(baseline, top)}
            />
            <text className="chart-axis-label" textAnchor="middle" x={x + barWidth / 2} y={height - 8}>
              {bar.label}
            </text>
          </g>
        );
      })}
    </ChartFigure>
  );
}

/** Signed before/after delta bars. Improvement (default: a decrease) is green. */
export function DeltaBar({
  items,
  title,
  description,
  caption,
  goodDirection = "down",
  unit = "",
  height = 200,
  width = 420,
}: {
  items: Array<{ label: string; before: number; after: number }>;
  title: string;
  description: string;
  caption?: ReactNode;
  goodDirection?: "down" | "up";
  unit?: string;
  height?: number;
  width?: number;
}) {
  const padding = 28;
  const deltas = items.map((item) => item.after - item.before);
  const domain = niceExtent(deltas, true);
  const y = scale(domain, [height - padding, padding]);
  const zero = y(0);
  const slot = (width - padding * 2) / Math.max(1, items.length);
  const barWidth = slot * 0.55;

  return (
    <ChartFigure
      caption={caption}
      description={description}
      table={dataTable(
        ["Item", "Before", "After", "Change"],
        items.map((item) => [item.label, `${item.before}${unit}`, `${item.after}${unit}`, `${item.after - item.before > 0 ? "+" : ""}${item.after - item.before}${unit}`]),
      )}
      title={title}
      viewBox={`0 0 ${width} ${height}`}
    >
      <line stroke="var(--color-border-strong)" strokeWidth="1" x1={padding} x2={width - padding} y1={zero} y2={zero} />
      {items.map((item, index) => {
        const delta = item.after - item.before;
        const improved = goodDirection === "down" ? delta < 0 : delta > 0;
        const color = delta === 0 ? toneVar("neutral") : improved ? toneVar("positive") : toneVar("danger");
        const top = y(delta);
        const x = padding + index * slot + (slot - barWidth) / 2;
        return (
          <g key={item.label}>
            <rect fill={color} height={Math.abs(zero - top)} rx="3" width={barWidth} x={x} y={Math.min(zero, top)} />
            <text className="chart-axis-label" textAnchor="middle" x={x + barWidth / 2} y={height - 8}>
              {item.label}
            </text>
          </g>
        );
      })}
    </ChartFigure>
  );
}

interface Segment {
  label: string;
  value: number;
  tone?: ChartTone;
}

const RISK_RAMP_TONES: ChartTone[] = ["risk-minimal", "risk-low", "risk-moderate", "risk-high", "risk-very-high"];

/** Donut / gauge with an optional center label. */
export function Donut({
  segments,
  title,
  description,
  centerLabel,
  caption,
  size = 200,
}: {
  segments: Segment[];
  title: string;
  description: string;
  centerLabel?: string;
  caption?: ReactNode;
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 6;
  const rInner = rOuter * 0.62;
  const angles = segmentAngles(segments.map((segment) => segment.value));

  return (
    <ChartFigure
      caption={caption}
      description={description}
      table={dataTable(["Segment", "Value"], segments.map((segment) => [segment.label, segment.value]))}
      title={title}
      viewBox={`0 0 ${size} ${size}`}
    >
      {segments.map((segment, index) => {
        const [start, end] = angles[index];
        if (end - start <= 0) {
          return null;
        }
        const tone = segment.tone ?? RISK_RAMP_TONES[index % RISK_RAMP_TONES.length];
        return <path d={arcPath(cx, cy, rInner, rOuter, start, end)} fill={toneVar(tone)} key={segment.label} />;
      })}
      {centerLabel ? (
        <text className="chart-center-label" textAnchor="middle" x={cx} y={cy + 6}>
          {centerLabel}
        </text>
      ) : null}
    </ChartFigure>
  );
}

/** Distribution histogram. */
export function Histogram({
  bins,
  title,
  description,
  caption,
  tone = "brand",
  height = 180,
  width = 420,
}: {
  bins: Array<{ label: string; count: number }>;
  title: string;
  description: string;
  caption?: ReactNode;
  tone?: ChartTone;
  height?: number;
  width?: number;
}) {
  const padding = 26;
  const domain = niceExtent(bins.map((bin) => bin.count), true);
  const y = scale(domain, [height - padding, padding]);
  const baseline = y(0);
  const slot = (width - padding * 2) / Math.max(1, bins.length);

  return (
    <ChartFigure
      caption={caption}
      description={description}
      table={dataTable(["Bin", "Count"], bins.map((bin) => [bin.label, bin.count]))}
      title={title}
      viewBox={`0 0 ${width} ${height}`}
    >
      <line stroke="var(--color-border-strong)" strokeWidth="1" x1={padding} x2={width - padding} y1={baseline} y2={baseline} />
      {bins.map((bin, index) => {
        const top = y(bin.count);
        const x = padding + index * slot + slot * 0.1;
        return (
          <g key={bin.label}>
            <rect fill={toneVar(tone)} height={Math.abs(baseline - top)} width={slot * 0.8} x={x} y={Math.min(baseline, top)} />
            <text className="chart-axis-label" textAnchor="middle" x={x + slot * 0.4} y={height - 8}>
              {bin.label}
            </text>
          </g>
        );
      })}
    </ChartFigure>
  );
}
