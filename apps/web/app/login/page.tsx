import { Suspense } from "react";

import { LoginConsole } from "@/components/platform-shell";
import { StatusPill } from "@/components/ui";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="page-shell centered-shell">
          <StatusPill label="Preparing session console" tone="warning" />
        </main>
      }
    >
      <LoginConsole />
    </Suspense>
  );
}
