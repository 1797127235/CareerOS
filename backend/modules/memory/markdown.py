"""将已提交的成长事件投影为 Markdown 快照。"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import USER_DATA_DIR
from backend.core.db import get_async_session_maker
from backend.core.logging import get_logger
from backend.modules.memory.events_merger import (
    deep_merge,
    generate_memory_md,
    merge_decision_events,
    merge_dict_events,
    merge_narrative_events,
    merge_profile_events,
)
from backend.modules.memory.models import GrowthEvent

logger = get_logger(__name__)

# .md 文件字符限制（原 constants.py，仅本文件使用）
MD_CHAR_LIMITS: dict[str, int] = {
    "memory": 8000,  # 合并后综合画像总上限
    "about_you": 2000,  # AI 生成画像
    "patterns": 2000,  # 模式洞察（预留）
}

MEMORY_CHAR_LIMIT = MD_CHAR_LIMITS["memory"]
COMBINED_TOTAL_LIMIT = sum(MD_CHAR_LIMITS.values())  # ~14000，合并后总上限

_BASE_MEMORY_DIR = USER_DATA_DIR / "memory"


def memory_dir(user_id: str) -> Path:
    safe_id = Path(user_id).name
    return _BASE_MEMORY_DIR / safe_id


def ensure_memory_dirs(user_id: str) -> None:
    memory_dir(user_id).mkdir(parents=True, exist_ok=True)


def memory_default() -> str:
    return """# 关于你

> 由 Lumen 自动更新，记录 AI 对你的理解。

_还没有足够的记录。多和 Lumen 聊聊，它会逐渐了解你。_

