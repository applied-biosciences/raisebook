"""Investor email outreach (Wasila v1.0.0.0): drafts, attachments, sending, campaigns,
investor updates and no-reply follow-ups.

The only writer of ``mail_settings``, ``campaigns`` and ``outreach_messages``.

- Email is sent **only** on an explicit send (a person's click, or an API/MCP caller with
  ``wasila:write`` sending one message it can see). Nothing is sent on import, on a schedule
  or in bulk without review: a campaign creates drafts, and each draft is sent on its own.
- Mail goes out through the workspace's own SMTP account (Gmail, Outlook, any provider), with
  the password sealed in ``workspace_secrets``. ``WASILA_OUTREACH_BACKEND=memory`` keeps
  messages in :data:`SENT` instead (tests and smoke runs never reach a mail server).
- Attachments are chosen by hand from **approved** Funding Room documents (their current
  version), and recorded with the message.
- Every sent message writes an ``email`` activity (outbound) on the investor's timeline in
  the same transaction, with the subject, recipient and attachment names.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from wasila.auth.principal import WorkspaceContext
from wasila.config import get_settings
from wasila.core.errors import APIError, Conflict, NotFound, ValidationFailed
from wasila.models.investor import Investor
from wasila.models.room import (
    Campaign,
    MailSettings,
    OutreachMessage,
    RoomDocument,
    RoomVersion,
)
from wasila.services import activities as act_svc
from wasila.services import workspace_secrets as secrets_svc

log = structlog.get_logger(__name__)

MAX_ATTACH_BYTES: Final[int] = 20 * 1024 * 1024
SENT: list[EmailMessage] = []  # memory backend


def invalid(message: str, field: str = "body") -> ValidationFailed:
    return ValidationFailed(field, message)


class MailNotConfigured(APIError):
    status_code = 422
    code = "mail_not_configured"
    default_message = "Set up your mail account in Settings → Email before sending."


class SendFailed(APIError):
    status_code = 502
    code = "send_failed"
    default_message = "Your mail server refused the message. Check Settings → Email and try again."


def _actor_cols(ws: WorkspaceContext) -> dict[str, Any]:
    a = ws.actor
    return {
        "actor_type": a.type.value,
        "actor_user_id": a.user_id,
        "actor_label": a.label,
        "via": a.via.value,
    }


# --- mail settings ------------------------------------------------------------------------------


async def get_mail(db: AsyncSession, ws: WorkspaceContext) -> MailSettings | None:
    row: MailSettings | None = await db.scalar(
        select(MailSettings).where(MailSettings.workspace_id == ws.workspace_id)
    )
    return row


async def put_mail(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    fields: dict[str, Any],
    password: str | None,
    now: datetime,
) -> MailSettings:
    row = await get_mail(db, ws)
    if row is None:
        row = MailSettings(workspace_id=ws.workspace_id)
        db.add(row)
    for k in (
        "host",
        "port",
        "security",
        "username",
        "from_email",
        "from_name",
        "reply_to",
        "bcc_self",
    ):
        if k in fields:
            setattr(row, k, fields[k])
    if row.security not in ("starttls", "ssl", "none"):
        raise invalid("security must be starttls, ssl or none.", "security")
    row.updated_at = now
    if password:
        await secrets_svc.put(db, ws, "smtp", password, now=now)
    await db.flush()
    return row


# --- drafts -------------------------------------------------------------------------------------


async def _investor(db: AsyncSession, ws: WorkspaceContext, investor_id: UUID) -> Investor:
    inv = await db.scalar(
        select(Investor).where(Investor.workspace_id == ws.workspace_id, Investor.id == investor_id)
    )
    if inv is None:
        raise NotFound("Investor not found.")
    return inv


async def attachment_refs(
    db: AsyncSession, ws: WorkspaceContext, document_ids: list[UUID]
) -> list[dict[str, Any]]:
    """Current versions of approved Funding Room documents, as stored on a message."""
    if not document_ids:
        return []
    ids = list(dict.fromkeys(document_ids))[:10]
    docs = {
        d.id: d
        for d in await db.scalars(
            select(RoomDocument).where(
                RoomDocument.workspace_id == ws.workspace_id, RoomDocument.id.in_(ids)
            )
        )
    }
    if len(docs) != len(ids):
        raise NotFound("Document not found in the Funding Room.")
    bad = [d.title for d in docs.values() if d.review_status != "approved" or d.current_version < 1]
    if bad:
        raise invalid(
            "Only approved Funding Room documents with a file can be attached: " + ", ".join(bad),
            "attachment_ids",
        )
    out: list[dict[str, Any]] = []
    for i in ids:
        d = docs[i]
        v = await db.scalar(
            select(RoomVersion).where(
                RoomVersion.workspace_id == ws.workspace_id,
                RoomVersion.document_id == d.id,
                RoomVersion.version == d.current_version,
            )
        )
        assert v is not None
        out.append(
            {
                "document_id": str(d.id),
                "version": v.version,
                "filename": v.filename,
                "size_bytes": v.size_bytes,
                "title": d.title,
            }
        )
    if sum(int(a["size_bytes"]) for a in out) > MAX_ATTACH_BYTES:
        raise invalid(
            "Attachments can be at most 20 MB in total. Share a link instead.", "attachment_ids"
        )
    return out


def render(template: str, inv: Investor, extra: dict[str, str] | None = None) -> str:
    """Mail-merge placeholders: {first_name} {name} {firm} {title} {country} {intro_by}."""
    first = inv.name.split()[0] if inv.name.split() else inv.name
    values = {
        "first_name": first,
        "name": inv.name,
        "firm": inv.firm or "",
        "title": inv.title or "",
        "country": inv.country or "",
        "intro_by": inv.warm_intro_by or "",
        **(extra or {}),
    }
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


async def create_draft(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    investor_id: UUID,
    subject: str,
    body: str,
    attachment_ids: list[UUID],
    kind: str = "outreach",
    to_email: str | None = None,
    campaign_id: UUID | None = None,
    round_id: UUID | None = None,
    drafted_by: str = "person",
    now: datetime,
) -> OutreachMessage:
    inv = await _investor(db, ws, investor_id)
    to = (to_email or inv.email or "").strip()
    if not to or "@" not in to:
        raise invalid(f"{inv.name} has no email address. Add one on their file first.", "to_email")
    subject = subject.strip()
    if not 1 <= len(subject) <= 300:
        raise invalid("subject must be 1 to 300 characters.", "subject")
    if not body.strip() or len(body) > 50000:
        raise invalid("body is required (at most 50,000 characters).", "body")
    if kind not in ("outreach", "update", "follow_up"):
        raise invalid("kind must be outreach, update or follow_up.", "kind")
    msg = OutreachMessage(
        workspace_id=ws.workspace_id,
        investor_id=inv.id,
        campaign_id=campaign_id,
        round_id=round_id,
        kind=kind,
        to_email=to,
        subject=subject,
        body=body.strip(),
        attachments=await attachment_refs(db, ws, attachment_ids),
        status="draft",
        drafted_by=drafted_by,
        created_at=now,
        updated_at=now,
        **_actor_cols(ws),
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_message(db: AsyncSession, ws: WorkspaceContext, msg_id: UUID) -> OutreachMessage:
    msg = await db.scalar(
        select(OutreachMessage).where(
            OutreachMessage.workspace_id == ws.workspace_id, OutreachMessage.id == msg_id
        )
    )
    if msg is None:
        raise NotFound("Message not found.")
    return msg


async def update_draft(
    db: AsyncSession,
    ws: WorkspaceContext,
    msg_id: UUID,
    *,
    subject: str | None,
    body: str | None,
    attachment_ids: list[UUID] | None,
    to_email: str | None,
    now: datetime,
) -> OutreachMessage:
    msg = await get_message(db, ws, msg_id)
    if msg.status not in ("draft", "failed"):
        raise Conflict("This message was already sent; it cannot change.", code="already_sent")
    if subject is not None:
        if not 1 <= len(subject.strip()) <= 300:
            raise invalid("subject must be 1 to 300 characters.", "subject")
        msg.subject = subject.strip()
    if body is not None:
        if not body.strip():
            raise invalid("body is required.", "body")
        msg.body = body.strip()
    if attachment_ids is not None:
        msg.attachments = await attachment_refs(db, ws, attachment_ids)
    if to_email is not None:
        if "@" not in to_email:
            raise invalid("to_email must be an email address.", "to_email")
        msg.to_email = to_email.strip()
    msg.updated_at = now
    await db.flush()
    return msg


async def delete_draft(db: AsyncSession, ws: WorkspaceContext, msg_id: UUID) -> None:
    msg = await get_message(db, ws, msg_id)
    if msg.status == "sent":
        raise Conflict("Sent messages stay on the record.", code="already_sent")
    await db.delete(msg)
    await db.flush()


async def list_messages(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    investor_id: UUID | None = None,
    campaign_id: UUID | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[OutreachMessage]:
    stmt = select(OutreachMessage).where(OutreachMessage.workspace_id == ws.workspace_id)
    if investor_id is not None:
        await _investor(db, ws, investor_id)
        stmt = stmt.where(OutreachMessage.investor_id == investor_id)
    if campaign_id is not None:
        await get_campaign(db, ws, campaign_id)
        stmt = stmt.where(OutreachMessage.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(OutreachMessage.status == status)
    return list(
        (await db.scalars(stmt.order_by(OutreachMessage.created_at.desc()).limit(limit))).all()
    )


# --- sending ------------------------------------------------------------------------------------


@dataclass
class MailAccount:
    settings: MailSettings
    password: str | None


def _build(
    msg: OutreachMessage, acct: MailAccount, files: list[tuple[str, str, bytes]]
) -> EmailMessage:
    m = EmailMessage()
    s = acct.settings
    m["From"] = formataddr((s.from_name or "", s.from_email))
    m["To"] = msg.to_email
    m["Subject"] = msg.subject
    if s.reply_to:
        m["Reply-To"] = s.reply_to
    if s.bcc_self:
        m["Bcc"] = s.from_email
    domain = s.from_email.split("@", 1)[-1]
    m["Message-ID"] = make_msgid(domain=domain)
    m.set_content(msg.body)
    for filename, ctype, data in files:
        maintype, _, subtype = ctype.partition("/")
        m.add_attachment(
            data, maintype=maintype, subtype=subtype or "octet-stream", filename=filename
        )
    return m


def _smtp_send(m: EmailMessage, acct: MailAccount) -> None:
    s = acct.settings
    ctx = ssl.create_default_context()
    if s.security == "ssl":
        with smtplib.SMTP_SSL(s.host, s.port, timeout=30, context=ctx) as smtp:
            if s.username and acct.password:
                smtp.login(s.username, acct.password)
            smtp.send_message(m)
        return
    with smtplib.SMTP(s.host, s.port, timeout=30) as smtp:
        if s.security == "starttls":
            smtp.starttls(context=ctx)
        if s.username and acct.password:
            smtp.login(s.username, acct.password)
        smtp.send_message(m)


async def send(
    db: AsyncSession, ws: WorkspaceContext, msg_id: UUID, *, now: datetime
) -> OutreachMessage:
    """Send one draft now and record it on the investor's timeline."""
    msg = await get_message(db, ws, msg_id)
    if msg.status == "sent":
        return msg
    if msg.status == "sending":
        raise Conflict("This message is already being sent.", code="already_sending")
    settings = await get_mail(db, ws)
    backend = get_settings().outreach_backend
    if settings is None and backend != "memory":
        raise MailNotConfigured()
    if settings is None:
        settings = MailSettings(
            workspace_id=ws.workspace_id,
            host="memory",
            port=25,
            security="none",
            from_email="founder@example.com",
            bcc_self=False,
        )
    files: list[tuple[str, str, bytes]] = []
    for a in msg.attachments:
        v = await db.scalar(
            select(RoomVersion)
            .options(undefer(RoomVersion.data))
            .where(
                RoomVersion.workspace_id == ws.workspace_id,
                RoomVersion.document_id == UUID(a["document_id"]),
                RoomVersion.version == a["version"],
            )
        )
        if v is None:
            raise invalid(
                f"The attachment {a['filename']} no longer exists. Re-attach it.", "attachments"
            )
        files.append((v.filename, v.content_type, v.data))
    acct = MailAccount(
        settings, await secrets_svc.reveal(db, ws, "smtp") if backend != "memory" else None
    )
    m = _build(msg, acct, files)
    try:
        if backend == "memory":
            SENT.append(m)
        else:
            await asyncio.to_thread(_smtp_send, m, acct)
    except (smtplib.SMTPException, OSError) as exc:
        msg.status = "failed"
        msg.error = type(exc).__name__
        msg.updated_at = now
        await db.flush()
        log.warning("outreach.send_failed", error=type(exc).__name__)
        raise SendFailed() from None
    msg.status = "sent"
    msg.error = None
    msg.sent_at = now
    msg.message_id = str(m["Message-ID"])
    msg.updated_at = now
    names = ", ".join(a["filename"] for a in msg.attachments)
    activity = await act_svc.log(
        db,
        ws,
        investor_id=msg.investor_id,
        kind="email",
        now=now,
        round_id=msg.round_id,
        body=f"Sent “{msg.subject}” to {msg.to_email}" + (f" with {names}" if names else ""),
        data={
            "direction": "outbound",
            "outreach_id": str(msg.id),
            "kind": msg.kind,
            "attachments": [a["filename"] for a in msg.attachments],
        },
    )
    msg.activity_id = activity.id
    await db.flush()
    return msg


