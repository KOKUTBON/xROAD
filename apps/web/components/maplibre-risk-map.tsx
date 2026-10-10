"use client";

import { demoMapStyle } from "@/lib/demo-map-style";

import { publicAsset } from "@/lib/demo-mode";

import * as maplibregl from "maplibre-gl";
import type {
  ExpressionSpecification,
  FilterSpecification,
  LayerSpecification,
  MapLayerMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  featureBand,
  featureIdentifier,
  featureLabel,
  formatDetailValue,
  type GeoJsonFeature,
  type GeoJsonFeatureCollection,
  type ScoreBand,
} from "@/lib/risk-map";
import {
  mapFallbackColor,
  mapLayerColors,
  riskBandColors,
  rgbaFromHex,
} from "@/lib/semantic-colors";
import { MapLegend } from "@/components/map-legend";
import { useTheme } from "@/components/theme-provider";
import { SegmentedControl } from "@/components/ui";

export type MapLayerTone = "tiles" | "segments" | "junctions" | "crossings";

export interface MapLibreLayerSpec {
  key: string;
  label: string;
  tone: MapLayerTone;
  features: GeoJsonFeature[];
  active: boolean;
}

// Free, no-API-key street basemap (CARTO Voyager raster tiles) so risk tiles
// sit on real streets and place names. Neutral palette keeps the risk colors
// dominant. Attribution is required and surfaced via AttributionControl.
const CARTO_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>';
const ESRI_ATTRIBUTION =
  "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community";

type BasemapMode = "streets" | "satellite";

const ROAD_RISK_STYLE: StyleSpecification = {
  version: 8,
  name: "Road risk municipal canvas",
  sources: {
    // Streets: CARTO Voyager raster (free, no key, neutral, labels built in).
    "carto-voyager": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 20,
      attribution: CARTO_ATTRIBUTION,
    },
    // Night-ops streets: CARTO Dark Matter, used for the streets basemap
    // while the dark appearance is active so the canvas matches the chrome.
    "carto-dark": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
        "https://d.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 20,
      attribution: CARTO_ATTRIBUTION,
    },
    // Satellite: Esri World Imagery (free, no key).
    "esri-imagery": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution: ESRI_ATTRIBUTION,
    },
    // Label-only overlay so place/street names stay readable over imagery.
    "carto-labels": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 20,
      attribution: CARTO_ATTRIBUTION,
    },
  },
  layers: [
    {
      id: "road-risk-background",
      type: "background",
      paint: {
        "background-color": mapLayerColors.basemap,
      },
    },
    {
      id: "carto-voyager-basemap",
      type: "raster",
      source: "carto-voyager",
      paint: { "raster-opacity": 1 },
    },
    {
      id: "carto-dark-basemap",
      type: "raster",
      source: "carto-dark",
      layout: { visibility: "none" },
    },
    {
      id: "esri-imagery-basemap",
      type: "raster",
      source: "esri-imagery",
      layout: { visibility: "none" },
    },
    {
      id: "carto-labels-basemap",
      type: "raster",
      source: "carto-labels",
      layout: { visibility: "none" },
    },
  ],
};

const BAND_COLORS: Record<ScoreBand, string> = {
  low: riskBandColors.low.fill,
  moderate: riskBandColors.moderate.fill,
  high: riskBandColors.high.fill,
  very_high: riskBandColors.very_high.fill,
};

function riskColorExpression(): ExpressionSpecification {
  return [
    "case",
    ["==", ["get", "__band"], "very_high"],
    BAND_COLORS.very_high,
    ["==", ["get", "__band"], "high"],
    BAND_COLORS.high,
    ["==", ["get", "__band"], "moderate"],
    BAND_COLORS.moderate,
    ["==", ["get", "__band"], "low"],
    BAND_COLORS.low,
    ["get", "__fallbackColor"],
  ];
}

function fallbackColor(tone: MapLayerTone): string {
  return mapFallbackColor(tone);
}

