# Wasila (وسيلة) · v1.0.0.0

<img src="web/public/brand/wasila-logo.png" alt="Wasila" width="160" align="right" />

**Wasila is an investor CRM and Funding Room for founders raising in the US, the UK and Saudi
Arabia.** It keeps one searchable master list of investors, every round's pipeline, a
diligence document room, email outreach with the right attachments, the pitch deck and the
funding costs in one place, with Claude and an MCP server for agentic work. Nothing is ever
sent, shared or changed by an AI without a person's click.

Wasila is a white-label build for Applied Biosciences. It is open source under AGPL-3.0;
see [NOTICE](NOTICE) for the upstream project it builds on.

## What's in v1.0.0.0

- **US, UK and Saudi rounds.** Each round names its market and gets the right defaults:
  USD, GBP or SAR; SAFE, priced equity, convertible notes or the UK advance subscription
  agreement (ASA); SEIS / EIS / SEIS-then-EIS tax relief for UK rounds; a Sharia-compliant
  flag for Saudi rounds.
- **Funding Room.** The diligence repository: documents by category (pitch, corporate,
  financial, technical, clinical, regulatory, IP, cybersecurity, data protection,
  commercial, legal, SEIS/EIS), every version kept, review status (draft, in review,
  approved, archived), confidentiality, and US / UK / KSA checklists. **Share links** expose
  approved documents only, expire after 1 to 90 days, can be revoked, and count views
  without tracking people.
- **Master list.** Import leads from **CSV, Excel (.xlsx) or Word (.docx) tables**, or add
  them by hand, into one deduplicated list with country, phone and interest tags. Filter by
  market (UK, US, KSA, GCC), type, interests, "has email" and "not contacted". Save lists.
  Add **custom fields** and **AI columns**.
- **Claude.** Each workspace adds its own Anthropic API key (sealed on the server, only the
  last four characters are ever shown). **Ask Wasila** turns a plain-English question into
  master-list filters; Claude fills AI columns, drafts warm letters and investor updates,
  and suggests deck edits. Claude sees public investor profile data only.
- **Outreach.** Email investors from your own mailbox (Gmail, Outlook or any SMTP account)
  with approved Funding Room documents attached by hand. Every send is an `email` activity
  on the investor's timeline. **Campaigns** merge one email (`{first_name}`, `{firm}`, …)
  into a reviewed draft per investor; **follow-ups** list sent mail with no reply after N
  days; replies are logged in one click.
- **Warm intros.** Who in your network knows each investor, and how well; the best path
  shows on the investor's file and in the master list.
- **Deck editor.** Edit the text of a PowerPoint deck from the Funding Room, hide or reorder
  slides, and save a new version (layout, images and fonts stay as designed). Claude can
  suggest a version tailored to one investor.
- **Funding costs.** Use of funds, SEIS/EIS tranches and the 48-month income and cost plan,
  imported from your business-plan workbook and editable in place, with monthly burn,
  runway and the funding gap.
- **Everything from the base pipeline:** rounds with Triage, Board and Table views, investor
  files with an append-only timeline, follow-ups, meetings with a calendar feed, linked
  cards, CSV/JSON export, hard delete, a REST API under `/v1` and an MCP server at `/mcp`
  with **26 tools** (31 with investor research on). Agents can draft emails
  (`draft_outreach`) but cannot send them, and there are no delete tools.
- **Every page** shows the version (`Wasila v1.0.0.0`) and a light/dark switch, works on a
  phone and on a desktop, and is ready for Arabic: **Settings → Language** switches to
  right-to-left with IBM Plex Sans Arabic (translation comes in a later release).

## Brand

| Token | Hex | Use |
|---|---|---|
| Primary | `#0000FF` | The app bar, actions and links (light mode), the headline KPI tile |
| Light | `#B9D9EB` | Soft fills: table headers, tags, empty states, the bar's secondary text |
| Sky | `#00A1EB` | Actions in dark mode, meters, card rules, section labels (as `--sky-ink`) |
| Gold | `#E5C100` | The rule under the app bar, the active tab, page-title marks, the version badge |

Tokens live in `web/app/globals.css` (`--brand-*`, `--accent`). The logo and app icons are in
`web/public/brand/` and `web/app/` (`icon.png`, `apple-icon.png`, `favicon.ico`).

## Run it on your computer (production style)

One command builds the web app for production, runs the API without auto-reload, applies the
migrations and opens http://localhost:3600. Nothing is deployed anywhere.

