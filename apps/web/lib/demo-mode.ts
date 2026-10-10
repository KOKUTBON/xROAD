/** Explicit build-time switch: fake auth is enabled only for the public export. */
export const STATIC_DEMO = process.env.NEXT_PUBLIC_STATIC_DEMO === "true";
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

/** Next Link handles basePath; plain asset URLs need this helper. */
export function publicAsset(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path;
  if (BASE_PATH && (path === BASE_PATH || path.startsWith(`${BASE_PATH}/`))) return path;
  return `${BASE_PATH}${path}`;
}