function layerSourceId(mapId: string, layerKey: string): string {
  return `${mapId}-${layerKey}-source`;
}

function layerPaintIds(mapId: string, layerKey: string): string[] {
  return [
    `${mapId}-${layerKey}-fill`,
    `${mapId}-${layerKey}-line`,
    `${mapId}-${layerKey}-circle`,
  ];
}

function selectedSourceId(mapId: string): string {
  return `${mapId}-selected-source`;
}

function selectedPaintIds(mapId: string): string[] {
  return [`${mapId}-selected-fill`, `${mapId}-selected-line`, `${mapId}-selected-circle`];
}

function geometryFilter(types: string[]): FilterSpecification {
  return ["in", ["geometry-type"], ["literal", types]] as unknown as FilterSpecification;
}

/** Best-available 0–100 risk score for a feature, used for heatmap weighting. */
function featureScore(feature: GeoJsonFeature): number {
  const properties = feature.properties ?? {};
  const raw =
    properties.public_score_index ??
    properties.tile_max_public_score_index ??
    properties.pedestrian_crossing_priority_score;
  const value = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(value) ? value : 0;
}

function toMapFeature(feature: GeoJsonFeature, layer: MapLibreLayerSpec): GeoJsonFeature {
  return {
    ...feature,
    properties: {
      ...feature.properties,
      __band: featureBand(feature) ?? "",
      __fallbackColor: fallbackColor(layer.tone),
      __featureId: featureIdentifier(feature),
      __featureLabel: featureLabel(feature),
      __layerLabel: layer.label,
      __weight: featureScore(feature),
    },
  };
}

/** Average of a feature's coordinate points — a representative heatmap point. */
function featureCentroid(feature: GeoJsonFeature): [number, number] | null {
  const points: Array<[number, number]> = [];
  collectGeometryPoints(feature.geometry.coordinates, points);
  if (points.length === 0) {
    return null;
  }
  const total = points.reduce<[number, number]>(
    (acc, [x, y]) => [acc[0] + x, acc[1] + y],
    [0, 0],
  );
  return [total[0] / points.length, total[1] / points.length];
}

/** One combined point collection (feature centroids) driving the heatmap. */
function heatmapCollection(layers: MapLibreLayerSpec[]): GeoJsonFeatureCollection {
  const features: GeoJsonFeature[] = [];
  for (const layer of layers) {
    for (const feature of layer.features) {
      const centroid = featureCentroid(feature);
      if (!centroid) {
        continue;
      }
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: centroid },
        properties: { __weight: featureScore(feature) },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

/** Density color ramp built from the ratified risk-ramp token fills. */
function heatmapColorExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["heatmap-density"],
    0,
    rgbaFromHex(riskBandColors.low.fill, 0),
    0.25,
    rgbaFromHex(riskBandColors.low.fill, 0.6),
    0.5,
    rgbaFromHex(riskBandColors.moderate.fill, 0.75),
    0.75,
    rgbaFromHex(riskBandColors.high.fill, 0.85),
    1,
    rgbaFromHex(riskBandColors.very_high.fill, 0.95),
  ];
}

function addHeatmapLayer(
  map: maplibregl.Map,
  mapId: string,
  layers: MapLibreLayerSpec[],
): Array<() => void> {
  const sourceId = `${mapId}-heatmap-source`;
  const layerId = `${mapId}-heatmap-layer`;
  map.addSource(sourceId, {
    type: "geojson",
    data: heatmapCollection(layers) as FeatureCollection,
  });
  map.addLayer({
    id: layerId,
    type: "heatmap",
    source: sourceId,
    paint: {
      "heatmap-weight": ["interpolate", ["linear"], ["get", "__weight"], 0, 0, 100, 1],
      "heatmap-intensity": 1,
      "heatmap-color": heatmapColorExpression(),
      "heatmap-radius": 18,
      "heatmap-opacity": 0.8,
    },
  });
  return [
    () => {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    },
  ];
}

