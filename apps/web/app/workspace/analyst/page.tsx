import { AreaGate } from "@/components/platform-shell";
import { AnalystRiskExplorer } from "@/components/risk-explorer";

export default function AnalystPage() {
  return (
    <AreaGate area="analyst">
      <AnalystRiskExplorer />
    </AreaGate>
  );
}
