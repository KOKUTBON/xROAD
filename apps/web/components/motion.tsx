"use client";

import { usePathname } from "next/navigation";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { motifForPath, type MotifId, type PageMotif } from "@/lib/page-motion";

/**
 * Motion system (UX 3.0).
 *
 * Three ingredients, all progressive enhancement: content is fully readable
 * with JavaScript disabled, and every animation is collapsed to its final
 * frame under `prefers-reduced-motion: reduce`.
 *
 *  - `Reveal` / `RouteStage`  — content eases up into place as it scrolls in.
 *  - `CountUp`                — figures climb to their value once on screen.
 *  - `MotifGraphic`           — one signature animation per page, chosen to
 *                               express what that page is *for* (see
 *                               `lib/page-motion.ts`).
 *
 * The "reveal" classes are added by script, never in the server markup, so a
 * failed hydration can never leave a page invisible. A belt-and-braces timeout
 * also reveals everything after a short delay if IntersectionObserver is
 * unavailable.
 */

/**
 * Safety net: if the observer never fires (a hidden/background tab, a browser
 * without IntersectionObserver), everything is revealed anyway. Kept short so
 * content is never perceptibly withheld and automated gates see a settled page.
 */
const REVEAL_FALLBACK_MS = 400;

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      return;
    }
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

/** Observe one element and report the first time it enters the viewport. */
function useInView<T extends HTMLElement>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    observer.observe(node);
    const fallback = window.setTimeout(() => setInView(true), REVEAL_FALLBACK_MS);
    return () => {
      observer.disconnect();
      window.clearTimeout(fallback);
    };
  }, []);

  return [ref, inView];
}

/**
 * Scroll-reveal wrapper. `delay` staggers siblings; `as` keeps the DOM
 * semantics of whatever it wraps.
 */
export function Reveal({
  children,
  className = "",
  delay = 0,
  variant = "rise",
}: {
  children: ReactNode;
  className?: string;
  /** Stagger index — multiplied by a token step, not raw milliseconds. */
  delay?: number;
  variant?: "rise" | "fade" | "scale" | "left" | "right";
}) {
  const [ref, inView] = useInView<HTMLDivElement>();
  return (
    <div
      className={`reveal reveal-${variant}${inView ? " reveal-in" : ""}${className ? ` ${className}` : ""}`}
      ref={ref}
      style={{ "--reveal-index": delay } as CSSProperties}
    >
      {children}
    </div>
  );
}

/**
 * Reveal a whole subtree's cards in sequence without touching every page.
 * Elements matching `selector` inside the stage get the reveal treatment as
 * they scroll into view, indexed so they cascade rather than pop together.
 */
function useCascadeReveal(
  containerRef: React.RefObject<HTMLElement | null>,
  selector: string,
  resetKey?: string,
) {
  useEffect(() => {
    const root = containerRef.current;
    if (!root) {
      return;
    }
    // Nodes still waiting to be revealed. Excludes anything already revealed
    // and anything inside an explicit <Reveal>, which owns its own timing.
    // Deliberately idempotent: the effect may run more than once (React
    // StrictMode remounts effects in development), and each run must be able
    // to re-establish the observer over the same nodes.
    const targets = Array.from(root.querySelectorAll<HTMLElement>(selector)).filter(
      (node) =>
        !node.classList.contains("reveal-in") &&
        !node.parentElement?.closest(".reveal"),
    );
    if (targets.length === 0) {
      return;
    }

    const revealAll = () => targets.forEach((node) => node.classList.add("reveal-in"));

    targets.forEach((node, index) => {
      node.classList.add("reveal", "reveal-rise");
      node.style.setProperty("--reveal-index", String(Math.min(index, 6)));
    });

    if (typeof IntersectionObserver === "undefined") {
      revealAll();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-in");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.05 },
    );
    targets.forEach((node) => observer.observe(node));
    // Safety net: a background/hidden tab never fires the observer, so nothing
    // can stay invisible for longer than this.
    const fallback = window.setTimeout(revealAll, REVEAL_FALLBACK_MS);

    return () => {
      observer.disconnect();
      window.clearTimeout(fallback);
    };
  }, [containerRef, selector, resetKey]);
}

