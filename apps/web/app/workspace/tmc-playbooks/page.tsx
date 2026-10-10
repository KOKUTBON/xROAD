import { AreaGate } from "@/components/platform-shell";
import { TmcPlaybookWorkbench } from "@/components/tmc-playbook-workbench";

export default function TmcPlaybooksPage() {
  return (
    <AreaGate area="analyst">
      <div className="wb-scope">
        <TmcPlaybookWorkbench />
      </div>
    </AreaGate>
  );
}
