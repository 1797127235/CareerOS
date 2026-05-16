"""MCP Client 模块 — 连接外部 MCP Server，将其工具注入 Lumen Agent。"""

from __future__ import annotations

from backend.modules.agent.tools.mcp.client_manager import get_mcp_manager
from backend.modules.agent.tools.mcp.tool_bridge import discover_and_register

__all__ = ["discover_and_register", "get_mcp_manager"]
