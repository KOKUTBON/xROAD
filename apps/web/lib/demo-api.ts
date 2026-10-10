import { STATIC_DEMO, publicAsset } from "./demo-mode";

type Snapshot = Record<string, unknown>;
let snapshot: Promise<Snapshot> | undefined;

function json(payload: unknown, status = 200): Response {
  return Response.json(payload, { status });
}

async function loadSnapshot(signal?: AbortSignal | null): Promise<Snapshot> {
  if (!snapshot) {
    snapshot = fetch(publicAsset("/demo/api.json"), { signal }).then(async (response) => {
      if (!response.ok) throw new Error("Demo sample data could not be loaded.");
      return response.json() as Promise<Snapshot>;
    }).catch((error) => { snapshot = undefined; throw error; });
  }
  return snapshot;
}

/** Resolve only demo API calls locally. Production requests use normal fetch. */
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!STATIC_DEMO) return fetch(input, init);
  const url = new URL(input instanceof Request ? input.url : String(input), "http://demo.local");
  const marker = "/api/backend";
  const index = url.pathname.indexOf(marker);
  if (index < 0) return fetch(input, init);
  const path = url.pathname.slice(index + marker.length);
  const method = (init?.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
  if (method !== "GET") {
    return json({ detail: "This action requires the institutional backend. The public demo uses read-only sample data; nothing was submitted or saved." }, 409);
  }
  const data = await loadSnapshot(init?.signal);
  if (!(path in data)) return json({ detail: "This workflow has no bundled sample in the static demo. Connect an institutional backend to use it." }, 404);
  const payload = structuredClone(data[path]);
  // GeoJSON is stored as inspectable local files, separate from API envelopes.
  async function hydrate(value: unknown): Promise<void> {
    if (!value || typeof value !== "object") return;
    const record = value as Record<string, unknown>;
    if (typeof record.demo_geojson === "string") {
      const response = await fetch(publicAsset(record.demo_geojson), { signal: init?.signal });
      if (!response.ok) throw new Error("Local demo GeoJSON could not be loaded.");
      const collection = await response.json();
      const bands = ["low", "moderate", "high", "very_high"];
      const minimum = bands.indexOf(url.searchParams.get("min_score_band") || "low");
      const year = url.searchParams.get("occurred_year");
      const limit = Number(url.searchParams.get("limit") || 10000);
      collection.features = collection.features.filter((feature: { properties: Record<string, unknown> }) => {
        const properties = feature.properties;
        return bands.indexOf(String(properties.public_score_band || properties.tile_public_score_band || "high")) >= minimum
          && (!year || !properties.occurred_year || String(properties.occurred_year) === year);
      }).slice(0, limit);
      record.data = collection;
      record.stats = { returned_features: collection.features.length };
      delete record.demo_geojson;
    }
    await Promise.all(Object.values(record).map((child) => hydrate(child)));
  }
  await hydrate(payload);
  const envelope = payload as Record<string, any>;
  if (path.endsWith("/risk-map") && envelope.map_resource) {
    const features = envelope.map_resource.data.features;
    envelope.summary.tile_rows = features.length;
    envelope.summary.tiles_high_or_very_high = features.filter((f: any) => ["high", "very_high"].includes(f.properties.tile_public_score_band)).length;
    envelope.summary.tiles_very_high = features.filter((f: any) => f.properties.tile_public_score_band === "very_high").length;
    envelope.filters = Object.fromEntries(url.searchParams);
  }
  if (envelope.intervention_shortlist) {
    const bands = ["low", "moderate", "high", "very_high"];
    const minimum = bands.indexOf(url.searchParams.get("min_score_band") || "low");
    envelope.intervention_shortlist.hotspot_tiles = envelope.intervention_shortlist.hotspot_tiles.filter((row: any) => bands.indexOf(row.tile_public_score_band) >= minimum);
  }
  if (envelope.recommendations) {
    envelope.recommendations = envelope.recommendations.filter((row: any) => row.benefit_cost_ratio >= Number(url.searchParams.get("minimum_bcr") || 0) && (!url.searchParams.get("review_state") || row.review_state === url.searchParams.get("review_state")));
    envelope.recommendation_count = envelope.recommendations.length;
  }
  if (envelope.segment_layer && envelope.segment_details) {
    const ids = new Set(envelope.segment_layer.data.features.map((f: any) => f.properties.segment_score_id));
    envelope.segment_details.rows = envelope.segment_details.rows.filter((row: any) => ids.has(row.segment_score_id));
  }
  return json(payload);
}
