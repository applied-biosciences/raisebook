# Wasila: working notes for agents

Wasila (v1.0.0.0) is Applied Biosciences' white-label investor CRM and Funding Room for US,
UK and Saudi raises, built on an AGPL-3.0 upstream (see NOTICE), with a first-class MCP
server and Claude integration. Spec: `docs/SPEC.md`. Its **§0 decisions block overrides the
rest**: the package is `wasila`, the env prefix is `WASILA_*`, the CLI is `wasilactl`, keys
are `wsl_live_` / `wsl_test_`, and the scopes are `wasila:read|write|admin`. Design rules:
`design/SYSTEM.md` (binding; Wasila palette in `web/app/globals.css`). Who edits what:
`docs/OWNERSHIP.md`. Nothing is deployed yet: never deploy, never touch DNS, and never push
to `main` (work on a branch). The v1.0.0.0 features (Funding Room, master list, Claude,
outreach, decks, funding costs) are summarised in CHANGELOG.md; their isolation cases live in
`tests/isolation/wasila_cases.py`.

## Wasila v1.0.0.0 invariants (keep them)
- Email is sent only by an explicit send of one reviewed draft (`services/outreach.send`);
  there is no MCP send tool. Attachments are approved Funding Room documents only.
- Claude runs only on the workspace's own key (`workspace_secrets`, kind `anthropic`) and on
  request; it sees `claude.public_profile` fields only, never emails, phones, amounts or notes.
- Share links expose approved documents only; only token hashes are stored.
- Real investor data never goes into the repository (fixtures stay fictional).
- The version shown on every page is `web/lib/version.ts`; keep it in step with
  `backend/wasila/__init__.py` and CHANGELOG.md.

## Layout
- `backend/` is the Python 3.12 project, managed by uv. The package is `backend/wasila/`
  (import as `from wasila.x import y`).
- `backend/alembic/versions/0001_init.py` holds the whole SPEC §3 schema: composite
  `(workspace_id, id)` FKs, CHECKs, partial unique indexes, and the `activities` append-only
  trigger.
- `web/` is Next.js 15 + React 19 + Tailwind v4. Tokens only, no component library.
- `deploy/` has the Dockerfiles, `docker-compose.yml` and `Caddyfile` (web at wasila.app,
  API and `/mcp` at api.wasila.app).
- `prototype.html` is the original single-file prototype and the design reference. It is
  read-only.
- `~/projects/smmist` is the sister project and a **read-only** reference. Copy and adapt its
  patterns (auth/session, api_keys, principal, mcp/server + auth, the tests/conftest
  harness); never import from it.

