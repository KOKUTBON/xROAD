"use client";

import { apiFetch } from "@/lib/demo-api";
import { STATIC_DEMO } from "@/lib/demo-mode";

import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  MapLibreRiskMap,
  type MapLayerTone,
  type MapLibreLayerSpec,
} from "@/components/maplibre-risk-map";
import { LiveTelematicsFeed } from "@/components/live-telematics-feed";
import { usePlatformSession } from "@/components/session-provider";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Eyebrow,
  FilterBar,
  LoadingState,
  MetricCard,
  NavChip,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { WorkspacePage } from "@/components/layout";
import { getClientApiBaseUrl } from "@/lib/api-client";
import {
  buildRiskMapSearchParams,
  normalizeScoreBandFilter,
  parseLayerVisibility,
  serializeLayerVisibility,
} from "@/lib/map-state";
import {
  cityYears,
  featureBand,
  featureIdentifier,
  featureLabel,
  formatCompactNumber,
  formatDetailValue,
  indexSegmentDetails,
  resolvePreferredCity,
  SCORE_BAND_OPTIONS,
  type AnalystRiskMapPayload,
  type GeoJsonFeature,
  type InterventionShortlistPayload,
  type PublicCityRecord,
  type PublicRiskMapPayload,
  type ScoreBandFilter,
} from "@/lib/risk-map";
import {
  mapFallbackColor,
  mapLayerColors,
  riskBandColor,
  riskBandColors,
  rgbaFromHex,
} from "@/lib/semantic-colors";

const API_BASE_URL = getClientApiBaseUrl();
const MAP_VIEWBOX = { width: 980, height: 620, padding: 32 };

interface CityCatalogPayload {
  api_version: string;
  summary_stats: Record<string, unknown>;
  cities: PublicCityRecord[];
}

interface Bounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

