"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";

import { Button, Combobox, Dialog, Field, LinkIcon, SectionLabel, useToast, type ComboboxOption } from "@/components/ui";
import { errorMessage, type ApiClient } from "@/lib/api/client";
import { linkInvestors, listInvestors, unlinkInvestor } from "@/lib/api/investors";
import type { Investor, LinkedInvestorBrief } from "@/lib/api/types";
import { briefOf, patchAfterLink, patchAfterUnlink, type LinkPatch } from "@/lib/links";

/**
 * Linked cards (SPEC §3.10) in the investor's file: the other people on this investor's team
 * (two partners at one fund working the deal together), each opening their own file and with
 * an Unlink, and "Link a card" to pick more from the workspace's contacts.
 *
 * `onChange` gets every affected card's new team (this one included), so the board, the table
 * and the page update in place.
 */
export function LinkedCards({
  client,
  investor,
  wsSlug,
  canWrite,
  onOpen,
  onChange,
  className,
}: {
  client: ApiClient;
  investor: Investor;
  wsSlug: string;
  canWrite: boolean;
  /** Open a member's file in place (the sheet); else their page is linked. */
  onOpen?: (investorId: string) => void;
  onChange: (patch: LinkPatch) => void;
  className?: string;
}) {
  const toast = useToast();
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const linked = investor.linked ?? [];
  const base = `/w/${encodeURIComponent(wsSlug)}`;

  const unlink = async (m: LinkedInvestorBrief) => {
    setBusy(m.id);
    try {
      await unlinkInvestor(client, m.id);
      onChange(patchAfterUnlink(investor.group_id ?? null, [briefOf(investor), ...linked], m.id));
      toast.show(`${m.name} unlinked from ${investor.name}.`);
    } catch (err) {
      toast.show(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-label="Linked cards" className={className}>
      <SectionLabel
        aside={
          canWrite ? (
            <button type="button" className="link t-body-s border-0 bg-transparent p-0 touch:min-h-44" onClick={() => setPicking(true)}>
              Link a card
            </button>
          ) : null
        }
      >
        Linked cards
      </SectionLabel>
      {linked.length === 0 ? (
        <p className="t-body-s text-muted">
          Not linked. Link the cards of people who work this deal as one team, like two partners at the same fund.
        </p>
      ) : (
        <ul className="m-0 list-none p-0" aria-label={`Linked with ${investor.name}`}>
          {linked.map((m) => {
            const label = (
              <>
                <span className="truncate font-medium">{m.name}</span>
                {m.firm ? <span className="t-body-s min-w-0 shrink truncate text-muted">{m.firm}</span> : null}
              </>
            );
            const cls = "flex min-h-32 min-w-0 flex-1 items-center gap-8 text-left hover:underline touch:min-h-44";
            return (
              <li key={m.id} className="flex min-w-0 items-center gap-10 border-t border-line first:border-t-0">
                <LinkIcon className="text-faint" />
                {onOpen ? (
                  <button type="button" className={`${cls} border-0 bg-transparent p-0`} onClick={() => onOpen(m.id)} title={`Open ${m.name}`}>
                    {label}
                  </button>
                ) : (
                  <Link href={`${base}/investors/${m.id}`} prefetch={false} className={cls} title={`Open ${m.name}`}>
                    {label}
                  </Link>
                )}
                {canWrite ? (
                  <button
                    type="button"
                    className="link t-body-s shrink-0 border-0 bg-transparent p-0 text-muted hover:text-fg disabled:opacity-50 touch:min-h-44"
                    disabled={busy !== null}
                    aria-label={`Unlink ${m.name} from ${investor.name}`}
                    onClick={() => void unlink(m)}
                  >
                    {busy === m.id ? "Unlinking…" : "Unlink"}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      {canWrite ? (
        <LinkCardsDialog
          open={picking}
          client={client}
          investor={investor}
          onClose={() => setPicking(false)}
          onLinked={(patch, n) => {
            setPicking(false);
            onChange(patch);
            toast.show(`${n === 1 ? "1 card" : `${n} cards`} linked with ${investor.name}.`);
          }}
        />
      ) : null}
    </section>
  );
}

/** Pick one or more contacts and link them to this investor's team. */
function LinkCardsDialog({
  open,
  client,
  investor,
  onClose,
  onLinked,
}: {
  open: boolean;
  client: ApiClient;
  investor: Investor;
  onClose: () => void;
  onLinked: (patch: LinkPatch, count: number) => void;
}) {
  const [picked, setPicked] = useState<LinkedInvestorBrief[]>([]);
  // Briefs of every row the search has shown, for onChange (a ref: the loader must not
  // re-render the dialog, or the Combobox would reload on every new loadOptions identity).
  const found = useRef<Record<string, LinkedInvestorBrief>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const linked = investor.linked;
  const pickedKey = picked.map((p) => p.id).join(",");
  const loadOptions = useCallback(
    async (q: string): Promise<ComboboxOption<string>[]> => {
      const already = new Set([investor.id, ...(linked ?? []).map((m) => m.id)]);
      const chosen = new Set(pickedKey ? pickedKey.split(",") : []);
      const page = await listInvestors(client, { q: q || undefined, limit: 30, sort: q ? undefined : "updated", order: q ? undefined : "desc" });
      const rows = page.data.filter((i) => !already.has(i.id));
      for (const i of rows) found.current[i.id] = briefOf(i);
      return rows.map((i): ComboboxOption<string> => {
        const team = i.linked?.length ? i.linked.length + 1 : 0;
        return {
          value: i.id,
          label: i.name,
          // In the text, not only the icon: linking this card brings its whole team along.
          description: [i.title, i.firm, team ? `on a team of ${team}` : null].filter(Boolean).join(" · ") || undefined,
          hint: team ? <LinkIcon className="text-muted" /> : undefined,
          disabled: chosen.has(i.id),
        };
      });
    },
    // pickedKey: a picked row is disabled from the next load on (the popover closes on pick
    // and reloads when reopened anyway).
    [client, investor.id, linked, pickedKey],
  );

  const close = () => {
    setPicked([]);
    setError(null);
    onClose();
  };

  const submit = async () => {
    if (!picked.length) return;
    setBusy(true);
    setError(null);
    try {
      const res = await linkInvestors(
        client,
        investor.id,
        picked.map((p) => p.id),
      );
      const n = picked.length;
      setPicked([]);
      onLinked(patchAfterLink(res.group_id, res.investors), n);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Link cards"
      description={`Who works this deal with ${investor.name}? Cards already on another team bring their team along.`}
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      actions={
        <>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!picked.length} busy={busy ? "Linking…" : false}>
            {picked.length > 1 ? `Link ${picked.length} cards` : "Link card"}
          </Button>
        </>
      }
    >
      <div className="mt-14 flex flex-col gap-12">
        <Field label="Investor">
          <Combobox<string>
            value={null}
            placeholder="Search your contacts…"
            searchPlaceholder="Name, firm or email"
            loadOptions={loadOptions}
            emptyText={(q) => (q ? `No other contact matches “${q}”.` : "No other contacts yet.")}
            onChange={(id) => {
              const m = id ? found.current[id] : null;
              if (m && !picked.some((p) => p.id === m.id)) setPicked((l) => [...l, m]);
            }}
          />
        </Field>
        {picked.length ? (
          <ul className="m-0 flex list-none flex-wrap gap-6 p-0" aria-label="Cards to link">
            {picked.map((m) => (
              <li key={m.id} className="t-chip inline-flex items-center gap-4 rounded-pill bg-sunk py-1 pr-2 pl-8 text-fg">
                {m.name}
                {m.firm ? <span className="text-muted">· {m.firm}</span> : null}
                <button
                  type="button"
                  className="inline-flex size-20 items-center justify-center rounded-pill border-0 bg-transparent p-0 text-muted hover:text-fg touch:size-32"
                  aria-label={`Remove ${m.name}`}
                  onClick={() => setPicked((l) => l.filter((x) => x.id !== m.id))}
                >
                  <span aria-hidden>✕</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {error ? (
          <p className="t-body-s text-bad" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
