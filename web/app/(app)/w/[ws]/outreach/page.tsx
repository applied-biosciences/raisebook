import type { Metadata } from "next";
import { Suspense } from "react";

import { Outreach } from "@/components/app/wasila/Outreach";

export const metadata: Metadata = { title: "Outreach" };

/** Investor email outreach (Wasila v1.0.0.0): drafts, sent mail, campaigns, follow-ups. */
export default function OutreachPage() {
  return (
    <Suspense>
      <Outreach />
    </Suspense>
  );
}
