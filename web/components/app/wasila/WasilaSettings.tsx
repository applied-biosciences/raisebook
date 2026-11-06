"use client";

import { useEffect, useState } from "react";

import { Button, Checkbox, Field, Input, LanguageSwitch, SectionLabel, Select, useToast } from "@/components/ui";
import { errorMessage } from "@/lib/api/client";
import { translate } from "@/lib/i18n";
import {
  deleteClaudeKey,
  getClaude,
  getMailSettings,
  putClaudeKey,
  putMailSettings,
  setClaudeModel,
  type ClaudeSettings as ClaudeState,
  type MailSettings,
} from "@/lib/api/wasila";
import { useWorkspace } from "@/lib/session";

/** Settings → Claude: the workspace's own Anthropic key (owner only) and the model. */
export function ClaudeSettings() {
  const { client, role } = useWorkspace();
  const toast = useToast();
  const isOwner = role === "owner";
  const [state, setState] = useState<ClaudeState | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClaude(client).then(setState).catch((e) => setError(errorMessage(e)));
  }, [client]);

  return (
    <div className="flex flex-col gap-20">
      <section>
        <SectionLabel>Claude</SectionLabel>
        <p className="m-0 max-w-[70ch] text-muted">
          Claude does agentic work in Wasila on your own Anthropic API key: Ask Wasila searches, AI columns, warm-letter and update drafts, and deck suggestions. It runs only when someone clicks, sees public investor profile data only (never emails, phone numbers, amounts or notes), and nothing it writes is sent or saved without your review.
        </p>
      </section>
      {state ? (
        <section className="flex flex-col gap-12 rounded-md border border-line bg-surface p-14">
          <p className="m-0">
            {state.ready ? (
              <>
                <span className="font-medium text-good-ink">Ready.</span> Key ending <span className="font-mono">{state.key_last4}</span>
                {state.key_set_at ? <span className="text-muted">, saved {new Date(state.key_set_at).toLocaleDateString()}</span> : null}.
              </>
            ) : (
              <span className="text-muted">No key yet.</span>
            )}
          </p>
          {isOwner ? (
            <form
              className="flex flex-col gap-8 sm:flex-row sm:items-end"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setError(null);
                try {
                  setState(await putClaudeKey(client, key.trim()));
                  setKey("");
                  toast.show("Key checked and saved. It will not be shown again.");
                } catch (err) {
                  setError(errorMessage(err));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Field label={state.ready ? "Replace the key" : "Anthropic API key"} error={error} className="flex-1" hint="From console.anthropic.com → API keys. Sealed on the server; only the last four characters are ever shown.">
                <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" />
              </Field>
              <Button type="submit" variant="primary" disabled={key.trim().length < 20} busy={busy ? "Checking…" : false}>
                Save key
              </Button>
            </form>
          ) : (
            <p className="m-0 text-13 text-muted">Only a workspace owner can add or remove the key.</p>
          )}
          <Field label="Model">
            <Select
              value={state.model}
              disabled={role === "viewer"}
              onChange={async (e) => {
                try {
                  setState(await setClaudeModel(client, e.target.value));
                } catch (err) {
                  toast.show(errorMessage(err));
                }
              }}
              className="max-w-[280px]"
            >
              {state.models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
          {isOwner && state.ready ? (
            <Button
              variant="danger-quiet"
              className="self-start"
              onClick={async () => {
                if (!window.confirm("Remove the Anthropic key? Claude features stop until a new key is saved.")) return;
                await deleteClaudeKey(client).catch((e) => toast.show(errorMessage(e)));
                setState(await getClaude(client));
              }}
            >
              Remove key
            </Button>
          ) : null}
        </section>
      ) : error ? (
        <p className="text-bad">{error}</p>
      ) : null}
    </div>
  );
}

/** Settings → Email: the mail account outreach is sent from (owner only to change). */
export function EmailSettings() {
  const { client, role } = useWorkspace();
  const toast = useToast();
  const isOwner = role === "owner";
  const [s, setS] = useState<MailSettings | null>(null);
  const [form, setForm] = useState({ host: "", port: "587", security: "starttls", username: "", password: "", from_email: "", from_name: "", reply_to: "", bcc_self: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMailSettings(client)
      .then((m) => {
        setS(m);
        if (m.configured)
          setForm((f) => ({
            ...f,
            host: m.host ?? "",
            port: String(m.port ?? 587),
            security: m.security ?? "starttls",
            username: m.username ?? "",
            from_email: m.from_email ?? "",
            from_name: m.from_name ?? "",
            reply_to: m.reply_to ?? "",
            bcc_self: m.bcc_self,
          }));
      })
      .catch((e) => setError(errorMessage(e)));
  }, [client]);

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="flex flex-col gap-20">
      <section>
        <SectionLabel>Email</SectionLabel>
        <p className="m-0 max-w-[70ch] text-muted">
          Outreach is sent from your own mailbox, so replies come back to you. Gmail and Google Workspace: smtp.gmail.com, port 587, STARTTLS, with an app password. Outlook / Microsoft 365: smtp.office365.com, port 587, STARTTLS. Emails are only sent when someone presses Send.
        </p>
      </section>
      {s ? (
        <form
          className="flex flex-col gap-12 rounded-md border border-line bg-surface p-14"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            try {
              const out = await putMailSettings(client, {
                host: form.host.trim(),
                port: Number(form.port) || 587,
                security: form.security,
                username: form.username.trim() || null,
                password: form.password || null,
                from_email: form.from_email.trim(),
                from_name: form.from_name.trim() || null,
                reply_to: form.reply_to.trim() || null,
                bcc_self: form.bcc_self,
              });
              setS(out);
              setForm((f) => ({ ...f, password: "" }));
              toast.show("Email settings saved.");
            } catch (err) {
              setError(errorMessage(err));
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="grid grid-cols-1 gap-12 sm:grid-cols-2">
            <Field label="SMTP server" error={error}>
              <Input value={form.host} onChange={set("host")} placeholder="smtp.gmail.com" disabled={!isOwner} />
            </Field>
            <div className="grid grid-cols-2 gap-8">
              <Field label="Port">
                <Input inputMode="numeric" value={form.port} onChange={set("port")} disabled={!isOwner} />
              </Field>
              <Field label="Security">
                <Select value={form.security} onChange={set("security")} disabled={!isOwner}>
                  <option value="starttls">STARTTLS</option>
                  <option value="ssl">SSL/TLS</option>
                  <option value="none">None</option>
                </Select>
              </Field>
            </div>
            <Field label="Username">
              <Input value={form.username} onChange={set("username")} autoComplete="off" disabled={!isOwner} />
            </Field>
            <Field label="Password or app password" hint={s.password_set ? "Saved. Leave empty to keep it." : "Sealed on the server and never shown again."}>
              <Input type="password" value={form.password} onChange={set("password")} autoComplete="new-password" disabled={!isOwner} />
            </Field>
            <Field label="From address">
              <Input type="email" value={form.from_email} onChange={set("from_email")} placeholder="founder@yourcompany.com" disabled={!isOwner} />
            </Field>
            <Field label="From name" optional>
              <Input value={form.from_name} onChange={set("from_name")} disabled={!isOwner} />
            </Field>
            <Field label="Reply-to" optional>
              <Input type="email" value={form.reply_to} onChange={set("reply_to")} disabled={!isOwner} />
            </Field>
          </div>
          <Checkbox label="Send me a copy (Bcc) of every email" checked={form.bcc_self} onChange={(e) => setForm((f) => ({ ...f, bcc_self: e.target.checked }))} disabled={!isOwner} />
          {isOwner ? (
            <Button type="submit" variant="primary" className="self-start" busy={busy ? "Saving…" : false}>
              Save email settings
            </Button>
          ) : (
            <p className="m-0 text-13 text-muted">Only a workspace owner can change the mail account.</p>
          )}
        </form>
      ) : error ? (
        <p className="text-bad">{error}</p>
      ) : null}
    </div>
  );
}

/** Settings → Language: English / العربية (bilingual scaffolding; Arabic text comes later). */
export function LanguageSettings() {
  return (
    <div className="flex flex-col gap-12">
      <SectionLabel>{translate("en", "settings.language.title")}</SectionLabel>
      <p className="m-0 max-w-[70ch] text-muted">{translate("en", "settings.language.help")}</p>
      <LanguageSwitch />
    </div>
  );
}
