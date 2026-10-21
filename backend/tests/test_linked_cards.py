"""Linked cards: investors linked as one team (migration 0009, ``services/investor_links``),
over REST and MCP. Fictional data only."""

from __future__ import annotations

import asyncio
import secrets as pysecrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import asyncpg
import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from raisebook.models.investor import Investor, InvestorGroup
from tests.api.helpers import activities_of, world
from tests.conftest import TEST_DB_URL
from tests.factories import make_investor, make_participant, make_workspace
from tests.research.test_research_schema import _alembic

AGENT = {"X-Agent-Name": "claude-code", "X-Agent-Model": "claude-opus-5-5"}


async def _people(db: AsyncSession, ws: Any, *names: str) -> list[Investor]:
    return [
        await make_investor(db, ws, name=n, firm="Harbor Light Ventures", email=None) for n in names
    ]


async def _groups(db: AsyncSession, ws: Any) -> list[Any]:
    return list(
        await db.scalars(select(InvestorGroup.id).where(InvestorGroup.workspace_id == ws.id))
    )


async def _group_of(db: AsyncSession, inv: Investor) -> Any:
    await db.refresh(inv)
    return inv.group_id


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [r["id"] for r in rows]


async def test_link_returns_team_and_reads_show_linked(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    bruno, dara, ezra = await _people(db, w.ws, "Bruno Castell", "Dara Holm", "Ezra Vance")
    c = key_client(w.key, headers=AGENT)
    r = await c.post(f"/v1/investors/{dara.id}/links", json={"investor_ids": [str(bruno.id)]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) == {"group_id", "investors"}
    assert [m["name"] for m in out["investors"]] == ["Bruno Castell", "Dara Holm"]
    assert set(out["investors"][0]) == {"id", "name", "firm", "title", "email"}
    gid = out["group_id"]

    r = await c.get(f"/v1/investors/{bruno.id}")
    body = r.json()
    assert body["group_id"] == gid
    assert [m["name"] for m in body["linked"]] == ["Dara Holm"]
    r = await c.get(f"/v1/investors/{ezra.id}")
    assert r.json()["group_id"] is None and r.json()["linked"] == []

    # Lists carry it too.
    r = await c.get("/v1/investors")
    by_name = {i["name"]: i for i in r.json()["data"]}
    assert _ids(by_name["Dara Holm"]["linked"]) == [str(bruno.id)]
    assert by_name["Ezra Vance"]["linked"] == []

    # Activities: one investor_updated per member, as the agent.
    for inv, other in ((bruno, dara), (dara, bruno)):
        acts = await activities_of(db, inv, "investor_updated")
        assert len(acts) == 1
        assert acts[0].data["fields"] == ["linked_cards"]
        assert acts[0].data["changes"]["linked_cards"] == {"from": [], "to": [str(other.id)]}
        assert acts[0].actor_label == "claude-code"


async def test_participants_carry_linked(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    bruno, dara = await _people(db, w.ws, "Bruno Castell", "Dara Holm")
    await make_participant(db, w.rnd, bruno)
    await make_participant(db, w.rnd, dara)
    c = key_client(w.key)
    await c.post(f"/v1/investors/{bruno.id}/links", json={"investor_ids": [str(dara.id)]})
    r = await c.get("/v1/rounds/seed/participants")
    rows = {p["investor"]["name"]: p["investor"] for p in r.json()["data"]}
    assert [m["name"] for m in rows["Bruno Castell"]["linked"]] == ["Dara Holm"]
    assert rows["Bruno Castell"]["group_id"] == rows["Dara Holm"]["group_id"] is not None
    r = await c.get(f"/v1/rounds/seed/participants/{dara.id}")
    assert [m["name"] for m in r.json()["investor"]["linked"]] == ["Bruno Castell"]


async def test_idempotent_and_merge(db: AsyncSession, key_client: Any, frozen_now: Any) -> None:
    w = await world(db)
    a, b, c_, d, e = await _people(db, w.ws, "Ana One", "Ben Two", "Cy Three", "Di Four", "Ed Five")
    c = key_client(w.key)
    r1 = await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(b.id)]})
    n = len(await activities_of(db, a))
    # Same link again (either direction): 200, same group, nothing written.
    r = await c.post(f"/v1/investors/{b.id}/links", json={"investor_ids": [str(a.id), str(a.id)]})
    assert r.status_code == 200 and r.json()["group_id"] == r1.json()["group_id"]
    assert len(await activities_of(db, a)) == n

    # A second team, then link across: both teams merge into one of the existing groups.
    r2 = await c.post(f"/v1/investors/{c_.id}/links", json={"investor_ids": [str(d.id)]})
    assert len(await _groups(db, w.ws)) == 2
    r = await c.post(f"/v1/investors/{e.id}/links", json={"investor_ids": [str(b.id), str(d.id)]})
    assert r.status_code == 200, r.text
    assert r.json()["group_id"] in {r1.json()["group_id"], r2.json()["group_id"]}
    assert [m["name"] for m in r.json()["investors"]] == [
        "Ana One",
        "Ben Two",
        "Cy Three",
        "Di Four",
        "Ed Five",
    ]
    assert await _groups(db, w.ws) == [await _group_of(db, a)]
    r = await c.get(f"/v1/investors/{c_.id}")
    assert [m["name"] for m in r.json()["linked"]] == ["Ana One", "Ben Two", "Di Four", "Ed Five"]


