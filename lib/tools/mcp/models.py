"""MCP 配置与状态模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class McpServerConfig(BaseModel):
    """单个 MCP Server 配置。"""

    name: str = Field(..., description="Server 唯一标识名")
    transport: str = Field(default="stdio", description="传输协议: stdio | sse")
    command: str = Field(default="", description="stdio: 可执行命令")
    args: list[str] = Field(default_factory=list, description="stdio: 命令参数")
    url: str = Field(default="", description="sse: Server URL")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    enabled: bool = Field(default=True, description="是否启用")
    auto_approve: bool = Field(default=True, description="是否跳过审批策略")
    read_only: bool = Field(default=False, description="是否标记为只读工具")


class McpServerStatus(BaseModel):
    """Server 运行时状态。"""

    name: str
    state: str = "disconnected"  # connected | disconnected | error
    error_msg: str = ""
    tools_count: int = 0


class McpServerCreate(BaseModel):
    """创建/更新请求体。"""

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    url: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    auto_approve: bool = True
    read_only: bool = False


class McpServerUpdate(BaseModel):
    """部分更新请求体。"""

    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None
    auto_approve: bool | None = None
    read_only: bool | None = None


class McpToolInfo(BaseModel):
    """暴露给前端的 MCP Tool 摘要。"""

    name: str
    description: str = ""
    server: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
