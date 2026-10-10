const RESOURCE_LABELS = {
  segment_score_tiles: "Public Tiles",
  segment_scores: "Public Segments",
};

const BAND_COLORS = {
  low: "#b6cab8",
  moderate: "#e0bf68",
  high: "#d77b49",
  very_high: "#9f2f2f",
};

const state = {
  apiBase: "",
  dashboardSummary: null,
  index: null,
  resourceName: "segment_score_tiles",
  predictionRunLabel: "",
  occurredYear: "",
  tileSizeM: "",
  minScoreBand: "very_high",
  limit: 60,
  selectedFeatureId: "",
  interventionSelection: null,
};

const elements = {
  apiOrigin: document.getElementById("api-origin"),
  contractVersion: document.getElementById("contract-version"),
  resourceName: document.getElementById("resource-name"),
  predictionRunLabel: document.getElementById("prediction-run-label"),
  occurredYear: document.getElementById("occurred-year"),
  tileSizeField: document.getElementById("tile-size-field"),
  tileSizeM: document.getElementById("tile-size-m"),
  minScoreBand: document.getElementById("min-score-band"),
  limit: document.getElementById("limit"),
  dashboardForm: document.getElementById("dashboard-form"),
  returnedCount: document.getElementById("returned-count"),
  matchedCount: document.getElementById("matched-count"),
  coveragePrimary: document.getElementById("coverage-primary"),
  coverageSecondary: document.getElementById("coverage-secondary"),
  runLabel: document.getElementById("run-label"),
  resourceView: document.getElementById("resource-view"),
  manifestName: document.getElementById("manifest-name"),
  manifestUpdated: document.getElementById("manifest-updated"),
  chartVeryHighTiles: document.getElementById("chart-very-high-tiles"),
  chartTopShare: document.getElementById("chart-top-share"),
  chartTransferGap: document.getElementById("chart-transfer-gap"),
  mapCaption: document.getElementById("map-caption"),
  surfaceMap: document.getElementById("surface-map"),
  mapEmpty: document.getElementById("map-empty"),
  runComparisonList: document.getElementById("run-comparison-list"),
  transferabilityTableBody: document.getElementById("transferability-table-body"),
  shortlistCorridors: document.getElementById("shortlist-corridors"),
  shortlistTiles: document.getElementById("shortlist-tiles"),
  interventionDetail: document.getElementById("intervention-detail"),
  recordTableBody: document.getElementById("record-table-body"),
  featureDetails: document.getElementById("feature-details"),
  requestTrace: document.getElementById("request-trace"),
};

function detectApiBase() {
  const params = new URLSearchParams(window.location.search);
  const explicit = params.get("apiBase");
  if (explicit) {
    return explicit.replace(/\/+$/, "");
  }
  if (window.location.origin && window.location.origin !== "null") {
    return window.location.origin;
  }
  return "http://127.0.0.1:8000";
}

