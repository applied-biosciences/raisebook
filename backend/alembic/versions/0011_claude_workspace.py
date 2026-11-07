"""Claude: the Anthropic workspace a user-scoped API key bills to.

An Anthropic key that is not scoped to a workspace needs an ``anthropic-workspace-id`` header
on every call. ``claude_settings.anthropic_workspace_id`` keeps that id (it is not a secret).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE claude_settings
          ADD COLUMN anthropic_workspace_id text NULL
            CONSTRAINT claude_settings_anthropic_workspace_id_check
            CHECK (anthropic_workspace_id ~ '^wrkspc_[A-Za-z0-9]{8,64}$')
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE claude_settings DROP COLUMN anthropic_workspace_id")
