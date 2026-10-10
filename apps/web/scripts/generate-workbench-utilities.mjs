#!/usr/bin/env node
/**
 * Generates `app/workbench-utilities.css`.
 *
 * A handful of workbenches (forensics, incident coordination, connected
 * fleets, TMC playbooks) are authored with Tailwind-style utility classes, but
 * the app ships plain CSS. This script scans those components for the exact
 * utilities they use and emits them, remapped onto the xROAD Signal palette:
 * slate → asphalt graphite, amber → signal amber, emerald → go green,
 * rose/red → hazard red, blue → guide-sign blue. `dark:` variants follow the
 * app's `data-theme="dark"` attribute rather than the OS preference.
 *
 * Run after editing any of the listed components:
 *   node scripts/generate-workbench-utilities.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, "..");
const SOURCES = [
  "components/forensic-reconstruction-workbench.tsx",
  "components/incident-coordination-workbench.tsx",
  "components/connected-fleets-workbench.tsx",
  "components/tmc-playbook-workbench.tsx",
];
const OUTPUT = path.join(WEB, "app", "workbench-utilities.css");

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const ramp = (hexes) => Object.fromEntries(STEPS.map((step, index) => [step, hexes[index]]));
const hazard = ramp(["#fff1f0", "#ffdfdc", "#ffc0ba", "#ff968c", "#ff6a5c", "#f2463a", "#d42f24", "#b0241b", "#8a1d17", "#5e1511", "#360b08"]);
const PALETTE = {
  slate: ramp(["#f6f7f8", "#eceef1", "#dcdfe4", "#c1c6ce", "#8f97a2", "#69717c", "#4d545e", "#373d45", "#22272e", "#161a1f", "#0e1013"]),
  amber: ramp(["#fff8e6", "#ffefc2", "#ffe08a", "#ffcd4d", "#ffbd1f", "#ffb400", "#b87900", "#8f5a00", "#6b4200", "#4d3000", "#2b1b00"]),
  emerald: ramp(["#eafaf1", "#cdf3de", "#9fe6bf", "#63d397", "#2fbf76", "#16a35e", "#0f7f47", "#0d6e3e", "#0c5532", "#093d24", "#052617"]),
  rose: hazard,
  red: hazard,
  blue: ramp(["#eef5ff", "#d9e8ff", "#b5d1ff", "#86b4ff", "#5a94f5", "#3576e6", "#1f5fd0", "#1a4ca8", "#173e86", "#122f63", "#0b1d3f"]),
  // Indigo accents fold into guide-sign blue so every workbench stays on palette.
  indigo: ramp(["#eef5ff", "#d9e8ff", "#b5d1ff", "#86b4ff", "#5a94f5", "#3576e6", "#1f5fd0", "#1a4ca8", "#173e86", "#122f63", "#0b1d3f"]),
};
const NAMED = { white: "#ffffff", black: "#000000", transparent: "transparent" };

function hexToRgb(hex) {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16)).join(" ");
}

/** Resolve `amber-500`, `slate-800/60`, `white` to a CSS color. */
function color(token) {
  const [name, alpha] = token.split("/");
  let hex = NAMED[name];
  if (!hex) {
    const match = /^([a-z]+)-(\d{2,3})$/.exec(name);
    if (!match || !PALETTE[match[1]]?.[match[2]]) {
      return null;
    }
    hex = PALETTE[match[1]][match[2]];
  }
  if (!alpha || hex === "transparent") {
    return hex;
  }
  return `rgb(${hexToRgb(hex)} / ${Number(alpha) / 100})`;
}

