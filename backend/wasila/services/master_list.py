"""The master investor list (Wasila v1.0.0.0): structured search, custom fields and AI
columns, saved lists and warm-intro connections.

``search`` is the one place filters become SQL: the web's filter bar, saved lists and
"Ask Wasila" (Claude turns a question into these same filters, never into SQL) all call it.
The only writer of ``investor_fields``, ``saved_lists``, ``intro_connections`` and of
``investors.custom``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Select, and_, delete, exists, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila.auth.principal import WorkspaceContext
from wasila.core.errors import Conflict, NotFound, ValidationFailed
from wasila.models.activity import Activity
from wasila.models.investor import Investor
from wasila.models.room import IntroConnection, InvestorField, OutreachMessage, SavedList
from wasila.models.round import Round, RoundParticipant

INVESTOR_TYPES: Final[tuple[str, ...]] = (
    "vc",
    "angel",
    "family_office",
    "corporate_vc",
    "accelerator",
    "scout",
    "other",
)
FIELD_KINDS: Final[tuple[str, ...]] = ("text", "number", "yes_no", "select", "url", "ai")
CONTACT_KINDS: Final[tuple[str, ...]] = ("email", "call", "meeting")

# Common ways people name the three raising markets, folded to one country label.
COUNTRY_ALIASES: Final[dict[str, str]] = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "united kingdom": "United Kingdom",
    "us": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "america": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "ksa": "Saudi Arabia",
    "saudi": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "uae": "United Arab Emirates",
    "emirates": "United Arab Emirates",
}
GCC: Final[tuple[str, ...]] = (
    "Saudi Arabia",
    "United Arab Emirates",
    "Qatar",
    "Kuwait",
    "Bahrain",
    "Oman",
)


def invalid(message: str, field_name: str = "body") -> ValidationFailed:
    return ValidationFailed(field_name, message)


def norm_country(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    return COUNTRY_ALIASES.get(v.lower(), v[:100])


@dataclass
class Filters:
    q: str | None = None
    countries: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    tags_any: list[str] = field(default_factory=list)
    has_email: bool | None = None
    not_contacted: bool | None = None
    in_round: str | None = None
    not_in_round: str | None = None
    custom: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Filters:
        d = d or {}
        countries: list[str] = []
        for c in d.get("countries") or []:
            if str(c).strip().lower() == "gcc":
                countries += list(GCC)
            elif (n := norm_country(str(c))) is not None:
                countries.append(n)
        types = [str(t) for t in d.get("types") or [] if str(t) in INVESTOR_TYPES]
        return cls(
            q=(str(d["q"]).strip()[:200] or None) if d.get("q") else None,
            countries=list(dict.fromkeys(countries))[:20],
            types=types,
            tags_any=[str(t).strip()[:60] for t in d.get("tags_any") or [] if str(t).strip()][:20],
            has_email=_opt_bool(d.get("has_email")),
            not_contacted=_opt_bool(d.get("not_contacted")),
            in_round=(str(d["in_round"])[:200] if d.get("in_round") else None),
            not_in_round=(str(d["not_in_round"])[:200] if d.get("not_in_round") else None),
            custom={
                str(k)[:40]: str(v)[:200]
                for k, v in (d.get("custom") or {}).items()
                if v not in (None, "")
            },
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if v not in (None, [], {}):
                out[k] = v
        return out


def _opt_bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "yes", "y")


async def _round_id(db: AsyncSession, ws: WorkspaceContext, ref: str) -> UUID | None:
    from wasila.core.refs import resolve_round

    rnd = await resolve_round(db, ws, ref, required=False)
    return rnd.id if isinstance(rnd, Round) else None


async def _stmt(db: AsyncSession, ws: WorkspaceContext, f: Filters) -> Select[tuple[Investor]]:
    stmt = select(Investor).where(Investor.workspace_id == ws.workspace_id)
    if f.q:
        for word in re.findall(r"[\w@.+-]+", f.q.lower())[:8]:
            stmt = stmt.where(Investor.search_text.contains(word))
    if f.countries:
        lowered = [c.lower() for c in f.countries]
        stmt = stmt.where(
            or_(
                func.lower(Investor.country).in_(lowered),
                *[Investor.location.ilike(f"%{c}%") for c in f.countries],
            )
        )
    if f.types:
        stmt = stmt.where(Investor.type.in_(f.types))
    if f.tags_any:
        wanted = [t.lower() for t in f.tags_any]
        stmt = stmt.where(
            or_(
                *[func.lower(func.array_to_string(Investor.tags, "|")).contains(t) for t in wanted],
                *[
                    func.lower(func.array_to_string(Investor.industries, "|")).contains(t)
                    for t in wanted
                ],
            )
        )
    if f.has_email is True:
        stmt = stmt.where(Investor.email.is_not(None))
    elif f.has_email is False:
        stmt = stmt.where(Investor.email.is_(None))
    if f.not_contacted:
        contacted = exists().where(
            Activity.workspace_id == ws.workspace_id,
            Activity.investor_id == Investor.id,
            Activity.kind.in_(CONTACT_KINDS),
        )
        sent = exists().where(
            OutreachMessage.workspace_id == ws.workspace_id,
            OutreachMessage.investor_id == Investor.id,
            OutreachMessage.status == "sent",
        )
        stmt = stmt.where(not_(contacted), not_(sent))
    for ref, want in ((f.in_round, True), (f.not_in_round, False)):
        if not ref:
            continue
        rid = await _round_id(db, ws, ref)
        member = exists().where(
            RoundParticipant.workspace_id == ws.workspace_id,
            RoundParticipant.investor_id == Investor.id,
            RoundParticipant.round_id == rid,
        )
        stmt = stmt.where(member if want else not_(member))
    for key, value in f.custom.items():
        stmt = stmt.where(func.lower(Investor.custom[key].astext).contains(value.lower()))
    return stmt


async def search(
    db: AsyncSession, ws: WorkspaceContext, f: Filters, *, limit: int = 100, offset: int = 0
) -> tuple[list[Investor], int]:
    stmt = await _stmt(db, ws, f)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.scalars(stmt.order_by(Investor.name, Investor.id).limit(limit).offset(offset))
    ).all()
    return list(rows), int(total)


async def facets(db: AsyncSession, ws: WorkspaceContext) -> dict[str, Any]:
    """Counts the filter bar shows: by country and by type."""
    countries = await db.execute(
        select(Investor.country, func.count())
        .where(Investor.workspace_id == ws.workspace_id, Investor.country.is_not(None))
        .group_by(Investor.country)
        .order_by(func.count().desc())
        .limit(30)
    )
    types = await db.execute(
        select(Investor.type, func.count())
        .where(Investor.workspace_id == ws.workspace_id)
        .group_by(Investor.type)
    )
    total = await db.scalar(
        select(func.count()).select_from(Investor).where(Investor.workspace_id == ws.workspace_id)
    )
    return {
        "total": int(total or 0),
        "countries": [{"value": c, "count": n} for c, n in countries.tuples()],
        "types": [{"value": t, "count": n} for t, n in types.tuples()],
    }


# --- custom fields and AI columns -------------------------------------------------------------


def _key_for(label: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40]
    if not key or not key[0].isalpha():
        key = f"f_{key}"[:40]
    return key


async def list_fields(db: AsyncSession, ws: WorkspaceContext) -> list[InvestorField]:
    return list(
        (
            await db.scalars(
                select(InvestorField)
                .where(InvestorField.workspace_id == ws.workspace_id)
                .order_by(InvestorField.position, InvestorField.label)
            )
        ).all()
    )


async def get_field(db: AsyncSession, ws: WorkspaceContext, field_id: UUID) -> InvestorField:
    row = await db.scalar(
        select(InvestorField).where(
            InvestorField.workspace_id == ws.workspace_id, InvestorField.id == field_id
        )
    )
    if row is None:
        raise NotFound("Field not found. List fields with GET /v1/investor-fields.")
    return row


async def create_field(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    label: str,
    kind: str,
    options: list[str] | None,
    prompt: str | None,
    now: datetime,
) -> InvestorField:
    label = label.strip()
    if not 1 <= len(label) <= 80:
        raise invalid("label must be 1 to 80 characters.", "label")
    if kind not in FIELD_KINDS:
        raise invalid(f"kind must be one of: {', '.join(FIELD_KINDS)}.", "kind")
    if kind == "ai" and not (prompt or "").strip():
        raise invalid(
            "An AI column needs a prompt (what Claude should answer per investor).", "prompt"
        )
    key = _key_for(label)
    taken = await db.scalar(
        select(InvestorField.id).where(
            InvestorField.workspace_id == ws.workspace_id, InvestorField.key == key
        )
    )
    if taken is not None:
        raise Conflict(f"A field called {label!r} already exists.", code="duplicate")
    pos = await db.scalar(
        select(func.coalesce(func.max(InvestorField.position), -1) + 1).where(
            InvestorField.workspace_id == ws.workspace_id
        )
    )
    row = InvestorField(
        workspace_id=ws.workspace_id,
        key=key,
        label=label,
        kind=kind,
        options=[o.strip()[:80] for o in (options or []) if o.strip()][:50],
        prompt=(prompt or "").strip()[:2000] or None if kind == "ai" else None,
        position=int(pos or 0),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_field(db: AsyncSession, ws: WorkspaceContext, field_id: UUID) -> None:
    row = await get_field(db, ws, field_id)
    await db.execute(
        Investor.__table__.update()  # type: ignore[attr-defined]
        .where(Investor.workspace_id == ws.workspace_id, Investor.custom.has_key(row.key))
        .values(custom=Investor.custom - row.key)
    )
    await db.execute(
        delete(InvestorField).where(
            InvestorField.workspace_id == ws.workspace_id, InvestorField.id == row.id
        )
    )
    await db.flush()


async def set_custom(
    db: AsyncSession,
    ws: WorkspaceContext,
    investor_id: UUID,
    values: dict[str, Any],
    *,
    now: datetime,
) -> Investor:
    """Set (or clear with null/"") custom field values on one investor."""
    inv = await db.scalar(
        select(Investor).where(Investor.workspace_id == ws.workspace_id, Investor.id == investor_id)
    )
    if inv is None:
        raise NotFound("Investor not found.")
    known = {f.key: f for f in await list_fields(db, ws)}
    custom = dict(inv.custom or {})
    for k, v in values.items():
        if k not in known:
            raise invalid(f"Unknown field {k!r}. Create it first.", "values")
        if v is None or v == "":
            custom.pop(k, None)
        else:
            custom[k] = _coerce(known[k], v)
    if custom != inv.custom:
        inv.custom = custom
        inv.updated_at = now
        await db.flush()
    return inv


def _coerce(f: InvestorField, v: Any) -> Any:
    if f.kind == "number":
        try:
            return float(v) if "." in str(v) else int(str(v).replace(",", ""))
        except ValueError as exc:
            raise invalid(f"{f.label} must be a number.", "values") from exc
    if f.kind == "yes_no":
        return str(v).strip().lower() in ("1", "true", "yes", "y")
    text = str(v).strip()[:2000]
    if f.kind == "select" and f.options and text not in f.options:
        raise invalid(f"{f.label} must be one of: {', '.join(f.options)}.", "values")
    return text


# --- saved lists ------------------------------------------------------------------------------


async def list_saved(db: AsyncSession, ws: WorkspaceContext) -> list[SavedList]:
    return list(
        (
            await db.scalars(
                select(SavedList)
                .where(SavedList.workspace_id == ws.workspace_id)
                .order_by(SavedList.name)
            )
        ).all()
    )


async def get_saved(db: AsyncSession, ws: WorkspaceContext, list_id: UUID) -> SavedList:
    row = await db.scalar(
        select(SavedList).where(SavedList.workspace_id == ws.workspace_id, SavedList.id == list_id)
    )
    if row is None:
        raise NotFound("List not found.")
    return row


async def save_list(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    name: str,
    filters: Filters,
    question: str | None,
    investor_ids: list[UUID] | None,
    now: datetime,
) -> SavedList:
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise invalid("name must be 1 to 120 characters.", "name")
    ids: list[UUID] = []
    if investor_ids:
        ids = list(
            (
                await db.scalars(
                    select(Investor.id).where(
                        Investor.workspace_id == ws.workspace_id,
                        Investor.id.in_(list(dict.fromkeys(investor_ids))[:5000]),
                    )
                )
            ).all()
        )
        if len(ids) != len(set(investor_ids)):
            raise NotFound("Investor not found.")
    a = ws.actor
    row = SavedList(
        workspace_id=ws.workspace_id,
        name=name,
        question=(question or "").strip()[:1000] or None,
        filters=filters.to_dict(),
        investor_ids=ids,
        created_at=now,
        updated_at=now,
        actor_type=a.type.value,
        actor_user_id=a.user_id,
        actor_label=a.label,
        via=a.via.value,
    )
    db.add(row)
    await db.flush()
    return row


async def list_members(
    db: AsyncSession, ws: WorkspaceContext, row: SavedList, *, limit: int = 500
) -> tuple[list[Investor], int]:
    """A list's investors: its pinned ids when it has them, else its filters, live."""
    if row.investor_ids:
        invs = list(
            (
                await db.scalars(
                    select(Investor)
                    .where(
                        Investor.workspace_id == ws.workspace_id,
                        Investor.id.in_(row.investor_ids),
                    )
                    .order_by(Investor.name)
                    .limit(limit)
                )
            ).all()
        )
        return invs, len(row.investor_ids)
    return await search(db, ws, Filters.from_dict(row.filters), limit=limit)