/** Animated figure. Counts from 0 to `value` once, the first time it is seen. */
export function CountUp({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 900,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}) {
  const [ref, inView] = useInView<HTMLSpanElement>();
  const reduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView) {
      return;
    }
    if (reduced || duration <= 0) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      // easeOutExpo — fast settle, Apple-ish deceleration.
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setShown(value * eased);
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [duration, inView, reduced, value]);

  const text = useMemo(
    () => `${prefix}${shown.toFixed(decimals)}${suffix}`,
    [decimals, prefix, shown, suffix],
  );

  return (
    <span className="count-up tabular-nums" ref={ref}>
      {text}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Signature graphics                                                  */
/* ------------------------------------------------------------------ */

function MotifRoad() {
  return (
    <>
      <path className="m-draw" d="M6 58C60 58 74 12 128 12s70 40 106 40" />
      <path className="m-dash" d="M6 58C60 58 74 12 128 12s70 40 106 40" />
      <circle className="m-node m-node-1" cx="74" cy="32" r="4" />
      <circle className="m-node m-node-2" cx="128" cy="12" r="4" />
      <circle className="m-node m-node-3" cx="186" cy="34" r="4" />
    </>
  );
}

function MotifControlRoom() {
  return (
    <>
      {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
        <rect
          className={`m-tile m-step-${index % 6}`}
          height={index % 2 === 0 ? 26 : 18}
          key={index}
          rx="5"
          width="22"
          x={12 + index * 28}
          y={index % 2 === 0 ? 20 : 26}
        />
      ))}
    </>
  );
}

function MotifBoard() {
  const bars = [18, 30, 24, 42, 36];
  return (
    <>
      <line className="m-base" x1="8" x2="232" y1="58" y2="58" />
      {bars.map((height, index) => (
        <rect
          className={`m-bar m-step-${index}`}
          height={height}
          key={index}
          rx="4"
          style={{ "--m-h": `${height}px` } as CSSProperties}
          width="20"
          x={26 + index * 40}
          y={58 - height}
        />
      ))}
    </>
  );
}

function MotifReport() {
  return (
    <>
      <rect className="m-sheet m-step-0" height="44" rx="5" width="34" x="14" y="12" />
      <rect className="m-sheet m-step-1" height="44" rx="5" width="34" x="58" y="12" />
      <rect className="m-sheet m-step-2" height="44" rx="5" width="34" x="102" y="12" />
      {[0, 1, 2, 3].map((index) => (
        <line
          className={`m-line m-step-${index}`}
          key={index}
          x1="154"
          x2="226"
          y1={18 + index * 11}
          y2={18 + index * 11}
        />
      ))}
    </>
  );
}

function MotifScatter() {
  const dots = [
    [24, 48],
    [52, 40],
    [76, 44],
    [104, 30],
    [132, 34],
    [160, 22],
    [188, 26],
    [214, 14],
  ];
  return (
    <>
      <line className="m-base" x1="8" x2="232" y1="58" y2="58" />
      {dots.map(([cx, cy], index) => (
        <circle className={`m-dot m-step-${index % 6}`} cx={cx} cy={cy} key={index} r="3.5" />
      ))}
      <path className="m-draw" d="M20 50C70 46 150 26 220 14" />
    </>
  );
}

function MotifBranch() {
  return (
    <>
      <path className="m-draw m-step-0" d="M10 32h68" />
      <path className="m-draw m-step-1" d="M78 32c34 0 34-20 68-20h74" />
      <path className="m-draw m-step-2" d="M78 32h142" />
      <path className="m-draw m-step-3" d="M78 32c34 0 34 20 68 20h74" />
      <circle className="m-node m-node-1" cx="78" cy="32" r="4" />
    </>
  );
}

function MotifDiff() {
  return (
    <>
      <rect className="m-sheet m-step-0" height="40" rx="6" width="90" x="14" y="14" />
      <rect className="m-sheet-swap m-step-2" height="40" rx="6" width="90" x="136" y="14" />
      <path className="m-draw m-step-1" d="M110 34h20m-6-6 6 6-6 6" />
    </>
  );
}

function MotifRadar() {
  return (
    <>
      <circle className="m-ring m-step-0" cx="120" cy="34" r="12" />
      <circle className="m-ring m-step-1" cx="120" cy="34" r="22" />
      <circle className="m-ring m-step-2" cx="120" cy="34" r="30" />
      <line className="m-sweep" x1="120" x2="120" y1="34" y2="6" />
      <circle className="m-node m-node-1" cx="142" cy="24" r="3.5" />
      <circle className="m-node m-node-3" cx="100" cy="48" r="3.5" />
    </>
  );
}

