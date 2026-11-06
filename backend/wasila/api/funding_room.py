"""The Funding Room: ``/v1/funding-room`` (documents, versions, share links, checklist,
activity) and the public share-link routes ``/v1/room-links/{token}``.

Reads need ``wasila:read``; changes need ``wasila:write``. A document id from another
workspace is 404. Uploads send the file as the raw request body with its name in the
``X-Filename`` header (URL-encoded), at most 25 MB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import quote, unquote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.api.deps import (
    WorkspaceContext,
    get_now,
    get_session,
    get_workspace_ctx,
    get_write_ctx,
    rate_limit,
)
from wasila.models.room import RoomDocument, RoomLink, RoomVersion
from wasila.models.workspace import Workspace
from wasila.schemas.common import ERROR_RESPONSES
from wasila.schemas.funding_room import (
    Checklist,
    ChecklistItem,
    DocumentCreate,
    DocumentList,
    DocumentOut,
    DocumentUpdate,
    EventList,
    EventOut,
    LinkCreate,
    LinkCreated,
    LinkList,
    LinkOut,
    PublicDocument,
    PublicRoom,
    VersionList,
    VersionOut,
)
from wasila.services import funding_room as svc

router = APIRouter(tags=["funding room"], responses=ERROR_RESPONSES)
P = "/v1/funding-room"


def _ver(v: RoomVersion) -> VersionOut:
    return VersionOut(
        version=v.version,
        filename=v.filename,
        content_type=v.content_type,
        size_bytes=v.size_bytes,
        sha256=v.sha256,
        note=v.note,
        created_at=v.created_at,
        actor_label=v.actor_label,
    )


async def _doc_out(
    db: AsyncSession, ws: WorkspaceContext, docs: list[RoomDocument]
) -> list[DocumentOut]:
    latest: dict[UUID, RoomVersion] = {}
    pairs = [(d.id, d.current_version) for d in docs if d.current_version > 0]
    if pairs:
        rows = await db.scalars(
            select(RoomVersion).where(
                RoomVersion.workspace_id == ws.workspace_id,
                RoomVersion.document_id.in_([p[0] for p in pairs]),
            )
        )
        want = dict(pairs)
        for v in rows:
            if want.get(v.document_id) == v.version:
                latest[v.document_id] = v
    return [
        DocumentOut(
            id=d.id,
            title=d.title,
            category=d.category,
            category_label=svc.CATEGORIES.get(d.category, d.category),
            folder=d.folder,
            description=d.description,
            confidentiality=d.confidentiality,
            review_status=d.review_status,
            jurisdiction=d.jurisdiction,
            is_deck=d.is_deck,
            current_version=d.current_version,
            latest=_ver(latest[d.id]) if d.id in latest else None,
            reviewed_at=d.reviewed_at,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]


def _link(link: RoomLink, now: datetime) -> LinkOut:
    return LinkOut(
        id=link.id,
        label=link.label,
        investor_id=link.investor_id,
        document_ids=list(link.document_ids),
        expires_at=link.expires_at,
        revoked_at=link.revoked_at,
        view_count=link.view_count,
        last_viewed_at=link.last_viewed_at,
        state=svc.link_state(link, now),
        created_at=link.created_at,
    )


def file_response(v: RoomVersion) -> Response:
    safe = v.filename.encode("ascii", "replace").decode().replace('"', "")
    return Response(
        content=v.data,
        media_type=v.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(v.filename)}"
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(f"{P}/documents", response_model=DocumentList)
async def list_documents(
    category: str | None = Query(None, max_length=40),
    review_status: str | None = Query(None, max_length=20),
    jurisdiction: str | None = Query(None, max_length=10),
    q: str | None = Query(None, max_length=200),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> DocumentList:
    docs = await svc.list_documents(
        db, ws, category=category, review_status=review_status, jurisdiction=jurisdiction, q=q
    )
    return DocumentList(
        data=await _doc_out(db, ws, docs),
        counts=await svc.counts(db, ws),
        categories=svc.CATEGORIES,
    )


@router.post(f"{P}/documents", status_code=201, response_model=DocumentOut)
async def create_document(
    body: DocumentCreate,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> DocumentOut:
    doc = await svc.create_document(db, ws, fields=body.model_dump(), now=now)
    await db.commit()
    return (await _doc_out(db, ws, [doc]))[0]


@router.get(f"{P}/documents/{{doc_id}}", response_model=DocumentOut)
async def get_document(
    doc_id: UUID,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> DocumentOut:
    return (await _doc_out(db, ws, [await svc.get_document(db, ws, doc_id)]))[0]


@router.patch(f"{P}/documents/{{doc_id}}", response_model=DocumentOut)
async def update_document(
    doc_id: UUID,
    body: DocumentUpdate,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> DocumentOut:
    doc, _ = await svc.update_document(
        db, ws, doc_id, fields=body.model_dump(exclude_unset=True), now=now
    )
    await db.commit()
    return (await _doc_out(db, ws, [doc]))[0]


@router.delete(f"{P}/documents/{{doc_id}}", status_code=204)
async def delete_document(
    doc_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> Response:
    await svc.delete_document(db, ws, doc_id, now=now)
    await db.commit()
    return Response(status_code=204)


@router.post(f"{P}/documents/{{doc_id}}/versions", status_code=201, response_model=VersionOut)
async def upload_version(
    doc_id: UUID,
    request: Request,
    x_filename: str = Header(..., max_length=600),
    x_note: str | None = Header(None, max_length=1500),
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> VersionOut:
    """Upload a new version: the file is the raw body, its name in ``X-Filename``."""
    data = await request.body()
    ver = await svc.add_version(
        db,
        ws,
        doc_id,
        filename=unquote(x_filename),
        data=data,
        note=unquote(x_note) if x_note else None,
        now=now,
    )
    await db.commit()
    return _ver(ver)


@router.get(f"{P}/documents/{{doc_id}}/versions", response_model=VersionList)
async def list_versions(
    doc_id: UUID,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> VersionList:
    return VersionList(data=[_ver(v) for v in await svc.list_versions(db, ws, doc_id)])


@router.get(f"{P}/documents/{{doc_id}}/download")
async def download(
    doc_id: UUID,
    version: int | None = Query(None, ge=1),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> Response:
    """The file of the latest (or a given) version. The download is recorded."""
    ver = await svc.get_version(db, ws, doc_id, version)
    await svc.record_download(db, ws, ver, now=now)
    await db.commit()
    return file_response(ver)


@router.get(f"{P}/links", response_model=LinkList)
async def list_links(
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> LinkList:
    return LinkList(data=[_link(x, now) for x in await svc.list_links(db, ws)])


@router.post(f"{P}/links", status_code=201, response_model=LinkCreated)
async def create_link(
    body: LinkCreate,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> LinkCreated:
    """A share link to approved documents, shown once. It expires after ``days``."""
    link, token = await svc.create_link(
        db,
        ws,
        label=body.label,
        document_ids=body.document_ids,
        investor_id=body.investor_id,
        days=body.days,
        now=now,
    )
    await db.commit()
    return LinkCreated(**_link(link, now).model_dump(), token=token)


@router.delete(f"{P}/links/{{link_id}}", response_model=LinkOut)
async def revoke_link(
    link_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> LinkOut:
    link = await svc.revoke_link(db, ws, link_id, now=now)
    await db.commit()
    return _link(link, now)


@router.get(f"{P}/checklist", response_model=Checklist)
async def checklist(
    jurisdiction: Literal["all", "us", "uk", "ksa"] = "all",
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> Checklist:
    items = await svc.checklist(db, ws, jurisdiction)
    return Checklist(jurisdiction=jurisdiction, items=[ChecklistItem(**i) for i in items])


@router.get(f"{P}/events", response_model=EventList)
async def events(
    limit: int = Query(50, ge=1, le=200),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> EventList:
    rows = await svc.list_events(db, ws, limit=limit)
    return EventList(
        data=[
            EventOut(
                id=e.id,
                document_id=e.document_id,
                kind=e.kind,
                data=e.data,
                actor_type=e.actor_type,
                actor_label=e.actor_label,
                created_at=e.created_at,
            )
            for e in rows
        ]
    )


# --- public share links (the token is the credential) -------------------------------------------


@router.get(
    "/v1/room-links/{token}",
    response_model=PublicRoom,
    dependencies=[Depends(rate_limit("anon_ip"))],
)
async def open_link(
    token: str,
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> PublicRoom:
    view = await svc.open_link(db, token, now=now)
    company = await db.scalar(select(Workspace.name).where(Workspace.id == view.link.workspace_id))
    vers = {
        v.document_id: v
        for v in await db.scalars(
            select(RoomVersion).where(
                RoomVersion.workspace_id == view.link.workspace_id,
                RoomVersion.document_id.in_([d.id for d in view.documents]),
            )
        )
        if any(d.id == v.document_id and d.current_version == v.version for d in view.documents)
    }
    await db.commit()
    return PublicRoom(
        company=company or "",
        label=view.link.label,
        expires_at=view.link.expires_at,
        documents=[
            PublicDocument(
                id=d.id,
                title=d.title,
                category_label=svc.CATEGORIES.get(d.category, d.category),
                description=d.description,
                filename=vers[d.id].filename,
                size_bytes=vers[d.id].size_bytes,
            )
            for d in view.documents
            if d.id in vers
        ],
    )


@router.get(
    "/v1/room-links/{token}/documents/{doc_id}", dependencies=[Depends(rate_limit("anon_ip"))]
)
async def link_download(
    token: str,
    doc_id: UUID,
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> Response:
    ver = await svc.link_file(db, token, doc_id, now=now)
    await db.commit()
    return file_response(ver)
