"""Agent 工具注册入口。各工具分别在独立模块中定义，通过此文件统一注册到 Agent。"""

from __future__ import annotations

from pydantic_ai import Agent

from backend.agent.deps import LumenDeps


def register_all_tools(agent: Agent[LumenDeps, str]) -> None:
    from backend.agent import tool_memory_save, tool_memory_search, tool_profile

    tool_memory_search.register(agent)
    tool_memory_save.register(agent)
    tool_profile.register(agent)
