"""investor groups: linked cards (two or more investors working a deal as one team).

- ``investor_groups``: one row per team of linked investors, scoped to a workspace
  (``UNIQUE (workspace_id, id)`` so investors can point at it with a composite key).
- ``investors.group_id``: the team an investor belongs to (NULL when not linked). The
  composite FK ``(workspace_id, group_id)`` keeps every member in the group's workspace;
  deleting a group sets only ``group_id`` to NULL.

A group always has at least two members: ``services/investor_links.py`` dissolves it when
unlinking or deleting an investor leaves fewer.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = (
    """
CREATE TABLE investor_groups (
  id           uuid NOT NULL DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_investor_groups PRIMARY KEY (id),
  CONSTRAINT uq_investor_groups_workspace_id_id UNIQUE (workspace_id, id),
  CONSTRAINT fk_investor_groups_workspace FOREIGN KEY (workspace_id)
    REFERENCES workspaces (id) ON DELETE CASCADE
)
""",
    "ALTER TABLE investors ADD COLUMN group_id uuid",
    "ALTER TABLE investors ADD CONSTRAINT fk_investors_workspace_group "
    "FOREIGN KEY (workspace_id, group_id) REFERENCES investor_groups (workspace_id, id) "
    "ON DELETE SET NULL (group_id)",
    "CREATE INDEX ix_investors_ws_group ON investors (workspace_id, group_id) "
    "WHERE group_id IS NOT NULL",
)

DOWN = (
    "DROP INDEX IF EXISTS ix_investors_ws_group",
    "ALTER TABLE investors DROP CONSTRAINT IF EXISTS fk_investors_workspace_group",
    "ALTER TABLE investors DROP COLUMN IF EXISTS group_id",
    "DROP TABLE IF EXISTS investor_groups",
)


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWN:
        op.execute(statement)
