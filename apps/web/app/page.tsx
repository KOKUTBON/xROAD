import { Suspense } from "react";

import { PublicHome } from "@/components/home-landing";

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <PublicHome />
    </Suspense>
  );
}