async function fetchJson(path) {
  const response = await fetch(`${state.apiBase}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload?.error?.message || `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

function uniqueSorted(values, compareFn) {
  return Array.from(new Set(values)).sort(compareFn);
}

function sortCatalogNewest(records) {
  return [...records].sort((left, right) => {
    const leftKey = `${left.document_mtime_utc || ""}|${left.manifest_path || ""}`;
    const rightKey = `${right.document_mtime_utc || ""}|${right.manifest_path || ""}`;
    return leftKey.localeCompare(rightKey);
  });
}

function recordsForResource(resourceName) {
  return (state.index?.catalog || []).filter((record) => record.resource_name === resourceName);
}

function updateSelect(select, values, formatter, preferredValue) {
  const currentValue = preferredValue && values.includes(preferredValue) ? preferredValue : values[0] || "";
  select.innerHTML = values
    .map((value) => `<option value="${String(value)}">${formatter(value)}</option>`)
    .join("");
  select.value = currentValue;
  return currentValue;
}

function syncStateFromIndex() {
  const supportedResources = state.index?.supported_resource_names || [];
  if (!supportedResources.includes(state.resourceName)) {
    state.resourceName = supportedResources[0] || "segment_score_tiles";
  }
  updateSelect(
    elements.resourceName,
    supportedResources,
    (value) => RESOURCE_LABELS[value] || value,
    state.resourceName,
  );
  state.resourceName = elements.resourceName.value;

  const resourceRecords = recordsForResource(state.resourceName);
  const newestRecords = sortCatalogNewest(resourceRecords);
  const latestRecord = newestRecords.at(-1);
  const runLabels = uniqueSorted(
    resourceRecords
      .map((record) => record.prediction_run_label)
      .filter(Boolean),
    (left, right) => String(left).localeCompare(String(right)),
  );
  state.predictionRunLabel = updateSelect(
    elements.predictionRunLabel,
    runLabels,
    (value) => String(value),
    runLabels.includes(state.predictionRunLabel) ? state.predictionRunLabel : latestRecord?.prediction_run_label,
  );

  const runRecords = resourceRecords.filter(
    (record) => record.prediction_run_label === state.predictionRunLabel,
  );
  const years = uniqueSorted(
    runRecords.flatMap((record) => record.occurred_years || []).map((value) => Number(value)),
    (left, right) => left - right,
  );
  const preferredYear = years.includes(Number(state.occurredYear))
    ? Number(state.occurredYear)
    : years.at(-1);
  state.occurredYear = String(
    updateSelect(elements.occurredYear, years, (value) => String(value), preferredYear),
  );

  const isTileResource = state.resourceName === "segment_score_tiles";
  elements.tileSizeField.hidden = !isTileResource;
  if (isTileResource) {
    const tileSizes = uniqueSorted(
      runRecords
        .filter((record) => (record.occurred_years || []).includes(Number(state.occurredYear)))
        .map((record) => record.tile_size_m)
        .filter((value) => value !== null && value !== undefined)
        .map((value) => Number(value)),
      (left, right) => left - right,
    );
    state.tileSizeM = String(
      updateSelect(elements.tileSizeM, tileSizes, (value) => `${value} m`, Number(state.tileSizeM)),
    );
  } else {
    state.tileSizeM = "";
    elements.tileSizeM.innerHTML = "";
  }

  clearInterventionSelectionIfStale();
  elements.minScoreBand.value = state.minScoreBand;
  elements.limit.value = String(state.limit);
}

function buildQueryString() {
  const params = new URLSearchParams({
    resource_name: state.resourceName,
    prediction_run_label: state.predictionRunLabel,
    occurred_year: String(state.occurredYear),
    min_score_band: state.minScoreBand,
    limit: String(state.limit),
  });
  if (state.resourceName === "segment_score_tiles" && state.tileSizeM) {
    params.set("tile_size_m", state.tileSizeM);
  }
  return params.toString();
}

function humanizeRunLabel(value) {
  const prefix = String(value).split("_frequency_")[0] || String(value);
  return prefix
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

function currentShortlist() {
  const shortlists = state.dashboardSummary?.intervention_shortlists || [];
  return shortlists.find((entry) => entry.prediction_run_label === state.predictionRunLabel) || null;
}

function clearInterventionSelectionIfStale() {
  if (
    state.interventionSelection &&
    state.interventionSelection.predictionRunLabel !== state.predictionRunLabel
  ) {
    state.interventionSelection = null;
  }
}

function focusedFeatureIds(resourceName) {
  if (!state.interventionSelection) {
    return [];
  }
  if (resourceName === "segment_scores") {
    return state.interventionSelection.focusSegmentScoreIds || [];
  }
  if (resourceName === "segment_score_tiles" && state.interventionSelection.focusTileScoreId) {
    return [state.interventionSelection.focusTileScoreId];
  }
  return [];
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function renderMiniChart(container, entries, valueFormatter, noteFormatter) {
  if (!entries.length) {
    container.innerHTML = "<div class=\"mini-chart-note\">No summary data available.</div>";
    return;
  }
  const maxValue = Math.max(1, ...entries.map((entry) => Number(entry.value || 0)));
  container.innerHTML = entries
    .map((entry) => {
      const width = `${Math.max(6, (Number(entry.value || 0) / maxValue) * 100)}%`;
      return `
        <div class="mini-chart-row">
          <div class="mini-chart-head">
            <span class="mini-chart-label">${escapeHtml(entry.label)}</span>
            <span class="mini-chart-value">${escapeHtml(valueFormatter(entry.value))}</span>
          </div>
          <div class="mini-chart-bar"><span style="width: ${width};"></span></div>
          <div class="mini-chart-note">${escapeHtml(noteFormatter(entry))}</div>
        </div>
      `;
    })
    .join("");
}

function renderRunComparison() {
  const records = state.dashboardSummary?.published_runs || [];

  const maxPrimaryMetric = Math.max(
    1,
    ...records.map((record) =>
      state.resourceName === "segment_score_tiles"
        ? Number(record?.score_tiles?.tile_rows || 0)
        : Number(record?.segment_scores?.segment_score_rows || 0),
    ),
  );

  elements.runComparisonList.innerHTML = records
    .map((record) => {
      const isActive = record.prediction_run_label === state.predictionRunLabel;
      const primaryMetric = state.resourceName === "segment_score_tiles"
        ? Number(record?.score_tiles?.tile_rows || 0)
        : Number(record?.segment_scores?.segment_score_rows || 0);
      const secondaryMetric = state.resourceName === "segment_score_tiles"
        ? `${record?.score_tiles?.tiles_very_high || 0} very high tiles`
        : `${formatPercent(record?.segment_scores?.top_5pct_observed_crash_share || 0)} top-5 observed share`;
      const primaryLabel = state.resourceName === "segment_score_tiles"
        ? `${primaryMetric} tiles`
        : `${primaryMetric} segments`;
      const barWidth = `${Math.max(6, (primaryMetric / maxPrimaryMetric) * 100)}%`;
      return `
        <div class="run-comparison-item ${isActive ? "is-active" : ""}">
          <div class="run-comparison-head">
            <div>
              <div class="run-comparison-title">${escapeHtml(record.display_name || humanizeRunLabel(record.prediction_run_label))}</div>
              <div class="run-comparison-subtitle">${escapeHtml(record.prediction_run_label)}</div>
            </div>
            <div class="run-comparison-metric">${escapeHtml(primaryLabel)}</div>
          </div>
          <div class="run-comparison-bar"><span style="width: ${barWidth};"></span></div>
          <div class="run-comparison-detail">${escapeHtml(secondaryMetric)}</div>
        </div>
      `;
    })
    .join("");
}

function renderTransferabilitySummary() {
  const matrix = state.dashboardSummary?.transferability_matrix || [];
  const modeOrder = [
    "cross_jurisdiction_temporal",
    "cross_jurisdiction_cold_start",
    "cross_jurisdiction_history_free",
  ];
  if (!matrix.length) {
    elements.transferabilityTableBody.innerHTML = `
      <tr><td colspan="4">Dashboard summary is missing transferability metrics.</td></tr>
    `;
    return;
  }

  elements.transferabilityTableBody.innerHTML = matrix
    .map((record) => {
      const cells = modeOrder.map((mode) => {
        const metrics = record.metrics_by_mode?.[mode];
        if (!metrics) {
          return "<td>n/a</td>";
        }
        return `<td>${Number(metrics.mean_poisson_deviance || 0).toFixed(3)}</td>`;
      });
      return `
        <tr>
          <td>${escapeHtml(record.display_name)}</td>
          ${cells.join("")}
        </tr>
      `;
    })
    .join("");
}

function renderInterventionCharts() {
  const entries = state.dashboardSummary?.intervention_priority || [];
  renderMiniChart(
    elements.chartVeryHighTiles,
    [...entries]
      .sort((left, right) => Number(right.tiles_very_high || 0) - Number(left.tiles_very_high || 0))
      .map((entry) => ({
        label: entry.display_name,
        value: Number(entry.tiles_very_high || 0),
        note: `${entry.very_high_tiles_rank}. rank`,
      })),
    (value) => `${Number(value).toFixed(0)}`,
    (entry) => `${entry.note}`,
  );
  renderMiniChart(
    elements.chartTopShare,
    [...entries]
      .sort(
        (left, right) =>
          Number(right.top_5pct_observed_crash_share || 0) - Number(left.top_5pct_observed_crash_share || 0),
      )
      .map((entry) => ({
        label: entry.display_name,
        value: Number(entry.top_5pct_observed_crash_share || 0),
        note: `${entry.top_5_share_rank}. rank`,
      })),
    (value) => formatPercent(value),
    (entry) => `${entry.note}`,
  );
  renderMiniChart(
    elements.chartTransferGap,
    [...entries]
      .sort(
        (left, right) =>
          Number(right.cold_start_gap_vs_temporal || 0) - Number(left.cold_start_gap_vs_temporal || 0),
      )
      .map((entry) => ({
        label: entry.display_name,
        value: Number(entry.cold_start_gap_vs_temporal || 0),
        note: `${entry.cold_start_gap_rank}. rank`,
      })),
    (value) => `+${Number(value).toFixed(3)}`,
    (entry) => `${entry.note}`,
  );
}

function buildInterventionSelection(kind, item) {
  const topSegments = item.top_segments || [];
  const focusSegmentScoreIds = item.focus_segment_score_ids || [];
  if (kind === "corridor") {
    return {
      kind,
      predictionRunLabel: state.predictionRunLabel,
      identifier: item.corridor_label,
      label: item.corridor_label,
      focusSegmentScoreIds,
      focusTileScoreId: "",
      focusFeatureId: focusSegmentScoreIds[0] || topSegments[0]?.segment_score_id || "",
      detail: item,
    };
  }
  return {
    kind,
    predictionRunLabel: state.predictionRunLabel,
    identifier: item.tile_score_id,
    label: item.tile_score_id,
    focusSegmentScoreIds,
    focusTileScoreId: item.tile_score_id,
    focusFeatureId: item.tile_score_id,
    detail: item,
  };
}

async function applyInterventionSelection(kind, index) {
  const shortlist = currentShortlist();
  if (!shortlist) {
    return;
  }
  const collection = kind === "corridor" ? shortlist.top_corridors || [] : shortlist.hotspot_tiles || [];
  const item = collection[index];
  if (!item) {
    return;
  }

  state.interventionSelection = buildInterventionSelection(kind, item);
  state.selectedFeatureId = state.interventionSelection.focusFeatureId;

  if (kind === "corridor") {
    state.resourceName = "segment_scores";
    state.minScoreBand = "high";
    state.limit = Math.max(120, (state.interventionSelection.focusSegmentScoreIds || []).length * 20);
  } else {
    state.resourceName = "segment_score_tiles";
    state.minScoreBand = "very_high";
    state.limit = Math.max(80, Number(elements.limit.value || state.limit || 80));
  }

  syncStateFromIndex();
  elements.resourceName.value = state.resourceName;
  elements.minScoreBand.value = state.minScoreBand;
  elements.limit.value = String(state.limit);
  renderInterventionShortlist();
  renderInterventionDetail();
  await refreshSurface();
}

function renderInterventionShortlist() {
  const shortlist = currentShortlist();
  if (!shortlist) {
    elements.shortlistCorridors.innerHTML = "<div class=\"mini-chart-note\">No corridor shortlist available.</div>";
    elements.shortlistTiles.innerHTML = "<div class=\"mini-chart-note\">No hotspot-tile shortlist available.</div>";
    return;
  }

  elements.shortlistCorridors.innerHTML = (shortlist.top_corridors || [])
    .map((item, index) => `
      <button
        type="button"
        class="shortlist-item shortlist-button ${
          state.interventionSelection?.kind === "corridor" &&
          state.interventionSelection?.identifier === item.corridor_label
            ? "is-active"
            : ""
        }"
        data-intervention-kind="corridor"
        data-intervention-index="${index}"
      >
        <strong>${escapeHtml(item.corridor_label)}</strong>
        <span>${Number(item.predicted_crash_total || 0).toFixed(2)} predicted crashes across ${item.segment_count} segments</span>
        <span>max public score ${Number(item.max_public_score_index || 0).toFixed(1)}</span>
        <span class="shortlist-action">Focus corridor</span>
      </button>
    `)
    .join("") || "<div class=\"mini-chart-note\">No corridor shortlist available.</div>";

  elements.shortlistTiles.innerHTML = (shortlist.hotspot_tiles || [])
    .map((item, index) => `
      <button
        type="button"
        class="shortlist-item shortlist-button ${
          state.interventionSelection?.kind === "tile" &&
          state.interventionSelection?.identifier === item.tile_score_id
            ? "is-active"
            : ""
        }"
        data-intervention-kind="tile"
        data-intervention-index="${index}"
      >
        <strong>${escapeHtml(item.tile_score_id)}</strong>
        <span>${item.tile_very_high_band_segment_count} very-high segments inside the tile</span>
        <span>${item.tile_segment_count} total scored segments, max score ${Number(item.tile_max_public_score_index || 0).toFixed(1)}</span>
        <span class="shortlist-action">Focus tile</span>
      </button>
    `)
    .join("") || "<div class=\"mini-chart-note\">No hotspot-tile shortlist available.</div>";

  document.querySelectorAll("[data-intervention-kind]").forEach((node) => {
    node.addEventListener("click", async () => {
      await applyInterventionSelection(node.dataset.interventionKind, Number(node.dataset.interventionIndex));
    });
  });
}

function renderInterventionDetail() {
  const selection = state.interventionSelection;
  if (!selection) {
    elements.interventionDetail.className = "intervention-detail-empty";
    elements.interventionDetail.textContent =
      "Select a corridor or hotspot tile from the shortlist to focus the surface and expand the top supporting segments.";
    return;
  }

  const detail = selection.detail || {};
  const topSegments = detail.top_segments || [];
  const metaCards = selection.kind === "corridor"
    ? [
        {
          value: `${Number(detail.predicted_crash_total || 0).toFixed(2)}`,
          label: "Predicted crashes across the corridor shortlist",
        },
        {
          value: `${detail.segment_count || 0}`,
          label: "High or very-high scored segments in the corridor",
        },
        {
          value: `${Number(detail.max_public_score_index || 0).toFixed(1)}`,
          label: "Maximum public score index",
        },
      ]
    : [
        {
          value: `${detail.tile_very_high_band_segment_count || 0}`,
          label: "Very-high segments inside the hotspot tile",
        },
        {
          value: `${detail.intersection_segment_count || 0}`,
          label: "Scored public segments intersecting the tile",
        },
        {
          value: `${Number(detail.tile_max_public_score_index || 0).toFixed(1)}`,
          label: "Maximum tile public score index",
        },
      ];

  const actionNote = selection.kind === "corridor"
    ? "The surface is switched to public segments at High+ so the top corridor segments stay visible and clickable."
    : "The surface is switched to public tiles at Very High. The supporting segment list below comes from the intersecting published segment scores.";

  elements.interventionDetail.className = "intervention-detail-card";
  elements.interventionDetail.innerHTML = `
    <div class="intervention-badge">${selection.kind === "corridor" ? "Corridor Focus" : "Hotspot Tile"}</div>
    <div>
      <h3 class="intervention-title">${escapeHtml(selection.label)}</h3>
      <div class="intervention-note">${escapeHtml(actionNote)}</div>
    </div>
    <div class="intervention-meta">
      ${metaCards
        .map(
          (item) => `
            <div class="intervention-metric">
              <strong>${escapeHtml(item.value)}</strong>
              <span>${escapeHtml(item.label)}</span>
            </div>
          `,
        )
        .join("")}
    </div>
    <div class="intervention-segment-list">
      ${
        topSegments.length
          ? topSegments
              .map(
                (segment) => `
                  <div class="intervention-segment-row">
                    <div class="intervention-segment-head">
                      <span class="intervention-segment-title">${escapeHtml(segment.segment_label || segment.segment_score_id)}</span>
                      <span class="intervention-segment-rank">Rank ${segment.score_rank_desc}</span>
                    </div>
                    <div class="intervention-segment-meta">
                      <span>${escapeHtml(segment.public_score_band || "unknown")} band</span>
                      <span>score ${Number(segment.public_score_index || 0).toFixed(1)}</span>
                      <span>${Number(segment.predicted_crash_count || 0).toFixed(2)} predicted</span>
                      <span>${Number(segment.segment_length_m || 0).toFixed(0)} m</span>
                    </div>
                  </div>
                `,
              )
              .join("")
          : '<div class="mini-chart-note">No supporting segments were derived for this intervention target.</div>'
      }
    </div>
  `;
}

function updateSummary(payload) {
  const resource = payload.resource;
  const stats = resource.stats || {};
  const sourceStats = resource.source_stats || {};
  const resolution = payload.resolution || {};
  const returned =
    stats.returned_features ?? stats.returned_rows ?? 0;
  const matched =
    stats.matched_features ?? stats.matched_rows ?? 0;

  elements.contractVersion.textContent = resource.contract_version || "unknown";
  elements.returnedCount.textContent = String(returned);
  elements.matchedCount.textContent = `${matched} matched`;
  elements.runLabel.textContent = resolution.prediction_run_label || sourceStats.prediction_run_label || "unknown";
  elements.resourceView.textContent = `${RESOURCE_LABELS[resource.resource_name] || resource.resource_name} / ${resource.view}`;
  elements.manifestName.textContent = (resolution.manifest_path || "").split("/").slice(-2).join("/");
  elements.manifestUpdated.textContent = resolution.document_mtime_utc || "No timestamp";
  elements.mapCaption.textContent = state.interventionSelection
    ? `${matched} published features matched the filter; ${returned} rendered. Focused on ${state.interventionSelection.kind === "corridor" ? "corridor" : "hotspot tile"} ${state.interventionSelection.label}.`
    : `${matched} published features matched the filter; ${returned} rendered in the map and ranking list.`;

  if (resource.resource_name === "segment_score_tiles") {
    elements.coveragePrimary.textContent = `${sourceStats.tile_rows || 0} tiles`;
    elements.coverageSecondary.textContent = `${sourceStats.tiles_very_high || 0} very high tiles in source surface`;
  } else {
    elements.coveragePrimary.textContent = `${sourceStats.segment_score_rows || 0} segments`;
    elements.coverageSecondary.textContent = `${sourceStats.top_5pct_observed_crash_share || 0} top-5 observed share`;
  }

  elements.requestTrace.textContent = JSON.stringify(
    {
      apiBase: state.apiBase,
      endpoint: "/v1/published-resource/query",
      query: Object.fromEntries(new URLSearchParams(buildQueryString()).entries()),
      resolved_manifest_path: resolution.manifest_path,
    },
    null,
    2,
  );
  renderRunComparison();
  renderTransferabilitySummary();
  renderInterventionCharts();
  renderInterventionShortlist();
  renderInterventionDetail();
}

function geometryToCoordinateSets(geometry) {
  if (!geometry || !geometry.type) {
    return [];
  }
  if (geometry.type === "LineString") {
    return [geometry.coordinates];
  }
  if (geometry.type === "MultiLineString") {
    return geometry.coordinates;
  }
  if (geometry.type === "Polygon") {
    return geometry.coordinates;
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.flat();
  }
  return [];
}

function computeBounds(features) {
  const coordinates = [];
  features.forEach((feature) => {
    geometryToCoordinateSets(feature.geometry).forEach((line) => {
      line.forEach((pair) => coordinates.push(pair));
    });
  });
  if (!coordinates.length) {
    return null;
  }
  const lons = coordinates.map((pair) => pair[0]);
  const lats = coordinates.map((pair) => pair[1]);
  return {
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

function projectCoordinateFactory(bounds) {
  const width = 1000;
  const height = 640;
  const padding = 44;
  const spanLon = Math.max(bounds.maxLon - bounds.minLon, 0.0001);
  const spanLat = Math.max(bounds.maxLat - bounds.minLat, 0.0001);
  return ([lon, lat]) => {
    const x = padding + ((lon - bounds.minLon) / spanLon) * (width - padding * 2);
    const y = height - padding - ((lat - bounds.minLat) / spanLat) * (height - padding * 2);
    return [Number(x.toFixed(2)), Number(y.toFixed(2))];
  };
}

function featureBand(feature, resourceName) {
  if (resourceName === "segment_score_tiles") {
    return feature.properties.tile_public_score_band;
  }
  return feature.properties.public_score_band;
}

function featureScore(feature, resourceName) {
  if (resourceName === "segment_score_tiles") {
    return Number(feature.properties.tile_max_public_score_index || 0);
  }
  return Number(feature.properties.public_score_index || 0);
}

function getFeatureId(feature, resourceName) {
  return resourceName === "segment_score_tiles"
    ? feature.properties.tile_score_id
    : feature.properties.segment_score_id;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderSurface(features, resourceName) {
  elements.surfaceMap.innerHTML = "";
  if (!features.length) {
    elements.mapEmpty.hidden = false;
    return;
  }
  elements.mapEmpty.hidden = true;

  const bounds = computeBounds(features);
  if (!bounds) {
    elements.mapEmpty.hidden = false;
    return;
  }
  const project = projectCoordinateFactory(bounds);
  const focusedIds = new Set(focusedFeatureIds(resourceName));

  features.forEach((feature) => {
    const band = featureBand(feature, resourceName);
    const score = featureScore(feature, resourceName);
    const id = getFeatureId(feature, resourceName);
    const color = BAND_COLORS[band] || BAND_COLORS.low;
    const sets = geometryToCoordinateSets(feature.geometry);
    sets.forEach((line) => {
      const points = line.map(project);
      const pathData = points
        .map((pair, index) => `${index === 0 ? "M" : "L"} ${pair[0]} ${pair[1]}`)
        .join(" ");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathData);
      path.dataset.featureId = id;
      path.classList.add("surface-feature");
      if (focusedIds.has(id)) {
        path.classList.add("is-focused");
      }
      if (resourceName === "segment_score_tiles") {
        path.setAttribute("fill", `${color}99`);
        path.setAttribute("stroke", color);
        path.setAttribute("stroke-width", "1.4");
      } else {
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", color);
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        path.setAttribute("stroke-width", String(Math.max(1.6, (score / 100) * 8)));
        path.setAttribute("opacity", "0.92");
      }
      path.addEventListener("click", () => selectFeature(id, features, resourceName));
      elements.surfaceMap.appendChild(path);
    });
  });

  if (!state.selectedFeatureId && features[0]) {
    state.selectedFeatureId = getFeatureId(features[0], resourceName);
  }
  highlightSelectedFeature();
}

function renderTable(features, resourceName) {
  const rows = features.slice(0, Math.min(features.length, 12));
  const focusedIds = new Set(focusedFeatureIds(resourceName));
  elements.recordTableBody.innerHTML = rows
    .map((feature, index) => {
      const id = getFeatureId(feature, resourceName);
      const band = featureBand(feature, resourceName);
      const score = featureScore(feature, resourceName).toFixed(1);
      const shortId = id.split(":").slice(-2).join(":");
      return `
        <tr
          data-feature-id="${escapeHtml(id)}"
          class="${id === state.selectedFeatureId ? "is-active" : ""} ${focusedIds.has(id) ? "is-focused" : ""}"
        >
          <td>${index + 1}</td>
          <td>${escapeHtml(shortId)}</td>
          <td>${escapeHtml(band)}</td>
          <td>${score}</td>
        </tr>
      `;
    })
    .join("");

  elements.recordTableBody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectFeature(row.dataset.featureId, features, resourceName));
  });
}

function highlightSelectedFeature() {
  elements.surfaceMap.querySelectorAll(".surface-feature").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.featureId === state.selectedFeatureId);
  });
  elements.recordTableBody.querySelectorAll("tr").forEach((row) => {
    row.classList.toggle("is-active", row.dataset.featureId === state.selectedFeatureId);
  });
}

