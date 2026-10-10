import type { InstitutionConfig } from "./institution";

export const MODULE_LABELS = {
  public_portal: "Public transparency", risk_analysis: "Risk analysis", reporting: "Reports and dossiers",
  interventions: "Intervention planning", data_ingestion: "Data ingestion", traffic_operations: "Traffic operations",
  automation: "Scheduled workflows", administration: "Administration", siting_advisor: "Facility siting",
  climate_resilience: "Climate resilience", connected_fleets: "Connected fleets", digital_twin: "Simulation and digital twin",
  forensics: "Crash reconstruction", incident_coordination: "Incident coordination", research: "Research workflows",
} as const;
export type InstitutionModule = keyof typeof MODULE_LABELS;

export interface InstitutionDeployment {
  schema_version: number;
  profile: string;
  enabled_modules: InstitutionModule[];
  revision: string;
}

const ROUTE_MODULES: Record<string, InstitutionModule> = {
  "/": "public_portal", "/workspace/executive": "risk_analysis", "/workspace/analyst": "risk_analysis",
  "/workspace/reports": "reporting", "/workspace/scenarios": "interventions", "/workspace/proposed-changes": "interventions",
  "/workspace/uploads": "data_ingestion", "/workspace/operations": "traffic_operations", "/workspace/automation": "automation",
  "/workspace/admin": "administration", "/workspace/siting-advisor": "siting_advisor", "/workspace/climate": "climate_resilience",
  "/workspace/connected-fleets": "connected_fleets", "/workspace/digital-twin": "digital_twin", "/workspace/forensics": "forensics",
  "/workspace/incident-coordination": "incident_coordination", "/workspace/tmc-playbooks": "incident_coordination",
  "/workspace/research": "research",
};

export function moduleForRoute(path: string): InstitutionModule | undefined {
  return Object.entries(ROUTE_MODULES).find(([route]) => path === route || (route !== "/" && path.startsWith(`${route}/`)))?.[1];
}

export function moduleEnabled(config: InstitutionConfig, module: InstitutionModule): boolean {
  return !config.deployment || config.deployment.enabled_modules.includes(module);
}

export function institutionRouteEnabled(config: InstitutionConfig, path: string): boolean {
  const module = moduleForRoute(path);
  return !module || moduleEnabled(config, module);
}
