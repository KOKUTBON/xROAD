"use client";

import { STATIC_DEMO } from "@/lib/demo-mode";

import { apiFetch } from "@/lib/demo-api";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button,
  EmptyState,
  MetricCard,
  Panel,
  StatusPill,
} from "@/components/ui";
import { KpiStrip } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";

const API_BASE_URL = getClientApiBaseUrl();

export type TelematicsStreamItem = {
  event_id: string;
  timestamp: string;
  event_type: string;
  source_type: string;
  severity: "critical" | "severe" | "moderate" | "info";
  segment_id: string;
  latitude: number;
  longitude: number;
  speed_kmh: number;
  peak_accel_g: number;
  secondary_metric?: number;
  vehicle_id?: string;
  description?: string;
};

interface LiveTelematicsFeedProps {
  onEventSelect?: (event: TelematicsStreamItem) => void;
  selectedEventId?: string | null;
}

export function LiveTelematicsFeed({ onEventSelect, selectedEventId }: LiveTelematicsFeedProps) {
  const [events, setEvents] = useState<TelematicsStreamItem[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "connecting" | "polling">("connecting");
  const [activeFilter, setActiveFilter] = useState<string>("all");
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch initial recent buffer
  const loadRecentEvents = useCallback(async () => {
    try {
      const res = await apiFetch(`${API_BASE_URL}/v1/telematics/events/recent?limit=25`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.events)) {
          setEvents(data.events);
        }
      }
    } catch {
      // Ignore initial fetch errors
    }
  }, []);

  // Connect WebSocket with fallback
  useEffect(() => {
    loadRecentEvents();
    if (STATIC_DEMO) {
      setConnectionStatus("polling");
      return;
    }

    let isSubscribed = true;
    let wsUrl = "ws://localhost:8000/v1/telematics/stream";
    if (typeof window !== "undefined") {
      const host = window.location.hostname || "localhost";
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${proto}//${host}:8000/v1/telematics/stream`;
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isSubscribed) setConnectionStatus("connected");
      };

      ws.onmessage = (evt) => {
        if (!isSubscribed) return;
        try {
          const payload = JSON.parse(evt.data);
          if (payload.type === "telematics_event" && payload.event) {
            setEvents((prev) => [payload.event, ...prev.slice(0, 49)]);
          } else if (payload.type === "connected" && Array.isArray(payload.recent_events)) {
            setEvents((prev) => {
              const existingIds = new Set(prev.map((e) => e.event_id));
              const newItems = payload.recent_events.filter((e: TelematicsStreamItem) => !existingIds.has(e.event_id));
              return [...newItems, ...prev].slice(0, 50);
            });
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        if (isSubscribed) {
          setConnectionStatus("polling");
        }
      };

      ws.onclose = () => {
        if (isSubscribed) {
          setConnectionStatus("polling");
        }
      };
    } catch {
      setConnectionStatus("polling");
    }

    // Fallback polling if WS fails
    pollTimerRef.current = setInterval(async () => {
      if (connectionStatus === "polling") {
        await loadRecentEvents();
      }
    }, 4000);

    return () => {
      isSubscribed = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [connectionStatus, loadRecentEvents]);

  // Filter items
  const filteredEvents = events.filter((e) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "braking") return e.event_type === "harsh_braking";
    if (activeFilter === "speed_drop") return e.event_type === "sudden_speed_drop";
    if (activeFilter === "micromobility") {
      return (
        e.event_type === "sidewalk_riding" ||
        e.event_type === "curb_impact" ||
        e.event_type === "evasive_swerve"
      );
    }
    return true;
  });

  const criticalCount = events.filter((e) => e.severity === "critical").length;
  const severeCount = events.filter((e) => e.severity === "severe").length;

  return (
    <Panel title="Real-Time Telematics & Micromobility Feed">
      {/* Header & Status Indicator */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
          padding: "0.6rem 0.8rem",
          background: "rgba(15, 23, 42, 0.7)",
          borderRadius: "6px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: connectionStatus === "connected" ? "#22c55e" : "#eab308",
              boxShadow: connectionStatus === "connected" ? "0 0 10px #22c55e" : "none",
              display: "inline-block",
            }}
          />
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>
            {connectionStatus === "connected"
              ? "LIVE WEBSOCKET STREAM"
              : connectionStatus === "connecting"
              ? "CONNECTING STREAM..."
              : "POLLING TELEMETRY GATEWAY"}
          </span>
        </div>
        
      </div>

      {/* Stream Metrics Strip */}
      <KpiStrip>
        <MetricCard
          label="Sliding Buffer"
          value={events.length}
          footnote="Recent in-memory ring buffer"
          tone="slate"
        />
        <MetricCard
          label="Critical Near-Misses"
          value={criticalCount}
          footnote="Emergency braking / curb strikes"
          tone="rust"
        />
        <MetricCard
          label="Severe Incursions"
          value={severeCount}
          footnote="Sidewalk riding & swerves"
          tone="teal"
        />
      </KpiStrip>

      {/* Filter Tabs */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          margin: "1rem 0 0.75rem",
          flexWrap: "wrap",
        }}
      >
        {[
          { key: "all", label: "All Telemetry" },
          { key: "braking", label: "Harsh Braking" },
          { key: "speed_drop", label: "Speed Drops" },
          { key: "micromobility", label: "Micromobility (VRU)" },
        ].map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setActiveFilter(f.key)}
            style={{
              background: activeFilter === f.key ? "#1d4ed8" : "rgba(255, 255, 255, 0.06)",
              color: "#ffffff",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              padding: "4px 10px",
              borderRadius: "6px",
              fontSize: "0.78rem",
              cursor: "pointer",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Live Stream List */}
      <div
        style={{
          maxHeight: "360px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        {filteredEvents.length === 0 ? (
          <EmptyState
            title="Waiting for Live Field Telemetry"
            detail="Connected vehicles and shared micromobility fleets will broadcast kinematic events in real time."
          />
        ) : (
          filteredEvents.map((evt) => {
            const isSelected = selectedEventId === evt.event_id;
            const timeFormatted = new Date(evt.timestamp).toLocaleTimeString();
            return (
              <div
                key={evt.event_id}
                onClick={() => onEventSelect && onEventSelect(evt)}
                style={{
                  padding: "0.6rem 0.8rem",
                  background: isSelected ? "rgba(59, 130, 246, 0.18)" : "rgba(255, 255, 255, 0.03)",
                  border: isSelected
                    ? "1px solid #3b82f6"
                    : "1px solid rgba(255, 255, 255, 0.07)",
                  borderRadius: "6px",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  transition: "background 150ms ease",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <StatusPill
                      label={evt.severity.toUpperCase()}
                      tone={
                        evt.severity === "critical"
                          ? "danger"
                          : evt.severity === "severe"
                          ? "warning"
                          : "neutral"
                      }
                    />
                    <strong style={{ fontSize: "0.85rem", color: "#f1f5f9" }}>
                      {evt.event_type.replace(/_/g, " ").toUpperCase()}
                    </strong>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8", fontFamily: "monospace" }}>
                    {timeFormatted}
                  </span>
                </div>

                <p style={{ margin: "2px 0", fontSize: "0.8rem", color: "#cbd5e1" }}>
                  {evt.description || `Kinematic anomaly on ${evt.segment_id}`}
                </p>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "0.75rem",
                    color: "#64748b",
                    fontFamily: "monospace",
                  }}
                >
                  <span>Speed: {evt.speed_kmh} km/h</span>
                  <span>Peak a: {evt.peak_accel_g > 0 ? `+${evt.peak_accel_g}g` : `${evt.peak_accel_g}g`}</span>
                  <span>GPS: {evt.latitude.toFixed(4)}, {evt.longitude.toFixed(4)}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}
