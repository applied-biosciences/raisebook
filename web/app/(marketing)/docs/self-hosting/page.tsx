import type { Metadata } from "next";

import {
  A,
  C,
  DocHeader,
  DocPagerFor,
  DocTable,
  H2,
  Note,
  P,
  Ul,
} from "@/components/marketing/docs/Prose";
import { REPO_URL, pageMeta } from "@/components/marketing/site";
import { CodeBlock } from "@/components/ui";

export const metadata: Metadata = pageMeta("/docs/self-hosting");

const INSTALL = [
  `git clone ${REPO_URL}.git`,
  "cd wasila",
  "cp deploy/.env.example deploy/.env",
  "# edit deploy/.env: hosts, POSTGRES_PASSWORD, WASILA_SESSION_SECRET, SMTP",
  "docker compose -f deploy/docker-compose.yml up -d --build",
].join("\n");

const SECRETS = [
  "# POSTGRES_PASSWORD",
  "openssl rand -base64 36 | tr -d '/+=' | cut -c1-40",
  "",
  "# WASILA_SESSION_SECRET (changing it later signs everyone out)",
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`,
].join("\n");

const UPDATE = [
  "cd wasila && git pull",
  "# build while the old containers keep serving, then swap",
  "docker compose -f deploy/docker-compose.yml build",
  "docker compose -f deploy/docker-compose.yml up -d",
  "# the migrate service applies database migrations before the API starts",
].join("\n");

const LOCAL = [
  "createdb wasila_dev",
  "psql wasila_dev -c 'CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS pg_trgm;'",
  "",
  "# terminal 1, from the repo root: API and MCP on :8000",
  "cd backend && uv sync",
  "WASILA_DATABASE_URL=postgresql://localhost/wasila_dev uv run alembic upgrade head",
  "WASILA_ENV=dev uv run uvicorn --factory wasila.main:create_app --reload",
  "",
  "# terminal 2, from the repo root: web on :3000",
  "cd web && npm ci && npm run dev",
  "",
  "# optional, from backend/: a sample workspace with fictional investors",
  "uv run wasilactl seed-demo --email you@example.com",
].join("\n");

export default function SelfHosting() {
  return (
    <>
      <DocHeader
        eyebrow="Docs · Operations"
        title="Self-hosting"
        lede={
          <p>
            Wasila is one repository and one Docker Compose file. If you would rather keep your
            investor list on a machine you control, run your own copy. It is the same software as
            wasila.app, with nothing held back.
          </p>
        }
      />

      <H2>What you need</H2>
      <Ul>
        <li>A Linux server with Docker and the Compose plugin. A small VM is enough to start.</li>
        <li>
          Two hostnames pointing at it, one for the web app and one for the API (for example{" "}
          <C>raise.example.com</C> and <C>api.raise.example.com</C>). Ports 80 and 443 open.
        </li>
        <li>
          An SMTP provider for sign-in links and invites. Any provider works; set up its SPF and
          DKIM records for your sending domain.
        </li>
      </Ul>

      <H2>Install</H2>
      <CodeBlock code={INSTALL} lang="shell" title="On the server" className="mb-14" />
      <P>Generate the two secrets:</P>
      <CodeBlock code={SECRETS} lang="shell" title="Secrets" className="mb-18" />
      <P>
        Caddy requests TLS certificates on its own once DNS points at the server. Open the web
        host, sign in with your email, and create your workspace.
      </P>

      <H2>What runs</H2>
      <DocTable
        caption="Compose services"
        head={["Service", "What it does"]}
        minWidth={420}
        rows={[
          ["postgres", "Postgres 17 with a named volume. Not exposed outside the compose network."],
          ["migrate", "Runs alembic upgrade head once, then exits. The API waits for it."],
          ["api", "FastAPI: the REST API under /v1 and the MCP server at /mcp."],
          ["worker", "A background job runner on the API image. No released feature uses it yet, so it idles."],
          ["web", "The Next.js app and this site."],
          ["caddy", "TLS and reverse proxy. The only service that publishes ports."],
        ]}
      />

      <H2>Configuration</H2>
      <P>
        Everything lives in <C>deploy/.env</C> (the template is <C>deploy/.env.example</C>). The
        main settings:
      </P>
      <DocTable
        caption="Main settings"
        head={["Variable", "What it sets"]}
        minWidth={520}
        rows={[
          ["WEB_HOST, API_HOST", "Your two hostnames. MCP is served at https://API_HOST/mcp."],
          ["POSTGRES_PASSWORD", "Database password. Required."],
          ["WASILA_SESSION_SECRET", "Signs session cookies and CSRF tokens. Required."],
          ["WASILA_SESSION_COOKIE_DOMAIN", "The parent domain both hosts share, so the session reaches the API."],
          ["WASILA_SMTP_HOST, _PORT, _USERNAME, _PASSWORD", "Your SMTP provider."],
          ["WASILA_EMAIL_FROM", 'Sender, e.g. "Wasila <login@raise.example.com>".'],
          ["WASILA_RATE_LIMIT_BACKEND", "postgres (default), memory or off."],
          ["WASILA_MAGIC_LINKS_PER_IP_HOUR", "Sign-in links per IP per hour (default 100). Raise it for an event on shared Wi-Fi."],
          ["WASILA_EMAIL_GLOBAL_PER_HOUR", "All outbound email per hour (default 500). Keep it under your email plan."],
          ["NEXT_PUBLIC_SPONSOR_URL", "The Support link. Empty hides it."],
        ]}
      />
      <Note>
        <p>
          The web image bakes in its public settings at build time. After changing a host or a{" "}
          <C>NEXT_PUBLIC_</C> value, rebuild with <C>up -d --build</C>.
        </p>
      </Note>

      <H2>Updating</H2>
      <CodeBlock code={UPDATE} lang="shell" title="Update" className="mb-18" />

      <H2>Backups</H2>
      <P>
        <C>deploy/backup.sh</C> dumps the database nightly and deletes dumps older than{" "}
        <C>BACKUP_RETENTION_DAYS</C> (14 by default). The hosted service promises that deleted
        data leaves backups within 14 days; keep the same limit if you make that promise to your
        team. Run it from cron, as the comment at the top of the script shows.
      </P>
      <P>
        Also run <C>docker compose -f deploy/docker-compose.yml exec api wasilactl housekeeping</C>{" "}
        once a day. It removes expired sign-in links, sessions and old rate-limit counters.
      </P>

      <H2>Run it locally</H2>
      <P>For development, run the API and the web app directly against a local Postgres 17:</P>
      <CodeBlock code={LOCAL} lang="shell" title="Development" className="mb-14" />
      <P>
        In development, the &ldquo;check your inbox&rdquo; page shows the sign-in link, so you do
        not need SMTP. Contributing? Read <A href={`${REPO_URL}/blob/main/CONTRIBUTING.md`}>CONTRIBUTING.md</A>.
      </P>

      <H2>The license</H2>
      <P>
        Wasila is AGPL-3.0. You can run, change and share it freely. If you change it and let
        other people use your version over a network, you must offer them its source code. Running an
        unmodified copy asks nothing more of you than keeping the license notices.
      </P>

      <DocPagerFor href="/docs/self-hosting" />
    </>
  );
}
