"""MCP 与 Agent 工具运行时集成测试。"""

from __future__ import annotations

import pytest

from backend.modules.agent.tools.core import ToolRegistry, ToolsetResolver
from backend.modules.agent.tools.core.factory import create_tool_runtime
from backend.modules.agent.tools.mcp.config_store import save_mcp_servers
from backend.modules.agent.tools.mcp.tool_bridge import discover_and_register


@pytest.fixture(autouse=True)
def _clean_mcp_config(monkeypatch):
    """每个测试前清空 MCP 配置并断开连接。"""
    save_mcp_servers([])
    from backend.modules.agent.tools.mcp.client_manager import _mcp_manager

    if _mcp_manager is not None:
        pass  # 同步 fixture 中无法安全断开异步连接，依赖测试隔离
    yield
    save_mcp_servers([])


def test_factory_registers_mcp_toolset():
    """create_tool_runtime 应注册 mcp toolset（即使为空）。"""
    _registry, _dispatcher, resolver = create_tool_runtime()

    toolsets = resolver.list_toolsets()
    assert "mcp" in toolsets


def test_discover_and_register_empty():
    """没有 MCP server 时，discover_and_register 返回空列表。"""
    registry = ToolRegistry()
    resolver = ToolsetResolver()
    registered = discover_and_register(registry, resolver)
    assert registered == []