async def mark_replied(
    db: AsyncSession, ws: WorkspaceContext, msg_id: UUID, *, note: str | None, now: datetime
) -> OutreachMessage:
    msg = await get_message(db, ws, msg_id)
    if msg.status != "sent":
        raise Conflict("Only a sent message can get a reply.", code="not_sent")
    if msg.replied_at is None:
        msg.replied_at = now
        msg.updated_at = now
        await act_svc.log(
            db,
            ws,
            investor_id=msg.investor_id,
            kind="email",
            now=now,
            round_id=msg.round_id,
            body=(note or "").strip()[:5000] or f"Replied to “{msg.subject}”",
            data={"direction": "inbound", "outreach_id": str(msg.id)},
        )
        await db.flush()
    return msg


# --- campaigns ----------------------------------------------------------------------------------


async def get_campaign(db: AsyncSession, ws: WorkspaceContext, campaign_id: UUID) -> Campaign:
    row = await db.scalar(
        select(Campaign).where(Campaign.workspace_id == ws.workspace_id, Campaign.id == campaign_id)
    )
    if row is None:
        raise NotFound("Campaign not found.")
    return row


async def list_campaigns(db: AsyncSession, ws: WorkspaceContext) -> list[Campaign]:
    return list(
        (
            await db.scalars(
                select(Campaign)
                .where(Campaign.workspace_id == ws.workspace_id)
                .order_by(Campaign.created_at.desc())
            )
        ).all()
    )


