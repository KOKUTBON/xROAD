import { lstatSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const DEMO_ASSETS = [
  "api.json", "public-tiles.geojson", "segments.geojson", "junctions.geojson",
  "crossings.geojson", "climate_risk_surface.geojson", "forecast_risk_surface.geojson",
  "weather_alerts.json",
];
const forbiddenFields = new Set([
  "email", "phone", "phone_number", "address", "date_of_birth", "license_plate",
  "registration_plate", "access_token", "refresh_token", "password", "client_secret",
  "actor_subject", "owner_subject", "manifest_path", "input_storage_uri",
  "manifest_storage_uri", "error_storage_uri", "upload_url", "download_url",
]);
const credentialPatterns = [
  /-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----/,
  /\bAKIA[0-9A-Z]{16}\b/, /\bgh[opsu]_[A-Za-z0-9_]{20,}\b/,
];

export function checkDemoData(directory) {
  const entries = readdirSync(directory);
  const unexpected = entries.filter((name) => !DEMO_ASSETS.includes(name));
  if (unexpected.length) throw new Error(`Unapproved public demo files: ${unexpected.join(", ")}`);
  for (const name of DEMO_ASSETS) {
    const filename = path.join(directory, name);
    if (!lstatSync(filename).isFile()) throw new Error(`Demo asset must be a regular file: ${name}`);
    const text = readFileSync(filename, "utf8");
    if (credentialPatterns.some((pattern) => pattern.test(text))) throw new Error(`Credential pattern in ${name}`);
    const payload = JSON.parse(text);
    function inspect(value, trail = name) {
      if (typeof value === "string") {
        if (/@|s3:\/\/|file:\/\/|\/Users\/|\/home\/|\b(?:bari|puglia|e2e)\b/i.test(value)) {
          throw new Error(`Non-public or outdated value at ${trail}`);
        }
      } else if (Array.isArray(value)) {
        value.forEach((item, index) => inspect(item, `${trail}[${index}]`));
      } else if (value && typeof value === "object") {
        for (const [key, item] of Object.entries(value)) {
          if (forbiddenFields.has(key)) throw new Error(`Private metadata field at ${trail}.${key}`);
          if (key === "geometry") {
            function checkCoordinates(coordinates) {
              if (!Array.isArray(coordinates)) return;
              if (typeof coordinates[0] === "number") {
                const [longitude, latitude] = coordinates;
                if (!(longitude >= 19.7 && longitude <= 19.95 && latitude >= 41.25 && latitude <= 41.4)) {
                  throw new Error(`Geometry outside Tirana demo bounds at ${trail}`);
                }
              } else coordinates.forEach(checkCoordinates);
            }
            checkCoordinates(item.coordinates);
          }
          inspect(item, `${trail}.${key}`);
        }
      }
    }
    inspect(payload);
    if (name === "api.json") {
      const cities = payload["/v1/public/cities"].cities;
      if (cities.length !== 1 || cities[0].city_key !== "tirana") throw new Error("The public sample must contain only Tirana.");
      if (payload["/v1/public/institution-config"].country_code !== "AL") throw new Error("The demo country must be Albania.");
    }
  }
  console.log(`Public demo data check passed (${DEMO_ASSETS.length} approved synthetic assets; Tirana only).`);
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  checkDemoData(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../public/demo"));
}
