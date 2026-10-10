// Type surface for the plain-ESM baseline scenario model (`baseline-scenarios.mjs`),
// so the TypeScript Playwright spec can import it without `any`.

export interface BaselineViewport {
  viewport: "desktop" | "mobile";
  width: number;
  height: number;
}

export interface BaselinePersona {
  id: string;
  label: string;
  roles: string[];
  topTasks: string[];
}

export interface BaselineRoute {
  route: string;
  area: string;
  accessArea: string;
  audience: string;
  primaryTask: string;
  layoutPattern: string;
  requiredStates: string[];
}

export type BaselineTheme = "light" | "dark";

export interface BaselineScenario {
  id: string;
  route: string;
  url: string;
  viewport: BaselineViewport;
  theme: BaselineTheme;
  persona: Pick<BaselinePersona, "id" | "label" | "roles" | "topTasks">;
  contract: {
    area: string;
    audience: string;
    primaryTask: string;
    layoutPattern: string;
    requiredStates: string[];
  };
  expectedAccess: "allowed" | "no-access";
  screenshotPath: string;
}

export interface BaselineManifest {
  generatedAt: string;
  baseUrl: string;
  scenarioCount: number;
  routeCount: number;
  viewportCount: number;
  personaCount: number;
  themeCount: number;
  notes: string[];
  smokeResults: unknown[];
  scenarios: BaselineScenario[];
}

export const DEFAULT_BASE_URL: string;
export const DEFAULT_OUTPUT_DIR: string;
export const viewports: BaselineViewport[];
export const themes: BaselineTheme[];
export const personas: BaselinePersona[];
export const routes: BaselineRoute[];
export const accessByArea: Record<string, string[]>;

export function canAccessRoute(persona: BaselinePersona, route: BaselineRoute): boolean;
export function captureSlug(
  route: BaselineRoute,
  persona: BaselinePersona,
  viewport: BaselineViewport,
  theme?: BaselineTheme,
): string;
export function scenarioFor(
  route: BaselineRoute,
  persona: BaselinePersona,
  viewport: BaselineViewport,
  theme?: BaselineTheme,
  baseUrl?: string,
  outputDir?: string,
): BaselineScenario;
export function allScenarios(baseUrl?: string, outputDir?: string): BaselineScenario[];
export function buildManifest(
  results: unknown[],
  baseUrl?: string,
  outputDir?: string,
): BaselineManifest;
