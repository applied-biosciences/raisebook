import type { Metadata } from "next";

import { DeckEditor } from "@/components/app/wasila/DeckEditor";

export const metadata: Metadata = { title: "Deck editor" };

/** The deck editor (Wasila v1.0.0.0): edit a Funding Room PowerPoint and save a new version. */
export default async function DeckPage({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  return <DeckEditor docId={doc} />;
}
