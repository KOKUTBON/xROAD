import { ClimateMap } from "@/components/climate-map";
import { AreaGate } from "@/components/platform-shell";

export default function ClimatePage() {
  return (
    <AreaGate area="analyst">
      <ClimateMap />
    </AreaGate>
  );
}
