"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Button,
  Chip,
  CodeBlock,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  SectionLabel,
  Segmented,
  Select,
  Textarea,
  useToast,
} from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import {
  CATEGORY_LABEL,
  CONFIDENTIALITY_LABEL,
  JURISDICTION_LABEL,
  REVIEW_LABEL,
  createDocument,
  createLink,
  deleteDocument,
  downloadPath,
  fileSize,
  getChecklist,
  listDocuments,
  listLinks,
  listRoomEvents,
  revokeLink,
  saveFile,
  updateDocument,
  uploadVersion,
  type ChecklistItem,
  type Confidentiality,
  type DocJurisdiction,
  type ReviewStatus,
  type RoomCategory,
  type RoomDocument,
  type RoomEvent,
  type RoomLink,
} from "@/lib/api/wasila";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/lib/session";

const STATUS_TONE: Record<ReviewStatus, string> = {
  draft: "bg-sunk text-muted",
  in_review: "bg-warm-soft text-warm-ink",
  approved: "bg-good-soft text-good-ink",
  archived: "bg-sunk text-faint",
};

const EVENT_WORDS: Record<string, string> = {
  created: "added",
  version_added: "uploaded a new version of",
  updated: "updated",
  deleted: "deleted",
  downloaded: "downloaded",
  link_created: "created a share link",
  link_revoked: "revoked a share link",
  link_viewed: "Share link opened",
};

