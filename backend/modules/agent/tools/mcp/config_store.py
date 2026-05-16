"""MCP 配置持久化 — 复用 ~/.lumen/config.json 的 mcp_servers 字段。"""

from __future__ import annotations

from typing import Any

from backend.core.config import load_user_config, save_user_config
from backend.modules.agent.tools.mcp.models import McpServerConfig

_CONFIG_KEY = "mcp_servers"


def load_mcp_servers() -> list[McpServerConfig]:
    """从用户配置读取 MCP Server 列表。"""
    cfg = load_user_config()
    raw = cfg.get(_CONFIG_KEY, [])
    if not isinstance(raw, list):
        return []
    servers: list[McpServerConfig] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                servers.append(McpServerConfig.model_validate(item))
            except Exception:
                continue
    return servers


def save_mcp_servers(servers: list[McpServerConfig]) -> None:
    """保存 MCP Server 列表到用户配置。"""
    data = {k: v for k, v in load_user_config().items() if k != _CONFIG_KEY}
    data[_CONFIG_KEY] = [s.model_dump(mode="json") for s in servers]
    save_user_config(data)


def get_mcp_server(name: str) -> McpServerConfig | None:
    """按名称查找单个 server 配置。"""
    for s in load_mcp_servers():
        if s.name == name:
            return s
    return None


def add_mcp_server(config: McpServerConfig) -> None:
    """新增 server（若同名则覆盖）。"""
    servers = [s for s in load_mcp_servers() if s.name != config.name]
    servers.append(config)
    save_mcp_servers(servers)


def remove_mcp_server(name: str) -> bool:
    """删除 server，返回是否成功删除。"""
    servers = load_mcp_servers()
    new_servers = [s for s in servers if s.name != name]
    if len(new_servers) == len(servers):
        return False
    save_mcp_servers(new_servers)
    return True


def update_mcp_server(name: str, updates: dict[str, Any]) -> McpServerConfig | None:
    """部分更新 server 配置。"""
    servers = load_mcp_servers()
    for i, s in enumerate(servers):
        if s.name == name:
            data = s.model_dump()
            for k, v in updates.items():
                if v is not None and k in data:
                    data[k] = v
            updated = McpServerConfig.model_validate(data)
            servers[i] = updated
            save_mcp_servers(servers)
            return updated
    return None
