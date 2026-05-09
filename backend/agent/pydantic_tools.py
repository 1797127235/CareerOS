"""Tool registration entry point.

All tool implementations live in agent/tools/ directory.
This module exists solely to keep agent/pydantic_agent.py's import unchanged:
    from backend.agent.pydantic_tools import register_tools
"""

from __future__ import annotations

from pydantic_ai import Agent

from backend.agent.deps import LumenDeps


def register_tools(agent: Agent[LumenDeps, str]) -> None:
    """Register all agent tools."""
    from backend.agent.tools import register_all_tools

    register_all_tools(agent)
