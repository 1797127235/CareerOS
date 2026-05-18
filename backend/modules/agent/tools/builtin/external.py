"""数据源读取工具 Handlers — data_source_search / get_item / notes_list。"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from sqlalchemy import select, text

from backend.core.db import get_async_session_maker
from backend.core.logging import get_logger
from backend.modules.agent.tools.core.context import ToolRuntimeContext
from backend.modules.memory.models import GrowthEvent
from backend.modules.memory.search import search_all

logger = get_logger(__name__)


async def handle_data_source_search(args: dict[str, Any], ctx: ToolRuntimeContext) -> str:
    """搜索用户记忆中的内容（随记、成长事件等），返回可引用结果。"""

    query = args.get("query", "").strip()
    limit = min(int(args.get("limit", 5)), 10)
    if not query:
        return "[工具错误] 请提供搜索关键词。"

    results = await search_all(ctx.user_id, query, limit=limit)
    if not results:
        return "未找到相关内容。"

    lines = [f"找到 {len(results)} 条相关内容："]
    for idx, item in enumerate(results, 1):
        lines.append(f"\n{idx}. {item.content}")

    return "\n".join(lines)


async def handle_notes_list(args: dict[str, Any], ctx: ToolRuntimeContext) -> str:
    """列出用户最近的随记。"""

    limit = min(int(args.get("limit", 10)), 50)
    async with get_async_session_maker()() as db:
        rows = (
            (
                await db.execute(
                    select(GrowthEvent)
                    .where(GrowthEvent.user_id == ctx.user_id)
                    .where(GrowthEvent.event_type == "quick_note")
                    .order_by(GrowthEvent.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    if not rows:
        return "用户目前没有任何随记。"

    lines = [f"用户共有 {len(rows)} 条随记（最近 {limit} 条）："]
    for i, ev in enumerate(rows, 1):
        payload = {}
        if ev.payload_json:
            with contextlib.suppress(json.JSONDecodeError):
                payload = json.loads(ev.payload_json)
        content = payload.get("content", "")
        ts = ev.created_at.strftime("%Y-%m-%d %H:%M") if ev.created_at else "未知时间"
        lines.append(f"\n{i}. [{ts}] {content}")

    return "\n".join(lines)


async def handle_data_source_get_item(args: dict[str, Any], ctx: ToolRuntimeContext) -> str:
    """按 item_id 读取外部文档的完整内容。"""

    item_id = args.get("item_id", "").strip()
    max_chars = min(int(args.get("max_chars", 4000)), 10000)
    if not item_id:
        return "[工具错误] 请提供 item_id。"

    async with get_async_session_maker()() as db:
        row = (
            await db.execute(
                text("""
                    SELECT title, uri, content, connector_type, data_source_id, indexed_at
                    FROM external_items
                    WHERE id = :id AND user_id = :uid AND deleted_at IS NULL
                """),
                {"id": item_id, "uid": ctx.user_id},
            )
        ).first()

        if not row:
            return f"未找到 item_id={item_id} 的文档。"

        title, uri, content, ctype, _ds_id, indexed_at = row
        snippet = (content or "")[:max_chars]
        truncated = "…（已截断）" if content and len(content) > max_chars else ""

        return (
            f"标题: {title or '未命名'}\n"
            f"来源: {uri or '未知'}\n"
            f"类型: {ctype or 'unknown'}\n"
            f"索引时间: {indexed_at.isoformat() if indexed_at else '无'}\n"
            f"内容:\n{snippet}{truncated}"
        )