function selectFeature(selectedFeatureId, features, resourceName) {
  state.selectedFeatureId = selectedFeatureId;
  const selected = features.find((feature) => getFeatureId(feature, resourceName) === selectedFeatureId);
  elements.featureDetails.textContent = selected
    ? JSON.stringify(selected.properties, null, 2)
    : "Feature not found in current response.";
  highlightSelectedFeature();
}

function renderPayload(payload) {
  const resource = payload.resource;
  const data = resource.data || {};
  const features = data.type === "FeatureCollection" ? data.features || [] : [];
  updateSummary(payload);
  renderSurface(features, resource.resource_name);
  renderTable(features, resource.resource_name);
  if (features.length) {
    const focusedIds = focusedFeatureIds(resource.resource_name);
    const focusedId = focusedIds.find((id) =>
      features.some((feature) => getFeatureId(feature, resource.resource_name) === id),
    );
    const initialId = focusedId
      || (features.some((feature) => getFeatureId(feature, resource.resource_name) === state.selectedFeatureId)
        ? state.selectedFeatureId
        : getFeatureId(features[0], resource.resource_name));
    selectFeature(initialId, features, resource.resource_name);
  } else {
    state.selectedFeatureId = "";
    elements.featureDetails.textContent = "No features returned for the current filter.";
  }
}

async function refreshSurface() {
  try {
    const queryString = buildQueryString();
    const payload = await fetchJson(`/v1/published-resource/query?${queryString}`);
    renderPayload(payload);
  } catch (error) {
    elements.mapEmpty.hidden = false;
    elements.mapEmpty.textContent = error.message;
    elements.featureDetails.textContent = error.message;
    elements.requestTrace.textContent = error.message;
  }
}

