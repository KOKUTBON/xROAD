import { ReportsHub } from "@/components/reports-hub";
import { AreaGate } from "@/components/platform-shell";

export default function Page() {
  return <AreaGate area="reports"><ReportsHub /></AreaGate>;
}
