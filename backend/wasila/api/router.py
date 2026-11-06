"""API router registry: every module from SPEC §2.1 is registered here already.

Each listed module exposes ``router: APIRouter`` with its own prefix. Feature
builders replace the stub modules' contents.

Order matters where paths overlap: ``exports`` (``/v1/investors/export``,
``/v1/rounds/{round}/export``) and ``imports`` come before ``investors`` and
``rounds`` so their literal paths win over ``/v1/investors/{investor_id}``.
"""

from __future__ import annotations

import importlib

from fastapi import APIRouter, FastAPI

API_MODULES: list[str] = [
    "wasila.api.health",
    "wasila.api.auth",
    "wasila.api.me",
    "wasila.api.workspaces",
    "wasila.api.members",
    "wasila.api.invites",
    "wasila.api.api_keys",
    # Import-Export+Ops (IE)
    "wasila.api.imports",
    "wasila.api.exports",
    # API+MCP (AM)
    "wasila.api.rounds",
    "wasila.api.participants",
    "wasila.api.investors",
    "wasila.api.activities",
    "wasila.api.follow_ups",
    # Meetings and the calendar feed
    "wasila.api.meetings",
    "wasila.api.calendar",
    # Wasila v1.0.0.0
    "wasila.api.funding_room",
    "wasila.api.master_list",
    "wasila.api.claude",
    "wasila.api.outreach",
    "wasila.api.decks",
    "wasila.api.funding_costs",
]

# Investor research (docs/RESEARCH-PLAN.md), served only with ``WASILA_RESEARCH_ENABLED``:
# settings and company profile (Part 1); runs, identities, dossiers, suggestions and the
# Research Policy (Part 2).
RESEARCH_API_MODULES: list[str] = [
    "wasila.api.ai_settings",
    "wasila.api.company_profile",
    "wasila.api.research",
    "wasila.api.research_policy",
]


def enabled_api_modules() -> list[str]:
    from wasila.config import get_settings

    if get_settings().research_enabled:
        # Before imports/investors, as before: literal paths win over ``{investor_id}``.
        return API_MODULES[:7] + RESEARCH_API_MODULES + API_MODULES[7:]
    return list(API_MODULES)


def include_api_routers(app: FastAPI, modules: list[str] | None = None) -> None:
    for name in modules if modules is not None else enabled_api_modules():
        module = importlib.import_module(name)
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{name} must define router: APIRouter")
        app.include_router(router)