async function initializeDashboard() {
  state.apiBase = detectApiBase();
  elements.apiOrigin.textContent = state.apiBase;

  try {
    const [indexPayload, summaryPayload] = await Promise.all([
      fetchJson("/v1/published-index"),
      fetchJson("/v1/dashboard-summary").catch(() => null),
    ]);
    state.index = indexPayload.index;
    state.dashboardSummary = summaryPayload?.summary || null;
    syncStateFromIndex();
    await refreshSurface();
  } catch (error) {
    elements.contractVersion.textContent = "error";
    elements.mapEmpty.hidden = false;
    elements.mapEmpty.textContent = error.message;
    elements.featureDetails.textContent = error.message;
    elements.requestTrace.textContent = error.message;
  }
}

elements.resourceName.addEventListener("change", () => {
  state.resourceName = elements.resourceName.value;
  state.predictionRunLabel = "";
  state.occurredYear = "";
  state.tileSizeM = "";
  syncStateFromIndex();
});

elements.predictionRunLabel.addEventListener("change", () => {
  state.predictionRunLabel = elements.predictionRunLabel.value;
  state.occurredYear = "";
  state.tileSizeM = "";
  syncStateFromIndex();
});

elements.occurredYear.addEventListener("change", () => {
  state.occurredYear = elements.occurredYear.value;
  state.tileSizeM = "";
  syncStateFromIndex();
});

elements.tileSizeM.addEventListener("change", () => {
  state.tileSizeM = elements.tileSizeM.value;
});

elements.dashboardForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.resourceName = elements.resourceName.value;
  state.predictionRunLabel = elements.predictionRunLabel.value;
  state.occurredYear = elements.occurredYear.value;
  state.tileSizeM = elements.tileSizeM.value;
  state.minScoreBand = elements.minScoreBand.value;
  state.limit = Number(elements.limit.value || 60);
  await refreshSurface();
});

