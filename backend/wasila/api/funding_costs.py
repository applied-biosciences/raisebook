"""Funding costs: ``/v1/funding-costs`` (Wasila v1.0.0.0).

Lines (funding tranches, use of funds, yearly income and costs), a summary with KPIs (burn,
runway, funding gap), and ``POST /v1/funding-costs/import`` for an ``.xlsx`` workbook sent as
the raw body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
)
from wasila.models.room import FundingCostLine
from wasila.schemas.common import ERROR_RESPONSES, APIModel, StrictInput
from wasila.services import funding_costs as svc

router = APIRouter(prefix="/v1/funding-costs", tags=["funding costs"], responses=ERROR_RESPONSES)

Kind = Literal["funding", "use_of_funds", "income", "cost"]
Tranche = Literal["seis", "eis", "equity", "grant", "other"]


class LineIn(StrictInput):
    kind: Kind
    grp: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    currency: str | None = Field(None, min_length=3, max_length=3)
    amount: int | str | None = None
    y1: int | str | None = None
    y2: int | str | None = None
    y3: int | str | None = None
    y4: int | str | None = None
    tranche: Tranche | None = None
    objective: str | None = Field(None, max_length=500)
    position: int | None = None


class LinePatch(StrictInput):
    kind: Kind | None = None
    grp: str | None = Field(None, min_length=1, max_length=80)
    name: str | None = Field(None, min_length=1, max_length=200)
    currency: str | None = Field(None, min_length=3, max_length=3)
    amount: int | str | None = None
    y1: int | str | None = None
    y2: int | str | None = None
    y3: int | str | None = None
    y4: int | str | None = None
    tranche: Tranche | None = None
    objective: str | None = Field(None, max_length=500)
    position: int | None = None


class LineOut(APIModel):
    id: UUID
    kind: str
    grp: str
    name: str
    currency: str
    amount: int
    y1: int
    y2: int
    y3: int
    y4: int
    tranche: str | None
    objective: str | None
    position: int


class CostsOut(BaseModel):
    data: list[LineOut]
    summary: dict[str, Any]


async def _out(db: AsyncSession, ws: WorkspaceContext, kind: str | None = None) -> CostsOut:
    lines: list[FundingCostLine] = await svc.list_lines(db, ws, kind=kind)
    everything = lines if kind is None else await svc.list_lines(db, ws)
    return CostsOut(
        data=[LineOut.model_validate(x) for x in lines], summary=svc.summarize(everything)
    )


@router.get("", response_model=CostsOut)
async def list_costs(
    kind: Kind | None = None,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> CostsOut:
    return await _out(db, ws, kind)


class MergeField(APIModel):
    key: str
    label: str
    value: str


class MergeFieldsOut(APIModel):
    data: list[MergeField]


@router.get("/merge-fields", response_model=MergeFieldsOut)
async def merge_fields(
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> MergeFieldsOut:
    """The funding figures an investor update can quote as ``{key}``, with today's values.

    Campaign drafts fill them in; an empty value means the figure is not entered yet.
    """
    values = svc.merge_values(await svc.list_lines(db, ws))
    return MergeFieldsOut(
        data=[MergeField(key=k, label=label, value=values[k]) for k, label in svc.MERGE_FIELDS]
    )


@router.post("", status_code=201, response_model=LineOut)
async def create_line(
    body: LineIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> LineOut:
    row = await svc.create_line(db, ws, fields=body.model_dump(exclude_none=True), now=now)
    await db.commit()
    return LineOut.model_validate(row)


@router.patch("/{line_id}", response_model=LineOut)
async def update_line(
    line_id: UUID,
    body: LinePatch,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> LineOut:
    row = await svc.update_line(
        db, ws, line_id, fields=body.model_dump(exclude_unset=True), now=now
    )
    await db.commit()
    return LineOut.model_validate(row)


@router.delete("/{line_id}", status_code=204)
async def delete_line(
    line_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_line(db, ws, line_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/import", response_model=CostsOut)
async def import_workbook(
    request: Request,
    currency: str = Query("GBP", min_length=3, max_length=3),
    replace: bool = Query(True, description="Replace every existing line (default) or add."),
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> CostsOut:
    """Import an ``.xlsx`` workbook (raw body): a "Use of funds" sheet and a "Summary" P&L,
    or a "Wasila costs" sheet."""
    await svc.import_workbook(
        db, ws, await request.body(), currency=currency.upper(), replace=replace, now=now
    )
    await db.commit()
    return await _out(db, ws)
