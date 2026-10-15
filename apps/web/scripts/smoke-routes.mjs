import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { buildManifest, routes, viewports } from "./baseline-scenarios.mjs";

const baseUrl = process.env.WEB_SMOKE_BASE_URL || "http://localhost:3000";
const smokeAccessToken = process.env.WEB_SMOKE_ACCESS_TOKEN;
const baselineMode = process.env.WEB_SMOKE_BASELINE === "true" || process.env.WEB_SMOKE_BASELINE === "1";
const baselineOutputDir = process.env.WEB_SMOKE_BASELINE_DIR || path.join("docs", "ui-baseline");
const demoAuthEnabled =
  process.env.NEXT_PUBLIC_AUTH_MODE === "demo" ||
  process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH === "true" ||
  process.env.WEB_SMOKE_DEMO_AUTH === "true";

function redirectsToLogin(response, item) {
  const location = response.headers.get("location") || "";
  if (!location) {
    return false;
  }
  return location.startsWith("/login") || new URL(location, new URL(item.route, baseUrl)).pathname === "/login";
}

async function smokeRoute(route, viewport) {
  const url = new URL(route.route, baseUrl);
  const isProtectedRoute = route.route.startsWith("/workspace");
  const response = await fetch(url, {
    redirect: "manual",
    headers: {
      ...(smokeAccessToken ? { cookie: `road_risk_access_token=${smokeAccessToken}` } : {}),
      "user-agent": `road-risk-smoke/${viewport.viewport}`,
      "viewport-width": String(viewport.width),
    },
  });

  if (isProtectedRoute && !smokeAccessToken && !demoAuthEnabled) {
    const ok = [307, 308].includes(response.status) && redirectsToLogin(response, route);
    return {
      ok,
      status: response.status,
      message: ok
        ? `${viewport.viewport} ${route.route} auth redirect ok`
        : `${viewport.viewport} ${route.route} expected auth redirect, got ${response.status}`,
    };
  }

  const body = await response.text();
  const ok = response.ok && body.includes("Road Risk Platform");
  return {
    ok,
    status: response.status,
    message: ok ? `${viewport.viewport} ${route.route} ok` : `${viewport.viewport} ${route.route} failed with ${response.status}`,
  };
}

async function writeBaselineManifest(results) {
  const manifest = buildManifest(results, baseUrl, baselineOutputDir);
  await mkdir(baselineOutputDir, { recursive: true });
  await writeFile(
    path.join(baselineOutputDir, "capture-manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
}

let failures = 0;
const results = [];

for (const route of routes) {
  for (const viewport of viewports) {
    const result = await smokeRoute(route, viewport);
    results.push({ route: route.route, viewport: viewport.viewport, ...result });
    if (!result.ok) {
      failures += 1;
      console.error(result.message);
    } else {
      console.log(result.message);
    }
  }
}

if (baselineMode) {
  await writeBaselineManifest(results);
  console.log(`baseline manifest written to ${path.join(baselineOutputDir, "capture-manifest.json")}`);
}

if (failures > 0) {
  process.exitCode = 1;
}