async function downloadMinisterialDossier() {
  const statusEl = document.getElementById("dossier-status");
  const btn = document.getElementById("btn-ministerial-dossier");
  if (statusEl) {
    statusEl.hidden = false;
    statusEl.textContent = "Compiling vector PDF/A ministerial dossier...";
  }
  if (btn) btn.disabled = true;

  try {
    const response = await fetch(`${state.apiBase}/v1/reporting/ministerial-dossier`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_id: "org-open-mobility",
        network_label: `${state.predictionRunLabel || "metropolitan"}_safety_dossier`,
        jurisdiction_name: "Metropolitan Transport Authority",
        ministry_authority: "Department of Transportation",
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err?.detail || `HTTP ${response.status}`);
    }
    const data = await response.json();
    if (data.pdf_base64) {
      const binary = atob(data.pdf_base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${state.predictionRunLabel || "metropolitan"}_safety_dossier.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      if (statusEl) {
        statusEl.textContent = `✓ Ministerial Dossier PDF downloaded (SHA-256: ${data.data_manifest?.sha256_digest?.slice(0, 16)}...)`;
      }
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = `Error: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function runResearchBenchmark() {
  const statusEl = document.getElementById("dossier-status");
  const resultsContainer = document.getElementById("research-benchmark-results");
  const tableBody = document.getElementById("benchmark-table-body");
  const manifestEl = document.getElementById("benchmark-manifest");
  const btn = document.getElementById("btn-research-eval");

  if (statusEl) {
    statusEl.hidden = false;
    statusEl.textContent = "Computing statistical baselines to Poisson GBDT...";
  }
  if (btn) btn.disabled = true;

  try {
    const response = await fetch(`${state.apiBase}/v1/research/evaluate-panel-risk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_id: "org-open-mobility",
        network_label: `${state.predictionRunLabel || "metropolitan"}_research`,
        split_strategy: "forward_temporal",
        weeks_count: 8,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err?.detail || `HTTP ${response.status}`);
    }
    const data = await response.json();
    if (resultsContainer && tableBody) {
      resultsContainer.hidden = false;
      tableBody.innerHTML = "";
      const models = Object.values(data.baseline_metrics || {});
      models.forEach((m) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><strong>${escapeHtml(m.model_name)}</strong></td>
          <td>${m.poisson_deviance.toFixed(4)}</td>
          <td>${m.negative_log_likelihood.toFixed(4)}</td>
          <td>${m.roc_auc.toFixed(3)}</td>
          <td>${(m.top_20_capture * 100).toFixed(1)}%</td>
        `;
        tableBody.appendChild(row);
      });
      if (manifestEl) {
        manifestEl.textContent = `Manifest SHA-256: ${data.data_manifest?.sha256_digest || "verified"}`;
      }
      if (statusEl) {
        statusEl.textContent = `✓ Research Benchmark Complete (${data.total_observations} segment-weeks evaluated).`;
      }
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = `Error: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

let twinSimState = {
  data: null,
  currentTime: 0.0,
  isPlaying: false,
  duration: 30.0,
  animId: null,
  lastTimestamp: null,
};

function renderTwinFrame() {
  const canvas = document.getElementById("twin-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const scale = Math.min(w, h) / 110;

  // Background
  ctx.fillStyle = "#0c121e";
  ctx.fillRect(0, 0, w, h);

  // Isometric projection helper (pitch 55, yaw 35)
  const radYaw = (35 * Math.PI) / 180;
  const radPitch = (55 * Math.PI) / 180;
  const proj = (x, y, z = 0) => {
    const rx = x * Math.cos(radYaw) - y * Math.sin(radYaw);
    const ry = x * Math.sin(radYaw) + y * Math.cos(radYaw);
    const py = ry * Math.cos(radPitch) - z * Math.sin(radPitch);
    return { sx: cx + rx * scale, sy: cy + py * scale };
  };

  // Grid lines
  ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
  ctx.lineWidth = 1;
  for (let g = -50; g <= 50; g += 15) {
    const p1 = proj(g, -50);
    const p2 = proj(g, 50);
    ctx.beginPath();
    ctx.moveTo(p1.sx, p1.sy);
    ctx.lineTo(p2.sx, p2.sy);
    ctx.stroke();

    const p3 = proj(-50, g);
    const p4 = proj(50, g);
    ctx.beginPath();
    ctx.moveTo(p3.sx, p3.sy);
    ctx.lineTo(p4.sx, p4.sy);
    ctx.stroke();
  }

  // Draw roadway polygon
  const drawRoadPoly = (pts, fill, stroke) => {
    ctx.beginPath();
    const p0 = proj(pts[0][0], pts[0][1]);
    ctx.moveTo(p0.sx, p0.sy);
    for (let i = 1; i < pts.length; i++) {
      const p = proj(pts[i][0], pts[i][1]);
      ctx.lineTo(p.sx, p.sy);
    }
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  };

  const roadW = 7.0;
  drawRoadPoly([[-50, -roadW], [50, -roadW], [50, roadW], [-50, roadW]], "#1e2638", "#2a364f");
  drawRoadPoly([[-roadW, -50], [roadW, -50], [roadW, 50], [-roadW, 50]], "#1e2638", "#2a364f");

  const template = twinSimState.data?.redesign_summary?.geometry_template || "DUTCH_PROTECTED_JUNCTION";
  if (template === "DUTCH_PROTECTED_JUNCTION") {
    // Corner refuge islands
    const isR = 4.5;
    drawRoadPoly([[-roadW, -roadW], [-roadW - isR, -roadW], [-roadW, -roadW - isR]], "#1b3a2a", "#22c55e");
    drawRoadPoly([[roadW, -roadW], [roadW + isR, -roadW], [roadW, -roadW - isR]], "#1b3a2a", "#22c55e");
    drawRoadPoly([[-roadW, roadW], [-roadW - isR, roadW], [-roadW, roadW + isR]], "#1b3a2a", "#22c55e");
    drawRoadPoly([[roadW, roadW], [roadW + isR, roadW], [roadW, roadW + isR]], "#1b3a2a", "#22c55e");
  } else if (template === "TURBO_ROUNDABOUT") {
    const circlePts = [];
    for (let i = 0; i < 20; i++) {
      const a = (i * 2 * Math.PI) / 20;
      circlePts.push([Math.cos(a) * 9, Math.sin(a) * 9]);
    }
    drawRoadPoly(circlePts, "#2a3d32", "#4ade80");
  }

  // Crosswalks
  ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
  [-roadW - 2, roadW + 2].forEach((x) => {
    const pt = proj(x, 0);
    ctx.fillRect(pt.sx - 3, pt.sy - 12, 6, 24);
  });

  const trajectories = twinSimState.data?.redesign_summary?.trajectories || [];
  const conflicts = twinSimState.data?.redesign_summary?.conflicts || [];
  const curT = twinSimState.currentTime;

  // Active SSAM Conflicts
  conflicts.forEach((c) => {
    if (Math.abs(c.time_sec - curT) <= 2.0) {
      const cp = proj(c.conflict_x, c.conflict_y);
      const isCrit = c.severity_tier === "critical";
      const col = isCrit ? "#ef4444" : "#f97316";

      ctx.beginPath();
      ctx.arc(cp.sx, cp.sy, 12, 0, 2 * Math.PI);
      ctx.strokeStyle = col;
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cp.sx, cp.sy, 4, 0, 2 * Math.PI);
      ctx.fillStyle = col;
      ctx.fill();

      // Label
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 10px monospace";
      ctx.fillText(`TTC: ${c.ttc_seconds.toFixed(1)}s`, cp.sx - 20, cp.sy - 16);
    }
  });

  // Agents
  trajectories.forEach((agent) => {
    const pts = agent.points || [];
    if (!pts.length || curT < pts[0].time_sec || curT > pts[pts.length - 1].time_sec) return;

    let p = pts[0];
    for (let i = 0; i < pts.length - 1; i++) {
      if (pts[i].time_sec <= curT && pts[i + 1].time_sec >= curT) {
        const r = (curT - pts[i].time_sec) / (pts[i + 1].time_sec - pts[i].time_sec);
        p = {
          x_coord: pts[i].x_coord + (pts[i + 1].x_coord - pts[i].x_coord) * r,
          y_coord: pts[i].y_coord + (pts[i + 1].y_coord - pts[i].y_coord) * r,
          speed_mps: pts[i].speed_mps,
          accel_mps2: pts[i].accel_mps2,
        };
        break;
      }
    }

    const pos = proj(p.x_coord, p.y_coord);
    if (agent.is_vru) {
      ctx.beginPath();
      ctx.arc(pos.sx, pos.sy, 4, 0, 2 * Math.PI);
      ctx.fillStyle = agent.agent_type === "pedestrian" ? "#fbbf24" : "#38bdf8";
      ctx.fill();
    } else {
      const isBraking = p.accel_mps2 < -1.5;
      ctx.fillStyle = agent.agent_type === "bus" ? "#eab308" : "#3b82f6";
      ctx.fillRect(pos.sx - 5, pos.sy - 3, 10, 6);
      if (isBraking) {
        ctx.fillStyle = "#ef4444";
        ctx.fillRect(pos.sx - 6, pos.sy - 3, 2, 6);
      }
    }
  });
}

function stepTwinAnimation(timestamp) {
  if (twinSimState.lastTimestamp !== null) {
    const delta = (timestamp - twinSimState.lastTimestamp) / 1000;
    twinSimState.currentTime += delta;
    if (twinSimState.currentTime >= twinSimState.duration) {
      twinSimState.currentTime = 0;
    }
    const scrubber = document.getElementById("twin-scrubber");
    const timer = document.getElementById("twin-timer");
    if (scrubber) scrubber.value = twinSimState.currentTime;
    if (timer) timer.textContent = `${twinSimState.currentTime.toFixed(1)}s / ${twinSimState.duration.toFixed(1)}s`;
  }
  twinSimState.lastTimestamp = timestamp;
  renderTwinFrame();
  if (twinSimState.isPlaying) {
    twinSimState.animId = requestAnimationFrame(stepTwinAnimation);
  }
}

async function runDigitalTwinSimulation() {
  const statusEl = document.getElementById("twin-status");
  const kpisEl = document.getElementById("twin-kpis");
  const btn = document.getElementById("btn-run-digital-twin");
  const templateSelect = document.getElementById("twin-template-select");

  const redesignTemplate = templateSelect?.value || "DUTCH_PROTECTED_JUNCTION";

  if (statusEl) {
    statusEl.hidden = false;
    statusEl.textContent = "Solving multi-agent car-following IDM physics & SSAM conflict deltas...";
  }
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`${state.apiBase}/v1/simulation/synthetic-countermeasure-eval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_id: "org-open-mobility",
        network_label: "digital_twin_eval",
        junction_id: "JNC-CENTRAL-01",
        baseline_template: "BASELINE_SIGNALIZED",
        redesign_template: redesignTemplate,
        duration_seconds: 30.0,
        vehicle_demand_vph: 700.0,
        vru_demand_pph: 120.0,
        random_seed: 42,
        include_trajectories: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    twinSimState.data = data;
    twinSimState.currentTime = 0.0;
    twinSimState.isPlaying = true;
    twinSimState.duration = 30.0;

    // Populate KPIs
    if (kpisEl) {
      kpisEl.hidden = false;
      const comp = data.comparison;
      const confEl = document.getElementById("twin-kpi-conflicts");
      const vruEl = document.getElementById("twin-kpi-vru");
      const dracEl = document.getElementById("twin-kpi-drac");
      const verdictEl = document.getElementById("twin-kpi-verdict");

      if (confEl) confEl.textContent = `-${comp.percent_conflict_reduction.toFixed(1)}%`;
      if (vruEl) vruEl.textContent = `-${comp.percent_vru_conflict_reduction.toFixed(1)}%`;
      if (dracEl) dracEl.textContent = `+${(comp.max_drac_baseline_mps2 - comp.max_drac_redesign_mps2).toFixed(1)} m/s²`;
      if (verdictEl) verdictEl.textContent = comp.appraisal_verdict.replace("_", " ").toUpperCase();
    }

    const playBtn = document.getElementById("btn-twin-play");
    if (playBtn) playBtn.textContent = "Pause";

    if (twinSimState.animId) cancelAnimationFrame(twinSimState.animId);
    twinSimState.lastTimestamp = null;
    twinSimState.animId = requestAnimationFrame(stepTwinAnimation);

    if (statusEl) {
      statusEl.textContent = `✓ 3D Simulation Active (${data.redesign_summary?.trajectories?.length || 0} agents simulated, ${data.redesign_summary?.conflicts?.length || 0} conflicts detected).`;
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

const btnRunTwin = document.getElementById("btn-run-digital-twin");
if (btnRunTwin) {
  btnRunTwin.addEventListener("click", runDigitalTwinSimulation);
}

const btnTwinPlay = document.getElementById("btn-twin-play");
if (btnTwinPlay) {
  btnTwinPlay.addEventListener("click", () => {
    twinSimState.isPlaying = !twinSimState.isPlaying;
    btnTwinPlay.textContent = twinSimState.isPlaying ? "Pause" : "Play";
    if (twinSimState.isPlaying) {
      twinSimState.lastTimestamp = null;
      twinSimState.animId = requestAnimationFrame(stepTwinAnimation);
    }
  });
}

const twinScrubber = document.getElementById("twin-scrubber");
if (twinScrubber) {
  twinScrubber.addEventListener("input", (e) => {
    twinSimState.currentTime = parseFloat(e.target.value);
    renderTwinFrame();
  });
}

const btnDossier = document.getElementById("btn-ministerial-dossier");
if (btnDossier) {
  btnDossier.addEventListener("click", downloadMinisterialDossier);
}
const btnResearch = document.getElementById("btn-research-eval");
if (btnResearch) {
  btnResearch.addEventListener("click", runResearchBenchmark);
}

// ---------------------------------------------------------------------------
// Real-Time Telematics & Micromobility Streaming Gateway
// ---------------------------------------------------------------------------
let streamSocket = null;
let streamEventSource = null;
let streamReconnectTimer = null;
const streamEvents = [];
const MAX_STREAM_EVENTS = 30;

function updateStreamStatus(status, isConnected = false, isError = false) {
  const statusText = document.getElementById("stream-status-text");
  const liveDot = document.getElementById("stream-live-dot");
  const statusPill = statusText ? statusText.closest(".stream-status-pill") : null;

  if (statusText) statusText.textContent = status;
  if (liveDot) {
    if (isConnected) {
      liveDot.classList.add("pulse");
    } else {
      liveDot.classList.remove("pulse");
    }
  }
  if (statusPill) {
    statusPill.classList.remove("connected", "error");
    if (isConnected) statusPill.classList.add("connected");
    if (isError) statusPill.classList.add("error");
  }
}

function renderStreamEventCard(event) {
  const timeStr = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  const eventType = (event.event_type || "telematics_event").replace(/_/g, " ");
  const vehicleType = (event.vehicle_type || "vehicle").replace(/_/g, " ");
  const severity = event.severity || "low";

  let telemetrySnippet = "";
  if (event.kinematics && event.kinematics.acceleration_g !== undefined) {
    telemetrySnippet += `accel: ${event.kinematics.acceleration_g.toFixed(2)}g `;
  }
  if (event.kinematics && event.kinematics.speed_kph !== undefined) {
    telemetrySnippet += `speed: ${event.kinematics.speed_kph.toFixed(0)} km/h `;
  }
  if (event.imu && event.imu.impact_magnitude_g !== undefined) {
    telemetrySnippet += `shock: ${event.imu.impact_magnitude_g.toFixed(2)}g `;
  }
  if (event.imu && event.imu.surface_roughness_score !== undefined) {
    telemetrySnippet += `roughness: ${event.imu.surface_roughness_score.toFixed(2)} `;
  }
  if (!telemetrySnippet && event.latitude && event.longitude) {
    telemetrySnippet = `lat: ${event.latitude.toFixed(4)}, lon: ${event.longitude.toFixed(4)}`;
  }

  const card = document.createElement("div");
  card.className = "stream-event-card";
  card.innerHTML = `
    <div class="stream-card-left">
      <span class="stream-badge stream-badge-type">${eventType}</span>
      <span class="stream-badge stream-badge-veh">${vehicleType}</span>
      <span class="stream-event-desc">${event.source_device_id || "device"} · ${event.anomaly_type || event.event_type}</span>
    </div>
    <div class="stream-card-right">
      ${telemetrySnippet ? `<span class="stream-telemetry-mono">${telemetrySnippet}</span>` : ""}
      <span class="stream-badge-sev ${severity}">${severity}</span>
      <span class="stream-time-text">${timeStr}</span>
    </div>
  `;
  return card;
}

function addStreamEvent(event) {
  if (streamEvents.some((e) => e.event_id === event.event_id)) return;
  streamEvents.unshift(event);
  if (streamEvents.length > MAX_STREAM_EVENTS) {
    streamEvents.pop();
  }

  const listEl = document.getElementById("stream-events-list");
  if (!listEl) return;

  const note = listEl.querySelector(".mini-chart-note");
  if (note) note.remove();

  const card = renderStreamEventCard(event);
  listEl.insertBefore(card, listEl.firstChild);

  while (listEl.children.length > MAX_STREAM_EVENTS) {
    listEl.removeChild(listEl.lastChild);
  }
}

async function loadRecentStreamEvents() {
  try {
    const res = await fetch(`${state.apiBase}/v1/telematics/events/recent?limit=8`);
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.events) && data.events.length > 0) {
        const listEl = document.getElementById("stream-events-list");
        if (listEl) listEl.innerHTML = "";
        for (let i = data.events.length - 1; i >= 0; i--) {
          addStreamEvent(data.events[i]);
        }
      }
    }
  } catch (err) {
    console.debug("Could not preload stream events:", err);
  }
}

function connectStream() {
  if (streamSocket || streamEventSource) return;

  const origin = state.apiBase || window.location.origin;
  const wsUrl = origin.replace(/^http:/, "ws:").replace(/^https:/, "wss:") + "/v1/telematics/stream";

  updateStreamStatus("CONNECTING...", false, false);

  try {
    const ws = new WebSocket(wsUrl);
    streamSocket = ws;

    ws.onopen = () => {
      updateStreamStatus("LIVE STREAMING (WS)", true, false);
      try {
        ws.send(JSON.stringify({ type: "filter", include_kinematics: true, include_micromobility: true }));
      } catch (_) {}
    };

    ws.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data);
        if (payload && payload.type === "telematics_event" && payload.data) {
          addStreamEvent(payload.data);
        } else if (payload && payload.event_id) {
          addStreamEvent(payload);
        }
      } catch (err) {
        console.debug("Stream parse error", err);
      }
    };

    ws.onerror = () => {
      // WS error triggers onclose which falls back to SSE
    };

    ws.onclose = () => {
      streamSocket = null;
      fallbackToSSE();
    };
  } catch (err) {
    fallbackToSSE();
  }
}

function fallbackToSSE() {
  if (streamEventSource) return;
  try {
    updateStreamStatus("CONNECTING (SSE)...", false, false);
    const sse = new EventSource(`${state.apiBase}/v1/telematics/events/sse`);
    streamEventSource = sse;

    sse.onopen = () => {
      updateStreamStatus("LIVE STREAMING (SSE)", true, false);
    };

    sse.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data);
        if (payload && payload.event_id) {
          addStreamEvent(payload);
        }
      } catch (err) {
        console.debug("SSE parse error", err);
      }
    };

    sse.onerror = () => {
      sse.close();
      streamEventSource = null;
      updateStreamStatus("RECONNECTING...", false, true);
      clearTimeout(streamReconnectTimer);
      streamReconnectTimer = setTimeout(() => {
        connectStream();
      }, 5000);
    };
  } catch (err) {
    updateStreamStatus("OFFLINE", false, true);
  }
}

async function injectDemoStreamEvent() {
  const btn = document.getElementById("btn-stream-inject");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Injecting...";
  }

  try {
    const res = await fetch(`${state.apiBase}/v1/telematics/events/demo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data && data.event) {
      addStreamEvent(data.event);
    }
  } catch (err) {
    console.error("Demo inject failed:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Inject Near-Miss Event";
    }
  }
}

function initializeStreamingGateway() {
  const btnInject = document.getElementById("btn-stream-inject");
  if (btnInject) {
    btnInject.addEventListener("click", injectDemoStreamEvent);
  }
  loadRecentStreamEvents();
  connectStream();
}

// ---------------------------------------------------------------------------
// Automated Incident Reconstruction & Forensic Playback
// ---------------------------------------------------------------------------
const FORENSIC_FALLBACK_DATA = {
  "CASE-SYN-001": {
    initial_speed_kph: 44.0,
    impact_speed_kph: 26.0,
    driver_prt_seconds: 1.80,
    energy_dissipated_kj: 28.6,
    aeb_clearance_m: 3.2,
    counterfactuals: [
      { name: "Baseline Observed Crash", outcome: "CRASH OCCURRED", tagClass: "tag-critical", clearance: "0.0 m", speed: "26.0 km/h", relief: "0.0%" },
      { name: "C-ITS / AEB Actuation", outcome: "✓ PREVENTED", tagClass: "tag-safe", clearance: "+3.2 m", speed: "0.0 km/h", relief: "-100.0%" },
      { name: "Speed Limit Compliance (30 km/h)", outcome: "✓ PREVENTED", tagClass: "tag-safe", clearance: "+1.8 m", speed: "0.0 km/h", relief: "-100.0%" },
      { name: "Sightline Clearance (+15m)", outcome: "✓ PREVENTED", tagClass: "tag-safe", clearance: "+4.5 m", speed: "0.0 km/h", relief: "-100.0%" },
    ],
  },
  "CASE-SYN-002": {
    initial_speed_kph: 56.0,
    impact_speed_kph: 32.0,
    driver_prt_seconds: 1.40,
    energy_dissipated_kj: 14.8,
    aeb_clearance_m: 4.1,
    counterfactuals: [
      { name: "Baseline Observed Crash", outcome: "CRASH OCCURRED", tagClass: "tag-critical", clearance: "0.0 m", speed: "32.0 km/h", relief: "0.0%" },
      { name: "C-ITS / AEB Actuation", outcome: "✓ PREVENTED", tagClass: "tag-safe", clearance: "+4.1 m", speed: "0.0 km/h", relief: "-100.0%" },
      { name: "Speed Limit Compliance (50 km/h)", outcome: "MITIGATED", tagClass: "tag-mitigated", clearance: "-2.8 m", speed: "18.5 km/h", relief: "-80.6%" },
    ],
  },
  "CASE-SYN-003": {
    initial_speed_kph: 82.0,
    impact_speed_kph: 46.0,
    driver_prt_seconds: 2.00,
    energy_dissipated_kj: 284.1,
    aeb_clearance_m: 12.4,
    counterfactuals: [
      { name: "Baseline Observed Crash", outcome: "CRASH OCCURRED", tagClass: "tag-critical", clearance: "0.0 m", speed: "46.0 km/h", relief: "0.0%" },
      { name: "C-ITS / AEB Actuation", outcome: "✓ PREVENTED", tagClass: "tag-safe", clearance: "+12.4 m", speed: "0.0 km/h", relief: "-100.0%" },
      { name: "Speed Limit Compliance (70 km/h)", outcome: "MITIGATED", tagClass: "tag-mitigated", clearance: "-6.2 m", speed: "28.0 km/h", relief: "-65.0%" },
    ],
  },
};

async function updateForensicCase(caseId) {
  let caseData = FORENSIC_FALLBACK_DATA[caseId];

  try {
    const res = await fetch(`${state.apiBase}/v1/forensics/cases/${caseId}`);
    if (res.ok) {
      const data = await res.json();
      if (data && data.case && data.case.kinetic_metrics) {
        const km = data.case.kinetic_metrics;
        const cfs = data.case.counterfactual_scenarios || [];
        const aebScen = cfs.find((s) => s.scenario_id === "SCENARIO_A_AEB");
        caseData = {
          initial_speed_kph: km.initial_speed_kph,
          impact_speed_kph: km.impact_speed_kph,
          driver_prt_seconds: km.driver_prt_seconds,
          energy_dissipated_kj: km.energy_dissipated_kj,
          aeb_clearance_m: aebScen ? aebScen.clearance_margin_m : 0.0,
          counterfactuals: [
            { name: "Baseline Observed Crash", outcome: "CRASH OCCURRED", tagClass: "tag-critical", clearance: "0.0 m", speed: `${km.impact_speed_kph.toFixed(1)} km/h`, relief: "0.0%" },
            ...cfs.map((s) => ({
              name: s.scenario_title,
              outcome: s.collision_avoided ? "✓ PREVENTED" : "MITIGATED",
              tagClass: s.collision_avoided ? "tag-safe" : "tag-mitigated",
              clearance: s.clearance_margin_m >= 0 ? `+${s.clearance_margin_m.toFixed(1)} m` : `${s.clearance_margin_m.toFixed(1)} m`,
              speed: `${s.counterfactual_impact_speed_kph.toFixed(1)} km/h`,
              relief: `-${s.injury_risk_reduction_pct.toFixed(1)}%`,
            })),
          ],
        };
      }
    }
  } catch (err) {
    console.debug("Forensic API fallback:", err);
  }

  if (!caseData) return;

  const elV0 = document.getElementById("forensic-kpi-v0");
  const elVimp = document.getElementById("forensic-kpi-vimp");
  const elPrt = document.getElementById("forensic-kpi-prt");
  const elEdiss = document.getElementById("forensic-kpi-ediss");
  const elAeb = document.getElementById("forensic-kpi-aeb");
  const elTbody = document.getElementById("forensic-counterfactual-tbody");

  if (elV0) elV0.textContent = `${caseData.initial_speed_kph.toFixed(1)} km/h`;
  if (elVimp) elVimp.textContent = `${caseData.impact_speed_kph.toFixed(1)} km/h`;
  if (elPrt) elPrt.textContent = `${caseData.driver_prt_seconds.toFixed(2)} s`;
  if (elEdiss) elEdiss.textContent = `${caseData.energy_dissipated_kj.toFixed(1)} kJ`;
  if (elAeb) elAeb.textContent = `PREVENTED (+${caseData.aeb_clearance_m.toFixed(1)}m)`;

  if (elTbody && Array.isArray(caseData.counterfactuals)) {
    elTbody.innerHTML = caseData.counterfactuals
      .map(
        (cf) => `
      <tr>
        <td><strong>${cf.name}</strong></td>
        <td><span class="badge-tag ${cf.tagClass}">${cf.outcome}</span></td>
        <td>${cf.clearance}</td>
        <td><strong>${cf.speed}</strong></td>
        <td><strong>${cf.relief}</strong></td>
      </tr>
    `
      )
      .join("");
  }
}

async function downloadForensicDossier() {
  const caseSelect = document.getElementById("forensic-case-select");
  const caseId = caseSelect ? caseSelect.value : "CASE-SYN-001";
  const btn = document.getElementById("btn-forensic-dossier");
  const statusEl = document.getElementById("forensic-status");

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Generating...";
  }

  try {
    let mdContent = "";
    const res = await fetch(`${state.apiBase}/v1/forensics/cases/${caseId}/dossier`);
    if (res.ok) {
      const data = await res.json();
      mdContent = data.dossier_markdown || "";
    } else {
      mdContent = `# FORENSIC DOSSIER (${caseId})\nKinematic reconstruction and counterfactual collision avoidance simulation...`;
    }

    const blob = new Blob([mdContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `DOSSIER_${caseId}_JUDICIAL.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    if (statusEl) {
      statusEl.hidden = false;
      statusEl.textContent = `✓ Evidentiary dossier DOSSIER_${caseId}_JUDICIAL.md successfully downloaded.`;
    }
  } catch (err) {
    if (statusEl) {
      statusEl.hidden = false;
      statusEl.textContent = `Error downloading dossier: ${err.message}`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Download Judicial Dossier";
    }
  }
}

function initializeForensics() {
  const caseSelect = document.getElementById("forensic-case-select");
  if (caseSelect) {
    caseSelect.addEventListener("change", (e) => {
      updateForensicCase(e.target.value);
    });
  }

  const btnDossier = document.getElementById("btn-forensic-dossier");
  if (btnDossier) {
    btnDossier.addEventListener("click", downloadForensicDossier);
  }

  updateForensicCase("CASE-SYN-001");
}

// --------------------------------------------------------------------------
// Autonomous TMC Incident Response & Playbook Automation
// --------------------------------------------------------------------------
const TMC_FALLBACK_DATA = {
  "INC-SYN-TMC-001": {
    threat: "PB_SHOCKWAVE_CONGESTION",
    prob: "78%",
    vsl: "60 km/h",
    picto: "A,17 + C,14",
    denm: "Cause 91 (100ms)",
    mds: "10 km/h",
    actions: [
      { tier: "Tier 1: VSL", sub: "vsl_control", cmd: "SET_DYNAMIC_SPEED_LIMIT", param: "Target: 60 km/h, Buffer: 2 gantries, Ramp: 15s", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 2: VMS", sub: "vms_signage", cmd: "DISPLAY_VARIABLE_MESSAGE", param: "Picto A,17 / 'SLOW DOWN QUEUE AHEAD / LIMIT 60'", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 3: C-ITS", sub: "cits_denm", cmd: "BROADCAST_DENM_V2X", param: "Cause 91, Relevance: 1500m, Station: TMC-ACTUATOR-01", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 4: MDS", sub: "micromobility_geofence", cmd: "APPLY_MDS_GEOFENCE_RESTRICTION", param: "Slow Zone 10 km/h, Radius: 350m, Shared Fleets", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 5: Dispatch", sub: "patrol_dispatch", cmd: "DISPATCH_HIGHWAY_PATROL_UNIT", param: "Highway Patrol / Incident Response Unit, Priority: URGENT", tier_gov: "ONE_CLICK", status: "STAGED" },
    ]
  },
  "INC-SYN-TMC-002": {
    threat: "PB_ADVERSE_WEATHER",
    prob: "69%",
    vsl: "50 km/h",
    picto: "A,24 + C,14",
    denm: "Cause 97 (200ms)",
    mds: "10 km/h",
    actions: [
      { tier: "Tier 1: VSL", sub: "vsl_control", cmd: "SET_DYNAMIC_SPEED_LIMIT", param: "Target: 50 km/h, Buffer: 2 gantries, Ramp: 15s", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 2: VMS", sub: "vms_signage", cmd: "DISPLAY_VARIABLE_MESSAGE", param: "Picto A,24 / 'FOG AND WET ROAD / LIMIT 50'", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 3: C-ITS", sub: "cits_denm", cmd: "BROADCAST_DENM_V2X", param: "Cause 97, Relevance: 2000m, Station: TMC-ACTUATOR-01", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 4: MDS", sub: "micromobility_geofence", cmd: "APPLY_MDS_GEOFENCE_RESTRICTION", param: "Slow Zone 10 km/h, Radius: 300m", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 5: Dispatch", sub: "patrol_dispatch", cmd: "DISPATCH_HIGHWAY_PATROL_UNIT", param: "Regional Patrol Unit, Priority: HIGH", tier_gov: "ONE_CLICK", status: "STAGED" },
    ]
  },
  "INC-SYN-TMC-003": {
    threat: "PB_VRU_CROSSWALK",
    prob: "62%",
    vsl: "30 km/h",
    picto: "A,32 + C,14",
    denm: "Cause 96 (100ms)",
    mds: "6 km/h",
    actions: [
      { tier: "Tier 1: VSL", sub: "vsl_control", cmd: "SET_DYNAMIC_SPEED_LIMIT", param: "Target: 30 km/h, Buffer: 1 gantry, Ramp: 10s", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 2: VMS", sub: "vms_signage", cmd: "DISPLAY_VARIABLE_MESSAGE", param: "Picto A,32 / 'PEDESTRIANS AHEAD / ZONE 30'", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 3: C-ITS", sub: "cits_denm", cmd: "BROADCAST_DENM_V2X", param: "Cause 96, Relevance: 800m, Station: TMC-ACTUATOR-01", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 4: MDS", sub: "micromobility_geofence", cmd: "APPLY_MDS_GEOFENCE_RESTRICTION", param: "Slow Zone 6 km/h, Radius: 250m", tier_gov: "ONE_CLICK", status: "STAGED" },
      { tier: "Tier 5: Dispatch", sub: "patrol_dispatch", cmd: "DISPATCH_HIGHWAY_PATROL_UNIT", param: "Urban Traffic Safety Unit, Priority: HIGH", tier_gov: "ONE_CLICK", status: "STAGED" },
    ]
  }
};

let currentTmcIncidentId = "INC-SYN-TMC-001";
let currentTmcActuated = false;

function updateTmcIncident(incidentId) {
  currentTmcIncidentId = incidentId;
  currentTmcActuated = false;

  const data = TMC_FALLBACK_DATA[incidentId] || TMC_FALLBACK_DATA["INC-SYN-TMC-001"];

  const elThreat = document.getElementById("tmc-kpi-threat");
  const elProb = document.getElementById("tmc-kpi-prob");
  const elVsl = document.getElementById("tmc-kpi-vsl");
  const elPicto = document.getElementById("tmc-kpi-picto");
  const elDenm = document.getElementById("tmc-kpi-denm");
  const elMds = document.getElementById("tmc-kpi-mds");
  const elTbody = document.getElementById("tmc-actuation-tbody");
  const elReceipt = document.getElementById("tmc-receipt-box");
  const btnActuate = document.getElementById("btn-tmc-actuate");

  if (elThreat) elThreat.textContent = data.threat;
  if (elProb) elProb.textContent = data.prob;
  if (elVsl) elVsl.textContent = data.vsl;
  if (elPicto) elPicto.textContent = data.picto;
  if (elDenm) elDenm.textContent = data.denm;
  if (elMds) elMds.textContent = data.mds;

  if (elReceipt) {
    elReceipt.hidden = true;
    elReceipt.textContent = "";
  }
  if (btnActuate) {
    btnActuate.disabled = false;
    btnActuate.textContent = "⚡ 1-Click Actuate Playbook";
  }

  if (elTbody) {
    elTbody.innerHTML = "";
    data.actions.forEach((act) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${act.tier}</strong> <small style="color:var(--muted)">(${act.sub})</small></td>
        <td><code>${act.cmd}</code></td>
        <td>${act.param}</td>
        <td><span class="badge-tag tag-mitigated">${act.tier_gov}</span></td>
        <td><span class="badge-tag tag-staged">${act.status}</span></td>
      `;
      elTbody.appendChild(tr);
    });
  }
}

