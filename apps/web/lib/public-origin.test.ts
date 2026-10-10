import { afterEach, describe, expect, it, vi } from "vitest";
import { publicRequestOrigin } from "./auth-session";

afterEach(() => vi.unstubAllEnvs());

describe("public redirects behind the institutional gateway", () => {
  it("uses the configured HTTPS origin instead of an internal host or scheme", () => {
    vi.stubEnv("ROAD_RISK_PUBLIC_ORIGIN", "https://roads.agency.test");
    expect(publicRequestOrigin("http://web:3000/api/auth/callback?code=secret")).toBe("https://roads.agency.test");
  });
  it("preserves development origins when no public origin is configured", () => {
    vi.stubEnv("ROAD_RISK_PUBLIC_ORIGIN", "");
    expect(publicRequestOrigin("http://localhost:3000/login")).toBe("http://localhost:3000");
  });
});
