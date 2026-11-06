# Changelog

All notable changes to Wasila. Versions use four parts (major.minor.patch.build).

## v1.0.0.0 · 2026-11-06

First Wasila release, built on the upstream investor CRM (see NOTICE).

### Name and brand
- Renamed everywhere: package `wasila`, env prefix `WASILA_*`, CLI `wasilactl`, API keys
  `wsl_live_` / `wsl_test_`, scopes `wasila:read|write|admin`, cookies and storage keys `wsl_` /
  `wsl-`, calendar tokens `wslcal_`. **Breaking** for any earlier deployment: re-issue API keys
  and calendar feed URLs, rename environment variables.
- Wasila palette (`#0000FF`, `#B9D9EB`, `#00A1EB`, `#E5C100`) in light and dark mode, the
  Wasila logo, favicon and app icons. The app bar is a solid Wasila blue band with a gold rule
  (the logo's arch); tables, tags and empty states use the light-blue tint; cards and KPI tiles
  carry sky and gold rules; the version badge is gold.
- Fonts are bundled (no build-time download), including IBM Plex Sans Arabic.
- `Wasila v1.0.0.0` and a light/dark switch on every page (app, sign-in, public site, error
  pages); the API's `/healthz` and the MCP server report `1.0.0.0`.
- Arabic/English scaffolding: Settings → Language sets `lang`/`dir` (right-to-left), a locale
  dictionary with English fallback, RTL font and CSS hooks. No translation yet.
- Upstream pricing, comparison and donation pages removed; terms and privacy name Applied
  Biosciences Limited (to be reviewed by your lawyer).

### Running locally
- `deploy/local/start.sh` runs Wasila on your computer production style (web production build
  on :3600, API on :8000, migrations, logs), with email sends in test mode by default;
  `deploy/local/stop.sh` stops it.
- Fix: Excel/Word imports and Funding Room uploads from the browser were blocked by CORS
  (`X-Filename` was not an allowed header).
- Investor profiles show and edit phone and country; the master list shows email and phone.

### US, UK and Saudi raising
- Rounds gain `jurisdiction` (us, uk, ksa, other), `tax_relief` (none, seis, eis, seis_eis; UK
  only) and `sharia_compliant`; instrument `asa` (UK advance subscription agreement). A
  round's currency defaults from its market (USD, GBP, SAR).

### Funding Room (`/v1/funding-room`)
- Documents with category, folder, description, confidentiality, review status and market;
  immutable versions (25 MB each, stored in Postgres) with SHA-256; download records.
- US / UK / KSA checklists.
- Share links (`/room/<token>`): approved documents only, 1 to 90 days, revocable, hashed
  tokens, private view counts.
- An activity log for every change, download and view.

### Master list, fields, lists and intros
- `POST /v1/imports/convert`: Excel sheets and Word tables to CSV for the import pipeline; the
  import page accepts `.xlsx` and `.docx`. New import fields: country, phone, AI interest and
  healthcare interest (Y/N → tags); more column aliases.
- Investors gain `country`, `phone` and `custom`.
- `POST /v1/master-list/search` and `/facets`; `/v1/investor-fields` (custom fields and AI
  columns); `/v1/saved-lists`; `/v1/investors/{id}/intros` (warm intros, best path).

### Claude (`/v1/claude`)
- The workspace's own Anthropic key, verified then sealed; owners only; model choice.
- `POST /v1/master-list/ask` (Ask Wasila), `POST /v1/investor-fields/{id}/fill` (AI columns),
  `POST /v1/outreach/draft` (warm letters and updates), `POST /v1/decks/{id}/suggest`.
- Claude sees public profile data only and runs only on request.

### Outreach (`/v1/outreach`)
- Mail settings per workspace (SMTP; password sealed; owners only).
- Drafts with hand-picked Funding Room attachments; send on click; every send is an `email`
  activity; replies logged; campaigns with mail merge and follow-up reminders.

### Deck editor (`/v1/decks`) and funding costs (`/v1/funding-costs`)
- Read a PowerPoint deck, edit text, hide/reorder slides, save as a new version; PDF export
  when LibreOffice is installed.
- Funding, use of funds, income and cost lines; workbook import; KPIs (burn, runway, gap).

### MCP
- `list_funding_room`, `search_master_list`, `draft_outreach` (26 core tools).

### Tests
- New: `tests/test_wasila_features.py`; isolation cases for every new route and tool
  (`tests/isolation/wasila_cases.py`); web unit tests for i18n and mail merge.
