import { AreaGate } from "@/components/platform-shell";
import { ProposedChangesWorkspace } from "@/components/proposed-changes-workspace";

export default function ProposedChangesPage() {
  return (
    <AreaGate area="analyst">
      <ProposedChangesWorkspace />
    </AreaGate>
  );
}
