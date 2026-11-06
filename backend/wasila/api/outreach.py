"""Investor email outreach: ``/v1/outreach`` (Wasila v1.0.0.0).

- ``GET|PUT /v1/outreach/mail-settings``: the workspace's mail account (owner only to change;
  the password is sealed and never returned).
- ``/v1/outreach/messages``: drafts and sent messages. ``POST …/{id}/send`` sends one draft
  now (``wasila:write``) and writes an ``email`` activity; ``POST …/{id}/replied`` records
  a reply. ``POST /v1/outreach/draft`` asks Claude for a personal draft.
- ``/v1/outreach/campaigns``: a template sent to many investors as reviewed drafts;
  ``POST …/{id}/drafts`` creates them, ``GET /v1/outreach/follow-ups`` lists no-replies due.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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
    require_owner_session,
)
from wasila.core.refs import resolve_round
from wasila.models.room import Campaign, OutreachMessage
from wasila.schemas.common import ERROR_RESPONSES, StrictInput, Timestamp
from wasila.services import claude as claude_svc
from wasila.services import master_list as ml_svc
from wasila.services import outreach as svc
from wasila.services import workspace_secrets as secrets_svc

router = APIRouter(prefix="/v1/outreach", tags=["outreach"], responses=ERROR_RESPONSES)


class MailIn(StrictInput):
    host: str = Field(..., min_length=1, max_length=253)
    port: int = Field(587, ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    username: str | None = Field(None, max_length=254)
    password: str | None = Field(None, max_length=500)
    from_email: str = Field(..., min_length=3, max_length=254)
    from_name: str | None = Field(None, max_length=120)
    reply_to: str | None = Field(None, max_length=254)
    bcc_self: bool = True


class MailOut(BaseModel):
    configured: bool
    host: str | None = None
    port: int | None = None
    security: str | None = None
    username: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to: str | None = None
    bcc_self: bool = True
    password_set: bool = False


async def _mail_out(db: AsyncSession, ws: WorkspaceContext) -> MailOut:
    m = await svc.get_mail(db, ws)
    if m is None:
        return MailOut(configured=False)
    pw = await secrets_svc.get_row(db, ws, "smtp")
    return MailOut(
        configured=True,
        host=m.host,
        port=m.port,
        security=m.security,
        username=m.username,
        from_email=m.from_email,
        from_name=m.from_name,
        reply_to=m.reply_to,
        bcc_self=m.bcc_self,
        password_set=pw is not None,
    )


@router.get("/mail-settings", response_model=MailOut)
async def get_mail(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> MailOut:
    return await _mail_out(db, ws)


@router.put(
    "/mail-settings", response_model=MailOut, dependencies=[Depends(require_owner_session())]
)
async def put_mail(
    body: MailIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MailOut:
    fields = body.model_dump(exclude={"password"})
    await svc.put_mail(db, ws, fields=fields, password=body.password, now=now)
    await db.commit()
    return await _mail_out(db, ws)


# --- messages -------------------------------------------------------------------------------------


class Attachment(BaseModel):
    document_id: str
    version: int
    filename: str
    size_bytes: int
    title: str | None = None


class MessageOut(BaseModel):
    id: UUID
    investor_id: UUID
    campaign_id: UUID | None
    kind: str
    to_email: str
    subject: str
    body: str
    attachments: list[Attachment]
    status: str
    drafted_by: str
    error: str | None
    sent_at: Timestamp | None
    replied_at: Timestamp | None
    created_at: Timestamp
    updated_at: Timestamp


class MessagePage(BaseModel):
    data: list[MessageOut]


def _msg(m: OutreachMessage) -> MessageOut:
    return MessageOut(
        id=m.id,
        investor_id=m.investor_id,
        campaign_id=m.campaign_id,
        kind=m.kind,
        to_email=m.to_email,
        subject=m.subject,
        body=m.body,
        attachments=[Attachment(**a) for a in m.attachments],
        status=m.status,
        drafted_by=m.drafted_by,
        error=m.error,
        sent_at=m.sent_at,
        replied_at=m.replied_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class MessageIn(StrictInput):
    investor_id: UUID
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=50000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    kind: Literal["outreach", "update", "follow_up"] = "outreach"
    to_email: str | None = Field(None, max_length=254)
    round: str | None = Field(None, max_length=200)


class MessagePatch(StrictInput):
    subject: str | None = Field(None, min_length=1, max_length=300)
    body: str | None = Field(None, min_length=1, max_length=50000)
    attachment_ids: list[UUID] | None = Field(None, max_length=10)
    to_email: str | None = Field(None, max_length=254)


class DraftIn(StrictInput):
    investor_id: UUID
    kind: Literal["outreach", "update"] = "outreach"
    instructions: str | None = Field(None, max_length=2000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    round: str | None = Field(None, max_length=200)


class RepliedIn(StrictInput):
    note: str | None = Field(None, max_length=5000)


@router.get("/messages", response_model=MessagePage)
async def list_messages(
    investor_id: UUID | None = None,
    campaign_id: UUID | None = None,
    status: Literal["draft", "sending", "sent", "failed"] | None = None,
    limit: int = Query(100, ge=1, le=500),
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> MessagePage:
    rows = await svc.list_messages(
        db, ws, investor_id=investor_id, campaign_id=campaign_id, status=status, limit=limit
    )
    return MessagePage(data=[_msg(m) for m in rows])


@router.post("/messages", status_code=201, response_model=MessageOut)
async def create_message(
    body: MessageIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessageOut:
    rnd = await resolve_round(db, ws, body.round, required=False)
    m = await svc.create_draft(
        db,
        ws,
        investor_id=body.investor_id,
        subject=body.subject,
        body=body.body,
        attachment_ids=body.attachment_ids,
        kind=body.kind,
        to_email=body.to_email,
        round_id=rnd.id if rnd else None,
        now=now,
    )
    await db.commit()
    return _msg(m)


@router.post("/draft", status_code=201, response_model=MessageOut)
async def claude_draft(
    body: DraftIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessageOut:
    """Claude writes a personal draft (warm letter or update). It is saved as a draft only."""
    inv = await svc._investor(db, ws, body.investor_id)
    refs = await svc.attachment_refs(db, ws, body.attachment_ids)
    best = ml_svc.best_path(await ml_svc.list_intros(db, ws, inv.id))
    subject, text = await claude_svc.draft_email(
        db,
        ws,
        inv,
        kind=body.kind,
        instructions=body.instructions,
        attachments=[a["title"] for a in refs],
        connector=best.connector_name if best else inv.warm_intro_by,
    )
    rnd = await resolve_round(db, ws, body.round, required=False)
    m = await svc.create_draft(
        db,
        ws,
        investor_id=inv.id,
        subject=subject,
        body=text,
        attachment_ids=body.attachment_ids,
        kind=body.kind,
        round_id=rnd.id if rnd else None,
        drafted_by="claude",
        now=now,
    )
    await db.commit()
    return _msg(m)


@router.get("/messages/{msg_id}", response_model=MessageOut)
async def get_message(
    msg_id: UUID,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> MessageOut:
    return _msg(await svc.get_message(db, ws, msg_id))


@router.patch("/messages/{msg_id}", response_model=MessageOut)
async def patch_message(
    msg_id: UUID,
    body: MessagePatch,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessageOut:
    m = await svc.update_draft(
        db,
        ws,
        msg_id,
        subject=body.subject,
        body=body.body,
        attachment_ids=body.attachment_ids,
        to_email=body.to_email,
        now=now,
    )
    await db.commit()
    return _msg(m)


@router.delete("/messages/{msg_id}", status_code=204)
async def delete_message(
    msg_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_draft(db, ws, msg_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/messages/{msg_id}/send", response_model=MessageOut)
async def send_message(
    msg_id: UUID,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessageOut:
    try:
        m = await svc.send(db, ws, msg_id, now=now)
    except svc.SendFailed:
        await db.commit()  # keep the failed status and error
        raise
    await db.commit()
    return _msg(m)


@router.post("/messages/{msg_id}/replied", response_model=MessageOut)
async def replied(
    msg_id: UUID,
    body: RepliedIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessageOut:
    m = await svc.mark_replied(db, ws, msg_id, note=body.note, now=now)
    await db.commit()
    return _msg(m)


@router.get("/follow-ups", response_model=MessagePage)
async def follow_ups(
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> MessagePage:
    return MessagePage(data=[_msg(m) for m in await svc.follow_ups_due(db, ws, now=now)])


# --- campaigns ------------------------------------------------------------------------------------


class CampaignIn(StrictInput):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Literal["outreach", "update"] = "outreach"
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=50000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    follow_up_days: int | None = Field(None, ge=1, le=90)


class CampaignOut(BaseModel):
    id: UUID
    name: str
    kind: str
    subject: str
    body: str
    attachment_ids: list[UUID]
    follow_up_days: int | None
    stats: dict[str, int]
    created_at: Timestamp


class CampaignPage(BaseModel):
    data: list[CampaignOut]


class CampaignDraftsIn(StrictInput):
    investor_ids: list[UUID] | None = Field(None, max_length=500)
    saved_list_id: UUID | None = None


class CampaignDraftsOut(BaseModel):
    created: list[MessageOut]
    skipped: list[dict[str, Any]]


async def _camp(db: AsyncSession, ws: WorkspaceContext, c: Campaign) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        name=c.name,
        kind=c.kind,
        subject=c.subject,
        body=c.body,
        attachment_ids=list(c.attachment_ids),
        follow_up_days=c.follow_up_days,
        stats=await svc.stats(db, ws, c.id),
        created_at=c.created_at,
    )


@router.get("/campaigns", response_model=CampaignPage)
async def campaigns(
    ws: WorkspaceContext = Depends(get_workspace_ctx), db: AsyncSession = Depends(get_session)
) -> CampaignPage:
    return CampaignPage(data=[await _camp(db, ws, c) for c in await svc.list_campaigns(db, ws)])


@router.post("/campaigns", status_code=201, response_model=CampaignOut)
async def create_campaign(
    body: CampaignIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> CampaignOut:
    c = await svc.create_campaign(db, ws, now=now, **body.model_dump())
    await db.commit()
    return await _camp(db, ws, c)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: UUID,
    ws: WorkspaceContext = Depends(get_workspace_ctx),
    db: AsyncSession = Depends(get_session),
) -> CampaignOut:
    return await _camp(db, ws, await svc.get_campaign(db, ws, campaign_id))


@router.post("/campaigns/{campaign_id}/drafts", response_model=CampaignDraftsOut)
async def campaign_drafts(
    campaign_id: UUID,
    body: CampaignDraftsIn,
    ws: WorkspaceContext = Depends(get_write_ctx),
    db: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_now),
) -> CampaignDraftsOut:
    """One merged draft per investor ({first_name}, {firm}, {intro_by} …). Nothing is sent."""
    ids = list(body.investor_ids or [])
    if body.saved_list_id is not None:
        row = await ml_svc.get_saved(db, ws, body.saved_list_id)
        members, _ = await ml_svc.list_members(db, ws, row, limit=500)
        ids += [m.id for m in members]
    batch = await svc.draft_campaign(db, ws, campaign_id, ids, now=now)
    await db.commit()
    return CampaignDraftsOut(created=[_msg(m) for m in batch.created], skipped=batch.skipped)
