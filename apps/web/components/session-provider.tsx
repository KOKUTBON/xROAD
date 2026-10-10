"use client";

import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  DEMO_PROFILES,
  applySessionContext,
  sessionFromApiSnapshot,
  type DemoProfile,
  type PlatformSession,
} from "@/lib/platform-shell";
import { STATIC_DEMO, BASE_PATH } from "@/lib/demo-mode";
import { isDemoAuthEnabled as resolveDemoAuthEnabled } from "@/lib/auth-session";

const STORAGE_KEY = STATIC_DEMO ? `road-risk-pages-session-tirana-v2:${BASE_PATH}` : "road-risk-web-session-v1";
const AUTH_SESSION_ENDPOINT = "/api/auth/session";

interface SessionContextValue {
  demoProfiles: DemoProfile[];
  isDemoAuthEnabled: boolean;
  isBootstrapping: boolean;
  session: PlatformSession;
  refreshFromApi: () => Promise<void>;
  selectContext: (organizationId: string | null, municipalityId: string | null) => void;
  signInAs: (profileId: string) => void;
  signOut: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function readStoredSession(): PlatformSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const rawValue = window.localStorage.getItem(STORAGE_KEY);
  if (!rawValue) {
    return null;
  }
  try {
    const parsed = JSON.parse(rawValue) as PlatformSession;
    return applySessionContext(
      parsed,
      parsed.selectedOrganizationId,
      parsed.selectedMunicipalityId,
    );
  } catch {
    return null;
  }
}

function persistSession(session: PlatformSession): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function clearSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(STORAGE_KEY);
}

async function fetchApiSession(): Promise<PlatformSession | null> {
  if (STATIC_DEMO) return null;
  const response = await fetch(AUTH_SESSION_ENDPOINT, {
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    return null;
  }
  const payload = await response.json();
  if (!payload || typeof payload !== "object") {
    return null;
  }
  return sessionFromApiSnapshot(payload);
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const demoAuthEnabled = resolveDemoAuthEnabled();
  const publicSession = DEMO_PROFILES[0].session;
  const [session, setSession] = useState<PlatformSession>(publicSession);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    let active = true;
    const storedSession = demoAuthEnabled ? readStoredSession() : null;
    if (storedSession) {
      setSession(storedSession);
    }

    async function load() {
      try {
        const liveSession = await fetchApiSession();
        if (!active) {
          return;
        }
        if (liveSession && liveSession.subject) {
          const hydrated = applySessionContext(
            liveSession,
            liveSession.selectedOrganizationId,
            liveSession.selectedMunicipalityId,
          );
          setSession(hydrated);
        } else if (!storedSession && !demoAuthEnabled) {
          setSession(publicSession);
        }
      } catch {
        // Keep public pages usable when the API is unavailable in local development.
      } finally {
        if (active) {
          setIsBootstrapping(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [demoAuthEnabled, publicSession]);

  async function refreshFromApi() {
    const liveSession = await fetchApiSession();
    if (!liveSession) {
      return;
    }
    const hydrated = applySessionContext(
      liveSession,
      liveSession.selectedOrganizationId,
      liveSession.selectedMunicipalityId,
    );
    startTransition(() => {
      setSession(hydrated);
    });
  }

  function signInAs(profileId: string) {
    if (!demoAuthEnabled) {
      return;
    }
    const profile = DEMO_PROFILES.find((item) => item.id === profileId);
    if (!profile) {
      return;
    }
    const hydrated = applySessionContext(
      profile.session,
      profile.session.selectedOrganizationId,
      profile.session.selectedMunicipalityId,
    );
    startTransition(() => {
      setSession(hydrated);
    });
    persistSession(hydrated);
  }

  function signOut() {
    clearSession();
    if (session.mode === "live" && typeof window !== "undefined") {
      window.location.assign("/api/auth/logout?returnTo=/");
      return;
    }
    startTransition(() => {
      setSession(publicSession);
    });
  }

  function selectContext(organizationId: string | null, municipalityId: string | null) {
    const nextSession = applySessionContext(session, organizationId, municipalityId);
    startTransition(() => {
      setSession(nextSession);
    });
    if (demoAuthEnabled && nextSession.mode === "demo") {
      persistSession(nextSession);
    }
  }

  return (
    <SessionContext.Provider
      value={{
        demoProfiles: demoAuthEnabled ? DEMO_PROFILES : [],
        isDemoAuthEnabled: demoAuthEnabled,
        isBootstrapping,
        session,
        refreshFromApi,
        selectContext,
        signInAs,
        signOut,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function usePlatformSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("usePlatformSession must be used inside SessionProvider.");
  }
  return context;
}
