"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Button,
  Chip,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  SectionLabel,
  Segmented,
  Select,
  Table,
  TableScroll,
  TBody,
  Td,
  Th,
  THead,
  Textarea,
  Tr,
  useToast,
} from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import { INVESTOR_TYPE_LABEL } from "@/lib/api/types";
import {
  askWasila,
  createField,
  deleteField,
  deleteSavedList,
  fillAiColumn,
  listFields,
  listSavedLists,
  openSavedList,
  saveList,
  searchMasterList,
  type Filters,
  type InvestorField,
  type SavedList,
  type SearchResult,
} from "@/lib/api/wasila";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/lib/session";

type Market = "all" | "uk" | "us" | "ksa" | "gcc";
const MARKET_COUNTRIES: Record<Market, string[]> = {
  all: [],
  uk: ["United Kingdom"],
  us: ["United States"],
  ksa: ["Saudi Arabia"],
  gcc: ["GCC"],
};

/**
 * The master list (Wasila v1.0.0.0): every investor in the workspace, filtered by market,
 * type, interest and contact state, or by an "Ask Wasila" question that Claude turns into the
 * same filters. Results can be saved as lists, sent to a campaign, and enriched with custom
 * fields and Claude AI columns.
 */
export function MasterList() {
  const { client, role, workspace } = useWorkspace();
  const toast = useToast();
  const canWrite = role !== "viewer";
  const base = `/w/${workspace.slug}`;
  const [market, setMarket] = useState<Market>("all");
  const [type, setType] = useState("");
  const [tag, setTag] = useState("");
  const [q, setQ] = useState("");
  const [hasEmail, setHasEmail] = useState(false);
  const [notContacted, setNotContacted] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [fields, setFields] = useState<InvestorField[]>([]);
  const [lists, setLists] = useState<SavedList[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [fieldOpen, setFieldOpen] = useState(false);
  const [filling, setFilling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filters: Filters = useMemo(
    () => ({
      q: q.trim() || undefined,
      countries: MARKET_COUNTRIES[market],
      types: type ? [type] : [],
      tags_any: tag.trim() ? tag.split(/[,;]/).map((t) => t.trim()).filter(Boolean) : [],
      has_email: hasEmail ? true : null,
      not_contacted: notContacted ? true : null,
    }),
    [q, market, type, tag, hasEmail, notContacted],
  );

  const run = useCallback(async () => {
    try {
      setResult(await searchMasterList(client, { ...filters, limit: 500 }));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [client, filters]);

  useEffect(() => {
    const t = setTimeout(() => void run(), 200);
    return () => clearTimeout(t);
  }, [run]);

  const loadMeta = useCallback(async () => {
    const [f, l] = await Promise.all([listFields(client), listSavedLists(client)]);
    setFields(f.data);
    setLists(l.data);
  }, [client]);

  useEffect(() => {
    void loadMeta().catch(() => undefined);
  }, [loadMeta]);

  const ask = async () => {
    if (question.trim().length < 3) return;
    setAsking(true);
    setError(null);
    try {
      setResult(await askWasila(client, question.trim()));
      setSelected([]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  const rows = result?.data ?? [];
  const allOn = rows.length > 0 && selected.length === rows.length;

  return (
    <>
      <PageHeader
        title="Master list"
        aside={result ? `${result.total} investors` : undefined}
        subline="Every lead in one searchable list. Import CSV, Excel or Word tables, or ask Wasila in plain words."
        actions={
          canWrite ? (
            <>
              <Link href={`${base}/import`} className="inline-flex h-32 items-center rounded-sm border border-line bg-surface px-12 font-medium touch:min-h-44">
                Import leads
              </Link>
              <Button onClick={() => setFieldOpen(true)}>Add column</Button>
            </>
          ) : null
        }
      />

      <form
        className="mb-14 flex flex-col gap-8 rounded-md border border-line bg-surface p-12 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <Field label="Ask Wasila (Claude)" className="flex-1" hint="Claude sees only your question, never investor data, and turns it into filters.">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Saudi healthcare angels with an email we haven't contacted"
          />
        </Field>
        <Button type="submit" variant="primary" busy={asking ? "Asking…" : false} disabled={question.trim().length < 3}>
          Ask
        </Button>
      </form>
      {result?.explanation ? (
        <p className="mb-10 text-13 text-muted">
          <span className="text-agent">Claude:</span> {result.explanation}{" "}
          <button type="button" className="border-0 bg-transparent p-0 text-accent underline" onClick={() => void run()}>
            Clear
          </button>
        </p>
      ) : null}

      <div className="mb-12 flex flex-wrap items-center gap-8">
        <Segmented
          label="Market"
          value={market}
          onChange={setMarket}
          options={[
            { value: "all", label: "All" },
            { value: "uk", label: "UK" },
            { value: "us", label: "US" },
            { value: "ksa", label: "KSA" },
            { value: "gcc", label: "GCC" },
          ]}
        />
        <Select aria-label="Investor type" value={type} onChange={(e) => setType(e.target.value)} className="w-[150px]">
          <option value="">All types</option>
          {Object.entries(INVESTOR_TYPE_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Input aria-label="Interest or tag" placeholder="Healthcare, AI…" value={tag} onChange={(e) => setTag(e.target.value)} className="w-[160px]" />
        <Input type="search" aria-label="Search names and firms" placeholder="Name, firm, notes" value={q} onChange={(e) => setQ(e.target.value)} className="w-[180px]" />
        <label className="flex items-center gap-6 text-13">
          <input type="checkbox" checked={hasEmail} onChange={(e) => setHasEmail(e.target.checked)} /> Has email
        </label>
        <label className="flex items-center gap-6 text-13">
          <input type="checkbox" checked={notContacted} onChange={(e) => setNotContacted(e.target.checked)} /> Not contacted
        </label>
      </div>
      {error ? <p className="mb-10 text-bad">{error}</p> : null}

      <div className="grid grid-cols-1 gap-20 xl:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          {selected.length ? (
            <div className="mb-8 flex flex-wrap items-center gap-8 rounded-md bg-accent-soft px-12 py-8 text-13">
              <span className="font-medium">{selected.length} selected</span>
              {canWrite ? (
                <>
                  <Button size="sm" onClick={() => setSaving(true)}>
                    Save as list
                  </Button>
                  <Link
                    href={`${base}/outreach?investors=${selected.join(",")}`}
                    className="inline-flex h-28 items-center rounded-sm border border-line bg-surface px-10 text-sm font-medium"
                  >
                    Email them
                  </Link>
                  {fields
                    .filter((f) => f.kind === "ai")
                    .map((f) => (
                      <Button
                        key={f.id}
                        size="sm"
                        busy={filling === f.id ? "Claude is filling…" : false}
                        onClick={async () => {
                          setFilling(f.id);
                          try {
                            const out = await fillAiColumn(client, f.id, selected.slice(0, 50));
                            toast.show(`Claude filled ${Object.keys(out.filled).length} (${out.skipped.length} already had a value).`);
                            void run();
                          } catch (err) {
                            toast.show(errorMessage(err));
                          } finally {
                            setFilling(null);
                          }
                        }}
                      >
                        Fill “{f.label}”
                      </Button>
                    ))}
                </>
              ) : null}
            </div>
          ) : null}
          {result && !rows.length ? (
            <EmptyState
              title="No investors match"
              actions={canWrite ? <Link href={`${base}/import`} className="text-accent underline">Import a lead list</Link> : null}
            >
              Change the filters, or import a CSV, Excel or Word table of investors.
            </EmptyState>
          ) : (
            <TableScroll>
              <Table>
                <THead>
                  <tr>
                    <Th className="w-32">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={allOn}
                        onChange={(e) => setSelected(e.target.checked ? rows.map((r) => r.id) : [])}
                      />
                    </Th>
                    <Th>Name</Th>
                    <Th>Firm and role</Th>
                    <Th>Country</Th>
                    <Th>Interests</Th>
                    <Th>Warm intro</Th>
                    {fields.map((f) => (
                      <Th key={f.id}>
                        <span className={f.kind === "ai" ? "text-agent" : undefined}>{f.label}</span>
                      </Th>
                    ))}
                  </tr>
                </THead>
                <TBody>
                  {rows.map((r) => {
                    const intro = result?.intros[r.id];
                    return (
                      <Tr key={r.id} selected={selected.includes(r.id)}>
                        <Td>
                          <input
                            type="checkbox"
                            aria-label={`Select ${r.name}`}
                            checked={selected.includes(r.id)}
                            onChange={(e) => setSelected((s) => (e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id)))}
                          />
                        </Td>
                        <Td>
                          <Link href={`${base}/investors/${r.id}`} className="font-medium hover:underline">
                            {r.name}
                          </Link>
                          {!r.email ? <span className="block text-2xs text-faint">no email</span> : null}
                        </Td>
                        <Td>
                          {r.firm ?? "—"}
                          {r.title ? <span className="block text-sm text-muted">{r.title}</span> : null}
                        </Td>
                        <Td>{r.country ?? r.location ?? "—"}</Td>
                        <Td>
                          <span className="flex max-w-[240px] flex-wrap gap-4">
                            {(r.tags ?? []).slice(0, 4).map((t) => (
                              <Chip key={t} tone="tag">
                                {t}
                              </Chip>
                            ))}
                          </span>
                        </Td>
                        <Td>
                          {intro ? (
                            <span className={cn(intro.strength === 3 ? "text-good-ink" : "text-fg")}>
                              {intro.connector_name}
                            </span>
                          ) : (
                            <span className="text-faint">—</span>
                          )}
                        </Td>
                        {fields.map((f) => (
                          <Td key={f.id}>{String(r.custom?.[f.key] ?? "")}</Td>
                        ))}
                      </Tr>
                    );
                  })}
                </TBody>
              </Table>
            </TableScroll>
          )}
        </div>

        <aside className="flex flex-col gap-16">
          <section>
            <SectionLabel>Saved lists</SectionLabel>
            {!lists.length ? <p className="m-0 text-13 text-muted">Select investors and save them, or save an Ask Wasila search.</p> : null}
            <ul className="m-0 flex list-none flex-col gap-4 p-0">
              {lists.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-6">
                  <button
                    type="button"
                    className="min-w-0 truncate border-0 bg-transparent p-0 text-left text-13 text-accent hover:underline"
                    onClick={async () => {
                      try {
                        setResult(await openSavedList(client, l.id));
                        setSelected([]);
                      } catch (err) {
                        toast.show(errorMessage(err));
                      }
                    }}
                  >
                    {l.name}
                  </button>
                  {canWrite ? (
                    <button
                      type="button"
                      aria-label={`Delete list ${l.name}`}
                      className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad"
                      onClick={async () => {
                        await deleteSavedList(client, l.id).catch((e) => toast.show(errorMessage(e)));
                        void loadMeta();
                      }}
                    >
                      ✕
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
            {canWrite && result?.explanation ? (
              <Button size="sm" className="mt-8" onClick={() => setSaving(true)}>
                Save this search
              </Button>
            ) : null}
          </section>
          <section>
            <SectionLabel>Columns</SectionLabel>
            <ul className="m-0 flex list-none flex-col gap-4 p-0 text-13">
              {fields.map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-6">
                  <span className={f.kind === "ai" ? "text-agent" : undefined}>
                    {f.label} <span className="text-2xs text-muted">{f.kind === "ai" ? "AI" : f.kind}</span>
                  </span>
                  {canWrite ? (
                    <button
                      type="button"
                      aria-label={`Delete column ${f.label}`}
                      className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad"
                      onClick={async () => {
                        if (!window.confirm(`Delete the column “${f.label}” and its values?`)) return;
                        await deleteField(client, f.id).catch((e) => toast.show(errorMessage(e)));
                        void loadMeta();
                        void run();
                      }}
                    >
                      ✕
                    </button>
                  ) : null}
                </li>
              ))}
              {!fields.length ? <li className="text-muted">Add your own columns, or an AI column Claude fills.</li> : null}
            </ul>
          </section>
        </aside>
      </div>

      <SaveListDialog
        open={saving}
        onClose={() => setSaving(false)}
        onSave={async (name) => {
          await saveList(client, {
            name,
            question: result?.explanation ?? null,
            ...(selected.length ? { investor_ids: selected } : { filters: result?.filters ?? filters }),
          });
          toast.show(`List “${name}” saved.`);
          void loadMeta();
        }}
      />
      <FieldDialog
        open={fieldOpen}
        onClose={() => setFieldOpen(false)}
        onCreate={async (body) => {
          await createField(client, body);
          void loadMeta();
        }}
      />
    </>
  );
}

function SaveListDialog({ open, onClose, onSave }: { open: boolean; onClose: () => void; onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Save as a list"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await onSave(name.trim());
          setName("");
          onClose();
        } catch (err) {
          setError(errorMessage(err));
        }
      }}
      actions={
        <>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!name.trim()}>
            Save list
          </Button>
        </>
      }
    >
      <Field label="Name" error={error}>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="KSA healthcare angels" />
      </Field>
    </Dialog>
  );
}

function FieldDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (body: { label: string; kind: InvestorField["kind"]; options?: string[]; prompt?: string | null }) => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<InvestorField["kind"]>("text");
  const [options, setOptions] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add a column"
      description="Your own field on every investor, or an AI column that Claude fills on request."
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await onCreate({
            label: label.trim(),
            kind,
            options: kind === "select" ? options.split(",").map((o) => o.trim()).filter(Boolean) : [],
            prompt: kind === "ai" ? prompt.trim() : null,
          });
          setLabel("");
          setPrompt("");
          onClose();
        } catch (err) {
          setError(errorMessage(err));
        }
      }}
      actions={
        <>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!label.trim() || (kind === "ai" && !prompt.trim())}>
            Add column
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-12">
        <Field label="Column name" error={error}>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Fit for Sakinah" />
        </Field>
        <Field label="Kind">
          <Select value={kind} onChange={(e) => setKind(e.target.value as InvestorField["kind"])}>
            <option value="text">Text</option>
            <option value="number">Number</option>
            <option value="yes_no">Yes / no</option>
            <option value="select">Choice</option>
            <option value="url">Link</option>
            <option value="ai">AI column (Claude fills it)</option>
          </Select>
        </Field>
        {kind === "select" ? (
          <Field label="Choices" hint="Separate with commas.">
            <Input value={options} onChange={(e) => setOptions(e.target.value)} placeholder="Lead, Follow, Pass" />
          </Field>
        ) : null}
        {kind === "ai" ? (
          <Field label="Question for Claude" hint="Answered per investor from public profile data (name, firm, role, country, tags).">
            <Textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Would they back an Arabic-first mental health AI company? Say why in a few words." />
          </Field>
        ) : null}
      </div>
    </Dialog>
  );
}
