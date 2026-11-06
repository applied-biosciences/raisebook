"""Wasila v1.0.0.0 features over REST: US/UK/Saudi rounds, the Funding Room and share links,
Excel/Word lead import, the master list, custom fields and AI columns, saved lists, warm
intros, Claude, email outreach and campaigns, the deck editor and funding costs.

Fictional data only (example.com, made-up people and firms). Claude and mail never leave the
process (``claude_mock``; ``WASILA_OUTREACH_BACKEND=memory``).
"""

from __future__ import annotations

import io
import json
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.helpers import activities_of, world
from tests.factories import make_investor
from wasila.core import clock
from wasila.models.investor import Investor
from wasila.services import outreach as outreach_svc

AGENT = {"X-Agent-Name": "claude-code", "X-Agent-Model": "claude-opus-5-5"}
PDF = b"%PDF-1.4 fictional one-page summary\n%%EOF\n"


def _upload(c: Any, doc_id: str, name: str, data: bytes) -> Any:
    return c.post(
        f"/v1/funding-room/documents/{doc_id}/versions",
        content=data,
        headers={"X-Filename": quote(name), "Content-Type": "application/octet-stream"},
    )


async def _approved_doc(c: Any, title: str = "One-page summary", data: bytes = PDF) -> str:
    r = await c.post(
        "/v1/funding-room/documents",
        json={"title": title, "category": "pitch", "review_status": "approved"},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    r = await _upload(c, doc_id, f"{title}.pdf", data)
    assert r.status_code == 201, r.text
    return str(doc_id)


def _deck_bytes() -> bytes:
    prs = Presentation()
    for title, body in (
        ("Kestrel Robotics", "Robots that sort parcels."),
        ("Traction", "Three fictional pilots."),
        ("The ask", "Raising 1m."),
    ):
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = title
        tb = s.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
        tb.text_frame.text = body
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


# --- rounds: US / UK / Saudi ----------------------------------------------------------------------


async def test_round_jurisdictions(db: AsyncSession, key_client: Any, frozen_now: Any) -> None:
    w = await world(db)
    c = key_client(w.key)
    r = await c.post(
        "/v1/rounds",
        json={
            "name": "UK pre-seed",
            "jurisdiction": "uk",
            "tax_relief": "seis_eis",
            "instrument": "asa",
        },
    )
    assert r.status_code == 201, r.text
    out = r.json()
    assert (out["jurisdiction"], out["tax_relief"], out["instrument"], out["currency"]) == (
        "uk",
        "seis_eis",
        "asa",
        "GBP",
    )
    r = await c.post(
        "/v1/rounds", json={"name": "KSA seed", "jurisdiction": "ksa", "sharia_compliant": True}
    )
    assert r.json()["currency"] == "SAR" and r.json()["sharia_compliant"] is True
    r = await c.post(
        "/v1/rounds", json={"name": "Bad", "jurisdiction": "ksa", "tax_relief": "seis"}
    )
    assert r.status_code == 422 and "UK rounds only" in r.text
    r = await c.patch(f"/v1/rounds/{w.rnd.slug}", json={"jurisdiction": "us"})
    assert r.json()["jurisdiction"] == "us"


# --- Funding Room ---------------------------------------------------------------------------------


async def test_funding_room_documents_versions_and_events(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key, headers=AGENT)
    r = await c.post(
        "/v1/funding-room/documents",
        json={"title": "Cap table", "category": "corporate", "jurisdiction": "uk"},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["review_status"] == "draft" and doc["current_version"] == 0
    assert (await _upload(c, doc["id"], "cap-table.exe", b"MZ")).status_code == 422
    assert (await _upload(c, doc["id"], "cap table.xlsx", b"")).status_code == 422
    r = await _upload(c, doc["id"], "cap table.xlsx", b"PK fictional")
    assert r.status_code == 201 and r.json()["version"] == 1
    r = await _upload(c, doc["id"], "cap table v2.xlsx", b"PK fictional two")
    assert r.json()["version"] == 2
    r = await c.get(f"/v1/funding-room/documents/{doc['id']}/versions")
    assert [v["version"] for v in r.json()["data"]] == [2, 1]
    r = await c.get(f"/v1/funding-room/documents/{doc['id']}/download", params={"version": 1})
    assert r.status_code == 200 and r.content == b"PK fictional"
    assert "cap%20table.xlsx" in r.headers["content-disposition"]
    r = await c.patch(f"/v1/funding-room/documents/{doc['id']}", json={"review_status": "approved"})
    assert r.json()["review_status"] == "approved" and r.json()["reviewed_at"]
    r = await c.get("/v1/funding-room/documents", params={"jurisdiction": "uk"})
    assert r.json()["data"][0]["latest"]["filename"] == "cap table v2.xlsx"
    assert r.json()["counts"] == {"approved": 1}
    kinds = [e["kind"] for e in (await c.get("/v1/funding-room/events")).json()["data"]]
    assert kinds.count("version_added") == 2 and "downloaded" in kinds and "updated" in kinds
    events = (await c.get("/v1/funding-room/events")).json()["data"]
    assert all(e["actor_label"] == "claude-code" for e in events)
    r = await c.get("/v1/funding-room/checklist", params={"jurisdiction": "uk"})
    keys = {i["key"]: i["status"] for i in r.json()["items"]}
    assert keys["cap_table"] == "approved" and keys["uk_advance_assurance"] == "missing"
    # A UK-only document does not count for the Saudi checklist.
    r = await c.get("/v1/funding-room/checklist", params={"jurisdiction": "ksa"})
    keys = {i["key"]: i["status"] for i in r.json()["items"]}
    assert keys["cap_table"] == "missing" and keys["ksa_cr"] == "missing"
    assert (await c.delete(f"/v1/funding-room/documents/{doc['id']}")).status_code == 204
    assert (await c.get(f"/v1/funding-room/documents/{doc['id']}")).status_code == 404


async def test_share_links_only_expose_approved_and_expire(
    db: AsyncSession, key_client: Any, client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    ok = await _approved_doc(c)
    r = await c.post(
        "/v1/funding-room/documents", json={"title": "Draft model", "category": "financial"}
    )
    draft = r.json()["id"]
    await _upload(c, draft, "model.xlsx", b"PK draft")
    r = await c.post(
        "/v1/funding-room/links", json={"label": "Fictional Fund", "document_ids": [ok, draft]}
    )
    assert r.status_code == 422 and "Draft model" in r.text
    r = await c.post(
        "/v1/funding-room/links", json={"label": "Fictional Fund", "document_ids": [ok], "days": 7}
    )
    assert r.status_code == 201, r.text
    link = r.json()
    token = link["token"]
    assert token.startswith("wslroom_")
    r = await client.get(f"/v1/room-links/{token}")
    assert r.status_code == 200, r.text
    assert r.json()["company"] == w.ws.name
    assert [d["title"] for d in r.json()["documents"]] == ["One-page summary"]
    r = await client.get(f"/v1/room-links/{token}/documents/{ok}")
    assert r.status_code == 200 and r.content == PDF
    assert (await client.get(f"/v1/room-links/{token}/documents/{draft}")).status_code == 404
    links = (await c.get("/v1/funding-room/links")).json()["data"]
    assert links[0]["view_count"] == 1 and "token" not in links[0]
    clock.freeze(frozen_now + timedelta(days=8))
    assert (await client.get(f"/v1/room-links/{token}")).status_code == 404
    clock.freeze(frozen_now)
    r = await c.delete(f"/v1/funding-room/links/{link['id']}")
    assert r.json()["state"] == "revoked"
    assert (await client.get(f"/v1/room-links/{token}")).status_code == 404
    assert (await client.get("/v1/room-links/not-a-token")).status_code == 404


# --- lead import from Excel and Word --------------------------------------------------------------


def _angel_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Investors"
    ws.append(
        [
            "Country",
            "City",
            "Contact name",
            "Company name",
            "Role",
            "Contact email",
            "Mobile number",
            "AI interest (Y/N)",
            "Healthcare interest (Y/N)",
            "Interest tags shown on list",
            "Source list",
        ]
    )
    ws.append(
        [
            "Saudi Arabia",
            "Riyadh",
            "Rana Fictional",
            "Dune Ventures",
            "Partner",
            "rana@dune.example.com",
            "+966 50 000 0000",
            "N",
            "Y",
            "Wellness; E-commerce (+12)",
            "Demo list",
        ]
    )
    ws.append(
        [
            "UK",
            "London",
            "Oliver Sample",
            "Thames Angels",
            "Angel",
            "oliver@thames.example.com",
            "",
            "Y",
            "Y",
            "Health Care",
            "Demo list",
        ]
    )
    ws.append(
        [
            "United States",
            "Austin",
            "Maya Madeup",
            "Prairie Capital",
            "GP",
            "",
            "",
            "N",
            "N",
            "",
            "Demo list",
        ]
    )
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


async def test_import_excel_into_master_list_and_search(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    r = await c.post(
        "/v1/imports/convert", content=_angel_xlsx(), headers={"X-Filename": "angels.xlsx"}
    )
    assert r.status_code == 200, r.text
    table = r.json()["tables"][0]
    assert table["name"] == "Investors" and table["rows"] == 3
    r = await c.post("/v1/imports/preview", json={"content": table["csv"]})
    assert r.status_code == 200, r.text
    r = await c.post("/v1/imports", json={"content": table["csv"], "source": "Angel list"})
    assert r.status_code == 200, r.text
    rana = await db.scalar(select(Investor).where(Investor.name == "Rana Fictional"))
    assert rana is not None
    assert (rana.country, rana.phone, rana.firm, rana.title) == (
        "Saudi Arabia",
        "+966 50 000 0000",
        "Dune Ventures",
        "Partner",
    )
    assert "Healthcare" in rana.tags and "AI" not in rana.tags and "E-commerce" in rana.tags
    oliver = await db.scalar(select(Investor).where(Investor.name == "Oliver Sample"))
    assert oliver is not None and oliver.country == "United Kingdom"
    assert {"AI", "Healthcare"} <= set(oliver.tags)

    async def names(**filters: Any) -> list[str]:
        r = await c.post("/v1/master-list/search", json=filters)
        assert r.status_code == 200, r.text
        return sorted(i["name"] for i in r.json()["data"])

    assert await names(countries=["KSA"]) == ["Rana Fictional"]
    assert await names(countries=["GCC"]) == ["Rana Fictional"]
    assert await names(tags_any=["healthcare"]) == ["Oliver Sample", "Rana Fictional"]
    assert await names(has_email=False) == ["Maya Madeup"]
    assert await names(countries=["uk", "us"], not_contacted=True) == [
        "Maya Madeup",
        "Oliver Sample",
    ]
    facets = (await c.get("/v1/master-list/facets")).json()
    assert facets["total"] == 3

    # Word tables convert too.
    from docx import Document

    d = Document()
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Name", "Firm"
    t.cell(1, 0).text, t.cell(1, 1).text = "Wren Example", "Harbor Fund"
    buf = io.BytesIO()
    d.save(buf)
    r = await c.post(
        "/v1/imports/convert", content=buf.getvalue(), headers={"X-Filename": "list.docx"}
    )
    assert r.json()["tables"][0]["csv"].startswith("Name,Firm")
    r = await c.post("/v1/imports/convert", content=b"x", headers={"X-Filename": "list.pdf"})
    assert r.status_code == 422


# --- custom fields, AI columns, saved lists, intros, Ask Wasila -------------------------------


async def test_fields_lists_intros_and_claude(
    db: AsyncSession,
    key_client: Any,
    session_client: Any,
    claude_mock: Any,
    frozen_now: Any,
) -> None:
    w = await world(db)
    c = key_client(w.key)
    inv = await make_investor(
        db, w.ws, name="Iris Fable", firm="Lumen Health Fund", email="iris@lumen.example.com"
    )
    inv.country = "United Kingdom"
    inv.tags = ["Healthcare"]
    await db.flush()

    r = await c.post(
        "/v1/investor-fields",
        json={"label": "Ticket band", "kind": "select", "options": ["Small", "Large"]},
    )
    assert r.status_code == 201 and r.json()["key"] == "ticket_band"
    assert (await c.post("/v1/investor-fields", json={"label": "Ticket band"})).status_code == 409
    r = await c.put(f"/v1/investors/{inv.id}/custom", json={"values": {"ticket_band": "Huge"}})
    assert r.status_code == 422
    r = await c.put(f"/v1/investors/{inv.id}/custom", json={"values": {"ticket_band": "Large"}})
    assert r.json()["custom"] == {"ticket_band": "Large"}
    r = await c.post("/v1/master-list/search", json={"custom": {"ticket_band": "large"}})
    assert r.json()["total"] == 1

    # Without a key, Claude features say what to do.
    r = await c.post("/v1/master-list/ask", json={"question": "UK healthcare investors"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_claude_key"

    # Only an owner on the web saves the key; it is verified first and never returned.
    r = await c.put("/v1/claude/key", json={"api_key": "sk-ant-fictional-0000000000-test"})
    assert r.status_code == 403
    owner = await session_client(w.owner, w.ws)
    r = await owner.put("/v1/claude/key", json={"api_key": "sk-ant-fictional-0000000000-test"})
    assert r.status_code == 200, r.text
    assert r.json()["ready"] is True and r.json()["key_last4"] == "test"
    assert "fictional" not in r.text
    assert claude_mock.requests[-1]["max_tokens"] == 5

    claude_mock.replies = [
        json.dumps(
            {"countries": ["UK"], "tags_any": ["Healthcare"], "explanation": "UK healthcare"}
        )
    ]
    r = await c.post("/v1/master-list/ask", json={"question": "UK healthcare investors"})
    assert r.status_code == 200, r.text
    assert [i["name"] for i in r.json()["data"]] == ["Iris Fable"]
    assert r.json()["explanation"] == "UK healthcare"
    sent = claude_mock.requests[-1]
    assert sent["messages"][0]["content"] == "UK healthcare investors"
    assert "iris@lumen" not in json.dumps(sent)

    r = await c.post(
        "/v1/investor-fields",
        json={
            "label": "Fit for us",
            "kind": "ai",
            "prompt": "Would they back a health AI company?",
        },
    )
    fld = r.json()
    claude_mock.replies = ["Likely: invests in digital health"]
    r = await c.post(f"/v1/investor-fields/{fld['id']}/fill", json={"investor_ids": [str(inv.id)]})
    assert r.status_code == 200, r.text
    assert r.json()["filled"][str(inv.id)] == "Likely: invests in digital health"
    assert "iris@lumen" not in json.dumps(claude_mock.requests[-1])
    r = await c.post(f"/v1/investor-fields/{fld['id']}/fill", json={"investor_ids": [str(inv.id)]})
    assert r.json()["skipped"] == [str(inv.id)]

    r = await c.post(
        "/v1/saved-lists",
        json={"name": "UK health", "question": "UK healthcare", "filters": {"countries": ["UK"]}},
    )
    assert r.status_code == 201
    lst = r.json()
    r = await c.get(f"/v1/saved-lists/{lst['id']}")
    assert r.json()["total"] == 1

    r = await c.post(
        f"/v1/investors/{inv.id}/intros",
        json={"connector_name": "Sam Connector", "relationship": "Former colleague", "strength": 3},
    )
    assert r.status_code == 201, r.text
    await c.post(
        f"/v1/investors/{inv.id}/intros", json={"connector_name": "Pat Weak", "strength": 1}
    )
    r = await c.get(f"/v1/investors/{inv.id}/intros")
    assert r.json()["best"]["connector_name"] == "Sam Connector"
    r = await c.post("/v1/master-list/search", json={"q": "iris"})
    assert r.json()["intros"][str(inv.id)]["connector_name"] == "Sam Connector"
    await db.refresh(inv)
    assert inv.warm_intro_by == "Sam Connector"
    weak = (await c.get(f"/v1/investors/{inv.id}/intros")).json()["data"][1]
    assert weak["connector_name"] == "Pat Weak"
    assert (await c.delete(f"/v1/intros/{weak['id']}")).status_code == 204
    assert (await c.delete(f"/v1/intros/{weak['id']}")).status_code == 404


# --- email outreach -------------------------------------------------------------------------------


async def test_outreach_draft_attach_send_and_reply(
    db: AsyncSession, key_client: Any, claude_mock: Any, session_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    owner = await session_client(w.owner, w.ws)
    await owner.put("/v1/claude/key", json={"api_key": "sk-ant-fictional-0000000000-test"})
    inv = await make_investor(
        db, w.ws, name="Nadia Example", firm="Oasis Partners", email="nadia@oasis.example.com"
    )
    doc = await _approved_doc(c)

    claude_mock.replies = [
        json.dumps({"subject": "Kestrel x Oasis", "body": "Dear Nadia,\n\nA short note.\n\nBest"})
    ]
    r = await c.post(
        "/v1/outreach/draft",
        json={
            "investor_id": str(inv.id),
            "attachment_ids": [doc],
            "instructions": "Mention Riyadh",
        },
    )
    assert r.status_code == 201, r.text
    msg = r.json()
    assert msg["status"] == "draft" and msg["drafted_by"] == "claude"
    assert msg["attachments"][0]["filename"] == "One-page summary.pdf"
    prompt = claude_mock.requests[-1]["messages"][0]["content"]
    assert "nadia@oasis" not in prompt and "One-page summary" in prompt
    assert outreach_svc.SENT == []  # drafting never sends

    r = await c.patch(
        f"/v1/outreach/messages/{msg['id']}", json={"subject": "Kestrel Robotics and Oasis"}
    )
    assert r.json()["subject"] == "Kestrel Robotics and Oasis"
    r = await c.post(f"/v1/outreach/messages/{msg['id']}/send")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and r.json()["sent_at"]
    assert len(outreach_svc.SENT) == 1
    m = outreach_svc.SENT[0]
    assert m["To"] == "nadia@oasis.example.com" and m["Subject"] == "Kestrel Robotics and Oasis"
    assert [p.get_filename() for p in m.iter_attachments()] == ["One-page summary.pdf"]
    acts = await activities_of(db, inv, "email")
    assert len(acts) == 1 and acts[0].data["direction"] == "outbound"
    assert "One-page summary.pdf" in (acts[0].body or "")
    # Sending again is a no-op; a sent message cannot change.
    await c.post(f"/v1/outreach/messages/{msg['id']}/send")
    assert len(outreach_svc.SENT) == 1
    r = await c.patch(f"/v1/outreach/messages/{msg['id']}", json={"subject": "x"})
    assert r.status_code == 409
    r = await c.post(
        f"/v1/outreach/messages/{msg['id']}/replied", json={"note": "Nadia replied: call Tuesday"}
    )
    assert r.json()["replied_at"]
    assert len(await activities_of(db, inv, "email")) == 2

    no_email = await make_investor(db, w.ws, name="Quinn Noemail", email=None)
    r = await c.post(
        "/v1/outreach/messages",
        json={"investor_id": str(no_email.id), "subject": "Hi", "body": "Hi"},
    )
    assert r.status_code == 422


async def test_campaigns_mail_merge_and_follow_ups(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    a = await make_investor(
        db, w.ws, name="Ada Sample", firm="North Fund", email="ada@north.example.com"
    )
    b = await make_investor(db, w.ws, name="Ben Sample", firm="South Fund", email=None)
    r = await c.post(
        "/v1/outreach/campaigns",
        json={
            "name": "November update",
            "kind": "update",
            "subject": "Kestrel update for {firm}",
            "body": "Hi {first_name},\n\nOur November update.",
            "follow_up_days": 5,
        },
    )
    assert r.status_code == 201, r.text
    camp = r.json()
    r = await c.post(
        f"/v1/outreach/campaigns/{camp['id']}/drafts", json={"investor_ids": [str(a.id), str(b.id)]}
    )
    out = r.json()
    assert [m["subject"] for m in out["created"]] == ["Kestrel update for North Fund"]
    assert out["created"][0]["body"].startswith("Hi Ada,")
    assert out["skipped"][0]["reason"] == "no email"
    assert outreach_svc.SENT == []
    r = await c.post(
        f"/v1/outreach/campaigns/{camp['id']}/drafts", json={"investor_ids": [str(a.id)]}
    )
    assert r.json()["skipped"][0]["reason"] == "already drafted"
    await c.post(f"/v1/outreach/messages/{out['created'][0]['id']}/send")
    assert (await c.get("/v1/outreach/follow-ups")).json()["data"] == []
    clock.freeze(frozen_now + timedelta(days=6))
    assert len((await c.get("/v1/outreach/follow-ups")).json()["data"]) == 1
    clock.freeze(frozen_now)
    r = await c.get(f"/v1/outreach/campaigns/{camp['id']}")
    assert r.json()["stats"] == {"drafts": 0, "sent": 1, "failed": 0, "replied": 0}


async def test_mail_settings_need_owner_and_hide_password(
    db: AsyncSession, key_client: Any, session_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    body = {
        "host": "smtp.example.com",
        "port": 587,
        "username": "founder@example.com",
        "password": "fictional-app-password",
        "from_email": "founder@example.com",
        "from_name": "Kestrel Founder",
    }
    assert (await key_client(w.key).put("/v1/outreach/mail-settings", json=body)).status_code == 403
    owner = await session_client(w.owner, w.ws)
    r = await owner.put("/v1/outreach/mail-settings", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["password_set"] is True and "fictional-app-password" not in r.text


# --- deck editor ----------------------------------------------------------------------------------


async def test_deck_editor_saves_new_version(
    db: AsyncSession, key_client: Any, session_client: Any, claude_mock: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    r = await c.post(
        "/v1/funding-room/documents", json={"title": "Investor deck", "category": "pitch"}
    )
    doc = r.json()["id"]
    assert (await _upload(c, doc, "deck.pptx", _deck_bytes())).status_code == 201
    r = await c.get(f"/v1/decks/{doc}")
    assert r.status_code == 200, r.text
    deck = r.json()
    assert len(deck["slides"]) == 3 and deck["slides"][1]["title"] == "Traction"
    shape = deck["slides"][2]["shapes"][-1]
    assert shape["text"] == "Raising 1m."
    r = await c.post(
        f"/v1/decks/{doc}/save",
        json={
            "base_version": 1,
            "edits": [{"slide": 3, "shape": shape["shape"], "text": "Raising £1m pre-seed"}],
            "hidden": [2],
            "order": [3, 1, 2],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2
    deck2 = (await c.get(f"/v1/decks/{doc}")).json()
    assert deck2["version"] == 2
    assert deck2["slides"][0]["shapes"][-1]["text"] == "Raising £1m pre-seed"
    assert deck2["slides"][2]["hidden"] is True
    # The first version is untouched.
    assert (await c.get(f"/v1/decks/{doc}", params={"version": 1})).json()["slides"][2]["shapes"][
        -1
    ]["text"] == "Raising 1m."
    r = await c.post(f"/v1/decks/{doc}/save", json={"base_version": 2, "order": [1, 1, 2]})
    assert r.status_code == 422

    owner = await session_client(w.owner, w.ws)
    await owner.put("/v1/claude/key", json={"api_key": "sk-ant-fictional-0000000000-test"})
    claude_mock.replies = [
        json.dumps(
            {
                "suggestions": [
                    {"slide": 1, "shape": shape["shape"], "text": "Raising £1m", "why": "shorter"}
                ]
            }
        )
    ]
    r = await c.post(f"/v1/decks/{doc}/suggest", json={"instruction": "Make it shorter"})
    assert r.status_code == 200, r.text
    assert r.json()["suggestions"][0]["text"] == "Raising £1m"
    # Suggestions change nothing.
    assert (await c.get(f"/v1/decks/{doc}")).json()["version"] == 2


# --- funding costs --------------------------------------------------------------------------------


def _costs_xlsx() -> bytes:
    wb = Workbook()
    u = wb.active
    u.title = "Use of funds"
    u.append(["Use of the round"])
    u.append(["Category", "£", "% of round", "Objective"])
    u.append(["Engineering", 600000, 0.6, "Build the product"])
    u.append(["Sales", 400000, 0.4, "First customers"])
    u.append(["Total", 1000000])
    u.append(["SEIS (first)", 250000])
    u.append(["EIS (balance)", 750000])
    s = wb.create_sheet("Summary")
    s.append(["Fictional plan"])
    s.append(["£", "Year 1", "Year 2", "Year 3", "Year 4", "48 months"])
    s.append(["Profit and loss"])
    s.append(["Licence income", 0, 200000, 600000, 900000, 1700000])
    s.append(["Total income", 0, 200000, 600000, 900000, 1700000])
    s.append(["Hosting", 12000, 24000, 36000, 48000, 120000])
    s.append(["Total direct costs", 12000, 24000, 36000, 48000, 120000])
    s.append(["People: engineering", 300000, 350000, 400000, 450000, 1500000])
    s.append(["Total people costs", 300000, 350000, 400000, 450000, 1500000])
    s.append(["Legal", 20000, 20000, 20000, 20000, 80000])
    s.append(["Total operating costs", 20000, 20000, 20000, 20000, 80000])
    s.append(["EBITDA", -332000, -194000, 144000, 382000, 0])
    s.append(["Cash and balance sheet (year end)"])
    s.append(["Equity raised", 1000000])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


async def test_funding_costs_import_edit_and_kpis(
    db: AsyncSession, key_client: Any, frozen_now: Any
) -> None:
    w = await world(db)
    c = key_client(w.key)
    r = await c.post("/v1/funding-costs/import", content=_costs_xlsx(), params={"currency": "GBP"})
    assert r.status_code == 200, r.text
    out = r.json()
    s = out["summary"]
    assert s["funding_total"] == 1_000_000 and s["tranches"] == {"seis": 250_000, "eis": 750_000}
    assert s["use_of_funds_total"] == 1_000_000 and s["unallocated"] == 0
    assert [u["pct"] for u in s["use_of_funds"]] == [60.0, 40.0]
    assert s["costs"] == {"y1": 332_000, "y2": 394_000, "y3": 456_000, "y4": 518_000}
    assert s["income"]["y4"] == 900_000
    assert set(s["cost_groups"]) == {"Direct costs", "People", "Operating"}
    assert s["kpis"]["monthly_burn_y1"] == round(332_000 / 12)
    people = next(x for x in out["data"] if x["grp"] == "People")
    assert people["name"] == "Engineering"
    r = await c.patch(f"/v1/funding-costs/{people['id']}", json={"y1": "310,000"})
    assert r.json()["y1"] == 310_000
    r = await c.post(
        "/v1/funding-costs",
        json={
            "kind": "funding",
            "grp": "Grants",
            "name": "Fictional grant",
            "amount": 50000,
            "tranche": "grant",
        },
    )
    assert r.status_code == 201
    s = (await c.get("/v1/funding-costs")).json()["summary"]
    assert s["funding_total"] == 1_050_000 and s["unallocated"] == 50_000
    assert (await c.delete(f"/v1/funding-costs/{r.json()['id']}")).status_code == 204
    r = await c.post(
        "/v1/funding-costs", json={"kind": "cost", "grp": "X", "name": "Y", "tranche": "loan"}
    )
    assert r.status_code == 422
