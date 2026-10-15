# Climate-Resilience GIS Layer

Extreme weather degrades both road-network safety and infrastructure
resilience. This module adds the climate-resilience data foundation and a
map-ready surface so local and regional authorities can identify and map where
weather hazards and crash risk overlap.

Implementation: `src/road_risk_modeling/climate_resilience.py`. Demo:
`tools/climate_resilience_demo.py` → `data/reporting/climate_resilience/`.

## What it does

### 1. Hazard ingestion

`ingest_hazard_layer` folds extreme-weather hazard-grid records into per-segment
exposures for four hazard families — **flood, heat, snow/ice,
wind** — keeping the worst exposure per hazard where a segment spans several
cells. The record shape (`segment_id`, `hazard_kind`, `intensity ∈ [0,1]`) is
what a join against a **Copernicus / EEA** climate-hazard layer produces.

### 2. Weather-conditioned crash risk

`weather_conditioned_risk` compares each segment's **adverse-weather crash
share** against a baseline (~25% of the time adverse) and returns a multiplier
≥ 1.0 where adverse-condition crashes are over-represented — the empirical
"risk under adverse conditions vs baseline". It is
capped to bound sparse-cell noise and returns `None` when the split is absent.

### 3. Infrastructure-resilience scoring

`score_segment_climate_risk` multiplies each hazard's **exposure** by an
attribute-derived structural **vulnerability** and combines them into a 0–100
climate-risk score (higher = least resilient), then amplifies by the
weather-conditioned multiplier:

| Hazard | Vulnerability driver (transparent) |
| --- | --- |
| Flood | bridges / tunnels / underpasses (flood-critical structures) |
| Snow/ice | fast + curvy sections; bridges freeze first |
| Wind | exposed structures (bridges, embankments) |
| Heat | higher-traffic (higher-class) pavements degrade fastest |

Hazard weights (flood 0.32, snow/ice 0.28, wind 0.22, heat 0.18) are an
engineering default to calibrate per region.

### 4. Map-ready GeoJSON surface

`run_climate_resilience_assessment` emits a **GeoJSON FeatureCollection**
(`climate_risk_surface.geojson`) with per-segment `climate_risk_score`,
`dominant_hazard`, and the weather multiplier — the surface the apps/web
MapLibre risk map renders so authorities can **see where extreme weather most
degrades network safety**. It also writes a classification CSV, a summary JSON,
and a lineage-hashed manifest.

### 5. Governance for the new record kinds

`CLIMATE_FIELD_CLASSIFICATIONS` declares data-governance entries for the new
`climate_hazard` / `climate_resilience` record kinds: hazard family and the
aggregate climate-risk score are **public** (the map surface); raw provider
hazard-grid intensity is **internal** under provider licensing. These should be
merged into the central registry in `data_governance.py`.

## Web map surface

The interactive map is live at **`/workspace/climate`** (analyst area):
`apps/web/components/climate-map.tsx` loads the published
`climate_risk_surface.geojson` (served from `apps/web/public/climate/`) and
renders each road section as a MapLibre circle coloured by its climate-risk band
(low / moderate / high / severe), with a **hazard filter**, a **legend**, a
**summary** (sections, mean risk, high-risk count, peak), and a per-section
popup. The colour scale and summary logic live in `apps/web/lib/climate-overlay.ts`
(unit-tested, framework-free), so authorities can see on a map where extreme
weather most degrades road-network safety.

## Honest scope

- Hazard exposures are **ingested inputs**: supply your own licensed hazard
  layer (for example Copernicus/EEA products).
- Vulnerability and hazard weights are **transparent engineering defaults** to
  calibrate per region with local asset and climate data.
- Scoring is **rule-based and auditable** by design — a resilience
  classification informs public investment and must be inspectable.

## CLI

```bash
road-risk climate-resilience \
  --segments path/to/segments.csv \
  --hazards path/to/hazards.csv \
  --output-dir data/reporting/climate_resilience
```