const rem = (units) => `${Number(units) * 0.25}rem`;
const TEXT = {
  xs: ["0.75rem", "1rem"],
  sm: ["0.875rem", "1.25rem"],
  base: ["1rem", "1.5rem"],
  lg: ["1.125rem", "1.75rem"],
  xl: ["1.25rem", "1.75rem"],
  "2xl": ["1.5rem", "2rem"],
  "3xl": ["1.875rem", "2.25rem"],
  "4xl": ["2.25rem", "2.5rem"],
  "5xl": ["3rem", "1"],
};
const WEIGHT = { medium: 500, semibold: 600, bold: 700, black: 800 };
const RADIUS = { "": "var(--radius-xs)", lg: "var(--radius-md)", xl: "var(--radius-lg)", "2xl": "var(--radius-xl)", full: "9999px" };
const SHADOW = {
  sm: "var(--shadow-sm)",
  "": "var(--shadow-md)",
  md: "var(--shadow-md)",
  lg: "0 10px 24px rgb(0 0 0 / 0.12)",
  xl: "0 18px 40px rgb(0 0 0 / 0.16)",
  "2xl": "var(--shadow-lg)",
  inner: "inset 0 2px 4px rgb(0 0 0 / 0.08)",
};
const MAX_W = { "3xl": "48rem", "4xl": "56rem", "7xl": "80rem" };
const STATIC = {
  block: "display:block",
  flex: "display:flex",
  grid: "display:grid",
  relative: "position:relative",
  "flex-col": "flex-direction:column",
  "flex-row": "flex-direction:row",
  "flex-wrap": "flex-wrap:wrap",
  "items-center": "align-items:center",
  "justify-between": "justify-content:space-between",
  "justify-center": "justify-content:center",
  "justify-items-center": "justify-items:center",
  "mx-auto": "margin-left:auto;margin-right:auto",
  "overflow-hidden": "overflow:hidden",
  "overflow-x-auto": "overflow-x:auto",
  truncate: "overflow:hidden;text-overflow:ellipsis;white-space:nowrap",
  "whitespace-pre-wrap": "white-space:pre-wrap",
  uppercase: "text-transform:uppercase",
  capitalize: "text-transform:capitalize",
  "text-left": "text-align:left",
  "text-center": "text-align:center",
  "font-mono": "font-family:var(--font-mono)",
  "font-sans": "font-family:var(--font-ui)",
  "tracking-tight": "letter-spacing:-0.02em",
  "tracking-wide": "letter-spacing:0.04em",
  "tracking-wider": "letter-spacing:0.1em",
  "leading-relaxed": "line-height:1.625",
  "cursor-pointer": "cursor:pointer",
  "cursor-default": "cursor:default",
  "border-collapse": "border-collapse:collapse",
  "w-full": "width:100%",
  "transition-all": "transition:all 160ms var(--ease-signal)",
  "transition-colors": "transition:color 160ms var(--ease-signal),background-color 160ms var(--ease-signal),border-color 160ms var(--ease-signal)",
  "animate-pulse": "animation:wb-pulse 2s cubic-bezier(0.4,0,0.6,1) infinite",
  "backdrop-blur": "backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)",
  "outline-none": "outline:2px solid transparent;outline-offset:2px",
  "opacity-50": "opacity:0.5",
  border: "border-width:1px;border-style:solid",
  "border-2": "border-width:2px;border-style:solid",
  "border-8": "border-width:8px;border-style:solid",
  "border-t": "border-top-width:1px;border-top-style:solid",
  "border-b": "border-bottom-width:1px;border-bottom-style:solid",
  "border-b-2": "border-bottom-width:2px;border-bottom-style:solid",
  "ring-2": "box-shadow:0 0 0 2px var(--wb-ring,rgb(255 180 0 / 0.5))",
  "bg-gradient-to-b": "background-image:linear-gradient(to bottom,var(--wb-from,transparent),var(--wb-via,var(--wb-to,transparent)),var(--wb-to,transparent))",
  "bg-gradient-to-r": "background-image:linear-gradient(to right,var(--wb-from,transparent),var(--wb-via,var(--wb-to,transparent)),var(--wb-to,transparent))",
};

