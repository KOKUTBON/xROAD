export type SmokeViewport = "desktop" | "mobile";

export interface BrowserSmokeRoute {
  route: string;
  workflow: string;
  requiredViewports: SmokeViewport[];
}

export const BROWSER_SMOKE_ROUTES: BrowserSmokeRoute[] = [
  {
    route: "/",
    workflow: "public-risk-inspection",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/login",
    workflow: "role-aware-entry",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace",
    workflow: "municipal-control-room",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/executive",
    workflow: "executive-safety-review",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/analyst",
    workflow: "analyst-hotspot-inspection",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/scenarios",
    workflow: "scenario-planning",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/proposed-changes",
    workflow: "recommendation-review",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/siting-advisor",
    workflow: "siting-analysis",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/research",
    workflow: "research-benchmarks-evaluation",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/digital-twin",
    workflow: "digital-twin-micro-simulation",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/forensics",
    workflow: "forensic-incident-reconstruction",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/tmc-playbooks",
    workflow: "tmc-playbook-automation-engine",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/connected-fleets",
    workflow: "connected-fleets-cv2x-ivi",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/incident-coordination",
    workflow: "multi-incident-coordination-spillover",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/operations",
    workflow: "traffic-operations-review",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/reports",
    workflow: "report-generation",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/admin",
    workflow: "ingestion-and-governance-review",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/uploads",
    workflow: "upload-validation-flow",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/automation",
    workflow: "automation-refresh-review",
    requiredViewports: ["desktop", "mobile"],
  },
  {
    route: "/workspace/system-health",
    workflow: "system-health-review",
    requiredViewports: ["desktop", "mobile"],
  },
];
