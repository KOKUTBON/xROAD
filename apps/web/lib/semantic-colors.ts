import type { ScoreBand } from "./risk-map";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";
export type PublicationTier = "public" | "internal" | "restricted";
export type ConfidenceLevel = "high" | "medium" | "low";

export interface SemanticColor {
  label: string;
  fill: string;
  ink: string;
}

export const riskBandColors: Record<ScoreBand | "minimal", SemanticColor> = {
  minimal: { label: "Minimal", fill: "#00204C", ink: "#00204C" },
  low: { label: "Low", fill: "#414D6B", ink: "#414D6B" },
  moderate: { label: "Moderate", fill: "#7C7B78", ink: "#52524E" },
  high: { label: "High", fill: "#BCAF6F", ink: "#634D33" },
  very_high: { label: "Very high", fill: "#FFEA46", ink: "#403120" },
};

export const statusColors: Record<StatusTone, SemanticColor> = {
  neutral: { label: "Neutral", fill: "#52524E", ink: "#52524E" },
  info: { label: "Info", fill: "#005A75", ink: "#005A75" },
  success: { label: "Success", fill: "#166534", ink: "#166534" },
  warning: { label: "Warning", fill: "#854D0E", ink: "#854D0E" },
  danger: { label: "Danger", fill: "#B42318", ink: "#B42318" },
};

export const governanceTierColors: Record<PublicationTier, SemanticColor> = {
  public: { label: "Public", fill: "#F5F1FA", ink: "#4B2A8C" },
  internal: { label: "Internal", fill: "#393936", ink: "#393936" },
  restricted: { label: "Restricted", fill: "#FFF8E8", ink: "#643A08" },
};

export const confidenceColors: Record<ConfidenceLevel, SemanticColor> = {
  high: { label: "High confidence", fill: "#4B2A8C", ink: "#4B2A8C" },
  medium: { label: "Medium confidence", fill: "#854D0E", ink: "#854D0E" },
  low: { label: "Low confidence", fill: "#52524E", ink: "#52524E" },
};

export const positiveChangeColor = "#166534";
export const mapLayerColors = {
  junctions: "#4B2A8C",
  crossings: "#91580D",
  selectedInk: "#0B0B0B",
  selectedFill: "#EAE2F4",
  basemap: "#FDFBF7",
  featureStroke: "#FFFFFF",
} as const;

export function riskBandColor(band: ScoreBand | null | undefined): string {
  return riskBandColors[band ?? "minimal"].fill;
}

export function mapFallbackColor(tone: "tiles" | "segments" | "junctions" | "crossings"): string {
  if (tone === "junctions") {
    return mapLayerColors.junctions;
  }
  if (tone === "crossings") {
    return mapLayerColors.crossings;
  }
  return riskBandColors.minimal.fill;
}

export function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
    throw new Error(`Invalid hex color: ${hex}`);
  }
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

export function rgbaFromHex(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgb(${r} ${g} ${b} / ${alpha})`;
}

function linearChannel(value: number): number {
  const normalized = value / 255;
  return normalized <= 0.03928
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(linearChannel);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(leftHex: string, rightHex: string): number {
  const left = relativeLuminance(leftHex);
  const right = relativeLuminance(rightHex);
  const lighter = Math.max(left, right);
  const darker = Math.min(left, right);
  return (lighter + 0.05) / (darker + 0.05);
}

export function simulatedColorblindHex(
  hex: string,
  mode: "deuteranopia" | "protanopia",
): string {
  const matrices = {
    deuteranopia: [
      [0.367, 0.861, -0.228],
      [0.28, 0.673, 0.047],
      [-0.012, 0.043, 0.969],
    ],
    protanopia: [
      [0.152, 1.053, -0.205],
      [0.115, 0.786, 0.099],
      [-0.004, -0.048, 1.052],
    ],
  } as const;
  const [r, g, b] = hexToRgb(hex);
  const matrix = matrices[mode];
  const transformed = matrix.map((row) =>
    Math.max(0, Math.min(255, Math.round(row[0] * r + row[1] * g + row[2] * b))),
  );
  return `#${transformed.map((value) => value.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}
