import type { ReactNode } from "react";

import { RouteStage } from "@/components/motion";

/**
 * Per-route motion stage (UX 3.0). A `template` (unlike `layout`) remounts on
 * every navigation, so the enter transition, the card cascade, and the route's
 * signature motif all replay as the user moves between workspace routes. Every
 * animation inside is collapsed to instant under prefers-reduced-motion.
 */
export default function WorkspaceTemplate({ children }: { children: ReactNode }) {
  return <RouteStage>{children}</RouteStage>;
}
