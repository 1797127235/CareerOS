"""Agent 系统提示快照 — 分层注入（固定块 + 近期块 + 语义召回）。"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.db import get_async_session_maker
from backend.logging_config import get_logger
from backend.models import GrowthEvent

logger = get_logger(__name__)

_FIXED_BUDGET = 800
_FIXED_ALLOCATION = {
    "identity": 300,
    "goals": 200,
    "skills": 200,
    "preferences": 100,
}

_RECENT_LIMIT = 10
_RECENT_MAX_AGE_DAYS = 30

_EVENT_DECAY_WEIGHTS: dict[str, float] = {
    "profile_updated": 0.0,
    "goal_updated": 0.1,
    "skill_added": 0.2,
    "skill_level_changed": 0.2,
    "preference_learned": 0.3,
    "status_changed": 0.4,
    "experience_added": 0.3,
    "decision_made": 0.3,
}

_DECAY_THRESHOLD = 5.0
_CACHE_TTL_MINUTES = 5


@dataclass
class _CacheEntry:
    user_id: str
    content: str
    created_at: datetime
    recent_event_ids: set[str]


_static_cache: dict[str, _CacheEntry] = {}


def invalidate_cache(user_id: str) -> None:
    _static_cache.pop(user_id, None)


def get_recent_event_ids(user_id: str) -> set[str]:
    entry = _static_cache.get(user_id)
    if entry is None:
        return set()
    if (datetime.now(UTC) - entry.created_at) >= timedelta(minutes=_CACHE_TTL_MINUTES):
        return set()
    return entry.recent_event_ids


def _truncate(text: str, limit: int, suffix: str = "…") -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)] + suffix


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


def _build_recent_block(events: list) -> tuple[str, set[str]]:
    now = datetime.now(UTC)
    filtered: list[tuple[str, str, float, str]] = []

    for event in events:
        if not event.created_at:
            continue

        age_days = (now - event.created_at.replace(tzinfo=UTC)).days
        if age_days > _RECENT_MAX_AGE_DAYS:
            continue

        if event.event_type == "profile_updated":
            continue

        weight = _EVENT_DECAY_WEIGHTS.get(event.event_type, 0.3)
        score = age_days * weight
        if score > _DECAY_THRESHOLD:
            continue

        content = ""
        if event.payload_json:
            try:
                payload = json.loads(event.payload_json)
                if isinstance(payload, dict):
                    content = payload.get("content") or payload.get("value") or payload.get("memory_md", "")
            except json.JSONDecodeError:
                pass
        if not content:
            content = f"{event.event_type}: {event.entity_type or ''}"

        filtered.append((event.event_type, content[:120], score, str(event.id)))

    if not filtered:
        return "", set()

    filtered.sort(key=lambda x: x[2])
    top = filtered[:_RECENT_LIMIT]

    lines = ["## 近期动态"]
    event_ids: set[str] = set()
    for event_type, content, _score, eid in top:
        lines.append(f"- [{event_type}] {content}")
        event_ids.add(eid)

    return "\n".join(lines), event_ids


async def build_snapshot(user_id: str) -> str:
    cached = _static_cache.get(user_id)
    if cached and (datetime.now(UTC) - cached.created_at) < timedelta(minutes=_CACHE_TTL_MINUTES):
        return cached.content

    from backend.memory.events_merger import (
        merge_dict_events,
        merge_profile_events,
        merge_skill_events,
    )

    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_MAX_AGE_DAYS)
    async with get_async_session_maker()() as db:
        stmt = select(GrowthEvent).where(GrowthEvent.user_id == user_id).order_by(GrowthEvent.created_at.desc())
        result = await db.execute(stmt)
        all_events = list(result.scalars().all())

    recent_events = [e for e in all_events if e.created_at and e.created_at >= cutoff]

    if not all_events:
        result = "【用户画像为空】"
        _static_cache[user_id] = _CacheEntry(
            user_id=user_id, content=result, created_at=datetime.now(UTC), recent_event_ids=set()
        )
        return result

    events_by_type: dict[str, list] = defaultdict(list)
    for event in all_events:
        events_by_type[event.event_type].append(event)

    profile = merge_profile_events(events_by_type.get("profile_updated", []))
    goals = merge_dict_events(events_by_type.get("goal_updated", []))
    skills = merge_skill_events(events_by_type.get("skill_added", []) + events_by_type.get("skill_level_changed", []))
    preferences = merge_dict_events(events_by_type.get("preference_learned", []))

    fixed_block = _build_fixed_block(profile, goals, skills, preferences)
    recent_block, recent_event_ids = _build_recent_block(recent_events)

    parts = [fixed_block]
    if recent_block:
        parts.append(recent_block)

    result = "\n\n".join(parts)
    _static_cache[user_id] = _CacheEntry(
        user_id=user_id, content=result, created_at=datetime.now(UTC), recent_event_ids=recent_event_ids
    )
    return result
