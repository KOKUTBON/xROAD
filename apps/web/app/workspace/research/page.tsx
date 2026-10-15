import { AreaGate } from "@/components/platform-shell";
import { ResearchWorkbench } from "@/components/research-workbench";

export default function ResearchPage() {
  return (
    <AreaGate area="analyst">
      <ResearchWorkbench />
    </AreaGate>
  );
}
