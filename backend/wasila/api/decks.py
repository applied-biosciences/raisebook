"""The deck editor: ``/v1/decks/{doc_id}`` (Wasila v1.0.0.0).

A deck is a Funding Room document whose file is a ``.pptx``. ``GET`` lists its slides and
text; ``POST …/save`` applies text edits, hidden slides and a new order and saves the result
as a new version (the old versions stay); ``POST …/suggest`` asks Claude for text edits
(nothing changes until they are saved); ``GET …/pdf`` exports the current version as PDF
when the server has LibreOffice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
)
from wasila.api.funding_room import _ver
from wasila.core.errors import ValidationFailed
from wasila.schemas.common import ERROR_RESPONSES, StrictInput
from wasila.schemas.funding_room import VersionOut
from wasila.services import claude as claude_svc
from wasila.services import decks as svc
from wasila.services import funding_room as room_svc
from wasila.services import investors as investors_svc

router = APIRouter(prefix="/v1/decks", tags=["decks"], responses=ERROR_RESPONSES)


class DeckOut(BaseModel):
    document_id: UUID
    title: str
    version: int
    filename: str
    width: int
    height: int
    slides: list[dict[str, Any]]


class EditIn(StrictInput):
    slide: int = Field(..., ge=1, le=500)
    shape: int = Field(..., ge=0)
    text: str = Field(..., max_length=4000)


class SaveIn(StrictInput):
    base_version: int = Field(..., ge=1)
    edits: list[EditIn] = Field(default_factory=list, max_length=500)
    hidden: list[int] | None = Field(None, max_length=500)
    order: list[int] | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=255)


class SuggestIn(StrictInput):
    instruction: str = Field(..., min_length=3, max_length=2000)
    investor_id: UUID | None = None


class SuggestOut(BaseModel):
    suggestions: list[dict[str, Any]]


async def _deck_version(
    db: AsyncSession, ws: WorkspaceContext, doc_id: UUID, version: int | None
) -> Any:
    ver = await room_svc.get_version(db, ws, doc_id, version)
    if room_svc.extension(ver.filename) != "pptx":
        raise ValidationFailed("doc_id", "Only PowerPoint (.pptx) documents can be edited here.")
    return ver


@router.get("/{doc_id}", response_model=DeckOut)
async def read_deck(
    doc_id: UUID,
    version: int | None = Query(None, ge=1),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> DeckOut:
    doc = await room_svc.get_document(db, ws, doc_id)
    ver = await _deck_version(db, ws, doc_id, version)
    info = svc.read(ver.data)
    return DeckOut(
        document_id=doc.id,
        title=doc.title,
        version=ver.version,
        filename=ver.filename,
        width=info["width"],
        height=info["height"],
        slides=info["slides"],
    )


@router.post("/{doc_id}/save", status_code=201, response_model=VersionOut)
async def save_deck(
    doc_id: UUID,
    body: SaveIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> VersionOut:
    """Apply the changes to ``base_version`` and save them as the next version."""
    ver = await _deck_version(db, ws, doc_id, body.base_version)
    data = svc.apply(
        ver.data,
        edits=[svc.Edit(e.slide, e.shape, e.text) for e in body.edits],
        hidden=body.hidden,
        order=body.order,
    )
    name = (body.filename or ver.filename).strip()
    if not name.lower().endswith(".pptx"):
        name += ".pptx"
    new = await room_svc.add_version(
        db,
        ws,
        doc_id,
        filename=name,
        data=data,
        note=body.note or f"Edited in Wasila from version {ver.version}",
        now=now,
    )
    await db.commit()
    return _ver(new)


@router.post("/{doc_id}/suggest", response_model=SuggestOut)
async def suggest(
    doc_id: UUID,
    body: SuggestIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> SuggestOut:
    ver = await _deck_version(db, ws, doc_id, None)
    info = svc.read(ver.data)
    inv = await investors_svc.get(db, ws, body.investor_id) if body.investor_id else None
    slides = [
        {
            "slide": s["slide"],
            "shapes": [{"shape": x["shape"], "text": x["text"]} for x in s["shapes"]],
        }
        for s in info["slides"]
        if not s["hidden"]
    ]
    out = await claude_svc.deck_suggestions(
        db, ws, slides, instruction=body.instruction, investor=inv
    )
    return SuggestOut(suggestions=out)


@router.get("/{doc_id}/pdf")
async def deck_pdf(
    doc_id: UUID,
    version: int | None = Query(None, ge=1),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    ver = await _deck_version(db, ws, doc_id, version)
    pdf = svc.to_pdf(ver.data)
    stem = ver.filename.rsplit(".", 1)[0]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
