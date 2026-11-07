"""Claude in Wasila (v1.0.0.0): agentic help on the workspace's own Anthropic API key.

Claude runs only when a person clicks (or an API/MCP caller asks), never on import or on a
schedule, and nothing it writes is sent or saved without a person's review:

- ``ask``: turns a question about the master list into ``master_list.Filters`` (the question
  is all Claude sees; it never sees investor rows for this).
- ``draft_email``: a warm letter or investor update to one investor, saved as a **draft**.
- ``fill_ai_column``: one short answer per investor for an AI column.
- ``deck_suggestions``: text edits for a deck, applied only in the deck editor.

What Claude sees about an investor is public profile data only (name, firm, title, country,
type, tags, industries, website, the warm-intro connector's name). Never email addresses,
phone numbers, amounts or notes. Tests install a mock transport (:func:`set_transport`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wasila import __version__
from wasila.auth.principal import WorkspaceContext
from wasila.config import get_settings
from wasila.core.errors import APIError, Unprocessable, ValidationFailed
from wasila.models.ai import CompanyProfile
from wasila.models.investor import Investor
from wasila.models.room import ClaudeSettings
from wasila.services import master_list
from wasila.services import workspace_secrets as secrets_svc

log = structlog.get_logger(__name__)

ANTHROPIC_VERSION: Final[str] = "2023-06-01"
MODELS: Final[tuple[str, ...]] = (
    "claude-sonnet-5-5",
    "claude-opus-5-5",
    "claude-haiku-5-5",
    "claude-fable-5-1",
)

_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Tests: route every Anthropic call to a mock transport."""
    global _transport
    _transport = transport


class NoClaudeKey(Unprocessable):
    code = "no_claude_key"
    default_message = (
        "Add your Anthropic API key in Settings → Claude first (only an owner can add it)."
    )


class ClaudeUnavailable(APIError):
    status_code = 502
    code = "claude_unavailable"
    default_message = "Claude did not answer. Try again in a moment."


class ClaudeWorkspaceRequired(Unprocessable):
    code = "claude_workspace_required"
    default_message = (
        "This Anthropic key is not tied to one Anthropic workspace. Add the workspace ID "
        "(it starts wrkspc_; console.anthropic.com → Settings → Workspaces) with the key, or "
        "create a key inside a workspace and save that instead."
    )


WORKSPACE_ID_RE: Final = re.compile(r"^wrkspc_[A-Za-z0-9]{8,64}$")


class InvalidClaudeKey(Unprocessable):
    code = "invalid_claude_key"
    default_message = "Anthropic rejected the API key. Check it and save it again."


async def get_settings_row(db: AsyncSession, ws: WorkspaceContext) -> ClaudeSettings | None:
    row: ClaudeSettings | None = await db.scalar(
        select(ClaudeSettings).where(ClaudeSettings.workspace_id == ws.workspace_id)
    )
    return row


async def model_for(db: AsyncSession, ws: WorkspaceContext) -> str:
    row = await get_settings_row(db, ws)
    return row.model if row is not None else get_settings().anthropic_default_model


async def anthropic_workspace_for(db: AsyncSession, ws: WorkspaceContext) -> str | None:
    row = await get_settings_row(db, ws)
    return row.anthropic_workspace_id if row is not None else None


