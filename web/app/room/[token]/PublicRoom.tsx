"use client";

import { useEffect, useState } from "react";

import { Wordmark } from "@/components/ui";
import { API_URL, api, errorMessage } from "@/lib/api/client";
import { fileSize, openRoomLink, type PublicRoom as Room } from "@/lib/api/wasila";

/** A Funding Room share link as the investor sees it: approved documents, nothing else. */
export function PublicRoom({ token }: { token: string }) {
  const [room, setRoom] = useState<Room | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    openRoomLink(api, token).then(setRoom).catch((e) => setError(errorMessage(e)));
  }, [token]);

  return (
    <main id="main" className="mx-auto flex min-h-dvh max-w-[760px] flex-col gap-20 px-16 py-32">
      <Wordmark size={22} />
      {error ? (
        <div className="rounded-md border border-line bg-surface p-20">
          <h1 className="t-display-s m-0">This link is not available</h1>
          <p className="m-0 mt-8 text-muted">{error}</p>
        </div>
      ) : !room ? (
        <p className="text-muted">Opening…</p>
      ) : (
        <>
          <header>
            <h1 className="t-display-s m-0">{room.company}: Funding Room</h1>
            <p className="m-0 mt-6 text-muted">
              Shared with {room.label}. Available until {new Date(room.expires_at).toLocaleDateString()}. Please keep these documents confidential.
            </p>
          </header>
          <ul className="m-0 flex list-none flex-col gap-10 p-0">
            {room.documents.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-10 rounded-md border border-line bg-surface p-14">
                <span className="min-w-0">
                  <span className="block font-medium">{d.title}</span>
                  <span className="block text-13 text-muted">
                    {d.category_label} · {d.filename} · {fileSize(d.size_bytes)}
                  </span>
                  {d.description ? <span className="mt-4 block text-13 text-muted">{d.description}</span> : null}
                </span>
                <a
                  href={`${API_URL}/v1/room-links/${encodeURIComponent(token)}/documents/${d.id}`}
                  className="inline-flex h-36 items-center rounded-sm border border-accent bg-accent px-14 font-medium text-accent-ink touch:min-h-44"
                >
                  Download
                </a>
              </li>
            ))}
          </ul>
          <p className="t-micro text-muted">Views are counted for the company; no tracking, no cookies.</p>
        </>
      )}
    </main>
  );
}
