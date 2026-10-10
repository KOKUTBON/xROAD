/**
 * Pure geometry helpers for the SVG chart kit (#179).
 *
 * Kept free of React/DOM so the math is unit-tested in isolation. All sizing is
 * in viewBox user units; components scale responsively via `preserveAspectRatio`.
 */

export interface Point {
  x: number;
  y: number;
}

/** Min/max of a value list. Returns [0, 0] for an empty list. */
export function extent(values: number[]): [number, number] {
  if (values.length === 0) {
    return [0, 0];
  }
  let min = values[0];
  let max = values[0];
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return [min, max];
}

/**
 * A padded, optionally zero-anchored domain. Guarantees min < max (pads a flat
 * series by ±1) so scales never divide by zero.
 */
export function niceExtent(values: number[], includeZero = false): [number, number] {
  let [min, max] = extent(values);
  if (includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  if (min === max) {
    return [min - 1, max + 1];
  }
  return [min, max];
}

/** Linear scale from a domain to a range as a plain function. */
export function scale(domain: [number, number], range: [number, number]): (value: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (value: number) => r0 + ((value - d0) / span) * (r1 - r0);
}

/**
 * Map a value series to evenly-spaced points inside a padded box. Y is inverted
 * (SVG y grows downward) so larger values sit higher.
 */
export function seriesPoints(
  values: number[],
  width: number,
  height: number,
  padding: number,
  domain: [number, number],
): Point[] {
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const y = scale(domain, [height - padding, padding]);
  const step = values.length > 1 ? innerWidth / (values.length - 1) : 0;
  return values.map((value, index) => ({
    x: padding + (values.length > 1 ? index * step : innerWidth / 2),
    y: y(value),
  }));
}

/** An SVG polyline path (`M … L …`) through the given points. */
export function linePath(points: Point[]): string {
  if (points.length === 0) {
    return "";
  }
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${round(point.x)} ${round(point.y)}`)
    .join(" ");
}

/** A closed area path under a line, down to `baselineY`. */
export function areaPath(points: Point[], baselineY: number): string {
  if (points.length === 0) {
    return "";
  }
  const first = points[0];
  const last = points[points.length - 1];
  return `${linePath(points)} L${round(last.x)} ${round(baselineY)} L${round(first.x)} ${round(baselineY)} Z`;
}

/** Up to ~`count` rounded tick values spanning the domain. */
export function ticks(min: number, max: number, count: number): number[] {
  if (min === max) {
    return [min];
  }
  const step = (max - min) / Math.max(1, count - 1);
  return Array.from({ length: count }, (_, index) => round(min + step * index));
}

function polar(cx: number, cy: number, radius: number, angleDeg: number): Point {
  const angle = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
}

/**
 * An annular (donut) segment path between two angles (degrees, clockwise from
 * 12 o'clock), from inner radius to outer radius.
 */
export function arcPath(
  cx: number,
  cy: number,
  rInner: number,
  rOuter: number,
  startAngle: number,
  endAngle: number,
): string {
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  const o0 = polar(cx, cy, rOuter, startAngle);
  const o1 = polar(cx, cy, rOuter, endAngle);
  const i1 = polar(cx, cy, rInner, endAngle);
  const i0 = polar(cx, cy, rInner, startAngle);
  return [
    `M${round(o0.x)} ${round(o0.y)}`,
    `A${rOuter} ${rOuter} 0 ${largeArc} 1 ${round(o1.x)} ${round(o1.y)}`,
    `L${round(i1.x)} ${round(i1.y)}`,
    `A${rInner} ${rInner} 0 ${largeArc} 0 ${round(i0.x)} ${round(i0.y)}`,
    "Z",
  ].join(" ");
}

/** Cumulative angle offsets (degrees) for a set of values summing to 360°. */
export function segmentAngles(values: number[]): Array<[number, number]> {
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0);
  if (total <= 0) {
    return values.map(() => [0, 0]);
  }
  let cursor = 0;
  return values.map((value) => {
    const start = cursor;
    const sweep = (Math.max(0, value) / total) * 360;
    cursor += sweep;
    return [start, cursor];
  });
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
