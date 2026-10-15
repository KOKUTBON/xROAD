/**
 * Per-route motion identity (UX 3.0).
 *
 * Every screen in the product gets one signature animation whose *meaning*
 * matches what the page is for — a heartbeat for system health, a radar sweep
 * for the siting advisor, a rain wash for climate resilience, and so on. The
 * motif is pure data so it can be unit-tested and reused by the page header,
 * the route stage, and the command palette without duplicating route strings.
 *
 * Motion is decoration only: nothing here gates content, and every motif is
 * collapsed to a static frame under `prefers-reduced-motion: reduce`.
 */

export const MOTIF_IDS = [
  "road",
  "control-room",
  "board",
  "report",
  "scatter",
  "branch",
  "diff",
  "radar",
  "rain",
  "signal",
  "shield",
  "upload",
  "cycle",
  "pulse",
  "key",
] as const;

export type MotifId = (typeof MOTIF_IDS)[number];

export interface PageMotif {
  /** Which signature animation to draw. */
  id: MotifId;
  /** Short human label for the motif (used as the graphic's accessible title). */
  title: string;
  /** Why this motion belongs to this page — the "idea" it expresses. */
  meaning: string;
}

const MOTIFS: Record<MotifId, PageMotif> = {
  road: {
    id: "road",
    title: "Road risk",
    meaning: "A road draws itself and risk points surface along it.",
  },
  "control-room": {
    id: "control-room",
    title: "Control room",
    meaning: "Operational tiles come online one after another.",
  },
  board: {
    id: "board",
    title: "Decision board",
    meaning: "Bars grow to a decision-ready posture.",
  },
  report: {
    id: "report",
    title: "Reporting",
    meaning: "Pages stack and fill as a report is composed.",
  },
  scatter: {
    id: "scatter",
    title: "Analysis",
    meaning: "Observations settle into a pattern a trend line explains.",
  },
  branch: {
    id: "branch",
    title: "Scenarios",
    meaning: "One present branches into alternative futures.",
  },
  diff: {
    id: "diff",
    title: "Proposed changes",
    meaning: "A current state is compared against a proposed one.",
  },
  radar: {
    id: "radar",
    title: "Siting advisor",
    meaning: "A sweep searches the area and locks onto candidate sites.",
  },
  rain: {
    id: "rain",
    title: "Climate resilience",
    meaning: "Weather washes across the network and exposure lights up.",
  },
  signal: {
    id: "signal",
    title: "Traffic operations",
    meaning: "Signal phases cycle as traffic is actively managed.",
  },
  shield: {
    id: "shield",
    title: "Governance",
    meaning: "A shield is drawn closed around the platform.",
  },
  upload: {
    id: "upload",
    title: "Ingestion",
    meaning: "Files rise into the platform and are validated.",
  },
  cycle: {
    id: "cycle",
    title: "Automation",
    meaning: "A scheduled loop turns on its own.",
  },
  pulse: {
    id: "pulse",
    title: "System health",
    meaning: "A steady heartbeat traces the platform's vital signs.",
  },
  key: {
    id: "key",
    title: "Secure entry",
    meaning: "Access resolves into focus as the session opens.",
  },
};

/**
 * Route prefix -> motif. Ordered longest-prefix-first so `/workspace/analyst`
 * never falls through to `/workspace`.
 */
const ROUTE_MOTIFS: ReadonlyArray<readonly [string, MotifId]> = [
  ["/workspace/proposed-changes", "diff"],
  ["/workspace/siting-advisor", "radar"],
  ["/workspace/system-health", "pulse"],
  ["/workspace/executive", "board"],
  ["/workspace/automation", "cycle"],
  ["/workspace/operations", "signal"],
  ["/workspace/scenarios", "branch"],
  ["/workspace/analyst", "scatter"],
  ["/workspace/climate", "rain"],
  ["/workspace/reports", "report"],
  ["/workspace/uploads", "upload"],
  ["/workspace/admin", "shield"],
  ["/workspace", "control-room"],
  ["/login", "key"],
  ["/", "road"],
];

/** Resolve the signature motif for a pathname. Always returns a motif. */
export function motifForPath(pathname: string | null | undefined): PageMotif {
  const path = typeof pathname === "string" && pathname.length > 0 ? pathname : "/";
  const match = ROUTE_MOTIFS.find(([prefix]) =>
    prefix === "/" ? path === "/" : path === prefix || path.startsWith(`${prefix}/`),
  );
  return MOTIFS[match ? match[1] : "control-room"];
}

export function motif(id: MotifId): PageMotif {
  return MOTIFS[id];
}