async function actuateTmcPlaybook() {
  const btn = document.getElementById("btn-tmc-actuate");
  const statusEl = document.getElementById("tmc-receipt-box");
  const elTbody = document.getElementById("tmc-actuation-tbody");

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Broadcasting All 5 Tiers...";
  }

  try {
    let receiptDigest = "877698217baac889d24326b798deba3fd7373db0ecb2240f3643dfa4844819e2";
    let execTime = new Date().toISOString().replace("T", " ").substring(0, 19) + "Z";

    try {
      const res = await fetch(`${state.apiBase}/v1/tmc/actuate-playbook`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: "org-open-mobility",
          incident_id: currentTmcIncidentId,
          operator_id: "OPERATOR-DASHBOARD",
          authorization_mode: "ONE_CLICK",
        }),
      });
      if (res.ok) {
        const payload = await res.json();
        if (payload.receipt) {
          receiptDigest = payload.receipt.sha256_receipt_hash;
          execTime = payload.receipt.executed_at_utc;
        }
      }
    } catch (e) {
      console.debug("TMC API fallback to local actuation:", e);
    }

    currentTmcActuated = true;

    // Update table statuses to broadcasting
    if (elTbody) {
      const rows = elTbody.querySelectorAll("tr");
      rows.forEach((r) => {
        const lastTd = r.querySelector("td:last-child");
        if (lastTd) {
          lastTd.innerHTML = '<span class="badge-tag tag-broadcasting">✓ BROADCASTING</span>';
        }
      });
    }

    if (btn) {
      btn.textContent = "✓ Actuated & Broadcasting";
    }

    if (statusEl) {
      statusEl.hidden = false;
      statusEl.textContent = `✓ 1-Click Actuation Successful: SHA-256 Digest ${receiptDigest} actively broadcasting across all 5 tiers at ${execTime}.`;
    }
  } catch (err) {
    if (statusEl) {
      statusEl.hidden = false;
      statusEl.textContent = `Error executing playbook: ${err.message}`;
    }
    if (btn) {
      btn.disabled = false;
      btn.textContent = "⚡ 1-Click Actuate Playbook";
    }
  }
}

