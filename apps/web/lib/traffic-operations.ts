export type TrafficCapabilityStatus =
  | "v1_supported"
  | "preview"
  | "v1_5_gated"
  | "unsupported_city"
  | "no_data";

export interface TrafficOperationCapability {
  capability_id: string;
  label: string;
  status: TrafficCapabilityStatus | string;
  enabled: boolean;
  visibility: string;
  release_stage: string;
  minimum_role: string;
  confidence_label: string;
  governance_label: string;
  reason: string;
}

export interface TrafficOperationsCapabilitiesPayload {
  api_version: string;
  contract_version: string;
  city: { city_key?: string; display_name?: string };
  production_scope: {
    status: string;
    supported_for_v1: boolean;
    reason: string;
  };
  feature_flags: {
    signal_phase_preview_enabled: boolean;
  };
  ui_policy: {
    show_operations_board: boolean;
    show_vru_panels: boolean;
    fetch_vru_summary: boolean;
    fetch_vru_corridors: boolean;
    show_signal_phase_preview: boolean;
    fetch_signal_phase_overview: boolean;
    show_signal_operator_board: boolean;
    allow_signal_write_actions: boolean;
    unsupported_message: string;
  };
  release_boundary: {
    v1_0_included: string[];
    v1_0_preview: string[];
    v1_0_excluded: string[];
    v1_5_candidates: string[];
  };
  capability_count: number;
  capabilities: TrafficOperationCapability[];
}

export function shouldFetchVru(payload: TrafficOperationsCapabilitiesPayload | null): boolean {
  return Boolean(
    payload?.ui_policy.fetch_vru_summary && payload.ui_policy.fetch_vru_corridors,
  );
}

export function shouldFetchSignalPhase(
  payload: TrafficOperationsCapabilitiesPayload | null,
): boolean {
  return Boolean(payload?.ui_policy.fetch_signal_phase_overview);
}

export function isUnsupportedOperationsCity(
  payload: TrafficOperationsCapabilitiesPayload | null,
): boolean {
  if (!payload) {
    return false;
  }
  return !payload.ui_policy.show_operations_board;
}

export function capabilityRows(
  payload: TrafficOperationsCapabilitiesPayload | null,
): string[][] {
  if (!payload) {
    return [];
  }
  return payload.capabilities.map((row) => [
    row.label,
    row.status.replace(/_/g, " "),
    row.release_stage,
    row.enabled ? "enabled" : "gated",
    row.confidence_label,
    row.governance_label,
  ]);
}

export function releaseBoundaryRows(
  payload: TrafficOperationsCapabilitiesPayload | null,
): string[][] {
  if (!payload) {
    return [];
  }
  return [
    ["v1.0 included", payload.release_boundary.v1_0_included.join("; ") || "—"],
    ["v1.0 preview", payload.release_boundary.v1_0_preview.join("; ") || "—"],
    ["v1.0 excluded", payload.release_boundary.v1_0_excluded.join("; ") || "—"],
    ["v1.5 candidates", payload.release_boundary.v1_5_candidates.join("; ") || "—"],
  ];
}
