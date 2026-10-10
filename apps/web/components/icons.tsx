import type { ReactNode, SVGProps } from "react";

/**
 * xROAD Signal icon set.
 *
 * Drawn for road-safety work: every glyph is built from the things the product
 * reasons about — carriageways, lane markings, junctions, signal heads,
 * vehicles, hotspots — on a 24px grid with a 1.75 stroke, round caps, and
 * `currentColor`. Most glyphs carry one tonal plate (`.icon-tone`, a 16%
 * current-color fill) the way a road sign carries its plate, so icons read at a
 * glance in dense navigation and still inherit the label's color and theme.
 *
 * Icons are decorative (`aria-hidden`, `focusable=false`); the surrounding
 * control owns the accessible label. Add new glyphs here rather than inlining a
 * one-off SVG, so the chrome stays one consistent set.
 */
function Icon({
  children,
  size = 18,
  className,
  ...props
}: SVGProps<SVGSVGElement> & { children: ReactNode; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      className={className ? `xr-icon ${className}` : "xr-icon"}
      fill="none"
      focusable="false"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.75}
      viewBox="0 0 24 24"
      width={size}
      {...props}
    >
      {children}
    </svg>
  );
}

type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & { size?: number };

/** Tonal plate: a soft current-color fill behind the line work. */
function Tone(props: SVGProps<SVGPathElement>) {
  return <path className="icon-tone" fill="currentColor" fillOpacity={0.16} stroke="none" {...props} />;
}

/* ---------------------------------------------------------------- chrome */

export function MenuIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 12h10M4 17h16" />
    </Icon>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Icon>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M14.5 6 8.5 12l6 6" />
    </Icon>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9.5 6l6 6-6 6" />
    </Icon>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

export function MinusIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 12h14" />
    </Icon>
  );
}

export function ArrowUpIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" />
    </Icon>
  );
}

export function ArrowDownIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 5v14M6.5 13.5 12 19l5.5-5.5" />
    </Icon>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 12h14M13.5 6.5 19 12l-5.5 5.5" />
    </Icon>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="m15 15 5 5" />
    </Icon>
  );
}

export function InboxIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M4 13h5l1.5 2.5h3L15 13h5v5.5H4Z" />
      <path d="M4 13l2.5-7h11L20 13M4 13v5.5h16V13M4 13h5l1.5 2.5h3L15 13h5" />
    </Icon>
  );
}

/** Warning-sign triangle, the universal "danger ahead" plate. */
export function AlertTriangleIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M12 4 21 19.5H3Z" />
      <path d="M10.3 5a2 2 0 0 1 3.4 0l7.4 12.6a2 2 0 0 1-1.7 3H4.6a2 2 0 0 1-1.7-3Z" />
      <path d="M12 10v4" />
      <path d="M12 17.2v.01" />
    </Icon>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M19.5 12a7.5 7.5 0 0 1-13.2 4.9M4.5 12a7.5 7.5 0 0 1 13.2-4.9" />
      <path d="M18 3.5v3.8h-3.8M6 20.5v-3.8h3.8" />
    </Icon>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z" />
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
    </Icon>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z" />
      <path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z" />
      <path d="M17 3.5v3M15.5 5h3" />
    </Icon>
  );
}

export function ContrastIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function GlobeIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.4 2.4 3.5 5.2 3.5 8.5s-1.1 6.1-3.5 8.5c-2.4-2.4-3.5-5.2-3.5-8.5s1.1-6.1 3.5-8.5Z" />
    </Icon>
  );
}

export function SignInIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M14 4h4.5a1.5 1.5 0 0 1 1.5 1.5v13a1.5 1.5 0 0 1-1.5 1.5H14" />
      <path d="M4 12h11M11 8l4 4-4 4" />
    </Icon>
  );
}

export function SignOutIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M10 4H5.5A1.5 1.5 0 0 0 4 5.5v13A1.5 1.5 0 0 0 5.5 20H10" />
      <path d="M9 12h11M16 8l4 4-4 4" />
    </Icon>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Icon>
  );
}

