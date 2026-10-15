import { AreaGate } from "@/components/platform-shell";
import { ConnectedFleetsWorkbench } from "@/components/connected-fleets-workbench";

export default function ConnectedFleetsPage() {
  return (
    <AreaGate area="analyst">
      <div className="wb-scope">
        <ConnectedFleetsWorkbench />
      </div>
    </AreaGate>
  );
}
