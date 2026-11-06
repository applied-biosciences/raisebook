"""Imports: ``/v1/imports`` (SPEC §5.8). Owner: Import-Export+Ops (IE).

- ``POST /v1/imports/preview``: the plan for a CSV or prototype-JSON payload, no writes.
- ``POST /v1/imports``: apply it in one transaction (error rows skipped and reported).
- ``GET /v1/imports``: the last 50 import runs.

Preview and commit share the per-workspace ``import`` rate limit (30 per hour).
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
    rate_limit,
)
from wasila.schemas.common import ERROR_RESPONSES
from wasila.schemas.data import ImportPreview, ImportRequest, ImportResult, ImportRunList
from wasila.services import csv_io, office_import
from wasila.services import imports as svc

router = APIRouter(prefix="/v1/imports", tags=["imports"], responses=ERROR_RESPONSES)


@router.post("/preview", response_model=ImportPreview, summary="Preview an import (no writes)")
async def preview_import(
    body: ImportRequest,
    ws: WorkspaceContext = Depends(get_write_ctx),
    _rl: object = Depends(rate_limit("import")),
    db: AsyncSession = Depends(get_session),
) -> ImportPreview:
    """Map the columns (auto-mapped unless `mapping` is given), match every row against the
    workspace (email, then LinkedIn, then name + firm) and against earlier rows, and return
    the action per row with counts. Nothing is written."""
    # Every row comes back, so the review can list and filter all of them (P1-10).
    return await svc.preview(db, ws, body, max_rows=csv_io.MAX_ROWS)


@router.post("", response_model=ImportResult, summary="Import investors")
async def run_import(
    body: ImportRequest,
    ws: WorkspaceContext = Depends(get_write_ctx),
    _rl: object = Depends(rate_limit("import")),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> ImportResult:
    """Apply the import in one transaction. Rows with errors are skipped and listed in
    `errors`; every other row is created, updated or skipped exactly as the preview said."""
    result = await svc.commit(db, ws, body, now=now)
    await db.commit()
    return result


@router.get("", response_model=ImportRunList, summary="Recent imports")
async def list_imports(
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> ImportRunList:
    return ImportRunList(data=await svc.list_runs(db, ws))


class ConvertedTable(BaseModel):
    name: str
    header: list[str]
    rows: int
    csv: str


class ConvertOut(BaseModel):
    filename: str
    tables: list[ConvertedTable]


@router.post("/convert", response_model=ConvertOut, summary="Read tables from Excel or Word")
async def convert(
    request: Request,
    x_filename: str = Header(..., max_length=600),
    ws: WorkspaceContext = Depends(get_write_ctx),
    _rl: object = Depends(rate_limit("import")),
) -> ConvertOut:
    """Wasila: send a ``.xlsx``, ``.docx`` or ``.csv`` file as the raw body (its name in
    ``X-Filename``). Every sheet or table comes back as CSV text for ``/v1/imports/preview``.
    Nothing is written."""
    name = unquote(x_filename)
    tables = office_import.convert(name, await request.body())
    return ConvertOut(
        filename=name,
        tables=[
            ConvertedTable(name=t.name, header=t.header, rows=t.rows, csv=t.csv) for t in tables
        ],
    )