/** Carriageway in perspective with a dashed centre line — "the road". */
export function RoadIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M4 20.5 10 3.5h4l6 17Z" />
      <path d="M4 20.5 10 3.5M20 20.5 14 3.5" />
      <path d="M12 19.5v-2.5M12 14v-2M12 9V7.5" />
    </Icon>
  );
}

/** Live pulse: a monitored signal on the network. */
export function PulseIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M2.5 12H7l2.5-6 5 12 2.5-6h4.5" />
    </Icon>
  );
}

export function LayersIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M12 3.5 20.5 8 12 12.5 3.5 8Z" />
      <path d="M12 3.5 20.5 8 12 12.5 3.5 8Z" />
      <path d="m3.5 12 8.5 4.5 8.5-4.5M3.5 16l8.5 4.5 8.5-4.5" />
    </Icon>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <Tone d="M12 3 19 5.8v5.4c0 4.6-3 8-7 9.8-4-1.8-7-5.2-7-9.8V5.8Z" />
      <path d="M12 3 19 5.8v5.4c0 4.6-3 8-7 9.8-4-1.8-7-5.2-7-9.8V5.8Z" />
      <path d="m8.8 12 2.3 2.3 4.2-4.6" />
    </Icon>
  );
}

/* ------------------------------------------------------------- workspaces */

/**
 * One glyph per destination, each carrying that workflow's meaning:
 * a folded map with a hotspot, a speed gauge for the control room, a traffic
 * cone for proposed works, a signal head for signal operations, and so on.
 */
