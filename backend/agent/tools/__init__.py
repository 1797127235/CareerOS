"""Agent 工具模块 — 统一工具系统入口。

使用方式：
  from backend.agent.tools import discover_toolsets
  toolsets = discover_toolsets()
  agent = Agent(..., toolsets=toolsets)

内部通过 AST 扫描发现 toolsets/*.py 中的 FunctionToolset（零副作用）。
"""

from backend.agent.tools.internal.memory_save import MemorySaveTool
from backend.agent.tools.internal.memory_search import MemorySearchTool
from backend.agent.tools.internal.profile import GetProfileTool, UpdateProfileTool
from backend.agent.tools.registry import discover_toolsets

__all__ = [
    "discover_toolsets",
    "MemorySearchTool",
    "MemorySaveTool",
    "GetProfileTool",
    "UpdateProfileTool",
]
