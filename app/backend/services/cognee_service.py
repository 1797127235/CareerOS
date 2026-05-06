"""Cognee 封装：失败时回退到 SQLite。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.backend.config import get_settings
from app.backend.db.base import get_async_session_maker
from app.backend.logging_config import get_logger

logger = get_logger(__name__)


def _cognee_metadata(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {**(extra or {}), "dataset": get_settings().cognee_dataset}


async def remember(user_id: str, content: str, metadata: dict[str, Any] | None = None) -> bool:
    try:
        import cognee

        await cognee.remember(content, metadata=_cognee_metadata(metadata))
        logger.debug("Cognee remember", user_id=user_id, content_length=len(content))
        return True
    except Exception as exc:
        logger.error("Cognee remember failed", user_id=user_id, error=str(exc))
        return False


async def recall(user_id: str, query: str, limit: int = 10) -> list[dict[str, str | None]]:
    """语义搜索。返回 [{"text": ..., "event_id": ..., "event_type": ..., "created_at": ...}]。"""
    try:
        import cognee

        results = await cognee.search(query)
        user_results: list[dict] = []
        for result in results or []:
            metadata = getattr(result, "metadata", None) or {}
            if metadata.get("user_id") != user_id:
                continue
            user_results.append(
                {
                    "text": getattr(result, "text", str(result)),
                    "event_id": metadata.get("event_id"),
                    "event_type": metadata.get("event_type"),
                    "created_at": metadata.get("created_at"),
                }
            )
        if user_results:
            return user_results[:limit]
    except Exception as exc:
        logger.warning("Cognee recall failed, fallback to SQLite", user_id=user_id, error=str(exc))

    return await _recall_from_sqlite(user_id, query, limit)


async def clear_user_index(user_id: str) -> bool:
    """清除 Cognee 索引。

    ⚠️ 架构限制：Cognee 当前使用全局 kuzu/lancedb 目录，不支持 per-user 隔离。
    此函数会删除 ALL 用户的语义索引，不仅是 user_id 指定的用户。
    单用户模式下安全；多用户场景需等 Cognee 支持 per-user namespace。
    """
    try:
        from app.backend.agent.cognee_client import USER_DATA_DIR, init_cognee

        logger.warning(
            "Clearing GLOBAL Cognee index (kuzu + lancedb). " "This affects ALL users, not just this user_id",
            user_id=user_id,
        )
        removed_any = False
        for name in ("kuzu", "lancedb"):
            path = Path(USER_DATA_DIR) / name
            if path.exists():
                shutil.rmtree(path, ignore_errors=False)
                removed_any = True

        init_cognee()
        logger.info("Cognee index cleared", user_id=user_id, removed_any=removed_any)
        return True
    except Exception as exc:
        logger.error("Cognee clear_user_index failed", user_id=user_id, error=str(exc))
        return False


async def rebuild_from_sqlite(user_id: str) -> bool:
    try:
        import cognee

        from app.backend.models.growth_event import GrowthEvent

        async with get_async_session_maker()() as db:
            result = await db.execute(
                select(GrowthEvent).where(GrowthEvent.user_id == user_id).order_by(GrowthEvent.created_at)
            )
            events = result.scalars().all()

            for event in events:
                content = event.payload_json or f"{event.event_type}: {event.entity_type or 'unknown'}"
                metadata = {
                    "user_id": event.user_id,
                    "event_id": str(event.id),
                    "event_type": event.event_type,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "source": event.source,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
                await cognee.remember(content, metadata=_cognee_metadata(metadata))
                event.projected_cognee_at = datetime.now(datetime.UTC)

            await db.commit()

        logger.info("Cognee rebuilt from SQLite", user_id=user_id, events_count=len(events))
        return True
    except Exception as exc:
        logger.error("Cognee rebuild failed", user_id=user_id, error=str(exc))
        return False


async def _recall_from_sqlite(user_id: str, query: str, limit: int) -> list[dict[str, str | None]]:
    """Cognee 不可用时的回退搜索：用 FTS5 全文匹配，而非盲目返回最新 N 条。"""
    try:
        import re as _re

        from sqlalchemy import text

        from app.backend.models.growth_event import GrowthEvent

        _CJK_RE = _re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

        async with get_async_session_maker()() as db:
            if query and query.strip():
                # CJK 用 trigram 表，非 CJK 用标准表
                fts_table = "growth_events_fts_trigram" if _CJK_RE.search(query) else "growth_events_fts"
                fts_sql = text(f"""
                    SELECT ge.id, ge.payload_json, ge.event_type, ge.entity_type, ge.created_at
                    FROM growth_events ge
                    JOIN {fts_table} fts ON fts.rowid = ge.rowid
                    WHERE ge.user_id = :uid AND {fts_table} MATCH :q
                    ORDER BY ge.created_at DESC
                    LIMIT :lim
                """)
                rows = (await db.execute(fts_sql, {"uid": user_id, "q": query, "lim": limit})).all()
                memories = []
                for row in rows:
                    event = GrowthEvent(
                        id=row[0],
                        payload_json=row[1],
                        event_type=row[2],
                        entity_type=row[3],
                        created_at=row[4],
                    )
                    memories.append(
                        {
                            "text": _format_event_text(event),
                            "event_id": str(row[0]),
                            "event_type": row[2],
                            "created_at": row[4].isoformat() if row[4] else None,
                        }
                    )
                if memories:
                    return memories

            # FTS5 无结果或 query 为空 → 按时间倒序兜底
            result = await db.execute(
                select(GrowthEvent)
                .where(GrowthEvent.user_id == user_id)
                .order_by(GrowthEvent.created_at.desc())
                .limit(limit)
            )
            events = result.scalars().all()

        return [
            {
                "text": _format_event_text(event),
                "event_id": str(event.id),
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
    except Exception as exc:
        logger.error("SQLite recall failed", user_id=user_id, error=str(exc))
        return []


def _format_event_text(event) -> str:
    """GrowthEvent → 人类可读文本。"""
    payload = {}
    if event.payload_json:
        try:
            payload = json.loads(event.payload_json)
        except json.JSONDecodeError:
            payload = {}

    if event.event_type == "skill_added":
        skill = payload.get("skill_name") or payload.get("name") or event.entity_id or "未知技能"
        level = payload.get("level", "未知水平")
        return f"掌握了 {skill}（{level}）"
    if event.event_type == "profile_updated":
        if payload.get("memory_md"):
            return "更新了核心画像"
        school = payload.get("school_name", "")
        major = payload.get("major", "")
        return f"更新了画像：{school} {major}".strip()
    if event.event_type == "experience_added":
        title = payload.get("title", event.entity_id or "未知经历")
        desc = payload.get("description", "")
        return f"经历：{title} — {desc}" if desc else f"经历：{title}"
    if payload:
        return f"{event.event_type}: {json.dumps(payload, ensure_ascii=False)}"
    return f"{event.event_type}: {event.entity_type or 'unknown'}"