/** Declarations for one bare utility (no variant prefix), or null if unknown. */
function declarations(utility) {
  if (STATIC[utility]) {
    return STATIC[utility];
  }
  let match;
  if ((match = /^text-\[(\d+)px\]$/.exec(utility))) {
    return `font-size:${match[1]}px`;
  }
  if ((match = /^text-(xs|sm|base|lg|xl|[2-5]xl)$/.exec(utility))) {
    return `font-size:${TEXT[match[1]][0]};line-height:${TEXT[match[1]][1]}`;
  }
  if ((match = /^font-(medium|semibold|bold|black)$/.exec(utility))) {
    return `font-weight:${WEIGHT[match[1]]}`;
  }
  if ((match = /^rounded(?:-(lg|xl|2xl|full))?$/.exec(utility))) {
    return `border-radius:${RADIUS[match[1] ?? ""]}`;
  }
  if ((match = /^shadow(?:-(sm|md|lg|xl|2xl|inner))?$/.exec(utility))) {
    return `box-shadow:${SHADOW[match[1] ?? ""]}`;
  }
  if ((match = /^shadow-([a-z]+-\d+(?:\/\d+)?)$/.exec(utility))) {
    return `--wb-shadow-color:${color(match[1])}`;
  }
  if ((match = /^max-w-(3xl|4xl|7xl)$/.exec(utility))) {
    return `max-width:${MAX_W[match[1]]}`;
  }
  if ((match = /^grid-cols-(\d+)$/.exec(utility))) {
    return `grid-template-columns:repeat(${match[1]},minmax(0,1fr))`;
  }
  if ((match = /^col-span-(\d+)$/.exec(utility))) {
    return `grid-column:span ${match[1]} / span ${match[1]}`;
  }
  if ((match = /^(p|px|py|pt|pb|m|mt|mb)-(\d+(?:\.5)?)$/.exec(utility))) {
    const value = rem(match[2]);
    const sides = {
      p: ["padding"],
      px: ["padding-left", "padding-right"],
      py: ["padding-top", "padding-bottom"],
      pt: ["padding-top"],
      pb: ["padding-bottom"],
      m: ["margin"],
      mt: ["margin-top"],
      mb: ["margin-bottom"],
    }[match[1]];
    return sides.map((side) => `${side}:${value}`).join(";");
  }
  if ((match = /^gap-(\d+(?:\.5)?)$/.exec(utility))) {
    return `gap:${rem(match[1])}`;
  }
  if ((match = /^(w|h)-(\d+(?:\.5)?)$/.exec(utility))) {
    return `${match[1] === "w" ? "width" : "height"}:${rem(match[2])}`;
  }
  if ((match = /^(bg|text|border|accent|ring|divide|from|via|to)-([a-z]+(?:-\d+)?(?:\/\d+)?)$/.exec(utility))) {
    const value = color(match[2]);
    if (!value) {
      return null;
    }
    switch (match[1]) {
      case "bg":
        return `background-color:${value}`;
      case "text":
        return `color:${value}`;
      case "border":
        return `border-color:${value}`;
      case "accent":
        return `accent-color:${value}`;
      case "ring":
        return `--wb-ring:${value}`;
      case "from":
        return `--wb-from:${value}`;
      case "via":
        return `--wb-via:${value}`;
      case "to":
        return `--wb-to:${value}`;
      default:
        return null;
    }
  }
  return null;
}

function escapeClass(name) {
  return name.replace(/([:/.[\]])/g, "\\$1");
}

const SPACE_Y = /^space-y-(\d+(?:\.5)?)$/;
const DIVIDE_Y = "divide-y";
const BREAKPOINTS = { sm: 640, md: 768, lg: 1024 };

function ruleFor(className) {
  const parts = className.split(":");
  const utility = parts.pop();
  const variants = parts;
  const breakpoint = variants.find((variant) => BREAKPOINTS[variant]);
  const dark = variants.includes("dark");
  const pseudo = variants
    .filter((variant) => ["hover", "focus", "disabled"].includes(variant))
    .map((variant) => `:${variant}`)
    .join("");

  let selector = `.${escapeClass(className)}${pseudo}`;
  let body;
  let match;
  if ((match = SPACE_Y.exec(utility))) {
    selector = `${selector} > :not([hidden]) ~ :not([hidden])`;
    body = `margin-top:${rem(match[1])}`;
  } else if (utility === DIVIDE_Y) {
    selector = `${selector} > :not([hidden]) ~ :not([hidden])`;
    body = "border-top-width:1px;border-top-style:solid;border-bottom-width:0";
  } else if ((match = /^divide-(.+)$/.exec(utility))) {
    const value = color(match[1]);
    if (!value) {
      return null;
    }
    selector = `${selector} > :not([hidden]) ~ :not([hidden])`;
    body = `border-color:${value}`;
  } else {
    body = declarations(utility);
  }
  if (!body) {
    return null;
  }
  if (dark) {
    selector = `[data-theme="dark"] ${selector}`;
  }
  return { breakpoint, css: `${selector}{${body}}` };
}