function MotifRain() {
  return (
    <>
      <path className="m-draw" d="M8 52c40 0 40-10 80-10s40 10 80 10 40-8 64-8" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
        <line
          className={`m-drop m-step-${index % 6}`}
          key={index}
          x1={20 + index * 28}
          x2={14 + index * 28}
          y1="6"
          y2="18"
        />
      ))}
    </>
  );
}

function MotifSignal() {
  return (
    <>
      <rect className="m-frame" height="52" rx="10" width="26" x="14" y="6" />
      <circle className="m-lamp m-lamp-1" cx="27" cy="18" r="5" />
      <circle className="m-lamp m-lamp-2" cx="27" cy="32" r="5" />
      <circle className="m-lamp m-lamp-3" cx="27" cy="46" r="5" />
      <path className="m-dash" d="M54 44h178" />
      <path className="m-dash m-step-3" d="M54 20h178" />
    </>
  );
}

function MotifShield() {
  return (
    <>
      <path className="m-draw" d="M120 6l30 12v18c0 16-12 24-30 28-18-4-30-12-30-28V18z" />
      <path className="m-draw m-step-3" d="M108 34l9 9 17-18" />
    </>
  );
}

function MotifUpload() {
  return (
    <>
      <path className="m-lift m-step-0" d="M92 44V18m-9 9 9-9 9 9" />
      <path className="m-lift m-step-2" d="M120 48V14m-9 9 9-9 9 9" />
      <path className="m-lift m-step-4" d="M148 44V18m-9 9 9-9 9 9" />
      <path className="m-draw" d="M72 54h96" />
    </>
  );
}

function MotifCycle() {
  return (
    <>
      <circle className="m-orbit" cx="120" cy="32" r="22" />
      <path className="m-draw m-step-2" d="M110 32l7 7 14-15" />
      <circle className="m-node m-node-2" cx="120" cy="10" r="3.5" />
    </>
  );
}

function MotifPulse() {
  return (
    <path
      className="m-ecg"
      d="M6 34h48l10-18 12 36 10-18h26l10-14 12 28 10-14h32l10-16 12 32 10-16h14"
    />
  );
}

function MotifKey() {
  return (
    <>
      <circle className="m-ring m-step-0" cx="120" cy="32" r="10" />
      <circle className="m-ring m-step-1" cx="120" cy="32" r="20" />
      <circle className="m-ring m-step-2" cx="120" cy="32" r="30" />
      <path className="m-draw m-step-3" d="M112 32l6 6 12-13" />
    </>
  );
}

const MOTIF_SHAPES: Record<MotifId, () => ReactNode> = {
  road: MotifRoad,
  "control-room": MotifControlRoom,
  board: MotifBoard,
  report: MotifReport,
  scatter: MotifScatter,
  branch: MotifBranch,
  diff: MotifDiff,
  radar: MotifRadar,
  rain: MotifRain,
  signal: MotifSignal,
  shield: MotifShield,
  upload: MotifUpload,
  cycle: MotifCycle,
  pulse: MotifPulse,
  key: MotifKey,
};

/**
 * The signature graphic for a page. Purely decorative — the meaning is also
 * carried by the page's own copy — so it is hidden from assistive technology.
 */
export function MotifGraphic({
  motif,
  size = "band",
}: {
  motif: PageMotif;
  size?: "band" | "hero";
}) {
  const [ref, inView] = useInView<HTMLDivElement>();
  const Shape = MOTIF_SHAPES[motif.id];
  return (
    <div
      aria-hidden="true"
      className={`motif motif-${size} motif-${motif.id}${inView ? " motif-live" : ""}`}
      data-motif={motif.id}
      ref={ref}
      title={motif.meaning}
    >
      <svg
        fill="none"
        preserveAspectRatio="xMidYMid meet"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 240 64"
      >
        <Shape />
      </svg>
    </div>
  );
}

/**
 * Route stage. Wraps every workspace page: replays the route transition,
 * cascades the page's cards into view, and stamps the route's motif on the
 * subtree so page chrome can pick it up.
 */
export function RouteStage({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const pathname = usePathname() ?? "/";
  const pageMotif = motifForPath(pathname);
  useCascadeReveal(
    ref,
    ".ws-zone-header, .ws-kpi-strip > *, .ws-zone-filters, .ws-zone-work > *, .ws-surface > *, .ws-zone-detail",
    pathname,
  );

  return (
    <div className="route-stage route-fade" data-motif={pageMotif.id} ref={ref}>
      <div className="route-motif-band">
        <MotifGraphic motif={pageMotif} />
      </div>
      {children}
    </div>
  );
}
