import { UploadCenter } from "@/components/upload-center";
import { AreaGate } from "@/components/platform-shell";

export default function Page() {
  return <AreaGate area="data_operations"><UploadCenter /></AreaGate>;
}
