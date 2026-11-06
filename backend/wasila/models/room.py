"""Wasila tables (migration 0010): the Funding Room, sealed workspace secrets, Claude and mail
settings, outreach, warm intros, saved lists, custom fields and funding costs.

The migration is the source of truth; these mappings mirror it. Every row is scoped to a
workspace and every service filters by ``ws.workspace_id`` (an id from another workspace is
404).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wasila.core.database import Base
from wasila.models._common import CreatedAtMixin, TimestampMixin, pk


def _ws_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )


class ActorMixin:
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'user'"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_label: Mapped[str | None] = mapped_column(Text)
    via: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'web'"))


class InvestorField(TimestampMixin, Base):
    __tablename__ = "investor_fields"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_investor_fields_key"),)

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'text'"))
    options: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'"), default=list
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class RoomDocument(ActorMixin, TimestampMixin, Base):
    __tablename__ = "funding_room_documents"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    folder: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    confidentiality: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'investors'")
    )
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'all'"))
    is_deck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoomVersion(ActorMixin, CreatedAtMixin, Base):
    __tablename__ = "funding_room_versions"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)


class RoomLink(ActorMixin, CreatedAtMixin, Base):
    __tablename__ = "funding_room_links"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    investor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    label: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoomEvent(ActorMixin, CreatedAtMixin, Base):
    __tablename__ = "funding_room_events"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )


class WorkspaceSecret(Base):
    __tablename__ = "workspace_secrets"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dek_wrapped: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dek_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_id: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str] = mapped_column(Text, nullable=False)
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ClaudeSettings(Base):
    __tablename__ = "claude_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'claude-sonnet-5-5'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MailSettings(Base):
    __tablename__ = "mail_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    host: Mapped[str] = mapped_column(Text, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="587")
    security: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'starttls'"))
    username: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    from_name: Mapped[str | None] = mapped_column(Text)
    reply_to: Mapped[str | None] = mapped_column(CITEXT)
    bcc_self: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Campaign(ActorMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'outreach'"))
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'"), default=list
    )
    follow_up_days: Mapped[int | None] = mapped_column(Integer)


class OutreachMessage(ActorMixin, TimestampMixin, Base):
    __tablename__ = "outreach_messages"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    investor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'outreach'"))
    to_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    drafted_by: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'person'"), default="person"
    )
    error: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class IntroConnection(ActorMixin, TimestampMixin, Base):
    __tablename__ = "intro_connections"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    investor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    connector_name: Mapped[str] = mapped_column(Text, nullable=False)
    connector_email: Mapped[str | None] = mapped_column(CITEXT)
    relationship: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")
    notes: Mapped[str | None] = mapped_column(Text)


class SavedList(ActorMixin, TimestampMixin, Base):
    __tablename__ = "saved_lists"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )
    investor_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'"), default=list
    )


class FundingCostLine(TimestampMixin, Base):
    __tablename__ = "funding_cost_lines"

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = _ws_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    grp: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    y1: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    y2: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    y3: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    y4: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0", default=0)
    tranche: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