async def test_unlink_and_dissolve(db: AsyncSession, key_client: Any, frozen_now: Any) -> None:
    w = await world(db)
    a, b, c_ = await _people(db, w.ws, "Ana One", "Ben Two", "Cy Three")
    c = key_client(w.key)
    await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(b.id), str(c_.id)]})
    gid = await _group_of(db, a)
    # Three members: unlinking one leaves a team of two.
    r = await c.delete(f"/v1/investors/{c_.id}/links")
    assert r.status_code == 204
    assert await _group_of(db, c_) is None
    assert await _group_of(db, a) == gid == await _group_of(db, b)
    acts = await activities_of(db, c_, "investor_updated")
    assert acts[-1].data["changes"]["linked_cards"]["to"] == []
    acts = await activities_of(db, a, "investor_updated")
    assert acts[-1].data["changes"]["linked_cards"]["to"] == [str(b.id)]
    # Unlinking someone not linked: 204, nothing written.
    n = len(await activities_of(db, c_))
    assert (await c.delete(f"/v1/investors/{c_.id}/links")).status_code == 204
    assert len(await activities_of(db, c_)) == n
    # Two members: unlinking one dissolves the team.
    assert (await c.delete(f"/v1/investors/{b.id}/links")).status_code == 204
    assert await _group_of(db, a) is None and await _group_of(db, b) is None
    assert await _groups(db, w.ws) == []
    r = await c.get(f"/v1/investors/{a.id}")
    assert r.json()["linked"] == [] and r.json()["group_id"] is None


async def test_delete_investor_dissolves_small_team(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    a, b, c_ = await _people(db, w.ws, "Ana One", "Ben Two", "Cy Three")
    c = key_client(w.key)
    await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(b.id), str(c_.id)]})
    gid = await _group_of(db, a)
    assert (await c.delete(f"/v1/investors/{c_.id}")).status_code == 204
    assert await _group_of(db, a) == gid  # two left: still a team
    r = await c.get(f"/v1/investors/{a.id}")
    assert [m["name"] for m in r.json()["linked"]] == ["Ben Two"]
    assert (await c.delete(f"/v1/investors/{b.id}")).status_code == 204
    assert await _group_of(db, a) is None
    assert await _groups(db, w.ws) == []


async def test_validation_and_cross_workspace(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    (a,) = await _people(db, w.ws, "Ana One")
    other_ws = await make_workspace(db, name="Elsewhere Labs")
    stranger = await make_investor(db, other_ws, name="Sol Stranger", email=None)
    c = key_client(w.key)
    r = await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": []})
    assert r.status_code == 422
    r = await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(a.id)]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(stranger.id)]})
    assert r.status_code == 404 and "Sol" not in r.text
    r = await c.post(f"/v1/investors/{stranger.id}/links", json={"investor_ids": [str(a.id)]})
    assert r.status_code == 404
    assert (await c.delete(f"/v1/investors/{stranger.id}/links")).status_code == 404
    assert await _group_of(db, a) is None and await _group_of(db, stranger) is None


async def test_read_key_cannot_link(db: AsyncSession, key_client: Any, frozen_now: Any) -> None:
    w = await world(db)
    a, b = await _people(db, w.ws, "Ana One", "Ben Two")
    c = key_client(w.reader)
    r = await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(b.id)]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "insufficient_scope"
    r = await c.delete(f"/v1/investors/{a.id}/links")
    assert r.status_code == 403
    assert await _group_of(db, a) is None


async def test_export_has_group_id(db: AsyncSession, key_client: Any, frozen_now: Any) -> None:
    w = await world(db)
    a, b = await _people(db, w.ws, "Ana One", "Ben Two")
    c = key_client(w.key)
    gid = (await c.post(f"/v1/investors/{a.id}/links", json={"investor_ids": [str(b.id)]})).json()[
        "group_id"
    ]
    r = await c.get("/v1/investors/export")
    assert r.status_code == 200
    header = r.text.splitlines()[0].split(",")
    assert "group_id" in header
    assert gid in r.text


@contextmanager
def count_queries(engine: AsyncEngine) -> Iterator[list[str]]:
    seen: list[str] = []

    def before(_conn: Any, _cur: Any, statement: str, *_a: Any) -> None:
        if not statement.lstrip().upper().startswith(("SAVEPOINT", "RELEASE", "ROLLBACK")):
            seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before)