function toFeatureCollection(layer: MapLibreLayerSpec): GeoJsonFeatureCollection {
  return {
    type: "FeatureCollection",
    features: layer.features.map((feature) => toMapFeature(feature, layer)),
  };
}

function collectGeometryPoints(coordinates: unknown, points: Array<[number, number]>): void {
  if (!Array.isArray(coordinates) || coordinates.length === 0) {
    return;
  }
  if (
    coordinates.length >= 2 &&
    typeof coordinates[0] === "number" &&
    typeof coordinates[1] === "number"
  ) {
    points.push([coordinates[0], coordinates[1]]);
    return;
  }
  for (const nested of coordinates) {
    collectGeometryPoints(nested, points);
  }
}

function mapBounds(features: GeoJsonFeature[]): maplibregl.LngLatBounds | null {
  const bounds = new maplibregl.LngLatBounds();
  let hasPoints = false;
  for (const feature of features) {
    const points: Array<[number, number]> = [];
    collectGeometryPoints(feature.geometry.coordinates, points);
    for (const point of points) {
      bounds.extend(point);
      hasPoints = true;
    }
  }
  return hasPoints ? bounds : null;
}

function escapeHtml(value: unknown): string {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function popupHtml(feature: maplibregl.MapGeoJSONFeature): string {
  const properties = feature.properties ?? {};
  const label = properties.__featureLabel ?? "Selected feature";
  const layer = properties.__layerLabel ?? "Risk layer";
  const band = properties.public_score_band ?? properties.tile_public_score_band ?? "n/a";
  const score =
    properties.public_score_index ??
    properties.tile_max_public_score_index ??
    properties.pedestrian_crossing_priority_score ??
    "n/a";

  const exposure = properties.exposure_vkt ? `<span>Exposure: ${escapeHtml(formatDetailValue(properties.exposure_vkt))} VKT</span>` : "";
  const aadt = properties.aadt ? `<span>AADT: ${escapeHtml(formatDetailValue(properties.aadt))}</span>` : "";

  return [
    `<strong>${escapeHtml(label)}</strong>`,
    `<span>${escapeHtml(layer)}</span>`,
    `<span>Band: ${escapeHtml(band)}</span>`,
    `<span>Score: ${escapeHtml(formatDetailValue(score))}</span>`,
    exposure,
    aadt,
  ]
    .filter(Boolean)
    .join("");
}

/** Lightweight hover popover: name + band chip, and a tier chip when present. */
function hoverPopupHtml(feature: maplibregl.MapGeoJSONFeature): string {
  const properties = feature.properties ?? {};
  const label = properties.__featureLabel ?? "Feature";
  const band = properties.public_score_band ?? properties.tile_public_score_band ?? "n/a";
  const tier = properties.publication_tier ?? properties.visibility_tier;
  const exposure = properties.exposure_vkt ? `<span>${escapeHtml(formatDetailValue(properties.exposure_vkt))} VKT</span>` : "";
  return [
    `<strong>${escapeHtml(label)}</strong>`,
    `<span>Band: ${escapeHtml(band)}</span>`,
    tier ? `<span>Tier: ${escapeHtml(tier)}</span>` : "",
    exposure,
  ]
    .filter(Boolean)
    .join("");
}

function isWebglSupported(): boolean {
  if (typeof window === "undefined" || !window.WebGLRenderingContext) {
    return false;
  }
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
  return Boolean(context);
}

function addLayerSet(
  map: maplibregl.Map,
  mapId: string,
  layer: MapLibreLayerSpec,
  onSelectFeature: (featureId: string) => void,
  popupRef: React.MutableRefObject<maplibregl.Popup | null>,
  hoverPopupRef: React.MutableRefObject<maplibregl.Popup | null>,
  extruded = false,
): Array<() => void> {
  const sourceId = layerSourceId(mapId, layer.key);
  const [fillLayerId, lineLayerId, circleLayerId] = layerPaintIds(mapId, layer.key);
  const sourceData = toFeatureCollection(layer);
  const cleanups: Array<() => void> = [];

  map.addSource(sourceId, {
    type: "geojson",
    data: sourceData as FeatureCollection,
  });

  // In 3D mode, extrude polygon tiles by their risk score so high-risk zones
  // literally rise above the city — the tallest blocks read as the hotspots.
  const fillLayer: LayerSpecification = extruded
    ? {
        id: fillLayerId,
        type: "fill-extrusion",
        source: sourceId,
        filter: geometryFilter(["Polygon", "MultiPolygon"]),
        paint: {
          "fill-extrusion-color": riskColorExpression(),
          "fill-extrusion-height": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "__weight"], 0],
            0,
            40,
            100,
            1500,
          ],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.88,
        },
      }
    : {
        id: fillLayerId,
        type: "fill",
        source: sourceId,
        filter: geometryFilter(["Polygon", "MultiPolygon"]),
        paint: {
          "fill-color": riskColorExpression(),
          "fill-opacity": layer.tone === "tiles" ? 0.42 : 0.24,
          "fill-outline-color": rgbaFromHex(mapLayerColors.selectedInk, 0.35),
        },
      };
  const lineLayer: LayerSpecification = {
    id: lineLayerId,
    type: "line",
    source: sourceId,
    filter: geometryFilter(["LineString", "MultiLineString", "Polygon", "MultiPolygon"]),
    paint: {
      "line-color": riskColorExpression(),
      "line-opacity": layer.tone === "tiles" ? 0.72 : 0.92,
      "line-width": layer.tone === "segments" ? 4 : 2,
    },
  };
  const circleLayer: LayerSpecification = {
    id: circleLayerId,
    type: "circle",
    source: sourceId,
    filter: geometryFilter(["Point", "MultiPoint"]),
    paint: {
      "circle-color": riskColorExpression(),
      "circle-radius": layer.tone === "junctions" ? 7 : 6,
      "circle-stroke-color": mapLayerColors.featureStroke,
      "circle-stroke-width": 2,
    },
  };

  for (const mapLayer of [fillLayer, lineLayer, circleLayer]) {
    map.addLayer(mapLayer);
  }

  for (const layerId of [fillLayerId, lineLayerId, circleLayerId]) {
    const clickHandler = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      const featureId = feature?.properties?.__featureId;
      if (typeof featureId === "string") {
        onSelectFeature(featureId);
      }
      if (feature) {
        popupRef.current?.remove();
        popupRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: true,
          className: "risk-map-popup",
          offset: 12,
        })
          .setLngLat(event.lngLat)
          .setHTML(popupHtml(feature))
          .addTo(map);
      }
    };
    const enterHandler = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const moveHandler = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature) {
        return;
      }
      hoverPopupRef.current?.remove();
      hoverPopupRef.current = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: "risk-map-popup risk-map-popup-hover",
        offset: 12,
      })
        .setLngLat(event.lngLat)
        .setHTML(hoverPopupHtml(feature))
        .addTo(map);
    };
    const leaveHandler = () => {
      map.getCanvas().style.cursor = "";
      hoverPopupRef.current?.remove();
      hoverPopupRef.current = null;
    };
    map.on("click", layerId, clickHandler);
    map.on("mouseenter", layerId, enterHandler);
    map.on("mousemove", layerId, moveHandler);
    map.on("mouseleave", layerId, leaveHandler);
    cleanups.push(() => {
      map.off("click", layerId, clickHandler);
      map.off("mouseenter", layerId, enterHandler);
      map.off("mousemove", layerId, moveHandler);
      map.off("mouseleave", layerId, leaveHandler);
    });
  }

  cleanups.push(() => {
    for (const layerId of [fillLayerId, lineLayerId, circleLayerId]) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }
  });

  return cleanups;
}

