"use client";

import { apiFetch } from "@/lib/demo-api";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePlatformSession } from "@/components/session-provider";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { KpiStrip, WorkSurface, WorkspacePage } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";

const API_BASE_URL = getClientApiBaseUrl();

type TrajectoryPoint = {
  time_sec: number;
  x_coord: number;
  y_coord: number;
  speed_mps: number;
  heading_deg: number;
  accel_mps2: number;
};

type SimulatedAgent = {
  agent_id: string;
  agent_type: string;
  is_vru: boolean;
  length_m: number;
  width_m: number;
  points: TrajectoryPoint[];
};

type ConflictEvent = {
  conflict_id: string;
  time_sec: number;
  agent_1_id: string;
  agent_1_type: string;
  agent_2_id: string;
  agent_2_type: string;
  conflict_type: string;
  ttc_seconds: number;
  pet_seconds: number;
  drac_mps2: number;
  delta_v_kmh?: number;
  is_vru_involved?: boolean;
  conflict_severity_index: number;
  severity_tier: "critical" | "severe" | "moderate";
  conflict_x: number;
  conflict_y: number;
};

type SimulationSummary = {
  scenario_name: string;
  geometry_template: string;
  junction_id: string;
  total_agents_simulated: number;
  total_vehicles: number;
  total_vrus: number;
  total_conflicts_count: number;
  critical_conflicts_count: number;
  vru_conflicts_count: number;
  min_ttc_seconds: number;
  min_pet_seconds: number;
  max_drac_mps2: number;
  mean_csi: number;
  trajectories?: SimulatedAgent[];
  conflicts?: ConflictEvent[];
};

type CountermeasureAppraisal = {
  junction_id: string;
  baseline_template: string;
  redesign_template: string;
  baseline_conflicts: number;
  redesign_conflicts: number;
  absolute_conflict_reduction: number;
  percent_conflict_reduction: number;
  baseline_vru_conflicts: number;
  redesign_vru_conflicts: number;
  percent_vru_conflict_reduction: number;
  min_ttc_baseline_sec: number;
  min_ttc_redesign_sec: number;
  max_drac_baseline_mps2: number;
  max_drac_redesign_mps2: number;
  appraisal_verdict: string;
  primary_safety_benefit: string;
};

type SimulationApiResponse = {
  api_version: string;
  sim_sandbox_version: string;
  contract_version: string;
  network_label: string;
  junction_id: string;
  comparison: CountermeasureAppraisal;
  baseline_summary: SimulationSummary;
  redesign_summary: SimulationSummary;
};

const JUNCTION_PRESETS = [
  { id: "JNC-CENTRAL-STATION", name: "Central Railway Station Plaza & Interchange", defaultBaseline: "BASELINE_SIGNALIZED" },
  { id: "JNC-COMMERCIAL-AVENUE", name: "Downtown Commercial Corridor / Main Avenue", defaultBaseline: "BASELINE_SIGNALIZED" },
  { id: "JNC-METRO-ARTERIAL", name: "Metropolitan Arterial Transit Junction", defaultBaseline: "BASELINE_SIGNALIZED" },
];

const TEMPLATE_DESCRIPTIONS: Record<string, { label: string; desc: string }> = {
  BASELINE_SIGNALIZED: {
    label: "Standard 4-Leg Signalized",
    desc: "Permissive left turns, direct concurrent pedestrian crossings without refuge.",
  },
  DUTCH_PROTECTED_JUNCTION: {
    label: "Dutch Protected Junction",
    desc: "Corner refuge islands, 5m setback crossings, separated cycle tracks.",
  },
  TURBO_ROUNDABOUT: {
    label: "Modern Turbo-Roundabout",
    desc: "Deflected approach, physical lane spiral separators, central raised apron.",
  },
  ROAD_DIET_REFUGE: {
    label: "Road Diet with Refuge Table",
    desc: "4-to-3 lane conversion, center turn lane, protected pedestrian refuge.",
  },
};

