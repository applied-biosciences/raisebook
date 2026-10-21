"""Linked cards: two or more investors linked as one team (migration 0009).

For example two partners at the same fund working the deal together. The only writer of
``investor_groups`` and ``investors.group_id``; REST (``POST``/``DELETE
/v1/investors/{id}/links``) and MCP (``link_investors``, ``unlink_investor``) call it.

Rules:

- :func:`link` puts an investor and the others in one group. When some already belong to
  different groups, those groups merge: every member of every involved group joins. Linking
  investors that are already together changes nothing (``changed: False``).
- :func:`unlink` takes one investor out of its group; a group left with fewer than two
  members is deleted and the last member's ``group_id`` cleared. Unlinking an investor that
  is not linked changes nothing.
- :func:`dissolve_if_small` runs after an investor is deleted (``services.investors``).
- Every investor whose set of linked cards changes gets one ``investor_updated`` activity
  (``data.fields = ["linked_cards"]``, ``data.changes.linked_cards = {from, to}`` as
  investor ids) and a new ``updated_at``. A no-op writes nothing.
- Ids from another workspace are 404 (``not_found``), never 403.

Concurrency: every writer of group membership (:func:`link`, :func:`unlink`,
:func:`dissolve_if_small` via ``services.investors.delete_investor``) first takes
:func:`lock_workspace`, a transaction-scoped advisory lock per workspace, so membership
changes in one workspace run one at a time (a merge can never miss a member a concurrent
link is adding). Row locks are then taken in ``Investor.id`` order, in one statement where
possible, so they cannot deadlock either.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from raisebook.auth.principal import WorkspaceContext
from raisebook.core.actor import Actor
from raisebook.core.errors import LimitReached, ValidationFailed, not_found
from raisebook.models.investor import Investor, InvestorGroup
from raisebook.schemas.investors import LinkedInvestorBrief
from raisebook.services import activities

MAX_GROUP_SIZE = 50
FIELD = "linked_cards"


@dataclass
class LinkResult:
    group_id: UUID
    members: list[Investor]  # every member, sorted by name
    changed: bool


async def lock_workspace(db: AsyncSession, ws: WorkspaceContext) -> None:
    """Serialize linked-card membership writes within one workspace (released at commit or
    rollback). Taken before any investor or group row lock."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"investor_links:{ws.workspace_id}"},
    )


def brief(inv: Investor) -> LinkedInvestorBrief:
    return LinkedInvestorBrief(
        id=inv.id,
        name=inv.name,
        firm=inv.firm,
        title=inv.title,
        email=str(inv.email) if inv.email else None,
    )


def _by_name(rows: Iterable[Investor]) -> list[Investor]:
    return sorted(rows, key=lambda i: (i.name.casefold(), str(i.id)))


async def _members(
    db: AsyncSession, ws: WorkspaceContext, group_ids: Iterable[UUID], *, lock: bool = False
) -> list[Investor]:
    ids = set(group_ids)
    if not ids:
        return []
    stmt = select(Investor).where(
        Investor.workspace_id == ws.workspace_id, Investor.group_id.in_(ids)
    )
    if lock:
        stmt = stmt.order_by(Investor.id).with_for_update()
    return list(await db.scalars(stmt.execution_options(populate_existing=True)))


async def _log_changes(
    db: AsyncSession,
    ws: WorkspaceContext,
    before: dict[UUID, set[UUID]],
    after: dict[UUID, set[UUID]],
    investors: dict[UUID, Investor],
    *,
    now: datetime,
    actor: Actor | None,
    group_id: UUID | None,
) -> None:
    """One ``investor_updated`` per investor whose linked set changed (ids, sorted)."""
    for inv_id in sorted(set(before) | set(after), key=str):
        old, new = before.get(inv_id, set()), after.get(inv_id, set())
        if old == new or inv_id not in investors:
            continue
        investors[inv_id].updated_at = now
        data: dict[str, Any] = {
            "fields": [FIELD],
            "changes": {FIELD: {"from": sorted(map(str, old)), "to": sorted(map(str, new))}},
        }
        if group_id is not None and new:
            data["group_id"] = str(group_id)
        await activities.log(
            db, ws, investor_id=inv_id, kind="investor_updated", now=now, data=data, actor=actor
        )


def _others(members: Sequence[Investor]) -> dict[UUID, set[UUID]]:
    ids = {m.id for m in members}
    return {m.id: ids - {m.id} for m in members}


