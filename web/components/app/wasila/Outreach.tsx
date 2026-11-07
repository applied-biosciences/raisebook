"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Button,
  Chip,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Tabs,
  Textarea,
  useToast,
} from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import {
  MERGE_FIELDS,
  listMergeFigures,
  missingFigures,
  UPDATE_TEMPLATE,
  type MergeFigure,
  claudeDraft,
  createCampaign,
  createMessage,
  deleteMessage,
  draftCampaign,
  followUpsDue,
  getClaude,
  getMailSettings,
  listCampaigns,
  listDocuments,
  listMessages,
  listSavedLists,
  markReplied,
  searchMasterList,
  sendMessage,
  updateMessage,
  type Campaign,
  type MasterInvestor,
  type OutreachMessage,
  type RoomDocument,
  type SavedList,
} from "@/lib/api/wasila";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/lib/session";

type Tab = "drafts" | "sent" | "campaigns" | "follow_ups";

function when(ts: string | null): string {
  return ts ? new Date(ts).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
}

/**
 * Outreach (Wasila v1.0.0.0): email investors from your own mail account with hand-picked
 * Funding Room attachments; every send is recorded on the investor's timeline. Claude can
 * draft a warm letter or an investor update; nothing is ever sent without your click.
 * Campaigns merge one template into reviewed drafts; follow-ups list sent mail with no reply.
 */
const OUTREACH_START = "Dear {first_name},\n\n\n\nKind regards,";

