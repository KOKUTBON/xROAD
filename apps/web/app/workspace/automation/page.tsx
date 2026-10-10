import { AutomationControls } from "@/components/automation-controls";
import { AreaGate } from "@/components/platform-shell";

export default function AutomationPage() {
  return (
    <AreaGate area="admin">
      <AutomationControls />
    </AreaGate>
  );
}