const found = new Set();
for (const source of SOURCES) {
  const text = readFileSync(path.join(WEB, source), "utf8");
  for (const attr of text.matchAll(/className=(?:"([^"]+)"|\{`([^`]+)`\})/g)) {
    const value = (attr[1] ?? attr[2]).replace(/\$\{[^}]*\}/g, " ");
    for (const token of value.split(/\s+/)) {
      if (token) {
        found.add(token);
      }
    }
  }
  // Class names chosen conditionally inside template literals / ternaries.
  for (const literal of text.matchAll(/["'`]([a-z0-9:\-/. [\]]+)["'`]/g)) {
    for (const token of literal[1].split(/\s+/)) {
      if (/^(?:[a-z]+:)*[a-z]+-[a-z0-9\-/.[\]]+$/.test(token) || STATIC[token]) {
        found.add(token);
      }
    }
  }
}

const base = [];
const media = { sm: [], md: [], lg: [] };
const unknown = [];
for (const className of [...found].sort()) {
  const rule = ruleFor(className);
  if (!rule) {
    unknown.push(className);
    continue;
  }
  (rule.breakpoint ? media[rule.breakpoint] : base).push(rule.css);
}

// Order matters: plain colors, then dark overrides, then state variants.
const weight = (css) => (css.startsWith("[data-theme") ? 1 : 0) + (/:(hover|focus|disabled)/.test(css) ? 2 : 0);
base.sort((a, b) => weight(a) - weight(b));

// Tailwind headings inherit their container's color; the app styles headings
// directly, so restore inheritance under any container that sets a text color.
// Emitted before the utilities so a heading's own color class still wins.
const textColorClasses = [...found].filter((name) => /^(?:dark:)?text-(?:white|[a-z]+-\d+)$/.test(name));
const headingInherit = textColorClasses.map((name) => {
  const scope = name.startsWith("dark:") ? `[data-theme="dark"] .${escapeClass(name)}` : `.${escapeClass(name)}`;
  return `${scope} :where(h1,h2,h3,h4,h5,h6)`;
});

const lines = [
  "/* Generated by scripts/generate-workbench-utilities.mjs — do not edit by hand. */",
  "/* Utility classes used by the forensics, incident, fleet, and TMC workbenches, */",
  "/* remapped onto the xROAD Signal palette. */",
  ".border,.border-2,.border-8,.border-t,.border-b,.border-b-2{border-color:var(--color-border)}",
  "@keyframes wb-pulse{50%{opacity:.5}}",
  ".focus\\:ring-2:focus{outline:none}",
  `${headingInherit.join(",")}{color:inherit}`,
  "/* Scoped preflight: the pages wrap these workbenches in .wb-scope. */",
  ".wb-scope :where(button){background:transparent;border:0 solid var(--color-border);color:inherit;font:inherit;padding:0;cursor:pointer}",
  ".wb-scope :where(h1,h2,h3,h4,h5,h6,p){margin:0}",
  ".wb-scope :where(ul,ol){margin:0;padding:0;list-style:none}",
  ".wb-scope :where(*){border-width:0;border-style:solid;border-color:var(--color-border)}",
  ".wb-scope .font-mono{overflow-wrap:anywhere}",
  ...base,
  "/* Amber action plates carry near-black ink, like a road sign. */",
  ".bg-amber-500.text-white,.bg-amber-600.text-white,.hover\\:bg-amber-700:hover.text-white{background-color:var(--signal-amber);color:var(--signal-on-amber)}",
  ".bg-amber-600.text-white:hover,.bg-amber-500.text-white:hover{background-color:var(--signal-amber-hi)}",
  ...Object.entries(media).flatMap(([name, rules]) =>
    rules.length ? [`@media (min-width:${BREAKPOINTS[name]}px){`, ...rules.map((rule) => `  ${rule}`), "}"] : [],
  ),
  "@media (prefers-reduced-motion:reduce){.animate-pulse{animation:none}}",
  "",
];
writeFileSync(OUTPUT, lines.join("\n"));
const ignored = unknown.filter((name) => /-/.test(name) && !/^(m-|ws-|ui-|data-)/.test(name));
console.log(`wrote ${base.length + Object.values(media).flat().length} utilities to ${path.relative(WEB, OUTPUT)}`);
if (ignored.length) {
  console.log(`unmapped: ${ignored.join(" ")}`);
}
