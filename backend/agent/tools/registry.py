"""工具注册表 — 统一发现、注册、管理所有 Agent 工具。

设计原则：
- 内置工具：通过文件约定自动发现（tools/internal/*.py 中继承 Tool 的类）
- MCP 桥接工具：运行时条件加载（配置启用时才注册）
- 外部扩展：未来可通过 entry_points 或动态导入扩展

Agent 侧只需调用 registry.register_all(agent)，无需关心工具有哪些、从哪来。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai import Agent

from backend.agent.deps import LumenDeps
from backend.config import get_settings
from backend.logging_config import get_logger

if TYPE_CHECKING:
    from backend.agent.tools.base import Tool

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表 — 单例。

    生命周期：
    1. 启动时 scan() 自动发现内置工具
    2. 配置变更时 reload() 重新组装工具池
    3. register_all(agent) 将当前工具池注册到 PydanticAI Agent
    """

    _instance: ToolRegistry | None = None

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: dict[str, Tool] = {}
            cls._instance._scanned = False
        return cls._instance

    # -- 发现 --

    def scan(self, *, force: bool = False) -> list[Tool]:
        """扫描并加载所有可用工具。

        扫描路径（按优先级）：
        1. backend/agent/tools/internal/ — 内置工具（始终加载）
        2. backend/agent/tools/mcp/ — MCP 桥接工具（条件加载）
        3. 未来：entry_points 动态扩展

        Args:
            force: 是否强制重新扫描（默认首次扫描后缓存）

        Returns:
            list[Tool]: 加载的工具实例列表
        """
        if self._scanned and not force:
            return list(self._tools.values())

        self._tools.clear()
        discovered: list[Tool] = []

        # 1. 内置工具（始终加载）
        discovered.extend(self._scan_package("backend.agent.tools.internal"))

        # 2. MCP 桥接工具（条件加载）
        settings = get_settings()
        if getattr(settings, "mcp_filesystem_enabled", False):
            discovered.extend(self._scan_package("backend.agent.tools.mcp.filesystem"))
        if getattr(settings, "mcp_github_enabled", False):
            discovered.extend(self._scan_package("backend.agent.tools.mcp.github"))

        # 去重 + 索引
        for tool in discovered:
            if tool.name in self._tools:
                logger.warning(
                    "Tool name collision",
                    name=tool.name,
                    existing=type(self._tools[tool.name]).__name__,
                    new=type(tool).__name__,
                )
                continue
            self._tools[tool.name] = tool

        self._scanned = True
        logger.info(
            "Tool registry scanned",
            total=len(self._tools),
            names=list(self._tools.keys()),
        )
        return list(self._tools.values())

    def _scan_package(self, package_name: str) -> list[Tool]:
        """扫描 Python 包中所有 Tool 子类并实例化。"""
        tools: list[Tool] = []

        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.debug("Tool package not found", package=package_name)
            return tools

        # 获取包路径
        if not hasattr(package, "__path__"):
            return tools

        package_path = Path(next(iter(package.__path__)))
        if not package_path.exists():
            return tools

        # 遍历模块
        for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
            if is_pkg:
                continue  # 暂不递归子包

            full_module_name = f"{package_name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
            except Exception as exc:
                logger.warning(
                    "Failed to import tool module",
                    module=full_module_name,
                    error=str(exc),
                )
                continue

            # 查找 Tool 子类
            from backend.agent.tools.base import Tool

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Tool) and obj is not Tool and not getattr(obj, "__abstractmethods__", None):
                    try:
                        instance = obj()
                        tools.append(instance)
                        logger.debug("Tool discovered", name=instance.name, module=full_module_name)
                    except Exception as exc:
                        logger.error(
                            "Failed to instantiate tool",
                            tool=obj.__name__,
                            error=str(exc),
                        )

        return tools

    # -- 查询 --

    def get(self, name: str) -> Tool | None:
        """按名称获取工具实例。"""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """获取所有已注册工具。"""
        return list(self._tools.values())

    def names(self) -> list[str]:
        """获取所有工具名称。"""
        return list(self._tools.keys())

    # -- 注册到 Agent --

    def _register_tools(self, agent: Agent[LumenDeps, str], tools: list[Tool]) -> None:
        """将指定工具列表注册到 PydanticAI Agent（内部方法）。"""
        from backend.agent.tools.executor import ToolExecutor

        executor = ToolExecutor()

        for tool in tools:
            # 使用闭包捕获 tool 实例
            def make_tool_wrapper(t: Tool):
                @agent.tool(name=t.name, description=t.description)
                async def tool_wrapper(ctx, **kwargs):
                    return await executor.execute(t, ctx, **kwargs)

                return tool_wrapper

            make_tool_wrapper(tool)
            logger.debug("Tool registered to agent", name=tool.name)

        logger.info("Tools registered to agent", count=len(tools), names=[t.name for t in tools])

    def register_all(self, agent: Agent[LumenDeps, str]) -> None:
        """将当前工具池注册到 PydanticAI Agent。

        为每个工具生成 @agent.tool 装饰的函数，保持与现有 Agent 的兼容性。
        """
        if not self._scanned:
            self.scan()

        self._register_tools(agent, list(self._tools.values()))

    def register_selective(self, agent: Agent[LumenDeps, str], names: list[str]) -> None:
        """选择性注册工具到 Agent（用于轻量 Agent 只加载部分工具）。"""
        if not self._scanned:
            self.scan()

        selected: list[Tool] = []
        for name in names:
            tool = self._tools.get(name)
            if tool:
                selected.append(tool)
            else:
                logger.warning("Tool not found in registry", name=name)

        self._register_tools(agent, selected)

    # -- 管理 --

    def add_tool(self, tool: Tool) -> None:
        """运行时动态添加工具（用于测试、MCP 热加载）。"""
        if tool.name in self._tools:
            logger.warning("Replacing existing tool", name=tool.name)
        self._tools[tool.name] = tool

    def remove_tool(self, name: str) -> Tool | None:
        """运行时移除工具。"""
        return self._tools.pop(name, None)

    def clear(self) -> None:
        """清空注册表（主要用于测试）。"""
        self._tools.clear()
        self._scanned = False


# 便捷函数 — 保持向后兼容
def get_registry() -> ToolRegistry:
    """获取 ToolRegistry 单例。"""
    return ToolRegistry()


def register_all_tools(agent: Agent[LumenDeps, str]) -> None:
    """注册所有工具到 Agent（兼容现有调用方式）。"""
    registry = get_registry()
    registry.register_all(agent)
