import http from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../out");
const { basePath } = JSON.parse(await readFile(path.join(root, "demo-build.json"), "utf8"));
const port = Number(process.env.DEMO_PORT || 4173);
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".geojson": "application/geo+json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".txt": "text/plain" };
http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (basePath && pathname === "/") { response.writeHead(302, { Location: `${basePath}/` }); response.end(); return; }
    if (basePath && pathname !== basePath && !pathname.startsWith(`${basePath}/`)) throw Error("Outside base path");
    let target = path.resolve(root, `.${pathname.slice(basePath.length) || "/"}`);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) throw Error("Outside export");
    if ((await stat(target)).isDirectory()) {
      if (!pathname.endsWith("/")) { response.writeHead(301, { Location: `${pathname}/` }); response.end(); return; }
      target = path.join(target, "index.html");
    }
    const body = await readFile(target);
    response.writeHead(200, { "Content-Type": types[path.extname(target)] || "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404, { "Content-Type": "text/html" });
    response.end(await readFile(path.join(root, "404.html")).catch(() => "Not found"));
  }
}).listen(port, "127.0.0.1", () => console.log(`Demo preview: http://127.0.0.1:${port}${basePath}/`));
