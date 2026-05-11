"""统一工具执行器 — 所有工具调用的中央流水线。

执行流程：
  Agent 调用 tool
    → ToolExecutor.execute()
      1. validate()    — 输入校验 + 权限检查
      2. pre_execute() — 日志、metrics、hook
      3. call()        — 实际执行（含 try/catch）
      4. post_execute()— 结果格式化、错误分类、metrics
      5. 返回 ToolResult

设计原则：
- 工具作者只写业务逻辑（call()）
- 横切关注点（日志、错误、metrics）在此统一处理
- 错误是数据不是异常：任何阶段失败都返回 ToolResult(error=...)，不抛异常打断 Agent
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic_ai import RunContext  # pyright: ignore[reportMissingImports]

from backend.agent.deps import LumenDeps
from backend.agent.tools.base import Tool, ToolResult, ValidationResult
from backend.logging_config import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """工具执行器 — 无状态，可复用。"""

    # 默认超时（秒）
    DEFAULT_TIMEOUT: float = 15.0

    async def execute(
        self,
        tool: Tool,
        ctx: RunContext[LumenDeps],
        **kwargs: Any,
    ) -> str:
        """执行单个工具 — 完整流水线。

        返回 str（兼容 PydanticAI Agent 的 tool 返回值类型）。
        内部错误被捕获并包装为 error message，不抛异常。

        Args:
            tool: 工具实例
            ctx: PydanticAI RunContext
            **kwargs: Agent 传入的参数

        Returns:
            str: 执行结果文本（成功或错误信息）
        """
        start_time = time.perf_counter()
        tool_name = tool.name

        # ── Stage 1: 输入校验 ──
        try:
            validation = await self._run_with_timeout(
                tool.validate(ctx, **kwargs),
                timeout=2.0,
                fallback=ValidationResult.reject("校验超时"),
            )
        except Exception as exc:
            logger.exception("Tool validation crashed", tool=tool_name, error=str(exc))
            validation = ValidationResult.reject(f"校验异常: {exc}")

        if not validation.ok:
            logger.warning(
                "Tool validation failed",
                tool=tool_name,
                user_id=ctx.deps.user_id,
                reason=validation.message,
            )
            return self._format_error(validation.message, validation.error_code)

        # ── Stage 2: 执行前日志 ──
        logger.info(
            "Tool executing",
            tool=tool_name,
            user_id=ctx.deps.user_id,
            read_only=tool.is_read_only,
            kwargs_summary=self._summarize_kwargs(kwargs),
        )

        # ── Stage 3: 实际执行 ──
        try:
            result = await self._run_with_timeout(
                tool.call(ctx, **kwargs),
                timeout=self.DEFAULT_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Tool timeout", tool=tool_name, timeout=self.DEFAULT_TIMEOUT)
            result = ToolResult.fail("执行超时，请重试")
        except Exception as exc:
            logger.exception("Tool execution failed", tool=tool_name, error=str(exc))
            result = ToolResult.fail(self._classify_error(exc))

        # ── Stage 4: 执行后处理 ──
        duration_ms = (time.perf_counter() - start_time) * 1000

        if result.is_error:
            logger.warning(
                "Tool failed",
                tool=tool_name,
                user_id=ctx.deps.user_id,
                error=result.error,
                duration_ms=round(duration_ms, 2),
            )
            return self._format_error(result.error or "未知错误", result.metadata.get("error_code", ""))

        logger.info(
            "Tool succeeded",
            tool=tool_name,
            user_id=ctx.deps.user_id,
            duration_ms=round(duration_ms, 2),
            result_length=len(result.data),
        )

        # metadata 可用于未来 metrics / tracing，现在只记录 debug
        if result.metadata:
            logger.debug("Tool metadata", tool=tool_name, metadata=result.metadata)

        return result.data

    # -- 内部辅助 --

    async def _run_with_timeout(
        self,
        coro,
        *,
        timeout: float,
        fallback: Any | None = None,
    ) -> Any:
        """带超时的协程执行。"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError:
            if fallback is not None:
                return fallback
            raise

    def _summarize_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """脱敏 + 截断参数，用于日志。"""
        summary: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in ("api_key", "token", "password", "secret"):
                summary[k] = "***"
            elif isinstance(v, str) and len(v) > 200:
                summary[k] = v[:200] + "..."
            else:
                summary[k] = v
        return summary

    def _classify_error(self, exc: Exception) -> str:
        """异常分类 — 生成 user-facing 错误信息。"""
        exc_type = type(exc).__name__

        # 已知异常类型 → 友好提示
        if exc_type in ("ConnectionError", "TimeoutError", "OSError"):
            return f"服务暂时不可用 ({exc_type}): {exc}"
        if exc_type in ("ValueError", "TypeError", "KeyError"):
            return f"参数错误: {exc}"
        if exc_type in ("PermissionError", "AccessDenied"):
            return f"权限不足: {exc}"

        # 未知异常 → 脱敏
        return f"执行失败 ({exc_type})"

    def _format_error(self, message: str, code: str = "") -> str:
        """格式化错误信息返回给 Agent。"""
        if code:
            return f"[工具错误/{code}] {message}"
        return f"[工具错误] {message}"
