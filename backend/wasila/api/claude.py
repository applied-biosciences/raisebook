"""Claude settings: ``/v1/claude`` (Wasila v1.0.0.0).

Only a workspace owner signed in to the web sets or removes the Anthropic API key; the key
is checked with one tiny call, sealed, and never shown again (only its last four
characters). Anyone who can read sees whether Claude is ready and which model it uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
    require_owner_session,
)
from wasila.models.room import ClaudeSettings
from wasila.schemas.common import ERROR_RESPONSES, StrictInput, Timestamp
from wasila.services import claude as svc
from wasila.services import workspace_secrets as secrets_svc

router = APIRouter(prefix="/v1/claude", tags=["claude"], responses=ERROR_RESPONSES)

Model = Literal["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5", "claude-fable-5-1"]


class ClaudeOut(BaseModel):
    ready: bool
    key_last4: str | None = None
    key_set_at: Timestamp | None = None
    model: str
    models: list[str]


class KeyIn(StrictInput):
    api_key: str = Field(..., min_length=20, max_length=300)


class ModelIn(StrictInput):
    model: Model


async def _out(db: AsyncSession, ws: WorkspaceContext) -> ClaudeOut:
    row = await secrets_svc.get_row(db, ws, "anthropic")
    return ClaudeOut(
        ready=row is not None,
        key_last4=row.last4 if row else None,
        key_set_at=row.set_at if row else None,
        model=await svc.model_for(db, ws),
        models=list(svc.MODELS),
    )


@router.get("", response_model=ClaudeOut)
async def get_claude(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> ClaudeOut:
    return await _out(db, ws)


@router.put("/key", response_model=ClaudeOut, dependencies=[Depends(require_owner_session())])
async def put_key(
    body: KeyIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> ClaudeOut:
    await svc.verify_key(db, ws, body.api_key)
    await secrets_svc.put(db, ws, "anthropic", body.api_key, now=now)
    await db.commit()
    return await _out(db, ws)


@router.delete("/key", status_code=204, dependencies=[Depends(require_owner_session())])
async def delete_key(
    ws: WorkspaceContext = Depends(get_write_ctx), db: AsyncSession = Depends(get_session)
) -> Response:
    await secrets_svc.remove(db, ws, "anthropic")
    await db.commit()
    return Response(status_code=204)


@router.patch("", response_model=ClaudeOut)
async def set_model(
    body: ModelIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> ClaudeOut:
    row = await svc.get_settings_row(db, ws)
    if row is None:
        row = ClaudeSettings(workspace_id=ws.workspace_id, model=body.model, updated_at=now)
        db.add(row)
    else:
        row.model = body.model
        row.updated_at = now
    await db.commit()
    return await _out(db, ws)
