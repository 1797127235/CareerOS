"""MCP 管理 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.modules.agent.tools.mcp.client_manager import get_mcp_manager
from backend.modules.agent.tools.mcp.config_store import (
    add_mcp_server,
    get_mcp_server,
    remove_mcp_server,
    update_mcp_server,
)
from backend.modules.agent.tools.mcp.models import (
    McpServerCreate,
    McpServerStatus,
    McpServerUpdate,
    McpToolInfo,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/servers")
async def list_servers() -> list[McpServerStatus]:
    """列出所有 MCP Server 配置与运行状态。"""
    return get_mcp_manager().get_status()


@router.post("/servers")
async def create_server(body: McpServerCreate) -> McpServerStatus:
    """新增 MCP Server。"""
    if get_mcp_server(body.name):
        raise HTTPException(status_code=409, detail=f"Server '{body.name}' 已存在")

    from backend.modules.agent.tools.mcp.models import McpServerConfig

    config = McpServerConfig(
        name=body.name,
        transport=body.transport,
        command=body.command,
        args=body.args,
        url=body.url,
        env=body.env,
        enabled=body.enabled,
        auto_approve=body.auto_approve,
        read_only=body.read_only,
    )
    add_mcp_server(config)

    # 如果启用，尝试立即连接
    manager = get_mcp_manager()
    if config.enabled:
        await manager.refresh()

    statuses = [s for s in manager.get_status() if s.name == body.name]
    return statuses[0] if statuses else McpServerStatus(name=body.name)


@router.get("/servers/{name}")
async def get_server(name: str) -> McpServerStatus:
    """获取单个 Server 状态。"""
    for s in get_mcp_manager().get_status():
        if s.name == name:
            return s
    raise HTTPException(status_code=404, detail=f"Server '{name}' 不存在")


@router.put("/servers/{name}")
async def update_server(name: str, body: McpServerUpdate) -> McpServerStatus:
    """更新 MCP Server。"""
    updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="没有提供更新字段")

    updated = update_mcp_server(name, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Server '{name}' 不存在")

    # 重建连接
    manager = get_mcp_manager()
    await manager.refresh()

    for s in manager.get_status():
        if s.name == name:
            return s
    return McpServerStatus(name=name)


@router.delete("/servers/{name}")
async def delete_server(name: str) -> dict[str, str]:
    """删除 MCP Server。"""
    if not remove_mcp_server(name):
        raise HTTPException(status_code=404, detail=f"Server '{name}' 不存在")

    # 重建连接
    await get_mcp_manager().refresh()
    return {"status": "deleted", "name": name}


@router.post("/servers/{name}/test")
async def test_server(name: str) -> McpServerStatus:
    """测试单个 Server 连接。"""
    config = get_mcp_server(name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Server '{name}' 不存在")

    manager = get_mcp_manager()
    await manager.refresh()

    for s in manager.get_status():
        if s.name == name:
            return s
    return McpServerStatus(name=name)


@router.post("/servers/{name}/refresh")
async def refresh_server(name: str) -> McpServerStatus:
    """手动刷新单个 Server 的工具列表。"""
    return await test_server(name)


@router.get("/tools")
async def list_tools() -> list[McpToolInfo]:
    """列出所有已发现的 MCP 工具。"""
    tools: list[McpToolInfo] = []
    for server_name, server_tools in get_mcp_manager().discover_tools():
        for t in server_tools:
            tools.append(
                McpToolInfo(
                    name=t["name"],
                    description=t.get("description", ""),
                    server=server_name,
                    input_schema=t.get("inputSchema", {}),
                )
            )
    return tools