async def create_campaign(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    name: str,
    kind: str,
    subject: str,
    body: str,
    attachment_ids: list[UUID],
    follow_up_days: int | None,
    now: datetime,
) -> Campaign:
    if kind not in ("outreach", "update"):
        raise invalid("kind must be outreach or update.", "kind")
    await attachment_refs(db, ws, attachment_ids)
    row = Campaign(
        workspace_id=ws.workspace_id,
        name=name.strip()[:120],
        kind=kind,
        subject=subject.strip()[:300],
        body=body.strip()[:50000],
        attachment_ids=list(dict.fromkeys(attachment_ids)),
        follow_up_days=follow_up_days,
        created_at=now,
        updated_at=now,
        **_actor_cols(ws),
    )
    db.add(row)
    await db.flush()
    return row


@dataclass
class DraftBatch:
    created: list[OutreachMessage]
    skipped: list[dict[str, str]]


async def draft_campaign(
    db: AsyncSession,
    ws: WorkspaceContext,
    campaign_id: UUID,
    investor_ids: list[UUID],
    *,
    now: datetime,
) -> DraftBatch:
    """One merged draft per investor (skipping those without email or already drafted)."""
    camp = await get_campaign(db, ws, campaign_id)
    ids = list(dict.fromkeys(investor_ids))[:500]
    invs = {
        i.id: i
        for i in await db.scalars(
            select(Investor).where(Investor.workspace_id == ws.workspace_id, Investor.id.in_(ids))
        )
    }
    if len(invs) != len(ids):
        raise NotFound("Investor not found.")
    already = set(
        (
            await db.scalars(
                select(OutreachMessage.investor_id).where(
                    OutreachMessage.workspace_id == ws.workspace_id,
                    OutreachMessage.campaign_id == camp.id,
                )
            )
        ).all()
    )
    created, skipped = [], []
    for i in ids:
        inv = invs[i]
        if inv.id in already:
            skipped.append(
                {"investor_id": str(inv.id), "name": inv.name, "reason": "already drafted"}
            )
            continue
        if not inv.email:
            skipped.append({"investor_id": str(inv.id), "name": inv.name, "reason": "no email"})
            continue
        created.append(
            await create_draft(
                db,
                ws,
                investor_id=inv.id,
                subject=render(camp.subject, inv),
                body=render(camp.body, inv),
                attachment_ids=list(camp.attachment_ids),
                kind=camp.kind,
                campaign_id=camp.id,
                now=now,
            )
        )
    return DraftBatch(created, skipped)


