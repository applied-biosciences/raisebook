"""The master investor list (Wasila v1.0.0.0).

- ``POST /v1/master-list/search``: structured filters (country, type, tags, has email,
  not contacted, in/not in a round, custom field values) over every workspace investor.
- ``POST /v1/master-list/ask``: "Ask Wasila" — Claude turns a question into the same filters.
- ``/v1/investor-fields``: custom fields and AI columns; ``POST …/{id}/fill`` asks Claude to
  fill an AI column for chosen investors.
- ``PUT /v1/investors/{id}/custom``: set custom values on one investor.
- ``/v1/saved-lists``: named searches or pinned sets of investors.
- ``/v1/investors/{id}/intros`` and ``DELETE /v1/intros/{id}``: warm-intro connections.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
)
from wasila.models.investor import Investor
from wasila.models.room import IntroConnection, InvestorField, SavedList
from wasila.schemas.common import ERROR_RESPONSES, APIModel, StrictInput, Timestamp
from wasila.schemas.investors import InvestorOut
from wasila.services import claude as claude_svc
from wasila.services import investors as investors_svc
from wasila.services import master_list as svc

router = APIRouter(tags=["master list"], responses=ERROR_RESPONSES)


class FiltersIn(StrictInput):
    q: str | None = Field(None, max_length=200)
    countries: list[str] = Field(default_factory=list, max_length=20)
    types: list[str] = Field(default_factory=list, max_length=10)
    tags_any: list[str] = Field(default_factory=list, max_length=20)
    has_email: bool | None = None
    not_contacted: bool | None = None
    in_round: str | None = Field(None, max_length=200)
    not_in_round: str | None = Field(None, max_length=200)
    custom: dict[str, str] = Field(default_factory=dict)


class SearchIn(FiltersIn):
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0, le=100000)


class IntroBrief(BaseModel):
    connector_name: str
    strength: int
    relationship: str | None = None


class SearchOut(BaseModel):
    filters: dict[str, Any]
    total: int
    data: list[InvestorOut]
    intros: dict[str, IntroBrief] = {}
    explanation: str | None = None


class AskIn(StrictInput):
    question: str = Field(..., min_length=3, max_length=1000)
    limit: int = Field(100, ge=1, le=500)


class Facets(BaseModel):
    total: int
    countries: list[dict[str, Any]]
    types: list[dict[str, Any]]


async def _search_out(
    db: AsyncSession,
    ws: WorkspaceContext,
    f: svc.Filters,
    *,
    limit: int,
    offset: int = 0,
    explanation: str | None = None,
) -> SearchOut:
    rows, total = await svc.search(db, ws, f, limit=limit, offset=offset)
    paths = await svc.best_paths(db, ws, [r.id for r in rows])
    return SearchOut(
        filters=f.to_dict(),
        total=total,
        data=await investors_svc.present(db, ws, rows, with_rounds=False),
        intros={
            str(k): IntroBrief(
                connector_name=v.connector_name, strength=v.strength, relationship=v.relationship
            )
            for k, v in paths.items()
        },
        explanation=explanation,
    )


@router.get("/v1/master-list/facets", response_model=Facets)
async def facets(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> Facets:
    return Facets(**await svc.facets(db, ws))


@router.post("/v1/master-list/search", response_model=SearchOut)
async def search(
    body: SearchIn,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> SearchOut:
    f = svc.Filters.from_dict(body.model_dump(exclude={"limit", "offset"}))
    return await _search_out(db, ws, f, limit=body.limit, offset=body.offset)


@router.post("/v1/master-list/ask", response_model=SearchOut)
async def ask(
    body: AskIn,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> SearchOut:
    """Ask Wasila: Claude reads only the question and returns filters; the search runs here."""
    res = await claude_svc.ask(db, ws, body.question)
    return await _search_out(db, ws, res.filters, limit=body.limit, explanation=res.explanation)


# --- custom fields and AI columns -----------------------------------------------------------------


class FieldIn(StrictInput):
    label: str = Field(..., min_length=1, max_length=80)
    kind: Literal["text", "number", "yes_no", "select", "url", "ai"] = "text"
    options: list[str] = Field(default_factory=list, max_length=50)
    prompt: str | None = Field(None, max_length=2000)


class FieldOut(APIModel):
    id: UUID
    key: str
    label: str
    kind: str
    options: list[str]
    prompt: str | None
    position: int


class FieldList(BaseModel):
    data: list[FieldOut]


class FillIn(StrictInput):
    investor_ids: list[UUID] = Field(..., min_length=1, max_length=50)
    overwrite: bool = False


class FillOut(BaseModel):
    filled: dict[str, str]
    skipped: list[str]


@router.get("/v1/investor-fields", response_model=FieldList)
async def list_fields(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> FieldList:
    return FieldList(data=[FieldOut.model_validate(f) for f in await svc.list_fields(db, ws)])


@router.post("/v1/investor-fields", status_code=201, response_model=FieldOut)
async def create_field(
    body: FieldIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> FieldOut:
    row = await svc.create_field(
        db, ws, label=body.label, kind=body.kind, options=body.options, prompt=body.prompt, now=now
    )
    await db.commit()
    return FieldOut.model_validate(row)


@router.delete("/v1/investor-fields/{field_id}", status_code=204)
async def delete_field(
    field_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_field(db, ws, field_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/v1/investor-fields/{field_id}/fill", response_model=FillOut)
async def fill_ai_column(
    field_id: UUID,
    body: FillIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> FillOut:
    """Claude answers the AI column's prompt for each investor (public profile data only)."""
    fld: InvestorField = await svc.get_field(db, ws, field_id)
    if fld.kind != "ai" or not fld.prompt:
        from wasila.core.errors import ValidationFailed

        raise ValidationFailed("field_id", "Only AI columns can be filled by Claude.")
    ids = list(dict.fromkeys(body.investor_ids))
    invs = list(
        (
            await db.scalars(
                select(Investor).where(
                    Investor.workspace_id == ws.workspace_id, Investor.id.in_(ids)
                )
            )
        ).all()
    )
    if len(invs) != len(ids):
        from wasila.core.errors import NotFound

        raise NotFound("Investor not found.")
    company = await claude_svc.company_context(db, ws)
    filled: dict[str, str] = {}
    skipped: list[str] = []
    for inv in invs:
        if not body.overwrite and (inv.custom or {}).get(fld.key):
            skipped.append(str(inv.id))
            continue
        value = await claude_svc.ai_value(db, ws, fld.prompt, inv, company)
        await svc.set_custom(db, ws, inv.id, {fld.key: value}, now=now)
        filled[str(inv.id)] = value
    await db.commit()
    return FillOut(filled=filled, skipped=skipped)


