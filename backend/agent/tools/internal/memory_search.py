"""memory_search 工具 — Agent 记忆搜索（统一 Tool 接口版）。"""

from __future__ import annotations

from pydantic_ai import RunContext

from backend.agent.deps import LumenDeps
from backend.agent.tools.base import Tool, ToolResult
from backend.logging_config import get_logger
from backend.memory import get_memory
from backend.memory.datasets import SCOPE_DATASETS

logger = get_logger(__name__)


class MemorySearchTool(Tool):
    """搜索用户记忆（内部 GrowthEvent）。支持 keyword / grep 两种模式。"""

    name = "memory_search"
    is_read_only = True
    description = (
        "搜索记忆。"
        "search_mode 选择："
        '- "keyword"（默认）— 关键词搜索，适用于「Python」「实习」等具体词；'
        '- "grep" — 时间范围浏览，适用于「最近做了什么」「这周」等自然语言，'
        "必须配合 time_filter 使用。"
        "time_filter（仅 grep 模式生效）："
        'today / yesterday / recent_3d / recent_7d / recent_30d / "YYYY-MM-DD~YYYY-MM-DD"'
        "scope（仅 keyword 模式生效）："
        "profile / emotions / reference / chat；不传则搜索全部。"
    )

    async def call(
        self,
        ctx: RunContext[LumenDeps],
        query: str,
        scope: str | None = None,
        search_mode: str = "keyword",
        time_filter: str | None = None,
    ) -> ToolResult:
        logger.info(
            "Tool call: memory_search",
            query=query,
            scope=scope,
            search_mode=search_mode,
            time_filter=time_filter,
        )

        if not query or not query.strip():
            return ToolResult.fail("请提供搜索关键词。")

        datasets = SCOPE_DATASETS.get(scope) if scope else None

        memory_instance = get_memory()
        items = await memory_instance.recall(
            ctx.deps.user_id,
            query,
            datasets=datasets,
            search_mode=search_mode,
            time_filter=time_filter,
        )
        if items:
            data = "\n".join(
                f"- [{item.categories[0] if item.categories else '?'}] {item.content[:300]}" for item in items
            )
            return ToolResult.ok(data, result_count=len(items))

        return ToolResult.ok("未找到相关内容。", result_count=0)
