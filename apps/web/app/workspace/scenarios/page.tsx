import { AreaGate } from "@/components/platform-shell";
import { ScenarioPlanner } from "@/components/scenario-planner";

export default function ScenariosPage() {
  return (
    <AreaGate area="analyst">
      <ScenarioPlanner />
    </AreaGate>
  );
}
