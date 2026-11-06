import type { Metadata } from "next";

import { ClaudeSettings } from "@/components/app/wasila/WasilaSettings";

export const metadata: Metadata = { title: "Claude" };

export default function ClaudeSettingsPage() {
  return <ClaudeSettings />;
}
