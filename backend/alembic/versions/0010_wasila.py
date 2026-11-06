"""Wasila v1.0.0.0: US/UK/Saudi rounds, the Funding Room, the master list, outreach, Claude,
warm intros, saved lists, custom fields and funding costs.

- ``rounds``: ``jurisdiction`` (us, uk, ksa, other), ``tax_relief`` (UK SEIS/EIS),
  ``sharia_compliant``; instrument ``asa`` (UK advance subscription agreement).
- ``investors``: ``country``, ``phone`` and ``custom`` (values of ``investor_fields``).
- ``investor_fields``: workspace custom fields; ``kind = 'ai'`` is an AI column Claude fills.
- ``funding_room_documents`` / ``_versions`` / ``_links`` / ``_events``: the document room.
  File bytes live in ``funding_room_versions.data`` (bytea, capped at 25 MB per version), so a
  database backup is a complete backup.
- ``workspace_secrets``: sealed secrets per workspace (Anthropic key, SMTP password), envelope
  encryption exactly like ``workspace_ai_settings`` (core/secrets.py).
- ``mail_settings``, ``campaigns``, ``outreach_messages``: email outreach, sent only on a click.
- ``intro_connections``: who in the founder's network knows an investor (warm intros).
- ``saved_lists``: named searches of the master list (filters or an Ask Wasila question).
- ``funding_cost_lines``: use of funds and 48-month cost lines.

Every table is workspace-scoped with ``UNIQUE (workspace_id, id)`` and composite foreign keys.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _actor(table: str) -> str:
    return f"""
  actor_type      text NOT NULL DEFAULT 'user',
  actor_user_id   uuid,
  actor_label     text,
  via             text NOT NULL DEFAULT 'web',
  CONSTRAINT ck_{table}_actor_type_valid CHECK (actor_type IN ('user', 'agent', 'system')),
  CONSTRAINT ck_{table}_via_valid CHECK (via IN ('web', 'api', 'mcp', 'import', 'system')),
  CONSTRAINT ck_{table}_actor_label_valid CHECK (
    actor_label IS NULL OR length(actor_label) <= 120),
  CONSTRAINT fk_{table}_actor_user FOREIGN KEY (actor_user_id)
    REFERENCES users (id) ON DELETE SET NULL,"""


def _ws(table: str) -> str:
    return f"""
  CONSTRAINT pk_{table} PRIMARY KEY (id),
  CONSTRAINT uq_{table}_workspace_id_id UNIQUE (workspace_id, id),
  CONSTRAINT fk_{table}_workspace FOREIGN KEY (workspace_id)
    REFERENCES workspaces (id) ON DELETE CASCADE"""


UP = (
    # --- rounds: US / UK / Saudi raising ------------------------------------------------------
    "ALTER TABLE rounds DROP CONSTRAINT ck_rounds_instrument_valid",
    "ALTER TABLE rounds ADD CONSTRAINT ck_rounds_instrument_valid CHECK ("
    "instrument IN ('safe', 'priced', 'convertible_note', 'asa', 'other'))",
    "ALTER TABLE rounds ADD COLUMN jurisdiction text NOT NULL DEFAULT 'us'",
    "ALTER TABLE rounds ADD CONSTRAINT ck_rounds_jurisdiction_valid CHECK ("
    "jurisdiction IN ('us', 'uk', 'ksa', 'other'))",
    "ALTER TABLE rounds ADD COLUMN tax_relief text NOT NULL DEFAULT 'none'",
    "ALTER TABLE rounds ADD CONSTRAINT ck_rounds_tax_relief_valid CHECK ("
    "tax_relief IN ('none', 'seis', 'eis', 'seis_eis'))",
    "ALTER TABLE rounds ADD COLUMN sharia_compliant boolean NOT NULL DEFAULT false",
    # --- investors: the master list --------------------------------------------------------------
    "ALTER TABLE investors ADD COLUMN country text",
    "ALTER TABLE investors ADD CONSTRAINT ck_investors_country_valid CHECK ("
    "country IS NULL OR length(country) <= 100)",
    "ALTER TABLE investors ADD COLUMN phone text",
    "ALTER TABLE investors ADD CONSTRAINT ck_investors_phone_valid CHECK ("
    "phone IS NULL OR length(phone) <= 40)",
    "ALTER TABLE investors ADD COLUMN custom jsonb NOT NULL DEFAULT '{}'",
    "ALTER TABLE investors ADD CONSTRAINT ck_investors_custom_valid CHECK ("
    "jsonb_typeof(custom) = 'object')",
    "CREATE INDEX ix_investors_ws_country ON investors (workspace_id, lower(country)) "
    "WHERE country IS NOT NULL",
    f"""
