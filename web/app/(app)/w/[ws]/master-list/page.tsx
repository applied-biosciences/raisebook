import type { Metadata } from "next";

import { MasterList } from "@/components/app/wasila/MasterList";

export const metadata: Metadata = { title: "Master list" };

/** The master investor list (Wasila v1.0.0.0): filters, Ask Wasila, saved lists, AI columns. */
export default function MasterListPage() {
  return <MasterList />;
}