---
*最后更新：待填写*
"""


def read_memory(user_id: str) -> str:
    memory_file = memory_dir(user_id) / "memory.md"
    if not memory_file.exists():
        return ""
    return memory_file.read_text(encoding="utf-8")


def _truncate_to_limit(content: str, limit: int) -> str:
    if len(content) <= limit:
        return content
    truncated = content[:limit]
    last_newline = truncated.rfind("\n\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    logger.warning("Content truncated", orig=len(content), truncated=len(truncated))
    return truncated


def _write_md_file_safe(path: str, content: str, max_chars: int | None = None) -> None:
    if max_chars is not None:
        content = _truncate_to_limit(content, max_chars)
    dir_name = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dir_name, suffix=".tmp", delete=False) as handle:
        handle.write(content)
        temp_path = handle.name
    os.replace(temp_path, path)


def _write_default_md_snapshot(user_id: str) -> None:
    ensure_memory_dirs(user_id)
    _write_md_file_safe(str(memory_dir(user_id) / "memory.md"), memory_default())


def _projection_cache_path(user_id: str) -> Path:
    return memory_dir(user_id) / "projection_cache.json"


def _load_projection_cache(user_id: str) -> dict | None:
    path = _projection_cache_path(user_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_projection_cache(user_id: str, data: dict) -> None:
    ensure_memory_dirs(user_id)
    path = _projection_cache_path(user_id)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(path.parent), suffix=".tmp", delete=False
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        temp = f.name
    os.replace(temp, path)


async def project_user_to_md(db: AsyncSession, user_id: str) -> bool:
    try:
        result = await db.execute(
            select(GrowthEvent).where(GrowthEvent.user_id == user_id).order_by(GrowthEvent.created_at.asc())
        )
        events = list(result.scalars().all())

        if not events:
            _write_default_md_snapshot(user_id)
            # 写入空缓存，避免后续增量更新回退
            _save_projection_cache(
                user_id,
                {
                    "profile": {},
                    "skills": {},
                    "experiences": [],
                    "preferences": {},
                    "status": {},
                    "goals": {},
                    "decisions": [],
                },
            )
            logger.debug("No events found; rebuilt default markdown", user_id=user_id)
            return True

        events_by_type: dict[str, list[GrowthEvent]] = defaultdict(list)
        for event in events:
            events_by_type[event.event_type].append(event)

        profile = merge_profile_events(events_by_type.get("profile_updated", []))
        interests = merge_dict_events(events_by_type.get("interest_observed", []))
        values = merge_dict_events(events_by_type.get("value_surfaced", []))
        preferences = merge_dict_events(events_by_type.get("preference_learned", []))
        emotions = merge_dict_events(events_by_type.get("emotional_pattern", []))
        moments = merge_narrative_events(events_by_type.get("significant_moment", []))
        decisions = merge_decision_events(events_by_type.get("decision_made", []))
        reflections = merge_narrative_events(events_by_type.get("reflection_added", []))
        relationships = merge_dict_events(events_by_type.get("relationship_noted", []))

        ensure_memory_dirs(user_id)
        d = memory_dir(user_id)

        core = generate_memory_md(
            profile,
            interests,
            values,
            preferences,
            emotions,
            moments,
            decisions,
            reflections,
            relationships,
        )
        combined = core

        _write_md_file_safe(str(d / "memory.md"), combined, max_chars=COMBINED_TOTAL_LIMIT)

        # 保存缓存供增量更新使用
        _save_projection_cache(
            user_id,
            {
                "profile": profile,
                "interests": interests,
                "values": values,
                "preferences": preferences,
                "emotions": emotions,
                "moments": moments,
                "decisions": decisions,
                "reflections": reflections,
                "relationships": relationships,
            },
        )

        now = datetime.now(UTC)
        for event in events:
            event.projected_md_at = now
        await db.flush()

        logger.info(
            ".md projection complete",
            user_id=user_id,
            events=len(events),
        )
        return True
    except Exception as exc:
        logger.error(".md projection failed", user_id=user_id, error=str(exc))
        return False


async def _incremental_update_md(db: AsyncSession, user_id: str, dirty_events: list[GrowthEvent]) -> bool:
    """增量更新 memory.md：只合并 dirty 事件到缓存数据，重新生成文件。

    前提：projection_cache.json 存在且有效；否则回退到 project_user_to_md。
    """
    cache = _load_projection_cache(user_id)
    if cache is None:
        logger.info("Projection cache missing; falling back to full rebuild", user_id=user_id)
        return await project_user_to_md(db, user_id)

    try:
        dirty_by_type: dict[str, list[GrowthEvent]] = defaultdict(list)
        for event in dirty_events:
            dirty_by_type[event.event_type].append(event)

        profile_updates = merge_profile_events(dirty_by_type.get("profile_updated", []))
        interests_updates = merge_dict_events(dirty_by_type.get("interest_observed", []))
        values_updates = merge_dict_events(dirty_by_type.get("value_surfaced", []))
        pref_updates = merge_dict_events(dirty_by_type.get("preference_learned", []))
        emotions_updates = merge_dict_events(dirty_by_type.get("emotional_pattern", []))
        moments_updates = merge_narrative_events(dirty_by_type.get("significant_moment", []))
        decision_updates = merge_decision_events(dirty_by_type.get("decision_made", []))
        reflections_updates = merge_narrative_events(dirty_by_type.get("reflection_added", []))
        relationships_updates = merge_dict_events(dirty_by_type.get("relationship_noted", []))

        profile = deep_merge(cache.get("profile", {}), profile_updates)
        interests = {**cache.get("interests", {}), **interests_updates}
        values = {**cache.get("values", {}), **values_updates}
        preferences = {**cache.get("preferences", {}), **pref_updates}
        emotions = {**cache.get("emotions", {}), **emotions_updates}
        moments = cache.get("moments", []) + moments_updates
        decisions = cache.get("decisions", []) + decision_updates
        reflections = cache.get("reflections", []) + reflections_updates
        relationships = {**cache.get("relationships", {}), **relationships_updates}

        core = generate_memory_md(
            profile,
            interests,
            values,
            preferences,
            emotions,
            moments,
            decisions,
            reflections,
            relationships,
        )
        combined = core

        _write_md_file_safe(str(memory_dir(user_id) / "memory.md"), combined, max_chars=COMBINED_TOTAL_LIMIT)

        _save_projection_cache(
            user_id,
            {
                "profile": profile,
                "interests": interests,
                "values": values,
                "preferences": preferences,
                "emotions": emotions,
                "moments": moments,
                "decisions": decisions,
                "reflections": reflections,
                "relationships": relationships,
            },
        )

        now = datetime.now(UTC)
        for event in dirty_events:
            event.projected_md_at = now
        await db.flush()

        logger.info(
            ".md projection incremental update complete",
            user_id=user_id,
            dirty_events=len(dirty_events),
        )
        return True
    except Exception as exc:
        logger.error("Incremental .md projection failed", user_id=user_id, error=str(exc))
        return False


def read_about_you(user_id: str) -> str:
    path = memory_dir(user_id) / "about_you.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


_META_RE = __import__("re").compile(r"^<!-- lumen-meta:.*?-->\n?")


def _strip_meta(content: str) -> str:
    """剥离 about_you.md 的元数据注释行，返回纯内容。"""
    return _META_RE.sub("", content, count=1)


def write_about_you(user_id: str, content: str, *, event_count: int = 0) -> None:
    """写入 AI 综合画像。

    首行附加元数据注释，记录覆盖事件数和生成时间，
    便于后续判断画像时效性和事件覆盖窗口。
    """
    from datetime import UTC, datetime

    ensure_memory_dirs(user_id)
    now = datetime.now(UTC).isoformat()
    meta = f"<!-- lumen-meta: events={event_count} generated_at={now} -->\n"
    _write_md_file_safe(
        str(memory_dir(user_id) / "about_you.md"),
        meta + content,
        max_chars=MD_CHAR_LIMITS.get("about_you", 2000),
    )


_INCREMENTAL_DIRTY_THRESHOLD = 5  # dirty < 5 走增量更新；>= 5 全量重建


async def sync_user_md_projection(user_id: str, *, db: AsyncSession | None = None) -> bool:
    """同步用户的 .md 投影。

    db 传入:   使用指定 session（调用方负责 commit/rollback）。
    db=None:   自开 session + commit。

    策略：
    - dirty == 0: 无需更新
    - 0 < dirty < _INCREMENTAL_DIRTY_THRESHOLD: 增量更新（读 dirty 事件 + 缓存，O(dirty)）
    - dirty >= _INCREMENTAL_DIRTY_THRESHOLD: 全量重建（读全部历史事件，O(n)）
    """
    if db is not None:
        dirty_count = await db.execute(
            select(func.count(GrowthEvent.id)).where(
                GrowthEvent.user_id == user_id,
                GrowthEvent.projected_md_at.is_(None),
            )
        )
        dirty = dirty_count.scalar() or 0
        if dirty == 0:
            return True

        if dirty < _INCREMENTAL_DIRTY_THRESHOLD:
            result = await db.execute(
                select(GrowthEvent)
                .where(
                    GrowthEvent.user_id == user_id,
                    GrowthEvent.projected_md_at.is_(None),
                )
                .order_by(GrowthEvent.created_at.asc())
            )
            dirty_events = list(result.scalars().all())
            return await _incremental_update_md(db, user_id, dirty_events)

        return await project_user_to_md(db, user_id)

    async with get_async_session_maker()() as db:
        success = await sync_user_md_projection(user_id, db=db)
        if success:
            await db.commit()
        else:
            await db.rollback()
        return success
