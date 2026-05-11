"""内置工具包。

此包中的模块会被 ToolRegistry 自动扫描，所有继承 Tool 基类的类会被实例化并注册。
无需手动在 __init__.py 中导出。
"""

from backend.agent.tools.internal.memory_save import MemorySaveTool
from backend.agent.tools.internal.memory_search import MemorySearchTool
from backend.agent.tools.internal.profile import GetProfileTool, UpdateProfileTool

__all__ = [
    "MemorySearchTool",
    "MemorySaveTool",
    "GetProfileTool",
    "UpdateProfileTool",
]