function when(ts: string): string {
  return new Date(ts).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/**
 * The Funding Room (Wasila v1.0.0.0): the diligence document repository. Documents by
 * category with versions, review status and confidentiality; the US / UK / KSA checklist;
 * expiring share links (approved documents only); and the room's activity.
 */
export function FundingRoom() {
  const { client, role, workspace } = useWorkspace();
  const toast = useToast();
  const canWrite = role !== "viewer";
  const [docs, setDocs] = useState<RoomDocument[] | null>(null);
  const [links, setLinks] = useState<RoomLink[]>([]);
  const [events, setEvents] = useState<RoomEvent[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [market, setMarket] = useState<DocJurisdiction>("uk");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [d, l, e] = await Promise.all([listDocuments(client), listLinks(client), listRoomEvents(client)]);
      setDocs(d.data);
      setLinks(l.data);
      setEvents(e.data);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [client]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    getChecklist(client, market)
      .then((r) => setChecklist(r.items))
      .catch(() => setChecklist([]));
  }, [client, market, docs]);

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (docs ?? []).filter((d) => !t || `${d.title} ${d.folder ?? ""} ${d.description ?? ""}`.toLowerCase().includes(t));
  }, [docs, q]);

  const grouped = useMemo(() => {
    const out = new Map<RoomCategory, RoomDocument[]>();
    for (const d of shown) out.set(d.category, [...(out.get(d.category) ?? []), d]);
    return [...out.entries()];
  }, [shown]);

  const approved = (docs ?? []).filter((d) => d.review_status === "approved" && d.current_version > 0);
  const counts = useMemo(() => {
    const c = { approved: 0, in_review: 0, draft: 0 };
    for (const d of docs ?? []) if (d.review_status in c) c[d.review_status as keyof typeof c] += 1;
    return c;
  }, [docs]);

  return (
    <>
      <PageHeader
        title="Funding Room"
        aside={docs ? `${docs.length} documents · ${counts.approved} approved` : undefined}
        subline="Your diligence repository: every version kept, only approved documents can be shared or attached."
        actions={
          canWrite ? (
            <>
              <Button onClick={() => setSharing(true)} disabled={!approved.length}>
                Share link
              </Button>
              <Button variant="primary" onClick={() => setAdding(true)}>
                Add document
              </Button>
            </>
          ) : null
        }
      />
      {error ? <p className="mb-12 text-bad">{error}</p> : null}

      <div className="grid grid-cols-1 gap-20 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-label="Documents" className="min-w-0">
          <div className="mb-12 flex flex-wrap items-center gap-8">
            <Input
              type="search"
              placeholder="Search titles and folders"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full sm:w-[320px]"
              aria-label="Search documents"
            />
          </div>
          {docs === null ? (
            <p className="text-muted">Loading the Funding Room…</p>
          ) : !docs.length ? (
            <EmptyState
              title="The Funding Room is empty"
              actions={canWrite ? <Button variant="primary" onClick={() => setAdding(true)}>Add your first document</Button> : null}
            >
              Add your deck, one-pager, financial model and diligence files. Each upload keeps its earlier versions.
            </EmptyState>
          ) : (
            <div className="flex flex-col gap-18">
              {grouped.map(([cat, list]) => (
                <div key={cat}>
                  <SectionLabel>{CATEGORY_LABEL[cat]}</SectionLabel>
                  <ul className="m-0 mt-6 flex list-none flex-col gap-8 p-0">
                    {list.map((d) => (
                      <DocumentRow key={d.id} doc={d} canWrite={canWrite} onChange={reload} wsSlug={workspace.slug} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="flex min-w-0 flex-col gap-20">
          <section aria-label="Checklist" className="rounded-md border border-line bg-surface p-14">
            <div className="mb-10 flex flex-wrap items-center justify-between gap-8">
              <h2 className="t-display-xs m-0">Checklist</h2>
              <Segmented
                label="Market"
                size="sm"
                value={market}
                onChange={setMarket}
                options={[
                  { value: "uk", label: "UK" },
                  { value: "us", label: "US" },
                  { value: "ksa", label: "KSA" },
                ]}
              />
            </div>
            <ul className="m-0 flex list-none flex-col gap-6 p-0">
              {checklist.map((i) => (
                <li key={i.key} className="flex items-start gap-8 text-13">
                  <span
                    aria-hidden
                    className={cn(
                      "mt-4 inline-block size-8 shrink-0 rounded-pill",
                      i.status === "approved" ? "bg-good" : i.status === "present" ? "bg-warm" : "bg-line",
                    )}
                  />
                  <span className={i.status === "missing" ? "text-muted" : "text-fg"}>
                    {i.label}
                    <span className="sr-only"> ({i.status})</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="t-micro mt-10 mb-0 text-muted">A guide to what investors usually ask for, not legal advice.</p>
          </section>

          <section aria-label="Share links" className="rounded-md border border-line bg-surface p-14">
            <h2 className="t-display-xs m-0 mb-10">Share links</h2>
            {!links.length ? (
              <p className="m-0 text-13 text-muted">No links yet. A link shows approved documents and expires on its own.</p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-10 p-0">
                {links.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center justify-between gap-6 text-13">
                    <span className="min-w-0">
                      <span className="font-medium">{l.label}</span>
                      <span className="block text-muted">
                        {l.state === "active" ? `Expires ${new Date(l.expires_at).toLocaleDateString()}` : l.state === "revoked" ? "Revoked" : "Expired"} ·{" "}
                        {l.view_count} {l.view_count === 1 ? "view" : "views"} · {l.document_ids.length} docs
                      </span>
                    </span>
                    {canWrite && l.state === "active" ? (
                      <Button
                        size="sm"
                        variant="danger-quiet"
                        onClick={async () => {
                          try {
                            await revokeLink(client, l.id);
                            toast.show("Link revoked.");
                            void reload();
                          } catch (err) {
                            toast.show(errorMessage(err));
                          }
                        }}
                      >
                        Revoke
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-label="Activity" className="rounded-md border border-line bg-surface p-14">
            <h2 className="t-display-xs m-0 mb-10">Activity</h2>
            <ul className="m-0 flex list-none flex-col gap-6 p-0 text-13">
              {events.slice(0, 12).map((e) => {
                const title = (docs ?? []).find((d) => d.id === e.document_id)?.title ?? (e.data.title as string | undefined);
                return (
                  <li key={e.id} className="text-muted">
                    <span className={e.actor_type === "agent" ? "text-agent" : "text-fg"}>
                      {e.kind === "link_viewed" ? "" : (e.actor_label ?? "Someone") + " "}
                    </span>
                    {EVENT_WORDS[e.kind] ?? e.kind} {title ? <span className="text-fg">{title}</span> : null}
                    <span className="block text-2xs">{when(e.created_at)}</span>
                  </li>
                );
              })}
              {!events.length ? <li className="text-muted">Nothing yet.</li> : null}
            </ul>
          </section>
        </aside>
      </div>

      <AddDocumentDialog open={adding} onClose={() => setAdding(false)} onDone={reload} />
      <ShareDialog open={sharing} onClose={() => setSharing(false)} approved={approved} onDone={reload} />
    </>
  );
}

function DocumentRow({
  doc,
  canWrite,
  onChange,
  wsSlug,
}: {
  doc: RoomDocument;
  canWrite: boolean;
  onChange: () => void;
  wsSlug: string;
}) {
  const { client } = useWorkspace();
  const toast = useToast();
  const file = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const isDeck = doc.latest?.filename.toLowerCase().endsWith(".pptx");

  const upload = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 25 * 1024 * 1024) {
      toast.show("Files can be at most 25 MB.");
      return;
    }
    setBusy(true);
    try {
      const v = await uploadVersion(client, doc.id, f, f.name);
      toast.show(`Version ${v.version} uploaded.`);
      onChange();
    } catch (err) {
      toast.show(errorMessage(err));
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  };

  return (
    <li className="rounded-md border border-line bg-surface p-12">
      <div className="flex flex-wrap items-start justify-between gap-10">
        <div className="min-w-0 flex-1">
          <p className="m-0 font-medium break-words">{doc.title}</p>
          <p className="m-0 mt-2 flex flex-wrap items-center gap-6 text-sm text-muted">
            <span className={cn("rounded-pill px-8 py-1 text-xs font-medium", STATUS_TONE[doc.review_status])}>{REVIEW_LABEL[doc.review_status]}</span>
            <Chip tone="type">{CONFIDENTIALITY_LABEL[doc.confidentiality]}</Chip>
            {doc.jurisdiction !== "all" ? <Chip tone="type">{JURISDICTION_LABEL[doc.jurisdiction]}</Chip> : null}
            {doc.latest ? (
              <span>
                v{doc.current_version} · {doc.latest.filename} · {fileSize(doc.latest.size_bytes)}
              </span>
            ) : (
              <span>No file yet</span>
            )}
          </p>
          {doc.description ? <p className="m-0 mt-4 text-13 text-muted">{doc.description}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-6">
          {doc.latest ? (
            <Button size="sm" onClick={() => saveFile(client, downloadPath(doc.id), doc.latest!.filename).catch((e) => toast.show(errorMessage(e)))}>
              Download
            </Button>
          ) : null}
          {isDeck ? (
            <Link href={`/w/${wsSlug}/decks/${doc.id}`} className="inline-flex h-28 items-center rounded-sm border border-line px-10 text-sm font-medium touch:min-h-44">
              Edit deck
            </Link>
          ) : null}
          {canWrite ? (
            <>
              <input
                ref={file}
                type="file"
                className="sr-only"
                aria-label={`Upload a new version of ${doc.title}`}
                accept=".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.png,.jpg,.jpeg"
                onChange={(e) => void upload(e.target.files?.[0])}
              />
              <Button size="sm" busy={busy ? "Uploading…" : false} onClick={() => file.current?.click()}>
                {doc.latest ? "New version" : "Upload file"}
              </Button>
              <Select
                size="sm"
                aria-label={`Review status of ${doc.title}`}
                value={doc.review_status}
                onChange={async (e) => {
                  try {
                    await updateDocument(client, doc.id, { review_status: e.target.value as ReviewStatus });
                    onChange();
                  } catch (err) {
                    toast.show(errorMessage(err));
                  }
                }}
              >
                {(Object.keys(REVIEW_LABEL) as ReviewStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {REVIEW_LABEL[s]}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Delete ${doc.title}`}
                onClick={async () => {
                  if (!window.confirm(`Delete “${doc.title}” and all its versions?`)) return;
                  try {
                    await deleteDocument(client, doc.id);
                    onChange();
                  } catch (err) {
                    toast.show(errorMessage(err));
                  }
                }}
              >
                Delete
              </Button>
            </>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function AddDocumentDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { client } = useWorkspace();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<RoomCategory>("pitch");
  const [confidentiality, setConf] = useState<Confidentiality>("investors");
  const [jurisdiction, setJur] = useState<DocJurisdiction>("all");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) {
      setError("Give the document a title.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const doc = await createDocument(client, { title: title.trim(), category, confidentiality, jurisdiction, description: description.trim() || null });
      if (file) await uploadVersion(client, doc.id, file, file.name);
      toast.show(`“${doc.title}” added.`);
      setTitle("");
      setDescription("");
      setFile(null);
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add a document"
      description="New documents start as drafts. Approve them before sharing or attaching."
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      actions={
        <>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" busy={busy ? "Adding…" : false}>
            Add document
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-12">
        <Field label="Title" error={error}>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Investor deck (November)" />
        </Field>
        <div className="grid grid-cols-1 gap-12 sm:grid-cols-2">
          <Field label="Category">
            <Select value={category} onChange={(e) => setCategory(e.target.value as RoomCategory)}>
              {(Object.keys(CATEGORY_LABEL) as RoomCategory[]).map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Confidentiality">
            <Select value={confidentiality} onChange={(e) => setConf(e.target.value as Confidentiality)}>
              {(Object.keys(CONFIDENTIALITY_LABEL) as Confidentiality[]).map((c) => (
                <option key={c} value={c}>
                  {CONFIDENTIALITY_LABEL[c]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Market">
            <Select value={jurisdiction} onChange={(e) => setJur(e.target.value as DocJurisdiction)}>
              {(Object.keys(JURISDICTION_LABEL) as DocJurisdiction[]).map((c) => (
                <option key={c} value={c}>
                  {JURISDICTION_LABEL[c]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="File" optional hint="PDF, Word, Excel, PowerPoint, CSV or images; 25 MB max.">
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.png,.jpg,.jpeg"
              className="text-13"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
        </div>
        <Field label="Description" optional>
          <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
      </div>
    </Dialog>
  );
}

function ShareDialog({
  open,
  onClose,
  approved,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  approved: RoomDocument[];
  onDone: () => void;
}) {
  const { client } = useWorkspace();
  const [label, setLabel] = useState("");
  const [days, setDays] = useState(14);
  const [chosen, setChosen] = useState<string[]>([]);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setUrl(null);
    setLabel("");
    setChosen([]);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      dismissible={!url}
      title={url ? "Copy the link now" : "Share approved documents"}
      description={url ? "It is shown once. Anyone with it can open these documents until it expires." : "A private link for one investor or fund. It expires on its own; you can revoke it."}
      actions={
        url ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <>
            <Button onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              busy={busy ? "Creating…" : false}
              onClick={async () => {
                if (!label.trim() || !chosen.length) {
                  setError("Name the link and choose at least one document.");
                  return;
                }
                setBusy(true);
                setError(null);
                try {
                  const l = await createLink(client, { label: label.trim(), document_ids: chosen, days });
                  setUrl(`${window.location.origin}/room/${l.token}`);
                  onDone();
                } catch (err) {
                  setError(errorMessage(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Create link
            </Button>
          </>
        )
      }
    >
      {url ? (
        <CodeBlock code={url} />
      ) : (
        <div className="flex flex-col gap-12">
          <Field label="Who is it for?" error={error}>
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Fictional Ventures (partner meeting)" />
          </Field>
          <Field label="Expires after">
            <Select value={String(days)} onChange={(e) => setDays(Number(e.target.value))}>
              {[3, 7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </Select>
          </Field>
          <fieldset className="m-0 flex flex-col gap-6 border-0 p-0">
            <legend className="mb-4 text-[12px] text-muted">Documents</legend>
            {approved.map((d) => (
              <label key={d.id} className="flex items-center gap-8 text-13">
                <input
                  type="checkbox"
                  checked={chosen.includes(d.id)}
                  onChange={(e) => setChosen((c) => (e.target.checked ? [...c, d.id] : c.filter((x) => x !== d.id)))}
                />
                {d.title}
              </label>
            ))}
          </fieldset>
        </div>
      )}
    </Dialog>
  );
}
