# GitHub Pages demo (prepared, unpublished)

The public demo is a static export of the xROAD frontend. It requires no Python
API, database, object storage, identity provider, or Node server after building.
The default repository path is `/xROAD`, matching this repository's GitHub remote.

## Build and preview locally

```sh
cd apps/web
npm ci
npm run build:demo
npm run preview:demo
```

Open <http://127.0.0.1:4173/xROAD/>. The preview uses a plain static HTTP server,
including directory indexes and real 404 responses; it does not emulate backend
routes. Build output is `apps/web/out/`, including `.nojekyll`. You can copy this
folder directly to any static host mounted at the configured path.

```sh
# Custom domain or account-level Pages site
PAGES_BASE_PATH='' npm run build:demo
# Another repository
PAGES_BASE_PATH=/another-repository npm run build:demo
```

The base path is baked into the build. Rebuild when it changes. Next navigation,
fonts, logos, manifest, map workers, JSON and GeoJSON use the same path.

## Demo behavior and data

- The home page and workspaces share the existing app design and navigation.
- The login page offers Public visitor, Analyst for Tirana, Demo admin and
  Traffic engineer profiles. No credentials are collected. Profile and selected
  context persist in localStorage; sign out clears the session.
- Fake authentication is explicitly enabled in the isolated demo build, including
  production mode. Ordinary production builds still disable development demo
  authentication and retain OIDC/backend authorization. Browser role checks are
  presentation controls: everything in a static export is publicly accessible.
- Risk tiles, segments, junctions, crossings and climate points are synthetic
  sample GeoJSON under `apps/web/public/demo/`. API-shaped sample envelopes are
  stored in `api.json`; no private crash data is included. The sample was curated
  from the project's deterministic browser fixtures, with contact details, audit identities, storage paths and external download links
  removed. These illustrative scores and geometries are not validated city data.
- Tirana 2024 is the bundled risk-map sample. Risk-band filters and feature details
  run locally; recommendations can be filtered by review state and minimum BCR.
- Reports, scenarios, traffic operations, administration, uploads and automation
  show sample snapshots. Backend mutation requests return an explicit unavailable
  response without making a network request or claiming successful execution.
  Report downloads without a bundled artifact are marked unavailable.
- Research workbenches retain their existing illustrative presets. New analysis,
  ingestion, report generation, scheduling, dispatch and controller operations
  require the institutional backend. The demo opens no live telematics WebSocket.
- Street/satellite basemaps load from OpenStreetMap/Esri and need internet access.
  Risk overlays, app assets and sample data are served locally. This is not a
  fully offline basemap package.

The builder creates `.pages-build/` from an explicit allowlist. It removes API
routes, omits the auth proxy, never copies `.env` files, and copies only `brand/`
and `demo/` from `public/`. It does not include ignored local climate exports,
`data/`, institution runtime stores, credentials or private datasets. Generated
build/export directories are ignored by Git. `npm run build` remains the regular
server application build.

## Verification

```sh
npm run typecheck
npm test
npm run build:demo
npx playwright install chromium
npm run test:demo
```

The export browser gate runs against the plain static server at `/xROAD` on desktop
and mobile. It checks local data, map filters, direct protected-page navigation,
fake login, role access, persistence after reload, workspace pages, branding,
blocked backend actions, absence of backend requests and uncaught browser errors.

## Publish later, when you choose

Nothing is published by the build or preview commands. The workflow
`.github/workflows/pages-demo.yml` runs **only** through **Actions → Prepare GitHub
Pages demo → Run workflow**. It has no push trigger.

1. Commit and push the prepared changes when ready.
2. Run the workflow with **Publish this demo to GitHub Pages unchecked** to build,
   test and download the `static-demo-review` artifact without publishing.
3. When ready to publish, set **Settings → Pages → Source → GitHub Actions**.
4. Run the same workflow with **Publish this demo to GitHub Pages checked** and
   base path `/xROAD`. Only that manual run requests Pages deployment permissions.

For a different base path the workflow still builds the artifact, but the current
browser gate is specifically configured for `/xROAD`; adjust its config and routes
before relying on it to validate another deployment path.

References: [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports),
[Next.js basePath](https://nextjs.org/docs/app/api-reference/config/next-config-js/basePath),
[GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Public data checks

`npm run check:demo-data` runs automatically before every static build and in the
manual Pages workflow. It permits only the eight named demo JSON/GeoJSON assets,
rejects symlinks and extra files, and checks for credential patterns, contact
fields, account/audit identities, machine paths and storage/download URLs. It
also requires Tirana/Albania configuration and checks all sample geometry against
Tirana bounds. The builder copies individual approved assets and omits the
internal design-system route.

The current publication review checked tracked and non-ignored new files plus
text blobs in all three reachable Git commits. The existing security release
checks and eight repository hygiene tests passed; no matched credentials or raw
dataset exports were found. The `data/` folder contains only its README and empty
placeholders. Public demo contact fields, audit entries and storage paths were
removed; the retained data is synthetic. Engineering source, public reference
tables and example configuration templates remain part of the open-source
project. The scan covers known credential patterns and reachable local history.

The Pages workflow is manual-only; merging source changes does not publish a site.

Street tiles use normal browser caching and visible OpenStreetMap attribution.
No tile downloading or offline prefetch is included; see the
[OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Private source repository and account site

Keep this repository private while preparing the site. A public Pages website
can be published from private source on an eligible paid plan. For a repository
owned by the personal account `reiidoda`, GitHub Pro enables private-repository
Pages; GitHub Team is the plan for organization-owned repositories.

The exact account-site address `https://kokutbon.github.io/` requires a repository
named `kokutbon.github.io` owned by `KOKUTBON` and a build with an empty base path.
The current repository name `xROAD` uses the project-site path `/xROAD`. Renaming,
transferring, purchasing a plan and publishing are separate follow-up actions.
A private source repository does not make the published website private.

See [GitHub plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)
and [Pages site types](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).
