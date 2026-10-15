"use client";

import { demoMapStyle } from "@/lib/demo-map-style";

import { demoCenter } from "@/lib/demo-city";

import { STATIC_DEMO, publicAsset } from "@/lib/demo-mode";

import { apiFetch } from "@/lib/demo-api";

import * as maplibregl from "maplibre-gl";
import type { FilterSpecification, StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  CLIMATE_RISK_BANDS,
  HAZARD_KINDS,
  type ClimateFeature,
  type ClimateFeatureCollection,
  type HazardKind,
  hazardLabel,
  summarizeClimate,
} from "@/lib/climate-overlay";
import { FilterBar, NavChip, Panel, PageHeader, WarningState } from "@/components/ui";
import { KpiCard } from "@/components/composites";
import { KpiStrip, WorkspacePage } from "@/components/layout";

const CARTO_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>';

const BASE_STYLE: StyleSpecification = {
  version: 8,
  name: "Climate resilience canvas",
  sources: {
    "carto-voyager": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 20,
      attribution: CARTO_ATTRIBUTION,
    },
  },
  layers: [{ id: "carto-voyager", type: "raster", source: "carto-voyager" }],
};

const SURFACE_URL = publicAsset(STATIC_DEMO ? "/demo/climate_risk_surface.geojson" : "/climate/climate_risk_surface.geojson");
const FORECAST_URL = publicAsset(STATIC_DEMO ? "/demo/forecast_risk_surface.geojson" : "/climate/forecast_risk_surface.geojson");
const ALERTS_URL = publicAsset(STATIC_DEMO ? "/demo/weather_alerts.json" : "/climate/weather_alerts.json");
const SOURCE_ID = "climate-risk";

// Step expression: colour each point by its climate-risk band threshold.
const CIRCLE_COLOR: maplibregl.ExpressionSpecification = [
  "step",
  ["get", "climate_risk_score"],
  CLIMATE_RISK_BANDS[0].color,
  CLIMATE_RISK_BANDS[1].min,
  CLIMATE_RISK_BANDS[1].color,
  CLIMATE_RISK_BANDS[2].min,
  CLIMATE_RISK_BANDS[2].color,
  CLIMATE_RISK_BANDS[3].min,
  CLIMATE_RISK_BANDS[3].color,
];

function hazardFilter(hazard: HazardKind | null): FilterSpecification | null {
  if (hazard === null) {
    return null;
  }
  return ["==", ["get", "dominant_hazard"], hazard];
}

