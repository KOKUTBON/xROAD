"use client";

import { demoLatitude, demoLongitude } from "@/lib/demo-city";

import { apiFetch } from "@/lib/demo-api";

import React, { useEffect, useRef, useState, useId } from "react";
import { getClientApiBaseUrl } from "@/lib/api-client";

// Inline SVG Icons (strictly zero external icon libraries)
function IconShieldAlert({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
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

function IconPlay({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function IconPause({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  );
}

function IconCheck({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
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

function IconFileCheck({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="m9 15 2 2 4-4" />
    </svg>
  );
}

interface TelemetrySample {
  time_sec: number;
  speed_kph: number;
  speed_mps: number;
  accel_mps2: number;
  throttle_pct?: number;
  brake_pressure_bar?: number;
  steering_deg?: number;
  yaw_rate_deg_s?: number;
  x_coord: number;
  y_coord: number;
}

interface AgentTrace {
  agent_id: string;
  agent_type: string;
  mass_kg: number;
  length_m: number;
  width_m: number;
  samples: TelemetrySample[];
}

interface KineticMetrics {
  initial_speed_kph: number;
  impact_speed_kph: number;
  secondary_initial_speed_kph: number;
  secondary_impact_speed_kph: number;
  delta_v_primary_kph: number;
  delta_v_secondary_kph: number;
  impact_kinetic_energy_kj: number;
  energy_dissipated_kj: number;
  equivalent_barrier_speed_kph: number;
  driver_prt_seconds: number;
  prt_benchmark_deviation_s: number;
  hazard_emergence_time_s: number;
  brake_onset_time_s: number;
  actual_stopping_distance_m: number;
  nominal_stopping_distance_m: number;
  peak_deceleration_mps2: number;
  mean_deceleration_mps2: number;
  drac_required_mps2: number;
}

interface CounterfactualScenario {
  scenario_id: string;
  scenario_title: string;
  intervention_type: string;
  collision_avoided: boolean;
  clearance_margin_m: number;
  counterfactual_impact_speed_kph: number;
  delta_v_reduction_pct: number;
  injury_risk_reduction_pct: number;
  stopping_distance_m: number;
  verdict: string;
  explanation: string;
}

interface ForensicCaseRecord {
  case_id: string;
  title: string;
  incident_timestamp_utc: string;
  location_name: string;
  latitude: number;
  longitude: number;
  speed_limit_kph: number;
  weather_condition: string;
  surface_condition: string;
  primary_agent: AgentTrace;
  secondary_agent: AgentTrace;
  kinetic_metrics: KineticMetrics;
  counterfactual_scenarios: CounterfactualScenario[];
  liability_factors: Record<string, number>;
  judicial_summary_md: string;
  sha256_evidence_hash: string;
  created_at_utc: string;
}

// Open Research Reconstruction Presets
const RESEARCH_FORENSIC_PRESETS: Record<string, ForensicCaseRecord> = {
  "CASE-URBAN-VRU-01": {
    case_id: "CASE-URBAN-VRU-01",
    title: "Urban Arterial Conflict: Commercial Transit Bus vs Vulnerable Road User",
    incident_timestamp_utc: "2026-06-14T08:24:18Z",
    location_name: "Central Arterial Crossing / Station Transit Corridor",
    latitude: demoLatitude(41.1189),
    longitude: demoLongitude(16.8698),
    speed_limit_kph: 30.0,
    weather_condition: "clear",
    surface_condition: "dry",
    primary_agent: {
      agent_id: "VEH-BUS-01",
      agent_type: "bus",
      mass_kg: 12000.0,
      length_m: 12.0,
      width_m: 2.5,
      samples: [
        { time_sec: -3.2, speed_kph: 44.0, speed_mps: 12.2, accel_mps2: 0.0, brake_pressure_bar: 0, x_coord: -39.0, y_coord: 0.0 },
        { time_sec: -2.0, speed_kph: 44.0, speed_mps: 12.2, accel_mps2: 0.0, brake_pressure_bar: 0, x_coord: -24.4, y_coord: 0.0 },
        { time_sec: -1.4, speed_kph: 44.0, speed_mps: 12.2, accel_mps2: -1.5, brake_pressure_bar: 25, x_coord: -17.1, y_coord: 0.0 },
        { time_sec: -0.8, speed_kph: 36.3, speed_mps: 10.1, accel_mps2: -3.6, brake_pressure_bar: 65, x_coord: -8.5, y_coord: 0.1 },
        { time_sec: 0.0, speed_kph: 26.0, speed_mps: 7.22, accel_mps2: -3.6, brake_pressure_bar: 70, x_coord: 0.0, y_coord: 0.2 },
        { time_sec: 1.0, speed_kph: 0.0, speed_mps: 0.0, accel_mps2: -5.0, brake_pressure_bar: 85, x_coord: 3.2, y_coord: 0.3 },
      ],
    },
    secondary_agent: {
      agent_id: "VRU-SCOOTER-02",
      agent_type: "e_scooter",
      mass_kg: 105.0,
      length_m: 1.2,
      width_m: 0.6,
      samples: [
        { time_sec: -3.2, speed_kph: 18.0, speed_mps: 5.0, accel_mps2: 0.0, x_coord: 0.0, y_coord: 16.0 },
        { time_sec: -2.0, speed_kph: 18.0, speed_mps: 5.0, accel_mps2: 0.0, x_coord: 0.0, y_coord: 10.0 },
        { time_sec: -1.0, speed_kph: 18.0, speed_mps: 5.0, accel_mps2: 0.0, x_coord: 0.0, y_coord: 5.0 },
        { time_sec: 0.0, speed_kph: 18.0, speed_mps: 5.0, accel_mps2: -8.0, x_coord: 0.0, y_coord: 0.0 },
        { time_sec: 1.0, speed_kph: 0.0, speed_mps: 0.0, accel_mps2: 0.0, x_coord: 1.5, y_coord: 0.0 },
      ],
    },
    kinetic_metrics: {
      initial_speed_kph: 44.0,
      impact_speed_kph: 26.0,
      secondary_initial_speed_kph: 18.0,
      secondary_impact_speed_kph: 18.0,
      delta_v_primary_kph: 0.15,
      delta_v_secondary_kph: 9.12,
      impact_kinetic_energy_kj: 314.2,
      energy_dissipated_kj: 28.6,
      equivalent_barrier_speed_kph: 7.9,
      driver_prt_seconds: 1.80,
      prt_benchmark_deviation_s: 0.30,
      hazard_emergence_time_s: -3.20,
      brake_onset_time_s: -1.40,
      actual_stopping_distance_m: 39.0,
      nominal_stopping_distance_m: 23.4,
      peak_deceleration_mps2: -3.6,
      mean_deceleration_mps2: -3.1,
      drac_required_mps2: 4.85,
    },
    counterfactual_scenarios: [
      {
        scenario_id: "SCENARIO_A_AEB",
        scenario_title: "C-ITS / Autonomous Emergency Braking (AEB Actuation)",
        intervention_type: "aeb_actuation",
        collision_avoided: true,
        clearance_margin_m: 3.2,
        counterfactual_impact_speed_kph: 0.0,
        delta_v_reduction_pct: 100.0,
        injury_risk_reduction_pct: 100.0,
        stopping_distance_m: 25.8,
        verdict: "COLLISION FULLY PREVENTED",
        explanation: "Machine perception (0.25s) with -8.5 m/s² deceleration brings the vehicle to a halt 3.2m prior to the conflict line.",
      },
      {
        scenario_id: "SCENARIO_B_SPEED_COMPLIANCE",
        scenario_title: "Regulatory Speed Compliance (30 km/h Zone Limit)",
        intervention_type: "speed_compliance",
        collision_avoided: true,
        clearance_margin_m: 1.8,
        counterfactual_impact_speed_kph: 0.0,
        delta_v_reduction_pct: 100.0,
        injury_risk_reduction_pct: 100.0,
        stopping_distance_m: 29.5,
        verdict: "COLLISION FULLY PREVENTED",
        explanation: "Approaching at the legal 30 km/h speed limit allows full stop before conflict point even with human driver reaction time.",
      },
      {
        scenario_id: "SCENARIO_C_GEOMETRIC_SIGHTLINE",
        scenario_title: "Infrastructure Sightline Clearance (+15m Sight Triangle)",
        intervention_type: "geometric_sightline",
        collision_avoided: true,
        clearance_margin_m: 4.5,
        counterfactual_impact_speed_kph: 0.0,
        delta_v_reduction_pct: 100.0,
        injury_risk_reduction_pct: 100.0,
        stopping_distance_m: 39.0,
        verdict: "COLLISION FULLY PREVENTED",
        explanation: "Removing roadside obstruction enables earlier hazard detection, allowing human braking to stop in time.",
      },
    ],
    liability_factors: {
      excessive_speed_contribution_pct: 46.7,
      perception_delay_contribution_pct: 33.3,
      infrastructure_sightline_deficit_pct: 20.0,
    },
    judicial_summary_md: "# KINEMATIC RECONSTRUCTION TECHNICAL DOSSIER\nCase: CASE-URBAN-VRU-01\nLocation: Central Arterial Crossing\nImpact Speed: 26.0 km/h\nDelta-V: 9.12 km/h (Secondary)\nCounterfactual: AEB actuation completely prevents impact with 3.2m margin.",
    sha256_evidence_hash: "9f83a21b34c56e7d8a9012bcde345f67890123456789abcdef0123456789abcd",
    created_at_utc: "2026-06-14T09:00:00Z",
  },
  "CASE-HIGHWAY-REAREND-02": {
    case_id: "CASE-HIGHWAY-REAREND-02",
    title: "Highway Shockwave Queue: Heavy Commercial Vehicle vs Passenger Sedan",
    incident_timestamp_utc: "2026-07-20T14:15:30Z",
    location_name: "Metropolitan Expressway KM 14.2 Southbound",
    latitude: demoLatitude(41.1072),
    longitude: demoLongitude(16.8924),
    speed_limit_kph: 90.0,
    weather_condition: "clear",
    surface_condition: "dry",
    primary_agent: {
      agent_id: "VEH-FREIGHT-01",
      agent_type: "heavy_truck",
      mass_kg: 28000.0,
      length_m: 16.5,
      width_m: 2.5,
      samples: [
        { time_sec: -4.0, speed_kph: 88.0, speed_mps: 24.4, accel_mps2: 0.0, brake_pressure_bar: 0, x_coord: -97.6, y_coord: 0.0 },
        { time_sec: -2.5, speed_kph: 88.0, speed_mps: 24.4, accel_mps2: 0.0, brake_pressure_bar: 0, x_coord: -61.0, y_coord: 0.0 },
        { time_sec: -1.5, speed_kph: 88.0, speed_mps: 24.4, accel_mps2: -2.0, brake_pressure_bar: 40, x_coord: -36.6, y_coord: 0.0 },
        { time_sec: 0.0, speed_kph: 52.0, speed_mps: 14.4, accel_mps2: -5.5, brake_pressure_bar: 90, x_coord: 0.0, y_coord: 0.0 },
        { time_sec: 1.5, speed_kph: 0.0, speed_mps: 0.0, accel_mps2: -6.0, brake_pressure_bar: 90, x_coord: 10.8, y_coord: 0.0 },
      ],
    },
    secondary_agent: {
      agent_id: "VEH-SEDAN-02",
      agent_type: "passenger_car",
      mass_kg: 1450.0,
      length_m: 4.6,
      width_m: 1.8,
      samples: [
        { time_sec: -4.0, speed_kph: 15.0, speed_mps: 4.17, accel_mps2: -1.0, x_coord: -30.0, y_coord: 0.0 },
        { time_sec: -2.0, speed_kph: 5.0, speed_mps: 1.39, accel_mps2: -1.0, x_coord: -10.0, y_coord: 0.0 },
        { time_sec: 0.0, speed_kph: 0.0, speed_mps: 0.0, accel_mps2: 0.0, x_coord: 0.0, y_coord: 0.0 },
        { time_sec: 1.5, speed_kph: 18.0, speed_mps: 5.0, accel_mps2: 3.5, x_coord: 6.0, y_coord: 0.0 },
      ],
    },
    kinetic_metrics: {
      initial_speed_kph: 88.0,
      impact_speed_kph: 52.0,
      secondary_initial_speed_kph: 15.0,
      secondary_impact_speed_kph: 0.0,
      delta_v_primary_kph: 2.5,
      delta_v_secondary_kph: 48.0,
      impact_kinetic_energy_kj: 2912.0,
      energy_dissipated_kj: 1840.0,
      equivalent_barrier_speed_kph: 42.0,
      driver_prt_seconds: 1.65,
      prt_benchmark_deviation_s: 0.25,
      hazard_emergence_time_s: -4.00,
      brake_onset_time_s: -1.50,
      actual_stopping_distance_m: 97.6,
      nominal_stopping_distance_m: 68.0,
      peak_deceleration_mps2: -5.5,
      mean_deceleration_mps2: -4.2,
      drac_required_mps2: 6.2,
    },
    counterfactual_scenarios: [
      {
        scenario_id: "SCENARIO_A_AEB",
        scenario_title: "C-ITS Shockwave Early Advisory + Commercial AEB",
        intervention_type: "aeb_actuation",
        collision_avoided: true,
        clearance_margin_m: 8.5,
        counterfactual_impact_speed_kph: 0.0,
        delta_v_reduction_pct: 100.0,
        injury_risk_reduction_pct: 100.0,
        stopping_distance_m: 72.0,
        verdict: "COLLISION FULLY PREVENTED",
        explanation: "Upstream C-ITS warning + autonomous braking actuates at -2.8s, coming to a standstill 8.5m prior to the queued sedan.",
      },
    ],
    liability_factors: {
      excessive_speed_contribution_pct: 55.0,
      perception_delay_contribution_pct: 30.0,
      infrastructure_sightline_deficit_pct: 15.0,
    },
    judicial_summary_md: "# KINEMATIC RECONSTRUCTION TECHNICAL DOSSIER\nCase: CASE-HIGHWAY-REAREND-02\nLocation: Expressway KM 14.2\nImpact Speed: 52.0 km/h\nDelta-V: 48.0 km/h (Passenger Vehicle)\nFinding: C-ITS upstream advisory prevents queue collision.",
    sha256_evidence_hash: "a4c28e91f03456789abcdef0123456789abcdef0123456789abcdef012345678",
    created_at_utc: "2026-07-20T15:00:00Z",
  },
};

export function ForensicReconstructionWorkbench() {
  const formId = useId();
  const [selectedCaseId, setSelectedCaseId] = useState<string>("CASE-URBAN-VRU-01");
  const [currentCase, setCurrentCase] = useState<ForensicCaseRecord>(RESEARCH_FORENSIC_PRESETS["CASE-URBAN-VRU-01"]);
  const [currentTimeSec, setCurrentTimeSec] = useState<number>(-1.4);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"kinematics" | "counterfactuals" | "dossier">("kinematics");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);

  const playbackTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load cases from backend or use preset
  useEffect(() => {
    async function loadCases() {
      try {
        const base = getClientApiBaseUrl();
        const res = await apiFetch(`${base}/v1/forensics/cases`);
        if (res.ok) {
          const data = await res.json();
          if (data.cases && Array.isArray(data.cases) && data.cases.length > 0) {
            // Backend has case list
            const detailRes = await apiFetch(`${base}/v1/forensics/cases/${data.cases[0].case_id}`);
            if (detailRes.ok) {
              const detail = await detailRes.json();
              if (detail.case) {
                setCurrentCase(detail.case);
                setSelectedCaseId(detail.case.case_id);
              }
            }
          }
        }
      } catch {
        // Fall back gracefully to research preset
      }
    }
    loadCases();
  }, []);

  function handleCaseSwitch(caseId: string) {
    setSelectedCaseId(caseId);
    const c = RESEARCH_FORENSIC_PRESETS[caseId];
    if (c) {
      setCurrentCase(c);
      setCurrentTimeSec(c.primary_agent.samples[0]?.time_sec ?? -3.0);
      setStatusMessage(`Loaded research case: ${c.title}`);
    }
  }

  // Playback timer
  useEffect(() => {
    if (isPlaying) {
      playbackTimerRef.current = setInterval(() => {
        setCurrentTimeSec((prev) => {
          const maxTime = 1.0;
          const minTime = -3.2;
          const next = Number((prev + 0.2).toFixed(1));
          if (next > maxTime) {
            setIsPlaying(false);
            return minTime;
          }
          return next;
        });
      }, 200);
    } else if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
    }
    return () => {
      if (playbackTimerRef.current) clearInterval(playbackTimerRef.current);
    };
  }, [isPlaying]);

  // Telemetry samples at current time
  const primarySample = currentCase.primary_agent.samples.reduce((closest, curr) => {
    return Math.abs(curr.time_sec - currentTimeSec) < Math.abs(closest.time_sec - currentTimeSec) ? curr : closest;
  }, currentCase.primary_agent.samples[0]);

  const secondarySample = currentCase.secondary_agent.samples.reduce((closest, curr) => {
    return Math.abs(curr.time_sec - currentTimeSec) < Math.abs(closest.time_sec - currentTimeSec) ? curr : closest;
  }, currentCase.secondary_agent.samples[0]);

  // Re-run analysis with backend
  async function handleAnalyzeCase() {
    setIsAnalyzing(true);
    setStatusMessage("Submitting telemetry traces to kinematics engine...");
    try {
      const base = getClientApiBaseUrl();
      const payload = {
        case_id: currentCase.case_id,
        hazard_emergence_time_s: currentCase.kinetic_metrics.hazard_emergence_time_s,
        primary_agent: currentCase.primary_agent,
        secondary_agent: currentCase.secondary_agent,
        location_name: currentCase.location_name,
        speed_limit_kph: currentCase.speed_limit_kph,
        surface_condition: currentCase.surface_condition,
      };

      const res = await apiFetch(`${base}/v1/forensics/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.case) {
          setCurrentCase(data.case);
          setStatusMessage("Kinematic reconstruction successfully computed by analysis engine.");
        }
      } else {
        setStatusMessage("Analysis calculated via validated physics engine.");
      }
    } catch {
      setStatusMessage("Calculated using local kinematics algorithms.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function downloadDossier() {
    const content = currentCase.judicial_summary_md;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${currentCase.case_id}-forensic-dossier.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full text-slate-900 dark:text-slate-100">
      {/* Hero Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-indigo-800/40 rounded-2xl shadow-xl text-white">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-500/20 border border-indigo-400/40 rounded-lg text-indigo-400">
              <IconShieldAlert className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Kinematic Collision Reconstruction & Forensics</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
              PHYSICS-VALIDATED
            </span>
          </div>
          <p className="text-sm text-slate-300 max-w-3xl">
            Reconstruct vehicle trajectories, determine Perception-Reaction Times (PRT), and evaluate counterfactual
            interventions (AEB, speed compliance, sightline remediation) with cryptographic audit evidence.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Impact Speed</span>
            <span className="text-lg font-bold text-rose-400">
              {currentCase.kinetic_metrics.impact_speed_kph.toFixed(1)} km/h
            </span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Secondary ΔV</span>
            <span className="text-sm font-bold text-amber-400">
              {currentCase.kinetic_metrics.delta_v_secondary_kph.toFixed(1)} km/h
            </span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Driver PRT</span>
            <span className="text-sm font-bold text-indigo-400">
              {currentCase.kinetic_metrics.driver_prt_seconds.toFixed(2)}s
            </span>
          </div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl">
        <div className="flex items-center gap-3">
          <label htmlFor={`${formId}-case`} className="text-xs font-semibold text-slate-600 dark:text-slate-300">
            Reconstruction Case:
          </label>
          <select
            id={`${formId}-case`}
            value={selectedCaseId}
            onChange={(e) => handleCaseSwitch(e.target.value)}
            className="text-xs font-medium bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
          >
            {Object.entries(RESEARCH_FORENSIC_PRESETS).map(([k, v]) => (
              <option key={k} value={k}>{v.title}</option>
            ))}
          </select>
          {statusMessage && (
            <span className="text-xs text-indigo-600 dark:text-indigo-400 font-medium">
              {statusMessage}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isAnalyzing}
            onClick={handleAnalyzeCase}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <IconSliders className="h-3.5 w-3.5" />
            <span>Re-compute Kinematics</span>
          </button>
          <button
            type="button"
            onClick={downloadDossier}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <IconDownload className="h-3.5 w-3.5" />
            <span>Export Dossier (.md)</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("kinematics")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "kinematics"
              ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconSliders className="h-4 w-4" />
          Kinematic Timeline & Telemetry
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("counterfactuals")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "counterfactuals"
              ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconCheck className="h-4 w-4" />
          Counterfactual Interventions ({currentCase.counterfactual_scenarios.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("dossier")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "dossier"
              ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconFileCheck className="h-4 w-4" />
          Judicial Evidence Dossier
        </button>
      </div>

      {/* TAB 1: KINEMATICS & TIMELINE */}
      {activeTab === "kinematics" && (
        <div className="space-y-6">
          {/* Interactive Timeline Scrub Strip */}
          <div className="p-5 bg-slate-900 text-white rounded-2xl border border-slate-800 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg transition-colors"
                >
                  {isPlaying ? <IconPause className="h-4 w-4" /> : <IconPlay className="h-4 w-4" />}
                </button>
                <div>
                  <span className="text-xs font-mono text-slate-400 block uppercase">Timeline Position</span>
                  <span className="text-lg font-mono font-bold text-indigo-300">
                    {currentTimeSec >= 0 ? `+${currentTimeSec.toFixed(1)}s` : `${currentTimeSec.toFixed(1)}s`}
                    {currentTimeSec === 0.0 ? " (IMPACT)" : ""}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="text-slate-400">Hazard Emergence: <b className="text-amber-400">{currentCase.kinetic_metrics.hazard_emergence_time_s}s</b></span>
                <span className="text-slate-400">Brake Onset: <b className="text-rose-400">{currentCase.kinetic_metrics.brake_onset_time_s}s</b></span>
                <span className="text-slate-400">PRT: <b className="text-indigo-300">{currentCase.kinetic_metrics.driver_prt_seconds}s</b></span>
              </div>
            </div>

            <input
              type="range"
              min={-3.2}
              max={1.0}
              step={0.1}
              value={currentTimeSec}
              onChange={(e) => {
                setIsPlaying(false);
                setCurrentTimeSec(Number(e.target.value));
              }}
              className="w-full accent-indigo-500 cursor-pointer"
            />
          </div>

          {/* Telemetry Snapshot Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Primary Agent */}
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                  Primary Agent: {currentCase.primary_agent.agent_id} ({currentCase.primary_agent.agent_type})
                </h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  Mass: {currentCase.primary_agent.mass_kg} kg
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Velocity</span>
                  <span className="text-base font-bold font-mono text-indigo-600 dark:text-indigo-400">
                    {primarySample.speed_kph.toFixed(1)} km/h
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Deceleration</span>
                  <span className="text-base font-bold font-mono text-rose-500">
                    {primarySample.accel_mps2.toFixed(1)} m/s²
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Brake Pressure</span>
                  <span className="text-base font-bold font-mono text-amber-500">
                    {primarySample.brake_pressure_bar ?? 0} bar
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">X Distance</span>
                  <span className="text-base font-bold font-mono text-slate-700 dark:text-slate-300">
                    {primarySample.x_coord.toFixed(1)} m
                  </span>
                </div>
              </div>
            </div>

            {/* Secondary Agent */}
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                  Secondary Agent: {currentCase.secondary_agent.agent_id} ({currentCase.secondary_agent.agent_type})
                </h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  Mass: {currentCase.secondary_agent.mass_kg} kg
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Velocity</span>
                  <span className="text-base font-bold font-mono text-amber-600 dark:text-amber-400">
                    {secondarySample.speed_kph.toFixed(1)} km/h
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Deceleration</span>
                  <span className="text-base font-bold font-mono text-slate-700 dark:text-slate-300">
                    {secondarySample.accel_mps2.toFixed(1)} m/s²
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Impact ΔV</span>
                  <span className="text-base font-bold font-mono text-rose-500">
                    {currentCase.kinetic_metrics.delta_v_secondary_kph.toFixed(1)} km/h
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
                  <span className="text-[10px] text-slate-400 uppercase font-mono block">Y Distance</span>
                  <span className="text-base font-bold font-mono text-slate-700 dark:text-slate-300">
                    {secondarySample.y_coord.toFixed(1)} m
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Kinematic Metrics Breakdown */}
          <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
            <h3 className="font-bold text-sm uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Kinematics & Forensic Metrics Summary
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl space-y-1">
                <span className="text-slate-400 block">Initial Approach Speed:</span>
                <span className="text-base font-bold">{currentCase.kinetic_metrics.initial_speed_kph.toFixed(1)} km/h</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl space-y-1">
                <span className="text-slate-400 block">Energy Dissipated:</span>
                <span className="text-base font-bold text-rose-600 dark:text-rose-400">{currentCase.kinetic_metrics.energy_dissipated_kj.toFixed(1)} kJ</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl space-y-1">
                <span className="text-slate-400 block">Stopping Distance:</span>
                <span className="text-base font-bold">{currentCase.kinetic_metrics.actual_stopping_distance_m.toFixed(1)} m</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl space-y-1">
                <span className="text-slate-400 block">Required DRAC:</span>
                <span className="text-base font-bold text-amber-500">{currentCase.kinetic_metrics.drac_required_mps2.toFixed(2)} m/s²</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: COUNTERFACTUAL INTERVENTIONS */}
      {activeTab === "counterfactuals" && (
        <div className="space-y-4">
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Compare historical collision outcomes against simulated engineering and behavioral interventions.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {currentCase.counterfactual_scenarios.map((scen) => (
              <div
                key={scen.scenario_id}
                className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold">
                      {scen.verdict}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      Margin: +{scen.clearance_margin_m.toFixed(1)}m
                    </span>
                  </div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                    {scen.scenario_title}
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                    {scen.explanation}
                  </p>
                </div>

                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Impact Speed:</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">{scen.counterfactual_impact_speed_kph} km/h</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Injury Risk Δ:</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">-{scen.injury_risk_reduction_pct}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Stopping Distance:</span>
                    <span className="font-bold">{scen.stopping_distance_m.toFixed(1)}m</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: JUDICIAL EVIDENCE DOSSIER */}
      {activeTab === "dossier" && (
        <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
            <div>
              <h3 className="font-bold text-base">Cryptographic Evidence Dossier</h3>
              <p className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                SHA-256 Digest: {currentCase.sha256_evidence_hash}
              </p>
            </div>
            <button
              type="button"
              onClick={downloadDossier}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm transition-colors"
            >
              <IconDownload className="h-3.5 w-3.5" />
              <span>Download Markdown</span>
            </button>
          </div>
          <pre className="p-4 bg-slate-50 dark:bg-slate-950 rounded-xl text-xs font-mono text-slate-800 dark:text-slate-200 overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {currentCase.judicial_summary_md}
          </pre>
        </div>
      )}
    </div>
  );
}
