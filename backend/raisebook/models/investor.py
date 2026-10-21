"""Investor contacts at workspace level, reusable across rounds (SPEC §3.4), and the
linked-card groups they can belong to (migration 0009).

``linkedin_key``, ``name_key`` and ``search_text`` are maintained by
``services/normalize.py`` on every write and never set from input.
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from raisebook.core.database import Base
from raisebook.models._common import TimestampMixin, check_in, pk
from raisebook.models.enums import InvestorType


class Investor(TimestampMixin, Base):
    __tablename__ = "investors"
    __table_args__ = (
        check_in("type", InvestorType),
        UniqueConstraint("workspace_id", "id", name="uq_investors_workspace_id_id"),
        ForeignKeyConstraint(
            ["workspace_id", "group_id"],
            ["investor_groups.workspace_id", "investor_groups.id"],
            name="fk_investors_workspace_group",
        ),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    firm: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'other'"))
    check_min: Mapped[int | None] = mapped_column(BigInteger)
    check_max: Mapped[int | None] = mapped_column(BigInteger)
    check_note: Mapped[str | None] = mapped_column(Text)
    stage_focus: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'"), default=list
    )
    industries: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'"), default=list
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'"), default=list
    )
    location: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    x_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    warm_intro_by: Mapped[str | None] = mapped_column(Text)
    linkedin_key: Mapped[str | None] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    # Linked cards (migration 0009): the team this investor belongs to, maintained only by
    # ``services/investor_links.py``. NULL when not linked.
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class InvestorGroup(TimestampMixin, Base):
    """Two or more investors linked as one team (for example partners at the same fund
    working the deal together). A group with fewer than two members is dissolved."""

    __tablename__ = "investor_groups"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_investor_groups_workspace_id_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
