import type { Metadata } from "next";

import { FundingCosts } from "@/components/app/wasila/FundingCosts";

export const metadata: Metadata = { title: "Funding costs" };

/** Funding costs (Wasila v1.0.0.0): use of funds, tranches, the 48-month plan and KPIs. */
export default function FundingCostsPage() {
  return <FundingCosts />;
}