CREATE TABLE investor_fields (
  id            uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL,
  key           text NOT NULL,
  label         text NOT NULL,
  kind          text NOT NULL DEFAULT 'text',
  options       text[] NOT NULL DEFAULT '{{}}',
  prompt        text,
  position      integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),{_ws("investor_fields")},
  CONSTRAINT uq_investor_fields_key UNIQUE (workspace_id, key),
  CONSTRAINT ck_investor_fields_key_valid CHECK (key ~ '^[a-z][a-z0-9_]{{0,39}}$'),
  CONSTRAINT ck_investor_fields_label_valid CHECK (length(btrim(label)) BETWEEN 1 AND 80),
  CONSTRAINT ck_investor_fields_kind_valid CHECK (
    kind IN ('text', 'number', 'yes_no', 'select', 'url', 'ai')),
  CONSTRAINT ck_investor_fields_prompt_valid CHECK (
    (kind = 'ai') = (prompt IS NOT NULL) AND (prompt IS NULL OR length(prompt) <= 2000)),
  CONSTRAINT ck_investor_fields_options_valid CHECK (cardinality(options) <= 50)
)
""",
    # --- Funding Room ----------------------------------------------------------------------------
    f"""
CREATE TABLE funding_room_documents (
  id               uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id     uuid NOT NULL,
  title            text NOT NULL,
  category         text NOT NULL,
  folder           text,
  description      text,
  confidentiality  text NOT NULL DEFAULT 'investors',
  review_status    text NOT NULL DEFAULT 'draft',
  jurisdiction     text NOT NULL DEFAULT 'all',
  is_deck          boolean NOT NULL DEFAULT false,
  current_version  integer NOT NULL DEFAULT 0,
  reviewed_at      timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),{_actor("funding_room_documents")}{_ws("funding_room_documents")},
  CONSTRAINT ck_funding_room_documents_title_valid CHECK (length(btrim(title)) BETWEEN 1 AND 200),
  CONSTRAINT ck_funding_room_documents_category_valid CHECK (category IN (
    'pitch', 'corporate', 'financial', 'technical', 'clinical', 'regulatory', 'ip',
    'cybersecurity', 'data_protection', 'commercial', 'legal', 'tax_relief', 'other')),
  CONSTRAINT ck_funding_room_documents_folder_valid CHECK (folder IS NULL OR length(folder) <= 120),
  CONSTRAINT ck_funding_room_documents_description_valid CHECK (
    description IS NULL OR length(description) <= 4000),
  CONSTRAINT ck_funding_room_documents_conf_valid CHECK (
    confidentiality IN ('public', 'investors', 'nda', 'restricted')),
  CONSTRAINT ck_funding_room_documents_review_valid CHECK (
    review_status IN ('draft', 'in_review', 'approved', 'archived')),
  CONSTRAINT ck_funding_room_documents_jurisdiction_valid CHECK (
    jurisdiction IN ('all', 'us', 'uk', 'ksa')),
  CONSTRAINT ck_funding_room_documents_version_valid CHECK (current_version >= 0)
)
""",
    "CREATE INDEX ix_funding_room_documents_ws ON funding_room_documents "
    "(workspace_id, category, updated_at DESC)",
    f"""
CREATE TABLE funding_room_versions (
  id             uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id   uuid NOT NULL,
  document_id    uuid NOT NULL,
  version        integer NOT NULL,
  filename       text NOT NULL,
  content_type   text NOT NULL,
  size_bytes     integer NOT NULL,
  sha256         text NOT NULL,
  note           text,
  data           bytea NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),{_actor("funding_room_versions")}{_ws("funding_room_versions")},
  CONSTRAINT uq_funding_room_versions_doc_version UNIQUE (document_id, version),
  CONSTRAINT fk_funding_room_versions_doc FOREIGN KEY (workspace_id, document_id)
    REFERENCES funding_room_documents (workspace_id, id) ON DELETE CASCADE,
  CONSTRAINT ck_funding_room_versions_version_valid CHECK (version >= 1),
  CONSTRAINT ck_funding_room_versions_filename_valid CHECK (length(filename) BETWEEN 1 AND 255),
  CONSTRAINT ck_funding_room_versions_size_valid CHECK (
    size_bytes BETWEEN 1 AND 26214400 AND size_bytes = octet_length(data)),
  CONSTRAINT ck_funding_room_versions_note_valid CHECK (note IS NULL OR length(note) <= 500)
)
""",
    f"""
