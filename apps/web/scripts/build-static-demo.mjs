import { checkDemoData, DEMO_ASSETS } from "./check-demo-data.mjs";
import { cpSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const staging = path.join(webRoot, ".pages-build");
const output = path.join(webRoot, "out");
const basePath = (process.env.PAGES_BASE_PATH ?? "/xROAD").replace(/\/$/, "");
if (basePath && !/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(basePath)) {
  throw new Error("PAGES_BASE_PATH must be empty or a path such as /xROAD.");
}
checkDemoData(path.join(webRoot, "public/demo"));
// Assemble an isolated application: no API routes, proxy, environment files,
// local climate exports, runtime stores or private datasets enter the demo.
rmSync(staging, { recursive: true, force: true });
mkdirSync(staging, { recursive: true });
for (const name of ["app", "components", "lib", "tsconfig.json", "next-env.d.ts", "package.json"]) {
  cpSync(path.join(webRoot, name), path.join(staging, name), { recursive: true });
}
rmSync(path.join(staging, "app/api"), { recursive: true, force: true });
mkdirSync(path.join(staging, "public"));
for (const directory of ["brand", "demo"]) mkdirSync(path.join(staging, "public", directory));
for (const name of ["road-accidents-risk-modeling-icon.svg", "road-accidents-risk-modeling-icon.png", "road-accidents-risk-modeling-icon-512.png"]) {
  cpSync(path.join(webRoot, "public/brand", name), path.join(staging, "public/brand", name));
}
for (const name of DEMO_ASSETS) {
  cpSync(path.join(webRoot, "public/demo", name), path.join(staging, "public/demo", name));
}
// Internal design-system fixtures are not part of the public demonstration.
rmSync(path.join(staging, "app/workspace/%5Fdesign"), { recursive: true, force: true });
symlinkSync(path.join(webRoot, "node_modules"), path.join(staging, "node_modules"), "dir");
const worker = spawnSync(process.execPath, [path.join(webRoot, "scripts/copy-maplibre-worker.mjs")], { cwd: staging, stdio: "inherit" });
if (worker.status !== 0) process.exit(worker.status || 1);
writeFileSync(path.join(staging, "next.config.mjs"), `export default {
  output: "export", basePath: ${JSON.stringify(basePath)}, trailingSlash: true,
  reactStrictMode: true, agentRules: false, images: { unoptimized: true },
  env: { NEXT_PUBLIC_STATIC_DEMO: "true", NEXT_PUBLIC_BASE_PATH: ${JSON.stringify(basePath)} }
};\n`);
const result = spawnSync(process.execPath, [path.join(webRoot, "node_modules/next/dist/bin/next"), "build", "--webpack"], {
  cwd: staging, stdio: "inherit",
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1", NEXT_PUBLIC_STATIC_DEMO: "true", NEXT_PUBLIC_BASE_PATH: basePath, NEXT_PUBLIC_API_BASE_URL: "", NODE_ENV: "production" },
});
if (result.status !== 0) process.exit(result.status || 1);
rmSync(output, { recursive: true, force: true });
cpSync(path.join(staging, "out"), output, { recursive: true });
writeFileSync(path.join(output, ".nojekyll"), "");
writeFileSync(path.join(output, "demo-build.json"), JSON.stringify({ basePath, mode: "static-demo", data: "synthetic" }, null, 2));
console.log(`Static demo ready at ${output} (base path: ${basePath || "/"}). Nothing was published.`);
