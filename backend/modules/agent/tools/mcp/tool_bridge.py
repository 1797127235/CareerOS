"""MCP Tool → Lumen ToolDefinition 桥接。"""

from __future__ import annotations

from typing import Any

from backend.core.logging import get_logger
from backend.modules.agent.tools.core import ToolDefinition, ToolRegistry, ToolsetConfig, ToolsetResolver
from backend.modules.agent.tools.mcp.client_manager import get_mcp_manager

logger = get_logger(__name__)


def discover_and_register(registry: ToolRegistry, resolver: ToolsetResolver) -> list[str]:
    """从所有已连接 MCP Server 发现工具并注册到 Registry。

    Args:
        registry: Lumen 工具注册表
        resolver: Toolset 解析器

    Returns:
        注册成功的工具名列表
    """
    manager = get_mcp_manager()
    discovered = manager.discover_tools()
    registered: list[str] = []

    for server_name, tools in discovered:
        for tool in tools:
            tool_name = tool["name"]
            # 命名空间: server_name_tool_name，避免冲突
            lumen_name = f"{server_name}_{tool_name}"
            # 如果已存在（可能是旧连接残留），先注销
            if registry.has(lumen_name):
                registry.unregister(lumen_name)

            description = tool.get("description", f"MCP tool '{tool_name}' from server '{server_name}'")
            input_schema = tool.get("inputSchema", {"type": "object", "properties": {}})
            config = manager.get_server_config(server_name)
            read_only = config.read_only if config else False
            auto_approve = config.auto_approve if config else True

            registry.register(
                ToolDefinition(
                    name=lumen_name,
                    description=f"[{server_name}] {description}",
                    input_schema=input_schema,
                    category="mcp",
                    read_only=read_only,
                    requires_approval=not auto_approve,
                    handler=_make_handler(server_name, tool_name),
                )
            )
            registered.append(lumen_name)

    if registered:
        logger.info("MCP tools registered", count=len(registered))
        # 注册 mcp toolset
        resolver.register("mcp", ToolsetConfig(description="MCP 外部工具", tools=registered))
    else:
        # 确保 mcp toolset 存在（即使为空）
        resolver.register("mcp", ToolsetConfig(description="MCP 外部工具", tools=[]))

    return registered


def _make_handler(server_name: str, tool_name: str):
    """创建指向特定 MCP server/tool 的 handler 闭包。"""

    async def _handler(args: dict[str, Any], ctx: Any) -> str:
        manager = get_mcp_manager()
        return await manager.call_tool(server_name, tool_name, args)

    return _handler
