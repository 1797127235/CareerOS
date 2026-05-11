"""统一工具接口 — Lumen Tool System 基础层。

所有 Agent 工具（内置、MCP 桥接、未来扩展）必须实现 Tool 接口。
Agent 侧通过 ToolRegistry 统一发现、注册和执行，不感知工具底层实现差异。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunContext  # pyright: ignore[reportMissingImports]

from backend.agent.deps import LumenDeps
from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果。

    统一返回格式，替代各工具直接返回 str/dict 的混乱局面。
    """

    data: str
    """给 Agent 看的文本结果。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据（遥测、日志、UI 渲染用），不进入 Agent 上下文。"""

    error: str | None = None
    """若执行失败， human-readable 错误信息。Agent 可见，用于自我纠正。"""

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @classmethod
    def ok(cls, data: str, **metadata: Any) -> ToolResult:
        return cls(data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, data: str = "", **metadata: Any) -> ToolResult:
        return cls(data=data, error=error, metadata=metadata)


@dataclass(frozen=True)
class ValidationResult:
    """输入校验 / 权限检查结果。"""

    ok: bool
    message: str = ""
    error_code: str = ""

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(ok=True)

    @classmethod
    def reject(cls, message: str, error_code: str = "") -> ValidationResult:
        return cls(ok=False, message=message, error_code=error_code)


class Tool(ABC):
    """Lumen 工具统一接口。

    内置工具、MCP 桥接工具、Web 工具等都从此抽象。
    Agent 侧只通过 name/call() 交互，不感知实现差异。

    实现者只需关注：
    1. name / description — Agent 可见的元数据
    2. call() — 实际执行逻辑
    3. 可选 validate() — 输入校验 / 权限检查

    其余（日志、错误包装、metrics）由 ToolExecutor 统一处理。
    """

    # -- 元数据（类属性，子类覆盖） --
    name: str = ""
    """工具唯一标识。Agent 通过此名调用。"""

    description: str = ""
    """工具描述，注入 Agent system prompt。"""

    is_read_only: bool = True
    """是否为只读工具。影响并发策略和权限检查粒度。"""

    # -- 核心执行 --

    @abstractmethod
    async def call(self, ctx: RunContext[LumenDeps], **kwargs: Any) -> ToolResult:
        """执行工具。

        Args:
            ctx: PydanticAI RunContext，包含 deps（user_id, db 等）
            **kwargs: Agent 传入的参数（已校验类型）

        Returns:
            ToolResult: 统一结果格式
        """
        ...

    async def validate(self, ctx: RunContext[LumenDeps], **kwargs: Any) -> ValidationResult:
        """【可选】输入校验 + 权限检查。

        在 call() 之前执行。失败时直接返回错误，不进入 call()。
        默认通过（无校验）。子类可覆盖实现自定义逻辑。

        Args:
            ctx: RunContext
            **kwargs: Agent 传入的原始参数

        Returns:
            ValidationResult: 通过 / 拒绝
        """
        return ValidationResult.success()

    # -- 注册辅助 --

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """子类化时自动校验必要属性。"""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise TypeError(f"Tool subclass {cls.__name__} must define 'name'")
        if not cls.description:
            logger.warning(f"Tool {cls.__name__} has no description")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, read_only={self.is_read_only})"