async def call(
    db: AsyncSession,
    ws: WorkspaceContext,
    *,
    system: str,
    user: str,
    max_tokens: int = 1200,
    key: str | None = None,
    anthropic_workspace_id: str | None = None,
) -> str:
    """One Messages API call. Returns the text of the reply.

    ``key`` / ``anthropic_workspace_id`` override the saved ones (used to verify a key
    before it is saved).
    """
    api_key = key or await secrets_svc.reveal(db, ws, "anthropic")
    if not api_key:
        raise NoClaudeKey()
    wrkspc = anthropic_workspace_id if key else await anthropic_workspace_for(db, ws)
    s = get_settings()
    body = {
        "model": await model_for(db, ws),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
        "user-agent": f"wasila/{__version__}",
    }
    if wrkspc:
        headers["anthropic-workspace-id"] = wrkspc
    try:
        async with httpx.AsyncClient(
            base_url=s.anthropic_base_url,
            transport=_transport,
            timeout=s.anthropic_timeout_s,
            follow_redirects=False,
        ) as client:
            r = await client.post("/v1/messages", json=body, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("claude.http_error", error=type(exc).__name__)
        raise ClaudeUnavailable() from exc
    if r.status_code in (401, 403):
        raise InvalidClaudeKey()
    if r.status_code == 400 and "anthropic-workspace-id" in r.text:
        raise ClaudeWorkspaceRequired()
    if r.status_code >= 400:
        log.warning("claude.error_status", status=r.status_code)
        raise ClaudeUnavailable(f"Claude returned an error ({r.status_code}). Try again.")
    try:
        data = r.json()
        return "".join(
            part.get("text", "") for part in data.get("content", []) if part.get("type") == "text"
        ).strip()
    except (ValueError, AttributeError) as exc:
        raise ClaudeUnavailable() from exc


async def verify_key(
    db: AsyncSession, ws: WorkspaceContext, key: str, anthropic_workspace_id: str | None = None
) -> None:
    """A tiny call that proves the key works before it is saved."""
    await call(
        db,
        ws,
        system="Reply with OK.",
        user="OK?",
        max_tokens=5,
        key=key,
        anthropic_workspace_id=anthropic_workspace_id,
    )


async def save_key(
    db: AsyncSession,
    ws: WorkspaceContext,
    key: str,
    *,
    anthropic_workspace_id: str | None,
    now: datetime,
) -> None:
    """Verify, then seal the key and record its Anthropic workspace (the only key writer)."""
    key = key.strip()
    wrkspc = (anthropic_workspace_id or "").strip() or None
    if wrkspc and not WORKSPACE_ID_RE.match(wrkspc):
        raise ValidationFailed(
            "anthropic_workspace_id",
            "An Anthropic workspace ID starts wrkspc_ (letters and digits).",
        )
    await verify_key(db, ws, key, wrkspc)
    await secrets_svc.put(db, ws, "anthropic", key, now=now)
    row = await get_settings_row(db, ws)
    if row is None:
        row = ClaudeSettings(
            workspace_id=ws.workspace_id,
            model=get_settings().anthropic_default_model,
            anthropic_workspace_id=wrkspc,
            updated_at=now,
        )
        db.add(row)
    else:
        row.anthropic_workspace_id = wrkspc
        row.updated_at = now
    await db.flush()


def parse_json(text: str) -> Any:
    """The first JSON object or array in Claude's reply (tolerates code fences)."""
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    raw = m.group(1) if m else text
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ClaudeUnavailable("Claude's answer was not in the expected format. Try again.")
    for end in range(len(raw), start, -1):
        try:
            return json.loads(raw[start:end])
        except ValueError:
            continue
    raise ClaudeUnavailable("Claude's answer was not in the expected format. Try again.")


def public_profile(inv: Investor, connector: str | None = None) -> dict[str, Any]:
    """The only investor data Claude ever sees."""
    out: dict[str, Any] = {
        "name": inv.name,
        "firm": inv.firm,
        "title": inv.title,
        "type": inv.type,
        "country": inv.country,
        "location": inv.location,
        "tags": inv.tags[:15],
        "industries": inv.industries[:15],
        "website": inv.website_url,
    }
    if connector:
        out["warm_intro_via"] = connector
    return {k: v for k, v in out.items() if v not in (None, [], "")}


async def company_context(db: AsyncSession, ws: WorkspaceContext) -> dict[str, Any]:
    prof = await db.scalar(
        select(CompanyProfile).where(CompanyProfile.workspace_id == ws.workspace_id)
    )
    out: dict[str, Any] = {"company": ws.name}
    if prof is not None:
        for k in ("pitch", "stage", "location", "website_url", "strategic_help"):
            if getattr(prof, k):
                out[k] = getattr(prof, k)
        if prof.sectors:
            out["sectors"] = prof.sectors
        if prof.traction:
            out["traction"] = prof.traction[:8]
    return out


# --- Ask Wasila ---------------------------------------------------------------------------------

ASK_SYSTEM: Final[
    str
] = """You turn a founder's question about their investor list into search filters.
Answer with one JSON object only, no prose, with these optional keys:
{"q": "free-text words that must appear (name, firm, notes)",
 "countries": ["United Kingdom" | "United States" | "Saudi Arabia" | "GCC" | other country names],
 "types": ["vc","angel","family_office","corporate_vc","accelerator","scout","other"],
 "tags_any": ["interest or sector words, e.g. Healthcare, AI, Mental health"],
 "has_email": true|false,
 "not_contacted": true|false,
 "custom": {"field_key": "value"},
 "explanation": "one short sentence saying what you searched for"}
Only use keys you are confident about. Custom field keys available: CUSTOM_KEYS."""


@dataclass
class AskResult:
    filters: master_list.Filters
    explanation: str


async def ask(db: AsyncSession, ws: WorkspaceContext, question: str) -> AskResult:
    question = question.strip()[:1000]
    keys = [f.key for f in await master_list.list_fields(db, ws)]
    system = ASK_SYSTEM.replace("CUSTOM_KEYS", ", ".join(keys) or "(none)")
    data = parse_json(await call(db, ws, system=system, user=question, max_tokens=400))
    if not isinstance(data, dict):
        raise ClaudeUnavailable("Claude's answer was not in the expected format. Try again.")
    explanation = str(data.pop("explanation", "") or "")[:300]
    return AskResult(master_list.Filters.from_dict(data), explanation)


# --- drafting -----------------------------------------------------------------------------------

DRAFT_SYSTEM: Final[str] = """You write short, warm, specific investor emails for a founder.
Write in the founder's voice, plain British English unless the investor is in the US.
No hype, no buzzwords, no invented facts: use only the company facts given. Under 220 words.
Mention the warm-intro connector by name if one is given. End with one clear, small ask.
If attachments are listed, mention them in one line ("I've attached ...").
Answer with JSON only: {"subject": "...", "body": "..."} (body is plain text with blank lines)."""


async def draft_email(
    db: AsyncSession,
    ws: WorkspaceContext,
    inv: Investor,
    *,
    kind: str,
    instructions: str | None,
    attachments: list[str],
    connector: str | None,
) -> tuple[str, str]:
    payload = {
        "email_kind": "investor update" if kind == "update" else "first outreach (warm letter)",
        "company": await company_context(db, ws),
        "investor": public_profile(inv, connector),
        "attachments": attachments,
        "founder_instructions": (instructions or "").strip()[:2000] or None,
    }
    data = parse_json(
        await call(db, ws, system=DRAFT_SYSTEM, user=json.dumps(payload), max_tokens=900)
    )
    subject = str(data.get("subject") or "").strip()[:300] if isinstance(data, dict) else ""
    body = str(data.get("body") or "").strip()[:50000] if isinstance(data, dict) else ""
    if not subject or not body:
        raise ClaudeUnavailable("Claude's draft was empty. Try again.")
    return subject, body


AI_COLUMN_SYSTEM: Final[str] = """You fill one column of an investor spreadsheet for a founder.
Answer the founder's column question about this one investor in at most 12 words.
Use only the profile and company facts given; if they are not enough, answer "Unknown".
Answer with the value only."""


async def ai_value(
    db: AsyncSession, ws: WorkspaceContext, prompt: str, inv: Investor, company: dict[str, Any]
) -> str:
    user = json.dumps(
        {"column_question": prompt, "company": company, "investor": public_profile(inv)}
    )
    text = await call(db, ws, system=AI_COLUMN_SYSTEM, user=user, max_tokens=60)
    return text.strip().strip('"')[:200] or "Unknown"


DECK_SYSTEM: Final[
    str
] = """You help a founder tailor their pitch deck. You get the deck's slides as text
(slide number, shape id, text) and an instruction. Suggest at most 12 concise text edits that
follow the instruction, keep every fact true to the original, and keep each text about the
same length. Answer with JSON only:
{"suggestions": [{"slide": 1, "shape": 3, "text": "new text", "why": "short reason"}]}"""


async def deck_suggestions(
    db: AsyncSession,
    ws: WorkspaceContext,
    slides: list[dict[str, Any]],
    *,
    instruction: str,
    investor: Investor | None,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"instruction": instruction.strip()[:2000], "slides": slides}
    if investor is not None:
        payload["tailor_for_investor"] = public_profile(investor)
    data = parse_json(
        await call(db, ws, system=DECK_SYSTEM, user=json.dumps(payload)[:60000], max_tokens=2500)
    )
    items = data.get("suggestions", []) if isinstance(data, dict) else []
    out = []
    for it in items[:12]:
        try:
            out.append(
                {
                    "slide": int(it["slide"]),
                    "shape": int(it["shape"]),
                    "text": str(it["text"])[:4000],
                    "why": str(it.get("why") or "")[:300],
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
