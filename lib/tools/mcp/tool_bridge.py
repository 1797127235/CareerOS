"""MCP tool bridge — 从已连接的 MCP Server 发现工具，返回 list[ToolDef]。"""

from __future__ import annotations

from typing import Any

from lib.tools._base import ToolDef
from lib.tools.mcp.client_manager import get_mcp_manager
from shared.logging import get_logger

logger = get_logger(__name__)


def discover_mcp_tools() -> list[ToolDef]:
    """从所有已连接 MCP Server 发现工具。连不上时返回空列表并 warn。"""
    manager = get_mcp_manager()
    discovered = manager.discover_tools()
    tools: list[ToolDef] = []

    for server_name, server_tools in discovered:
        config = manager.get_server_config(server_name)
        read_only = config.read_only if config else False

        for tool in server_tools:
            tool_name = tool["name"]
            lumen_name = f"{server_name}_{tool_name}"
            description = tool.get("description", f"MCP tool '{tool_name}' from '{server_name}'")
            input_schema = tool.get("inputSchema", {"type": "object", "properties": {}})

            tools.append(
                ToolDef(
                    name=lumen_name,
                    description=f"[{server_name}] {description}",
                    input_schema=input_schema,
                    execute=_make_handler(server_name, tool_name),
                    read_only=read_only,
                    category="mcp",
                )
            )

    if tools:
        logger.info("MCP tools discovered", count=len(tools))
    return tools


def _make_handler(server_name: str, tool_name: str):
    async def handler(args: dict[str, Any], deps) -> str:
        manager = get_mcp_manager()
        return await manager.call_tool(server_name, tool_name, args)

    return handler
