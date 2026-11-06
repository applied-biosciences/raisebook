"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button, Field, Input, PageHeader, Textarea, useToast } from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import {
  downloadPath,
  getClaude,
  readDeck,
  saveDeck,
  saveFile,
  searchMasterList,
  suggestDeck,
  type Deck,
  type MasterInvestor,
} from "@/lib/api/wasila";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/lib/session";

type Suggestion = { slide: number; shape: number; text: string; why: string };

/**
 * The deck editor (Wasila v1.0.0.0): change the words on each slide, hide slides or change
 * their order, and save a new version of the deck in the Funding Room. Layout, images and
 * fonts stay as designed. Claude can suggest a version tailored to one investor; its
 * suggestions only fill the boxes, they are saved when you save.
 */
export function DeckEditor({ docId }: { docId: string }) {
  const { client, role, workspace } = useWorkspace();
  const toast = useToast();
  const canWrite = role !== "viewer";
  const [deck, setDeck] = useState<Deck | null>(null);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [hidden, setHidden] = useState<number[]>([]);
  const [order, setOrder] = useState<number[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [claudeReady, setClaudeReady] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [investorQ, setInvestorQ] = useState("");
  const [investor, setInvestor] = useState<MasterInvestor | null>(null);
  const [matches, setMatches] = useState<MasterInvestor[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await readDeck(client, docId);
      setDeck(d);
      setTexts(Object.fromEntries(d.slides.flatMap((s) => s.shapes.map((sh) => [`${s.slide}:${sh.shape}`, sh.text]))));
      setHidden(d.slides.filter((s) => s.hidden).map((s) => s.slide));
      setOrder(d.slides.map((s) => s.slide));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [client, docId]);

  useEffect(() => {
    void load();
    getClaude(client).then((c) => setClaudeReady(c.ready)).catch(() => undefined);
  }, [client, load]);

  useEffect(() => {
    if (investor || investorQ.trim().length < 2) {
      setMatches([]);
      return;
    }
    const t = setTimeout(() => searchMasterList(client, { q: investorQ, limit: 6 }).then((r) => setMatches(r.data)).catch(() => undefined), 200);
    return () => clearTimeout(t);
  }, [client, investorQ, investor]);

  const edits = useMemo(() => {
    if (!deck) return [];
    return deck.slides.flatMap((s) =>
      s.shapes
        .filter((sh) => texts[`${s.slide}:${sh.shape}`] !== sh.text)
        .map((sh) => ({ slide: s.slide, shape: sh.shape, text: texts[`${s.slide}:${sh.shape}`] ?? sh.text })),
    );
  }, [deck, texts]);
  const orderChanged = deck ? order.join(",") !== deck.slides.map((s) => s.slide).join(",") : false;
  const hiddenChanged = deck ? hidden.slice().sort().join(",") !== deck.slides.filter((s) => s.hidden).map((s) => s.slide).join(",") : false;
  const dirty = edits.length > 0 || orderChanged || hiddenChanged;

  const move = (i: number, by: number) =>
    setOrder((o) => {
      const j = i + by;
      if (j < 0 || j >= o.length) return o;
      const n = o.slice();
      [n[i], n[j]] = [n[j]!, n[i]!];
      return n;
    });

  if (error) return <p className="text-bad">{error}</p>;
  if (!deck) return <p className="text-muted">Opening the deck…</p>;
  const bySlide = new Map(deck.slides.map((s) => [s.slide, s]));

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Funding Room", href: `/w/${workspace.slug}/funding-room` }]}
        title={deck.title}
        aside={`Version ${deck.version} · ${deck.slides.length} slides`}
        actions={
          <>
            <Button onClick={() => saveFile(client, downloadPath(docId, deck.version), deck.filename).catch((e) => toast.show(errorMessage(e)))}>Download</Button>
            {canWrite ? (
              <Button
                variant="primary"
                disabled={!dirty}
                busy={busy === "save" ? "Saving…" : false}
                onClick={async () => {
                  setBusy("save");
                  try {
                    const v = await saveDeck(client, docId, {
                      base_version: deck.version,
                      edits,
                      hidden,
                      order: orderChanged ? order : undefined,
                    });
                    toast.show(`Saved as version ${v.version}. Earlier versions are kept.`);
                    setSuggestions([]);
                    void load();
                  } catch (err) {
                    toast.show(errorMessage(err));
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                Save as new version
              </Button>
            ) : null}
          </>
        }
        subline="Edit the words only: layout, images and fonts stay exactly as designed. New versions go to the Funding Room as drafts of the same document."
      />

      <div className="grid grid-cols-1 gap-20 xl:grid-cols-[minmax(0,1fr)_320px]">
        <ol className="m-0 flex list-none flex-col gap-12 p-0">
          {order.map((n, i) => {
            const s = bySlide.get(n)!;
            const off = hidden.includes(n);
            return (
              <li key={n} className={cn("rounded-md border border-line bg-surface p-12", off && "opacity-55")}>
                <div className="mb-8 flex flex-wrap items-center justify-between gap-8">
                  <p className="m-0 font-medium">
                    <span className="t-micro mr-6 text-muted">Slide {i + 1}</span>
                    {s.title}
                  </p>
                  {canWrite ? (
                    <span className="flex items-center gap-6">
                      <Button size="sm" variant="ghost" aria-label={`Move slide ${i + 1} up`} disabled={i === 0} onClick={() => move(i, -1)}>
                        ↑
                      </Button>
                      <Button size="sm" variant="ghost" aria-label={`Move slide ${i + 1} down`} disabled={i === order.length - 1} onClick={() => move(i, 1)}>
                        ↓
                      </Button>
                      <label className="flex items-center gap-4 text-13">
                        <input type="checkbox" checked={off} onChange={(e) => setHidden((h) => (e.target.checked ? [...h, n] : h.filter((x) => x !== n)))} /> Hide
                      </label>
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-col gap-8">
                  {s.shapes.map((sh) => {
                    const key = `${n}:${sh.shape}`;
                    const sug = suggestions.find((x) => x.slide === n && x.shape === sh.shape);
                    return (
                      <div key={key}>
                        <Textarea
                          aria-label={`Slide ${i + 1}, ${sh.name}`}
                          rows={Math.min(6, Math.max(1, Math.ceil((texts[key] ?? "").length / 70) + (texts[key] ?? "").split("\n").length - 1))}
                          value={texts[key] ?? ""}
                          disabled={!canWrite}
                          onChange={(e) => setTexts((t) => ({ ...t, [key]: e.target.value }))}
                          className={cn(texts[key] !== sh.text && "border-accent")}
                        />
                        {sug ? (
                          <p className="m-0 mt-4 text-13">
                            <span className="text-agent">Claude suggests:</span> {sug.text} <span className="text-muted">({sug.why})</span>{" "}
                            <button type="button" className="border-0 bg-transparent p-0 text-accent underline" onClick={() => setTexts((t) => ({ ...t, [key]: sug.text }))}>
                              Use it
                            </button>
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                  {!s.shapes.length ? <p className="m-0 text-13 text-muted">No text on this slide (images or a chart only).</p> : null}
                </div>
              </li>
            );
          })}
        </ol>

        <aside className="flex flex-col gap-12">
          <section className="rounded-md border border-line bg-surface p-12">
            <h2 className="t-display-xs m-0 mb-8">Tailor with Claude</h2>
            {!claudeReady ? (
              <p className="m-0 text-13 text-muted">
                Add your Anthropic key in{" "}
                <Link href={`/w/${workspace.slug}/settings/claude`} className="text-accent underline">
                  Settings → Claude
                </Link>{" "}
                to get suggestions.
              </p>
            ) : (
              <div className="flex flex-col gap-10">
                <Field label="What should change?">
                  <Textarea rows={3} value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Tailor for a Saudi healthcare family office; lead with the MOH evaluation." />
                </Field>
                <Field label="For an investor" optional>
                  {investor ? (
                    <p className="m-0 text-13">
                      {investor.name}{" "}
                      <button type="button" className="border-0 bg-transparent p-0 text-accent underline" onClick={() => setInvestor(null)}>
                        Change
                      </button>
                    </p>
                  ) : (
                    <Input value={investorQ} onChange={(e) => setInvestorQ(e.target.value)} placeholder="Search by name or firm" />
                  )}
                </Field>
                {matches.map((m) => (
                  <button key={m.id} type="button" className="border-0 bg-transparent p-0 text-left text-13 text-accent" onClick={() => { setInvestor(m); setInvestorQ(""); }}>
                    {m.name} <span className="text-muted">{m.firm}</span>
                  </button>
                ))}
                <Button
                  busy={busy === "suggest" ? "Claude is reading the deck…" : false}
                  disabled={instruction.trim().length < 3}
                  onClick={async () => {
                    setBusy("suggest");
                    try {
                      const r = await suggestDeck(client, docId, { instruction, investor_id: investor?.id ?? null });
                      setSuggestions(r.suggestions);
                      toast.show(r.suggestions.length ? `${r.suggestions.length} suggestions under the slides.` : "Claude had no changes to suggest.");
                    } catch (err) {
                      toast.show(errorMessage(err));
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  Suggest edits
                </Button>
                <p className="m-0 text-2xs text-muted">Claude sees the slide text and the investor&apos;s public profile. Nothing changes until you save.</p>
              </div>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}
