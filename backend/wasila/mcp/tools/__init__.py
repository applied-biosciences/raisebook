"""The MCP tool registry: every tool module from SPEC §6.4 is registered here already.

Each module defines ``register(server: FastMCP) -> None``. Feature builders fill
their modules; they never edit this list.
"""

from __future__ import annotations

import importlib

from mcp.server.fastmcp import FastMCP

TOOL_MODULES: list[str] = [
    "wasila.mcp.tools.workspace",  # AM: get_workspace
    "wasila.mcp.tools.rounds",  # AM: list_rounds, get_round_summary
    "wasila.mcp.tools.investors",  # AM: search_investors, get_investor, add/update_investor
    "wasila.mcp.tools.pipeline",  # AM: add_to_round, move_stage, log_activity, …
    "wasila.mcp.tools.data",  # IE: import_investors_csv, export_round
    "wasila.mcp.tools.meetings",  # schedule/list/update/complete_meeting
    "wasila.mcp.tools.room",  # Wasila: list_funding_room, search_master_list, draft_outreach
]

# Investor research (RESEARCH-PLAN §7): get_dossier, list_research_runs, research_investor,
# match_identity, save_dossier. Registered only with ``WASILA_RESEARCH_ENABLED``.
RESEARCH_TOOL_MODULES: list[str] = ["wasila.mcp.tools.research"]


def enabled_tool_modules() -> list[str]:
    from wasila.config import get_settings

    if get_settings().research_enabled:
        return TOOL_MODULES + RESEARCH_TOOL_MODULES
    return list(TOOL_MODULES)


def register_tools(server: FastMCP) -> None:
    for name in enabled_tool_modules():
        module = importlib.import_module(name)
        register = getattr(module, "register", None)
        if not callable(register):
            raise TypeError(f"{name} must define register(server: FastMCP) -> None")
        register(server)
