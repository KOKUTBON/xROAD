import { AreaGate } from "@/components/platform-shell";
import { SitingAdvisorWorkspace } from "@/components/siting-advisor-workspace";

export default function SitingAdvisorPage() {
  return (
    <AreaGate area="analyst">
      <SitingAdvisorWorkspace />
    </AreaGate>
  );
}
