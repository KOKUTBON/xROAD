"use client";

import { type ReactNode } from "react";

import { DeltaBar, Sparkline, type ChartTone } from "@/components/charts";
import { ArrowDownIcon, ArrowRightIcon, ArrowUpIcon, MinusIcon } from "@/components/icons";

/**
 * Analytical composites (#181) built on the chart kit + tokens: KPI cards that
 * show value + trend + change, a before/after CompareView, and a lifecycle
 * Timeline. These replace static numbers and string-table before/after across
 * the executive board, scenario planner, and operations queues.
 */

export type Confidence = "high" | "medium" | "low";

const CONFIDENCE_FILLED: Record<Confidence, number> = { high: 3, medium: 2, low: 1 };

function ConfidencePips({ level }: { level: Confidence }) {
  const filled = CONFIDENCE_FILLED[level];
  return (
    <span className="kpi-confidence" role="img" aria-label={`Data confidence: ${level}`}>
      {[0, 1, 2].map((index) => (
        <span className={`kpi-pip${index < filled ? " is-filled" : ""}`} key={index} aria-hidden="true" />
      ))}
    </span>
  );
}

export interface KpiDelta {
  value: number;
  /** Which direction counts as improvement. Default "up". */
  goodDirection?: "up" | "down";
  label?: string;
}

/** KPI card: value + optional sparkline, period delta, target marker, confidence, freshness. */
export function KpiCard({
  label,
  value,
  unit = "",
  series,
  seriesTone = "brand",
  delta,
  target,
  confidence,
  freshness,
}: {
  label: string;
  value: string | number;
  unit?: string;
  series?: number[];
  seriesTone?: ChartTone;
  delta?: KpiDelta;
  target?: string;
  confidence?: Confidence;
  freshness?: string;
}) {
  let deltaTone: "positive" | "danger" | "neutral" = "neutral";
  if (delta && delta.value !== 0) {
    const improved = (delta.goodDirection ?? "up") === "up" ? delta.value > 0 : delta.value < 0;
    deltaTone = improved ? "positive" : "danger";
  }
  const DeltaArrow = delta
    ? delta.value > 0
      ? ArrowUpIcon
      : delta.value < 0
        ? ArrowDownIcon
        : MinusIcon
    : null;

  return (
    <article className="kpi-card">
      <div className="kpi-card-top">
        <span className="kpi-card-label">{label}</span>
        {confidence ? <ConfidencePips level={confidence} /> : null}
      </div>
      <div className="kpi-card-figure">
        <strong className="kpi-card-value">
          {value}
          {unit ? <span className="kpi-card-unit">{unit}</span> : null}
        </strong>
        {series && series.length > 1 ? (
          <div className="kpi-card-spark">
            <Sparkline title={`${label} trend`} tone={seriesTone} values={series} />
          </div>
        ) : null}
      </div>
      <div className="kpi-card-foot">
        {delta ? (
          <span className={`kpi-delta kpi-delta-${deltaTone}`}>
            {DeltaArrow ? <DeltaArrow size={14} /> : null}
            {Math.abs(delta.value)}
            {unit}
            {delta.label ? ` ${delta.label}` : ""}
          </span>
        ) : null}
        {target ? <span className="kpi-target">Target {target}</span> : null}
      </div>
      {freshness ? <small className="kpi-freshness">{freshness}</small> : null}
    </article>
  );
}

/** Before/after comparison: paired delta bars + per-item percent-change chips. */
export function CompareView({
  title,
  items,
  unit = "",
  goodDirection = "down",
  description,
}: {
  title: string;
  items: Array<{ label: string; before: number; after: number }>;
  unit?: string;
  goodDirection?: "down" | "up";
  description?: string;
}) {
  return (
    <div className="compare-view">
      <DeltaBar
        description={description ?? `Before/after change for ${items.length} items.`}
        goodDirection={goodDirection}
        items={items}
        title={title}
        unit={unit}
      />
      <ul className="compare-summary">
        {items.map((item) => {
          const delta = item.after - item.before;
          const pct = item.before !== 0 ? Math.round((delta / item.before) * 100) : 0;
          const improved = goodDirection === "down" ? delta < 0 : delta > 0;
          const tone = delta === 0 ? "neutral" : improved ? "positive" : "danger";
          return (
            <li className="compare-row" key={item.label}>
              <span className="compare-row-label">{item.label}</span>
              <span className="compare-row-values">
                {item.before}
                {unit}
                <ArrowRightIcon size={14} />
                {item.after}
                {unit}
              </span>
              <span className={`compare-chip compare-chip-${tone}`}>
                {pct > 0 ? "+" : ""}
                {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export type TimelineState = "done" | "current" | "pending" | "blocked";

const TIMELINE_STATE_LABEL: Record<TimelineState, string> = {
  done: "complete",
  current: "in progress",
  pending: "pending",
  blocked: "blocked",
};

/** Lifecycle / audit rail bound to status tokens (draft → validated → published → delivered). */
export function Timeline({
  steps,
  caption,
}: {
  steps: Array<{ label: string; state: TimelineState; detail?: string }>;
  caption?: ReactNode;
}) {
  return (
    <div className="timeline">
      <ol className="timeline-track">
        {steps.map((step) => (
          <li className={`timeline-step timeline-${step.state}`} key={step.label}>
            <span className="timeline-dot" aria-hidden="true" />
            <span className="timeline-label">{step.label}</span>
            <span className="timeline-state">{TIMELINE_STATE_LABEL[step.state]}</span>
            {step.detail ? <span className="timeline-detail">{step.detail}</span> : null}
          </li>
        ))}
      </ol>
      {caption ? <p className="timeline-caption">{caption}</p> : null}
    </div>
  );
}
