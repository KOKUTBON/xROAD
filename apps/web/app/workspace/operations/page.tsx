import { AreaGate } from "@/components/platform-shell";
import { VruSignalsOperations } from "@/components/vru-signals";

export default function OperationsPage() {
  return (
    <AreaGate area="traffic_engineering">
      <VruSignalsOperations />
    </AreaGate>
  );
}