async def follow_ups_due(
    db: AsyncSession, ws: WorkspaceContext, *, now: datetime
) -> list[OutreachMessage]:
    """Sent campaign messages with no reply after the campaign's follow-up days."""
    rows = await db.execute(
        select(OutreachMessage, Campaign.follow_up_days)
        .join(
            Campaign,
            (Campaign.workspace_id == OutreachMessage.workspace_id)
            & (Campaign.id == OutreachMessage.campaign_id),
        )
        .where(
            OutreachMessage.workspace_id == ws.workspace_id,
            OutreachMessage.status == "sent",
            OutreachMessage.replied_at.is_(None),
            Campaign.follow_up_days.is_not(None),
        )
    )
    out = []
    for msg, days in rows.tuples():
        if msg.sent_at is not None and days and msg.sent_at + timedelta(days=days) <= now:
            out.append(msg)
    return out


async def stats(db: AsyncSession, ws: WorkspaceContext, campaign_id: UUID) -> dict[str, int]:
    msgs = await list_messages(db, ws, campaign_id=campaign_id, limit=5000)
    return {
        "drafts": sum(m.status == "draft" for m in msgs),
        "sent": sum(m.status == "sent" for m in msgs),
        "failed": sum(m.status == "failed" for m in msgs),
        "replied": sum(m.replied_at is not None for m in msgs),
    }