async function fetchJson<T>(input: string): Promise<T> {
  const response = await apiFetch(input, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${input}`);
  }
  return (await response.json()) as T;
}

function parseYearParam(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function bandColor(band: string | null, tone: MapLayerTone): string {
  if (tone === "junctions" || tone === "crossings") {
    return mapFallbackColor(tone);
  }
  return riskBandColor(band === "low" || band === "moderate" || band === "high" || band === "very_high" ? band : null);
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

function featurePoints(feature: GeoJsonFeature): Array<[number, number]> {
  const points: Array<[number, number]> = [];
  collectGeometryPoints(feature.geometry.coordinates, points);
  return points;
}

function computeBounds(features: GeoJsonFeature[]): Bounds {
  const points = features.flatMap((feature) => featurePoints(feature));
  if (points.length === 0) {
    return {
      minX: 0,
      maxX: 1,
      minY: 0,
      maxY: 1,
    };
  }
  const xs = points.map(([longitude]) => longitude);
  const ys = points.map(([, latitude]) => latitude);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}

function projectPoint([longitude, latitude]: [number, number], bounds: Bounds): [number, number] {
  const drawableWidth = MAP_VIEWBOX.width - MAP_VIEWBOX.padding * 2;
  const drawableHeight = MAP_VIEWBOX.height - MAP_VIEWBOX.padding * 2;
  const width = Math.max(bounds.maxX - bounds.minX, 0.000001);
  const height = Math.max(bounds.maxY - bounds.minY, 0.000001);
  const x = MAP_VIEWBOX.padding + ((longitude - bounds.minX) / width) * drawableWidth;
  const normalizedY = (latitude - bounds.minY) / height;
  const y = MAP_VIEWBOX.height - MAP_VIEWBOX.padding - normalizedY * drawableHeight;
  return [x, y];
}

function coordinatePath(coordinates: unknown, bounds: Bounds, closePath: boolean): string {
  if (!Array.isArray(coordinates)) {
    return "";
  }
  const points = coordinates.filter(Array.isArray) as Array<[number, number]>;
  if (points.length === 0) {
    return "";
  }
  const [firstX, firstY] = projectPoint(points[0], bounds);
  const parts = [`M ${firstX.toFixed(2)} ${firstY.toFixed(2)}`];
  for (const point of points.slice(1)) {
    const [x, y] = projectPoint(point, bounds);
    parts.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
  }
  if (closePath) {
    parts.push("Z");
  }
  return parts.join(" ");
}

function geometryPaths(feature: GeoJsonFeature, bounds: Bounds): string[] {
  const { geometry } = feature;
  if (geometry.type === "LineString") {
    return [coordinatePath(geometry.coordinates, bounds, false)];
  }
  if (geometry.type === "MultiLineString" && Array.isArray(geometry.coordinates)) {
    return geometry.coordinates.map((part) => coordinatePath(part, bounds, false)).filter(Boolean);
  }
  if (geometry.type === "Polygon" && Array.isArray(geometry.coordinates)) {
    return geometry.coordinates
      .map((ring: unknown) => coordinatePath(ring, bounds, true))
      .filter(Boolean);
  }
  if (geometry.type === "MultiPolygon" && Array.isArray(geometry.coordinates)) {
    return geometry.coordinates
      .flatMap((polygon: unknown) =>
        Array.isArray(polygon)
          ? polygon.map((ring: unknown) => coordinatePath(ring, bounds, true))
          : [],
      )
      .filter(Boolean);
  }
  return [];
}

function featureSummaryRows(
  feature: GeoJsonFeature | null,
  detailRow?: Record<string, string>,
): Array<[string, string]> {
  if (!feature) {
    return [];
  }
  const properties = feature.properties;
  const pairs: Array<[string, unknown]> = [
    ["Label", featureLabel(feature)],
    [
      "Score band",
      properties.public_score_band || properties.tile_public_score_band || detailRow?.public_score_band,
    ],
    [
      "Score index",
      properties.public_score_index ||
        properties.tile_max_public_score_index ||
        detailRow?.public_score_index ||
        properties.pedestrian_crossing_priority_score,
    ],
    ["Predicted crashes", detailRow?.predicted_crash_count],
    ["Observed crashes", detailRow?.observed_crash_count],
    ["Road class", detailRow?.highway || properties.segment_highway],
    ["Protection", properties.crossing_protection_state],
    ["Crash count", properties.crash_count],
    ["Node role", properties.node_role],
  ];
  return pairs
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([label, value]) => [label, formatDetailValue(value)]);
}

function MapLegend() {
  const riskItems = [
    ["minimal", riskBandColors.minimal.label, "legend-minimal"],
    ["low", riskBandColors.low.label, "legend-low"],
    ["moderate", riskBandColors.moderate.label, "legend-moderate"],
    ["high", riskBandColors.high.label, "legend-high"],
    ["very_high", riskBandColors.very_high.label, "legend-very-high"],
  ] as const;
  return (
    <div className="map-legend" aria-label="Risk and support-layer legend">
      {riskItems.map(([, label, className]) => (
        <span className="legend-item" key={className}>
          <span className={`legend-swatch ${className}`} />
          <small>{label}</small>
        </span>
      ))}
      <span className="legend-item">
      <span className="legend-swatch legend-junction" />
      <small>Junctions</small>
      </span>
      <span className="legend-item">
      <span className="legend-swatch legend-crossing" />
      <small>Crossings</small>
      </span>
    </div>
  );
}

function LayerToggle({
  active,
  disabled = false,
  onToggle,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <button
      className={`layer-toggle${active ? " layer-toggle-active" : ""}`}
      disabled={disabled}
      onClick={onToggle}
      type="button"
    >
      {children}
    </button>
  );
}

function SvgRiskSurface({
  layers,
  selectedFeatureId,
  onSelectFeature,
}: {
  layers: MapLibreLayerSpec[];
  selectedFeatureId: string | null;
  onSelectFeature: (featureId: string) => void;
}) {
  const activeFeatures = layers.flatMap((layer) => (layer.active ? layer.features : []));
  const bounds = useMemo(() => computeBounds(activeFeatures), [activeFeatures]);

  return (
    <div className="risk-map-shell">
      <svg
        aria-label="Risk map surface"
        className="risk-map-svg"
        role="img"
        viewBox={`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`}
      >
        <rect className="risk-map-background" height={MAP_VIEWBOX.height} width={MAP_VIEWBOX.width} x="0" y="0" />
        <g className="risk-map-grid">
          {Array.from({ length: 6 }).map((_, index) => {
            const horizontal = ((index + 1) / 7) * MAP_VIEWBOX.height;
            const vertical = ((index + 1) / 7) * MAP_VIEWBOX.width;
            return (
              <g key={`grid-${index}`}>
                <line x1="0" x2={MAP_VIEWBOX.width} y1={horizontal} y2={horizontal} />
                <line x1={vertical} x2={vertical} y1="0" y2={MAP_VIEWBOX.height} />
              </g>
            );
          })}
        </g>
        {layers.map((layer) =>
          layer.active
            ? layer.features.map((feature) => {
                const featureId = featureIdentifier(feature);
                const isSelected = featureId === selectedFeatureId;
                const color = bandColor(featureBand(feature), layer.tone);

                if (feature.geometry.type === "Point") {
                  const [point] = featurePoints(feature);
                  if (!point) {
                    return null;
                  }
                  const [x, y] = projectPoint(point, bounds);
                  return (
                    <circle
                      key={`${layer.key}:${featureId}`}
                      className="risk-point"
                      cx={x}
                      cy={y}
                      fill={color}
                      onClick={() => onSelectFeature(featureId)}
                      r={isSelected ? 9 : 6}
                      stroke={isSelected ? mapLayerColors.selectedInk : rgbaFromHex(mapLayerColors.featureStroke, 0.8)}
                      strokeWidth={isSelected ? 3 : 2}
                    />
                  );
                }

                return geometryPaths(feature, bounds).map((path, index) => (
                  <path
                    key={`${layer.key}:${featureId}:${index}`}
                    className={`risk-shape risk-shape-${layer.tone}${isSelected ? " risk-shape-selected" : ""}`}
                    d={path}
                    fill={layer.tone === "tiles" ? rgbaFromHex(color, 0.34) : "none"}
                    onClick={() => onSelectFeature(featureId)}
                    stroke={color}
                    strokeWidth={layer.tone === "segments" ? (isSelected ? 6 : 4) : isSelected ? 3 : 1.6}
                  />
                ));
              })
            : null,
        )}
      </svg>
    </div>
  );
}

export function PublicRiskExplorer() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const routeSearch = searchParams.toString();
  const [cities, setCities] = useState<PublicCityRecord[]>([]);
  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(() => searchParams.get("city"));
  const [selectedYear, setSelectedYear] = useState<number | null>(() =>
    parseYearParam(searchParams.get("year")),
  );
  const [scoreBand, setScoreBand] = useState<ScoreBandFilter>(() =>
    normalizeScoreBandFilter(searchParams.get("band"), "very_high"),
  );
  const [payload, setPayload] = useState<PublicRiskMapPayload | null>(null);
  const [interventions, setInterventions] = useState<InterventionShortlistPayload | null>(null);
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(() => searchParams.get("feature"));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const deferredCityKey = useDeferredValue(selectedCityKey);

  function replaceRouteState(updates: Parameters<typeof buildRiskMapSearchParams>[1]) {
    router.replace(`${pathname}${buildRiskMapSearchParams(routeSearch, updates)}`, {
      scroll: false,
    });
  }

  function selectCity(cityKey: string) {
    startTransition(() => {
      setSelectedCityKey(cityKey);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ city: cityKey, feature: null });
  }

  function selectYear(year: number) {
    startTransition(() => {
      setSelectedYear(year);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ feature: null, year });
  }

  function selectScoreBand(nextBand: ScoreBandFilter) {
    startTransition(() => {
      setScoreBand(nextBand);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ band: nextBand, feature: null });
  }

  function selectFeature(featureId: string) {
    setSelectedFeatureId(featureId);
    replaceRouteState({ feature: featureId });
  }

  useEffect(() => {
    let active = true;

    async function loadCities() {
      try {
        const catalog = await fetchJson<CityCatalogPayload>(`${API_BASE_URL}/v1/public/cities`);
        if (!active) {
          return;
        }
        setCities(catalog.cities);
        startTransition(() => {
          const preferredCity = resolvePreferredCity(catalog.cities, selectedCityKey);
          setSelectedCityKey(preferredCity);
          if (preferredCity) {
            replaceRouteState({ city: preferredCity });
          }
        });
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load city catalog.");
          setLoading(false);
        }
      }
    }

    void loadCities();
    return () => {
      active = false;
    };
  }, []);

  const selectedCity = useMemo(
    () => cities.find((city) => city.city_key === selectedCityKey) ?? null,
    [cities, selectedCityKey],
  );
  const availableYears = useMemo(() => cityYears(selectedCity), [selectedCity]);

  useEffect(() => {
    if (availableYears.length === 0) {
      return;
    }
    if (selectedYear && availableYears.includes(selectedYear)) {
      return;
    }
    startTransition(() => {
      const nextYear = availableYears[0];
      setSelectedYear(nextYear);
      replaceRouteState({ year: nextYear });
    });
  }, [availableYears, selectedYear]);

  useEffect(() => {
    if (!deferredCityKey || selectedYear === null) {
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);

    async function loadMap() {
      try {
        const mapUrl = new URL(`${API_BASE_URL}/v1/public/cities/${deferredCityKey}/risk-map`);
        mapUrl.searchParams.set("occurred_year", String(selectedYear));
        mapUrl.searchParams.set("limit", "320");
        if (scoreBand !== "all") {
          mapUrl.searchParams.set("min_score_band", scoreBand);
        }
        const interventionsUrl = `${API_BASE_URL}/v1/public/cities/${deferredCityKey}/interventions${STATIC_DEMO ? `?${mapUrl.searchParams}` : ""}`;
        const [mapPayload, interventionPayload] = await Promise.all([
          fetchJson<PublicRiskMapPayload>(mapUrl.toString()),
          fetchJson<InterventionShortlistPayload>(interventionsUrl),
        ]);
        if (!active) {
          return;
        }
        setPayload(mapPayload);
        setInterventions(interventionPayload);
        const defaultFeature = mapPayload.map_resource.data.features[0];
        const featureIds = new Set(
          mapPayload.map_resource.data.features.map((feature) => featureIdentifier(feature)),
        );
        const nextFeatureId =
          selectedFeatureId && featureIds.has(selectedFeatureId)
            ? selectedFeatureId
            : defaultFeature
              ? featureIdentifier(defaultFeature)
              : null;
        setSelectedFeatureId(nextFeatureId);
        replaceRouteState({ feature: nextFeatureId });
        setLoading(false);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load the public map.");
          setLoading(false);
        }
      }
    }

    void loadMap();
    return () => {
      active = false;
    };
  }, [deferredCityKey, scoreBand, selectedYear]);

  const selectedFeature = useMemo(
    () =>
      payload?.map_resource.data.features.find((feature) => featureIdentifier(feature) === selectedFeatureId) ?? null,
    [payload, selectedFeatureId],
  );
  const tileLayers = useMemo<MapLibreLayerSpec[]>(
    () => [
      {
        key: "tiles",
        label: "Public score tiles",
        tone: "tiles",
        features: payload?.map_resource.data.features ?? [],
        active: true,
      },
    ],
    [payload],
  );

  return (
    <section className="workspace-grid">
      <div className="workspace-title">
        <Eyebrow>Public risk map</Eyebrow>
        <h3>Explore published risk tiles, corridors, and safety works in one public view.</h3>
        <p>
          Choose a municipality, year, and risk band to understand where safety attention is
          concentrated. The map keeps public data aggregated and pairs each selection with a clear
          explanation panel.
        </p>
      </div>

      <FilterBar
        summary={
          <>
            <NavChip>Aggregated public tiles</NavChip>
            <NavChip>Legend always visible</NavChip>
            <NavChip>Selection updates details</NavChip>
          </>
        }
      >
        <label>
          <span>Municipality</span>
          <select
            onChange={(event) => selectCity(event.target.value)}
            value={selectedCityKey ?? ""}
          >
            {cities.map((city) => (
              <option key={city.city_key} value={city.city_key}>
                {city.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Year</span>
          <select
            onChange={(event) => selectYear(Number.parseInt(event.target.value, 10))}
            value={selectedYear ?? ""}
          >
            {availableYears.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Score band</span>
          <select
            onChange={(event) => selectScoreBand(event.target.value as ScoreBandFilter)}
            value={scoreBand}
          >
            {SCORE_BAND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      {loading ? (
        <LoadingState
          title="Preparing public map"
          detail="Loading the selected city, year, risk band, and intervention shortlist."
        />
      ) : null}
      {error ? (
        <ErrorState
          detail={`The public dashboard could not load this view. ${error}`}
        />
      ) : null}

      {payload && !loading && !error ? (
        <>
          <div className="metrics-grid">
            <MetricCard
              footnote={`${payload.city.display_name} published run`}
              label="Tile rows"
              value={formatCompactNumber(payload.summary.tile_rows)}
            />
            <MetricCard
              footnote="High and very-high public tiles"
              label="Priority tiles"
              value={formatCompactNumber(payload.summary.tiles_high_or_very_high)}
            />
            <MetricCard
              footnote="Current very-high-band footprint"
              label="Very-high tiles"
              value={formatCompactNumber(payload.summary.tiles_very_high)}
            />
            <MetricCard
              footnote="Published model total"
              label="Predicted crashes"
              value={formatCompactNumber(payload.summary.predicted_crash_total)}
            />
          </div>

          <div className="content-grid explorer-grid">
            <Panel
              accent="teal"
              detail="Use the visible legend and selected tile panel to understand the relative public-risk intensity."
              title="Tile surface"
            >
              <div className="map-toolbar">
                <MapLegend />
                <div className="chip-row">
                  <NavChip>{payload.city.prediction_run_label || "published run"}</NavChip>
                  <NavChip>{formatCompactNumber(payload.map_resource.stats.returned_features)} visible tiles</NavChip>
                  <NavChip>{formatCompactNumber(payload.summary.tile_size_m)} m tile size</NavChip>
                </div>
              </div>
              <MapLibreRiskMap
                fallback={
                  <SvgRiskSurface
                    layers={tileLayers}
                    onSelectFeature={selectFeature}
                    selectedFeatureId={selectedFeatureId}
                  />
                }
                layers={tileLayers}
                mapId="public-risk-map"
                onSelectFeature={selectFeature}
                selectedFeatureId={selectedFeatureId}
                subtitle="Published public score tiles rendered as interactive GeoJSON layers."
                title="Public MapLibre risk surface"
              />
            </Panel>

            <Panel
              accent="slate"
              detail="The selected tile and intervention shortlist share the same summary-driven city context."
              title="Public detail panel"
            >
              <div className="detail-stack">
                <StatusPill label={payload.city.display_name} tone="success" />
                {featureSummaryRows(selectedFeature).length > 0 ? (
                  <dl className="detail-grid">
                    {featureSummaryRows(selectedFeature).map(([label, value]) => (
                      <div key={`${label}:${value}`}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p>Select a tile to inspect its public score band and relative intensity.</p>
                )}
              </div>
            </Panel>
          </div>

          {interventions ? (
            <div className="content-grid explorer-grid">
              <Panel
                accent="rust"
                detail="Corridors are summarized for public transparency without exposing restricted crash records."
                title="Top corridors"
              >
                <DataTable
                  columns={["Corridor", "Predicted crashes", "Segments", "Best rank"]}
                  rows={interventions.intervention_shortlist.top_corridors
                    .slice(0, 5)
                    .map((corridor: Record<string, unknown>) => [
                    String(corridor.corridor_label ?? "Unnamed corridor"),
                    formatDetailValue(corridor.predicted_crash_total),
                    formatDetailValue(corridor.segment_count),
                    formatDetailValue(corridor.best_rank),
                  ])}
                />
              </Panel>

              <Panel accent="slate" detail="Hotspot tiles stay aligned with the selected municipality." title="Priority hotspots">
                <DataTable
                  columns={["Tile", "Band", "Score"]}
                  rows={interventions.intervention_shortlist.hotspot_tiles
                    .slice(0, 5)
                    .map((tile: Record<string, unknown>) => [
                    String(tile.tile_score_id ?? "Unnamed tile"),
                    String(tile.tile_public_score_band ?? "n/a"),
                    formatDetailValue(tile.tile_max_public_score_index),
                  ])}
                />
              </Panel>
            </div>
          ) : !loading && !error ? (
            <EmptyState
              title="No public intervention shortlist yet"
              detail="Risk tiles are available for the selected view, but intervention summaries have not been published for this municipality."
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function AnalystRiskExplorer() {
  const { session } = usePlatformSession();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const routeSearch = searchParams.toString();
  const [cities, setCities] = useState<PublicCityRecord[]>([]);
  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(() => searchParams.get("city"));
  const [selectedYear, setSelectedYear] = useState<number | null>(() =>
    parseYearParam(searchParams.get("year")),
  );
  const [scoreBand, setScoreBand] = useState<ScoreBandFilter>(() =>
    normalizeScoreBandFilter(searchParams.get("band"), "high"),
  );
  const [payload, setPayload] = useState<AnalystRiskMapPayload | null>(null);
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(() => searchParams.get("feature"));
  const [activeLayers, setActiveLayers] = useState(() =>
    parseLayerVisibility(searchParams.get("layers"), {
      segments: true,
      junctions: true,
      crossings: true,
    }),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const deferredCityKey = useDeferredValue(selectedCityKey);

  function replaceRouteState(updates: Parameters<typeof buildRiskMapSearchParams>[1]) {
    router.replace(`${pathname}${buildRiskMapSearchParams(routeSearch, updates)}`, {
      scroll: false,
    });
  }

  function selectCity(cityKey: string) {
    startTransition(() => {
      setSelectedCityKey(cityKey);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ city: cityKey, feature: null });
  }

  function selectYear(year: number) {
    startTransition(() => {
      setSelectedYear(year);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ feature: null, year });
  }

  function selectScoreBand(nextBand: ScoreBandFilter) {
    startTransition(() => {
      setScoreBand(nextBand);
      setSelectedFeatureId(null);
    });
    replaceRouteState({ band: nextBand, feature: null });
  }

  function selectFeature(featureId: string) {
    setSelectedFeatureId(featureId);
    replaceRouteState({ feature: featureId });
  }

  function closeFeature() {
    setSelectedFeatureId(null);
    replaceRouteState({ feature: null });
  }

  function toggleLayer(layerKey: keyof typeof activeLayers) {
    const nextLayers = { ...activeLayers, [layerKey]: !activeLayers[layerKey] };
    startTransition(() => {
      setActiveLayers(nextLayers);
      setSelectedFeatureId(null);
    });
    replaceRouteState({
      feature: null,
      layers: serializeLayerVisibility(nextLayers),
    });
  }

  useEffect(() => {
    let active = true;

    async function loadCities() {
      try {
        const catalog = await fetchJson<CityCatalogPayload>(`${API_BASE_URL}/v1/public/cities`);
        if (!active) {
          return;
        }
        setCities(catalog.cities);
        startTransition(() => {
          const preferredCity = resolvePreferredCity(
            catalog.cities,
            selectedCityKey ?? session.selectedMunicipalityId,
          );
          setSelectedCityKey(preferredCity);
          if (preferredCity) {
            replaceRouteState({ city: preferredCity });
          }
        });
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load analyst cities.");
          setLoading(false);
        }
      }
    }

    void loadCities();
    return () => {
      active = false;
    };
  }, [session.selectedMunicipalityId]);

  const selectedCity = useMemo(
    () => cities.find((city) => city.city_key === selectedCityKey) ?? null,
    [cities, selectedCityKey],
  );
  const availableYears = useMemo(() => cityYears(selectedCity), [selectedCity]);

  useEffect(() => {
    if (availableYears.length === 0) {
      return;
    }
    if (selectedYear && availableYears.includes(selectedYear)) {
      return;
    }
    startTransition(() => {
      const nextYear = availableYears[0];
      setSelectedYear(nextYear);
      replaceRouteState({ year: nextYear });
    });
  }, [availableYears, selectedYear]);

  useEffect(() => {
    if (!deferredCityKey || selectedYear === null) {
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);

    async function loadMap() {
      try {
        const url = new URL(`${API_BASE_URL}/v1/analyst/cities/${deferredCityKey}/risk-map`);
        url.searchParams.set("occurred_year", String(selectedYear));
        url.searchParams.set("limit", "220");
        url.searchParams.set("junction_limit", "120");
        url.searchParams.set("crossing_limit", "120");
        if (scoreBand !== "all") {
          url.searchParams.set("min_score_band", scoreBand);
        }
        const nextPayload = await fetchJson<AnalystRiskMapPayload>(url.toString());
        if (!active) {
          return;
        }
        setPayload(nextPayload);
        const defaultFeature =
          nextPayload.segment_layer.data.features[0] ||
          nextPayload.support_layers.junctions.data.features[0] ||
          nextPayload.support_layers.crossings.data.features[0];
        const featureIds = new Set(
          [
            ...nextPayload.segment_layer.data.features,
            ...nextPayload.support_layers.junctions.data.features,
            ...nextPayload.support_layers.crossings.data.features,
          ].map((feature) => featureIdentifier(feature)),
        );
        const nextFeatureId =
          selectedFeatureId && featureIds.has(selectedFeatureId)
            ? selectedFeatureId
            : defaultFeature
              ? featureIdentifier(defaultFeature)
              : null;
        setSelectedFeatureId(nextFeatureId);
        replaceRouteState({ feature: nextFeatureId });
        setLoading(false);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Could not load analyst risk layers.");
          setLoading(false);
        }
      }
    }

    void loadMap();
    return () => {
      active = false;
    };
  }, [deferredCityKey, scoreBand, selectedYear]);

  const segmentDetailsById = useMemo(
    () => indexSegmentDetails(payload?.segment_details.rows ?? []),
    [payload],
  );
  const mapLayers = useMemo<MapLibreLayerSpec[]>(() => {
    if (!payload) {
      return [];
    }
    return [
      {
        key: "segments",
        label: "Segments",
        tone: "segments",
        features: payload.segment_layer.data.features,
        active: activeLayers.segments,
      },
      {
        key: "junctions",
        label: "Junctions",
        tone: "junctions",
        features: payload.support_layers.junctions.data.features,
        active: activeLayers.junctions,
      },
      {
        key: "crossings",
        label: "Crossings",
        tone: "crossings",
        features: payload.support_layers.crossings.data.features,
        active: activeLayers.crossings,
      },
    ];
  }, [activeLayers.crossings, activeLayers.junctions, activeLayers.segments, payload]);

  const selectedFeature = useMemo(() => {
    for (const layer of mapLayers) {
      const match = layer.features.find((feature) => featureIdentifier(feature) === selectedFeatureId);
      if (match) {
        return match;
      }
    }
    return null;
  }, [mapLayers, selectedFeatureId]);

  const selectedDetailRow = useMemo(() => {
    if (!selectedFeature) {
      return undefined;
    }
    const identifier = String(
      selectedFeature.properties.segment_score_id ||
        selectedFeature.properties.segment_id ||
        "",
    );
    return segmentDetailsById[identifier];
  }, [segmentDetailsById, selectedFeature]);

  return (
    <WorkspacePage
      density="comfortable"
      header={
        <PageHeader
          eyebrow="Analyst risk explorer"
          title="Investigate scored segments, junction context, and crossing priorities from one workbench."
          description="Analysts can filter the city model, toggle operational layers, select a feature, and move from map evidence to a prioritized action list without leaving the route."
          meta={
            <>
              <StatusPill label="Map-list-detail workflow" tone="success" />
              <NavChip>Segment and support layers</NavChip>
            </>
          }
        />
      }
    >

      <FilterBar
        summary={
          <>
            <NavChip>Map-list-detail workflow</NavChip>
            <NavChip>Segment and support layers</NavChip>
            <NavChip>Professional triage view</NavChip>
          </>
        }
      >
        <label>
          <span>Municipality</span>
          <select
            onChange={(event) => selectCity(event.target.value)}
            value={selectedCityKey ?? ""}
          >
            {cities.map((city) => (
              <option key={city.city_key} value={city.city_key}>
                {city.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Model year</span>
          <select
            onChange={(event) => selectYear(Number.parseInt(event.target.value, 10))}
            value={selectedYear ?? ""}
          >
            {availableYears.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Score band</span>
          <select
            onChange={(event) => selectScoreBand(event.target.value as ScoreBandFilter)}
            value={scoreBand}
          >
            {SCORE_BAND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      {loading ? (
        <LoadingState
          title="Preparing analyst map"
          detail="Loading scored segments, available support layers, and selected feature details."
        />
      ) : null}
      {error ? (
        <ErrorState
          detail={`The analyst workbench could not load this view. ${error}`}
        />
      ) : null}

      {payload && !loading && !error ? (
        <>
          <div className="metrics-grid">
            <MetricCard
              footnote={`${payload.city.display_name} scored network subset`}
              label="Visible segments"
              value={formatCompactNumber(payload.segment_layer.stats.returned_features)}
            />
            <MetricCard
              footnote={payload.support_layers.junctions.availability === "available" ? "Signal-node baseline" : "Unavailable for this context"}
              label="Junction layer"
              value={formatCompactNumber(payload.support_layers.junctions.stats.returned_features)}
            />
            <MetricCard
              footnote={payload.support_layers.crossings.availability === "available" ? "Pedestrian crossing priorities" : "Unavailable for this context"}
              label="Crossing layer"
              value={formatCompactNumber(payload.support_layers.crossings.stats.returned_features)}
            />
            <MetricCard
              footnote="Returned analyst detail rows"
              label="Detail rows"
              value={formatCompactNumber(payload.segment_details.stats.returned_rows)}
            />
          </div>

          <Panel
            accent="teal"
            detail="Segments come from published model outputs; junctions and crossings are attached as operational support layers when available. Select a feature on the map to open its detail drawer."
            title="Internal risk map"
          >
            <div className="map-toolbar">
              <MapLegend />
              <div className="chip-row">
                <LayerToggle
                  active={activeLayers.segments}
                  onToggle={() => toggleLayer("segments")}
                >
                  Segments
                </LayerToggle>
                <LayerToggle
                  active={activeLayers.junctions}
                  disabled={payload.support_layers.junctions.availability !== "available"}
                  onToggle={() => toggleLayer("junctions")}
                >
                  Junctions
                </LayerToggle>
                <LayerToggle
                  active={activeLayers.crossings}
                  disabled={payload.support_layers.crossings.availability !== "available"}
                  onToggle={() => toggleLayer("crossings")}
                >
                  Crossings
                </LayerToggle>
              </div>
            </div>
            <MapLibreRiskMap
              fallback={
                <SvgRiskSurface
                  layers={mapLayers}
                  onSelectFeature={selectFeature}
                  selectedFeatureId={selectedFeatureId}
                />
              }
              layers={mapLayers}
              mapId="analyst-risk-map"
              onSelectFeature={selectFeature}
              selectedFeatureId={selectedFeatureId}
              subtitle="Scored segments, junctions, and crossings rendered as interactive GeoJSON layers."
              title="Analyst MapLibre risk surface"
            />
          </Panel>

          <Panel
            accent="slate"
            detail="Selected map features bind back to analyst rows and supporting operational layers. The map and its layer controls stay live while a feature is selected."
            title="Selected feature"
          >
            <div className="detail-stack">
              {selectedFeature ? (
                <>
                  <dl className="detail-grid">
                    {featureSummaryRows(selectedFeature, selectedDetailRow).map(([label, value]) => (
                      <div key={`${label}:${value}`}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="chip-row">
                    <StatusPill label={payload.city.display_name} tone="success" />
                    <NavChip>{payload.city.prediction_run_label || "published run"}</NavChip>
                    {payload.support_layers.junctions.resolved_year ? (
                      <NavChip>Junction year {payload.support_layers.junctions.resolved_year}</NavChip>
                    ) : null}
                    <Button onClick={closeFeature} size="sm" variant="ghost">
                      Clear selection
                    </Button>
                  </div>
                </>
              ) : (
                <p>Select a segment, junction, or crossing on the map to inspect its detail here.</p>
              )}
            </div>
          </Panel>

          <div className="content-grid explorer-grid">
            <Panel
              accent="rust"
              detail="Coverage notes clarify which operational layers are available for the selected municipality."
              title="Layer coverage"
            >
              <DataTable
                columns={["Layer", "Availability", "Returned", "Notes"]}
                rows={[
                  [
                    "Segments",
                    "available",
                    formatDetailValue(payload.segment_layer.stats.returned_features),
                    "Published segment-score geometry and analyst detail rows",
                  ],
                  [
                    "Junctions",
                    payload.support_layers.junctions.availability,
                    formatDetailValue(payload.support_layers.junctions.stats.returned_features),
                    payload.support_layers.junctions.reason || "Signalized junction baseline",
                  ],
                  [
                    "Crossings",
                    payload.support_layers.crossings.availability,
                    formatDetailValue(payload.support_layers.crossings.stats.returned_features),
                    payload.support_layers.crossings.reason || "Pedestrian crossing priority baseline",
                  ],
                ]}
              />
            </Panel>

            <Panel accent="slate" detail="Highest-ranked segment rows are available immediately for corridor triage." title="Top segment rows">
              <DataTable
                columns={["Segment", "Band", "Predicted", "Observed"]}
                rows={payload.segment_details.rows.slice(0, 5).map((row) => [
                  row.name || row.segment_id || "Unnamed segment",
                  row.public_score_band || "n/a",
                  formatDetailValue(row.predicted_crash_count),
                  formatDetailValue(row.observed_crash_count),
                ])}
              />
            </Panel>

            <LiveTelematicsFeed />
          </div>
        </>
      ) : null}
    </WorkspacePage>
  );
}
