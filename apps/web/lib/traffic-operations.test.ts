import { describe, expect, test } from "vitest";

import {
  capabilityRows,
  isUnsupportedOperationsCity,
  releaseBoundaryRows,
  shouldFetchSignalPhase,
  shouldFetchVru,
  type TrafficOperationsCapabilitiesPayload,
} from "./traffic-operations";

function capabilities(
  overrides: Partial<TrafficOperationsCapabilitiesPayload> = {},
): TrafficOperationsCapabilitiesPayload {
  return {
    api_version: "v1",
    contract_version: "traffic_operations_capabilities_v1",
    city: { city_key: "bari", display_name: "Bari" },
    production_scope: {
      status: "v1_supported",
      supported_for_v1: true,
      reason: "Bari v1 scope.",
    },
    feature_flags: { signal_phase_preview_enabled: true },
    ui_policy: {
      show_operations_board: true,
      show_vru_panels: true,
      fetch_vru_summary: true,
      fetch_vru_corridors: true,
      show_signal_phase_preview: true,
      fetch_signal_phase_overview: true,
      show_signal_operator_board: true,
      allow_signal_write_actions: false,
      unsupported_message: "Bari v1 scope.",
    },
    release_boundary: {
      v1_0_included: ["Bari VRU planning highlights"],
      v1_0_preview: ["Bari signal-phase coverage evidence"],
      v1_0_excluded: ["live signal-phase dispatch send"],
      v1_5_candidates: ["multi-city operational signal-phase rollout"],
    },
    capability_count: 2,
    capabilities: [
      {
        capability_id: "vru_priority_intelligence",
        label: "VRU priority intelligence",
        status: "v1_supported",
        enabled: true,
        visibility: "visible",
        release_stage: "v1.0",
        minimum_role: "traffic_engineer",
        confidence_label: "Medium - proxy exposure",
        governance_label: "Internal municipal operations",
        reason: "Available.",
      },
      {
        capability_id: "signal_phase_operator_board",
        label: "Signal-phase operator board",
        status: "preview",
        enabled: true,
        visibility: "preview_read_only",
        release_stage: "v1.5_preview",
        minimum_role: "traffic_engineer",
        confidence_label: "Low - read-only queue",
        governance_label: "Restricted traffic-engineering preview",
        reason: "Preview only.",
      },
    ],
    ...overrides,
  };
}

describe("traffic operations capability policy", () => {
  test("bari v1 scope fetches VRU and signal preview but blocks write actions", () => {
    const payload = capabilities();

    expect(shouldFetchVru(payload)).toBe(true);
    expect(shouldFetchSignalPhase(payload)).toBe(true);
    expect(isUnsupportedOperationsCity(payload)).toBe(false);
    expect(payload.ui_policy.allow_signal_write_actions).toBe(false);
    expect(capabilityRows(payload)[1]).toContain("preview");
  });

  test("unsupported cities do not fetch operational artifacts", () => {
    const payload = capabilities({
      city: { city_key: "lecce", display_name: "Lecce" },
      production_scope: {
        status: "not_supported",
        supported_for_v1: false,
        reason: "Bari pilot only.",
      },
      ui_policy: {
        show_operations_board: false,
        show_vru_panels: false,
        fetch_vru_summary: false,
        fetch_vru_corridors: false,
        show_signal_phase_preview: false,
        fetch_signal_phase_overview: false,
        show_signal_operator_board: false,
        allow_signal_write_actions: false,
        unsupported_message: "Bari pilot only.",
      },
    });

    expect(shouldFetchVru(payload)).toBe(false);
    expect(shouldFetchSignalPhase(payload)).toBe(false);
    expect(isUnsupportedOperationsCity(payload)).toBe(true);
  });

  test("release boundary rows keep v1 and v1.5 commitments visible", () => {
    expect(releaseBoundaryRows(capabilities())).toEqual([
      ["v1.0 included", "Bari VRU planning highlights"],
      ["v1.0 preview", "Bari signal-phase coverage evidence"],
      ["v1.0 excluded", "live signal-phase dispatch send"],
      ["v1.5 candidates", "multi-city operational signal-phase rollout"],
    ]);
  });
});