## Run (backend, always from `backend/`)
```bash
cd backend
uv sync
uv run pytest -q                                   # needs local Postgres 17 (below)
uv run ruff check . && uv run ruff format --check .
uv run mypy wasila
WASILA_DATABASE_URL=postgresql://localhost/wasila_dev uv run alembic upgrade head
WASILA_ENV=dev uv run uvicorn --factory wasila.main:create_app --reload   # API + /mcp on :8000
uv run wasilactl worker    # background jobs (research), beside uvicorn; --once drains and exits
uv run wasilactl --help    # workspace | apikey | seed-demo --email | housekeeping | worker | secrets
```
Research needs `WASILA_RESEARCH_ENABLED=true` and `WASILA_SECRETS_KEK` (`uv run wasilactl secrets gen-kek`); without it the app
works and research reports `research_unavailable`. Production setup (the `worker` compose
service, the KEK, rotation, removal requests) is in `docs/DEPLOY.md` under "AI research". Never point dev at real OpenRouter money:
run `uv run python scripts/mock_openrouter.py --port 8787` and set
`WASILA_OPENROUTER_BASE_URL=http://localhost:8787/api/v1` for both uvicorn and the worker
(its canned answers are about the sample's fictional Dana Whitfield).
Sign in locally: run the API with `WASILA_ENV=dev`, request a link at `/signin`, and the
"check your email" page shows the `dev_link`. `uv run wasilactl seed-demo --email you@example.com`
creates the fictional sandbox workspace "Kestrel Robotics (sample)".

## Run (web)
```bash
cd web
npm ci
npm run dev                                        # :3000, needs the API on :8000
npm run lint && npm run typecheck && npm run build
```

## End-to-end run (integrator recipe, no Docker)
```bash
# API on :8100 (from backend/); the web origin on :3100 is WASILA_APP_URL, so it is allowed.
WASILA_ENV=dev WASILA_PUBLIC_BASE_URL=http://localhost:8100 \
  WASILA_APP_URL=http://localhost:3100 WASILA_SESSION_COOKIE_SECURE=false \
  uv run uvicorn --factory wasila.main:create_app --port 8100
# Web production build on :3100 (from web/); NEXT_PUBLIC_* are baked in at build time.
NEXT_PUBLIC_API_URL=http://localhost:8100 NEXT_PUBLIC_SITE_URL=http://localhost:3100 npm run build
npx next start -p 3100
```
`WASILA_CORS_ORIGINS` takes a comma-separated list or a JSON list. Final screenshots of every
route (light, dark, 390px) are in `design/screens/final/`. Signing in by script: request a link
(`POST /v1/auth/magic-link`), open the `dev_link` and press **Continue**: the verify page never
spends the token on load. Use a throwaway database (for example `wasila_shots`) and
`WASILA_RATE_LIMIT_BACKEND=off` for screenshot runs.

## Tests
- Local Homebrew **Postgres 17**: databases `wasila_dev` and `wasila_test` exist, with
  `citext` and `pg_trgm`. Override the test DB with `WASILA_TEST_DATABASE_URL`. There is no
  Docker and no testcontainers.
- Each pytest session creates its own schema `t_<pid>_<hex>`, runs `alembic upgrade head` into
  it, and drops it at exit (`WASILA_TEST_KEEP_SCHEMA=1` keeps it). Concurrent runs are safe.
- The `db` fixture rolls back an outer transaction per test, and service commits release a
  savepoint. Clients: `client` (anonymous), `session_client(user, ws)` (cookie + CSRF),
  `key_client(key)`, and `mcp_call(key, tool, args)` (the real `/mcp` route). Factories are in
  `tests/factories.py`. Emails land in the `outbox` fixture.
- **Workspace isolation is the critical invariant.** `tests/isolation/` enumerates every
  `/v1` route and every MCP tool and checks that workspace A can neither read nor change B. A
  new route or tool that the isolation suite does not cover fails the build.
- No network calls in tests. Use an injectable clock everywhere (`core/clock.get_now`, MCP
  `Clock`). Never call `datetime.now()` deep inside logic.
- OpenRouter is never reached from tests: an autouse guard installs a refusing transport (an
  unmocked request fails the test). Use the `openrouter_mock` fixture
  (`tests/research/openrouter_mock.py`, fictional `FAKE_KEY`, recorded models list in
  `tests/research/fixtures/`). conftest sets a throwaway `WASILA_SECRETS_KEK` per run.
- Queue and worker races use `committing_sessionmaker` with a test-only job kind
  (`test.<hex>`) and delete their rows afterwards.

## Conventions and contracts
- Every workspace-scoped service function takes `ws: WorkspaceContext` (from the principal)
  and filters by `ws.workspace_id`. Never take a workspace id from request input. An id from
  another workspace is **404**, never 403.
- Every write takes an `actor: Actor` and writes its activity in the same transaction
  (`services/activities.log`). No-ops write nothing. Agents (API key or MCP) are recorded with
  `actor_label` from `X-Agent-Name` (else the key's `agent_name`, else its name) and
  `agent_model` from `X-Agent-Model`.
- Errors: raise `wasila.core.errors.APIError` subclasses. The envelope is
  `{"error": {code, message, details, request_id}}`. Messages say what to do next.
- MCP tools call the same services as REST and never re-implement rules. Reference resolution
  (investor by id, email, LinkedIn or name; round by id, slug or name, defaulting to the single
  open round) lives only in `core/refs.py`.
- Dedupe and normalization live only in `services/normalize.py` (email → LinkedIn →
  name+firm).
- Money is whole currency units in `bigint`. Dates are `date` in the workspace timezone.
- New API module: `api/router.py` already registers every planned module. New MCP tool: add it
  in the right `mcp/tools/<area>.py` with `read_only(...)` or `write(...)` annotations.
- Web: only design tokens exist in Tailwind (`bg-surface`, `text-muted`, `text-agent`,
  `bg-stage-teal`…). Cobalt = you can act, orchid = an agent did this, green = committed
  money, red = act now or failed. Components live in `web/components/ui`. Every `/v1` call
  goes through `web/lib/api/*`.
- Privacy is a product feature: no analytics, trackers or third-party runtime requests. Fonts
  come through `next/font`. Logs never include request bodies, investor fields or emails.
- Demo, test and docs data is **fictional only** (example.com emails, made-up people and
  firms). Never commit real people's data.
- Never print or commit secrets (API keys, session secrets, SMTP passwords).

## Invariants added in the polish pass (keep them)
- API keys die with their creator's access: `services/members.revoke_keys_created_by` runs on
  remove, leave, owner demotion and account deletion (`tests/test_key_lifecycle.py`).
- `/auth/verify` POSTs only on a click; a different signed-in user gets 409
  `session_conflict` unless `switch_account` (`tests/test_auth_hardening.py`). Sessions end
  90 days after sign-in (`session_max_days`); `/v1/me/sessions` lists and ends them.
- Per-IP `auth_fail`, per-person `invite_user`/`invite_user_new` buckets, and
  `workspaces_per_user` caps. Invite subjects are fixed; names cannot contain links.
- MCP: `mcp/server.WasilaMCP` returns compact JSON text (no outputSchema), rewrites
  argument validation errors to `validation_error: …`, hides write tools from read-only keys
  and reports the Wasila version. Shapes live in `mcp/shaping.py`; shared argument types
  (descriptions, "VC"/"250k" leniency) in `mcp/tools/_args.py`. Error text names MCP tools
  for MCP callers (`core.refs.how`) and REST paths for REST callers.
- `add_investor` defaults to `fill_empty`, appends notes on a match, reports `not_applied`,
  and matches by name alone when exactly one person has that name. Omitted rounds resolve
  to the investor's only open round when several are open.
- Web: text on soft tints uses the `*-ink` tokens (`text-warm-ink`, …), never the fill hue.
  Round views share `RoundHeader` (no second tab row). Phones get a compact ledger, a
  stacked pipeline list and single-column sheet fields.

## Invariants added in UX pass 1 (keep them)
- Web unit tests: `npm run test:unit` (node's test runner over `web/lib/**/*.test.ts`); run it
  with lint, typecheck and build.
- Pickers: a list longer than about 12 options, or one where search helps, is a `Combobox`
  (`TimezonePicker`, `CurrencyPicker` for zones and currencies; never a native select).
  Zones are saved canonical (`Asia/Kolkata`, not `Asia/Calcutta`) on both sides. Dates in
  the app use `DateField` and the **workspace** timezone.
- Pipeline: server props are initial data only. Rows live in a client store per round and
  the newer `updated_at` wins. Filter, sort, search and view changes send no requests (URL via
  `replaceState`); the sheet opens and closes with `replaceState` too.
- Keyboard: every global shortcut goes through `lib/hotkeys.ts` (`useHotkey`), never a
  document `keydown` listener of its own. Sheets register with `priority: 1`. App-wide keys set
  `blockedByModals`. Nothing fires while typing in a field.
- Long lists render windowed (`useVirtualRows`); no "Load more" or "Show 60 more" in the app.
- Import: only a missing name is a row error; bad optional cells are dropped with a warning.
- Bulk writes go through `POST /v1/rounds/{round}/participants/bulk-update` with a shared
  `data.bulk_id`; feeds collapse runs with `GET /v1/activities?collapse_runs=true`.
- Google sign-in is off unless `WASILA_GOOGLE_CLIENT_ID` and `_SECRET` are set; the web
  asks `GET /v1/auth/providers` and hides the button otherwise.

## Invariants added in the pipeline redo (keep them; spec: `design/pipeline-redo/DECISION.md`)
- The round page has three views: Triage, Board, Table. Pure rules (default view, money
  exists, dominant stage, triage keys, the card's one right slot, Next up buckets, pace) live
  in `web/lib/pipeline.ts` with unit tests. Triage needs a writer and an open stage.
- The board never folds a column into a rail. Board cards are the rich `DealCard`
  (`DECISION.md` §15; helpers in `web/lib/boardCard.ts`); the industry "Other" and the type
  `other` are never shown as chips or labels.
- Bare digits write only in Triage. Triage moves are optimistic through the page's store
  (`TriageStore`), and Undo restores the turn's snapshot with one `bulk-update` `restore`.
- Fictional fixtures for the 411-in-New and mature states: `design/pipeline-redo/fixtures/seed.py`
  (through the API, against a dev server).
- Critique 1 (`DECISION.md` §10): Triage counts are "left" (New and not skipped); U undoes the
  last change of any kind; a bulk move never skips the current undecided row; `restore` writes
  `data.undo` and timelines drop undone pairs (`dropUndone`). Fit pips are neutral ink, one
  encoding per place. The end-stage pill lives in the toolbar. The title row, ledger and table size to the page's measured width
  (the split sheet reflows them), never to viewport breakpoints alone.
- Critique 2 (`DECISION.md` §11): fit pips are quiet (`faint`) and absent inside single-fit
  groups; the type chip is neutral; a value every queued investor shares (source, the import
  history) is hidden. Triage asks before a talking stage (`claimsContact`) unless the intro was
  drafted; no preselected focus. The sheet is a split pane in every view, puts Contact and Facts
  first for open-kind stages and folds Money; imports show once (`collapseImportRuns`). Solo
  workspaces get no owner UI. `useHotkey({ listOnly })` lists keys a component handles itself.
- Critique 3 (`DECISION.md` §12): Triage has no rail and one population for every count
  (skipped ones are still New); the pace uses only real single-decision gaps (`paceEstimate`)
  and desktop Triage reports changes in the decision panel, not toasts. The open file follows
  the queue. Pips only in not-contacted stages (`hiddenPipFit`). Add investor lives in the title row in every view. Long dialogs
  use `Dialog scrollBody`; the Filter menu never scrolls an ancestor.
- Critique 4 (`DECISION.md` §13): the Triage pane is full height with the decision panel pinned
  (it never moves between investors); one Triage entry per screen besides the segment
  (`shownBuckets`); bulk Undo returns to the pre-move cursor; the sheet's "N of M" in Triage is
  the still-New walk; the pace plans at `PACE_FLOOR_MS` when faster. Reach out is one component
  (`components/app/ReachOut.tsx`, `introFitLine`) in Triage, the sheet, phone and the investor
  page. Talking columns sort by follow-up (`defaultColumnSort`). The Triage file is a split pane
  from 1024px.

## Kanban board (`DECISION.md` §14; keep it)
- The Board view is a classic kanban: one equal-width column per stage (`boardTrack`), empty
  ones included with "Drag investors here"; no rails, no shared "Drop to file" track, no fit
  groups on the board. Columns are windowed and sorted by `defaultColumnSort` (fit, follow-up,
  amount, recency by stage kind). Drag a card onto a column to move it; §5.5 keys still work.

## Investor research, Part 1 foundation (spec `docs/RESEARCH-SPEC.md`, plan `docs/RESEARCH-PLAN.md`)
- **Unreleased and off by default.** Only `WASILA_RESEARCH_ENABLED=true` serves its REST
  modules (`api/router.RESEARCH_API_MODULES`), its MCP tools (`mcp/tools.RESEARCH_TOOL_MODULES`)
  and the research line of the MCP instructions. With it off the MCP surface is the 23 core tools
  every public page promises (`tests/test_research_flag.py`). Never mention research on a
  public page, the README or the changelog until it ships. Tests run with the flag on.
- Migration `0003_research` holds every research table. Public facts (`research_sources`,
  `investor_identities`, `investor_identity_candidates`, `dossier_facts`) stay apart from
  private analysis (`dossiers`, `research_runs`, `field_suggestions`). Composite
  `(workspace_id, …)` FKs everywhere; `activities.kind` includes `research`.
- The OpenRouter key is sealed by `core/secrets.py` (AES-256-GCM DEK per key, wrapped by the
  KEK; AAD = workspace id). Only `key_last4` is ever returned; no export, log or error carries
  the key; `sk-or-…` is redacted from logs. Only an owner signed in to the web sets or removes
  it (`require_owner_session`); preset, model ids and cap need `wasila:admin`.
- `services/ai_settings.PRESETS` is pinned to the recorded models list by a test; ids are
  verified on `GET /models` when a key is saved and when models change with a key present.
- Money for AI is USD micros (`*_micros bigint`). Every OpenRouter call reserves first with
  `services/spend.reserve_for_run` (one conditional UPDATE; never over the cap), then
  `settle_for_run` with OpenRouter's reported cost; recovery, cancel and shutdown call
  `release_for_run`.
- Jobs: `services/jobs.py` (enqueue with `dedupe_key`, `FOR UPDATE SKIP LOCKED` claims, leases,
  backoff, `recover_stuck`) and `wasila/worker.py` (`wasilactl worker`). Handlers register with
  `worker.register(kind, handler, on_recover=…)` from a module listed in
  `worker.HANDLER_MODULES`, are idempotent per step and call `ctx.check_lease()` between steps.
  Jobs carry ids only, never secrets or investor fields.

## Investor research, Part 2 pipeline (keep these)
- Runs (`services/research.py`): `research.run` jobs carry the run id only; the handler acts as
  the requester via `auth/principal.worker_context` (lost write access → `cancelled`), opens
  the key only inside the run, and commits each step with its cost. Every OpenRouter call
  reserves first (`spend.reserve_for_run`, ×1.5 of that call's budget) and settles
  OpenRouter's `usage.cost` (priced from the snapshot and flagged `estimated` when missing).
  A refused reservation ends the run `capped`; `failed`/`partial`/`capped` runs resume and
  skip finished steps. One active run per investor and kind (double clicks return it).
- Identity first (`services/research_identity.py`): confidence is recomputed in code;
  ≥ 0.80 with a 0.15 margin → `matched`, else `needs_pick` (2-3 candidates) or `not_found`.
  Dossier runs refuse (`identity_required`) or end `blocked_identity` until anchored. A
  LinkedIn URL a person entered confirms without a model call.
- One validator (`services/research_validate.py`) and one privacy filter
  (`services/privacy_filter.py`) serve model and agent dossiers: sources must match the anchor
  (LinkedIn profile, firm domain, name + firm, name + title), personal social sites never
  count, facts cite accepted sources (uncited: model → `unverified`, agent → dropped and
  listed), phones/addresses/consumer emails are stripped and private topics dropped.
- Dossiers (`services/dossiers.py`): `dossiers` (private analysis) + `dossier_facts` (public
  facts citing `research_sources` ids); last 5 versions; "new since" via strict + loose fact
  keys; stale > 90 days and the Meeting refresh offer > 30 days are computed, never stored.
- Write-back (`services/research_writeback.py`) fills only empty fields (an `auto_applied`
  suggestion row is the "from research" mark) and suggests the rest; identity fills point at
  their run (`field_suggestions.run_id`, migration 0004). Ignored values are never suggested
  again; accept-all shares one `bulk_id`.
- `save_dossier` (MCP) / `POST /v1/investors/{id}/dossier` need no key and cost nothing; the
  dossier and its activity are "by <agent-name>". The writer never sees emails, amounts or
  timelines, and sees notes only when `use_notes_in_research` is on (prompts in
  `services/research_prompts.py`, hash-pinned by a test: bump `PROMPT_VERSION` with any change).
- Removal (`services/research_removal.py`) holds the only cross-workspace writes
  (DELETE/UPDATE, counts only); suppressions refuse research for that person everywhere.
  `services/research_reuse.py` holds the only cross-workspace **read** (see "Never pay twice").
- Tests: `tests/research/pipeline_mock.Script` scripts OpenRouter's answers;
  `tests/research/helpers.run_jobs(db)` runs queued jobs in-process on the test session.

## Investor research: never pay twice (spec #14 to #16, owner decisions 2026-10-14; plan §12)
- A `dossier` run on a dossier under `FRESH_DOSSIER_DAYS` (30) returns it (`created: false`,
  `reason: "fresh"`, `dossier`); only `kind=refresh` or `force` pays again. An identity run on
  a confirmed/matched identity returns `reason: "identified"`. Web: a fresh dossier shows
  **Open dossier** + a secondary **Refresh**.
- Reuse (`services/research_reuse.py`) is the single named cross-workspace read: only when the
  requester (a session owner, or the owner who created the API key) owns **both** workspaces,
  the same person (confirmed LinkedIn, else exact normalized name + firm domain), research
  finished within 30 days, nothing suppressed, never from a sample workspace. It copies the
  identity, accepted sources and public `dossier_facts` only (never `dossiers`, notes or
  suggestions); the run is `reuse → filter → write → save`, priced as the writer alone, and the
  dossier says "Reused research from <workspace> (<date>)". Non-owners and different owners
  never reuse (`tests/research/test_research_reuse.py`).
- `workspace_ai_settings.use_notes_in_research` (default off; admin): notes go through
  `privacy_filter.notes_for_research` (≈2,000 chars, phones/addresses/private lines removed) to
  the searches ("Already known …") and the writer (NOTES). Notes-only claims live in
  `dossiers.analysis.from_notes` ("from your notes"), never in `dossier_facts`, never reused.

## Investor research, Part 3 web (keep these)
- Research runs only on the workspace's own OpenRouter key, only on a click (never on import,
  never automatic); every bulk run goes through `EstimateDialog` (count, left out, each and
  total, left under the limit) and `batchBody` sends the total the person confirmed.
- Every research call goes through `web/lib/api/research.ts`; pure rules (money, freshness,
  the Meeting offer, sections and citation numbers, suggestion lines, estimate and run words)
  live in `web/lib/research.ts` with unit tests. Components are in
  `web/components/app/research/` (`DossierPanel`, `Brief`, `IdentityPicker`, `SuggestionList`,
  `RunProgress`, `EstimateDialog`, `BatchProgress`, `TriageResearch`, settings pages).
- The key is never shown again after saving: the web shows `key_last4` only, and only an owner
  signed in on the web sees the key form.
- The sheet has Pipeline | Dossier tabs (`R`); the Triage decision panel's research band has a
  fixed height (`TRIAGE_RESEARCH_H`) and `A` accepts all suggestions for the investor, undone
  by U (`Decision.revert` puts investor fields back). Write-back is shown, never silent:
  "from research" marks on filled fields, suggestions everywhere else.
- The Meeting refresh offer is a toast action (`refreshOffer`, > 30 days) and a banner on the
  Dossier tab; it never starts a run by itself. A run started elsewhere is announced
  (`announceRun`) so an open dossier follows it.
- Polls (runs, batches) go every 2s and pause while the tab is hidden; no websockets.
- Screenshots of every research screen (1440 light and dark, 1280, 390) are in
  `design/research/shots/`, taken against a throwaway database and a local fake OpenRouter;
  the re-shoot after the verification fixes is in `design/research/final/`. The fake must cite
  a `linkedin.com/in/…` page for a clear identity, or the run stops at "Is this them?".

## Meetings (SPEC §3.9, §5.9, §6.8; keep these)
- `services/meetings.py` is the only writer of `meetings`/`meeting_guests`; REST
  (`api/meetings.py`) and MCP (`mcp/tools/meetings.py`: schedule_meeting, list_meetings,
  update_meeting, complete_meeting; core tools; 23 core with the linked-card tools) call it. Every change writes
  `meeting_scheduled` / `meeting_updated` (`data.change`, `data.seq`) or, when done, a `meeting`
  activity with `data.meeting_id`; that timeline is the meeting's history. Same investor + same
  start = the same meeting (`created: false`). `done` is final (409 `meeting_done`).
- Scheduling in a round moves an open/active investor that is earlier to the Meeting stage (key
  `meeting`, else a "Meeting" label) unless `move_to_meeting_stage=false`; never moves back.
  Guests are only people at the same firm (`norm_firm`).
- Deletion follows investors (investor/guest cascade; a round delete sets `round_id` NULL).
  Meetings are in the workspace JSON export.
- `services/calendar_feed.py`: one hashed `wslcal_` secret per user, shown once; the feed reads
  the user's current memberships on every request (the only per-user cross-workspace read
  besides research reuse). Feed routes are org-less in `tests/isolation`.
- Web: pure rules in `web/lib/meetings.ts` (unit tested): chip text, `meetingBeatsFollowUp`,
  groups, Google Calendar link, `zonedToUtc`. Times are entered in the workspace timezone and
  shown in the viewer's (`useViewerTimeZone`, workspace zone on the server render). The card
  slot (`cardSlot(…, {timeZone})`) shows "Meeting today 11:00" / "Wed 12:00" instead of the
  follow-up when the meeting comes first and no follow-up is due. B schedules in the investor
  sheet, the investor page and Meetings; `g m` goes to Meetings. Components live in
  `web/components/app/meetings/`.
- Screenshots (1440 light and dark, 390): `design/meetings/*.jpg` (fixtures: `design/meetings/fixtures/seed.py`).

## Linked cards (SPEC §3.10, §5.10, §6.9; keep these)
- `services/investor_links.py` is the only writer of `investor_groups` and `investors.group_id`
  (migration 0009; composite `(workspace_id, group_id)` FK, `ON DELETE SET NULL (group_id)`).
  REST `POST`/`DELETE /v1/investors/{id}/links` and MCP `link_investors` / `unlink_investor`
  call it. Linking merges every involved group; a group never has fewer than two members
  (unlink and investor delete dissolve it). Repeats are no-ops that write nothing.
- Each investor whose linked set changes gets one `investor_updated` activity
  (`data.fields = ["linked_cards"]`, `changes.linked_cards = {from, to}` as ids).
- `Investor` and the participant's `investor` carry `group_id` and `linked` (other members,
  by name); `linked_map` loads them for a whole page in one query (no N+1, tested by query
  count in `tests/test_linked_cards.py`). MCP shows `linked: [{id, name, firm}]`.

## Wasila brand pass and local run (keep these)
- The app bar is the brand band: `[data-app-bar]` swaps the neutral tokens for `--bar-*` in
  `globals.css` and restores the page tokens for menus/dialogs inside it. Gold (`brand-gold`)
  marks: the bar's rule, active nav/tab, page-title mark, version badge. Tags and table heads
  use `accent-soft`; section labels use `--sky-ink`. Text on brand fills uses `on-brand` /
  `on-gold`. No raw hex outside `globals.css`.
- `deploy/local/start.sh` / `stop.sh` run the production build locally (web :3600 standalone
  server, API :8000, `wasila_dev`), outreach in `memory` mode unless `REAL_EMAIL=1`. Logs, pid
  files and `.env.local` are git-ignored.
- CORS allows `X-Filename` and `X-Note` (raw-body uploads); `tests/test_core.py` pins it.
- Investor-update merge fields come only from `funding_costs.merge_values` (`MERGE_FIELDS`);
  campaign drafts render them; a figure not entered is an empty string, never a raw `{key}`.
- `claude_settings.anthropic_workspace_id` (0011) is sent as `anthropic-workspace-id` on every
  Claude call; `claude.save_key` is the only key writer (REST and `wasilactl claude set-key`).
  The key file for `start.sh` (`deploy/local/claude-key.txt`) is git-ignored and deleted after use.