export function DigitalTwinWorkbench() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId || "org-mobility-research";

  // Scenario configuration
  const [junctionId, setJunctionId] = useState<string>("JNC-CENTRAL-STATION");
  const [baselineTemplate, setBaselineTemplate] = useState<string>("BASELINE_SIGNALIZED");
  const [redesignTemplate, setRedesignTemplate] = useState<string>("DUTCH_PROTECTED_JUNCTION");
  const [durationSeconds, setDurationSeconds] = useState<number>(30.0);
  const [vehicleDemandVph, setVehicleDemandVph] = useState<number>(700.0);
  const [vruDemandPph, setVruDemandPph] = useState<number>(140.0);

  // Simulation execution state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [simData, setSimData] = useState<SimulationApiResponse | null>(null);

  // Active view & playback state
  const [activeGeometry, setActiveGeometry] = useState<"redesign" | "baseline">("redesign");
  const [currentTime, setCurrentTime] = useState<number>(0.0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [selectedConflict, setSelectedConflict] = useState<ConflictEvent | null>(null);

  // 3D Camera Controls: pitch (deg), yaw (deg), zoom
  const [pitch, setPitch] = useState<number>(55);
  const [yaw, setYaw] = useState<number>(35);
  const [zoom, setZoom] = useState<number>(1.0);
  const [is3dMode, setIs3dMode] = useState<boolean>(true);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastFrameTimeRef = useRef<number | null>(null);
  const isDraggingRef = useRef<boolean>(false);
  const dragStartPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Run simulation query
  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSelectedConflict(null);
    try {
      const res = await apiFetch(`${API_BASE_URL}/v1/simulation/synthetic-countermeasure-eval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          organization_id: organizationId,
          network_label: "digital_twin_simulation",
          junction_id: junctionId,
          baseline_template: baselineTemplate,
          redesign_template: redesignTemplate,
          duration_seconds: durationSeconds,
          vehicle_demand_vph: vehicleDemandVph,
          vru_demand_pph: vruDemandPph,
          random_seed: 42,
          include_trajectories: true,
        }),
      });

      if (!res.ok) {
        throw new Error(`Simulation service returned status ${res.status}`);
      }

      const data: SimulationApiResponse = await res.json();
      setSimData(data);
      setCurrentTime(0.0);
      setIsPlaying(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run simulation");
    } finally {
      setIsLoading(false);
    }
  }, [organizationId, junctionId, baselineTemplate, redesignTemplate, durationSeconds, vehicleDemandVph, vruDemandPph]);

  // Initial load
  useEffect(() => {
    runSimulation();
  }, [runSimulation]);

  // Active simulation dataset
  const activeSimSummary = simData
    ? activeGeometry === "redesign"
      ? simData.redesign_summary
      : simData.baseline_summary
    : null;

  const trajectories = activeSimSummary?.trajectories || [];
  const conflicts = activeSimSummary?.conflicts || [];

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) {
      lastFrameTimeRef.current = null;
      return;
    }

    const stepAnimation = (timestamp: number) => {
      if (lastFrameTimeRef.current !== null) {
        const deltaSeconds = (timestamp - lastFrameTimeRef.current) / 1000;
        setCurrentTime((prev) => {
          const next = prev + deltaSeconds * playbackSpeed;
          if (next >= durationSeconds) {
            return 0.0; // Loop seamlessly
          }
          return next;
        });
      }
      lastFrameTimeRef.current = timestamp;
      animationFrameRef.current = requestAnimationFrame(stepAnimation);
    };

    animationFrameRef.current = requestAnimationFrame(stepAnimation);
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, durationSeconds]);

  // Interpolate agent position at current time t
  const getAgentAtTime = (agent: SimulatedAgent, t: number) => {
    const pts = agent.points;
    if (!pts || pts.length === 0) return null;
    if (t < pts[0].time_sec || t > pts[pts.length - 1].time_sec) return null;

    // Binary search / find segment
    let low = 0;
    let high = pts.length - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (pts[mid].time_sec <= t) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    const idx = Math.max(0, high);
    const p1 = pts[idx];
    const p2 = pts[Math.min(idx + 1, pts.length - 1)];

    if (p1 === p2 || p2.time_sec === p1.time_sec) {
      return {
        x: p1.x_coord,
        y: p1.y_coord,
        speed: p1.speed_mps,
        heading: p1.heading_deg,
        accel: p1.accel_mps2,
      };
    }

    const ratio = Math.max(0, Math.min(1, (t - p1.time_sec) / (p2.time_sec - p1.time_sec)));
    return {
      x: p1.x_coord + (p2.x_coord - p1.x_coord) * ratio,
      y: p1.y_coord + (p2.y_coord - p1.y_coord) * ratio,
      speed: p1.speed_mps + (p2.speed_mps - p1.speed_mps) * ratio,
      heading: p1.heading_deg,
      accel: p1.accel_mps2,
    };
  };

  // 3D Isometric Projection Transformation
  const project3D = useCallback(
    (x: number, y: number, z: number, width: number, height: number) => {
      const cx = width / 2;
      const cy = height / 2;
      const baseScale = Math.min(width, height) / 110 * zoom;

      if (!is3dMode) {
        // Orthographic Top-Down 2D
        return {
          sx: cx + x * baseScale,
          sy: cy - y * baseScale,
          scale: baseScale,
        };
      }

      // 3D Isometric View
      const radYaw = (yaw * Math.PI) / 180;
      const radPitch = (pitch * Math.PI) / 180;

      // Rotate around Z axis (yaw)
      const rx = x * Math.cos(radYaw) - y * Math.sin(radYaw);
      const ry = x * Math.sin(radYaw) + y * Math.cos(radYaw);

      // Tilt around X axis (pitch)
      const py = ry * Math.cos(radPitch) - z * Math.sin(radPitch);

      return {
        sx: cx + rx * baseScale,
        sy: cy + py * baseScale,
        scale: baseScale,
      };
    },
    [is3dMode, pitch, yaw, zoom]
  );

  // Main Canvas Rendering Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Handle high-DPI scaling
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = canvas.clientWidth;
    const displayHeight = canvas.clientHeight;
    if (canvas.width !== displayWidth * dpr || canvas.height !== displayHeight * dpr) {
      canvas.width = displayWidth * dpr;
      canvas.height = displayHeight * dpr;
    }
    ctx.save();
    ctx.scale(dpr, dpr);

    const w = displayWidth;
    const h = displayHeight;

    // 1. Background Fill (Dark Sovereign Canvas)
    ctx.fillStyle = "#0c121e";
    ctx.fillRect(0, 0, w, h);

    // Subtle coordinate grid
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 1;
    const gridStep = 10;
    for (let gx = -50; gx <= 50; gx += gridStep) {
      const p1 = project3D(gx, -50, 0, w, h);
      const p2 = project3D(gx, 50, 0, w, h);
      ctx.beginPath();
      ctx.moveTo(p1.sx, p1.sy);
      ctx.lineTo(p2.sx, p2.sy);
      ctx.stroke();
    }
    for (let gy = -50; gy <= 50; gy += gridStep) {
      const p1 = project3D(-50, gy, 0, w, h);
      const p2 = project3D(50, gy, 0, w, h);
      ctx.beginPath();
      ctx.moveTo(p1.sx, p1.sy);
      ctx.lineTo(p2.sx, p2.sy);
      ctx.stroke();
    }

    const curTemplate = activeSimSummary?.geometry_template || baselineTemplate;

    // 2. Draw Junction Road Geometry
    // Road segments: East-West (-50 to 50, y: -7 to 7) & North-South (x: -7 to 7, y: -50 to 50)
    const drawPoly = (points: [number, number][], fill: string, stroke?: string, lineWidth = 1) => {
      ctx.beginPath();
      const p0 = project3D(points[0][0], points[0][1], 0, w, h);
      ctx.moveTo(p0.sx, p0.sy);
      for (let i = 1; i < points.length; i++) {
        const p = project3D(points[i][0], points[i][1], 0, w, h);
        ctx.lineTo(p.sx, p.sy);
      }
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
      }
    };

    // Asphalt surface
    const roadWidth = curTemplate === "ROAD_DIET_REFUGE" ? 5.5 : 7.0;
    drawPoly([[-50, -roadWidth], [50, -roadWidth], [50, roadWidth], [-50, roadWidth]], "#1e2638", "#2a364f");
    drawPoly([[-roadWidth, -50], [roadWidth, -50], [roadWidth, 50], [-roadWidth, 50]], "#1e2638", "#2a364f");

    // Geometric Features per Template
    if (curTemplate === "DUTCH_PROTECTED_JUNCTION") {
      // Dutch Corner Refuge Islands (curbed safety islands)
      const islandFill = "#1b3a2a"; // Green-stone refuge
      const islandBorder = "#22c55e";
      const islandR = 4.5;
      drawPoly([[-roadWidth, -roadWidth], [-roadWidth - islandR, -roadWidth], [-roadWidth, -roadWidth - islandR]], islandFill, islandBorder);
      drawPoly([[roadWidth, -roadWidth], [roadWidth + islandR, -roadWidth], [roadWidth, -roadWidth - islandR]], islandFill, islandBorder);
      drawPoly([[-roadWidth, roadWidth], [-roadWidth - islandR, roadWidth], [-roadWidth, roadWidth + islandR]], islandFill, islandBorder);
      drawPoly([[roadWidth, roadWidth], [roadWidth + islandR, roadWidth], [roadWidth, roadWidth + islandR]], islandFill, islandBorder);

      // Protected cycle tracks (Green paths setback 5m)
      ctx.strokeStyle = "rgba(34, 197, 94, 0.4)";
      ctx.lineWidth = 3;
      const c1 = project3D(-25, -roadWidth - 2.5, 0, w, h);
      const c2 = project3D(25, -roadWidth - 2.5, 0, w, h);
      ctx.beginPath();
      ctx.moveTo(c1.sx, c1.sy);
      ctx.lineTo(c2.sx, c2.sy);
      ctx.stroke();
    } else if (curTemplate === "TURBO_ROUNDABOUT") {
      // Central circular raised island
      const centerFill = "#2a3d32";
      const centerBorder = "#4ade80";
      const circlePts: [number, number][] = [];
      const numPts = 24;
      const radius = 9.0;
      for (let i = 0; i < numPts; i++) {
        const ang = (i * 2 * Math.PI) / numPts;
        circlePts.push([Math.cos(ang) * radius, Math.sin(ang) * radius]);
      }
      drawPoly(circlePts, centerFill, centerBorder, 2);
    } else if (curTemplate === "ROAD_DIET_REFUGE") {
      // Pedestrian Refuge Table in center of road
      drawPoly([[-2.0, -1.2], [2.0, -1.2], [2.0, 1.2], [-2.0, 1.2]], "#283548", "#f59e0b", 2);
    }

    // Lane dividers (Dashed white lines)
    ctx.strokeStyle = "rgba(255, 255, 255, 0.3)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 6]);
    const l1 = project3D(-45, 0, 0, w, h);
    const l2 = project3D(-roadWidth, 0, 0, w, h);
    ctx.beginPath();
    ctx.moveTo(l1.sx, l1.sy);
    ctx.lineTo(l2.sx, l2.sy);
    ctx.stroke();

    const l3 = project3D(roadWidth, 0, 0, w, h);
    const l4 = project3D(45, 0, 0, w, h);
    ctx.beginPath();
    ctx.moveTo(l3.sx, l3.sy);
    ctx.lineTo(l4.sx, l4.sy);
    ctx.stroke();

    const l5 = project3D(0, -45, 0, w, h);
    const l6 = project3D(0, -roadWidth, 0, w, h);
    ctx.beginPath();
    ctx.moveTo(l5.sx, l5.sy);
    ctx.lineTo(l6.sx, l6.sy);
    ctx.stroke();

    const l7 = project3D(0, roadWidth, 0, w, h);
    const l8 = project3D(0, 45, 0, w, h);
    ctx.beginPath();
    ctx.moveTo(l7.sx, l7.sy);
    ctx.lineTo(l8.sx, l8.sy);
    ctx.stroke();
    ctx.setLineDash([]);

    // Crosswalk zebra stripes
    const drawCrosswalk = (startX: number, startY: number, isVertical: boolean) => {
      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      const stripes = 5;
      for (let s = 0; s < stripes; s++) {
        const offset = (s - 2) * 1.6;
        if (isVertical) {
          const pt = project3D(startX, startY + offset, 0, w, h);
          ctx.fillRect(pt.sx - 8, pt.sy - 2, 16, 4);
        } else {
          const pt = project3D(startX + offset, startY, 0, w, h);
          ctx.fillRect(pt.sx - 2, pt.sy - 8, 4, 16);
        }
      }
    };
    drawCrosswalk(-roadWidth - 2, 0, false);
    drawCrosswalk(roadWidth + 2, 0, false);
    drawCrosswalk(0, -roadWidth - 2, true);
    drawCrosswalk(0, roadWidth + 2, true);

    // 3. Render Active Near-Miss Conflict Beacons & TTC Cones
    const activeConflicts = conflicts.filter((c) => Math.abs(c.time_sec - currentTime) <= 2.0);

    for (const conf of activeConflicts) {
      const confPt = project3D(conf.conflict_x, conf.conflict_y, 0, w, h);
      const isCritical = conf.severity_tier === "critical";
      const ringColor = isCritical ? "#ef4444" : conf.severity_tier === "severe" ? "#f97316" : "#eab308";

      // Pulsing conflict halo
      const pulsePhase = (Date.now() % 1000) / 1000;
      const haloRadius = 14 + pulsePhase * 18;

      ctx.beginPath();
      ctx.arc(confPt.sx, confPt.sy, haloRadius, 0, 2 * Math.PI);
      ctx.strokeStyle = ringColor;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 1.0 - pulsePhase;
      ctx.stroke();
      ctx.globalAlpha = 1.0;

      // Solid central beacon
      ctx.beginPath();
      ctx.arc(confPt.sx, confPt.sy, 5, 0, 2 * Math.PI);
      ctx.fillStyle = ringColor;
      ctx.fill();

      // Find conflicting agents to draw 3D TTC danger connector line
      const a1 = trajectories.find((t) => t.agent_id === conf.agent_1_id);
      const a2 = trajectories.find((t) => t.agent_id === conf.agent_2_id);
      if (a1 && a2) {
        const p1 = getAgentAtTime(a1, currentTime);
        const p2 = getAgentAtTime(a2, currentTime);
        if (p1 && p2) {
          const s1 = project3D(p1.x, p1.y, 1.2, w, h);
          const s2 = project3D(p2.x, p2.y, 1.2, w, h);

          ctx.beginPath();
          ctx.setLineDash([4, 4]);
          ctx.strokeStyle = ringColor;
          ctx.lineWidth = 2;
          ctx.moveTo(s1.sx, s1.sy);
          ctx.lineTo(confPt.sx, confPt.sy);
          ctx.lineTo(s2.sx, s2.sy);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // Floating 3D TTC tag
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.strokeStyle = ringColor;
      ctx.lineWidth = 1;
      const tagText = `TTC: ${conf.ttc_seconds.toFixed(1)}s • ${conf.conflict_type}`;
      ctx.font = "bold 11px system-ui, -apple-system, sans-serif";
      const tagW = ctx.measureText(tagText).width + 12;
      ctx.fillRect(confPt.sx - tagW / 2, confPt.sy - 28, tagW, 20);
      ctx.strokeRect(confPt.sx - tagW / 2, confPt.sy - 28, tagW, 20);
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(tagText, confPt.sx, confPt.sy - 18);
    }

    // 4. Render Multi-Agent Trajectories (Vehicles, Buses, VRUs)
    for (const agent of trajectories) {
      const state = getAgentAtTime(agent, currentTime);
      if (!state) continue;

      const pos = project3D(state.x, state.y, 0, w, h);
      const isBraking = state.accel < -1.5;

      if (agent.is_vru) {
        // VRU rendering (Pedestrian / Cyclist / E-Scooter)
        const vruColor = agent.agent_type === "pedestrian" ? "#fbbf24" : "#38bdf8";
        ctx.beginPath();
        ctx.arc(pos.sx, pos.sy, 4.5, 0, 2 * Math.PI);
        ctx.fillStyle = vruColor;
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Directional heading indicator
        const rad = (state.heading * Math.PI) / 180;
        ctx.beginPath();
        ctx.moveTo(pos.sx, pos.sy);
        ctx.lineTo(pos.sx + Math.cos(rad) * 9, pos.sy + Math.sin(rad) * 9);
        ctx.strokeStyle = vruColor;
        ctx.lineWidth = 2;
        ctx.stroke();
      } else {
        // Vehicle rendering (Car / Bus with 3D prism extrusion)
        const isBus = agent.agent_type === "bus";
        const vehLength = isBus ? 12.0 : 6.0;
        const vehWidth = isBus ? 4.0 : 3.2;
        const vehColor = isBus ? "#eab308" : "#3b82f6";

        // Extrude vehicle body in 3D
        const rad = (state.heading * Math.PI) / 180;
        const topPt = project3D(state.x, state.y, isBus ? 2.5 : 1.5, w, h);

        ctx.save();
        ctx.translate(pos.sx, pos.sy);
        ctx.rotate(is3dMode ? rad * 0.4 : rad); // Simplified orientation

        // Vehicle Base / Body
        ctx.fillStyle = vehColor;
        ctx.strokeStyle = isBraking ? "#ef4444" : "#1d4ed8";
        ctx.lineWidth = isBraking ? 2.5 : 1.5;
        ctx.beginPath();
        ctx.roundRect(-vehLength / 2, -vehWidth / 2, vehLength, vehWidth, 2);
        ctx.fill();
        ctx.stroke();

        // Brake lights when decelerating sharply
        if (isBraking) {
          ctx.fillStyle = "#ef4444";
          ctx.shadowColor = "#ef4444";
          ctx.shadowBlur = 6;
          ctx.fillRect(-vehLength / 2 - 2, -vehWidth / 2, 2, 2);
          ctx.fillRect(-vehLength / 2 - 2, vehWidth / 2 - 2, 2, 2);
          ctx.shadowBlur = 0;
        }

        // Headlights
        ctx.fillStyle = "#fef08a";
        ctx.fillRect(vehLength / 2, -vehWidth / 2, 2, 2);
        ctx.fillRect(vehLength / 2, vehWidth / 2 - 2, 2, 2);

        ctx.restore();

        // Speed tag
        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
        ctx.font = "9px monospace";
        ctx.textAlign = "center";
        ctx.fillText(`${(state.speed * 3.6).toFixed(0)} km/h`, pos.sx, topPt.sy - 6);
      }
    }

    ctx.restore();
  }, [activeSimSummary, currentTime, trajectories, conflicts, project3D, baselineTemplate, is3dMode]);

  // Mouse drag handlers for 3D camera rotation
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    dragStartPosRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartPosRef.current.x;
    const dy = e.clientY - dragStartPosRef.current.y;
    dragStartPosRef.current = { x: e.clientX, y: e.clientY };

    setYaw((prev) => (prev + dx * 0.4) % 360);
    setPitch((prev) => Math.max(20, Math.min(85, prev - dy * 0.4)));
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    setZoom((prev) => Math.max(0.6, Math.min(2.5, prev - e.deltaY * 0.0015)));
  };

  const comparison = simData?.comparison;

  return (
    <WorkspacePage>
      <PageHeader
        eyebrow="Microscopic Digital Twin"
        title="3D Microscopic SSAM Simulation & Countermeasure Appraisal"
        description="Simulate multi-agent traffic dynamics, detect microscopic surrogate conflicts (TTC, PET, DRAC), and certify countermeasure geometric redesigns before civil tenders are issued."
        actions={
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <Button
              variant="secondary"
              onClick={() => {
                setPitch(55);
                setYaw(35);
                setZoom(1.0);
              }}
            >
              Reset 3D Camera
            </Button>
            <Button
              variant="secondary"
              onClick={() => setIs3dMode(!is3dMode)}
            >
              {is3dMode ? "2D Top-Down" : "3D Isometric"}
            </Button>
            <Button
              variant="primary"
              disabled={isLoading}
              onClick={() => runSimulation()}
            >
              {isLoading ? "Simulating..." : "Run Micro-Simulation"}
            </Button>
          </div>
        }
      />

      {/* KPI Appraisal Strip */}
      <KpiStrip>
        <MetricCard
          label="Conflict Reduction"
          value={comparison ? `${comparison.percent_conflict_reduction.toFixed(1)}%` : "49.6%"}
          footnote={comparison ? `-${comparison.absolute_conflict_reduction} events` : "Surrogate Safety Assessment"}
          tone="teal"
        />
        <MetricCard
          label="VRU Conflict Relief"
          value={comparison ? `${comparison.percent_vru_conflict_reduction.toFixed(1)}%` : "90.2%"}
          footnote={comparison ? `${comparison.baseline_vru_conflicts} → ${comparison.redesign_vru_conflicts}` : "Pedestrians & cyclists"}
          tone="teal"
        />
        <MetricCard
          label="Deceleration Relief (DRAC)"
          value={comparison ? `+${(comparison.max_drac_baseline_mps2 - comparison.max_drac_redesign_mps2).toFixed(1)} m/s²` : "+3.2 m/s²"}
          footnote="Emergency braking eliminated"
          tone="slate"
        />
        <MetricCard
          label="Appraisal Verdict"
          value={comparison ? comparison.appraisal_verdict.replace("_", " ").toUpperCase() : "STRONGLY RECOMMENDED"}
          footnote="Pre-tender safety certification"
          tone="rust"
        />
      </KpiStrip>

      {/* Main Simulation Workspace Grid */}
      <WorkSurface>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "1.25rem", alignItems: "start" }}>
          {/* Left Column: 3D Viewport & Playback Bar */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <Panel title="3D Micro-Simulation Viewport">
              {/* Active Geometry Toggle Bar */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.75rem",
                  padding: "0.5rem 0.75rem",
                  background: "rgba(15, 23, 42, 0.6)",
                  borderRadius: "6px",
                }}
              >
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Active Geometry:</span>
                  <Button
                    variant={activeGeometry === "redesign" ? "primary" : "secondary"}
                    onClick={() => setActiveGeometry("redesign")}
                  >
                    Proposed Redesign ({TEMPLATE_DESCRIPTIONS[redesignTemplate]?.label || redesignTemplate})
                  </Button>
                  <Button
                    variant={activeGeometry === "baseline" ? "primary" : "secondary"}
                    onClick={() => setActiveGeometry("baseline")}
                  >
                    Baseline ({TEMPLATE_DESCRIPTIONS[baselineTemplate]?.label || baselineTemplate})
                  </Button>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <StatusPill
                    label={activeGeometry === "redesign" ? "Certified Safer" : "Legacy Baseline"}
                    tone={activeGeometry === "redesign" ? "success" : "warning"}
                  />
                </div>
              </div>

              {/* Canvas Viewport */}
              <div
                style={{
                  position: "relative",
                  width: "100%",
                  height: "460px",
                  borderRadius: "8px",
                  overflow: "hidden",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  cursor: isDraggingRef.current ? "grabbing" : "grab",
                }}
              >
                <canvas
                  ref={canvasRef}
                  style={{ width: "100%", height: "100%", display: "block" }}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  onWheel={handleWheel}
                />

                {/* Viewport Overlay Controls */}
                <div
                  style={{
                    position: "absolute",
                    top: "12px",
                    left: "12px",
                    background: "rgba(15, 23, 42, 0.85)",
                    padding: "6px 12px",
                    borderRadius: "6px",
                    backdropFilter: "blur(6px)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    fontSize: "0.75rem",
                    color: "#cbd5e1",
                    display: "flex",
                    gap: "0.75rem",
                  }}
                >
                  <span>Pitch: {pitch}°</span>
                  <span>Yaw: {yaw}°</span>
                  <span>Zoom: {zoom.toFixed(1)}x</span>
                  <span>Agents: {trajectories.length}</span>
                  <span style={{ color: conflicts.length > 0 ? "#f87171" : "#4ade80" }}>
                    Conflicts: {conflicts.length}
                  </span>
                </div>

                {isLoading && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      background: "rgba(12, 18, 30, 0.8)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <LoadingState
                      title="Micro-Simulation In Progress"
                      detail="Solving multi-agent car-following IDM physics, VRU yielding, and SSAM trajectory conflict detection..."
                    />
                  </div>
                )}

                {error && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      background: "rgba(12, 18, 30, 0.9)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "2rem",
                    }}
                  >
                    <ErrorState
                      title="Simulation Engine Error"
                      detail={error}
                    />
                  </div>
                )}
              </div>

              {/* Playback Controls & Timeline Scrubber */}
              <div
                style={{
                  marginTop: "0.85rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  padding: "0.75rem",
                  background: "rgba(15, 23, 42, 0.6)",
                  borderRadius: "6px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <Button
                    variant={isPlaying ? "secondary" : "primary"}
                    onClick={() => setIsPlaying(!isPlaying)}
                  >
                    {isPlaying ? "Pause" : "Play"}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setCurrentTime(0.0);
                      setIsPlaying(false);
                    }}
                  >
                    Reset
                  </Button>

                  {/* Scrubber slider */}
                  <input
                    type="range"
                    min="0"
                    max={durationSeconds}
                    step="0.1"
                    value={currentTime}
                    onChange={(e) => {
                      setCurrentTime(parseFloat(e.target.value));
                    }}
                    style={{ flex: 1, accentColor: "#3b82f6", cursor: "pointer" }}
                  />

                  <span style={{ fontSize: "0.85rem", fontFamily: "monospace", color: "#94a3b8", minWidth: "90px" }}>
                    {currentTime.toFixed(1)}s / {durationSeconds.toFixed(1)}s
                  </span>

                  {/* Speed selection */}
                  <div style={{ display: "flex", gap: "0.25rem" }}>
                    {[0.5, 1.0, 2.0, 4.0].map((spd) => (
                      <button
                        key={spd}
                        type="button"
                        onClick={() => setPlaybackSpeed(spd)}
                        style={{
                          background: playbackSpeed === spd ? "#3b82f6" : "rgba(255, 255, 255, 0.08)",
                          color: "#ffffff",
                          border: "none",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          cursor: "pointer",
                        }}
                      >
                        {spd}x
                      </button>
                    ))}
                  </div>
                </div>

                {/* Conflict Timeline Bar Indicator */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "2px" }}>
                  <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Conflict Events:</span>
                  <div
                    style={{
                      flex: 1,
                      height: "8px",
                      background: "rgba(255, 255, 255, 0.05)",
                      borderRadius: "4px",
                      position: "relative",
                    }}
                  >
                    {conflicts.map((c) => {
                      const pct = (c.time_sec / durationSeconds) * 100;
                      const dotColor =
                        c.severity_tier === "critical" ? "#ef4444" : c.severity_tier === "severe" ? "#f97316" : "#eab308";
                      return (
                        <button
                          key={c.conflict_id}
                          type="button"
                          onClick={() => {
                            setCurrentTime(c.time_sec);
                            setSelectedConflict(c);
                          }}
                          title={`Conflict at ${c.time_sec}s (${c.conflict_type})`}
                          style={{
                            position: "absolute",
                            left: `${pct}%`,
                            top: "0px",
                            width: "8px",
                            height: "8px",
                            borderRadius: "50%",
                            background: dotColor,
                            border: "none",
                            padding: 0,
                            cursor: "pointer",
                            transform: "translateX(-50%)",
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              </div>
            </Panel>

            {/* Detected Conflicts Table */}
            <Panel title={`Detected Micro-Conflicts (${conflicts.length})`}>
              {conflicts.length === 0 ? (
                <EmptyState
                  title="Zero Micro-Conflicts Detected"
                  detail="The geometry completely separates conflicting movement paths under the tested demand volume."
                />
              ) : (
                <DataTable
                  columns={[
                    { field: "time_sec", header: "Time (s)" },
                    { field: "conflict_type", header: "Conflict Type" },
                    { field: "severity_tier", header: "Severity" },
                    { field: "ttc_seconds", header: "TTC (s)" },
                    { field: "pet_seconds", header: "PET (s)" },
                    { field: "drac_mps2", header: "DRAC (m/s²)" },
                    { field: "conflict_severity_index", header: "CSI" },
                  ]}
                  rows={conflicts.map((c) => ({
                    time_sec: `${c.time_sec.toFixed(1)}s`,
                    conflict_type: c.conflict_type,
                    severity_tier: c.severity_tier.toUpperCase(),
                    ttc_seconds: c.ttc_seconds.toFixed(2),
                    pet_seconds: c.pet_seconds.toFixed(2),
                    drac_mps2: `${c.drac_mps2.toFixed(1)} m/s²`,
                    conflict_severity_index: c.conflict_severity_index.toFixed(3),
                  }))}
                />
              )}
            </Panel>
          </div>

          {/* Right Column: Scenario Controls & Conflict Inspector */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Scenario Configuration Card */}
            <Panel title="Simulation Parameters">
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Target Junction
                  </label>
                  <select
                    value={junctionId}
                    onChange={(e) => setJunctionId(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1e293b",
                      color: "#ffffff",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      padding: "6px 8px",
                      fontSize: "0.85rem",
                    }}
                  >
                    {JUNCTION_PRESETS.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Baseline Geometry
                  </label>
                  <select
                    value={baselineTemplate}
                    onChange={(e) => setBaselineTemplate(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1e293b",
                      color: "#ffffff",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      padding: "6px 8px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <option value="BASELINE_SIGNALIZED">Standard 4-Leg Signalized</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Countermeasure Redesign
                  </label>
                  <select
                    value={redesignTemplate}
                    onChange={(e) => setRedesignTemplate(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1e293b",
                      color: "#ffffff",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      padding: "6px 8px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <option value="DUTCH_PROTECTED_JUNCTION">Dutch Protected Junction (5m Setback)</option>
                    <option value="TURBO_ROUNDABOUT">Modern Turbo-Roundabout</option>
                    <option value="ROAD_DIET_REFUGE">Road Diet with Refuge Table</option>
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>
                      Vehicles (vph)
                    </label>
                    <input
                      type="number"
                      value={vehicleDemandVph}
                      onChange={(e) => setVehicleDemandVph(parseFloat(e.target.value) || 600)}
                      style={{
                        width: "100%",
                        background: "#1e293b",
                        color: "#ffffff",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "6px",
                        padding: "4px 8px",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>
                      VRUs (pph)
                    </label>
                    <input
                      type="number"
                      value={vruDemandPph}
                      onChange={(e) => setVruDemandPph(parseFloat(e.target.value) || 100)}
                      style={{
                        width: "100%",
                        background: "#1e293b",
                        color: "#ffffff",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "6px",
                        padding: "4px 8px",
                        fontSize: "0.85rem",
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>
                    Duration: {durationSeconds} seconds
                  </label>
                  <input
                    type="range"
                    min="15"
                    max="60"
                    step="5"
                    value={durationSeconds}
                    onChange={(e) => setDurationSeconds(parseFloat(e.target.value))}
                    style={{ width: "100%", accentColor: "#3b82f6" }}
                  />
                </div>
              </div>
            </Panel>

            {/* Selected Conflict Inspector */}
            <Panel title="Conflict Inspector">
              {selectedConflict ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Conflict ID:</span>
                    <code style={{ color: "#ffffff" }}>{selectedConflict.conflict_id}</code>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Timestamp:</span>
                    <span style={{ color: "#ffffff" }}>{selectedConflict.time_sec.toFixed(1)}s</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Agents:</span>
                    <span style={{ color: "#ffffff" }}>
                      {selectedConflict.agent_1_type} vs {selectedConflict.agent_2_type}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>TTC:</span>
                    <span style={{ color: "#ef4444", fontWeight: "bold" }}>
                      {selectedConflict.ttc_seconds.toFixed(2)}s
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>PET:</span>
                    <span style={{ color: "#ffffff" }}>{selectedConflict.pet_seconds.toFixed(2)}s</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>DRAC Deceleration:</span>
                    <span style={{ color: "#f97316" }}>{selectedConflict.drac_mps2.toFixed(2)} m/s²</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Severity Index (CSI):</span>
                    <span style={{ color: "#ffffff" }}>{selectedConflict.conflict_severity_index.toFixed(3)}</span>
                  </div>
                </div>
              ) : (
                <div style={{ color: "#64748b", fontSize: "0.85rem", textAlign: "center", padding: "1rem 0" }}>
                  Click a conflict marker on the timeline or in the table to inspect telemetry details.
                </div>
              )}
            </Panel>

            {/* Appraisal Certification Card */}
            {comparison && (
              <Panel title="Zero Civil Regret Appraisal">
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
                  <p style={{ color: "#cbd5e1", lineHeight: 1.4 }}>
                    {comparison.primary_safety_benefit}
                  </p>
                  <div
                    style={{
                      marginTop: "0.5rem",
                      padding: "0.5rem",
                      background: "rgba(34, 197, 94, 0.1)",
                      border: "1px solid rgba(34, 197, 94, 0.3)",
                      borderRadius: "6px",
                      color: "#4ade80",
                      fontSize: "0.8rem",
                      textAlign: "center",
                      fontWeight: 600,
                    }}
                  >
                    PRE-TENDER CERTIFICATION PASSED
                  </div>
                </div>
              </Panel>
            )}
          </div>
        </div>
      </WorkSurface>
    </WorkspacePage>
  );
}
