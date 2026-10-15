import { Suspense, type ReactNode } from "react";

import { WorkspaceFrame } from "@/components/platform-shell";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <Suspense fallback={null}><WorkspaceFrame>{children}</WorkspaceFrame></Suspense>;
}