export function Outreach() {
  const { client, role, workspace } = useWorkspace();
  const toast = useToast();
  const params = useSearchParams();
  const canWrite = role !== "viewer";
  const base = `/w/${workspace.slug}`;
  const [tab, setTab] = useState<Tab>("drafts");
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [followUps, setFollowUps] = useState<OutreachMessage[]>([]);
  const [docs, setDocs] = useState<RoomDocument[]>([]);
  const [lists, setLists] = useState<SavedList[]>([]);
  const [names, setNames] = useState<Record<string, MasterInvestor>>({});
  const [mailReady, setMailReady] = useState<boolean | null>(null);
  const [claudeReady, setClaudeReady] = useState(false);
  const [compose, setCompose] = useState<{ investor?: MasterInvestor; message?: OutreachMessage } | null>(null);
  const [campaignOpen, setCampaignOpen] = useState(false);
  const preset = params.get("investors");

  const reload = useCallback(async () => {
    try {
      const [m, c, f, d, l] = await Promise.all([
        listMessages(client, { limit: "500" }),
        listCampaigns(client),
        followUpsDue(client),
        listDocuments(client, { review_status: "approved" }),
        listSavedLists(client),
      ]);
      setMessages(m.data);
      setCampaigns(c.data);
      setFollowUps(f.data);
      setDocs(d.data.filter((x) => x.current_version > 0));
      setLists(l.data);
      const res = await searchMasterList(client, { limit: 500 });
      setNames(Object.fromEntries(res.data.map((i) => [i.id, i])));
    } catch (err) {
      toast.show(errorMessage(err));
    }
  }, [client, toast]);

  useEffect(() => {
    void reload();
    getMailSettings(client).then((m) => setMailReady(m.configured)).catch(() => setMailReady(false));
    getClaude(client).then((c) => setClaudeReady(c.ready)).catch(() => setClaudeReady(false));
  }, [client, reload]);

  useEffect(() => {
    if (!preset || !Object.keys(names).length) return;
    const ids = preset.split(",").filter(Boolean);
    if (ids.length === 1 && names[ids[0]!]) setCompose({ investor: names[ids[0]!] });
    else if (ids.length > 1) setCampaignOpen(true);
  }, [preset, names]);

  const drafts = messages.filter((m) => m.status === "draft" || m.status === "failed");
  const sent = messages.filter((m) => m.status === "sent");
  const list = tab === "drafts" ? drafts : tab === "sent" ? sent : tab === "follow_ups" ? followUps : [];

  return (
    <>
      <PageHeader
        title="Outreach"
        aside={`${sent.length} sent · ${drafts.length} drafts`}
        subline="Email investors from your own account. Attach approved Funding Room documents by hand; every send lands on the investor's timeline."
        actions={
          canWrite ? (
            <>
              <Button onClick={() => setCampaignOpen(true)}>New campaign</Button>
              <Button variant="primary" onClick={() => setCompose({})}>
                New email
              </Button>
            </>
          ) : null
        }
      />
      {mailReady === false ? (
        <p className="mb-12 rounded-md bg-warm-soft px-12 py-8 text-13 text-warm-ink">
          Mail is not set up yet: drafts work, sending needs your account.{" "}
          <Link href={`${base}/settings/email`} className="underline">
            Set up email
          </Link>
        </p>
      ) : null}

      <Tabs
        label="Outreach"
        value={tab}
        onChange={setTab}
        items={[
          { value: "drafts", label: `Drafts (${drafts.length})` },
          { value: "sent", label: `Sent (${sent.length})` },
          { value: "campaigns", label: `Campaigns (${campaigns.length})` },
          { value: "follow_ups", label: `Follow-ups (${followUps.length})` },
        ]}
      />

      <div className="mt-14">
        {tab === "campaigns" ? (
          !campaigns.length ? (
            <EmptyState title="No campaigns yet" actions={canWrite ? <Button onClick={() => setCampaignOpen(true)}>New campaign</Button> : null}>
              A campaign merges one email (or a monthly investor update) into a reviewed draft per investor.
            </EmptyState>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-8 p-0">
              {campaigns.map((c) => (
                <li key={c.id} className="rounded-md border border-line bg-surface p-12">
                  <p className="m-0 font-medium">
                    {c.name} <Chip tone="type">{c.kind === "update" ? "Investor update" : "Outreach"}</Chip>
                  </p>
                  <p className="m-0 mt-2 text-13 text-muted">
                    {c.stats.sent} sent · {c.stats.drafts} drafts · {c.stats.replied} replied
                    {c.follow_up_days ? ` · follow up after ${c.follow_up_days} days` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )
        ) : !list.length ? (
          <EmptyState title={tab === "drafts" ? "No drafts" : tab === "sent" ? "Nothing sent yet" : "No follow-ups due"}>
            {tab === "follow_ups"
              ? "Campaign emails with no reply after their follow-up days show here."
              : "Write an email, ask Claude for a warm letter, or start a campaign from a saved list."}
          </EmptyState>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-8 p-0">
            {list.map((m) => {
              const inv = names[m.investor_id];
              return (
                <li key={m.id} className="rounded-md border border-line bg-surface p-12">
                  <div className="flex flex-wrap items-start justify-between gap-8">
                    <div className="min-w-0 flex-1">
                      <p className="m-0 font-medium break-words">{m.subject}</p>
                      <p className="m-0 mt-2 text-13 text-muted">
                        To{" "}
                        <Link href={`${base}/investors/${m.investor_id}`} className="text-fg hover:underline">
                          {inv?.name ?? m.to_email}
                        </Link>{" "}
                        · {m.to_email}
                        {m.attachments.length ? ` · ${m.attachments.map((a) => a.filename).join(", ")}` : ""}
                      </p>
                      <p className="m-0 mt-2 text-2xs text-muted">
                        {m.status === "sent" ? `Sent ${when(m.sent_at)}` : m.status === "failed" ? `Failed: ${m.error ?? "try again"}` : `Draft ${when(m.updated_at)}`}
                        {m.drafted_by === "claude" ? <span className="text-agent"> · drafted by Claude</span> : null}
                        {m.replied_at ? <span className="text-good-ink"> · replied {when(m.replied_at)}</span> : null}
                      </p>
                    </div>
                    {canWrite ? (
                      <div className="flex flex-wrap gap-6">
                        {m.status !== "sent" ? (
                          <Button size="sm" onClick={() => setCompose({ investor: inv, message: m })}>
                            Review
                          </Button>
                        ) : !m.replied_at ? (
                          <Button
                            size="sm"
                            onClick={async () => {
                              const note = window.prompt("What did they say? (optional)") ?? undefined;
                              try {
                                await markReplied(client, m.id, note);
                                toast.show("Reply logged on the timeline.");
                                void reload();
                              } catch (err) {
                                toast.show(errorMessage(err));
                              }
                            }}
                          >
                            Log reply
                          </Button>
                        ) : null}
                        {tab === "follow_ups" && inv ? (
                          <Button size="sm" variant="primary" onClick={() => setCompose({ investor: inv })}>
                            Follow up
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {compose ? (
        <Composer
          key={compose.message?.id ?? compose.investor?.id ?? "new"}
          initialInvestor={compose.investor}
          message={compose.message}
          docs={docs}
          claudeReady={claudeReady}
          mailReady={!!mailReady}
          onClose={() => setCompose(null)}
          onDone={reload}
        />
      ) : null}
      <CampaignDialog
        open={campaignOpen}
        onClose={() => setCampaignOpen(false)}
        docs={docs}
        lists={lists}
        presetIds={preset?.split(",").filter(Boolean) ?? []}
        onDone={() => {
          setTab("drafts");
          void reload();
        }}
      />
    </>
  );
}

function Composer({
  initialInvestor,
  message,
  docs,
  claudeReady,
  mailReady,
  onClose,
  onDone,
}: {
  initialInvestor?: MasterInvestor;
  message?: OutreachMessage;
  docs: RoomDocument[];
  claudeReady: boolean;
  mailReady: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const { client } = useWorkspace();
  const toast = useToast();
  const [investor, setInvestor] = useState<MasterInvestor | undefined>(initialInvestor);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<MasterInvestor[]>([]);
  const [subject, setSubject] = useState(message?.subject ?? "");
  const [body, setBody] = useState(message?.body ?? "");
  const [attach, setAttach] = useState<string[]>(message?.attachments.map((a) => a.document_id) ?? []);
  const [kind, setKind] = useState<"outreach" | "update">((message?.kind === "update" ? "update" : "outreach"));
  const [instructions, setInstructions] = useState("");
  const [draftId, setDraftId] = useState<string | null>(message?.id ?? null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (investor || query.trim().length < 2) {
      setMatches([]);
      return;
    }
    const t = setTimeout(() => {
      searchMasterList(client, { q: query.trim(), limit: 8 })
        .then((r) => setMatches(r.data))
        .catch(() => setMatches([]));
    }, 200);
    return () => clearTimeout(t);
  }, [client, query, investor]);

  const save = async (): Promise<string | null> => {
    if (!investor) {
      setError("Choose who the email is to.");
      return null;
    }
    if (!subject.trim() || !body.trim()) {
      setError("Write a subject and a message.");
      return null;
    }
    setError(null);
    if (draftId) {
      await updateMessage(client, draftId, { subject, body, attachment_ids: attach });
      return draftId;
    }
    const m = await createMessage(client, { investor_id: investor.id, subject, body, attachment_ids: attach, kind });
    setDraftId(m.id);
    return m.id;
  };

  const askClaude = async () => {
    if (!investor) {
      setError("Choose who the email is to first.");
      return;
    }
    setBusy("claude");
    setError(null);
    try {
      const m = await claudeDraft(client, { investor_id: investor.id, kind, instructions: instructions.trim() || undefined, attachment_ids: attach });
      if (draftId) await deleteMessage(client, draftId).catch(() => undefined);
      setDraftId(m.id);
      setSubject(m.subject);
      setBody(m.body);
      toast.show("Claude drafted it. Read it, edit, then send.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      width={720}
      scrollBody
      title={message ? "Review email" : "New email"}
      description="Nothing is sent until you press Send."
      actions={
        <>
          {draftId ? (
            <Button
              variant="danger-quiet"
              onClick={async () => {
                await deleteMessage(client, draftId).catch((e) => toast.show(errorMessage(e)));
                onDone();
                onClose();
              }}
            >
              Discard
            </Button>
          ) : null}
          <Button
            busy={busy === "save" ? "Saving…" : false}
            onClick={async () => {
              setBusy("save");
              try {
                if (await save()) {
                  toast.show("Draft saved.");
                  onDone();
                  onClose();
                }
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(null);
              }
            }}
          >
            Save draft
          </Button>
          <Button
            variant="primary"
            disabled={!mailReady}
            title={mailReady ? undefined : "Set up email in Settings first"}
            busy={busy === "send" ? "Sending…" : false}
            onClick={async () => {
              setBusy("send");
              try {
                const id = await save();
                if (!id) return;
                if (!window.confirm(`Send “${subject}” to ${investor?.name} now?`)) return;
                await sendMessage(client, id);
                toast.show(`Sent to ${investor?.name}. It is on their timeline.`);
                onDone();
                onClose();
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(null);
              }
            }}
          >
            Send
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-12">
        {investor ? (
          <p className="m-0 flex flex-wrap items-center gap-8 text-13">
            To <span className="font-medium">{investor.name}</span>
            <span className="text-muted">{investor.firm ? `· ${investor.firm}` : ""} {investor.email ? `· ${investor.email}` : "· no email on file"}</span>
            {!message ? (
              <button type="button" className="border-0 bg-transparent p-0 text-accent underline" onClick={() => setInvestor(undefined)}>
                Change
              </button>
            ) : null}
          </p>
        ) : (
          <Field label="To">
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search an investor by name or firm" autoFocus />
          </Field>
        )}
        {matches.length ? (
          <ul className="m-0 -mt-6 flex list-none flex-col rounded-md border border-line p-0">
            {matches.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className="w-full border-0 bg-transparent px-10 py-8 text-left text-13 hover:bg-sunk"
                  onClick={() => {
                    setInvestor(m);
                    setQuery("");
                  }}
                >
                  {m.name} <span className="text-muted">{m.firm ?? ""}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="grid grid-cols-1 gap-12 sm:grid-cols-[160px_minmax(0,1fr)]">
          <Field label="Kind">
            <Select value={kind} onChange={(e) => setKind(e.target.value as "outreach" | "update")} disabled={!!message}>
              <option value="outreach">Warm letter</option>
              <option value="update">Investor update</option>
            </Select>
          </Field>
          <Field label="Subject" error={error}>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </Field>
        </div>
        <Field label="Message">
          <Textarea rows={12} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <fieldset className="m-0 flex flex-col gap-6 border-0 p-0">
          <legend className="mb-4 text-[12px] text-muted">Attach from the Funding Room (approved documents)</legend>
          {!docs.length ? <p className="m-0 text-13 text-muted">No approved documents yet. Approve your deck and one-pager in the Funding Room.</p> : null}
          {docs.map((d) => (
            <label key={d.id} className="flex items-center gap-8 text-13">
              <input
                type="checkbox"
                checked={attach.includes(d.id)}
                onChange={(e) => setAttach((a) => (e.target.checked ? [...a, d.id] : a.filter((x) => x !== d.id)))}
              />
              {d.title} <span className="text-muted">{d.latest?.filename}</span>
            </label>
          ))}
        </fieldset>
        <div className={cn("rounded-md border border-line p-10", !claudeReady && "opacity-70")}>
          <Field label="Ask Claude to draft it" hint={claudeReady ? "Claude sees the investor's public profile, your company profile and the attachment names, never emails or notes." : "Add your Anthropic key in Settings → Claude to use this."}>
            <Input value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="Mention we'll be in Riyadh at the end of November" disabled={!claudeReady} />
          </Field>
          <Button size="sm" className="mt-8" disabled={!claudeReady} busy={busy === "claude" ? "Claude is writing…" : false} onClick={() => void askClaude()}>
            Draft with Claude
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function CampaignDialog({
  open,
  onClose,
  docs,
  lists,
  presetIds,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  docs: RoomDocument[];
  lists: SavedList[];
  presetIds: string[];
  onDone: () => void;
}) {
  const { client, workspace } = useWorkspace();
  const toast = useToast();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"outreach" | "update">("outreach");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState(OUTREACH_START);
  const [figures, setFigures] = useState<MergeFigure[]>([]);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!open) return;
    let live = true;
    listMergeFigures(client).then(
      (r) => live && setFigures(r.data),
      () => live && setFigures([]),
    );
    return () => {
      live = false;
    };
  }, [open, client]);
  const missing = useMemo(() => missingFigures(`${subject}\n${body}`, figures), [subject, body, figures]);
  /** Put {key} where the cursor is in the message (or at the end). */
  const insertFigure = (key: string) => {
    const el = bodyRef.current;
    const token = `{${key}}`;
    const at = el ? el.selectionStart : body.length;
    const end = el ? el.selectionEnd : body.length;
    setBody(body.slice(0, at) + token + body.slice(end));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(at + token.length, at + token.length);
    });
  };
  const [attach, setAttach] = useState<string[]>([]);
  const [listId, setListId] = useState("");
  const [followUp, setFollowUp] = useState("7");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const who = useMemo(() => (presetIds.length ? `${presetIds.length} selected investors` : ""), [presetIds]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      width={680}
      scrollBody
      title="New campaign"
      description="One email merged per investor ({first_name}, {firm} …). It creates drafts to review; nothing is sent."
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            busy={busy ? "Creating drafts…" : false}
            onClick={async () => {
              if (!name.trim() || !subject.trim() || !body.trim() || (!listId && !presetIds.length)) {
                setError("Name it, write the email and choose who it goes to.");
                return;
              }
              setBusy(true);
              setError(null);
              try {
                const camp = await createCampaign(client, {
                  name: name.trim(),
                  kind,
                  subject,
                  body,
                  attachment_ids: attach,
                  follow_up_days: followUp ? Number(followUp) : null,
                });
                const out = await draftCampaign(client, camp.id, listId ? { saved_list_id: listId } : { investor_ids: presetIds });
                toast.show(`${out.created.length} drafts ready to review${out.skipped.length ? `, ${out.skipped.length} skipped (no email)` : ""}.`);
                onDone();
                onClose();
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            Create drafts
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-12">
        <div className="grid grid-cols-1 gap-12 sm:grid-cols-2">
          <Field label="Campaign name" error={error}>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="November investor update" />
          </Field>
          <Field label="Kind">
            <Select
              value={kind}
              onChange={(e) => {
                const next = e.target.value as "outreach" | "update";
                setKind(next);
                // Swap the starting text only while it is untouched.
                if (next === "update" && body === OUTREACH_START) setBody(UPDATE_TEMPLATE);
                if (next === "outreach" && body === UPDATE_TEMPLATE) setBody(OUTREACH_START);
              }}
            >
              <option value="outreach">Warm outreach</option>
              <option value="update">Investor update</option>
            </Select>
          </Field>
          <Field label="To">
            {presetIds.length ? (
              <Input value={who} readOnly />
            ) : (
              <Select value={listId} onChange={(e) => setListId(e.target.value)}>
                <option value="">Choose a saved list…</option>
                {lists.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Follow up if no reply after">
            <Select value={followUp} onChange={(e) => setFollowUp(e.target.value)}>
              <option value="">No reminder</option>
              {[3, 5, 7, 10, 14, 21].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Subject">
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Applied Biosciences x {firm}" />
        </Field>
        <Field label="Message" hint={`Placeholders: ${MERGE_FIELDS.map((f) => `{${f}}`).join(" ")}`}>
          <Textarea ref={bodyRef} rows={10} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        {kind === "update" && figures.length ? (
          <div className="flex flex-col gap-6 rounded-md border border-line bg-accent-soft p-10">
            <span className="text-[12px] font-medium text-sky-ink">Insert a funding figure (filled in from Costs for every investor)</span>
            <div className="flex flex-wrap gap-6">
              {figures.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => insertFigure(f.key)}
                  title={`{${f.key}}`}
                  className="rounded-sm border border-brand-sky/45 bg-surface px-8 py-3 text-[12px] text-accent hover:border-accent"
                >
                  {f.label}
                  <span className="ml-6 text-muted">{f.value || "not set"}</span>
                </button>
              ))}
            </div>
            {missing.length ? (
              <span className="text-[12px] text-warm-ink">
                {missing.map((f) => f.label).join(", ")} {missing.length === 1 ? "is" : "are"} not in Costs yet, so {missing.length === 1 ? "it" : "they"} would be left blank.{" "}
                <Link href={`/w/${workspace.slug}/funding-costs`} className="underline">
                  Open Costs
                </Link>
              </span>
            ) : null}
          </div>
        ) : null}
        <fieldset className="m-0 flex flex-col gap-6 border-0 p-0">
          <legend className="mb-4 text-[12px] text-muted">Attachments (approved Funding Room documents)</legend>
          {docs.map((d) => (
            <label key={d.id} className="flex items-center gap-8 text-13">
              <input type="checkbox" checked={attach.includes(d.id)} onChange={(e) => setAttach((a) => (e.target.checked ? [...a, d.id] : a.filter((x) => x !== d.id)))} />
              {d.title}
            </label>
          ))}
        </fieldset>
      </div>
    </Dialog>
  );
}
