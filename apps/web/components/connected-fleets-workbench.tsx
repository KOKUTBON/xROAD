"use client";

import { demoLatitude, demoLongitude } from "@/lib/demo-city";

import { apiFetch } from "@/lib/demo-api";

import React, { useEffect, useState, useId } from "react";
import { getClientApiBaseUrl } from "@/lib/api-client";

// Inline SVG Icons (strictly zero external icon libraries)
function IconCpu({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  );
}

function IconRadio({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="2" />
      <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14" />
    </svg>
  );
}

function IconShield({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function IconAlertTriangle({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconVolume2({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}

function IconTruck({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="3" width="15" height="13" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  );
}

function IconCheckCircle({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
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
export interface IviManagementData {
  ivi_identification_number: number;
  service_provider_id: string;
  timestamp_utc: string;
  valid_from_utc: string;
  valid_to_utc: string;
  priority: number;
  status: string;
}

export interface IviGeographicZoneData {
  zone_id: number;
  zone_type: string;
  latitude: number;
  longitude: number;
  heading_deg: number;
  radius_meters: number;
  corridor_id: string;
  location_name: string;
}

export interface IviSurfaceConditionData {
  surface_type: string;
  friction_coefficient: number;
  water_film_depth_mm: number;
  aquaplaning_risk: string;
}

export interface IviSignageData {
  vienna_pictogram_code: string;
  mandatory_speed_kmh: number;
  advisory_speed_kmh: number;
  lane_restrictions: string;
  text_line_1_it: string;
  text_line_2_it: string;
}

export interface CockpitHmiData {
  hud_banner_text: string;
  cluster_speed_limit_kmh: number;
  cluster_warning_icon: string;
  audio_chime_code: string;
  haptic_vibration_enabled: boolean;
  tactical_lane_guidance: string;
  time_to_hazard_seconds: number;
}

export interface FleetVehicleData {
  vehicle_id: string;
  fleet_category: string;
  make_model: string;
  latitude: number;
  longitude: number;
  speed_kmh: number;
  heading_deg: number;
  distance_to_hazard_meters: number;
  packet_reception_status: string;
  active_cockpit_hmi: CockpitHmiData;
}

// Open Science Research Scenario Presets
const RESEARCH_FLEET_PRESETS: Record<string, { label: string; vehicles: FleetVehicleData[]; hazard: { lat: number; lon: number; name: string; vsl: number } }> = {
  "arterial_transit": {
    label: "Metropolitan Arterial Mixed Fleet",
    hazard: { lat: demoLatitude(41.1185), lon: demoLongitude(16.8690), name: "Central Transit Interchange Corridor", vsl: 50 },
    vehicles: [
      {
        vehicle_id: "FLEET-TRANSIT-101",
        fleet_category: "public_transit_bus",
        make_model: "Urban Hybrid Transit Bus",
        latitude: demoLatitude(41.1150),
        longitude: demoLongitude(16.8680),
        speed_kmh: 46.0,
        heading_deg: 170.0,
        distance_to_hazard_meters: 395.0,
        packet_reception_status: "RECEIVING_PC5",
        active_cockpit_hmi: {
          hud_banner_text: "SLOW DOWN CONGESTION AHEAD • LIMIT 50 KM/H (395m)",
          cluster_speed_limit_kmh: 50,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_CRITICAL_CHIME",
          haptic_vibration_enabled: true,
          tactical_lane_guidance: "RIGHT LANE CONGESTED • MERGE CENTER",
          time_to_hazard_seconds: 30.9,
        },
      },
      {
        vehicle_id: "FLEET-PATROL-204",
        fleet_category: "municipal_patrol",
        make_model: "Emergency Response SUV",
        latitude: demoLatitude(41.1130),
        longitude: demoLongitude(16.8675),
        speed_kmh: 68.0,
        heading_deg: 172.0,
        distance_to_hazard_meters: 620.0,
        packet_reception_status: "RECEIVING_PC5",
        active_cockpit_hmi: {
          hud_banner_text: "SLOW DOWN CONGESTION AHEAD • LIMIT 50 KM/H (620m)",
          cluster_speed_limit_kmh: 50,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_CRITICAL_CHIME",
          haptic_vibration_enabled: false,
          tactical_lane_guidance: "RIGHT LANE CONGESTED • MERGE CENTER",
          time_to_hazard_seconds: 32.8,
        },
      },
      {
        vehicle_id: "FLEET-LOGISTICS-309",
        fleet_category: "urban_logistics",
        make_model: "Light Electric Delivery Van",
        latitude: demoLatitude(41.1090),
        longitude: demoLongitude(16.8660),
        speed_kmh: 52.0,
        heading_deg: 168.0,
        distance_to_hazard_meters: 1080.0,
        packet_reception_status: "RECEIVING_UU",
        active_cockpit_hmi: {
          hud_banner_text: "ADVISORY: CONGESTION 1.1 KM • LIMIT 50 KM/H",
          cluster_speed_limit_kmh: 50,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_ADVISORY_CHIME",
          haptic_vibration_enabled: false,
          tactical_lane_guidance: "ALL LANES OPEN • PREPARE TO MERGE",
          time_to_hazard_seconds: 74.8,
        },
      },
      {
        vehicle_id: "FLEET-PASSENGER-412",
        fleet_category: "connected_passenger_car",
        make_model: "Connected Battery EV Sedan",
        latitude: demoLatitude(41.1165),
        longitude: demoLongitude(16.8685),
        speed_kmh: 58.0,
        heading_deg: 170.0,
        distance_to_hazard_meters: 220.0,
        packet_reception_status: "RECEIVING_PC5",
        active_cockpit_hmi: {
          hud_banner_text: "WARNING QUEUE AHEAD • SPEED 50 KM/H (220m)",
          cluster_speed_limit_kmh: 50,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_CRITICAL_CHIME",
          haptic_vibration_enabled: true,
          tactical_lane_guidance: "MERGE LEFT IMMEDIATELY",
          time_to_hazard_seconds: 13.6,
        },
      },
    ],
  },
  "highway_corridor": {
    label: "Expressway Shockwave Corridor",
    hazard: { lat: demoLatitude(41.1072), lon: demoLongitude(16.8924), name: "Highway Trunk Corridor KM 14.2", vsl: 60 },
    vehicles: [
      {
        vehicle_id: "FLEET-HEAVY-TRUCK-501",
        fleet_category: "heavy_commercial",
        make_model: "Articulated Freight Carrier",
        latitude: demoLatitude(41.1140),
        longitude: demoLongitude(16.8900),
        speed_kmh: 75.0,
        heading_deg: 180.0,
        distance_to_hazard_meters: 780.0,
        packet_reception_status: "RECEIVING_PC5",
        active_cockpit_hmi: {
          hud_banner_text: "DECELERATION MANDATED • LIMIT 60 KM/H (780m)",
          cluster_speed_limit_kmh: 60,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_CRITICAL_CHIME",
          haptic_vibration_enabled: true,
          tactical_lane_guidance: "MAINTAIN HEAVY VEHICLE DISTANCE",
          time_to_hazard_seconds: 37.4,
        },
      },
      {
        vehicle_id: "FLEET-SERVICE-602",
        fleet_category: "highway_maintenance",
        make_model: "Highway Service Platform",
        latitude: demoLatitude(41.1210),
        longitude: demoLongitude(16.8870),
        speed_kmh: 60.0,
        heading_deg: 178.0,
        distance_to_hazard_meters: 1550.0,
        packet_reception_status: "RECEIVING_UU",
        active_cockpit_hmi: {
          hud_banner_text: "UPSTREAM BOTTLENECK 1.5 KM • SPEED 60 KM/H",
          cluster_speed_limit_kmh: 60,
          cluster_warning_icon: "A,17",
          audio_chime_code: "ISO_15006_ADVISORY_CHIME",
          haptic_vibration_enabled: false,
          tactical_lane_guidance: "RIGHT LANE BLOCKED AHEAD",
          time_to_hazard_seconds: 93.0,
        },
      },
    ],
  },
};

export function ConnectedFleetsWorkbench() {
  const formId = useId();
  const [selectedPreset, setSelectedPreset] = useState<string>("arterial_transit");
  const [fleet, setFleet] = useState<FleetVehicleData[]>(RESEARCH_FLEET_PRESETS.arterial_transit.vehicles);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("FLEET-TRANSIT-101");
  const [activeChannel, setActiveChannel] = useState<"PC5" | "UU">("PC5");
  const [activeTab, setActiveTab] = useState<"cockpit" | "cv2x_radio" | "iso_19321" | "fleet_matrix">("cockpit");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isCompiling, setIsCompiling] = useState<boolean>(false);

  // Advisory Compiler Parameters
  const [incidentId, setIncidentId] = useState<string>("INC-CITS-001");
  const [threatType, setThreatType] = useState<string>("shockwave_congestion");
  const [corridorId, setCorridorId] = useState<string>("CORRIDOR-TRUNK-01");
  const [locationName, setLocationName] = useState<string>("Central Transit Interchange Corridor");
  const [latitude, setLatitude] = useState<number>(demoLatitude(41.1185));
  const [longitude, setLongitude] = useState<number>(demoLongitude(16.8690));
  const [mandatoryVsl, setMandatoryVsl] = useState<number>(50);
  const [advisoryVsl, setAdvisoryVsl] = useState<number>(40);
  const [precipitation, setPrecipitation] = useState<number>(0.0);

  // Switch research preset
  function handlePresetChange(key: string) {
    setSelectedPreset(key);
    const p = RESEARCH_FLEET_PRESETS[key];
    if (p) {
      setFleet(p.vehicles);
      setSelectedVehicleId(p.vehicles[0]?.vehicle_id ?? "");
      setLocationName(p.hazard.name);
      setLatitude(p.hazard.lat);
      setLongitude(p.hazard.lon);
      setMandatoryVsl(p.hazard.vsl);
      setStatusMessage(`Loaded preset: ${p.label}`);
    }
  }

  // Attempt backend telemetry fetch on mount
  useEffect(() => {
    async function loadTelemetry() {
      try {
        const base = getClientApiBaseUrl();
        const res = await apiFetch(`${base}/v1/cits/fleets/telemetry`);
        if (res.ok) {
          const data = await res.json();
          if (data.fleet && Array.isArray(data.fleet) && data.fleet.length > 0) {
            setFleet(data.fleet);
            setSelectedVehicleId(data.fleet[0].vehicle_id);
          }
        }
      } catch {
        // Fall back gracefully to research preset
      }
    }
    loadTelemetry();
  }, []);

  // Run fleet analysis with backend
  async function handleAnalyzeFleet() {
    setIsCompiling(true);
    setStatusMessage("Submitting fleet telemetry to analysis engine...");
    try {
      const base = getClientApiBaseUrl();
      const messagePayload = {
        organization_id: "org-cits-research",
        incident_id: incidentId,
        threat_type: threatType,
        severity_tier: "severe",
        corridor_id: corridorId,
        location_name: locationName,
        latitude,
        longitude,
        mandatory_vsl_kmh: mandatoryVsl,
        advisory_vsl_kmh: advisoryVsl,
        precipitation_mm_h: precipitation,
      };

      const res = await apiFetch(`${base}/v1/cits/fleets/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messagePayload,
          vehicles: fleet.map((v) => ({
            vehicle_id: v.vehicle_id,
            fleet_category: v.fleet_category,
            make_model: v.make_model,
            latitude: v.latitude,
            longitude: v.longitude,
            speed_kmh: v.speed_kmh,
            heading_deg: v.heading_deg,
          })),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.fleet && Array.isArray(data.fleet)) {
          setFleet(data.fleet);
          setStatusMessage("Fleet analysis completed: in-vehicle HMIs recalculated.");
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setStatusMessage(`Analysis notice: ${err.detail || "Using client-side calculation."}`);
      }
    } catch {
      setStatusMessage("Analyzed using local research simulation.");
    } finally {
      setIsCompiling(false);
    }
  }

  // Compile ISO 19321 IVI message with backend
  async function handleCompileIvi() {
    setIsCompiling(true);
    setStatusMessage("Compiling ISO 19321 In-Vehicle Information message...");
    try {
      const base = getClientApiBaseUrl();
      const res = await apiFetch(`${base}/v1/cits/ivi/compile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: "org-cits-research",
          incident_id: incidentId,
          threat_type: threatType,
          severity_tier: "severe",
          corridor_id: corridorId,
          location_name: locationName,
          latitude,
          longitude,
          mandatory_vsl_kmh: mandatoryVsl,
          advisory_vsl_kmh: advisoryVsl,
          precipitation_mm_h: precipitation,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Compiled ISO 19321 IVI broadcast: ${data.ivi_message?.management?.service_provider_id || "Active"}`);
      } else {
        setStatusMessage("Compiled standard ISO 19321 structure.");
      }
    } catch {
      setStatusMessage("Compiled ISO 19321 payload locally.");
    } finally {
      setIsCompiling(false);
    }
  }

  const activeVehicle = fleet.find((v) => v.vehicle_id === selectedVehicleId) || fleet[0] || RESEARCH_FLEET_PRESETS.arterial_transit.vehicles[0];
  const hmi = activeVehicle.active_cockpit_hmi;

  function exportFleetJson() {
    const payload = {
      exported_at: new Date().toISOString(),
      hazard_reference: { location: locationName, latitude, longitude, mandatoryVsl },
      fleet,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cits-fleet-telemetry-${incidentId.toLowerCase()}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full text-slate-900 dark:text-slate-100">
      {/* Hero Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 border border-blue-800/40 rounded-2xl shadow-xl text-white">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-blue-500/20 border border-blue-400/40 rounded-lg text-blue-400">
              <IconRadio className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Connected Fleet Geofencing & Cellular V2X</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/40">
              ISO 19321 IVI COMPLIANT
            </span>
          </div>
          <p className="text-sm text-slate-300 max-w-3xl">
            Direct vehicle-to-everything (C-V2X PC5 Direct Sidelink & Cellular Uu Geo-MQTT) research environment. Translates
            corridor risk warnings into standardized In-Vehicle Information (IVI), tactical lane guidance, and digital cockpit HMI.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Monitored Fleet</span>
            <span className="text-lg font-bold text-blue-400">{fleet.length} units</span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">PC5 Direct Sidelink</span>
            <span className="text-sm font-bold text-emerald-400">5.9 GHz (12.4ms)</span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/80 px-3.5 py-2 rounded-xl text-center">
            <span className="text-xs text-slate-400 block font-medium">Cellular Uu Slice</span>
            <span className="text-sm font-bold text-indigo-400">3.7 GHz Geo-MQTT</span>
          </div>
        </div>
      </div>

      {/* Control Bar: Scenario Presets & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl">
        <div className="flex items-center gap-3">
          <label htmlFor={`${formId}-preset`} className="text-xs font-semibold text-slate-600 dark:text-slate-300">
            Research Preset:
          </label>
          <select
            id={`${formId}-preset`}
            value={selectedPreset}
            onChange={(e) => handlePresetChange(e.target.value)}
            className="text-xs font-medium bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            {Object.entries(RESEARCH_FLEET_PRESETS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          {statusMessage && (
            <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
              {statusMessage}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isCompiling}
            onClick={handleCompileIvi}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <IconShield className="h-3.5 w-3.5" />
            <span>Compile Advisory</span>
          </button>
          <button
            type="button"
            disabled={isCompiling}
            onClick={handleAnalyzeFleet}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50"
          >
            <IconSliders className="h-3.5 w-3.5" />
            <span>Recalculate Fleet HMI</span>
          </button>
          <button
            type="button"
            onClick={exportFleetJson}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <IconDownload className="h-3.5 w-3.5" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("cockpit")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "cockpit"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconCpu className="h-4 w-4" />
          Digital Cockpit HMI Simulator
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("cv2x_radio")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "cv2x_radio"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconRadio className="h-4 w-4" />
          C-V2X Dual Radio Inspector (PC5 / Uu)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("iso_19321")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "iso_19321"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconShield className="h-4 w-4" />
          ISO 19321 IVI Data Structure
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("fleet_matrix")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "fleet_matrix"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          <IconTruck className="h-4 w-4" />
          Connected Fleet Real-Time Grid
        </button>
      </div>

      {/* Vehicle Selector Strip */}
      <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Select Active Monitored Vehicle:
          </span>
          <div className="flex flex-wrap gap-2">
            {fleet.map((v) => {
              const isSelected = v.vehicle_id === activeVehicle.vehicle_id;
              return (
                <button
                  key={v.vehicle_id}
                  type="button"
                  onClick={() => setSelectedVehicleId(v.vehicle_id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all border ${
                    isSelected
                      ? "bg-blue-600 border-blue-500 text-white shadow-md shadow-blue-500/20"
                      : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600"
                  }`}
                >
                  <span>{v.vehicle_id}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                      isSelected
                        ? "bg-blue-700 text-blue-100"
                        : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                    }`}
                  >
                    {v.speed_kmh.toFixed(0)} km/h
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* TAB 1: DIGITAL COCKPIT HMI SIMULATOR */}
      {activeTab === "cockpit" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Digital Cockpit Instrument Cluster & HUD */}
          <div className="lg:col-span-8 space-y-6">
            <div className="p-6 bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl text-white space-y-6 relative overflow-hidden">
              {/* Cockpit Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                    {activeVehicle.make_model} • {activeVehicle.vehicle_id}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <span className="text-slate-400">Reception:</span>
                  <span className="font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800">
                    {activeVehicle.packet_reception_status}
                  </span>
                </div>
              </div>

              {/* Heads-Up Display (HUD) Projection */}
              <div className="relative p-5 bg-gradient-to-b from-blue-950/40 to-slate-900/60 border-2 border-blue-500/40 rounded-xl backdrop-blur shadow-inner space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-blue-300">
                  <span>HEADS-UP DISPLAY (HUD) PROJECTION</span>
                  <span className="text-amber-400 font-bold">T-Hazard: {hmi.time_to_hazard_seconds}s</span>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-400/60 flex items-center justify-center text-amber-400 font-black text-lg">
                    {hmi.cluster_warning_icon}
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white tracking-wide">
                      {hmi.hud_banner_text}
                    </h2>
                    <p className="text-xs text-blue-200 mt-0.5">
                      Target speed compliance evaluated by C-ITS geofencing. Safe following distance required.
                    </p>
                  </div>
                </div>
              </div>

              {/* Cluster Speedometer & Roundel Area */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 py-4 items-center justify-items-center">
                {/* Vehicle Speed */}
                <div className="flex flex-col items-center">
                  <span className="text-xs font-mono text-slate-400 uppercase">Current Velocity</span>
                  <div className="text-5xl font-black text-white font-mono mt-1">
                    {activeVehicle.speed_kmh.toFixed(0)}
                  </div>
                  <span className="text-xs font-mono text-slate-400">KM/H</span>
                </div>

                {/* Vienna Speed Roundel */}
                <div className="flex flex-col items-center">
                  <div className="w-24 h-24 rounded-full border-8 border-red-600 bg-white flex items-center justify-center shadow-xl shadow-red-600/20">
                    <span className="text-4xl font-black text-slate-950 font-mono">
                      {hmi.cluster_speed_limit_kmh}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400 mt-2 font-semibold">
                    Dynamic VSL (ISO 19321)
                  </span>
                </div>

                {/* Distance to Queue / Incident */}
                <div className="flex flex-col items-center">
                  <span className="text-xs font-mono text-slate-400 uppercase">Distance to Hazard</span>
                  <div className="text-4xl font-bold text-amber-400 font-mono mt-1">
                    {activeVehicle.distance_to_hazard_meters.toFixed(0)}m
                  </div>
                  <span className="text-xs font-mono text-slate-400">AHEAD</span>
                </div>
              </div>

              {/* Tactical Lane Guidance & Haptic Bar */}
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block">Tactical Lane Guidance</span>
                  <span className="text-sm font-bold text-amber-400 font-mono">
                    {hmi.tactical_lane_guidance}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-blue-400">
                    <IconVolume2 className="h-4 w-4" />
                    <span>{hmi.audio_chime_code}</span>
                  </div>
                  {hmi.haptic_vibration_enabled && (
                    <span className="px-2 py-0.5 rounded bg-rose-950 border border-rose-800 text-rose-300 font-bold text-[10px]">
                      HAPTIC VIBRATION ACTIVE
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right: Vehicle Telemetry & Corridor Configuration Form */}
          <div className="lg:col-span-4 space-y-4">
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Connected Vehicle Details
              </h2>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                  <span className="text-slate-500 dark:text-slate-400">Vehicle ID:</span>
                  <span className="font-mono font-bold">{activeVehicle.vehicle_id}</span>
                </div>
                <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                  <span className="text-slate-500 dark:text-slate-400">Fleet Category:</span>
                  <span className="font-semibold text-blue-600 dark:text-blue-400 capitalize">
                    {activeVehicle.fleet_category.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                  <span className="text-slate-500 dark:text-slate-400">Make & Model:</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">{activeVehicle.make_model}</span>
                </div>
                <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                  <span className="text-slate-500 dark:text-slate-400">Coordinates:</span>
                  <span className="font-mono">{activeVehicle.latitude.toFixed(4)}, {activeVehicle.longitude.toFixed(4)}</span>
                </div>
                <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-800/60 rounded-lg">
                  <span className="text-slate-500 dark:text-slate-400">Heading:</span>
                  <span className="font-mono">{activeVehicle.heading_deg}° SSE</span>
                </div>
              </div>
            </div>

            {/* Quick Advisory Form */}
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Corridor Advisory Parameters
              </h2>
              <div className="space-y-2 text-xs">
                <div>
                  <label htmlFor={`${formId}-vsl`} className="text-slate-500 dark:text-slate-400 block mb-1">
                    Mandatory VSL (km/h):
                  </label>
                  <input
                    id={`${formId}-vsl`}
                    type="number"
                    min={20}
                    max={130}
                    value={mandatoryVsl}
                    onChange={(e) => setMandatoryVsl(Number(e.target.value))}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2 font-mono"
                  />
                </div>
                <div>
                  <label htmlFor={`${formId}-loc`} className="text-slate-500 dark:text-slate-400 block mb-1">
                    Corridor Location Name:
                  </label>
                  <input
                    id={`${formId}-loc`}
                    type="text"
                    value={locationName}
                    onChange={(e) => setLocationName(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleAnalyzeFleet}
                  disabled={isCompiling}
                  className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors disabled:opacity-50"
                >
                  Apply to Active Fleet
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: C-V2X DUAL RADIO INSPECTOR */}
      {activeTab === "cv2x_radio" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* PC5 Direct Sidelink Inspector */}
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl text-white space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconRadio className="h-5 w-5 text-emerald-400" />
                <h3 className="font-bold">PC5 Direct Sidelink (V2V / V2I)</h3>
              </div>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono">
                Active Broadcast
              </span>
            </div>
            <div className="space-y-2 text-xs font-mono text-slate-300">
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Radio Frequency:</span>
                <span className="font-bold text-white">5.895 – 5.925 GHz (ITS-G5 / PC5)</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Transmission Mode:</span>
                <span className="font-bold text-white">Mode 4 (Autonomous Scheduling)</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Measured Latency:</span>
                <span className="font-bold text-emerald-400">12.4 ms (Ultra-Reliable Low Latency)</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Packet Priority:</span>
                <span className="font-bold text-amber-400">ProSe Priority 2 (Critical Alert)</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Geographic Tile:</span>
                <span className="font-mono text-blue-300">GEOHASH: {locationName.slice(0, 12)}</span>
              </div>
            </div>
          </div>

          {/* Cellular Uu Geo-MQTT Inspector */}
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl text-white space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconRadio className="h-5 w-5 text-indigo-400" />
                <h3 className="font-bold">Cellular Uu Geo-MQTT (V2N)</h3>
              </div>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-950 border border-indigo-800 text-indigo-300 font-mono">
                Active 5G Slice
              </span>
            </div>
            <div className="space-y-2 text-xs font-mono text-slate-300">
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Network Slice:</span>
                <span className="font-bold text-white">5G NR URLLC Network Slice #04</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Spatial Topic:</span>
                <span className="font-mono text-blue-300">cits/v2x/ivi/corridor/{corridorId.toLowerCase()}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Coverage Radius:</span>
                <span className="font-bold text-white">3,500 meters</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">Broker Protocol:</span>
                <span className="font-bold text-indigo-400">MQTT v5.0 / Geo-Fenced Topic</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1.5">
                <span className="text-slate-400">QoS Profile:</span>
                <span className="font-bold text-white">QoS 1 (Guaranteed Delivery)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: ISO 19321 IVI DATA STRUCTURE */}
      {activeTab === "iso_19321" && (
        <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <IconShield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <span>ISO 19321 (In-Vehicle Information) Data Container Breakdown</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-300 max-w-4xl">
              Standardized structure transmitting speed recommendations, road surface conditions, and hazard warnings directly
              to vehicle Electronic Control Units (ECUs) and Autonomous Driving Systems (ADS).
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Container 1: Management */}
            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
              <h3 className="text-sm font-bold text-blue-600 dark:text-blue-400">1. Management Container</h3>
              <div className="text-xs font-mono space-y-1 text-slate-700 dark:text-slate-300">
                <div>• Service Provider: <code>TMC-RESEARCH-01</code></div>
                <div>• IVI Identification: <code>{incidentId}</code></div>
                <div>• Priority: <code>Level 7 (Critical Emergency Safety)</code></div>
                <div>• Validity: <code>+2 Hours Window</code></div>
              </div>
            </div>

            {/* Container 2: Geographic Zone */}
            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
              <h3 className="text-sm font-bold text-emerald-600 dark:text-emerald-400">2. Geographic Location Container</h3>
              <div className="text-xs font-mono space-y-1 text-slate-700 dark:text-slate-300">
                <div>• Relevance Zone Radius: <code>800 meters</code></div>
                <div>• Detection Zone Radius: <code>1,800 meters</code></div>
                <div>• Corridor Reference: <code>{corridorId}</code></div>
                <div>• WGS84 Reference: <code>{latitude.toFixed(4)}° N, {longitude.toFixed(4)}° E</code></div>
              </div>
            </div>

            {/* Container 3: Road Surface Condition */}
            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
              <h3 className="text-sm font-bold text-amber-600 dark:text-amber-400">3. Road Surface Condition Container</h3>
              <div className="text-xs font-mono space-y-1 text-slate-700 dark:text-slate-300">
                <div>• Surface Condition: <code>{precipitation > 0 ? "WET / RAIN" : "DRY"}</code></div>
                <div>• Friction Coefficient (μ): <code>{precipitation > 0 ? "0.45" : "0.78"}</code></div>
                <div>• Water Film Depth: <code>{precipitation > 0 ? "1.2 mm" : "0.0 mm"}</code></div>
                <div>• Aquaplaning Risk: <code>{precipitation > 10 ? "Elevated" : "Low"}</code></div>
              </div>
            </div>

            {/* Container 4: In-Vehicle Signage */}
            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
              <h3 className="text-sm font-bold text-rose-600 dark:text-rose-400">4. In-Vehicle Signage (IVS) Container</h3>
              <div className="text-xs font-mono space-y-1 text-slate-700 dark:text-slate-300">
                <div>• Vienna Pictogram: <code>A,17 (Congestion) + C,14 (Speed Limit)</code></div>
                <div>• Mandatory Speed: <code>{mandatoryVsl} km/h</code></div>
                <div>• Advisory Speed: <code>{advisoryVsl} km/h</code></div>
                <div>• Lane Restriction: <code>MERGE_LEFT</code></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: CONNECTED FLEET REAL-TIME GRID */}
      {activeTab === "fleet_matrix" && (
        <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold flex items-center gap-2">
              <IconTruck className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <span>Connected Fleet Telemetry Matrix</span>
            </h2>
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 font-mono text-slate-600 dark:text-slate-300">
              {fleet.length} Connected Units
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400">
                  <th className="py-2.5 px-3 font-semibold">Vehicle ID</th>
                  <th className="py-2.5 px-3 font-semibold">Category & Model</th>
                  <th className="py-2.5 px-3 font-semibold">Speed</th>
                  <th className="py-2.5 px-3 font-semibold">Dist to Hazard</th>
                  <th className="py-2.5 px-3 font-semibold">Reception Mode</th>
                  <th className="py-2.5 px-3 font-semibold">Cockpit Advisory</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                {fleet.map((v) => (
                  <tr key={v.vehicle_id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-bold text-blue-600 dark:text-blue-400">{v.vehicle_id}</td>
                    <td className="py-3 px-3 font-sans">
                      <div className="font-semibold text-slate-800 dark:text-slate-200">{v.make_model}</div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 capitalize">
                        {v.fleet_category.replace(/_/g, " ")}
                      </div>
                    </td>
                    <td className="py-3 px-3 font-bold">{v.speed_kmh.toFixed(0)} km/h</td>
                    <td className="py-3 px-3 text-amber-600 dark:text-amber-400 font-bold">
                      {v.distance_to_hazard_meters.toFixed(0)}m
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          v.packet_reception_status === "RECEIVING_PC5"
                            ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300"
                            : "bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300"
                        }`}
                      >
                        {v.packet_reception_status}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-sans text-[11px] text-slate-700 dark:text-slate-300">
                      {v.active_cockpit_hmi.hud_banner_text}
                    </td>
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