async def delete_saved(db: AsyncSession, ws: WorkspaceContext, list_id: UUID) -> None:
    row = await get_saved(db, ws, list_id)
    await db.execute(
        delete(SavedList).where(SavedList.workspace_id == ws.workspace_id, SavedList.id == row.id)
    )
    await db.flush()


# --- warm intros ------------------------------------------------------------------------------


STRENGTH: Final[dict[int, str]] = {1: "Weak", 2: "Good", 3: "Strong"}


async def _investor(db: AsyncSession, ws: WorkspaceContext, investor_id: UUID) -> Investor:
    inv = await db.scalar(
        select(Investor).where(Investor.workspace_id == ws.workspace_id, Investor.id == investor_id)
    )
    if inv is None:
        raise NotFound("Investor not found.")
    return inv


async def list_intros(
    db: AsyncSession, ws: WorkspaceContext, investor_id: UUID
) -> list[IntroConnection]:
    await _investor(db, ws, investor_id)
    return list(
        (
            await db.scalars(
                select(IntroConnection)
                .where(
                    IntroConnection.workspace_id == ws.workspace_id,
                    IntroConnection.investor_id == investor_id,
                )
                .order_by(IntroConnection.strength.desc(), IntroConnection.connector_name)
            )
        ).all()
    )


