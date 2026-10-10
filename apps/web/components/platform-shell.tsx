"use client";

import Link from "next/link";
import { STATIC_DEMO } from "@/lib/demo-mode";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useInstitution } from "@/components/institution-provider";
import { institutionRouteEnabled, moduleEnabled } from "@/lib/institution-product";
import { BrandMark } from "@/components/brand";
import { CommandPalette } from "@/components/command-palette";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CloseIcon,
  MenuIcon,
  RefreshIcon,
  SearchIcon,
  SignInIcon,
  SignOutIcon,
  WorkspaceIcon,
} from "@/components/icons";
import { useLocale } from "@/components/locale-provider";
import { Reveal } from "@/components/motion";
import { usePlatformSession } from "@/components/session-provider";
import { ThemeToggle } from "@/components/theme-provider";
import { sanitizeReturnTo } from "@/lib/auth-session";
import { LOCALE_LABELS, LOCALES, isLocale } from "@/lib/i18n";
import {
  buildNavigationGroups,
  canAccessArea,
  NAV_ITEMS,
  resolveDefaultRoute,
  sessionMunicipalities,
  sessionOrganizations,
  type DemoProfile,
  type ShellArea,
} from "@/lib/platform-shell";
import { Eyebrow, NoAccessState, StatusPill, WarningState } from "./ui";

function LoginRoadArt() {
  return (
    <svg aria-hidden="true" className="login-road" focusable="false" preserveAspectRatio="xMidYMax slice" viewBox="0 0 600 420">
      <defs>
        <linearGradient id="login-road-fade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#0e1013" stopOpacity="0" />
          <stop offset="1" stopColor="#0e1013" stopOpacity=".9" />
        </linearGradient>
        <linearGradient id="login-road-top" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset=".35" stopColor="#fff" stopOpacity="1" />
        </linearGradient>
        <mask id="login-road-mask">
          <rect fill="url(#login-road-top)" height="420" width="600" />
        </mask>
      </defs>
      <g mask="url(#login-road-mask)">
      <g stroke="#2a3038" strokeWidth="1">
        {[110, 150, 200, 265, 345].map((y) => (
          <path d={`M0 ${y}H600`} key={y} opacity={0.4 + y / 700} />
        ))}
      </g>
      <path d="M40 420 286 78h28l246 342Z" fill="#181c21" />
      <path d="M40 420 286 78M560 420 314 78" stroke="#f4f2ec" strokeOpacity=".5" strokeWidth="2" />
      <path className="login-road-lane" d="M300 420V82" stroke="#ffb400" strokeDasharray="18 22" strokeWidth="4" />
      <path d="M142 420 293 78M458 420 307 78" stroke="#f4f2ec" strokeDasharray="10 16" strokeOpacity=".22" strokeWidth="1.5" />
      <g className="login-road-hotspots">
        <circle cx="330" cy="176" fill="#ff4b3e" r="5" />
        <circle cx="330" cy="176" fill="none" r="16" stroke="#ff4b3e" strokeOpacity=".5" />
        <circle cx="250" cy="290" fill="#ffb400" r="4.5" />
        <circle cx="250" cy="290" fill="none" r="14" stroke="#ffb400" strokeOpacity=".5" />
      </g>
      </g>
      <rect fill="url(#login-road-fade)" height="200" width="600" y="220" />
    </svg>
  );
}