CREATE TABLE funding_room_links (
  id              uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id    uuid NOT NULL,
  investor_id     uuid,
  label           text NOT NULL,
  token_hash      bytea NOT NULL,
  document_ids    uuid[] NOT NULL,
  expires_at      timestamptz NOT NULL,
  revoked_at      timestamptz,
  view_count      integer NOT NULL DEFAULT 0,
  last_viewed_at  timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),{_actor("funding_room_links")}{_ws("funding_room_links")},
  CONSTRAINT uq_funding_room_links_token UNIQUE (token_hash),
  CONSTRAINT fk_funding_room_links_investor FOREIGN KEY (workspace_id, investor_id)
    REFERENCES investors (workspace_id, id) ON DELETE CASCADE,
  CONSTRAINT ck_funding_room_links_label_valid CHECK (length(btrim(label)) BETWEEN 1 AND 120),
  CONSTRAINT ck_funding_room_links_docs_valid CHECK (cardinality(document_ids) BETWEEN 1 AND 50)
)
""",
    f"""
CREATE TABLE funding_room_events (
  id            uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL,
  document_id   uuid,
  kind          text NOT NULL,
  data          jsonb NOT NULL DEFAULT '{{}}',
  created_at    timestamptz NOT NULL DEFAULT now(),{_actor("funding_room_events")}{_ws("funding_room_events")},
  CONSTRAINT ck_funding_room_events_kind_valid CHECK (kind IN (
    'created', 'version_added', 'updated', 'deleted', 'downloaded', 'link_created',
    'link_revoked', 'link_viewed')),
  CONSTRAINT ck_funding_room_events_data_valid CHECK (jsonb_typeof(data) = 'object')
)
""",
    "CREATE INDEX ix_funding_room_events_ws ON funding_room_events (workspace_id, created_at DESC)",
    # --- sealed secrets, mail, outreach ----------------------------------------------------------
    """
CREATE TABLE workspace_secrets (
  workspace_id     uuid NOT NULL,
  kind             text NOT NULL,
  ciphertext       bytea NOT NULL,
  nonce            bytea NOT NULL,
  dek_wrapped      bytea NOT NULL,
  dek_nonce        bytea NOT NULL,
  kek_id           text NOT NULL,
  last4            text NOT NULL,
  set_at           timestamptz NOT NULL DEFAULT now(),
  set_by_user_id   uuid,
  CONSTRAINT pk_workspace_secrets PRIMARY KEY (workspace_id, kind),
  CONSTRAINT fk_workspace_secrets_workspace FOREIGN KEY (workspace_id)
    REFERENCES workspaces (id) ON DELETE CASCADE,
  CONSTRAINT fk_workspace_secrets_user FOREIGN KEY (set_by_user_id)
    REFERENCES users (id) ON DELETE SET NULL,
  CONSTRAINT ck_workspace_secrets_kind_valid CHECK (kind IN ('anthropic', 'smtp'))
)
""",
    """
CREATE TABLE claude_settings (
  workspace_id   uuid NOT NULL,
  model          text NOT NULL DEFAULT 'claude-sonnet-5-5',
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_claude_settings PRIMARY KEY (workspace_id),
  CONSTRAINT fk_claude_settings_workspace FOREIGN KEY (workspace_id)
    REFERENCES workspaces (id) ON DELETE CASCADE,
  CONSTRAINT ck_claude_settings_model_valid CHECK (model ~ '^[a-z0-9.-]{3,80}$')
)
""",
    """
CREATE TABLE mail_settings (
  workspace_id   uuid NOT NULL,
  host           text NOT NULL,
  port           integer NOT NULL DEFAULT 587,
  security       text NOT NULL DEFAULT 'starttls',
  username       text,
  from_email     citext NOT NULL,
  from_name      text,
  reply_to       citext,
  bcc_self       boolean NOT NULL DEFAULT true,
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_mail_settings PRIMARY KEY (workspace_id),
  CONSTRAINT fk_mail_settings_workspace FOREIGN KEY (workspace_id)
    REFERENCES workspaces (id) ON DELETE CASCADE,
  CONSTRAINT ck_mail_settings_port_valid CHECK (port BETWEEN 1 AND 65535),
  CONSTRAINT ck_mail_settings_security_valid CHECK (security IN ('starttls', 'ssl', 'none')),
  CONSTRAINT ck_mail_settings_host_valid CHECK (length(host) BETWEEN 1 AND 253),
  CONSTRAINT ck_mail_settings_from_valid CHECK (position('@' IN from_email) > 1)
)
""",
    f"""
