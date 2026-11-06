"""The Funding Room (Wasila v1.0.0.0): the workspace's document repository for diligence.

The only writer of ``funding_room_documents``, ``funding_room_versions``,
``funding_room_links`` and ``funding_room_events``. Every change writes one event (the room's
audit trail) in the same transaction; no-ops write nothing.

- Documents have a category (the diligence areas: pitch, corporate, financial, technical,
  clinical, regulatory, IP, cybersecurity, data protection, commercial, legal, tax relief),
  a confidentiality level, a review status and a jurisdiction (all, US, UK, KSA).
- Each upload is a new immutable version (bytes stored in Postgres, at most 25 MB). Downloads
  are recorded.
- Share links are per investor or audience, expire (1 to 90 days), can be revoked, and only
  ever expose **approved** documents. Only the token's SHA-256 is stored. Views are counted,
  never tied to an IP address or a person.
- Jurisdiction checklists (US, UK, KSA) say which standard documents are present.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from wasila.auth.principal import WorkspaceContext
from wasila.core.errors import NotFound, PayloadTooLarge, ValidationFailed
from wasila.models.investor import Investor
from wasila.models.room import RoomDocument, RoomEvent, RoomLink, RoomVersion

CATEGORIES: Final[dict[str, str]] = {
    "pitch": "Pitch and overview",
    "corporate": "Corporate",
    "financial": "Financial",
    "technical": "Technical",
    "clinical": "Clinical",
    "regulatory": "Regulatory",
    "ip": "Intellectual property",
    "cybersecurity": "Cybersecurity",
    "data_protection": "Data protection",
    "commercial": "Commercial",
    "legal": "Legal",
    "tax_relief": "Tax relief (SEIS/EIS)",
    "other": "Other",
}
CONFIDENTIALITY: Final[tuple[str, ...]] = ("public", "investors", "nda", "restricted")
REVIEW_STATUSES: Final[tuple[str, ...]] = ("draft", "in_review", "approved", "archived")
JURISDICTIONS: Final[tuple[str, ...]] = ("all", "us", "uk", "ksa")

MAX_BYTES: Final[int] = 25 * 1024 * 1024
LINK_PREFIX: Final[str] = "wslroom_"
MAX_LINK_DAYS: Final[int] = 90

CONTENT_TYPES: Final[dict[str, str]] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "txt": "text/plain",
    "md": "text/markdown",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

# Standard documents per jurisdiction: (key, label, category). "all" items apply everywhere.
CHECKLISTS: Final[dict[str, tuple[tuple[str, str, str], ...]]] = {
    "all": (
        ("deck", "Investor deck", "pitch"),
        ("one_pager", "One-page summary", "pitch"),
        ("financial_model", "Financial model and use of funds", "financial"),
        ("cap_table", "Cap table", "corporate"),
        ("ip_assignment", "IP assignment to the company", "ip"),
        ("dpia", "Data protection impact assessment", "data_protection"),
        ("security", "Security and penetration test summary", "cybersecurity"),
    ),
    "us": (
        ("us_incorporation", "Certificate of incorporation (e.g. Delaware C-Corp)", "corporate"),
        ("us_safe", "SAFE or note form (YC post-money SAFE)", "legal"),
        ("us_409a", "409A valuation (if options are granted)", "financial"),
        ("us_hipaa", "HIPAA position (if handling US health data)", "regulatory"),
    ),
    "uk": (
        ("uk_incorporation", "Certificate of incorporation (Companies House)", "corporate"),
        ("uk_articles", "Articles of association", "corporate"),
        ("uk_advance_assurance", "HMRC SEIS/EIS advance assurance", "tax_relief"),
        ("uk_asa", "Advance subscription agreement (if used)", "legal"),
        ("uk_dtac", "NHS DTAC / DCB0129 clinical safety (health products)", "clinical"),
    ),
    "ksa": (
        ("ksa_cr", "Commercial Registration (CR)", "corporate"),
        ("ksa_misa", "MISA investment licence", "regulatory"),
        ("ksa_zatca", "ZATCA (zakat and tax) registration", "financial"),
        ("ksa_pdpl", "PDPL (Saudi data protection) assessment", "data_protection"),
        ("ksa_sfda", "SFDA position (medical device software)", "clinical"),
        ("ksa_arabic", "Arabic summary or deck", "pitch"),
    ),
}


def invalid(message: str, field: str = "body") -> ValidationFailed:
    return ValidationFailed(field, message)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _actor_cols(ws: WorkspaceContext) -> dict[str, Any]:
    a = ws.actor
    return {
        "actor_type": a.type.value,
        "actor_user_id": a.user_id,
        "actor_label": a.label,
        "via": a.via.value,
    }


def _check(value: str, allowed: tuple[str, ...] | dict[str, str], field: str) -> str:
    if value not in allowed:
        raise invalid(f"{field} must be one of: {', '.join(allowed)}.", field=field)
    return value


def extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def content_type_for(filename: str) -> str:
    ext = extension(filename)
    if ext not in CONTENT_TYPES:
        raise invalid(
            f"Files of type .{ext or '?'} are not accepted. Upload one of: "
            + ", ".join(f".{e}" for e in CONTENT_TYPES)
            + ".",
            field="filename",
        )
    return CONTENT_TYPES[ext]


async def _event(
    db: AsyncSession,
    ws: WorkspaceContext,
    kind: str,
    *,
    now: datetime,
    document_id: UUID | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    db.add(
        RoomEvent(
            workspace_id=ws.workspace_id,
            document_id=document_id,
            kind=kind,
            data=data or {},
            created_at=now,
            **_actor_cols(ws),
        )
    )


# --- documents --------------------------------------------------------------------------------


async def list_documents(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    category: str | None = None,
    review_status: str | None = None,
    jurisdiction: str | None = None,
    q: str | None = None,
) -> list[RoomDocument]:
    stmt = select(RoomDocument).where(RoomDocument.workspace_id == ws.workspace_id)
    if category:
        stmt = stmt.where(RoomDocument.category == category)
    if review_status:
        stmt = stmt.where(RoomDocument.review_status == review_status)
    if jurisdiction:
        stmt = stmt.where(RoomDocument.jurisdiction.in_(("all", jurisdiction)))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            RoomDocument.title.ilike(like)
            | RoomDocument.description.ilike(like)
            | RoomDocument.folder.ilike(like)
        )
    stmt = stmt.order_by(RoomDocument.category, RoomDocument.title)
    return list((await db.scalars(stmt)).all())


async def get_document(db: AsyncSession, ws: WorkspaceContext, doc_id: UUID) -> RoomDocument:
    doc = await db.scalar(
        select(RoomDocument).where(
            RoomDocument.workspace_id == ws.workspace_id, RoomDocument.id == doc_id
        )
    )
    if doc is None:
        raise NotFound("Document not found. List documents with GET /v1/funding-room/documents.")
    return doc


async def create_document(
    db: AsyncSession, ws: WorkspaceContext, *, fields: dict[str, Any], now: datetime
) -> RoomDocument:
    clean = _clean_fields(fields, creating=True)
    doc = RoomDocument(
        workspace_id=ws.workspace_id, created_at=now, updated_at=now, **clean, **_actor_cols(ws)
    )
    if clean.get("review_status") == "approved":
        doc.reviewed_at = now
    db.add(doc)
    await db.flush()
    await _event(db, ws, "created", now=now, document_id=doc.id, data={"title": doc.title})
    await db.flush()
    return doc


def _clean_fields(fields: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in fields.items():
        if v is None and k in ("folder", "description"):
            out[k] = None
            continue
        if v is None:
            continue
        if k == "title":
            v = str(v).strip()
            if not 1 <= len(v) <= 200:
                raise invalid("title must be 1 to 200 characters.")
        elif k == "category":
            _check(v, CATEGORIES, "category")
        elif k == "confidentiality":
            _check(v, CONFIDENTIALITY, "confidentiality")
        elif k == "review_status":
            _check(v, REVIEW_STATUSES, "review_status")
        elif k == "jurisdiction":
            _check(v, JURISDICTIONS, "jurisdiction")
        elif k in ("folder", "description"):
            v = str(v).strip() or None
        elif k == "is_deck":
            v = bool(v)
        else:
            continue
        out[k] = v
    if creating and ("title" not in out or "category" not in out):
        raise invalid("title and category are required.")
    return out


async def update_document(
    db: AsyncSession, ws: WorkspaceContext, doc_id: UUID, *, fields: dict[str, Any], now: datetime
) -> tuple[RoomDocument, bool]:
    doc = await get_document(db, ws, doc_id)
    clean = _clean_fields(fields, creating=False)
    changed = {k: v for k, v in clean.items() if getattr(doc, k) != v}
    if not changed:
        return doc, False
    before = {k: getattr(doc, k) for k in changed}
    for k, v in changed.items():
        setattr(doc, k, v)
    if changed.get("review_status") == "approved":
        doc.reviewed_at = now
    doc.updated_at = now
    await _event(
        db,
        ws,
        "updated",
        now=now,
        document_id=doc.id,
        data={"changes": {k: {"from": before[k], "to": v} for k, v in changed.items()}},
    )
    await db.flush()
    return doc, True


async def delete_document(
    db: AsyncSession, ws: WorkspaceContext, doc_id: UUID, *, now: datetime
) -> None:
    doc = await get_document(db, ws, doc_id)
    await _event(db, ws, "deleted", now=now, document_id=None, data={"title": doc.title})
    await db.execute(
        update(RoomEvent)
        .where(RoomEvent.workspace_id == ws.workspace_id, RoomEvent.document_id == doc.id)
        .values(document_id=None)
    )
    await db.execute(
        delete(RoomDocument).where(
            RoomDocument.workspace_id == ws.workspace_id, RoomDocument.id == doc.id
        )
    )
    await db.flush()


# --- versions ---------------------------------------------------------------------------------


async def add_version(
    db: AsyncSession,
    ws: WorkspaceContext,
    doc_id: UUID,
    *,
    filename: str,
    data: bytes,
    note: str | None,
    now: datetime,
) -> RoomVersion:
    doc = await get_document(db, ws, doc_id)
    filename = (filename or "").strip().replace("/", "_").replace("\\", "_")[:255]
    if not filename:
        raise invalid("Send the file name in the X-Filename header.")
    if not data:
        raise invalid("The file is empty.")
    if len(data) > MAX_BYTES:
        raise PayloadTooLarge("Files can be at most 25 MB. Compress the file or split it.")
    ctype = content_type_for(filename)
    if note is not None and len(note) > 500:
        raise invalid("note must be at most 500 characters.")
    # Lock the document row so two uploads never take the same version number.
    await db.execute(
        select(RoomDocument.id)
        .where(RoomDocument.workspace_id == ws.workspace_id, RoomDocument.id == doc.id)
        .with_for_update()
    )
    number = doc.current_version + 1
    ver = RoomVersion(
        workspace_id=ws.workspace_id,
        document_id=doc.id,
        version=number,
        filename=filename,
        content_type=ctype,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        note=(note or "").strip() or None,
        data=data,
        created_at=now,
        **_actor_cols(ws),
    )
    db.add(ver)
    doc.current_version = number
    doc.updated_at = now
    if ctype == CONTENT_TYPES["pptx"]:
        doc.is_deck = True
    await _event(
        db,
        ws,
        "version_added",
        now=now,
        document_id=doc.id,
        data={"version": number, "filename": filename, "size_bytes": len(data)},
    )
    await db.flush()
    return ver


async def list_versions(db: AsyncSession, ws: WorkspaceContext, doc_id: UUID) -> list[RoomVersion]:
    await get_document(db, ws, doc_id)
    return list(
        (
            await db.scalars(
                select(RoomVersion)
                .where(
                    RoomVersion.workspace_id == ws.workspace_id,
                    RoomVersion.document_id == doc_id,
                )
                .order_by(RoomVersion.version.desc())
            )
        ).all()
    )


async def get_version(
    db: AsyncSession,
    ws: WorkspaceContext,
    doc_id: UUID,
    version: int | None = None,
    *,
    with_data: bool = True,
) -> RoomVersion:
    doc = await get_document(db, ws, doc_id)
    number = version if version is not None else doc.current_version
    stmt = select(RoomVersion).where(
        RoomVersion.workspace_id == ws.workspace_id,
        RoomVersion.document_id == doc.id,
        RoomVersion.version == number,
    )
    if with_data:
        stmt = stmt.options(undefer(RoomVersion.data))
    ver = await db.scalar(stmt)
    if ver is None:
        raise NotFound("That version does not exist. Upload a file first.")
    return ver


async def record_download(
    db: AsyncSession, ws: WorkspaceContext, ver: RoomVersion, *, now: datetime
) -> None:
    await _event(
        db, ws, "downloaded", now=now, document_id=ver.document_id, data={"version": ver.version}
    )
    await db.flush()


# --- share links ------------------------------------------------------------------------------


@dataclass
class LinkView:
    link: RoomLink
    documents: list[RoomDocument]


async def create_link(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    label: str,
    document_ids: list[UUID],
    investor_id: UUID | None,
    days: int,
    now: datetime,
) -> tuple[RoomLink, str]:
    label = (label or "").strip()
    if not 1 <= len(label) <= 120:
        raise invalid("label must be 1 to 120 characters.")
    if not 1 <= days <= MAX_LINK_DAYS:
        raise invalid(f"days must be between 1 and {MAX_LINK_DAYS}.")
    ids = list(dict.fromkeys(document_ids))
    if not 1 <= len(ids) <= 50:
        raise invalid("Choose 1 to 50 documents.")
    docs = list(
        (
            await db.scalars(
                select(RoomDocument).where(
                    RoomDocument.workspace_id == ws.workspace_id, RoomDocument.id.in_(ids)
                )
            )
        ).all()
    )
    if len(docs) != len(ids):
        raise NotFound("Document not found. List documents with GET /v1/funding-room/documents.")
    unready = [d.title for d in docs if d.review_status != "approved" or d.current_version < 1]
    if unready:
        raise invalid(
            "Only approved documents with a file can be shared. Approve these first: "
            + ", ".join(unready),
            field="document_ids",
        )
    if investor_id is not None:
        found = await db.scalar(
            select(Investor.id).where(
                Investor.workspace_id == ws.workspace_id, Investor.id == investor_id
            )
        )
        if found is None:
            raise NotFound("Investor not found.")
    token = LINK_PREFIX + secrets.token_urlsafe(32)
    link = RoomLink(
        workspace_id=ws.workspace_id,
        investor_id=investor_id,
        label=label,
        token_hash=hash_token(token),
        document_ids=ids,
        expires_at=now + timedelta(days=days),
        created_at=now,
        **_actor_cols(ws),
    )
    db.add(link)
    await db.flush()
    await _event(
        db,
        ws,
        "link_created",
        now=now,
        data={"link_id": str(link.id), "label": label, "days": days},
    )
    await db.flush()
    return link, token


async def list_links(db: AsyncSession, ws: WorkspaceContext) -> list[RoomLink]:
    return list(
        (
            await db.scalars(
                select(RoomLink)
                .where(RoomLink.workspace_id == ws.workspace_id)
                .order_by(RoomLink.created_at.desc())
            )
        ).all()
    )


async def revoke_link(
    db: AsyncSession, ws: WorkspaceContext, link_id: UUID, *, now: datetime
) -> RoomLink:
    link = await db.scalar(
        select(RoomLink).where(RoomLink.workspace_id == ws.workspace_id, RoomLink.id == link_id)
    )
    if link is None:
        raise NotFound("Share link not found.")
    if link.revoked_at is None:
        link.revoked_at = now
        await _event(db, ws, "link_revoked", now=now, data={"link_id": str(link.id)})
        await db.flush()
    return link


def link_state(link: RoomLink, now: datetime) -> str:
    if link.revoked_at is not None:
        return "revoked"
    if link.expires_at <= now:
        return "expired"
    return "active"


async def _live_link(db: AsyncSession, token: str, now: datetime) -> RoomLink:
    missing = NotFound("This link is not valid. Ask the company for a new one.")
    if not token.startswith(LINK_PREFIX) or len(token) > 120:
        raise missing
    link = await db.scalar(select(RoomLink).where(RoomLink.token_hash == hash_token(token)))
    if link is None or link_state(link, now) != "active":
        raise missing
    return link


async def open_link(db: AsyncSession, token: str, *, now: datetime) -> LinkView:
    """Public: the documents behind a share link (approved ones only). Counts a view."""
    link = await _live_link(db, token, now)
    docs = list(
        (
            await db.scalars(
                select(RoomDocument)
                .where(
                    RoomDocument.workspace_id == link.workspace_id,
                    RoomDocument.id.in_(link.document_ids),
                    RoomDocument.review_status == "approved",
                    RoomDocument.current_version > 0,
                )
                .order_by(RoomDocument.category, RoomDocument.title)
            )
        ).all()
    )
    link.view_count += 1
    link.last_viewed_at = now
    db.add(
        RoomEvent(
            workspace_id=link.workspace_id,
            kind="link_viewed",
            data={"link_id": str(link.id)},
            created_at=now,
            actor_type="system",
            actor_label="share link",
            via="system",
        )
    )
    await db.flush()
    return LinkView(link, docs)


async def link_file(db: AsyncSession, token: str, doc_id: UUID, *, now: datetime) -> RoomVersion:
    link = await _live_link(db, token, now)
    if doc_id not in link.document_ids:
        raise NotFound("This link is not valid. Ask the company for a new one.")
    doc = await db.scalar(
        select(RoomDocument).where(
            RoomDocument.workspace_id == link.workspace_id,
            RoomDocument.id == doc_id,
            RoomDocument.review_status == "approved",
        )
    )
    if doc is None or doc.current_version < 1:
        raise NotFound("This link is not valid. Ask the company for a new one.")
    ver = await db.scalar(
        select(RoomVersion)
        .options(undefer(RoomVersion.data))
        .where(
            RoomVersion.workspace_id == link.workspace_id,
            RoomVersion.document_id == doc.id,
            RoomVersion.version == doc.current_version,
        )
    )
    if ver is None:
        raise NotFound("This link is not valid. Ask the company for a new one.")
    db.add(
        RoomEvent(
            workspace_id=link.workspace_id,
            document_id=doc.id,
            kind="downloaded",
            data={"link_id": str(link.id), "version": ver.version},
            created_at=now,
            actor_type="system",
            actor_label="share link",
            via="system",
        )
    )
    await db.flush()
    return ver


# --- events and checklists --------------------------------------------------------------------


async def list_events(
    db: AsyncSession, ws: WorkspaceContext, *, limit: int = 50
) -> list[RoomEvent]:
    return list(
        (
            await db.scalars(
                select(RoomEvent)
                .where(RoomEvent.workspace_id == ws.workspace_id)
                .order_by(RoomEvent.created_at.desc(), RoomEvent.id)
                .limit(limit)
            )
        ).all()
    )


def checklist_items(jurisdiction: str) -> list[tuple[str, str, str]]:
    _check(jurisdiction, ("us", "uk", "ksa", "all"), "jurisdiction")
    items = list(CHECKLISTS["all"])
    if jurisdiction != "all":
        items += list(CHECKLISTS[jurisdiction])
    return items


# Words that identify each standard document in a title (lower case, substring match).
KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "deck": ("deck", "pitch", "presentation"),
    "one_pager": ("one-pager", "one pager", "onepager", "summary", "teaser", "executive"),
    "financial_model": ("model", "business plan", "forecast", "financial", "p&l", "use of funds"),
    "cap_table": ("cap table", "captable", "shareholder", "register of members"),
    "ip_assignment": ("ip ", "ip assignment", "intellectual property", "patent", "assignment"),
    "dpia": ("dpia", "impact assessment", "data protection"),
    "security": ("security", "penetration", "pen test", "pentest", "iso 27001", "soc 2"),
    "us_incorporation": ("incorporation", "delaware", "certificate"),
    "us_safe": ("safe", "convertible", "note"),
    "us_409a": ("409a", "valuation"),
    "us_hipaa": ("hipaa",),
    "uk_incorporation": ("incorporation", "companies house", "certificate"),
    "uk_articles": ("articles",),
    "uk_advance_assurance": ("advance assurance", "seis", "eis"),
    "uk_asa": ("asa", "advance subscription"),
    "uk_dtac": ("dtac", "dcb0129", "dcb 0129", "clinical safety"),
    "ksa_cr": ("commercial registration", " cr", "cr "),
    "ksa_misa": ("misa", "investment licence", "investment license"),
    "ksa_zatca": ("zatca", "zakat"),
    "ksa_pdpl": ("pdpl", "personal data protection"),
    "ksa_sfda": ("sfda",),
    "ksa_arabic": ("arabic", "عربي"),
}


def _matches(key: str, category: str, doc: RoomDocument) -> bool:
    if doc.category != category:
        return False
    if key == "deck" and doc.is_deck:
        return True
    title = f" {doc.title.lower()} "
    return any(k in title for k in KEYWORDS.get(key, ()))


async def checklist(
    db: AsyncSession, ws: WorkspaceContext, jurisdiction: str
) -> list[dict[str, Any]]:
    """Each standard document with the room documents that likely cover it: same category
    and a telling word in the title (a guide for people, not a legal opinion). Documents for
    another market do not count."""
    items = checklist_items(jurisdiction)
    docs = [
        d
        for d in await list_documents(db, ws)
        if d.review_status != "archived"
        and (jurisdiction == "all" or d.jurisdiction in ("all", jurisdiction))
    ]
    out = []
    for key, label, category in items:
        matches = [d for d in docs if _matches(key, category, d)]
        out.append(
            {
                "key": key,
                "label": label,
                "category": category,
                "status": (
                    "approved"
                    if any(d.review_status == "approved" for d in matches)
                    else "present"
                    if matches
                    else "missing"
                ),
                "document_ids": [str(d.id) for d in matches],
            }
        )
    return out


async def counts(db: AsyncSession, ws: WorkspaceContext) -> dict[str, int]:
    rows = await db.execute(
        select(RoomDocument.review_status, func.count())
        .where(RoomDocument.workspace_id == ws.workspace_id)
        .group_by(RoomDocument.review_status)
    )
    return {status: n for status, n in rows.tuples()}