```bash
# Local (Mac Terminal, in the repository folder)
./deploy/local/start.sh     # start, or rebuild and restart after a git pull
./deploy/local/stop.sh      # stop
```

It uses your local Postgres database `wasila_dev`, creates a local encryption key once in
`deploy/local/.env.local` (git-ignored), and writes logs to `deploy/local/logs/`. For safe
testing, sign-in links are shown on screen and outreach sends are recorded without emailing
anyone; `REAL_EMAIL=1 ./deploy/local/start.sh` uses the SMTP settings saved in Settings →
Email, and `MOCK_CLAUDE=1` swaps Claude for a local fake at no cost.

## Quick start (development)

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20.9+, and Postgres 16 or
17 on localhost with `wasila_dev` and `wasila_test` databases (extensions `citext` and
`pg_trgm`).

```bash
# Local (terminal 1, in backend/): API and MCP server on :8000
cd backend
uv sync
WASILA_DATABASE_URL=postgresql://localhost/wasila_dev uv run alembic upgrade head
export WASILA_SECRETS_KEK="$(uv run wasilactl secrets gen-kek)"   # seals the Claude key and mail password
WASILA_ENV=dev uv run uvicorn --factory wasila.main:create_app --reload

# Local (terminal 2, in web/): web app on :3000
cd web
npm ci
npm run dev
```

Open http://localhost:3000/signin and request a link; in development the "check your
inbox" page shows it. For fictional sample data: `uv run wasilactl seed-demo --email you@example.com`.

Settings you will want:

| Variable | What it does |
|---|---|
| `WASILA_SECRETS_KEK` | Required to save the Anthropic key and the SMTP password (`wasilactl secrets gen-kek`). |
| `WASILA_ANTHROPIC_BASE_URL` | Defaults to `https://api.anthropic.com`; point at a local fake for development. |
| `WASILA_OUTREACH_BACKEND` | `smtp` (default) sends through each workspace's mail settings; `memory` never sends (tests, demos). |

Checks:

```bash
cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy wasila
cd web && npm run lint && npm run typecheck && npm run test:unit && npm run build
```

## Connect an agent (MCP)

Create a key in Settings → Connect an agent (shown once), then for Claude Code:

```bash
claude mcp add --transport http wasila https://api.wasila.app/mcp \
  --header "Authorization: Bearer wsl_live_XXXX" \
  --header "X-Agent-Name: claude-code"
```

Then ask: "List the Funding Room checklist for KSA", "Find UK healthcare angels we have not
contacted", or "Draft a warm letter to Dana Whitfield with the one-pager attached". Drafts
appear in Wasila → Outreach for a person to review and send.

## Self-hosting

`deploy/` has the Dockerfiles, `docker-compose.yml` and a `Caddyfile`. See
[`docs/DEPLOY.md`](docs/DEPLOY.md). Set `WASILA_SECRETS_KEK` in production, back up the
database (Funding Room files are stored in it), and run `wasilactl housekeeping` daily.
v1.0.0.0 is **not deployed**; AWS deployment is a later step.

## Repository

| Path | What |
|---|---|
| `backend/` | FastAPI, SQLAlchemy 2 (async), Alembic, Postgres. REST under `/v1`, MCP at `/mcp`. Package `wasila`, CLI `wasilactl`. |
| `backend/alembic/versions/0010_wasila.py` | Every v1.0.0.0 table (Funding Room, outreach, Claude, lists, intros, costs). |
| `web/` | Next.js 15, React 19, Tailwind v4: the app, the public site and the docs. |
| `web/components/app/wasila/` | Funding Room, master list, outreach, deck editor, funding costs, settings. |
| `web/lib/i18n/` | Arabic / English scaffolding. |
| `deploy/` | Dockerfiles, compose, Caddy, backups. |
| `CHANGELOG.md` | Release notes. |

## Data and privacy

Demo, test and docs data is fictional. Real investor lists, letters, decks and workbooks are
imported at runtime and never committed to this repository. Workspaces are isolated (an id
from another workspace is always 404, enforced by `tests/isolation/` for every route and MCP
tool), secrets are sealed with AES-256-GCM envelope encryption, and there are no analytics
or third-party runtime requests.

## License

Wasila is free software under the GNU Affero General Public License, version 3
([LICENSE](LICENSE)). If you run a modified copy as a network service, you must offer its
source to its users. Copyright notices for the upstream work are in [NOTICE](NOTICE).
