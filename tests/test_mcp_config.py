"""MCP 配置持久化测试。"""

from __future__ import annotations

import pytest

from backend.modules.agent.tools.mcp.config_store import (
    add_mcp_server,
    get_mcp_server,
    load_mcp_servers,
    remove_mcp_server,
    save_mcp_servers,
    update_mcp_server,
)
from backend.modules.agent.tools.mcp.models import McpServerConfig


@pytest.fixture(autouse=True)
def _clean_mcp_config(monkeypatch):
    """每个测试前清空 MCP 配置。"""
    save_mcp_servers([])
    yield
    save_mcp_servers([])


def test_load_empty():
    servers = load_mcp_servers()
    assert servers == []


def test_add_and_load():
    cfg = McpServerConfig(
        name="fs",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    )
    add_mcp_server(cfg)

    servers = load_mcp_servers()
    assert len(servers) == 1
    assert servers[0].name == "fs"
    assert servers[0].transport == "stdio"


def test_get_server():
    add_mcp_server(McpServerConfig(name="github", transport="sse", url="http://localhost:3000"))

    s = get_mcp_server("github")
    assert s is not None
    assert s.name == "github"
    assert s.url == "http://localhost:3000"

    assert get_mcp_server("missing") is None


def test_remove_server():
    add_mcp_server(McpServerConfig(name="a"))
    add_mcp_server(McpServerConfig(name="b"))

    assert remove_mcp_server("a") is True
    assert len(load_mcp_servers()) == 1
    assert load_mcp_servers()[0].name == "b"

    assert remove_mcp_server("missing") is False


def test_update_server():
    add_mcp_server(McpServerConfig(name="x", command="old"))

    updated = update_mcp_server("x", {"command": "new"})
    assert updated is not None
    assert updated.command == "new"

    s = get_mcp_server("x")
    assert s is not None
    assert s.command == "new"


def test_update_missing():
    assert update_mcp_server("missing", {"command": "new"}) is None
