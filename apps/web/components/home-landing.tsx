"use client";
import Link from "next/link";
import { Suspense, useEffect, useRef } from "react";

import { useInstitution } from "@/components/institution-provider";
import { moduleEnabled } from "@/lib/institution-product";
import { BrandLockup, BrandMark } from "@/components/brand";
import { ArrowRightIcon, LayersIcon, PulseIcon, RoadIcon, ShieldIcon, WorkspaceIcon } from "@/components/icons";
import { useLocale } from "@/components/locale-provider";
import { PublicReportsPanel } from "@/components/reports-hub";
import { PublicRiskExplorer } from "@/components/risk-explorer";
import { usePlatformSession } from "@/components/session-provider";
import { ThemeToggle } from "@/components/theme-provider";
import { LoadingState } from "@/components/ui";
import { LOCALE_LABELS, LOCALES, isLocale } from "@/lib/i18n";
import { resolveDefaultRoute } from "@/lib/platform-shell";

function HomeNav() {
  const { config } = useInstitution();
  const { session } = usePlatformSession();
  const { locale, setLocale, t } = useLocale();
  const signedIn = session.mode !== "public";

  return (
    <header className="sx-nav">
      <div className="sx-nav-inner">
        <Link aria-label={`${config.brand_name} home`} className="sx-brand" href="/">
          <BrandMark size={34} />
          <span>
            <strong>{config.brand_name}</strong>
            <small>{config.portal_subtitle}</small>
          </span>
        </Link>
        <nav aria-label="Public sections" className="sx-nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#risk-map">Risk map</a>
          <a href="#reports">Reports</a>
        </nav>
        <div className="sx-nav-actions">
          <label className="sx-nav-locale">
            <span className="sr-only">{t("shell.language")}</span>
            <select
              aria-label={t("shell.language")}
              onChange={(event) => {
                if (isLocale(event.target.value)) {
                  setLocale(event.target.value);
                }
              }}
              value={locale}
            >
              {LOCALES.map((name) => (
                <option key={name} value={name}>
                  {LOCALE_LABELS[name]}
                </option>
              ))}
            </select>
          </label>
          <ThemeToggle onDark />
          <Link className="primary-button sx-nav-cta" href={signedIn ? resolveDefaultRoute(session, config) : "/login"}>
            {signedIn ? "Open workspace" : "Sign in"}
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------ road scene */

const VIEW_W = 640;
const VIEW_H = 480;
const HORIZON = 150;
const FOCAL = 330; // camera height 1 → ground at depth 1 lands on the bottom edge
const CX = VIEW_W / 2;
const ROAD_HALF = 0.79;

/** One-point perspective projection of a ground-plane point (x lateral, z depth, h height). */
function project(x: number, z: number, h = 0): [number, number] {
  return [CX + (FOCAL * x) / z, HORIZON + (FOCAL * (1 - h)) / z];
}

function quad(points: Array<[number, number]>): string {
  return `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L")}Z`;
}

/** Foreshortened centre-line dashes for a given travel offset. */
function laneDashes(offset: number): string {
  const spacing = 0.9;
  const length = 0.42;
  const half = 0.018;
  let d = "";
  for (let i = 0; i < 46; i += 1) {
    const near = 0.75 + i * spacing - (offset % spacing);
    const far = near + length;
    if (near < 0.72 || far > 42) {
      continue;
    }
    d += quad([project(-half, near), project(half, near), project(half, far), project(-half, far)]);
  }
  return d;
}

const CROSS_NEAR = 2.6;
const CROSS_FAR = 3.25;
const POLES = [1.6, 3.9, 6.5, 10, 16, 26];

function RoadScene() {
  const laneRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    const path = laneRef.current;
    if (!path) {
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      return;
    }
    let frame = 0;
    let start: number | null = null;
    const tick = (now: number) => {
      start ??= now;
      path.setAttribute("d", laneDashes(((now - start) / 1000) * 1.1));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  const crossNearY = project(0, CROSS_NEAR)[1];
  const crossFarY = project(0, CROSS_FAR)[1];
  const [jx, jy] = project(0, (CROSS_NEAR + CROSS_FAR) / 2);
  const [sx, sy] = project(0.42, 6.2);
  const leftEdge = [project(-ROAD_HALF, 0.72), project(-ROAD_HALF, 400)];
  const rightEdge = [project(ROAD_HALF, 0.72), project(ROAD_HALF, 400)];

  return (
    <svg
      aria-label="Illustrative night view of a road approaching a junction, with a very-high-risk hotspot at the junction and a high-risk segment beyond it"
      className="sx-scene-svg"
      role="img"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
    >
      <defs>
        <linearGradient id="sx-sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#08090b" />
          <stop offset="1" stopColor="#151a20" />
        </linearGradient>
        <radialGradient id="sx-glow" cx=".5" cy=".31" r=".6">
          <stop offset="0" stopColor="#ffb400" stopOpacity=".32" />
          <stop offset=".45" stopColor="#ffb400" stopOpacity=".06" />
          <stop offset="1" stopColor="#ffb400" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="sx-asphalt" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#262c34" />
          <stop offset="1" stopColor="#343b45" />
        </linearGradient>
        <radialGradient id="sx-heat-red">
          <stop offset="0" stopColor="#ff4b3e" stopOpacity=".75" />
          <stop offset=".55" stopColor="#ff4b3e" stopOpacity=".22" />
          <stop offset="1" stopColor="#ff4b3e" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="sx-heat-amber">
          <stop offset="0" stopColor="#ffb400" stopOpacity=".7" />
          <stop offset=".6" stopColor="#ffb400" stopOpacity=".18" />
          <stop offset="1" stopColor="#ffb400" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="sx-vignette" x1="0" x2="0" y1="0" y2="1">
          <stop offset=".62" stopColor="#0e1013" stopOpacity="0" />
          <stop offset="1" stopColor="#0e1013" stopOpacity=".85" />
        </linearGradient>
      </defs>

      <rect fill="url(#sx-sky)" height={VIEW_H} width={VIEW_W} />
      <rect fill="url(#sx-glow)" height={VIEW_H} width={VIEW_W} />

      {/* Ground survey grid, foreshortened toward the horizon. */}
      <g stroke="#2a3038" strokeWidth="1">
        {[1.1, 1.5, 2, 2.6, 3.4, 4.6, 6.4, 9, 14, 24].map((z) => {
          const y = project(0, z)[1];
          return <path d={`M0 ${y.toFixed(1)}H${VIEW_W}`} key={z} opacity={Math.min(0.9, 1.4 / z + 0.15)} />;
        })}
        {[-5, -3.4, -2.2, -1.4, 1.4, 2.2, 3.4, 5].map((x) => {
          const [x1, y1] = project(x, 0.9);
          return <path d={`M${x1.toFixed(1)} ${y1.toFixed(1)}L${CX} ${HORIZON}`} key={x} opacity=".45" />;
        })}
      </g>
      <path d={`M0 ${HORIZON}H${VIEW_W}`} stroke="#48505b" strokeWidth="1" />

      {/* Cross road and main carriageway. */}
      <path d={`M0 ${crossFarY.toFixed(1)}H${VIEW_W}V${crossNearY.toFixed(1)}H0Z`} fill="url(#sx-asphalt)" />
      <path
        d={quad([project(-ROAD_HALF, 0.72), project(ROAD_HALF, 0.72), project(ROAD_HALF, 400), project(-ROAD_HALF, 400)])}
        fill="url(#sx-asphalt)"
      />
      <path d={`M0 ${crossFarY.toFixed(1)}H${VIEW_W}M0 ${crossNearY.toFixed(1)}H${VIEW_W}`} stroke="#f4f2ec" strokeOpacity=".28" strokeDasharray="14 10" />
      {/* Stop lines at the junction mouth. */}
      <path
        d={quad([project(0.04, CROSS_NEAR - 0.05), project(ROAD_HALF - 0.06, CROSS_NEAR - 0.05), project(ROAD_HALF - 0.06, CROSS_NEAR - 0.12), project(0.04, CROSS_NEAR - 0.12)])}
        fill="#f4f2ec"
        fillOpacity=".55"
      />
      <path d={`M${leftEdge[0].join(" ")}L${leftEdge[1].join(" ")}M${rightEdge[0].join(" ")}L${rightEdge[1].join(" ")}`} stroke="#f4f2ec" strokeOpacity=".62" strokeWidth="2.2" />

      {/* Risk heat on the surface: very high at the junction, high on the segment beyond. */}
      <ellipse cx={jx} cy={jy} fill="url(#sx-heat-red)" rx="170" ry="30" />
      <ellipse cx={sx} cy={sy} fill="url(#sx-heat-amber)" rx="52" ry="9" />

      <path d={laneDashes(0)} fill="#ffb400" ref={laneRef} />

      {/* Street lighting along both verges. */}
      <g>
        {POLES.flatMap((z) =>
          [-1.05, 1.05].map((x) => {
            const [bx, by] = project(x, z);
            const [tx, ty] = project(x, z, 1.35);
            const [lx] = project(x * 0.86, z, 1.35);
            const r = Math.max(1.2, 9 / z);
            return (
              <g key={`${x}-${z}`}>
                <path d={`M${bx.toFixed(1)} ${by.toFixed(1)}L${tx.toFixed(1)} ${ty.toFixed(1)}L${lx.toFixed(1)} ${ty.toFixed(1)}`} stroke="#48505b" strokeWidth={Math.max(0.8, 3 / z)} fill="none" />
                <circle cx={lx} cy={ty} fill="#ffe1a0" opacity=".9" r={r * 0.45} />
                <circle cx={lx} cy={ty} fill="#ffc940" opacity=".12" r={r * 2.4} />
              </g>
            );
          }),
        )}
      </g>

      {/* Hotspot beacons. */}
      <g className="sx-beacon">
        <circle cx={jx} cy={jy} fill="none" r="18" stroke="#ff4b3e" strokeWidth="1.5" />
        <circle cx={jx} cy={jy} fill="none" r="30" stroke="#ff4b3e" strokeOpacity=".4" />
      </g>
      <circle cx={jx} cy={jy} fill="#ff4b3e" r="5.5" stroke="#0e1013" strokeWidth="2" />
      <g className="sx-beacon sx-beacon-late">
        <circle cx={sx} cy={sy} fill="none" r="11" stroke="#ffb400" strokeWidth="1.2" />
      </g>
      <circle cx={sx} cy={sy} fill="#ffb400" r="3.6" stroke="#0e1013" strokeWidth="1.5" />

      {/* Callout leaders to the instrument cards. */}
      <path d={`M${jx + 6} ${jy - 6}L${jx + 70} ${jy - 70}H${jx + 150}`} fill="none" stroke="#ff4b3e" strokeOpacity=".75" strokeWidth="1" />
      <path d={`M${sx - 4} ${sy - 4}L${sx - 60} ${sy - 46}H${sx - 150}`} fill="none" stroke="#ffb400" strokeOpacity=".75" strokeWidth="1" />

      <rect fill="url(#sx-vignette)" height={VIEW_H} width={VIEW_W} />
    </svg>
  );
}

const RAMP = [
  { label: "Minimal", token: "var(--color-risk-minimal-fill)" },
  { label: "Low", token: "var(--color-risk-low-fill)" },
  { label: "Moderate", token: "var(--color-risk-moderate-fill)" },
  { label: "High", token: "var(--color-risk-high-fill)" },
  { label: "Very high", token: "var(--color-risk-very-high-fill)" },
];

function HeroScene() {
  return (
    <figure className="sx-scene" aria-label="Concept view of the xROAD risk lens. Illustrative, not observed data.">
      <div className="sx-scene-bar">
        <span>
          <PulseIcon size={15} /> RISK LENS
        </span>
        <span className="sx-scene-tag">CONCEPT VIEW · NOT LIVE DATA</span>
      </div>
      <div className="sx-scene-stage">
        <RoadScene />
        <div className="sx-hud sx-hud-junction">
          <span className="sx-hud-kicker">
            <i className="sx-hud-dot sx-hud-dot-red" /> Junction
          </span>
          <strong>Very high risk</strong>
          <small>Crash history · exposure · geometry</small>
        </div>
        <div className="sx-hud sx-hud-segment">
          <span className="sx-hud-kicker">
            <i className="sx-hud-dot" /> Segment
          </span>
          <strong>High risk</strong>
          <small>Interval shown with every estimate</small>
        </div>
      </div>
      <figcaption className="sx-scene-legend">
        <span>Risk band</span>
        <ol>
          {RAMP.map((band) => (
            <li key={band.label}>
              <i style={{ background: band.token }} />
              {band.label}
            </li>
          ))}
        </ol>
      </figcaption>
    </figure>
  );
}

/* ----------------------------------------------------------------- page */

const CAPABILITIES = [
  { icon: <WorkspaceIcon name="analyst" size={22} />, title: "Hotspot detection", copy: "Segments and junctions ranked by modelled risk, not raw counts." },
  { icon: <LayersIcon size={22} />, title: "Exposure-aware models", copy: "Traffic volume and geometry normalise every estimate." },
  { icon: <WorkspaceIcon name="scenarios" size={22} />, title: "Intervention what-ifs", copy: "Compare treatments before a single cone goes down." },
  { icon: <ShieldIcon size={22} />, title: "Governed evidence", copy: "Provenance, review, and publication on the record." },
];

const WORKFLOWS = [
  {
    km: "KM 01",
    icon: "uploads",
    title: "Build the evidence",
    copy: "Bring crash records, road geometry, and exposure together. Check quality and provenance before analysis.",
  },
  {
    km: "KM 02",
    icon: "analyst",
    title: "Understand the risk",
    copy: "Explore segments and junctions, inspect model evidence, and consider uncertainty alongside every estimate.",
  },
  {
    km: "KM 03",
    icon: "scenarios",
    title: "Evaluate the response",
    copy: "Compare intervention scenarios, document tradeoffs, and publish findings that others can review.",
  },
];

export function PublicHome() {
  const { config, isLoaded, configurationError, retryConfiguration } = useInstitution();
  const { session } = usePlatformSession();
  const workspace = session.mode !== "public" ? resolveDefaultRoute(session, config) : "/login";
  if (!isLoaded) return <main className="page-shell"><LoadingState title="Loading institution" detail="Preparing the institution portal." /></main>;
  if (configurationError) return <main className="page-shell"><BrandLockup /><h1>Institution configuration unavailable</h1><p>Retry or contact the platform administrator.</p><button className="primary-button" type="button" onClick={retryConfiguration}>Retry</button></main>;
  if (!moduleEnabled(config, "public_portal")) return <main className="page-shell centered-shell"><BrandLockup /><h1>{config.institution_name}</h1><p>{config.portal_subtitle}</p><Link className="primary-button" href={workspace}>Open institutional workspace</Link></main>;
  return (
    <div className="home sx-home">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="sx-night">
        <HomeNav />
        <section className="sx-hero" aria-labelledby="sx-hero-title">
          <div className="sx-hero-copy">
            <p className="signal-kicker">
              <span className="signal-dot signal-dot-amber" aria-hidden="true" /> Road safety intelligence
            </p>
            <h1 id="sx-hero-title">
              See the risk <br />
              <em>before the crash.</em>
            </h1>
            <p className="sx-lede">
              xROAD turns crash records, traffic exposure, and road geometry into a live picture of where the next
              collision is most likely — and which intervention will prevent it.
            </p>
            <div className="sx-actions">
              <a className="primary-button ui-button-lg" href="#risk-map">
                <WorkspaceIcon name="map" /> <span>Explore the risk map</span>
              </a>
              <Link className="sx-secondary" href={workspace}>
                <span>Open workspace</span> <ArrowRightIcon />
              </Link>
            </div>
            <ul className="sx-attributes">
              <li>
                <WorkspaceIcon name="research" size={16} /> Reproducible research
              </li>
              <li>
                <ShieldIcon size={16} /> Evidence-led decisions
              </li>
              <li>
                <RoadIcon size={16} /> Open public data
              </li>
            </ul>
          </div>
          <HeroScene />
        </section>
        <ul className="sx-capabilities" aria-label="Capabilities">
          {CAPABILITIES.map((item) => (
            <li key={item.title}>
              <span className="sx-capability-icon">{item.icon}</span>
              <span>
                <strong>{item.title}</strong>
                <small>{item.copy}</small>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <main className="sx-main" id="main">
        <section className="sx-section sx-route-section" id="how-it-works">
          <div className="sx-section-heading">
            <div>
              <p className="eyebrow">From evidence to action</p>
              <h2>Better decisions start with context.</h2>
            </div>
            <p>A traceable route from the data you collect to the improvements you propose.</p>
          </div>
          <ol className="sx-route">
            {WORKFLOWS.map((item) => (
              <li key={item.km}>
                <div className="sx-route-post">
                  <span className="sx-route-icon">
                    <WorkspaceIcon name={item.icon} size={24} />
                  </span>
                  <span className="sx-route-km">{item.km}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.copy}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="sx-section" id="risk-map">
          <div className="sx-section-heading">
            <div>
              <p className="eyebrow">Public risk explorer</p>
              <h2>A network view. A local understanding.</h2>
            </div>
            <span className="sx-access">
              <ShieldIcon size={16} /> Public aggregated data
            </span>
          </div>
          <p className="sx-section-description">
            Filter by municipality, year, and risk band. Inspect available evidence and share your selected view.
          </p>
          <Suspense
            fallback={<LoadingState title="Preparing public risk explorer" detail="Loading map state and public filters." />}
          >
            <PublicRiskExplorer />
          </Suspense>
        </section>

        <section className="sx-section" id="reports">
          <div className="sx-section-heading">
            <div>
              <p className="eyebrow">Open evidence</p>
              <h2>Research you can review.</h2>
            </div>
            <span className="sx-access">
              <WorkspaceIcon name="reports" size={16} /> Published with sources
            </span>
          </div>
          <p className="sx-section-description">
            Published reports and approved public extracts, with dates and sources attached.
          </p>
          <PublicReportsPanel />
        </section>

        <section className="sx-cta">
          <div>
            <p className="signal-kicker">
              <span className="signal-dot signal-dot-amber" aria-hidden="true" /> The analysis behind the map
            </p>
            <h2>Move from insight to intervention.</h2>
            <p>Explore models, compare scenarios, and manage your road safety research.</p>
          </div>
          <Link className="primary-button ui-button-lg" href={workspace}>
            <span>Open your workspace</span> <ArrowRightIcon />
          </Link>
        </section>
      </main>

      <footer className="sx-footer">
        <div className="sx-footer-inner">
          <Link className="sx-brand" href="/">
            <BrandMark size={30} />
            <span>
              <strong>xROAD</strong>
              <small>Road risk intelligence</small>
            </span>
          </Link>
          <p>Road accident risk modeling · Open research, informed decisions.</p>
          <Link className="sx-footer-link" href="/login">
            <span>Workspace sign in</span> <ArrowRightIcon size={14} />
          </Link>
        </div>
      </footer>
    </div>
  );
}