function updateSelectedFeature(
  map: maplibregl.Map,
  mapId: string,
  feature: GeoJsonFeature | null,
): () => void {
  const sourceId = selectedSourceId(mapId);
  const [fillLayerId, lineLayerId, circleLayerId] = selectedPaintIds(mapId);
  const selectedCollection: GeoJsonFeatureCollection = {
    type: "FeatureCollection",
    features: feature
      ? [
          {
            ...feature,
            properties: {
              ...feature.properties,
              __band: featureBand(feature) ?? "",
              __fallbackColor: mapLayerColors.selectedInk,
            },
          },
        ]
      : [],
  };

  map.addSource(sourceId, {
    type: "geojson",
    data: selectedCollection as FeatureCollection,
  });
  map.addLayer({
    id: fillLayerId,
    type: "fill",
    source: sourceId,
    filter: geometryFilter(["Polygon", "MultiPolygon"]),
    paint: {
      "fill-color": rgbaFromHex(mapLayerColors.selectedFill, 0.42),
      "fill-outline-color": mapLayerColors.selectedInk,
    },
  });
  map.addLayer({
    id: lineLayerId,
    type: "line",
    source: sourceId,
    filter: geometryFilter(["LineString", "MultiLineString", "Polygon", "MultiPolygon"]),
    paint: {
      "line-color": mapLayerColors.selectedInk,
      "line-width": 7,
    },
  });
  map.addLayer({
    id: circleLayerId,
    type: "circle",
    source: sourceId,
    filter: geometryFilter(["Point", "MultiPoint"]),
    paint: {
      "circle-color": mapLayerColors.selectedFill,
      "circle-radius": 10,
      "circle-stroke-color": mapLayerColors.selectedInk,
      "circle-stroke-width": 3,
    },
  });

  return () => {
    for (const layerId of [fillLayerId, lineLayerId, circleLayerId]) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }
  };
}