const workspaceGlyphs: Record<string, ReactNode> = {
  // Public map — folded map sheet with a risk hotspot.
  map: (
    <>
      <path d="M3.5 6.2 9 4l6 2.2L20.5 4v13.8L15 20l-6-2.2-5.5 2.2Z" />
      <path d="M9 4v13.8M15 6.2V20" />
      <Tone d="M12 8a3.2 3.2 0 1 1 0 6.4A3.2 3.2 0 0 1 12 8Z" />
      <circle cx="12" cy="11.2" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  // Operations overview — the control-room gauge.
  workspace: (
    <>
      <Tone d="M4 16a8 8 0 0 1 16 0Z" />
      <path d="M4 16a8 8 0 0 1 16 0" />
      <path d="M12 8v1.3M6.4 10.4l.9.9M17.6 10.4l-.9.9" />
      <path d="m12 16 3.6-4.2" />
      <circle cx="12" cy="16" r="1.4" fill="currentColor" stroke="none" />
      <path d="M3.5 19.5h17" />
    </>
  ),
  // Executive board — KPI bars climbing toward a target.
  executive: (
    <>
      <Tone d="M4.5 20v-4.5h3V20ZM10.5 20v-7.5h3V20ZM16.5 20v-10h3V20Z" />
      <path d="M4.5 20v-4.5h3V20M10.5 20v-7.5h3V20M16.5 20v-10h3V20" />
      <path d="M4 10 9 6.5l3.5 2.5L18 4" />
      <path d="M14.8 4H18v3.2" />
    </>
  ),
  // Reports — a published sheet with its trend line.
  reports: (
    <>
      <Tone d="M6 3.5h8.5l4 4v13H6Z" />
      <path d="M6 3.5h8.5l4 4v13H6Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M8.5 11h4M8.5 17l2.5-2.5 2 1.5 3-3.5" />
    </>
  ),
  // Analyst desk — a lens over a road segment's hotspot.
  analyst: (
    <>
      <Tone d="M10.5 4.5a6 6 0 1 1 0 12 6 6 0 0 1 0-12Z" />
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="m15 15 5 5" />
      <path d="M6.6 13c1.7-.4 2.3-3.9 4.9-4.3.9-.1 1.7.1 2.3.5" />
      <circle cx="10.4" cy="10" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  // Scenario planner — the road forks into alternative interventions.
  scenarios: (
    <>
      <path d="M12 21v-7.5M12 13.5 6.5 6.2M12 13.5l5.5-7.3" />
      <Tone d="M17.5 2.8a2 2 0 1 1 0 4 2 2 0 0 1 0-4Z" />
      <circle cx="6.5" cy="4.8" r="2" />
      <circle cx="17.5" cy="4.8" r="2" />
      <path d="M10 21h4" />
    </>
  ),
  // Proposed changes — the traffic cone of planned road works.
  "proposed-changes": (
    <>
      <Tone d="M10.2 3.5h3.6L18 18.5H6Z" />
      <path d="M10.2 3.5h3.6L18 18.5H6Z" />
      <path d="M8.6 9.5h6.8M7.3 14h9.4M4 20.5h16" />
    </>
  ),
  // Siting advisor — a placement pin with its target ring.
  "siting-advisor": (
    <>
      <Tone d="M12 21s6.5-6.1 6.5-11.2a6.5 6.5 0 1 0-13 0C5.5 14.9 12 21 12 21Z" />
      <path d="M12 21s6.5-6.1 6.5-11.2a6.5 6.5 0 1 0-13 0C5.5 14.9 12 21 12 21Z" />
      <circle cx="12" cy="9.8" r="2.4" />
      <path d="M12 5.2v1.2M12 13.2v1.2M7.4 9.8h1.2M15.4 9.8h1.2" />
    </>
  ),
  // Climate resilience — storm cloud and rain over the network.
  climate: (
    <>
      <Tone d="M7 15.5h10a3.5 3.5 0 0 0 .4-7A5.5 5.5 0 0 0 6.9 8 3.8 3.8 0 0 0 7 15.5Z" />
      <path d="M7 15.5h10a3.5 3.5 0 0 0 .4-7A5.5 5.5 0 0 0 6.9 8 3.8 3.8 0 0 0 7 15.5Z" />
      <path d="m8.5 18.5-.9 2M12.5 18.5l-.9 2M16.5 18.5l-.9 2" />
    </>
  ),
  // Research & benchmarks — the experiment flask.
  research: (
    <>
      <Tone d="M7.3 14h9.4l2.4 4.2a1.6 1.6 0 0 1-1.4 2.3H6.3a1.6 1.6 0 0 1-1.4-2.3Z" />
      <path d="M9.5 3.5h5M10.5 3.5v5.2L4.9 18.2a1.6 1.6 0 0 0 1.4 2.3h11.4a1.6 1.6 0 0 0 1.4-2.3L13.5 8.7V3.5" />
      <circle cx="10.5" cy="17.2" r=".9" fill="currentColor" stroke="none" />
      <circle cx="14" cy="16" r=".7" fill="currentColor" stroke="none" />
    </>
  ),
  // Digital twin — a mirrored road tile over simulation layers.
  "digital-twin": (
    <>
      <Tone d="M12 3.5 20 8l-8 4.5L4 8Z" />
      <path d="M12 3.5 20 8l-8 4.5L4 8Z" />
      <path d="M8 10.2 16 5.8" strokeDasharray="1.6 1.6" />
      <path d="m4 12.2 8 4.5 8-4.5M4 16.2l8 4.5 8-4.5" />
    </>
  ),
  // Forensic reconstruction — two trajectories meeting at the impact point.
  forensics: (
    <>
      <path d="M3.5 20.5 9 15M20.5 20.5 15 15" strokeDasharray="2 2.2" />
      <Tone d="m12 4 1.3 2.8 3-.9-.9 3 2.6 1.6-2.9.9.3 3L12 12.6l-2.4 1.8.3-3-2.9-.9 2.6-1.6-.9-3 3 .9Z" />
      <path d="m12 4 1.3 2.8 3-.9-.9 3 2.6 1.6-2.9.9.3 3L12 12.6l-2.4 1.8.3-3-2.9-.9 2.6-1.6-.9-3 3 .9Z" />
    </>
  ),
  // TMC playbooks — an open playbook with a run control.
  "tmc-playbooks": (
    <>
      <path d="M3.5 5.5c3-.9 5.8-.6 8.5 1.2 2.7-1.8 5.5-2.1 8.5-1.2v13c-3-.9-5.8-.6-8.5 1.2-2.7-1.8-5.5-2.1-8.5-1.2Z" />
      <path d="M12 6.7v13.2M6 10h3.5M6 13h3.5" />
      <Tone d="M14.5 9.8v5.4l4.2-2.7Z" />
      <path d="M14.5 9.8v5.4l4.2-2.7Z" />
    </>
  ),
  // Connected fleets & C-V2X — a vehicle broadcasting to the network.
  "connected-fleets": (
    <>
      <Tone d="M3 16.5V10h10.5l3.8 3.2H21v3.3Z" />
      <path d="M4.9 16.5H3V10h10.5l3.8 3.2H21v3.3h-1.4M9.1 16.5h6.3" />
      <circle cx="7" cy="16.8" r="2" />
      <circle cx="17.5" cy="16.8" r="2" />
      <path d="M16.2 6.6a3.4 3.4 0 0 1 4 0M14.6 4.3a6.6 6.6 0 0 1 7.2 0" />
    </>
  ),
  // Multi-incident coordination — the emergency beacon.
  "incident-coordination": (
    <>
      <Tone d="M7 17v-5a5 5 0 0 1 10 0v5Z" />
      <path d="M7 17v-5a5 5 0 0 1 10 0v5M5 17h14v3.5H5Z" />
      <path d="M12 11v3M12 2.5v2M4.6 5.6 6 7M19.4 5.6 18 7M2.5 12h2M19.5 12h2" />
    </>
  ),
  // Traffic engineering — the signal head.
  operations: (
    <>
      <path d="M9 2.5h6a1.5 1.5 0 0 1 1.5 1.5v13a1.5 1.5 0 0 1-1.5 1.5H9A1.5 1.5 0 0 1 7.5 17V4A1.5 1.5 0 0 1 9 2.5Z" />
      <Tone d="M12 4.7a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Z" />
      <circle cx="12" cy="6.5" r="1.8" />
      <circle cx="12" cy="10.5" r="1.8" />
      <circle cx="12" cy="14.5" r="1.8" fill="currentColor" />
      <path d="M12 18.5v3" />
    </>
  ),
  // Admin control — the protected account.
  admin: (
    <>
      <Tone d="M12 3 19 5.8v5.4c0 4.6-3 8-7 9.8-4-1.8-7-5.2-7-9.8V5.8Z" />
      <path d="M12 3 19 5.8v5.4c0 4.6-3 8-7 9.8-4-1.8-7-5.2-7-9.8V5.8Z" />
      <circle cx="12" cy="10" r="2.2" />
      <path d="M8.4 16.2a4.1 4.1 0 0 1 7.2 0" />
    </>
  ),
  // Upload center — records flowing into the evidence store.
  uploads: (
    <>
      <Tone d="M4.5 6c0-1.4 3.4-2.5 7.5-2.5s7.5 1.1 7.5 2.5-3.4 2.5-7.5 2.5S4.5 7.4 4.5 6Z" />
      <path d="M4.5 6c0-1.4 3.4-2.5 7.5-2.5s7.5 1.1 7.5 2.5-3.4 2.5-7.5 2.5S4.5 7.4 4.5 6Z" />
      <path d="M4.5 6v12c0 1.4 3.4 2.5 7.5 2.5M19.5 6v5M4.5 12c0 1.4 3.4 2.5 7.5 2.5" />
      <path d="M17.5 21v-6.5M14.8 17.2l2.7-2.7 2.7 2.7" />
    </>
  ),
  // Automation — a scheduled cycle.
  automation: (
    <>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path d="M19.8 3.6v3.6h-3.6" />
      <Tone d="M12 7.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z" />
      <path d="M12 8.5V12l2.5 1.6" />
    </>
  ),
  // System health — the monitored heartbeat.
  "system-health": (
    <>
      <Tone d="M3.5 5.5a1 1 0 0 1 1-1h15a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1Z" />
      <path d="M3.5 5.5a1 1 0 0 1 1-1h15a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1Z" />
      <path d="M9 20.5h6M12 16.5v4" />
      <path d="M6 10.5h2.5l1.5-3 2.5 6 1.5-3H18" />
    </>
  ),
};

export function WorkspaceIcon({ name, ...props }: IconProps & { name: string }) {
  return <Icon {...props}>{workspaceGlyphs[name] ?? workspaceGlyphs.map}</Icon>;
}

/** Names with a dedicated workspace glyph (used by the design gallery). */
export const WORKSPACE_ICON_NAMES = Object.keys(workspaceGlyphs);