export function LoginConsole() {
  const { config } = useInstitution();
  const { demoProfiles, isDemoAuthEnabled, signInAs } = usePlatformSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawReturnTo = searchParams.get("returnTo");
  const requestedReturnTo = sanitizeReturnTo(rawReturnTo, "/workspace");
  const authConfig = searchParams.get("authConfig");
  const authError = searchParams.get("authError");
  const requiredRoles = searchParams.get("requiredRoles");
  const oidcLoginHref = `/api/auth/login?returnTo=${encodeURIComponent(requestedReturnTo)}`;

  function activateProfile(profile: DemoProfile) {
    signInAs(profile.id);
    router.push(rawReturnTo ? requestedReturnTo : resolveDefaultRoute(profile.session, config));
  }

  return (
    <main className="login-page">
      <section className="login-aside" aria-label={config.brand_name}>
        <Link aria-label={`${config.brand_name} home`} className="login-brand" href="/">
          <BrandMark size={40} />
          <span>
            <strong>{config.brand_name}</strong>
            <small>{config.portal_subtitle}</small>
          </span>
        </Link>
        <div className="login-aside-copy">
          <p className="signal-kicker">
            <span className="signal-dot signal-dot-amber" aria-hidden="true" /> Institutional workspace
          </p>
          <h1>Every segment. Every junction. One view of risk.</h1>
          <p>
            Use your institution’s configured workflows to investigate road risk and review evidence for safety decisions.
          </p>
        </div>
        <LoginRoadArt />
        <ul className="login-aside-facts">
          <li>
            <WorkspaceIcon name="analyst" size={18} /> Hotspot investigation
          </li>
          {moduleEnabled(config, "interventions") ? <li><WorkspaceIcon name="scenarios" size={18} /> Intervention planning</li> : null}
          {moduleEnabled(config, "reporting") ? <li><WorkspaceIcon name="reports" size={18} /> Evidence and reports</li> : null}
        </ul>
      </section>
      <section className="login-shell">
        <div className="login-toolbar">
          <Link className="ghost-button ui-button-sm" href="/">
            <WorkspaceIcon name="map" size={16} />
            <span>{moduleEnabled(config, "public_portal") ? "Explore public map" : "Institution portal"}</span>
          </Link>
          <ThemeToggle />
        </div>
        <div className="hero-copy">
          <Eyebrow>Welcome to {config.brand_name}</Eyebrow>
          <h2>Your road safety workspace.</h2>
          <p>{STATIC_DEMO ? "Choose a demo role. No account or password is required; this is a simulated session in your browser." : "Sign in with your institutional account to explore risk, plan improvements, and manage road safety."}</p>
        </div>
        <Reveal delay={1} variant="rise">
          <div className="profile-grid">
            {!STATIC_DEMO ? <a className="profile-card profile-card-primary" href={oidcLoginHref}>
              <span className="profile-card-icon" aria-hidden="true">
                <SignInIcon size={20} />
              </span>
              <strong>Institutional identity provider</strong>
              <span>Continue with your institutional account.</span>
              <small>Secure organizational sign-in</small>
            </a> : null}
            {isDemoAuthEnabled
              ? demoProfiles.map((profile) => (
                  <button
                    key={profile.id}
                    className="profile-card"
                    onClick={() => activateProfile(profile)}
                    type="button"
                  >
                    <span className="profile-card-icon" aria-hidden="true">
                      {initials(profile.label)}
                    </span>
                    <strong>{profile.label}</strong>
                    <span>{profile.description}</span>
                    <small>{profile.session.roles.join(" · ")}</small>
                  </button>
                ))
              : null}
          </div>
        </Reveal>
        {authConfig === "missing" ? (
          <WarningState
            title="OIDC configuration missing"
            detail="Set the institution identity-provider issuer and client ID, or explicit provider URLs, before enabling production login."
            tone="danger"
          />
        ) : null}
        {authError ? (
          <WarningState
            title="Access could not be completed"
            detail={`Reason: ${authError}. Required roles: ${requiredRoles || "authenticated institutional role"}.`}
            tone="warning"
          />
        ) : null}
        {!isDemoAuthEnabled ? (
          <WarningState
            title="Local demo profiles disabled"
            detail="Set NEXT_PUBLIC_ENABLE_DEMO_AUTH=true in a non-production environment to use demo role profiles for local shell testing."
          />
        ) : null}
      </section>
    </main>
  );
}

function sessionScopeLabel(session: ReturnType<typeof usePlatformSession>["session"]): string {
  const municipality = sessionMunicipalities(session).find((item) => item.id === session.selectedMunicipalityId);
  return municipality?.name ?? "All municipalities";
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : name.slice(0, 2)).toUpperCase();
}

