import type { Metadata } from "next";

import { LanguageSettings } from "@/components/app/wasila/WasilaSettings";

export const metadata: Metadata = { title: "Language" };

export default function LanguageSettingsPage() {
  return <LanguageSettings />;
}
