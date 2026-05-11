"""Agent 工具模块 — 统一工具系统入口。

使用方式：
  from backend.agent.tools import register_all_tools
  register_all_tools(agent)

内部通过 ToolRegistry 自动发现并注册所有工具（内置 + MCP 桥接）。
"""

from backend.agent.tools.internal.memory_save import MemorySaveTool

# 向后兼容：保留旧的显式导入路径
from backend.agent.tools.internal.memory_search import MemorySearchTool
from backend.agent.tools.internal.profile import GetProfileTool, UpdateProfileTool
from backend.agent.tools.registry import register_all_tools

__all__ = [
    "register_all_tools",
    "MemorySearchTool",
    "MemorySaveTool",
    "GetProfileTool",
    "UpdateProfileTool",
]
