import { AreaGate } from "@/components/platform-shell";
import { DigitalTwinWorkbench } from "@/components/digital-twin-workbench";

export default function DigitalTwinPage() {
  return (
    <AreaGate area="analyst">
      <DigitalTwinWorkbench />
    </AreaGate>
  );
}
