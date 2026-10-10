import { describe, expect, it } from "vitest";

import { MOTIF_IDS, motif, motifForPath } from "./page-motion";
import { NAV_ITEMS } from "./platform-shell";

describe("page motion identity", () => {
  it("gives every navigable route its own motif", () => {
    for (const item of NAV_ITEMS) {
      const resolved = motifForPath(item.href);
      expect(MOTIF_IDS).toContain(resolved.id);
      expect(resolved.meaning.length).toBeGreaterThan(10);
    }
  });

  it("matches the most specific route prefix", () => {
    expect(motifForPath("/").id).toBe("road");
    expect(motifForPath("/workspace").id).toBe("control-room");
    expect(motifForPath("/workspace/analyst").id).toBe("scatter");
    expect(motifForPath("/workspace/system-health").id).toBe("pulse");
    // A nested route inherits its section's motif.
    expect(motifForPath("/workspace/reports/2026-01").id).toBe("report");
    expect(motifForPath("/login").id).toBe("key");
  });

  it("never returns undefined for unknown or empty paths", () => {
    expect(motifForPath("/workspace/not-a-route").id).toBe("control-room");
    expect(motifForPath("").id).toBe("road");
    expect(motifForPath(null).id).toBe("road");
  });

  it("exposes a titled, explained motif for every id", () => {
    for (const id of MOTIF_IDS) {
      const entry = motif(id);
      expect(entry.id).toBe(id);
      expect(entry.title).toBeTruthy();
      expect(entry.meaning).toBeTruthy();
    }
  });
});