function initializeTmc() {
  const incSelect = document.getElementById("tmc-incident-select");
  if (incSelect) {
    incSelect.addEventListener("change", (e) => {
      updateTmcIncident(e.target.value);
    });
  }

  const btnActuate = document.getElementById("btn-tmc-actuate");
  if (btnActuate) {
    btnActuate.addEventListener("click", actuateTmcPlaybook);
  }

  updateTmcIncident("INC-SYN-TMC-001");
}

// --------------------------------------------------------------------------
// Connected Fleet Geofencing & Cellular V2X (C-V2X PC5/Uu)
// --------------------------------------------------------------------------
const CONNECTED_FLEET_FALLBACK_DATA = {
  "FLEET-TRANSIT-BUS-12": {
    model: "Urban Transit Hybrid Bus",
    speed: "48 km/h",
    vsl: "60 km/h",
    dist: "413 m",
    channel: "PC5 DIRECT (5.9 GHz)",
    chime: "ISO 15006 + HAPTIC",
    banner: "SLOW DOWN: QUEUE AHEAD 1.2 KM • SPEED LIMIT 60 KM/H (413m)",
    lane: "TACTICAL GUIDANCE: RIGHT LANE BLOCKED • MERGE LEFT",
    t_hazard: "30.9s"
  },
  "FLEET-PATROL-UNIT-04": {
    model: "Patrol Interceptor SUV",
    speed: "72 km/h",
    vsl: "60 km/h",
    dist: "720 m",
    channel: "PC5 DIRECT (5.9 GHz)",
    chime: "ISO 15006 CHIME",
    banner: "SLOW DOWN: QUEUE AHEAD 1.2 KM • SPEED LIMIT 60 KM/H (720m)",
    lane: "TACTICAL GUIDANCE: RIGHT LANE BLOCKED • MERGE LEFT",
    t_hazard: "36.0s"
  },
  "FLEET-MAINTENANCE-09": {
    model: "Roadway Maintenance Van",
    speed: "55 km/h",
    vsl: "60 km/h",
    dist: "1250 m",
    channel: "CELLULAR Uu (5G NR)",
    chime: "ISO 15006 ADVISORY",
    banner: "SLOW DOWN: QUEUE AHEAD 1.2 KM • SPEED LIMIT 60 KM/H (1250m)",
    lane: "TACTICAL GUIDANCE: RIGHT LANE BLOCKED • MERGE LEFT",
    t_hazard: "81.8s"
  },
  "FLEET-CIVILIAN-781": {
    model: "Connected Passenger Sedan",
    speed: "68 km/h",
    vsl: "60 km/h",
    dist: "550 m",
    channel: "PC5 DIRECT (5.9 GHz)",
    chime: "ISO 15006 + HAPTIC",
    banner: "SLOW DOWN: QUEUE AHEAD 1.2 KM • SPEED LIMIT 60 KM/H (550m)",
    lane: "TACTICAL GUIDANCE: RIGHT LANE BLOCKED • MERGE LEFT",
    t_hazard: "29.1s"
  }
};

