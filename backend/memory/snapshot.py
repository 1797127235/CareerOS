"""Agent 系统提示快照 — 分层注入（固定块 + 近期上下文 + 语义召回）。

L0 固定块：用户画像聚合（GrowthEvent → about_you.md / 字段拼接）
L1 近期上下文：最近对话的摘要（Conversation + Message，非原始事件）
L2 语义召回：Cognee / FTS5 / .md 检索（由 facade.build_context 触发）

L0 和 L1 使用不同的数据源（GrowthEvent vs Conversation），
因此物理上不可能出现同一信息的聚合态和原始态重复注入。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.db import get_async_session_maker
from backend.domain.models import Conversation, GrowthEvent, Message
from backend.logging_config import get_logger

logger = get_logger(__name__)

_FIXED_BUDGET = 800
_FIXED_ALLOCATION = {
    "identity": 300,
    "goals": 200,
    "skills": 200,
    "preferences": 100,
}

_CONTEXT_MAX_CONVERSATIONS = 5
_CONTEXT_MAX_MESSAGES_PER_CONV = 3
_CONTEXT_MAX_AGE_DAYS = 7
_CONTEXT_MAX_CHARS = 600

_CACHE_TTL_MINUTES = 5
_MAX_CACHE_SIZE = 100


@dataclass
class _CacheEntry:
    user_id: str
    content: str
    created_at: datetime
    context_conv_ids: set[str]


_static_cache: dict[str, _CacheEntry] = {}


def _cache_insert(entry: _CacheEntry) -> None:
    """插入缓存条目，超出上限时驱逐最久未使用的条目。"""
    if len(_static_cache) >= _MAX_CACHE_SIZE:
        lru_user = min(_static_cache, key=lambda k: _static_cache[k].created_at)
        del _static_cache[lru_user]
    _static_cache[entry.user_id] = entry


def invalidate_cache(user_id: str) -> None:
    _static_cache.pop(user_id, None)


def get_recent_event_ids(user_id: str) -> set[str]:
    """保持向后兼容 — L2 去重现在基于对话 ID 而非事件 ID。"""
    return get_context_conv_ids(user_id)


def get_context_conv_ids(user_id: str) -> set[str]:
    entry = _static_cache.get(user_id)
    if entry is None:
        return set()
    if (datetime.now(UTC) - entry.created_at) >= timedelta(minutes=_CACHE_TTL_MINUTES):
        return set()
    return entry.context_conv_ids


def _truncate(text: str, limit: int, suffix: str = "…") -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)] + suffix


# ── L0: 固定块（画像聚合，数据源 = GrowthEvent）──────────────────


def _build_fixed_block(
    profile: dict,
    goals: dict,
    skills: dict,
    preferences: dict,
) -> str:
    parts: list[str] = []
    budget = _FIXED_BUDGET

    identity_lines: list[str] = []
    identity_lines.append("## 身份")
    if profile.get("school_name"):
        identity_lines.append(f"- 学校：{profile['school_name']}")
    if profile.get("major"):
        identity_lines.append(f"- 专业：{profile['major']}")
    if profile.get("grade"):
        identity_lines.append(f"- 年级：{profile['grade']}")
    if profile.get("target_direction"):
        identity_lines.append(f"- 目标：{profile['target_direction']}")
    if profile.get("city"):
        identity_lines.append(f"- 城市：{profile['city']}")
    identity_text = "\n".join(identity_lines)
    identity_truncated = _truncate(identity_text, _FIXED_ALLOCATION["identity"])
    parts.append(identity_truncated)
    budget -= len(identity_truncated)

    if goals:
        goals_lines = ["## 目标"]
        for name, detail in list(goals.items())[:5]:
            goals_lines.append(f"- {name}：{str(detail)[:60]}")
        goals_text = "\n".join(goals_lines)
        goals_truncated = _truncate(goals_text, _FIXED_ALLOCATION["goals"])
        parts.append(goals_truncated)
        budget -= len(goals_truncated)

    if skills:
        skills_lines = ["## 技能"]
        for name, info in list(skills.items())[:8]:
            level = info.get("level", "")
            skills_lines.append(f"- {name}" + (f"（{level}）" if level else ""))
        skills_text = "\n".join(skills_lines)
        skills_truncated = _truncate(skills_text, _FIXED_ALLOCATION["skills"])
        parts.append(skills_truncated)
        budget -= len(skills_truncated)

    if preferences and budget > 50:
        pref_lines = ["## 偏好"]
        for key, value in list(preferences.items())[:5]:
            pref_lines.append(f"- {key}：{str(value)[:40]}")
        pref_text = "\n".join(pref_lines)
        pref_truncated = _truncate(pref_text, max(budget, _FIXED_ALLOCATION["preferences"]))
        parts.append(pref_truncated)

    return "\n\n".join(parts)


def _build_fixed_block_v2(
    user_id: str,
    profile: dict,
    goals: dict,
    skills: dict,
    preferences: dict,
) -> str:
    """L0 固定块 v2：优先使用 AI 综合画像，降级到字段拼接。"""
    from backend.memory.markdown import read_about_you

    about_you = read_about_you(user_id)
    if about_you and len(about_you.strip()) > 50:
        return f"## AI 对你的理解\n{about_you.strip()}"

    return _build_fixed_block(profile, goals, skills, preferences)


# ── L1: 近期上下文（数据源 = Conversation + Message）────────────


def _build_context_block(
    conversations: list[Conversation],
    messages_by_conv: dict[str, list[Message]],
) -> tuple[str, set[str]]:
    """从最近对话中提取上下文摘要。

    与 L0 不同：L0 聚合 GrowthEvent 得到"用户是谁"，
    L1 从对话记录提取"最近在聊什么" — 数据源完全分离，不存在重复。
    """
    if not conversations:
        return "", set()

    lines: list[str] = ["## 近期对话"]
    conv_ids: set[str] = set()
    total_chars = 0

    for conv in conversations:
        if total_chars >= _CONTEXT_MAX_CHARS:
            break

        msgs = messages_by_conv.get(conv.conversation_id, [])
        if not msgs:
            continue

        # 对话标题（优先用 title，否则用第一条用户消息截断）
        title = conv.title
        if not title:
            user_msgs = [m for m in msgs if m.role == "user"]
            if user_msgs:
                title = (user_msgs[0].content or "")[:40]
            else:
                title = "未命名对话"

        # 对话摘要（如果有 LLM 生成的 summary）
        if conv.summary:
            line = f"- **{title}**：{conv.summary[:80]}"
        else:
            # 取最近几条消息的内容片段
            msg_parts: list[str] = []
            for msg in msgs[:_CONTEXT_MAX_MESSAGES_PER_CONV]:
                if msg.content:
                    msg_parts.append(msg.content[:60])
            content_hint = "；".join(msg_parts)
            line = f"- **{title}**：{content_hint[:80]}" if content_hint else f"- **{title}**"

        if len(line) > 120:
            line = line[:117] + "…"

        lines.append(line)
        conv_ids.add(conv.conversation_id)
        total_chars += len(line)

    if len(lines) <= 1:  # 只有标题行
        return "", set()

    return "\n".join(lines), conv_ids


async def _fetch_recent_conversations(
    user_id: str,
    db,
) -> tuple[list[Conversation], dict[str, list[Message]]]:
    """查询最近 N 天的对话及其最新消息。"""
    cutoff = datetime.now(UTC) - timedelta(days=_CONTEXT_MAX_AGE_DAYS)

    # 取最近的对话
    conv_stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.status == "active",
            Conversation.last_message_at >= cutoff,
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(_CONTEXT_MAX_CONVERSATIONS)
    )
    conv_result = await db.execute(conv_stmt)
    conversations = list(conv_result.scalars().all())

    if not conversations:
        return [], {}

    # 取每个对话的最新消息
    conv_ids = [c.conversation_id for c in conversations]
    msg_stmt = select(Message).where(Message.conversation_id.in_(conv_ids)).order_by(Message.created_at.desc())
    msg_result = await db.execute(msg_stmt)
    all_messages = list(msg_result.scalars().all())

    # 按对话分组，每个对话最多保留指定条数
    messages_by_conv: dict[str, list[Message]] = {}
    for msg in all_messages:
        msgs = messages_by_conv.setdefault(msg.conversation_id, [])
        if len(msgs) < _CONTEXT_MAX_MESSAGES_PER_CONV:
            msgs.append(msg)

    return conversations, messages_by_conv


# ── 构建快照 ──────────────────────────────────────────────────────


async def build_snapshot(user_id: str) -> str:
    cached = _static_cache.get(user_id)
    if cached and (datetime.now(UTC) - cached.created_at) < timedelta(minutes=_CACHE_TTL_MINUTES):
        return cached.content

    from backend.memory.events_merger import (
        merge_dict_events,
        merge_profile_events,
        merge_skill_events,
    )

    async with get_async_session_maker()() as db:
        # L0: 从 GrowthEvent 聚合画像
        stmt = select(GrowthEvent).where(GrowthEvent.user_id == user_id).order_by(GrowthEvent.created_at.desc())
        result = await db.execute(stmt)
        all_events = list(result.scalars().all())

        # L1: 从 Conversation + Message 提取近期上下文
        conversations, messages_by_conv = await _fetch_recent_conversations(user_id, db)

    if not all_events and not conversations:
        content = "【用户画像为空】"
        _cache_insert(
            _CacheEntry(user_id=user_id, content=content, created_at=datetime.now(UTC), context_conv_ids=set())
        )
        return content

    # L0 固定块
    fixed_block = ""
    if all_events:
        events_by_type: dict[str, list] = defaultdict(list)
        for event in all_events:
            events_by_type[event.event_type].append(event)

        profile = merge_profile_events(events_by_type.get("profile_updated", []))
        goals = merge_dict_events(events_by_type.get("goal_updated", []))
        skills = merge_skill_events(
            events_by_type.get("skill_added", []) + events_by_type.get("skill_level_changed", [])
        )
        preferences = merge_dict_events(events_by_type.get("preference_learned", []))

        fixed_block = _build_fixed_block_v2(user_id, profile, goals, skills, preferences)

    # L1 近期上下文
    context_block, conv_ids = _build_context_block(conversations, messages_by_conv)

    parts = [p for p in [fixed_block, context_block] if p]
    content = "\n\n".join(parts) if parts else "【用户画像为空】"

    _cache_insert(
        _CacheEntry(user_id=user_id, content=content, created_at=datetime.now(UTC), context_conv_ids=conv_ids)
    )
    return content
