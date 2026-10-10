import { InstitutionSetup } from "@/components/institution-setup";
import { AdminControlCenter } from "@/components/admin-control-center";
import { AreaGate } from "@/components/platform-shell";

export default function AdminPage() {
  return (
    <AreaGate area="admin">
      <InstitutionSetup />
      <AdminControlCenter />
    </AreaGate>
  );
}
