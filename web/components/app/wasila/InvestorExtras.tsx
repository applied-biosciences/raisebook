"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button, Field, Input, SectionLabel, Select, useToast } from "@/components/ui";
import type { ApiClient } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/client";
import { addIntro, deleteIntro, listIntros, listMessages, type Intro, type OutreachMessage } from "@/lib/api/wasila";
import { cn } from "@/lib/cn";

/**
 * Wasila panels on the investor page: warm-intro connections (the best path first), the
 * investor's email history from Outreach, and a shortcut to email them.
 */
export function InvestorExtras({
  client,
  investorId,
  wsSlug,
  canWrite,
  country,
  phone,
}: {
  client: ApiClient;
  investorId: string;
  wsSlug: string;
  canWrite: boolean;
  country?: string | null;
  phone?: string | null;
}) {
  const toast = useToast();
  const [intros, setIntros] = useState<Intro[]>([]);
  const [mail, setMail] = useState<OutreachMessage[]>([]);
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("");
  const [strength, setStrength] = useState("2");

  const load = useCallback(async () => {
    const [i, m] = await Promise.all([listIntros(client, investorId), listMessages(client, { investor_id: investorId })]);
    setIntros(i.data);
    setMail(m.data);
  }, [client, investorId]);

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);

  return (
    <>
      {country || phone ? (
        <p className="m-0 text-13 text-muted">
          {country ? <span>{country}</span> : null}
          {country && phone ? " · " : null}
          {phone ? <a href={`tel:${phone.replace(/\s+/g, "")}`} className="text-fg">{phone}</a> : null}
        </p>
      ) : null}
      <section aria-label="Warm intros">
        <SectionLabel aside={intros.length ? `${intros.length}` : undefined}>Warm intros</SectionLabel>
        <ul className="m-0 flex list-none flex-col gap-6 p-0">
          {intros.map((c, i) => (
            <li key={c.id} className="flex items-start justify-between gap-8 text-13">
              <span>
                <span className={cn("font-medium", i === 0 && "text-good-ink")}>{c.connector_name}</span>{" "}
                <span className="text-muted">
                  {c.strength_label}
                  {c.relationship ? ` · ${c.relationship}` : ""}
                  {i === 0 ? " · best path" : ""}
                </span>
              </span>
              {canWrite ? (
                <button
                  type="button"
                  aria-label={`Remove ${c.connector_name}`}
                  className="border-0 bg-transparent p-0 text-xs text-muted hover:text-bad"
                  onClick={async () => {
                    await deleteIntro(client, c.id).catch((e) => toast.show(errorMessage(e)));
                    void load();
                  }}
                >
                  ✕
                </button>
              ) : null}
            </li>
          ))}
          {!intros.length ? <li className="text-13 text-muted">Who could introduce you? Add the people who know them.</li> : null}
        </ul>
        {canWrite ? (
          <form
            className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_110px_auto] sm:items-end"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!name.trim()) return;
              try {
                await addIntro(client, investorId, { connector_name: name.trim(), relationship: relationship.trim() || null, strength: Number(strength) });
                setName("");
                setRelationship("");
                void load();
              } catch (err) {
                toast.show(errorMessage(err));
              }
            }}
          >
            <Field label="Connector">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
            </Field>
            <Field label="How they know them" optional>
              <Input value={relationship} onChange={(e) => setRelationship(e.target.value)} placeholder="Former colleague" />
            </Field>
            <Field label="Strength">
              <Select value={strength} onChange={(e) => setStrength(e.target.value)}>
                <option value="3">Strong</option>
                <option value="2">Good</option>
                <option value="1">Weak</option>
              </Select>
            </Field>
            <Button type="submit" disabled={!name.trim()}>
              Add
            </Button>
          </form>
        ) : null}
      </section>
      <section aria-label="Emails" className="mt-16">
        <SectionLabel
          aside={
            canWrite ? (
              <Link href={`/w/${wsSlug}/outreach?investors=${investorId}`} className="text-accent">
                Email
              </Link>
            ) : undefined
          }
        >
          Emails
        </SectionLabel>
        <ul className="m-0 flex list-none flex-col gap-6 p-0 text-13">
          {mail.map((m) => (
            <li key={m.id}>
              <span className="font-medium">{m.subject}</span>{" "}
              <span className="text-muted">
                {m.status === "sent" ? `sent ${new Date(m.sent_at!).toLocaleDateString()}` : m.status}
                {m.attachments.length ? ` · ${m.attachments.map((a) => a.filename).join(", ")}` : ""}
                {m.replied_at ? " · replied" : ""}
              </span>
            </li>
          ))}
          {!mail.length ? <li className="text-muted">No emails yet.</li> : null}
        </ul>
      </section>
    </>
  );
}