CREATE TABLE campaigns (
  id                 uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id       uuid NOT NULL,
  name               text NOT NULL,
  kind               text NOT NULL DEFAULT 'outreach',
  subject            text NOT NULL,
  body               text NOT NULL,
  attachment_ids     uuid[] NOT NULL DEFAULT '{{}}',
  follow_up_days     integer,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),{_actor("campaigns")}{_ws("campaigns")},
  CONSTRAINT ck_campaigns_name_valid CHECK (length(btrim(name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_campaigns_kind_valid CHECK (kind IN ('outreach', 'update')),
  CONSTRAINT ck_campaigns_subject_valid CHECK (length(subject) BETWEEN 1 AND 300),
  CONSTRAINT ck_campaigns_body_valid CHECK (length(body) BETWEEN 1 AND 50000),
  CONSTRAINT ck_campaigns_follow_up_valid CHECK (
    follow_up_days IS NULL OR follow_up_days BETWEEN 1 AND 90)
)
""",
    f"""
CREATE TABLE outreach_messages (
  id               uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id     uuid NOT NULL,
  investor_id      uuid NOT NULL,
  campaign_id      uuid,
  round_id         uuid,
  kind             text NOT NULL DEFAULT 'outreach',
  to_email         citext NOT NULL,
  subject          text NOT NULL,
  body             text NOT NULL,
  attachments      jsonb NOT NULL DEFAULT '[]',
  status           text NOT NULL DEFAULT 'draft',
  drafted_by       text NOT NULL DEFAULT 'person',
  error            text,
  message_id       text,
  sent_at          timestamptz,
  replied_at       timestamptz,
  activity_id      uuid,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),{_actor("outreach_messages")}{_ws("outreach_messages")},
  CONSTRAINT fk_outreach_messages_investor FOREIGN KEY (workspace_id, investor_id)
    REFERENCES investors (workspace_id, id) ON DELETE CASCADE,
  CONSTRAINT fk_outreach_messages_campaign FOREIGN KEY (workspace_id, campaign_id)
    REFERENCES campaigns (workspace_id, id) ON DELETE SET NULL (campaign_id),
  CONSTRAINT fk_outreach_messages_round FOREIGN KEY (workspace_id, round_id)
    REFERENCES rounds (workspace_id, id) ON DELETE SET NULL (round_id),
  CONSTRAINT fk_outreach_messages_activity FOREIGN KEY (activity_id)
    REFERENCES activities (id) ON DELETE SET NULL,
  CONSTRAINT ck_outreach_messages_kind_valid CHECK (kind IN ('outreach', 'update', 'follow_up')),
  CONSTRAINT ck_outreach_messages_status_valid CHECK (
    status IN ('draft', 'sending', 'sent', 'failed')),
  CONSTRAINT ck_outreach_messages_drafted_by_valid CHECK (drafted_by IN ('person', 'claude')),
  CONSTRAINT ck_outreach_messages_subject_valid CHECK (length(subject) BETWEEN 1 AND 300),
  CONSTRAINT ck_outreach_messages_body_valid CHECK (length(body) BETWEEN 1 AND 50000),
  CONSTRAINT ck_outreach_messages_attachments_valid CHECK (jsonb_typeof(attachments) = 'array')
)
""",
    "CREATE INDEX ix_outreach_messages_ws ON outreach_messages (workspace_id, created_at DESC)",
    "CREATE INDEX ix_outreach_messages_investor ON outreach_messages (workspace_id, investor_id)",
    # --- warm intros and saved lists -------------------------------------------------------------
    f"""
CREATE TABLE intro_connections (
  id               uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id     uuid NOT NULL,
  investor_id      uuid NOT NULL,
  connector_name   text NOT NULL,
  connector_email  citext,
  relationship     text,
  strength         smallint NOT NULL DEFAULT 2,
  notes            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),{_actor("intro_connections")}{_ws("intro_connections")},
  CONSTRAINT fk_intro_connections_investor FOREIGN KEY (workspace_id, investor_id)
    REFERENCES investors (workspace_id, id) ON DELETE CASCADE,
  CONSTRAINT ck_intro_connections_name_valid CHECK (length(btrim(connector_name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_intro_connections_relationship_valid CHECK (
    relationship IS NULL OR length(relationship) <= 200),
  CONSTRAINT ck_intro_connections_strength_valid CHECK (strength BETWEEN 1 AND 3),
  CONSTRAINT ck_intro_connections_notes_valid CHECK (notes IS NULL OR length(notes) <= 2000)
)
""",
    "CREATE INDEX ix_intro_connections_investor ON intro_connections (workspace_id, investor_id)",
    f"""
CREATE TABLE saved_lists (
  id            uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL,
  name          text NOT NULL,
  question      text,
  filters       jsonb NOT NULL DEFAULT '{{}}',
  investor_ids  uuid[] NOT NULL DEFAULT '{{}}',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),{_actor("saved_lists")}{_ws("saved_lists")},
  CONSTRAINT ck_saved_lists_name_valid CHECK (length(btrim(name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_saved_lists_question_valid CHECK (question IS NULL OR length(question) <= 1000),
  CONSTRAINT ck_saved_lists_filters_valid CHECK (jsonb_typeof(filters) = 'object'),
  CONSTRAINT ck_saved_lists_ids_valid CHECK (cardinality(investor_ids) <= 5000)
)
""",
    # --- funding costs ----------------------------------------------------------------------------
    f"""
CREATE TABLE funding_cost_lines (
  id            uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL,
  kind          text NOT NULL,
  grp           text NOT NULL,
  name          text NOT NULL,
  currency      char(3) NOT NULL DEFAULT 'GBP',
  amount        bigint NOT NULL DEFAULT 0,
  y1            bigint NOT NULL DEFAULT 0,
  y2            bigint NOT NULL DEFAULT 0,
  y3            bigint NOT NULL DEFAULT 0,
  y4            bigint NOT NULL DEFAULT 0,
  tranche       text,
  objective     text,
  position      integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),{_ws("funding_cost_lines")},
  CONSTRAINT ck_funding_cost_lines_kind_valid CHECK (
    kind IN ('use_of_funds', 'cost', 'income', 'funding')),
  CONSTRAINT ck_funding_cost_lines_grp_valid CHECK (length(btrim(grp)) BETWEEN 1 AND 80),
  CONSTRAINT ck_funding_cost_lines_name_valid CHECK (length(btrim(name)) BETWEEN 1 AND 200),
  CONSTRAINT ck_funding_cost_lines_currency_valid CHECK (currency ~ '^[A-Z]{{3}}$'),
  CONSTRAINT ck_funding_cost_lines_tranche_valid CHECK (
    tranche IS NULL OR tranche IN ('seis', 'eis', 'equity', 'grant', 'other')),
  CONSTRAINT ck_funding_cost_lines_objective_valid CHECK (
    objective IS NULL OR length(objective) <= 500)
)
""",
    "CREATE INDEX ix_funding_cost_lines_ws ON funding_cost_lines (workspace_id, kind, position)",
)

DOWN = (
    "DROP TABLE IF EXISTS funding_cost_lines",
    "DROP TABLE IF EXISTS saved_lists",
    "DROP TABLE IF EXISTS intro_connections",
    "DROP TABLE IF EXISTS outreach_messages",
    "DROP TABLE IF EXISTS campaigns",
    "DROP TABLE IF EXISTS mail_settings",
    "DROP TABLE IF EXISTS claude_settings",
    "DROP TABLE IF EXISTS workspace_secrets",
    "DROP TABLE IF EXISTS funding_room_events",
    "DROP TABLE IF EXISTS funding_room_links",
    "DROP TABLE IF EXISTS funding_room_versions",
    "DROP TABLE IF EXISTS funding_room_documents",
    "DROP TABLE IF EXISTS investor_fields",
    "DROP INDEX IF EXISTS ix_investors_ws_country",
    "ALTER TABLE investors DROP COLUMN IF EXISTS custom",
    "ALTER TABLE investors DROP COLUMN IF EXISTS phone",
    "ALTER TABLE investors DROP COLUMN IF EXISTS country",
    "ALTER TABLE rounds DROP COLUMN IF EXISTS sharia_compliant",
    "ALTER TABLE rounds DROP COLUMN IF EXISTS tax_relief",
    "ALTER TABLE rounds DROP COLUMN IF EXISTS jurisdiction",
    "UPDATE rounds SET instrument = 'other' WHERE instrument = 'asa'",
    "ALTER TABLE rounds DROP CONSTRAINT ck_rounds_instrument_valid",
    "ALTER TABLE rounds ADD CONSTRAINT ck_rounds_instrument_valid CHECK ("
    "instrument IN ('safe', 'priced', 'convertible_note', 'other'))",
)


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWN:
        op.execute(statement)