async def test_lists_batch_linked_members(
    db: AsyncSession, key_client: Any, engine: AsyncEngine, frozen_now: Any
) -> None:
    """Listing 4 or 12 linked investors costs the same number of queries (no N+1)."""
    w = await world(db)
    c = key_client(w.key)

    async def add_pairs(start: int, pairs: int) -> None:
        for i in range(start, start + pairs):
            x, y = await _people(db, w.ws, f"Pair{i:02d} Left", f"Pair{i:02d} Right")
            await make_participant(db, w.rnd, x)
            await make_participant(db, w.rnd, y)
            r = await c.post(f"/v1/investors/{x.id}/links", json={"investor_ids": [str(y.id)]})
            assert r.status_code == 200

    async def measure() -> tuple[int, int]:
        with count_queries(engine) as q1:
            r = await c.get("/v1/rounds/seed/participants", params={"limit": 200})
            assert r.status_code == 200
            assert all(len(p["investor"]["linked"]) == 1 for p in r.json()["data"])
        with count_queries(engine) as q2:
            r = await c.get("/v1/investors", params={"limit": 200})
            assert r.status_code == 200
            assert all(len(i["linked"]) == 1 for i in r.json()["data"])
        return len(q1), len(q2)

    await add_pairs(0, 2)
    small = await measure()
    await add_pairs(2, 4)
    large = await measure()
    assert small == large, (small, large)


async def test_mcp_link_tools(db: AsyncSession, mcp_call: Any, frozen_now: Any) -> None:
    w = await world(db)
    bruno, dara, _ = await _people(db, w.ws, "Bruno Castell", "Dara Holm", "Ezra Vance")
    await make_participant(db, w.rnd, bruno)
    res = await mcp_call(
        w.key,
        "link_investors",
        {"investor": "Dara Holm", "investors": ["Bruno Castell @ Harbor Light Ventures"]},
        headers=AGENT,
    )
    assert res.ok, res.text
    assert [m["name"] for m in res.data["team"]] == ["Bruno Castell", "Dara Holm"]
    assert res.data["changed"] is True
    again = await mcp_call(
        w.key, "link_investors", {"investor": str(bruno.id), "investors": [str(dara.id)]}
    )
    assert again.ok and again.data["changed"] is False

    res = await mcp_call(w.key, "get_investor", {"investor": "Bruno Castell"})
    assert res.ok, res.text
    assert res.data["investor"]["linked"] == [
        {"id": str(dara.id), "name": "Dara Holm", "firm": "Harbor Light Ventures"}
    ]
    assert "group_id" not in res.data["investor"]
    res = await mcp_call(w.key, "search_investors", {"query": "Dara"})
    assert res.data["results"][0]["linked"][0]["name"] == "Bruno Castell"
    res = await mcp_call(w.key, "search_investors", {"round": "seed"})
    assert res.data["results"][0]["linked"][0]["name"] == "Dara Holm"
    res = await mcp_call(w.key, "search_investors", {"query": "Ezra"})
    assert "linked" not in res.data["results"][0]

    res = await mcp_call(
        w.key, "link_investors", {"investor": "Dara Holm", "investors": ["Dara Holm"]}
    )
    assert not res.ok and res.code == "validation_error"
    res = await mcp_call(w.key, "link_investors", {"investor": "Dara Holm", "investors": []})
    assert not res.ok
    res = await mcp_call(
        w.reader, "link_investors", {"investor": "Dara Holm", "investors": ["Ezra Vance"]}
    )
    assert not res.ok

    res = await mcp_call(w.key, "unlink_investor", {"investor": "Dara Holm"}, headers=AGENT)
    assert res.ok and res.data["changed"] is True, res.text
    res = await mcp_call(w.key, "unlink_investor", {"investor": "Dara Holm"})
    assert res.ok and res.data["changed"] is False
    assert await _group_of(db, bruno) is None
    acts = await activities_of(db, bruno, "investor_updated")
    assert acts[-1].via == "mcp" and acts[-1].actor_label == "claude-code"


async def test_0009_round_trip() -> None:
    schema = f"t_mig_{pysecrets.token_hex(4)}"
    dsn = TEST_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)

    async def cols() -> set[str]:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = $1 AND table_name = 'investors'",
            schema,
        )
        return {r["column_name"] for r in rows}

    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await asyncio.to_thread(_alembic, schema, "upgrade", "head")
        assert "group_id" in await cols()
        await asyncio.to_thread(_alembic, schema, "downgrade", "0008")
        assert "group_id" not in await cols()
        await asyncio.to_thread(_alembic, schema, "upgrade", "head")
        assert "group_id" in await cols()
    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def test_group_must_be_in_the_same_workspace(db: AsyncSession) -> None:
    ws = await make_workspace(db)
    other = await make_workspace(db)
    inv = await make_investor(db, ws)
    group = InvestorGroup(workspace_id=other.id)
    db.add(group)
    await db.flush()
    async with db.begin_nested() as sp:
        with pytest.raises(IntegrityError):
            await db.execute(
                update(Investor).where(Investor.id == inv.id).values(group_id=group.id)
            )
        await sp.rollback()