class CustomIn(StrictInput):
    values: dict[str, Any]


@router.put("/v1/investors/{investor_id}/custom", response_model=InvestorOut)
async def set_custom(
    investor_id: UUID,
    body: CustomIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvestorOut:
    inv = await svc.set_custom(db, ws, investor_id, body.values, now=now)
    await db.commit()
    return await investors_svc.present_one(db, ws, inv)


# --- saved lists ----------------------------------------------------------------------------------


class ListIn(StrictInput):
    name: str = Field(..., min_length=1, max_length=120)
    question: str | None = Field(None, max_length=1000)
    filters: FiltersIn | None = None
    investor_ids: list[UUID] | None = Field(None, max_length=5000)


class ListOut(APIModel):
    id: UUID
    name: str
    question: str | None
    filters: dict[str, Any]
    pinned: int
    created_at: Timestamp
    updated_at: Timestamp


class ListPage(BaseModel):
    data: list[ListOut]


def _list_out(r: SavedList) -> ListOut:
    return ListOut(
        id=r.id,
        name=r.name,
        question=r.question,
        filters=r.filters,
        pinned=len(r.investor_ids),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/v1/saved-lists", response_model=ListPage)
async def saved_lists(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> ListPage:
    return ListPage(data=[_list_out(r) for r in await svc.list_saved(db, ws)])


@router.post("/v1/saved-lists", status_code=201, response_model=ListOut)
async def create_list(
    body: ListIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> ListOut:
    row = await svc.save_list(
        db,
        ws,
        name=body.name,
        filters=svc.Filters.from_dict(body.filters.model_dump() if body.filters else {}),
        question=body.question,
        investor_ids=body.investor_ids,
        now=now,
    )
    await db.commit()
    return _list_out(row)


@router.get("/v1/saved-lists/{list_id}", response_model=SearchOut)
async def open_list(
    list_id: UUID,
    limit: int = Query(500, ge=1, le=500),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> SearchOut:
    row = await svc.get_saved(db, ws, list_id)
    rows, total = await svc.list_members(db, ws, row, limit=limit)
    paths = await svc.best_paths(db, ws, [r.id for r in rows])
    return SearchOut(
        filters=row.filters,
        total=total,
        data=await investors_svc.present(db, ws, rows, with_rounds=False),
        intros={
            str(k): IntroBrief(
                connector_name=v.connector_name, strength=v.strength, relationship=v.relationship
            )
            for k, v in paths.items()
        },
        explanation=row.question,
    )


@router.delete("/v1/saved-lists/{list_id}", status_code=204)
async def delete_list(
    list_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_saved(db, ws, list_id)
    await db.commit()
    return Response(status_code=204)


# --- warm intros ----------------------------------------------------------------------------------


class IntroIn(StrictInput):
    connector_name: str = Field(..., min_length=1, max_length=120)
    connector_email: str | None = Field(None, max_length=254)
    relationship: str | None = Field(None, max_length=200)
    strength: int = Field(2, ge=1, le=3)
    notes: str | None = Field(None, max_length=2000)


class IntroOut(APIModel):
    id: UUID
    investor_id: UUID
    connector_name: str
    connector_email: str | None
    relationship: str | None
    strength: int
    strength_label: str
    notes: str | None
    created_at: Timestamp


class IntroList(BaseModel):
    data: list[IntroOut]
    best: IntroOut | None = None


def _intro(c: IntroConnection) -> IntroOut:
    return IntroOut(
        id=c.id,
        investor_id=c.investor_id,
        connector_name=c.connector_name,
        connector_email=c.connector_email,
        relationship=c.relationship,
        strength=c.strength,
        strength_label=svc.STRENGTH.get(c.strength, ""),
        notes=c.notes,
        created_at=c.created_at,
    )


@router.get("/v1/investors/{investor_id}/intros", response_model=IntroList)
async def intros(
    investor_id: UUID,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> IntroList:
    rows = await svc.list_intros(db, ws, investor_id)
    best = svc.best_path(rows)
    return IntroList(data=[_intro(r) for r in rows], best=_intro(best) if best else None)


@router.post("/v1/investors/{investor_id}/intros", status_code=201, response_model=IntroOut)
async def add_intro(
    investor_id: UUID,
    body: IntroIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> IntroOut:
    row = await svc.add_intro(db, ws, investor_id, now=now, **body.model_dump())
    await db.commit()
    return _intro(row)


@router.delete("/v1/intros/{intro_id}", status_code=204)
async def delete_intro(
    intro_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_intro(db, ws, intro_id)
    await db.commit()
    return Response(status_code=204)