export function ClimateMap() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [collection, setCollection] = useState<ClimateFeatureCollection | null>(null);
  const [hazard, setHazard] = useState<HazardKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forecast, setForecast] = useState<ClimateFeatureCollection | null>(null);
  const [forecastTimes, setForecastTimes] = useState<string[]>([]);
  const [forecastIndex, setForecastIndex] = useState(0);
  const [alerts, setAlerts] = useState<Array<{ alert_id: string; message: string; minimum_model_confidence: number }>>([]);

  // Load the static climate-risk surface once.
  useEffect(() => {
    let cancelled = false;
    apiFetch(SURFACE_URL, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load climate surface (${response.status})`);
        }
        return response.json() as Promise<ClimateFeatureCollection>;
      })
      .then((data) => {
        if (!cancelled) {
          setCollection(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load climate data");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void apiFetch(FORECAST_URL, { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const payload = (await response.json()) as {
        type: "FeatureCollection";
        features: Array<{
          type: "Feature";
          geometry: { type: "Point"; coordinates: [number, number] };
          properties: {
            segment_id: string;
            forecast_at_utc: string;
            risk_score: number;
            condition: string;
            risk_multiplier: number;
          };
        }>;
      };
      const times = [...new Set(payload.features.map((feature) => feature.properties.forecast_at_utc))].sort();
      setForecastTimes(times);
      setForecast({
        type: "FeatureCollection",
        features: payload.features.map((feature) => ({
          type: "Feature",
          geometry: feature.geometry,
          properties: {
            segment_id: feature.properties.segment_id,
            climate_risk_score: feature.properties.risk_score,
            dominant_hazard:
              feature.properties.condition === "wet" ? "flood"
              : feature.properties.condition === "snow_ice" || feature.properties.condition === "freezing" ? "snow_ice"
              : feature.properties.condition === "high_wind" ? "wind"
              : feature.properties.condition === "heat" ? "heat"
              : null,
            weather_conditioned_multiplier: feature.properties.risk_multiplier,
            forecast_at_utc: feature.properties.forecast_at_utc,
          },
        })),
      });
    });
    void apiFetch(ALERTS_URL, { cache: "no-store" }).then(async (response) => {
      if (response.ok) setAlerts(((await response.json()) as { alerts: typeof alerts }).alerts);
    });
  }, []);

  const displayedCollection = useMemo(() => {
    if (!forecast || !forecastTimes.length) return collection;
    const selectedTime = forecastTimes[forecastIndex];
    return {
      type: "FeatureCollection" as const,
      features: forecast.features.filter(
        (feature) => feature.properties.forecast_at_utc === selectedTime,
      ),
    };
  }, [collection, forecast, forecastIndex, forecastTimes]);

  // Initialise the map and the climate layer once data is available.
  useEffect(() => {
    if (!containerRef.current || !collection || mapRef.current) {
      return;
    }
    maplibregl.setWorkerUrl(publicAsset("/maplibre/maplibre-gl-worker.mjs"));
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: demoMapStyle(BASE_STYLE),
      center: demoCenter([16.85, 41.05]),
      zoom: 8,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.AttributionControl({ compact: true }));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    // The container can gain its real width *after* the map initialises (client
    // navigation into this route), and MapLibre sizes its canvas to whatever the
    // container measured at init. Observe the container and resize so the map
    // fills it once laid out.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      map.addSource(SOURCE_ID, { type: "geojson", data: collection });
      map.addLayer({
        id: "climate-risk-circles",
        type: "circle",
        source: SOURCE_ID,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 4, 12, 10],
          "circle-color": CIRCLE_COLOR,
          "circle-opacity": 0.85,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "climate-risk-circles", (event) => {
        const feature = event.features?.[0] as unknown as ClimateFeature | undefined;
        if (!feature) {
          return;
        }
        const props = feature.properties;
        new maplibregl.Popup({ closeButton: true })
          .setLngLat(event.lngLat)
          .setHTML(
            `<strong>${props.segment_id}</strong><br/>` +
              `Climate risk: <b>${props.climate_risk_score}</b><br/>` +
              `Dominant hazard: ${hazardLabel(props.dominant_hazard)}`,
          )
          .addTo(map);
      });
      map.on("mouseenter", "climate-risk-circles", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "climate-risk-circles", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [collection]);

  // Apply the hazard filter live.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer?.("climate-risk-circles")) {
      return;
    }
    map.setFilter("climate-risk-circles", hazardFilter(hazard));
  }, [hazard]);

  useEffect(() => {
    const source = mapRef.current?.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (source && displayedCollection) source.setData(displayedCollection);
  }, [displayedCollection]);

  const summary = useMemo(
    () => (displayedCollection ? summarizeClimate(displayedCollection.features) : null),
    [displayedCollection],
  );

  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Climate resilience"
          title="Where extreme weather most degrades road-network safety."
          description="Road sections coloured by their climate-risk score, so resilience works can target where hazards and traffic risk overlap."
          meta={<NavChip>Climate overlay</NavChip>}
        />
      }
    >
      <FilterBar
        summary={<span>The hazard filter updates the map and the summary together.</span>}
      >
        <label>
          <span>Hazard</span>
          <select
            aria-label="Filter by dominant hazard"
            value={hazard ?? ""}
            onChange={(event) => setHazard((event.target.value || null) as HazardKind | null)}
          >
            <option value="">All hazards</option>
            {HAZARD_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {hazardLabel(kind)}
              </option>
            ))}
          </select>
        </label>
        {forecastTimes.length ? (
          <label>
            <span>Forecast hour · {forecastTimes[forecastIndex]}</span>
            <input
              aria-label="Forecast hour"
              type="range"
              min="0"
              max={forecastTimes.length - 1}
              value={forecastIndex}
              onChange={(event) => setForecastIndex(Number(event.target.value))}
            />
          </label>
        ) : null}
      </FilterBar>

      {error ? (
        <WarningState title="Climate surface unavailable" detail={error} tone="danger" />
      ) : null}

      {summary ? (
        <KpiStrip min="180px">
          <KpiCard label="Sections" value={summary.total} />
          <KpiCard label="Mean risk" value={summary.meanScore} />
          <KpiCard label="High-risk (≥50)" value={summary.highRisk} />
          <KpiCard label="Peak risk" value={summary.maxScore} />
        </KpiStrip>
      ) : null}

      {forecastTimes.length ? (
        <WarningState
          title={`${alerts.length} operational weather alerts`}
          detail={
            alerts[0]?.message ??
            "Forecast risk is shown as network bands with uncertainty, not individual crash predictions."
          }
        />
      ) : null}

      <Panel
        accent="teal"
        title="Climate risk map"
        detail="Points are road sections; colour is the climate-risk band. Pan and zoom to inspect a corridor."
      >
        <div className="climate-map-canvas" ref={containerRef} role="application" aria-label="Climate risk map" />
        <ul className="climate-legend" aria-label="Climate risk legend">
          {CLIMATE_RISK_BANDS.map((band) => (
            <li key={band.id}>
              <span className="climate-legend-swatch" style={{ background: band.color }} aria-hidden="true" />
              {band.label} ({band.min}+)
            </li>
          ))}
        </ul>
      </Panel>
    </WorkspacePage>
  );
}