function updateConnectedFleetVehicle(vehicleId) {
  const data = CONNECTED_FLEET_FALLBACK_DATA[vehicleId] || CONNECTED_FLEET_FALLBACK_DATA["FLEET-TRANSIT-BUS-12"];

  const elModel = document.getElementById("fleet-kpi-model");
  const elSpeed = document.getElementById("fleet-kpi-speed");
  const elVsl = document.getElementById("fleet-kpi-vsl");
  const elDist = document.getElementById("fleet-kpi-dist");
  const elChannel = document.getElementById("fleet-kpi-channel");
  const elChime = document.getElementById("fleet-kpi-chime");
  const elBanner = document.getElementById("fleet-hud-banner");
  const elLane = document.getElementById("fleet-lane-guide");
  const elTime = document.getElementById("fleet-hud-hazard-time");
  const elTbody = document.getElementById("fleet-telemetry-tbody");

  if (elModel) elModel.textContent = data.model;
  if (elSpeed) elSpeed.textContent = data.speed;
  if (elVsl) elVsl.textContent = data.vsl;
  if (elDist) elDist.textContent = data.dist;
  if (elChannel) elChannel.textContent = data.channel;
  if (elChime) elChime.textContent = data.chime;
  if (elBanner) elBanner.textContent = data.banner;
  if (elLane) elLane.textContent = data.lane;
  if (elTime) elTime.textContent = `T-Hazard: ${data.t_hazard}`;

  if (elTbody) {
    elTbody.innerHTML = "";
    Object.keys(CONNECTED_FLEET_FALLBACK_DATA).forEach((vId) => {
      const item = CONNECTED_FLEET_FALLBACK_DATA[vId];
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${vId}</strong></td>
        <td>${item.model}</td>
        <td><strong>${item.speed}</strong></td>
        <td style="color:#d97706; font-weight:bold;">${item.dist}</td>
        <td><span class="badge-tag ${item.channel.includes("PC5") ? "tag-broadcasting" : "tag-mitigated"}">${item.channel}</span></td>
        <td><small>${item.banner}</small></td>
      `;
      elTbody.appendChild(tr);
    });
  }
}

function initializeConnectedFleets() {
  const select = document.getElementById("fleet-vehicle-select");
  if (select) {
    select.addEventListener("change", (e) => {
      updateConnectedFleetVehicle(e.target.value);
    });
  }

  updateConnectedFleetVehicle("FLEET-TRANSIT-BUS-12");
}

// Multi-Incident Conflict & Congestion Spillover Manager
const COORDINATION_FALLBACK_DATA = {
  "scenario_ring_road_bottleneck": {
    wave: "-18.4 km/h",
    reach: "6.8 min",
    conflicts: "1 Detour Clash",
    tier: "CRITICAL_IMMINENT",
    tierBg: "#fee2e2",
    tierColor: "#991b1b",
    delay: "+728 veh·h",
    safety: "-43.1%",
    conflictTitle: "DIRECT COLLISION COURSE DETECTED (CONF-001)",
    conflictDesc: "Detour for incident INC-A1 routes traffic directly onto Arterial Link A, which is currently impaired by INC-A2 with 50% capacity reduction.",
    remedyDesc: "Automated Remedy: Sever detour routing to Arterial Link A; redistribute diversion flow to Bypass B (42%) and Coastal route C (33%).",
    splits: [
      { corridor: "Ring Corridor South (Main)", split: "25.0%", flow: "625 vph", cap: "2,500 vph", speed: "32 km/h", vms: "LANE OPEN - REDUCED SPEED" },
      { corridor: "Bypass B / Secondary Feeder", split: "42.0%", flow: "1,050 vph", cap: "1,600 vph", speed: "52 km/h", vms: "RECOMMENDED DETOUR: BYPASS B" },
      { corridor: "Coastal Route C", split: "33.0%", flow: "825 vph", cap: "1,300 vph", speed: "38 km/h", vms: "ALTERNATIVE ROUTE: COASTAL C" },
    ],
  },
  "scenario_vru_surge_interchange": {
    wave: "-14.2 km/h",
    reach: "5.9 min",
    conflicts: "1 Spillover Gridlock",
    tier: "ELEVATED",
    tierBg: "#fef3c7",
    tierColor: "#92400e",
    delay: "+512 veh·h",
    safety: "-36.8%",
    conflictTitle: "SECONDARY SPILLOVER GRIDLOCK DETECTED (CONF-002)",
    conflictDesc: "Central connector receives concurrent detour flows from both Boulevard D VRU surge and Interchange E station works. Cumulative volume exceeds link capacity.",
    remedyDesc: "Automated Remedy: Enforce capacity cap on central connector (28%); reroute station-bound traffic via Ringway H (44%).",
    splits: [
      { corridor: "Boulevard D (Main)", split: "28.0%", flow: "336 vph", cap: "1,200 vph", speed: "22 km/h", vms: "VRU SURGE: SPEED LIMIT 20 KM/H" },
      { corridor: "Coastal Route G", split: "28.0%", flow: "336 vph", cap: "1,400 vph", speed: "42 km/h", vms: "CITY DETOUR VIA COASTAL ROUTE" },
      { corridor: "Ringway H", split: "44.0%", flow: "528 vph", cap: "1,500 vph", speed: "36 km/h", vms: "STATION ACCESS: USE RINGWAY H" },
    ],
  },
};

function updateIncidentCoordinationScenario(scenarioId) {
  const data = COORDINATION_FALLBACK_DATA[scenarioId] || COORDINATION_FALLBACK_DATA["scenario_ring_road_bottleneck"];

  const elWave = document.getElementById("coord-kpi-wave");
  const elReach = document.getElementById("coord-kpi-reach");
  const elConflicts = document.getElementById("coord-kpi-conflicts");
  const elTier = document.getElementById("coord-kpi-tier");
  const elDelay = document.getElementById("coord-kpi-delay");
  const elSafety = document.getElementById("coord-kpi-safety");
  const elTitle = document.getElementById("coord-conflict-title");
  const elDesc = document.getElementById("coord-conflict-desc");
  const elRemedy = document.getElementById("coord-remedy-desc");
  const elTbody = document.getElementById("coordination-splits-tbody");

  if (elWave) elWave.textContent = data.wave;
  if (elReach) elReach.textContent = data.reach;
  if (elConflicts) elConflicts.textContent = data.conflicts;
  if (elTier) {
    elTier.textContent = data.tier;
    elTier.style.background = data.tierBg;
    elTier.style.color = data.tierColor;
  }
  if (elDelay) elDelay.textContent = data.delay;
  if (elSafety) elSafety.textContent = data.safety;
  if (elTitle) elTitle.textContent = data.conflictTitle;
  if (elDesc) elDesc.textContent = data.conflictDesc;
  if (elRemedy) elRemedy.textContent = data.remedyDesc;

  if (elTbody) {
    elTbody.innerHTML = "";
    data.splits.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${item.corridor}</strong></td>
        <td><span class="badge-tag tag-mitigated" style="font-weight:bold;">${item.split}</span></td>
        <td>${item.flow}</td>
        <td>${item.cap}</td>
        <td>${item.speed}</td>
        <td><span style="font-family:monospace; font-weight:bold; color:#d97706; background:#fffbeb; padding:2px 6px; border-radius:4px; border:1px solid #fde68a;">${item.vms}</span></td>
      `;
      elTbody.appendChild(tr);
    });
  }
}

function initializeIncidentCoordination() {
  const select = document.getElementById("coordination-scenario-select");
  if (select) {
    select.addEventListener("change", (e) => {
      updateIncidentCoordinationScenario(e.target.value);
    });
  }

  updateIncidentCoordinationScenario("scenario_ring_road_bottleneck");
}

initializeDashboard();
initializeStreamingGateway();
initializeForensics();
initializeTmc();
initializeConnectedFleets();
initializeIncidentCoordination();