function WorkspaceRail({
  collapsed,
  onCloseMobile,
  onToggle,
}: {
  collapsed: boolean;
  onCloseMobile: () => void;
  onToggle: () => void;
}) {
  const { session } = usePlatformSession();
  const { t } = useLocale();
  const { config } = useInstitution();
  const navGroups = buildNavigationGroups(session, config);
  const pathname = usePathname();

  return (
    <aside className={`app-rail${collapsed ? " app-rail-collapsed" : ""}`} aria-label="Workspace navigation">
      <div className="app-rail-brand">
        <BrandMark className="app-rail-mark" size={34} />
        {!collapsed ? (
          <span className="app-rail-wordmark">
            <strong>{config.brand_name}</strong>
            <small>{config.portal_subtitle}</small>
          </span>
        ) : null}
        <button
          aria-label={t("shell.closeNav")}
          className="app-rail-close"
          onClick={onCloseMobile}
          type="button"
        >
          <CloseIcon />
        </button>
      </div>
      <nav className="app-rail-nav" aria-label="Primary">
        {navGroups.map((group) => (
          <div className="rail-group" key={group.id}>
            {!collapsed ? <div className="rail-group-label">{group.label}</div> : null}
            {group.items.map((item) => {
              const isActive =
                item.href === "/" || item.href === "/workspace" ? pathname === item.href : pathname.startsWith(item.href);
              return (
                <Link
                  aria-current={isActive ? "page" : undefined}
                  className={`rail-link${isActive ? " rail-link-active" : ""}`}
                  href={item.href}
                  key={item.href}
                  aria-label={collapsed ? item.label : undefined}
                  title={collapsed ? item.label : undefined}
                >
                  <WorkspaceIcon name={item.href.split("/").pop() || "map"} className="rail-icon" />
                  {!collapsed ? <span>{item.label}</span> : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="app-rail-foot">
        <div className="app-rail-status" title={`${sessionScopeLabel(session)} · network feed`}>
          <span className={`signal-dot${session.mode === "live" ? "" : " signal-dot-amber"}`} aria-hidden="true" />
          {!collapsed ? (
            <span>
              <strong>{session.mode === "live" ? "Network live" : session.mode === "demo" ? "Demo network" : "Public network"}</strong>
              {sessionScopeLabel(session)}
            </span>
          ) : null}
        </div>
        <button
          aria-label={collapsed ? t("shell.collapse") : undefined}
          className="app-rail-toggle"
          onClick={onToggle}
          type="button"
        >
          {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          {!collapsed ? <span>{t("shell.collapse")}</span> : null}
        </button>
      </div>
    </aside>
  );
}

function LanguageSwitch() {
  const { locale, setLocale, t } = useLocale();

  return (
    <label className="scope-field language-switch">
      <span>{t("shell.language")}</span>
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
  );
}

function ScopeSwitcher() {
  const { selectContext, session } = usePlatformSession();
  const { t } = useLocale();
  const organizations = sessionOrganizations(session);
  const municipalities = sessionMunicipalities(session);

  return (
    <div className="scope-switcher">
      <label className="scope-field">
        <span>{t("shell.org")}</span>
        <select
          aria-label={t("shell.org")}
          onChange={(event) => selectContext(event.target.value || null, session.selectedMunicipalityId)}
          value={session.selectedOrganizationId ?? ""}
        >
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>
              {organization.shortLabel}
            </option>
          ))}
        </select>
      </label>
      <label className="scope-field">
        <span>{t("shell.city")}</span>
        <select
          aria-label={t("shell.city")}
          onChange={(event) => selectContext(session.selectedOrganizationId, event.target.value || null)}
          value={session.selectedMunicipalityId ?? ""}
        >
          {municipalities.map((municipality) => (
            <option key={municipality.id} value={municipality.id}>
              {municipality.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function UtilityBar({ onOpenNav }: { onOpenNav: () => void }) {
  const { config } = useInstitution();
  const { refreshFromApi, session, signOut } = usePlatformSession();
  const { t } = useLocale();
  const environment =
    session.mode === "live"
      ? { key: "live" as const, label: t("env.live") }
      : session.mode === "demo"
        ? { key: "demo" as const, label: t("env.demo") }
        : { key: "public" as const, label: t("env.public") };

  return (
    <header className="utility-bar">
      <button
        aria-label={t("shell.openNav")}
        className="app-nav-toggle"
        onClick={onOpenNav}
        type="button"
      >
        <MenuIcon />
      </button>
      <Link href="/" className="mobile-brand" aria-label={`${config.brand_name} home`}><BrandMark size={32} /><strong>{config.brand_name}</strong></Link>
      <ScopeSwitcher />
      <div className="utility-bar-actions">
        <button
          className="command-trigger"
          onClick={() => window.dispatchEvent(new Event("command-palette:open"))}
          type="button"
        >
          <span>
            <SearchIcon size={16} />
            <span className="command-trigger-label">{t("shell.search")}</span>
          </span>
          <kbd>⌘K</kbd>
        </button>
        <span className={`env-badge env-${environment.key}`}>{environment.label}</span>
        <LanguageSwitch />
        <ThemeToggle />
        <button
          aria-label={t("shell.refresh")}
          className="icon-button utility-refresh"
          onClick={() => void refreshFromApi()}
          title={t("shell.refresh")}
          type="button"
        >
          <RefreshIcon size={17} />
        </button>
        <div className="utility-identity">
          <span className="identity-avatar" aria-hidden="true">
            {initials(session.displayName)}
          </span>
          <span>
            <strong>{session.displayName}</strong>
            <small>{session.roles[session.roles.length - 1] ?? "public"}</small>
          </span>
        </div>
        {session.mode !== "public" ? (
          <button className="ghost-button ui-button-sm" onClick={signOut} type="button">
            <SignOutIcon size={16} />
            <span>{t("shell.signOut")}</span>
          </button>
        ) : (
          <Link className="primary-button ui-button-sm" href="/login">
            <SignInIcon size={16} />
            <span>{t("shell.signIn")}</span>
          </Link>
        )}
      </div>
    </header>
  );
}

function WorkspaceBreadcrumbs() {
  const pathname = usePathname();
  const { t } = useLocale();
  const current = NAV_ITEMS.find((item) =>
    item.href === "/workspace" ? pathname === "/workspace" : item.href !== "/" && pathname.startsWith(item.href),
  );

  return (
    <nav aria-label="Breadcrumb" className="app-breadcrumbs">
      <ol>
        <li>
          <Link href="/workspace">{t("shell.workspace")}</Link>
        </li>
        {current && current.href !== "/workspace" ? (
          <li aria-current="page">{current.label}</li>
        ) : null}
      </ol>
    </nav>
  );
}

export function WorkspaceFrame({
  children,
  variant = "internal",
}: {
  children: ReactNode;
  variant?: "internal" | "public";
}) {
  const { config, isLoaded, configurationError, retryConfiguration } = useInstitution();
  const { isBootstrapping, session } = usePlatformSession();
  const { t } = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const deniedPath = searchParams.get("accessDenied");
  const requiredRoles = searchParams.get("requiredRoles");
  const [railCollapsed, setRailCollapsed] = useState(false);
  // Off-canvas navigation drawer for narrow viewports (#253). Closes whenever
  // the route changes so a tap-through dismisses it.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const isPublic = variant === "public";

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (isBootstrapping || isPublic) {
      return;
    }
    if (!canAccessArea(session, "internal")) {
      router.replace(`/login?returnTo=${encodeURIComponent(pathname)}`);
    }
  }, [isBootstrapping, isPublic, pathname, router, session]);

  if (configurationError) {
    return <main className="page-shell centered-shell"><NoAccessState title="Institution configuration unavailable" detail="The installation settings could not be loaded. Retry or contact your platform administrator." action={<button className="primary-button" type="button" onClick={retryConfiguration}>Retry</button>} /></main>;
  }

  if (isBootstrapping || !isLoaded) {
    return (
      <main className="page-shell centered-shell">
        <StatusPill label="Bootstrapping session" tone="warning" />
      </main>
    );
  }

  if (!isPublic && session.mode === "live" && (!session.selectedOrganizationId || !session.selectedMunicipalityId)) {
    return <main className="page-shell centered-shell"><NoAccessState title="No configured jurisdiction assigned" detail="Your account has no access to a jurisdiction configured for this institution. Ask the administrator to review your organization and jurisdiction assignments." /></main>;
  }

  // Public visitors get the same command-center shell (rail + utility bar),
  // just without the internal-access gate or workspace breadcrumbs.
  if (!isPublic && !canAccessArea(session, "internal")) {
    return null;
  }

  return (
    <div
      className={`app-shell${railCollapsed ? " app-shell-collapsed" : ""}${mobileNavOpen ? " app-shell-nav-open" : ""}`}
    >
      <WorkspaceRail
        collapsed={railCollapsed}
        onCloseMobile={() => setMobileNavOpen(false)}
        onToggle={() => setRailCollapsed((value) => !value)}
      />
      {mobileNavOpen ? (
        <button
          aria-label={t("shell.closeNav")}
          className="app-rail-backdrop"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        />
      ) : null}
      <div className="app-main">
        <UtilityBar onOpenNav={() => setMobileNavOpen(true)} />
        {!isPublic ? <WorkspaceBreadcrumbs /> : null}
        <main className="app-content">
          {deniedPath ? (
            <WarningState
              title="Route access denied"
              detail={`You were redirected from ${deniedPath}. Required roles: ${requiredRoles || "not supplied"}.`}
              tone="warning"
            />
          ) : null}
          {institutionRouteEnabled(config, pathname) ? children : (
            <NoAccessState title="Module not enabled" detail="This workflow is not included in your institution's configuration. Contact your platform administrator." action={<Link className="primary-button" href="/workspace">Open workspace</Link>} />
          )}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

export function AreaGate({
  area,
  children,
}: {
  area: Exclude<ShellArea, "public">;
  children: ReactNode;
}) {
  const { session } = usePlatformSession();

  if (canAccessArea(session, area)) {
    return <>{children}</>;
  }

  return (
    <NoAccessState
      title="This workspace is outside your current role"
      detail={`This page requires ${area.replace("_", " ")} access. Use the safe default route for your current session or sign in with a role that includes this workflow.`}
      action={
        <Link className="primary-button" href={resolveDefaultRoute(session)}>
          Open my workspace
        </Link>
      }
    />
  );
}
