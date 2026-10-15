# Road Risk Web Shell

This directory contains the production frontend shell for the municipal road-safety intelligence platform. The shell is organized around public transparency, executive control, analyst investigation, traffic engineering, reporting, administration, automation, and system-health workflows.

## Stack

- Next.js App Router
- TypeScript
- MapLibre GL JS for public and analyst map work surfaces
- CSS design-system baseline in `app/globals.css`
- cookie-backed OIDC session bridge that can:
  - redirect to a Keycloak-compatible identity provider from `/api/auth/login`
  - exchange the callback code at `/api/auth/callback`
  - hydrate frontend sessions from `/api/auth/session`, which calls the FastAPI `/v1/auth/me` endpoint with the bearer token
  - proxy API calls through `/api/backend/*` so backend JWKS/RBAC checks receive the bearer token
  - keep demo profiles available only when `NEXT_PUBLIC_ENABLE_DEMO_AUTH=true` is set outside production

## Routes

- `/` public risk map backed by published tiles, intervention shortlists, and published transparency reports
- `/login` production OIDC login with explicit local-demo fallback when enabled
- `/workspace` internal shared shell
- `/workspace/executive` executive KPIs, budget impact, priority board, and monthly briefing entry
- `/workspace/reports` reporting hub with executive KPIs, report history, export generation, review/publish/archive lifecycle actions, governed downloads, and public transparency publication controls
- `/workspace/analyst` analyst risk explorer backed by segment, junction, and crossing layers
- `/workspace/scenarios` scenario planner for ranked interventions, draft authoring, before/after runs, managed intervention portfolio lifecycle, and assumptions
- `/workspace/operations` capability-gated VRU and signal-phase operations board
- `/workspace/admin` admin route frame and control-center
- `/workspace/uploads` browser Upload Center for source selection, schema mapping, object-storage upload, validation review, approve/reject decisions, worker execution, retry, and cancellation
- `/workspace/automation` automation schedules, pause/resume/update controls, stale-source checks, recent runs, and notification delivery dry-runs
- `/workspace/system-health` release readiness, observability, runbook, and smoke-test posture

## Quick start

```bash
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000>.

By default, browser API calls go through `/api/backend/*`, which forwards to `http://localhost:8000` and attaches the secure auth cookie as a bearer token. Override the backend target for the web server with:

```bash
ROAD_RISK_WEB_API_BASE_URL=http://localhost:8000 npm run dev
```

Production login expects a Keycloak-compatible OIDC configuration:

```bash
ROAD_RISK_WEB_OIDC_ISSUER=https://auth.example.gov/realms/road-risk
ROAD_RISK_WEB_OIDC_CLIENT_ID=road-risk-web
ROAD_RISK_WEB_OIDC_CLIENT_SECRET=...
```

Set `ROAD_RISK_WEB_OIDC_AUTHORIZATION_ENDPOINT`, `ROAD_RISK_WEB_OIDC_TOKEN_ENDPOINT`, or `ROAD_RISK_WEB_OIDC_LOGOUT_ENDPOINT` when using a provider that does not expose Keycloak-style endpoint paths. For local shell testing only, enable demo profiles with:

```bash
NEXT_PUBLIC_ENABLE_DEMO_AUTH=true npm run dev
```

The demo flag is ignored when `NODE_ENV=production`.

## Commands

```bash
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npm run e2e
npm run smoke:routes
```

`npm run smoke:routes` expects a running web server, for example `npm run dev` or
`npm run start`, and checks every v1 public and workspace route with desktop and
mobile viewport headers.

Protected routes are expected to redirect to `/login` unless `WEB_SMOKE_ACCESS_TOKEN`
is supplied. For staging, provide a short-lived test token with the required
workspace roles so the same smoke script can validate authenticated route access.

`npm run e2e` is the browser release gate. It starts the Next.js dev server on
`127.0.0.1:3100` with demo auth enabled, intercepts backend calls with deterministic
API fixtures, and runs Chromium desktop and mobile projects. The gate covers the
public map, login, workspace overview, analyst map, no-access state, Upload Center
file validation, Reports generation, Admin control center, Automation manual
refresh, and Traffic Operations VRU/signal-phase pages. It also checks keyboard
reachability, visible control labels, missing image alt text, mobile horizontal
overflow, and attaches full-page visual-smoke screenshots to the Playwright run.
Web CI runs the same suite through the hosted Chrome channel to avoid downloading
browser binaries on every pull request. Local runs use Playwright-managed Chromium
after `npx playwright install chromium`.

Use a different local web port only when needed:

```bash
PLAYWRIGHT_WEB_PORT=3200 npm run e2e
```

## Current scope

The current scope is no longer only the application frame:

- auth-aware route handling
- grouped public, executive, analyst, traffic-engineering, and admin navigation
- shared navigation entries for scenarios, operations, and automation
- unified workspace information architecture across public, analytical, and operational roles
- reporting hub for executive, technical, data-quality/governance, intervention-portfolio, and public-transparency reports with generation, review/publish/archive actions, public report surfacing, and governed download state
- organization and municipality context selection
- MapLibre public risk-map surface with municipality, year, score-band filters, popups, keyboard shortcuts, and shareable URL state
- MapLibre analyst risk explorer with segment detail rows plus junction and crossing layers, layer toggles, popups, and shareable URL state
- executive dashboard for priority, budget, delivery, and monthly briefing surfaces
- scenario planner for generated interventions, organization-scoped draft authoring, before/after run history, managed portfolio status changes, and cost-benefit ranking
- capability-gated VRU and signal-phase operations surface for selected-municipality operational evidence; Bari VRU is v1-supported, Bari signal-phase is preview/read-only, and unsupported cities show an explicit no-data/v1.5 gate
- Upload Center for data operators with CSV, GeoJSON, JSON, and ZIP detection, field mapping, validation artifacts, row-error review, queue/reject actions, and executable ingestion worker controls
- automation dashboard for scheduler state, recurring policy controls, stale-source checks, recent runs, and notification delivery dry-runs
- system-health dashboard for release acceptance, staging proof, smoke checks, and operational checks
- shared production UI states for loading, empty, error, and access-denied views
- route experience contracts and smoke coverage for every v1 route
- browser E2E release gates for role workflows, accessibility baseline, responsive
  desktop/mobile layout, and visual-smoke screenshots
- baseline map, metric, form, filter, state, and table styling

## Unpublished GitHub Pages demo

`npm run build:demo` creates a separate static demo in `out/` with `/xROAD` routing,
local synthetic GeoJSON and simulated browser login. `npm run preview:demo` serves
it at <http://127.0.0.1:4173/xROAD/>; `npm run test:demo` verifies desktop and mobile
flows without a backend. No command publishes it. See
[the GitHub Pages demo guide](../../docs/github-pages-demo.md) for data boundaries,
limitations, custom base paths and the opt-in manual deployment workflow.