async def add_intro(
    db: AsyncSession,
    ws: WorkspaceContext,
    investor_id: UUID,
    *,
    connector_name: str,
    connector_email: str | None,
    relationship: str | None,
    strength: int,
    notes: str | None,
    now: datetime,
) -> IntroConnection:
    inv = await _investor(db, ws, investor_id)
    name = connector_name.strip()
    if not 1 <= len(name) <= 120:
        raise invalid("connector_name must be 1 to 120 characters.", "connector_name")
    if strength not in STRENGTH:
        raise invalid("strength must be 1 (weak), 2 (good) or 3 (strong).", "strength")
    a = ws.actor
    row = IntroConnection(
        workspace_id=ws.workspace_id,
        investor_id=inv.id,
        connector_name=name,
        connector_email=(connector_email or "").strip() or None,
        relationship=(relationship or "").strip()[:200] or None,
        strength=strength,
        notes=(notes or "").strip()[:2000] or None,
        created_at=now,
        updated_at=now,
        actor_type=a.type.value,
        actor_user_id=a.user_id,
        actor_label=a.label,
        via=a.via.value,
    )
    db.add(row)
    # The strongest connector is also the investor's "warm intro by" when it is empty.
    if not inv.warm_intro_by:
        inv.warm_intro_by = name
        inv.updated_at = now
    await db.flush()
    return row


async def delete_intro(db: AsyncSession, ws: WorkspaceContext, intro_id: UUID) -> None:
    res = await db.execute(
        delete(IntroConnection).where(
            IntroConnection.workspace_id == ws.workspace_id, IntroConnection.id == intro_id
        )
    )
    if not getattr(res, "rowcount", 0):
        raise NotFound("Connection not found.")
    await db.flush()


def best_path(intros: list[IntroConnection]) -> IntroConnection | None:
    return max(intros, key=lambda c: (c.strength, c.updated_at), default=None)


async def best_paths(
    db: AsyncSession, ws: WorkspaceContext, investor_ids: list[UUID]
) -> dict[UUID, IntroConnection]:
    if not investor_ids:
        return {}
    rows = await db.scalars(
        select(IntroConnection).where(
            and_(
                IntroConnection.workspace_id == ws.workspace_id,
                IntroConnection.investor_id.in_(investor_ids),
            )
        )
    )
    out: dict[UUID, IntroConnection] = {}
    for r in rows:
        cur = out.get(r.investor_id)
        if cur is None or (r.strength, r.updated_at) > (cur.strength, cur.updated_at):
            out[r.investor_id] = r
    return out
