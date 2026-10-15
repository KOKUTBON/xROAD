import { AreaGate } from "@/components/platform-shell";
import { ForensicReconstructionWorkbench } from "@/components/forensic-reconstruction-workbench";

export default function ForensicsPage() {
  return (
    <AreaGate area="analyst">
      <div className="wb-scope">
        <ForensicReconstructionWorkbench />
      </div>
    </AreaGate>
  );
}
