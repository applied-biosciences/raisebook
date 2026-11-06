"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Button,
  EmptyState,
  Input,
  PageHeader,
  SectionLabel,
  Select,
  Table,
  TableScroll,
  TBody,
  Td,
  Th,
  THead,
  Tr,
  useToast,
} from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import {
  createCost,
  deleteCost,
  importCosts,
  listCosts,
  updateCost,
  type CostKind,
  type CostLine,
  type CostSummary,
} from "@/lib/api/wasila";
import { useWorkspace } from "@/lib/session";

const YEARS = ["y1", "y2", "y3", "y4"] as const;
const TRANCHE_LABEL: Record<string, string> = { seis: "SEIS", eis: "EIS", equity: "Equity", grant: "Grant", other: "Other" };

function fmt(n: number, currency: string | null): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency ?? "GBP", maximumFractionDigits: 0 }).format(n);
  } catch {
    return n.toLocaleString();
  }
}

/** A number cell that saves on blur (Enter blurs). */
function MoneyCell({ value, onSave, disabled, label }: { value: number; onSave: (v: number) => Promise<void>; disabled: boolean; label: string }) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  return (
    <span className="inline-block w-[110px]">
    <Input
      aria-label={label}
      inputMode="numeric"
      value={v}
      disabled={disabled}
      onChange={(e) => setV(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
      onBlur={async () => {
        const n = Math.round(Number(v.replace(/[^0-9.-]/g, "")));
        if (Number.isFinite(n) && n !== value) await onSave(n);
        else setV(String(value));
      }}
      className="text-right font-mono"
      size="sm"
    />
    </span>
  );
}

/**
 * Funding costs (Wasila v1.0.0.0): the round's tranches (SEIS/EIS, equity, grants), use of
 * funds, and 48-month income and costs by group, editable in place, with burn, runway and
 * the funding gap. Import the business-plan workbook to fill it.
 */
export function FundingCosts() {
  const { client, role, workspace } = useWorkspace();
  const toast = useToast();
  const canWrite = role !== "viewer";
  const [lines, setLines] = useState<CostLine[] | null>(null);
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [importing, setImporting] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const [currency, setCurrency] = useState(workspace.default_currency ?? "GBP");

  const reload = useCallback(async () => {
    try {
      const r = await listCosts(client);
      setLines(r.data);
      setSummary(r.summary);
    } catch (err) {
      toast.show(errorMessage(err));
    }
  }, [client, toast]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const by = useMemo(() => {
    const out: Record<CostKind, CostLine[]> = { funding: [], use_of_funds: [], income: [], cost: [] };
    for (const l of lines ?? []) out[l.kind].push(l);
    return out;
  }, [lines]);
  const groups = useMemo(() => [...new Set(by.cost.map((l) => l.grp))], [by.cost]);
  const cur = summary?.currency ?? currency;

  const save = async (id: string, patch: Partial<CostLine>) => {
    try {
      await updateCost(client, id, patch);
      void reload();
    } catch (err) {
      toast.show(errorMessage(err));
    }
  };

  const add = async (kind: CostKind, grp: string) => {
    const name = window.prompt("Name of the new line");
    if (!name?.trim()) return;
    try {
      await createCost(client, { kind, grp, name: name.trim(), currency: cur });
      void reload();
    } catch (err) {
      toast.show(errorMessage(err));
    }
  };

  const remove = async (l: CostLine) => {
    if (!window.confirm(`Delete “${l.name}”?`)) return;
    await deleteCost(client, l.id).catch((e) => toast.show(errorMessage(e)));
    void reload();
  };

  return (
    <>
      <PageHeader
        title="Funding costs"
        aside={summary ? `${fmt(summary.funding_total, cur)} funding · ${fmt(summary.total_costs_48m, cur)} costs over 48 months` : undefined}
        subline="Use of funds, SEIS/EIS tranches and the 48-month cost plan. Investor updates quote these KPIs."
        actions={
          canWrite ? (
            <>
              <span className="w-[90px]">
              <Select aria-label="Currency" size="md" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {["GBP", "USD", "SAR", "EUR", "AED"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
              </span>
              <input
                ref={file}
                type="file"
                accept=".xlsx"
                className="sr-only"
                aria-label="Import a workbook"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  if (lines?.length && !window.confirm("Importing replaces every current line. Continue?")) return;
                  setImporting(true);
                  try {
                    const r = await importCosts(client, f, currency);
                    setLines(r.data);
                    setSummary(r.summary);
                    toast.show(`Imported ${r.data.length} lines from ${f.name}.`);
                  } catch (err) {
                    toast.show(errorMessage(err));
                  } finally {
                    setImporting(false);
                    if (file.current) file.current.value = "";
                  }
                }}
              />
              <Button variant="primary" busy={importing ? "Importing…" : false} onClick={() => file.current?.click()}>
                Import workbook
              </Button>
            </>
          ) : null
        }
      />

      {summary ? (
        <dl className="mb-20 grid grid-cols-2 gap-10 lg:grid-cols-4">
          {[
            ["Funding", fmt(summary.funding_total, cur)],
            ["Monthly burn (year 1)", fmt(summary.kpis.monthly_burn_y1, cur)],
            [
              "Runway",
              summary.kpis.runway_beyond_48m ? "Beyond 48 months" : summary.kpis.runway_months != null ? `${summary.kpis.runway_months} months` : "—",
            ],
            ["Funding gap (48 months)", summary.kpis.funding_gap_48m ? fmt(summary.kpis.funding_gap_48m, cur) : "None"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-md border border-line bg-surface p-12">
              <dt className="t-micro text-muted">{k}</dt>
              <dd className="m-0 mt-4 font-display text-2xl font-bold">{v}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {lines !== null && !lines.length ? (
        <EmptyState title="No costs yet" actions={canWrite ? <Button variant="primary" onClick={() => file.current?.click()}>Import workbook</Button> : null}>
          Import your business-plan workbook (a “Use of funds” sheet and a “Summary” P&amp;L with Year 1 to Year 4), or add lines by hand.
        </EmptyState>
      ) : null}

      <div className="grid grid-cols-1 gap-20 lg:grid-cols-2">
        <section>
          <SectionLabel aside={summary ? fmt(summary.use_of_funds_total, cur) : undefined}>Use of funds</SectionLabel>
          <ul className="m-0 flex list-none flex-col gap-8 p-0">
            {(summary?.use_of_funds ?? []).map((u) => {
              const line = by.use_of_funds.find((l) => l.id === u.id);
              return (
                <li key={u.id} className="rounded-md border border-line bg-surface p-10">
                  <div className="flex flex-wrap items-center justify-between gap-8">
                    <span className="font-medium">{u.name}</span>
                    <span className="flex items-center gap-8">
                      <span className="t-micro text-muted">{u.pct}%</span>
                      {line ? <MoneyCell label={`${u.name} amount`} value={line.amount} disabled={!canWrite} onSave={(v) => save(line.id, { amount: v })} /> : null}
                      {canWrite && line ? (
                        <button type="button" aria-label={`Delete ${u.name}`} className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad" onClick={() => void remove(line)}>
                          ✕
                        </button>
                      ) : null}
                    </span>
                  </div>
                  <div className="mt-6 h-6 overflow-hidden rounded-pill bg-sunk" aria-hidden>
                    <div className="h-full rounded-pill bg-brand-sky" style={{ width: `${Math.min(100, u.pct)}%` }} />
                  </div>
                  {u.objective ? <p className="m-0 mt-6 text-13 text-muted">{u.objective}</p> : null}
                </li>
              );
            })}
          </ul>
          {canWrite ? (
            <Button size="sm" className="mt-8" onClick={() => void add("use_of_funds", "Use of funds")}>
              Add use of funds
            </Button>
          ) : null}
          {summary && summary.unallocated !== 0 ? (
            <p className="mt-8 text-13 text-warm-ink">{fmt(Math.abs(summary.unallocated), cur)} {summary.unallocated > 0 ? "not yet allocated" : "over the funding"}.</p>
          ) : null}
        </section>

        <section>
          <SectionLabel>Funding tranches</SectionLabel>
          <ul className="m-0 flex list-none flex-col gap-8 p-0">
            {by.funding.map((l) => (
              <li key={l.id} className="flex flex-wrap items-center justify-between gap-8 rounded-md border border-line bg-surface p-10">
                <span>
                  <span className="font-medium">{l.name}</span>{" "}
                  {l.tranche ? <span className="rounded-pill bg-brand-gold/25 px-6 py-1 text-xs text-brand-gold-ink">{TRANCHE_LABEL[l.tranche]}</span> : null}
                </span>
                <span className="flex items-center gap-8">
                  <MoneyCell label={`${l.name} amount`} value={l.amount} disabled={!canWrite} onSave={(v) => save(l.id, { amount: v })} />
                  {canWrite ? (
                    <button type="button" aria-label={`Delete ${l.name}`} className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad" onClick={() => void remove(l)}>
                      ✕
                    </button>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
          {canWrite ? (
            <Button size="sm" className="mt-8" onClick={() => void add("funding", "Round")}>
              Add tranche
            </Button>
          ) : null}
        </section>
      </div>

      {by.income.length || by.cost.length ? (
        <section className="mt-24">
          <SectionLabel>48-month plan</SectionLabel>
          <TableScroll>
            <Table>
              <THead>
                <tr>
                  <Th>Line</Th>
                  {YEARS.map((y, i) => (
                    <Th key={y} align="right">
                      Year {i + 1}
                    </Th>
                  ))}
                  <Th align="right">48 months</Th>
                </tr>
              </THead>
              <TBody>
                {[["Income", by.income] as const, ...groups.map((g) => [g, by.cost.filter((l) => l.grp === g)] as const)].map(([g, rows]) => (
                  <PlanGroup key={g} title={g} rows={rows} cur={cur} canWrite={canWrite} onSave={save} onRemove={remove} onAdd={() => void add(g === "Income" ? "income" : "cost", g)} />
                ))}
                {summary ? (
                  <Tr>
                    <Td className="font-semibold">Net (income − costs)</Td>
                    {YEARS.map((y) => (
                      <Td key={y} variant="num" className={summary.net[y] < 0 ? "text-bad" : "text-good-ink"}>
                        {fmt(summary.net[y], cur)}
                      </Td>
                    ))}
                    <Td variant="num" className="font-semibold">
                      {fmt(YEARS.reduce((a, y) => a + summary.net[y], 0), cur)}
                    </Td>
                  </Tr>
                ) : null}
              </TBody>
            </Table>
          </TableScroll>
        </section>
      ) : null}
    </>
  );
}

function PlanGroup({
  title,
  rows,
  cur,
  canWrite,
  onSave,
  onRemove,
  onAdd,
}: {
  title: string;
  rows: readonly CostLine[];
  cur: string | null;
  canWrite: boolean;
  onSave: (id: string, patch: Partial<CostLine>) => Promise<void>;
  onRemove: (l: CostLine) => Promise<void>;
  onAdd: () => void;
}) {
  const total = YEARS.map((y) => rows.reduce((a, r) => a + r[y], 0));
  return (
    <>
      <Tr>
        <Td className="bg-sunk font-semibold" colSpan={6}>
          <span className="flex items-center justify-between gap-8">
            {title}
            {canWrite ? (
              <button type="button" className="border-0 bg-transparent p-0 text-xs text-accent" onClick={onAdd}>
                + line
              </button>
            ) : null}
          </span>
        </Td>
      </Tr>
      {rows.map((r) => (
        <Tr key={r.id}>
          <Td>
            <span className="flex items-center gap-6">
              {r.name}
              {canWrite ? (
                <button type="button" aria-label={`Delete ${r.name}`} className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad" onClick={() => void onRemove(r)}>
                  ✕
                </button>
              ) : null}
            </span>
          </Td>
          {YEARS.map((y, i) => (
            <Td key={y} variant="num">
              <MoneyCell label={`${r.name} year ${i + 1}`} value={r[y]} disabled={!canWrite} onSave={(v) => onSave(r.id, { [y]: v })} />
            </Td>
          ))}
          <Td variant="num">{fmt(YEARS.reduce((a, y) => a + r[y], 0), cur)}</Td>
        </Tr>
      ))}
      <Tr>
        <Td className="text-muted">Total {title.toLowerCase()}</Td>
        {total.map((t, i) => (
          <Td key={i} variant="num" className="text-muted">
            {fmt(t, cur)}
          </Td>
        ))}
        <Td variant="num" className="text-muted">
          {fmt(total.reduce((a, b) => a + b, 0), cur)}
        </Td>
      </Tr>
    </>
  );
}
