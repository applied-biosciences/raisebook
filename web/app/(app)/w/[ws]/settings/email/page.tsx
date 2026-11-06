import type { Metadata } from "next";

import { EmailSettings } from "@/components/app/wasila/WasilaSettings";

export const metadata: Metadata = { title: "Email" };

export default function EmailSettingsPage() {
  return <EmailSettings />;
}
