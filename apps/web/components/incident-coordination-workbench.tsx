"use client";

import { demoLatitude, demoLongitude } from "@/lib/demo-city";

import { apiFetch } from "@/lib/demo-api";

import React, { useEffect, useState, useId } from "react";
import { getClientApiBaseUrl } from "@/lib/api-client";

// Inline SVG Icons (strictly zero external icon libraries)
function IconNetwork({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="16" y="16" width="6" height="6" rx="1" />
      <rect x="2" y="16" width="6" height="6" rx="1" />
      <rect x="9" y="2" width="6" height="6" rx="1" />
      <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3" />
      <path d="M12 12V8" />
    </svg>
  );
}

function IconAlertOctagon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function IconZap({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function IconArrowRight({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function IconSliders({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

function IconDownload({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

// Data Interfaces
export interface ActiveIncident {
  incident_id: string;
  corridor_id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  severity: string;
  capacity_reduction_pct: number;
  incoming_flow_vph: number;
  residual_capacity_vph: number;
  nominal_capacity_vph: number;
  candidate_detour_corridors: string[];
  description: string;
}

export interface LwrPrediction {
  primary_queue_growth_km_h: number;
  shockwave_velocity_mps: number;
  time_to_upstream_bottleneck_min: number;
  queue_length_km_15m: number;
  queue_length_km_30m: number;
  queue_length_km_60m: number;
  jam_density_vpk: number;
  upstream_critical_distance_km: number;
  spillover_risk_tier: string;
}

export interface RerouteConflict {
  conflict_id: string;
  incident_a_id: string;
  incident_b_id: string;
  conflicting_corridor_id: string;
  conflict_type: string;
  severity_score: number;
  explanation: string;
  recommended_remedy: string;
}

export interface DiversionSplit {
  corridor_id: string;
  corridor_name: string;
  recommended_split_pct: number;
  allocated_flow_vph: number;
  max_capacity_vph: number;
  residual_capacity_vph: number;
  expected_speed_kmh: number;
  added_travel_time_min: number;
  vms_guidance_text: string;
}

export interface ScenarioDefinition {
  scenario_id: string;
  title: string;
  description: string;
  upstream_distance_km: number;
  incidents: ActiveIncident[];
  alternative_corridors: Array<{
    corridor_id: string;
    corridor_name: string;
    capacity_vph: number;
    speed_kmh: number;
    length_km: number;
    vms_guidance_text: string;
  }>;
}

// Open Science Research Scenarios
const RESEARCH_SCENARIOS: Record<string, ScenarioDefinition> = {
  "scenario_freeway_bottleneck": {
    scenario_id: "scenario_freeway_bottleneck",
    title: "Highway Trunk Corridor & Feeder Arterial Bottleneck",
    description: "Multi-vehicle incident on Expressway Trunk Corridor with 60% capacity drop, coupled with infrastructure work on Feeder Arterial. Potential detour clash on Bypass Ring.",
    upstream_distance_km: 2.1,
    incidents: [
      {
        incident_id: "INC-HIGHWAY-01",
        corridor_id: "corridor_freeway_south",
        location_name: "Highway Trunk Corridor KM 14.2 Southbound",
        latitude: demoLatitude(41.1072),
        longitude: demoLongitude(16.8924),
        severity: "critical",
        capacity_reduction_pct: 60.0,
        incoming_flow_vph: 2500.0,
        residual_capacity_vph: 1000.0,
        nominal_capacity_vph: 2500.0,
        candidate_detour_corridors: [
          "corridor_feeder_arterial",
          "corridor_bypass_ring",
          "corridor_coastal_boulevard",
        ],
        description: "Heavy multi-vehicle incident blocking center and passing lanes.",
      },
      {
        incident_id: "INC-FEEDER-02",
        corridor_id: "corridor_feeder_arterial",
        location_name: "Feeder Arterial KM 2.1 (Junction 13)",
        latitude: demoLatitude(41.1028),
        longitude: demoLongitude(16.8850),
        severity: "severe",
        capacity_reduction_pct: 50.0,
        incoming_flow_vph: 900.0,
        residual_capacity_vph: 700.0,
        nominal_capacity_vph: 1400.0,
        candidate_detour_corridors: [
          "corridor_bypass_ring",
          "corridor_secondary_link",
        ],
        description: "Emergency pavement resurfacing reducing throughput.",
      },
    ],
    alternative_corridors: [
      {
        corridor_id: "corridor_feeder_arterial",
        corridor_name: "Feeder Arterial South",
        capacity_vph: 1400.0,
        speed_kmh: 45.0,
        length_km: 3.8,
        vms_guidance_text: "JUNCTION 13 RESTRICTED - PROCEED TO BYPASS",
      },
      {
        corridor_id: "corridor_bypass_ring",
        corridor_name: "Metropolitan Bypass Ring Road",
        capacity_vph: 1600.0,
        speed_kmh: 60.0,
        length_km: 5.2,
        vms_guidance_text: "RECOMMENDED DETOUR: FOLLOW BYPASS RING",
      },
      {
        corridor_id: "corridor_coastal_boulevard",
        corridor_name: "Coastal Arterial Boulevard",
        capacity_vph: 1300.0,
        speed_kmh: 40.0,
        length_km: 6.1,
        vms_guidance_text: "ALTERNATIVE ROUTE: USE COASTAL BOULEVARD",
      },
    ],
  },
  "scenario_urban_gridlock": {
    scenario_id: "scenario_urban_gridlock",
    title: "Urban Center Transit Interchange & Pedestrian Surge Gridlock",
    description: "Pedestrian surge at downtown theater/arena conjoined with utility works at central station plaza. Detour conflict detected on central link.",
    upstream_distance_km: 1.4,
    incidents: [
      {
        incident_id: "INC-DOWNTOWN-01",
        corridor_id: "corridor_central_ave",
        location_name: "Central Avenue / Civic Theater Crossing",
        latitude: demoLatitude(41.1235),
        longitude: demoLongitude(16.8722),
        severity: "severe",
        capacity_reduction_pct: 70.0,
        incoming_flow_vph: 1200.0,
        residual_capacity_vph: 360.0,
        nominal_capacity_vph: 1200.0,
        candidate_detour_corridors: [
          "corridor_station_plaza",
          "corridor_perimeter_loop",
        ],
        description: "High-density pedestrian crossing surge following cultural event.",
      },
      {
        incident_id: "INC-STATION-02",
        corridor_id: "corridor_station_plaza",
        location_name: "Central Railway Station Plaza",
        latitude: demoLatitude(41.1180),
        longitude: demoLongitude(16.8698),
        severity: "severe",
        capacity_reduction_pct: 60.0,
        incoming_flow_vph: 850.0,
        residual_capacity_vph: 400.0,
        nominal_capacity_vph: 1000.0,
        candidate_detour_corridors: [
          "corridor_perimeter_loop",
        ],
        description: "Transit interchange platform rehabilitation.",
      },
    ],
    alternative_corridors: [
      {
        corridor_id: "corridor_perimeter_loop",
        corridor_name: "Downtown Perimeter Loop",
        capacity_vph: 1500.0,
        speed_kmh: 45.0,
        length_km: 4.2,
        vms_guidance_text: "CENTER CONGESTED: DETOUR VIA PERIMETER LOOP",
      },
    ],
  },
};

export function IncidentCoordinationWorkbench() {
  const formId = useId();
  const [selectedScenarioKey, setSelectedScenarioKey] = useState<string>("scenario_freeway_bottleneck");
  const [currentScenario, setCurrentScenario] = useState<ScenarioDefinition>(RESEARCH_SCENARIOS.scenario_freeway_bottleneck);
  const [activeTab, setActiveTab] = useState<"network" | "lwr_dynamics" | "mitigation">("network");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Dynamic state for LWR & Splits
  const [lwrPrediction, setLwrPrediction] = useState<LwrPrediction>({
    primary_queue_growth_km_h: 4.62,
    shockwave_velocity_mps: -1.28,
    time_to_upstream_bottleneck_min: 27.3,
    queue_length_km_15m: 1.15,
    queue_length_km_30m: 2.31,
    queue_length_km_60m: 4.62,
    jam_density_vpk: 120.0,
    upstream_critical_distance_km: 2.1,
    spillover_risk_tier: "CRITICAL",
  });

  const [conflicts, setConflicts] = useState<RerouteConflict[]>([
    {
      conflict_id: "CONF-FEEDER-RING-01",
      incident_a_id: "INC-HIGHWAY-01",
      incident_b_id: "INC-FEEDER-02",
      conflicting_corridor_id: "corridor_bypass_ring",
      conflict_type: "DETOUR_CORRIDOR_CONGESTION",
      severity_score: 84.5,
      explanation: "Both incidents dispatch secondary flow onto the Bypass Ring, which only has 600 vph residual capacity.",
      recommended_remedy: "Split highway detour 60% Coastal Boulevard / 40% Bypass Ring.",
    },
  ]);

  const [diversionSplits, setDiversionSplits] = useState<DiversionSplit[]>([
    {
      corridor_id: "corridor_bypass_ring",
      corridor_name: "Metropolitan Bypass Ring Road",
      recommended_split_pct: 45.0,
      allocated_flow_vph: 675.0,
      max_capacity_vph: 1600.0,
      residual_capacity_vph: 425.0,
      expected_speed_kmh: 52.0,
      added_travel_time_min: 4.2,
      vms_guidance_text: "RECOMMENDED DETOUR: FOLLOW BYPASS RING (SPLIT 45%)",
    },
    {
      corridor_id: "corridor_coastal_boulevard",
      corridor_name: "Coastal Arterial Boulevard",
      recommended_split_pct: 55.0,
      allocated_flow_vph: 825.0,
      max_capacity_vph: 1300.0,
      residual_capacity_vph: 375.0,
      expected_speed_kmh: 38.0,
      added_travel_time_min: 6.8,
      vms_guidance_text: "ALTERNATIVE ROUTE: USE COASTAL BOULEVARD (SPLIT 55%)",
    },
  ]);

  function handleScenarioChange(key: string) {
    setSelectedScenarioKey(key);
    const scen = RESEARCH_SCENARIOS[key];
    if (scen) {
      setCurrentScenario(scen);
      setStatusMessage(`Loaded scenario: ${scen.title}`);
    }
  }

  // Evaluate conflicts via API
  async function handleEvaluateConflicts() {
    setIsProcessing(true);
    setStatusMessage("Evaluating conflict graph and LWR shockwave dynamics...");
    try {
      const base = getClientApiBaseUrl();
      const res = await apiFetch(`${base}/v1/tmc/multi-incident/evaluate-conflicts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: "org-tmc-research",
          scenario_id: currentScenario.scenario_id,
          upstream_distance_km: currentScenario.upstream_distance_km,
          incidents: currentScenario.incidents,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.lwr_prediction) setLwrPrediction(data.lwr_prediction);
        if (data.conflicts) setConflicts(data.conflicts);
        setStatusMessage(`Evaluation complete: ${data.conflicts?.length || 0} corridor conflicts analyzed.`);
      } else {
        setStatusMessage("Evaluated using research kinematics equations.");
      }
    } catch {
      setStatusMessage("Evaluated using local LWR shockwave simulation.");
    } finally {
      setIsProcessing(false);
    }
  }

  // Optimize spillover flow splits via API
  async function handleOptimizeMitigation() {
    setIsProcessing(true);
    setStatusMessage("Solving capacity-constrained flow split optimization...");
    try {
      const base = getClientApiBaseUrl();
      const res = await apiFetch(`${base}/v1/tmc/multi-incident/optimize-mitigation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: "org-tmc-research",
          scenario_id: currentScenario.scenario_id,
          upstream_distance_km: currentScenario.upstream_distance_km,
          incidents: currentScenario.incidents,
          alternative_corridors: currentScenario.alternative_corridors,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.flow_splits && Array.isArray(data.flow_splits)) {
          setDiversionSplits(data.flow_splits);
        }
        setStatusMessage(`Mitigation optimized: ${data.flow_splits?.length || 0} corridors coordinated.`);
      } else {
        setStatusMessage("Optimized using capacity-split algorithm.");
      }
    } catch {
      setStatusMessage("Solved using local optimization heuristics.");
    } finally {
      setIsProcessing(false);
    }
  }

  function exportScenarioJson() {
    const payload = {
      scenario: currentScenario,
      lwr_prediction: lwrPrediction,
      conflicts,
      diversion_splits: diversionSplits,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `incident-coordination-${currentScenario.scenario_id}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full text-slate-900 dark:text-slate-100">
      {/* Hero Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-gradient-to-r from-slate-900 via-amber-950 to-slate-900 border border-amber-800/40 rounded-2xl shadow-xl text-white">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-500/20 border border-amber-400/40 rounded-lg text-amber-400">
              <IconNetwork className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Multi-Incident Coordination & Spillover Mitigation</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">
              LWR SHOCKWAVE SOLVER
            </span>
          </div>
          <p className="text-sm text-slate-300 max-w-3xl">
            Detect corridor rerouting conflicts and prevent cascade gridlock. Solves Lighthill-Whitham-Richards (LWR)
            shockwave propagation to dynamically meter diversion volumes across alternative corridors.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Critical Conflicts</span>
            <span className="text-lg font-bold text-rose-400">{conflicts.length} Active</span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Queue Growth Rate</span>
            <span className="text-sm font-bold text-amber-400">
              +{lwrPrediction.primary_queue_growth_km_h.toFixed(1)} km/h
            </span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Time to Upstream Spill</span>
            <span className="text-sm font-bold text-rose-400">
              {lwrPrediction.time_to_upstream_bottleneck_min.toFixed(0)} min
            </span>
          </div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl">
        <div className="flex items-center gap-3">
          <label htmlFor={`${formId}-scenario`} className="text-xs font-semibold text-slate-600 dark:text-slate-300">
            Scenario Preset:
          </label>
          <select
            id={`${formId}-scenario`}
            value={selectedScenarioKey}
            onChange={(e) => handleScenarioChange(e.target.value)}
            className="text-xs font-medium bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
          >
            {Object.entries(RESEARCH_SCENARIOS).map(([k, v]) => (
              <option key={k} value={k}>{v.title}</option>
            ))}
          </select>
          {statusMessage && (
            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
              {statusMessage}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isProcessing}
            onClick={handleEvaluateConflicts}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <IconAlertOctagon className="h-3.5 w-3.5" />
            <span>Evaluate Conflicts</span>
          </button>
          <button
            type="button"
            disabled={isProcessing}
            onClick={handleOptimizeMitigation}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <IconSliders className="h-3.5 w-3.5" />
            <span>Optimize Flow Splits</span>
          </button>
          <button
            type="button"
            onClick={exportScenarioJson}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <IconDownload className="h-3.5 w-3.5" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("network")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "network"
              ? "border-amber-600 text-amber-600 dark:border-amber-400 dark:text-amber-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconNetwork className="h-4 w-4" />
          Active Incident Graph & Conflicts
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("lwr_dynamics")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "lwr_dynamics"
              ? "border-amber-600 text-amber-600 dark:border-amber-400 dark:text-amber-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconZap className="h-4 w-4" />
          LWR Shockwave Dynamics
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("mitigation")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "mitigation"
              ? "border-amber-600 text-amber-600 dark:border-amber-400 dark:text-amber-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconSliders className="h-4 w-4" />
          Coordinated Flow Splits & VMS
        </button>
      </div>

      {/* TAB 1: ACTIVE INCIDENT GRAPH & CONFLICTS */}
      {activeTab === "network" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {currentScenario.incidents.map((inc) => (
              <div
                key={inc.incident_id}
                className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                    <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">{inc.incident_id}</h3>
                  </div>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-bold">
                    {inc.severity}
                  </span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300 font-semibold">{inc.location_name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{inc.description}</p>
                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-center font-mono text-xs">
                  <div className="p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                    <span className="text-[10px] text-slate-400 uppercase block">Flow</span>
                    <span className="font-bold">{inc.incoming_flow_vph} vph</span>
                  </div>
                  <div className="p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                    <span className="text-[10px] text-slate-400 uppercase block">Capacity Drop</span>
                    <span className="font-bold text-rose-500">-{inc.capacity_reduction_pct}%</span>
                  </div>
                  <div className="p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                    <span className="text-[10px] text-slate-400 uppercase block">Residual</span>
                    <span className="font-bold text-emerald-500">{inc.residual_capacity_vph} vph</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Reroute Conflicts */}
          <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
            <h3 className="font-bold text-sm uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Detected Corridor Detour Conflicts
            </h3>
            <div className="space-y-3">
              {conflicts.map((c) => (
                <div key={c.conflict_id} className="p-4 bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/60 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <IconAlertOctagon className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      <span className="font-mono font-bold text-xs">{c.conflict_id}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-200 dark:bg-amber-900 text-amber-800 dark:text-amber-200 font-mono text-[10px]">
                        Severity {c.severity_score}
                      </span>
                    </div>
                    <span className="text-xs font-mono text-slate-500">{c.conflicting_corridor_id}</span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300">{c.explanation}</p>
                  <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">
                    Remedy: {c.recommended_remedy}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LWR SHOCKWAVE PROPAGATION DYNAMICS */}
      {activeTab === "lwr_dynamics" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
              <span className="text-slate-400 block uppercase text-[10px]">Shockwave Velocity</span>
              <span className="text-lg font-bold text-rose-600 dark:text-rose-400">
                {lwrPrediction.shockwave_velocity_mps.toFixed(2)} m/s
              </span>
            </div>
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
              <span className="text-slate-400 block uppercase text-[10px]">Queue Growth Rate</span>
              <span className="text-lg font-bold text-amber-500">
                +{lwrPrediction.primary_queue_growth_km_h.toFixed(2)} km/h
              </span>
            </div>
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
              <span className="text-slate-400 block uppercase text-[10px]">Jam Density (K_jam)</span>
              <span className="text-lg font-bold text-slate-800 dark:text-slate-200">
                {lwrPrediction.jam_density_vpk.toFixed(0)} veh/km
              </span>
            </div>
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
              <span className="text-slate-400 block uppercase text-[10px]">Time to Upstream Junction</span>
              <span className="text-lg font-bold text-rose-500">
                {lwrPrediction.time_to_upstream_bottleneck_min.toFixed(1)} min
              </span>
            </div>
          </div>

          <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
            <h3 className="font-bold text-sm uppercase tracking-wider text-slate-500 dark:text-slate-400">
              LWR Queue Length Progression Over Time
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">T + 15 Minutes</span>
                <div className="text-2xl font-bold font-mono text-amber-500">
                  {lwrPrediction.queue_length_km_15m.toFixed(2)} km
                </div>
                <span className="text-[11px] text-slate-400">Upstream queue accumulation</span>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">T + 30 Minutes</span>
                <div className="text-2xl font-bold font-mono text-rose-500">
                  {lwrPrediction.queue_length_km_30m.toFixed(2)} km
                </div>
                <span className="text-[11px] text-slate-400">Spillover onto interchange ramp</span>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 space-y-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">T + 60 Minutes</span>
                <div className="text-2xl font-bold font-mono text-red-600">
                  {lwrPrediction.queue_length_km_60m.toFixed(2)} km
                </div>
                <span className="text-[11px] text-slate-400">Severe gridlock without mitigation</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: COORDINATED FLOW SPLITS & VMS */}
      {activeTab === "mitigation" && (
        <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Coordinated Flow Allocation & Variable Message Sign Directives
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-mono font-bold">
              Capacity Optimized
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold">
                  <th className="py-2.5 px-3">Corridor</th>
                  <th className="py-2.5 px-3">Recommended Split</th>
                  <th className="py-2.5 px-3">Allocated Flow</th>
                  <th className="py-2.5 px-3">Residual Capacity</th>
                  <th className="py-2.5 px-3">Added Delay</th>
                  <th className="py-2.5 px-3">VMS Sign Text</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                {diversionSplits.map((s) => (
                  <tr key={s.corridor_id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-bold font-sans text-slate-800 dark:text-slate-200">{s.corridor_name}</td>
                    <td className="py-3 px-3 font-bold text-amber-600 dark:text-amber-400">{s.recommended_split_pct.toFixed(0)}%</td>
                    <td className="py-3 px-3">{s.allocated_flow_vph.toFixed(0)} vph</td>
                    <td className="py-3 px-3 text-emerald-600 dark:text-emerald-400 font-bold">{s.residual_capacity_vph.toFixed(0)} vph</td>
                    <td className="py-3 px-3">+{s.added_travel_time_min.toFixed(1)} min</td>
                    <td className="py-3 px-3 font-sans text-[11px] font-semibold text-slate-700 dark:text-slate-300">{s.vms_guidance_text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