async def link(
    db: AsyncSession,
    ws: WorkspaceContext,
    investor: Investor,
    other_ids: Sequence[UUID],
    *,
    now: datetime,
    actor: Actor | None = None,
) -> LinkResult:
    """Link ``investor`` with ``other_ids`` (merging any groups they already belong to)."""
    wanted = list(dict.fromkeys(other_ids))
    if not wanted:
        raise ValidationFailed("investor_ids", "Pass at least one other investor to link.")
    if investor.id in wanted:
        raise ValidationFailed(
            "investor_ids", "An investor cannot be linked to themselves; pass other investors."
        )
    await lock_workspace(db, ws)
    locked = list(
        await db.scalars(
            select(Investor)
            .where(
                Investor.workspace_id == ws.workspace_id, Investor.id.in_([investor.id, *wanted])
            )
            .order_by(Investor.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if len(locked) != len(wanted) + 1:
        raise not_found("Investor")
    direct = [investor, *(i for i in locked if i.id != investor.id)]
    groups = {i.group_id for i in direct if i.group_id is not None}
    existing = await _members(db, ws, groups, lock=True)
    everyone: dict[UUID, Investor] = {i.id: i for i in existing}
    for i in direct:
        everyone.setdefault(i.id, i)
    if len(everyone) > MAX_GROUP_SIZE:
        raise LimitReached(f"A linked team can have at most {MAX_GROUP_SIZE} investors.")

    if len(groups) == 1 and all(i.group_id in groups for i in direct):
        gid = next(iter(groups))
        return LinkResult(gid, _by_name(everyone.values()), False)

    before = _others(existing)
    if groups:
        # Keep the oldest group (a stable id for the team); merge the rest into it.
        oldest = await db.scalar(
            select(InvestorGroup.id)
            .where(InvestorGroup.workspace_id == ws.workspace_id, InvestorGroup.id.in_(groups))
            .order_by(InvestorGroup.created_at, InvestorGroup.id)
            .limit(1)
        )
        assert oldest is not None
        gid = oldest
        kept = await db.get(InvestorGroup, gid)
        assert kept is not None
        kept.updated_at = now
    else:
        group = InvestorGroup(workspace_id=ws.workspace_id, created_at=now, updated_at=now)
        db.add(group)
        await db.flush()
        gid = group.id
    for inv in everyone.values():
        inv.group_id = gid
    await db.flush()
    stale = groups - {gid}
    if stale:
        await db.execute(
            delete(InvestorGroup).where(
                InvestorGroup.workspace_id == ws.workspace_id, InvestorGroup.id.in_(stale)
            )
        )
    members = list(everyone.values())
    await _log_changes(
        db, ws, before, _others(members), everyone, now=now, actor=actor, group_id=gid
    )
    await db.flush()
    return LinkResult(gid, _by_name(members), True)


async def unlink(
    db: AsyncSession,
    ws: WorkspaceContext,
    investor: Investor,
    *,
    now: datetime,
    actor: Actor | None = None,
) -> bool:
    """Take ``investor`` out of its group (dissolving a group left with one member).
    Returns False when the investor was not linked (nothing written)."""
    await lock_workspace(db, ws)
    await db.refresh(investor, with_for_update=True)
    gid = investor.group_id
    if gid is None:
        return False
    members = await _members(db, ws, [gid], lock=True)
    before = _others(members)
    investor.group_id = None
    rest = [m for m in members if m.id != investor.id]
    if len(rest) < 2:
        for m in rest:
            m.group_id = None
    await db.flush()
    if len(rest) < 2:
        await _delete_group(db, ws, gid)
    after = _others(rest) if len(rest) >= 2 else {}
    everyone = {m.id: m for m in members}
    everyone[investor.id] = investor
    await _log_changes(db, ws, before, after, everyone, now=now, actor=actor, group_id=gid)
    await db.flush()
    return True


async def _delete_group(db: AsyncSession, ws: WorkspaceContext, gid: UUID) -> None:
    await db.execute(
        delete(InvestorGroup).where(
            InvestorGroup.workspace_id == ws.workspace_id, InvestorGroup.id == gid
        )
    )


async def dissolve_if_small(
    db: AsyncSession,
    ws: WorkspaceContext,
    gid: UUID | None,
    *,
    now: datetime,
    deleted_id: UUID,
    actor: Actor | None = None,
) -> None:
    """After member ``deleted_id`` of group ``gid`` was deleted: a group with fewer than two
    members left is removed (and the last member's ``group_id`` cleared). Every remaining
    member's linked set loses the deleted investor, so each gets a new ``updated_at`` and an
    ``investor_updated`` activity; the deleted investor's own timeline is gone with them.
    The caller holds :func:`lock_workspace`."""
    if gid is None:
        return
    rest = await _members(db, ws, [gid], lock=True)
    after = _others(rest) if len(rest) >= 2 else {}
    ids = {m.id for m in rest}
    before = {m.id: (ids - {m.id}) | {deleted_id} for m in rest}
    if len(rest) < 2:
        for m in rest:
            m.group_id = None
        await db.flush()
        await _delete_group(db, ws, gid)
    await _log_changes(
        db, ws, before, after, {m.id: m for m in rest}, now=now, actor=actor, group_id=gid
    )
    await db.flush()


# --- presentation ------------------------------------------------------------------------


async def linked_map(
    db: AsyncSession, ws: WorkspaceContext, investors: Iterable[Investor]
) -> dict[UUID, list[LinkedInvestorBrief]]:
    """For each investor, the other members of its group sorted by name (one query for any
    number of investors; none when nobody is linked)."""
    invs = list(investors)
    groups = {i.group_id for i in invs if i.group_id is not None}
    out: dict[UUID, list[LinkedInvestorBrief]] = {i.id: [] for i in invs}
    if not groups:
        return out
    rows = await db.execute(
        select(
            Investor.id,
            Investor.name,
            Investor.firm,
            Investor.title,
            Investor.email,
            Investor.group_id,
        ).where(Investor.workspace_id == ws.workspace_id, Investor.group_id.in_(groups))
    )
    by_group: dict[UUID, list[LinkedInvestorBrief]] = defaultdict(list)
    for iid, name, firm, title, email, gid in rows.tuples():
        if gid is None:
            continue
        by_group[gid].append(
            LinkedInvestorBrief(
                id=iid, name=name, firm=firm, title=title, email=str(email) if email else None
            )
        )
    for members in by_group.values():
        members.sort(key=lambda b: (b.name.casefold(), str(b.id)))
    for inv in invs:
        if inv.group_id is not None:
            out[inv.id] = [b for b in by_group.get(inv.group_id, []) if b.id != inv.id]
    return out
