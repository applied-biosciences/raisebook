import type { Metadata } from "next";

import { PublicRoom } from "./PublicRoom";

export const metadata: Metadata = { title: "Funding Room", robots: { index: false, follow: false } };

/** Public Funding Room share link (Wasila v1.0.0.0). The token in the URL is the credential. */
export default async function RoomPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PublicRoom token={token} />;
}
