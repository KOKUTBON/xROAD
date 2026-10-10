import { readFileSync } from "node:fs";
import { spawn } from "node:child_process";

if (process.env.ROAD_RISK_INSTITUTION_DEPLOYMENT === "true") {
  try {
    for (const name of ["ROAD_RISK_PUBLIC_ORIGIN", "ROAD_RISK_WEB_OIDC_ISSUER", "ROAD_RISK_WEB_OIDC_REDIRECT_URI"]) {
      const url = new URL(process.env[name]);
      if (url.protocol !== "https:" || url.username || url.password || url.hash) throw new Error();
    }
    for (const name of ["ROAD_RISK_WEB_OIDC_AUTHORIZATION_ENDPOINT", "ROAD_RISK_WEB_OIDC_TOKEN_ENDPOINT", "ROAD_RISK_WEB_OIDC_LOGOUT_ENDPOINT"]) {
      if (process.env[name]) {
        const url = new URL(process.env[name]);
        if (url.protocol !== "https:" || url.username || url.password || url.hash) throw new Error();
      }
    }
    const origin = new URL(process.env.ROAD_RISK_PUBLIC_ORIGIN);
    const callback = new URL(process.env.ROAD_RISK_WEB_OIDC_REDIRECT_URI);
    if (origin.pathname !== "/" || origin.search || callback.origin !== origin.origin || callback.pathname !== "/api/auth/callback" || callback.search) throw new Error();
    if (!process.env.ROAD_RISK_WEB_OIDC_CLIENT_ID?.trim()) throw new Error();
    const secret = readFileSync(process.env.ROAD_RISK_WEB_OIDC_CLIENT_SECRET_FILE, "utf8").replace(/[\r\n]+$/, "");
    if (secret.length < 24 || /changeme|example|replace_me/i.test(secret)) throw new Error();
    process.env.ROAD_RISK_WEB_OIDC_CLIENT_SECRET = secret;
  } catch {
    console.error("Institutional web startup rejected: configure HTTPS origin, OIDC issuer/client/callback, and a non-placeholder client secret (minimum 24 characters).");
    process.exit(1);
  }
}
const [command, ...args] = process.argv.slice(2);
if (command === "--check") process.exit(0);
const child = spawn(command, args, { stdio: "inherit", env: process.env });
for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => child.kill(signal));
child.on("error", () => process.exit(1));
child.on("exit", (code) => process.exit(code ?? 1));
