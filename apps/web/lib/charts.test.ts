import { describe, expect, it } from "vitest";

import {
  areaPath,
  extent,
  linePath,
  niceExtent,
  scale,
  segmentAngles,
  seriesPoints,
  ticks,
} from "./charts";

describe("chart geometry helpers", () => {
  it("extent finds min/max and handles empty", () => {
    expect(extent([3, 1, 8, 4])).toEqual([1, 8]);
    expect(extent([])).toEqual([0, 0]);
  });

  it("niceExtent zero-anchors and pads flat series", () => {
    expect(niceExtent([4, 9, 6], true)).toEqual([0, 9]);
    expect(niceExtent([5, 5])).toEqual([4, 6]);
  });

  it("scale maps domain to range and is clamp-free", () => {
    const s = scale([0, 10], [0, 100]);
    expect(s(0)).toBe(0);
    expect(s(5)).toBe(50);
    expect(s(10)).toBe(100);
  });

  it("scale never divides by zero on a flat domain", () => {
    const s = scale([5, 5], [0, 100]);
    expect(Number.isFinite(s(5))).toBe(true);
  });

  it("seriesPoints spans the padded width and inverts y", () => {
    const points = seriesPoints([0, 10], 100, 100, 10, [0, 10]);
    expect(points[0].x).toBe(10);
    expect(points[1].x).toBe(90);
    // value 0 sits at the bottom, value 10 at the top (smaller y)
    expect(points[0].y).toBeGreaterThan(points[1].y);
  });

  it("seriesPoints centers a single point", () => {
    const [point] = seriesPoints([7], 100, 100, 10, [0, 10]);
    expect(point.x).toBe(50);
  });

  it("linePath emits a move then lines", () => {
    expect(linePath([{ x: 0, y: 0 }, { x: 10, y: 5 }])).toBe("M0 0 L10 5");
    expect(linePath([])).toBe("");
  });

  it("areaPath closes the shape to the baseline", () => {
    const path = areaPath([{ x: 0, y: 0 }, { x: 10, y: 5 }], 100);
    expect(path.startsWith("M0 0 L10 5")).toBe(true);
    expect(path.endsWith("Z")).toBe(true);
    expect(path).toContain("L10 100");
  });

  it("ticks returns count values spanning the domain", () => {
    expect(ticks(0, 100, 5)).toEqual([0, 25, 50, 75, 100]);
    expect(ticks(5, 5, 4)).toEqual([5]);
  });

  it("segmentAngles partitions 360 degrees proportionally", () => {
    const angles = segmentAngles([1, 1, 2]);
    expect(angles[0]).toEqual([0, 90]);
    expect(angles[1]).toEqual([90, 180]);
    expect(angles[2]).toEqual([180, 360]);
  });

  it("segmentAngles collapses to zero on a non-positive total", () => {
    expect(segmentAngles([0, 0])).toEqual([[0, 0], [0, 0]]);
  });
});
