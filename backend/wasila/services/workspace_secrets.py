"""Sealed workspace secrets (Wasila v1.0.0.0): the Anthropic API key and the SMTP password.

Envelope encryption exactly like the OpenRouter key (``core/secrets.py``): a DEK per secret,
wrapped by the server KEK, with the workspace id and the secret kind as AAD. Only ``last4``
is ever returned; nothing here logs or returns the secret itself. Without
``WASILA_SECRETS_KEK`` secrets cannot be saved (``secrets_unavailable``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.auth.principal import WorkspaceContext
from wasila.core import secrets as sec
from wasila.core.errors import APIError
from wasila.models.room import WorkspaceSecret

SecretKind = Literal["anthropic", "smtp"]


class SecretsUnavailable(APIError):
    status_code = 503
    code = "secrets_unavailable"
    default_message = (
        "This server cannot store secrets yet. The operator must set WASILA_SECRETS_KEK "
        "(generate one with `wasilactl secrets gen-kek`)."
    )


def aad(workspace_id: UUID, kind: str) -> bytes:
    return b"wsl:" + kind.encode("ascii") + b":" + workspace_id.bytes


def _ring() -> sec.Keyring:
    ring = sec.get_keyring()
    if ring is None:
        raise SecretsUnavailable()
    return ring


async def get_row(
    db: AsyncSession, ws: WorkspaceContext, kind: SecretKind
) -> WorkspaceSecret | None:
    row: WorkspaceSecret | None = await db.scalar(
        select(WorkspaceSecret).where(
            WorkspaceSecret.workspace_id == ws.workspace_id, WorkspaceSecret.kind == kind
        )
    )
    return row


async def put(
    db: AsyncSession, ws: WorkspaceContext, kind: SecretKind, value: str, *, now: datetime
) -> WorkspaceSecret:
    sealed = sec.seal(value.strip(), aad=aad(ws.workspace_id, kind), ring=_ring())
    row = await get_row(db, ws, kind)
    if row is None:
        row = WorkspaceSecret(workspace_id=ws.workspace_id, kind=kind)
        db.add(row)
    row.ciphertext = sealed.ciphertext
    row.nonce = sealed.nonce
    row.dek_wrapped = sealed.dek_wrapped
    row.dek_nonce = sealed.dek_nonce
    row.kek_id = sealed.kek_id
    row.last4 = sec.last4(value)
    row.set_at = now
    row.set_by_user_id = ws.actor.user_id
    await db.flush()
    return row


async def remove(db: AsyncSession, ws: WorkspaceContext, kind: SecretKind) -> bool:
    res = await db.execute(
        delete(WorkspaceSecret).where(
            WorkspaceSecret.workspace_id == ws.workspace_id, WorkspaceSecret.kind == kind
        )
    )
    await db.flush()
    return bool(getattr(res, "rowcount", 0))


async def reveal(db: AsyncSession, ws: WorkspaceContext, kind: SecretKind) -> str | None:
    """The plaintext, for use inside one call only (never returned or logged)."""
    row = await get_row(db, ws, kind)
    if row is None:
        return None
    sealed = sec.Sealed(row.ciphertext, row.nonce, row.dek_wrapped, row.dek_nonce, row.kek_id)
    try:
        return sec.open_sealed(sealed, aad=aad(ws.workspace_id, kind), ring=_ring())
    except sec.SecretUnavailable as exc:
        raise SecretsUnavailable(
            "The saved secret cannot be opened with this server's key. Save it again."
        ) from exc
