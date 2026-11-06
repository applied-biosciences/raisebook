import type { Metadata } from "next";

import { FundingRoom } from "@/components/app/wasila/FundingRoom";

export const metadata: Metadata = { title: "Funding Room" };

/** The Funding Room (Wasila v1.0.0.0): diligence documents, checklist, share links. */
export default function FundingRoomPage() {
  return <FundingRoom />;
}
