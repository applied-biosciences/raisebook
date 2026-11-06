# mypy: disable-error-code="type-arg"
"""MCP tools (Wasila v1.0.0.0): list_funding_room, search_master_list, draft_outreach.

They call the same services as ``/v1/funding-room``, ``/v1/master-list/search`` and
``/v1/outreach/messages``. ``draft_outreach`` only saves a **draft**: an agent can write the
email, but a person sends it from Wasila (there is no send tool, by design).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from wasila.auth.scopes import SCOPE_WRITE
from wasila.core.refs import resolve_investor
from wasila.mcp.annotations import read_only, write
from wasila.mcp.tools._args import InvestorArg
from wasila.mcp.tools._common import Clock, parse_uuid, tool_call
from wasila.services import funding_room as room_svc
from wasila.services import master_list as ml_svc
from wasila.services import outreach as outreach_svc

StrList = Annotated[list[str] | None, Field(max_length=20)]


def register(server: FastMCP) -> None:
    @server.tool(annotations=read_only("Funding Room documents"))
    async def list_funding_room(
        category: Annotated[
            str | None,
            Field(
                description="pitch, corporate, financial, technical, clinical, regulatory, ip, "
                "cybersecurity, data_protection, commercial, legal, tax_relief or other."
            ),
        ] = None,
        jurisdiction: Literal["us", "uk", "ksa"] | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """The Funding Room (diligence documents): title, category, review status, confidentiality, jurisdiction and latest version for each document, plus the US/UK/KSA checklist when `jurisdiction` is given. Files themselves are not returned."""  # noqa: E501
        async with tool_call(ctx) as (db, ws):
            docs = await room_svc.list_documents(
                db, ws, category=category, jurisdiction=jurisdiction
            )
            out: dict[str, Any] = {
                "documents": [
                    {
                        "id": str(d.id),
                        "title": d.title,
                        "category": d.category,
                        "review_status": d.review_status,
                        "confidentiality": d.confidentiality,
                        "jurisdiction": d.jurisdiction,
                        "version": d.current_version,
                    }
                    for d in docs
                ]
            }
            if jurisdiction:
                out["checklist"] = [
                    {"label": i["label"], "status": i["status"]}
                    for i in await room_svc.checklist(db, ws, jurisdiction)
                ]
            return out

    @server.tool(annotations=read_only("Search the master list"))
    async def search_master_list(
        query: Annotated[str | None, Field(max_length=200)] = None,
        countries: StrList = None,
        types: StrList = None,
        tags_any: StrList = None,
        has_email: bool | None = None,
        not_contacted: bool | None = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Filter every investor in the workspace: `countries` (United Kingdom, United States, Saudi Arabia, GCC, …; UK/US/KSA work), `types` (vc, angel, family_office …), `tags_any` (sector or interest words), `has_email`, `not_contacted` (no email, call or meeting logged and nothing sent). Returns name, firm, title, country, tags and whether there is an email."""  # noqa: E501
        async with tool_call(ctx) as (db, ws):
            f = ml_svc.Filters.from_dict(
                {
                    "q": query,
                    "countries": countries or [],
                    "types": types or [],
                    "tags_any": tags_any or [],
                    "has_email": has_email,
                    "not_contacted": not_contacted,
                }
            )
            rows, total = await ml_svc.search(db, ws, f, limit=limit)
            return {
                "total": total,
                "investors": [
                    {
                        "id": str(i.id),
                        "name": i.name,
                        "firm": i.firm,
                        "title": i.title,
                        "country": i.country,
                        "tags": i.tags,
                        "has_email": bool(i.email),
                    }
                    for i in rows
                ],
            }

    @server.tool(annotations=write("Draft an investor email", idempotent=False))
    async def draft_outreach(
        investor: InvestorArg,
        subject: Annotated[str, Field(min_length=1, max_length=300)],
        body: Annotated[str, Field(min_length=1, max_length=50000)],
        attachment_ids: Annotated[
            list[str] | None,
            Field(
                description="Approved Funding Room document ids (list_funding_room).", max_length=10
            ),
        ] = None,
        kind: Literal["outreach", "update", "follow_up"] = "outreach",
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Save an email to one investor as a DRAFT in Wasila (it is not sent). A person reviews and sends it from the Outreach page. Attach approved Funding Room documents by id."""  # noqa: E501
        async with tool_call(ctx, SCOPE_WRITE) as (db, ws):
            inv = await resolve_investor(db, ws, investor)
            msg = await outreach_svc.create_draft(
                db,
                ws,
                investor_id=inv.id,
                subject=subject,
                body=body,
                attachment_ids=[parse_uuid(a, "attachment_ids") for a in attachment_ids or []],
                kind=kind,
                now=Clock.now(),
            )
            return {
                "draft_id": str(msg.id),
                "to": msg.to_email,
                "status": msg.status,
                "attachments": [a["filename"] for a in msg.attachments],
                "next": "A person sends it from Wasila → Outreach.",
            }
