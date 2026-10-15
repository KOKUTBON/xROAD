import { AreaGate } from "@/components/platform-shell";
import { IncidentCoordinationWorkbench } from "@/components/incident-coordination-workbench";

export default function IncidentCoordinationPage() {
  return (
    <AreaGate area="analyst">
      <div className="wb-scope">
        <IncidentCoordinationWorkbench />
      </div>
    </AreaGate>
  );
}
