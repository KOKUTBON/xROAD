# First Dashboard

The repo now has a first same-origin dashboard client served by the local published API.

## Purpose

This is the first maintainable front end on top of the serving layer.

It is intentionally narrow:

- read-only
- public-contract only
- same-origin with the local API
- driven entirely by the published-resource index and manifest-backed query routes

That means the browser never reads raw crash records directly.

## Run

Refresh the published index and dashboard summary first:

```bash
road-risk build-published-refresh-bundle \
  --data-root data \
  --registry-output-dir data/registry \
  --published-index-output-dir data/published_index \
  --dashboard-output-dir data/dashboard \
  --output-dir data/reporting/published_refresh/latest
```

Start the local API plus dashboard assets with:

```bash
road-risk serve-published-api \
  --host 127.0.0.1 \
  --port 8000 \
  --published-index-path data/published_index/published_resources.json \
  --root-dir . \
  --dashboard-dir dashboard \
  --dashboard-summary-path data/dashboard/dashboard_summary.json
```

Then open:

- `http://127.0.0.1:8000/dashboard/`

## Current Behavior

The dashboard currently:

- loads the published-resource index
- loads a static dashboard summary built from published resources plus transferability metrics
- carries published-resource freshness flags and lineage traces through that summary payload for downstream consumers
- lists available public resources from that index
- filters by prediction run, year, and tile size where relevant
- queries the published API for the latest matching resource
- renders public tile or segment GeoJSON through the MapLibre web map surface in `apps/web`, with a lightweight SVG fallback for no-WebGL environments
- shows top-ranked records and selected feature details
- exposes the exact request trace used for the current view
- compares the latest published municipality runs in a side-panel summary
- shows cross-jurisdiction transferability deviance for temporal, cold-start, and history-free modes
- highlights intervention-oriented charts for very-high tile count, top-5 crash concentration, and cold-start transfer gap
- shows an intervention shortlist for the selected city with top corridors and very-high hotspot tiles derived from published analyst and tile summaries
- expands the selected corridor or hotspot tile into supporting top-segment detail and switches the surface toward the relevant public view
- pairs cleanly with exportable intervention briefs built from the same summary artifact

## Current Scope

This is a first public overview client, not the final analyst application.

Current published municipality runs in the dashboard flow:

- Bari
- Foggia municipality
- Taranto municipality
- Lecce municipality

What it already does well:

- avoids raw browser-side data loading
- uses the same contracts as downstream API consumers
- resolves latest-vs-stale published artifacts through the same index and refresh rules as the API
- works for both `segment_score_tiles` and `segment_scores`
- stays on the same origin as the local read-only API

What it does not do yet:

- authentication
- municipality scoping
- analyst-only views
- intervention workflow tools
- production deployment packaging