export function MapLibreRiskMap({
  fallback,
  layers,
  mapId,
  onSelectFeature,
  selectedFeatureId,
  subtitle,
  title,
}: {
  fallback: ReactNode;
  layers: MapLibreLayerSpec[];
  mapId: string;
  onSelectFeature: (featureId: string) => void;
  selectedFeatureId: string | null;
  subtitle: string;
  title: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const hoverPopupRef = useRef<maplibregl.Popup | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [fallbackReason, setFallbackReason] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"choropleth" | "heatmap" | "extrusion">("choropleth");
  const [basemap, setBasemap] = useState<BasemapMode>("streets");
  const { theme } = useTheme();

  const activeLayers = useMemo(() => layers.filter((layer) => layer.active), [layers]);
  const activeFeatures = useMemo(
    () => activeLayers.flatMap((layer) => layer.features),
    [activeLayers],
  );
  const selectedFeature = useMemo(
    () => activeFeatures.find((feature) => featureIdentifier(feature) === selectedFeatureId) ?? null,
    [activeFeatures, selectedFeatureId],
  );
  const shortcutFeatures = activeFeatures.slice(0, 6);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }
    if (!isWebglSupported()) {
      setFallbackReason("WebGL is unavailable in this browser, so the lightweight fallback map is shown.");
      return;
    }

    maplibregl.setWorkerUrl(publicAsset("/maplibre/maplibre-gl-worker.mjs"));
    const map = new maplibregl.Map({
      attributionControl: false,
      container: containerRef.current,
      maxZoom: 16,
      minZoom: 8,
      renderWorldCopies: false,
      style: demoMapStyle(ROAD_RISK_STYLE),
    });
    // Map furniture (#180): compass/reset-north + fullscreen + zoom on the
    // right, scale bottom-left, compact attribution bottom-right.
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.on("load", () => setIsLoaded(true));
    map.on("error", () => {
      setFallbackReason("The interactive map could not initialize, so the fallback map is shown.");
    });
    mapRef.current = map;

    // The container can gain (or change) its width after init — client
    // navigation into the route, the rail collapsing, or the viewport
    // resizing. MapLibre sizes its canvas to whatever the container measured at
    // init, so observe the container and resize to keep the canvas filling it
    // (matches the climate map). #253.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      popupRef.current?.remove();
      hoverPopupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Toggle the active basemap: streets (CARTO Voyager, or Dark Matter in the
  // dark appearance) vs satellite (Esri imagery + a label overlay so place
  // names stay readable).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded || fallbackReason) {
      return;
    }
    const satellite = basemap === "satellite";
    const setVisibility = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    };
    const night = theme === "dark";
    setVisibility("carto-voyager-basemap", !satellite && !night);
    setVisibility("carto-dark-basemap", !satellite && night);
    setVisibility("esri-imagery-basemap", satellite);
    setVisibility("carto-labels-basemap", satellite);
  }, [basemap, isLoaded, fallbackReason, theme]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded || fallbackReason) {
      return;
    }

    const is3D = viewMode === "extrusion";
    const cleanups =
      viewMode === "heatmap"
        ? addHeatmapLayer(map, mapId, activeLayers)
        : activeLayers.flatMap((layer) =>
            addLayerSet(map, mapId, layer, onSelectFeature, popupRef, hoverPopupRef, is3D),
          );
    const cleanupSelected = updateSelectedFeature(map, mapId, selectedFeature);
    const bounds = mapBounds(activeFeatures);
    // Tilt and rotate the camera in 3D mode so extruded risk towers are legible;
    // flatten back to top-down for the 2D modes. Honors prefers-reduced-motion (#180).
    const reduceMotion =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pitch = is3D ? 52 : 0;
    const bearing = is3D ? -18 : 0;
    if (bounds) {
      map.fitBounds(bounds, {
        duration: reduceMotion ? 0 : 600,
        maxZoom: activeFeatures.length <= 1 ? 13 : 14,
        padding: 42,
        pitch,
        bearing,
      });
    } else {
      map.easeTo({ pitch, bearing, duration: reduceMotion ? 0 : 600 });
    }

    return () => {
      cleanupSelected();
      for (const cleanup of cleanups) {
        cleanup();
      }
    };
  }, [activeFeatures, activeLayers, fallbackReason, isLoaded, mapId, onSelectFeature, selectedFeature, viewMode]);

  if (fallbackReason) {
    return (
      <div className="maplibre-fallback-shell">
        <div className="maplibre-fallback-note" role="status">
          <strong>Interactive map fallback</strong>
          <p>{fallbackReason}</p>
        </div>
        {fallback}
      </div>
    );
  }

  return (
    <section className="maplibre-shell" aria-label={title}>
      <div className="maplibre-heading">
        <div>
          <h4>{title}</h4>
          <p>{subtitle}</p>
        </div>
        <div className="maplibre-heading-controls">
          <SegmentedControl
            ariaLabel="Map view mode"
            onChange={setViewMode}
            options={[
              { value: "choropleth", label: "Choropleth" },
              { value: "heatmap", label: "Heatmap" },
              { value: "extrusion", label: "3D" },
            ]}
            value={viewMode}
          />
          <SegmentedControl
            ariaLabel="Basemap"
            onChange={setBasemap}
            options={[
              { value: "streets", label: "Streets" },
              { value: "satellite", label: "Satellite" },
            ]}
            value={basemap}
          />
          <span>{isLoaded ? "MapLibre active" : "Preparing map"}</span>
        </div>
      </div>
      <div className="maplibre-canvas-wrap">
        <div
          aria-label={title}
          className="maplibre-container"
          ref={containerRef}
          role="application"
        />
        <div className="map-legend-overlay">
          <MapLegend orientation="vertical" showMeaning={false} title="Risk band" />
        </div>
      </div>
      <div className="map-feature-shortcuts" aria-label="Map feature shortcuts">
        {shortcutFeatures.map((feature) => {
          const featureId = featureIdentifier(feature);
          const isSelected = featureId === selectedFeatureId;
          return (
            <button
              aria-pressed={isSelected}
              className={`map-feature-shortcut${isSelected ? " map-feature-shortcut-selected" : ""}`}
              key={featureId}
              onClick={() => onSelectFeature(featureId)}
              type="button"
            >
              {featureLabel(feature)}
            </button>
          );
        })}
      </div>
    </section>
  );
}
