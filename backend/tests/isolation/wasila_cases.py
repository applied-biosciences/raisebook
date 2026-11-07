"""Workspace isolation for the Wasila v1.0.0.0 routes (Funding Room, master list, custom
fields, saved lists, intros, Claude, outreach, decks, funding costs).

Registered into ``test_rest_isolation.CASES`` on import, so ``test_every_route_is_covered``
fails when a new Wasila route has no case here. B's rows are built by :func:`b_rows`; A must
get 404 for every B id, see none of B's rows in lists, and change nothing of B's
(:func:`snapshot`).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.isolation.test_rest_isolation import Ref, Two, case, is_404, no_b
from wasila.models.investor import Investor
from wasila.models.room import (
    Campaign,
    FundingCostLine,
    IntroConnection,
    InvestorField,
    MailSettings,
    OutreachMessage,
    RoomDocument,
    RoomLink,
    RoomVersion,
    SavedList,
)

ACTOR = {"actor_type": "system", "actor_label": "wasila", "via": "system"}
B_DOC = "Bravo secret term sheet"
B_TOKEN = "wslroom_bravo-secret-token-for-isolation-tests-only"


async def b_rows(db: AsyncSession, b: Any, b_inv: Any) -> dict[str, Ref]:
    now = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    doc = RoomDocument(
        workspace_id=b.id,
        title=B_DOC,
        category="legal",
        review_status="approved",
        current_version=1,
        **ACTOR,
    )
    db.add(doc)
    await db.flush()
    db.add(
        RoomVersion(
            workspace_id=b.id,
            document_id=doc.id,
            version=1,
            filename="bravo-terms.pdf",
            content_type="application/pdf",
            size_bytes=5,
            sha256="0" * 64,
            data=b"%PDF-",
            **ACTOR,
        )
    )
    link = RoomLink(
        workspace_id=b.id,
        label="Bravo secret link",
        token_hash=hashlib.sha256(B_TOKEN.encode()).digest(),
        document_ids=[doc.id],
        expires_at=now + timedelta(days=3650),
        **ACTOR,
    )
    fld = InvestorField(
        workspace_id=b.id,
        key="bravo_secret_field",
        label="Bravo secret field",
        kind="ai",
        prompt="Bravo secret prompt",
    )
    lst = SavedList(workspace_id=b.id, name="Bravo secret list", investor_ids=[b_inv.id], **ACTOR)
    intro = IntroConnection(
        workspace_id=b.id, investor_id=b_inv.id, connector_name="Bravo secret connector", **ACTOR
    )
    camp = Campaign(
        workspace_id=b.id, name="Bravo secret campaign", subject="Bravo", body="Bravo", **ACTOR
    )
    db.add_all([link, fld, lst, intro, camp])
    await db.flush()
    msg = OutreachMessage(
        workspace_id=b.id,
        investor_id=b_inv.id,
        campaign_id=camp.id,
        to_email="blake.quill@example.com",
        subject="Bravo secret subject",
        body="Bravo secret body",
        **ACTOR,
    )
    cost = FundingCostLine(
        workspace_id=b.id, kind="cost", grp="Bravo", name="Bravo secret cost", y1=999
    )
    db.add_all([msg, cost])
    db.add(MailSettings(workspace_id=b.id, host="smtp.bravo.example", from_email="b@bravo.example"))
    await db.flush()
    return {
        "doc": Ref(doc.id, name=B_DOC),
        "link": Ref(link.id, name="Bravo secret link"),
        "field": Ref(fld.id, name="Bravo secret field"),
        "list": Ref(lst.id, name="Bravo secret list"),
        "intro": Ref(intro.id, name="Bravo secret connector"),
        "campaign": Ref(camp.id, name="Bravo secret campaign"),
        "msg": Ref(msg.id, name="Bravo secret subject"),
        "cost": Ref(cost.id, name="Bravo secret cost"),
    }


async def snapshot(db: AsyncSession, wid: UUID) -> list[Any]:
    async def rows(stmt: Any) -> list[Any]:
        return [tuple(r) for r in (await db.execute(stmt)).all()]

    return (
        await rows(
            select(
                RoomDocument.id,
                RoomDocument.title,
                RoomDocument.review_status,
                RoomDocument.current_version,
                RoomDocument.updated_at,
            )
            .where(RoomDocument.workspace_id == wid)
            .order_by(RoomDocument.id)
        )
        + await rows(
            select(RoomVersion.id, RoomVersion.version)
            .where(RoomVersion.workspace_id == wid)
            .order_by(RoomVersion.id)
        )
        + await rows(
            select(RoomLink.id, RoomLink.revoked_at, RoomLink.view_count)
            .where(RoomLink.workspace_id == wid)
            .order_by(RoomLink.id)
        )
        + await rows(
            select(InvestorField.id, InvestorField.label).where(InvestorField.workspace_id == wid)
        )
        + await rows(select(SavedList.id, SavedList.name).where(SavedList.workspace_id == wid))
        + await rows(
            select(IntroConnection.id, IntroConnection.strength).where(
                IntroConnection.workspace_id == wid
            )
        )
        + await rows(
            select(OutreachMessage.id, OutreachMessage.status, OutreachMessage.subject).where(
                OutreachMessage.workspace_id == wid
            )
        )
        + await rows(select(Campaign.id, Campaign.name).where(Campaign.workspace_id == wid))
        + await rows(
            select(FundingCostLine.id, FundingCostLine.y1).where(
                FundingCostLine.workspace_id == wid
            )
        )
        + await rows(select(MailSettings.host).where(MailSettings.workspace_id == wid))
        + await rows(select(Investor.id, Investor.custom).where(Investor.workspace_id == wid))
    )


def _bw(t: Two, k: str) -> str:
    return str(t.bw[k].id)


# --- Funding Room ---------------------------------------------------------------------------------


@case("GET", "/v1/funding-room/documents")
async def _fr_list(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/funding-room/documents", params={"q": "Bravo"})
    assert r.status_code == 200 and r.json()["data"] == []
    no_b((await c.get("/v1/funding-room/documents")).text, t)


@case("POST", "/v1/funding-room/documents")
async def _fr_create(c: Any, t: Two, who: str) -> None:
    r = await c.post("/v1/funding-room/documents", json={"title": B_DOC, "category": "legal"})
    assert r.status_code == 201 and r.json()["id"] != _bw(t, "doc")


@case("GET", "/v1/funding-room/documents/{doc_id}")
async def _fr_get(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/funding-room/documents/{_bw(t, 'doc')}"))


@case("PATCH", "/v1/funding-room/documents/{doc_id}")
async def _fr_patch(c: Any, t: Two, who: str) -> None:
    is_404(await c.patch(f"/v1/funding-room/documents/{_bw(t, 'doc')}", json={"title": "Hacked"}))


@case("DELETE", "/v1/funding-room/documents/{doc_id}")
async def _fr_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/funding-room/documents/{_bw(t, 'doc')}"))


@case("POST", "/v1/funding-room/documents/{doc_id}/versions")
async def _fr_upload(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post(
            f"/v1/funding-room/documents/{_bw(t, 'doc')}/versions",
            content=b"%PDF-x",
            headers={"X-Filename": "x.pdf"},
        )
    )


@case("GET", "/v1/funding-room/documents/{doc_id}/versions")
async def _fr_versions(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/funding-room/documents/{_bw(t, 'doc')}/versions"))


@case("GET", "/v1/funding-room/documents/{doc_id}/download")
async def _fr_download(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/funding-room/documents/{_bw(t, 'doc')}/download"))


@case("GET", "/v1/funding-room/links")
async def _fr_links(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/funding-room/links")
    assert r.status_code == 200 and r.json()["data"] == []


@case("POST", "/v1/funding-room/links")
async def _fr_link_create(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post("/v1/funding-room/links", json={"label": "x", "document_ids": [_bw(t, "doc")]})
    )


@case("DELETE", "/v1/funding-room/links/{link_id}")
async def _fr_link_revoke(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/funding-room/links/{_bw(t, 'link')}"))


@case("GET", "/v1/funding-room/checklist")
async def _fr_checklist(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/funding-room/checklist", params={"jurisdiction": "ksa"})
    assert r.status_code == 200
    assert all(i["document_ids"] == [] for i in r.json()["items"])
    no_b(r.text, t)


@case("GET", "/v1/funding-room/events")
async def _fr_events(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/funding-room/events")
    assert r.status_code == 200
    no_b(r.text, t)


# --- master list, fields, lists, intros -----------------------------------------------------------


@case("GET", "/v1/master-list/facets")
async def _ml_facets(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/master-list/facets")
    assert r.json()["total"] == 1


@case("POST", "/v1/master-list/search")
async def _ml_search(c: Any, t: Two, who: str) -> None:
    r = await c.post("/v1/master-list/search", json={"q": "blake"})
    assert r.json()["total"] == 0
    is_404(await c.post("/v1/master-list/search", json={"in_round": t.b_round.slug}))
    no_b((await c.post("/v1/master-list/search", json={})).text, t)


@case("POST", "/v1/master-list/ask")
async def _ml_ask(c: Any, t: Two, who: str) -> None:
    # A has no Claude key: the question never runs, and nothing of B is used.
    r = await c.post("/v1/master-list/ask", json={"question": "Bravo investors"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_claude_key"


@case("GET", "/v1/investor-fields")
async def _fields(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/investor-fields")
    assert r.json()["data"] == []


@case("POST", "/v1/investor-fields")
async def _field_create(c: Any, t: Two, who: str) -> None:
    # B's field key is free in A.
    r = await c.post("/v1/investor-fields", json={"label": "Bravo secret field"})
    assert r.status_code == 201 and r.json()["id"] != _bw(t, "field")


@case("DELETE", "/v1/investor-fields/{field_id}")
async def _field_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/investor-fields/{_bw(t, 'field')}"))


@case("POST", "/v1/investor-fields/{field_id}/fill")
async def _field_fill(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post(
            f"/v1/investor-fields/{_bw(t, 'field')}/fill",
            json={"investor_ids": [str(t.a_inv.id)]},
        )
    )


@case("PUT", "/v1/investors/{investor_id}/custom")
async def _custom(c: Any, t: Two, who: str) -> None:
    is_404(await c.put(f"/v1/investors/{t.b_inv.id}/custom", json={"values": {}}))


@case("GET", "/v1/saved-lists")
async def _lists(c: Any, t: Two, who: str) -> None:
    assert (await c.get("/v1/saved-lists")).json()["data"] == []


@case("POST", "/v1/saved-lists")
async def _list_create(c: Any, t: Two, who: str) -> None:
    is_404(await c.post("/v1/saved-lists", json={"name": "x", "investor_ids": [str(t.b_inv.id)]}))


@case("GET", "/v1/saved-lists/{list_id}")
async def _list_get(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/saved-lists/{_bw(t, 'list')}"))


@case("DELETE", "/v1/saved-lists/{list_id}")
async def _list_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/saved-lists/{_bw(t, 'list')}"))


@case("GET", "/v1/investors/{investor_id}/intros")
async def _intros(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/investors/{t.b_inv.id}/intros"))


@case("POST", "/v1/investors/{investor_id}/intros")
async def _intro_add(c: Any, t: Two, who: str) -> None:
    is_404(await c.post(f"/v1/investors/{t.b_inv.id}/intros", json={"connector_name": "x"}))


@case("DELETE", "/v1/intros/{intro_id}")
async def _intro_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/intros/{_bw(t, 'intro')}"))


# --- Claude ---------------------------------------------------------------------------------------


@case("GET", "/v1/claude")
async def _claude(c: Any, t: Two, who: str) -> None:
    assert (await c.get("/v1/claude")).json()["ready"] is False


@case("PUT", "/v1/claude/key")
async def _claude_key(c: Any, t: Two, who: str) -> None:
    # Too short to be a key: refused before any call to Anthropic (keys get 403 or 422).
    r = await c.put("/v1/claude/key", json={"api_key": "sk-ant-short"})
    assert r.status_code in (403, 422)


@case("DELETE", "/v1/claude/key")
async def _claude_key_delete(c: Any, t: Two, who: str) -> None:
    r = await c.delete("/v1/claude/key")
    assert r.status_code in (204, 403)


@case("PATCH", "/v1/claude")
async def _claude_model(c: Any, t: Two, who: str) -> None:
    r = await c.patch("/v1/claude", json={"model": "claude-opus-5-5"})
    assert r.json()["model"] == "claude-opus-5-5"


# --- outreach -------------------------------------------------------------------------------------


@case("GET", "/v1/outreach/mail-settings")
async def _mail(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/outreach/mail-settings")
    assert r.json()["configured"] is False and "bravo" not in r.text


@case("PUT", "/v1/outreach/mail-settings")
async def _mail_put(c: Any, t: Two, who: str) -> None:
    r = await c.put(
        "/v1/outreach/mail-settings",
        json={"host": "smtp.alpha.example", "from_email": "a@alpha.example"},
    )
    assert r.status_code in (200, 403)


@case("GET", "/v1/outreach/messages")
async def _msgs(c: Any, t: Two, who: str) -> None:
    assert (await c.get("/v1/outreach/messages")).json()["data"] == []
    is_404(await c.get("/v1/outreach/messages", params={"investor_id": str(t.b_inv.id)}))
    is_404(await c.get("/v1/outreach/messages", params={"campaign_id": _bw(t, "campaign")}))


@case("POST", "/v1/outreach/messages")
async def _msg_create(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post(
            "/v1/outreach/messages",
            json={"investor_id": str(t.b_inv.id), "subject": "x", "body": "x"},
        )
    )
    is_404(
        await c.post(
            "/v1/outreach/messages",
            json={
                "investor_id": str(t.a_inv.id),
                "subject": "x",
                "body": "x",
                "to_email": "a@example.com",
                "attachment_ids": [_bw(t, "doc")],
            },
        )
    )


@case("POST", "/v1/outreach/draft")
async def _draft(c: Any, t: Two, who: str) -> None:
    is_404(await c.post("/v1/outreach/draft", json={"investor_id": str(t.b_inv.id)}))


@case("GET", "/v1/outreach/messages/{msg_id}")
async def _msg_get(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/outreach/messages/{_bw(t, 'msg')}"))


@case("PATCH", "/v1/outreach/messages/{msg_id}")
async def _msg_patch(c: Any, t: Two, who: str) -> None:
    is_404(await c.patch(f"/v1/outreach/messages/{_bw(t, 'msg')}", json={"subject": "Hacked"}))


@case("DELETE", "/v1/outreach/messages/{msg_id}")
async def _msg_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/outreach/messages/{_bw(t, 'msg')}"))


@case("POST", "/v1/outreach/messages/{msg_id}/send")
async def _msg_send(c: Any, t: Two, who: str) -> None:
    is_404(await c.post(f"/v1/outreach/messages/{_bw(t, 'msg')}/send"))


@case("POST", "/v1/outreach/messages/{msg_id}/replied")
async def _msg_replied(c: Any, t: Two, who: str) -> None:
    is_404(await c.post(f"/v1/outreach/messages/{_bw(t, 'msg')}/replied", json={}))


@case("GET", "/v1/outreach/follow-ups")
async def _follow_ups(c: Any, t: Two, who: str) -> None:
    assert (await c.get("/v1/outreach/follow-ups")).json()["data"] == []


@case("GET", "/v1/outreach/campaigns")
async def _camps(c: Any, t: Two, who: str) -> None:
    assert (await c.get("/v1/outreach/campaigns")).json()["data"] == []


@case("POST", "/v1/outreach/campaigns")
async def _camp_create(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post(
            "/v1/outreach/campaigns",
            json={"name": "x", "subject": "x", "body": "x", "attachment_ids": [_bw(t, "doc")]},
        )
    )


@case("GET", "/v1/outreach/campaigns/{campaign_id}")
async def _camp_get(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/outreach/campaigns/{_bw(t, 'campaign')}"))


@case("POST", "/v1/outreach/campaigns/{campaign_id}/drafts")
async def _camp_drafts(c: Any, t: Two, who: str) -> None:
    is_404(
        await c.post(
            f"/v1/outreach/campaigns/{_bw(t, 'campaign')}/drafts",
            json={"investor_ids": [str(t.a_inv.id)]},
        )
    )


# --- decks ----------------------------------------------------------------------------------------


@case("GET", "/v1/decks/{doc_id}")
async def _deck(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/decks/{_bw(t, 'doc')}"))


@case("POST", "/v1/decks/{doc_id}/save")
async def _deck_save(c: Any, t: Two, who: str) -> None:
    is_404(await c.post(f"/v1/decks/{_bw(t, 'doc')}/save", json={"base_version": 1}))


@case("POST", "/v1/decks/{doc_id}/suggest")
async def _deck_suggest(c: Any, t: Two, who: str) -> None:
    is_404(await c.post(f"/v1/decks/{_bw(t, 'doc')}/suggest", json={"instruction": "shorter"}))


@case("GET", "/v1/decks/{doc_id}/pdf")
async def _deck_pdf(c: Any, t: Two, who: str) -> None:
    is_404(await c.get(f"/v1/decks/{_bw(t, 'doc')}/pdf"))


# --- funding costs --------------------------------------------------------------------------------


@case("GET", "/v1/funding-costs")
async def _costs(c: Any, t: Two, who: str) -> None:
    r = await c.get("/v1/funding-costs")
    assert r.json()["data"] == []
    no_b(r.text, t)


@case("GET", "/v1/funding-costs/merge-fields")
async def _cost_merge_fields(c: Any, t: Two, who: str) -> None:
    # A has no lines; B's figures never show through.
    r = await c.get("/v1/funding-costs/merge-fields")
    assert r.status_code == 200
    assert all(f["value"] == "" for f in r.json()["data"])
    no_b(r.text, t)


@case("POST", "/v1/funding-costs")
async def _cost_create(c: Any, t: Two, who: str) -> None:
    r = await c.post("/v1/funding-costs", json={"kind": "cost", "grp": "A", "name": "A cost"})
    assert r.status_code == 201


@case("PATCH", "/v1/funding-costs/{line_id}")
async def _cost_patch(c: Any, t: Two, who: str) -> None:
    is_404(await c.patch(f"/v1/funding-costs/{_bw(t, 'cost')}", json={"y1": 1}))


@case("DELETE", "/v1/funding-costs/{line_id}")
async def _cost_delete(c: Any, t: Two, who: str) -> None:
    is_404(await c.delete(f"/v1/funding-costs/{_bw(t, 'cost')}"))


@case("POST", "/v1/funding-costs/import")
async def _cost_import(c: Any, t: Two, who: str) -> None:
    # Replacing A's lines never touches B's (the snapshot checks).
    r = await c.post("/v1/funding-costs/import", content=b"not a workbook")
    assert r.status_code == 422


@case("POST", "/v1/imports/convert")
async def _convert(c: Any, t: Two, who: str) -> None:
    r = await c.post(
        "/v1/imports/convert", content=b"Name\nBlake\n", headers={"X-Filename": "x.csv"}
    )
    assert r.status_code == 200
