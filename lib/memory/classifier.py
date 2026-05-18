"""事件分类器 — 双管线路由的单一真相源。

Profile 管线：描述用户「是谁」— 身份、兴趣、价值观、偏好
             → .md 投影 + L0 固定注入，不进 FTS5/Provider

Narrative 管线：描述用户「经历了什么」— 重要经历、决策、反思、矛盾、关系
                → FTS5/Provider 索引 + L2 按需召回
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Profile 事件：用户画像，永远注入 L0 ──
PROFILE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "profile_updated",  # 基础信息
        "interest_observed",  # 对什么真正着迷
        "value_surfaced",  # 在意什么、底线是什么
        "preference_learned",  # 偏好学习
        "emotional_pattern",  # 情绪规律观察
    }
)

# ── Narrative 事件：用户时间线，需要搜索召回 ──
NARRATIVE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "significant_moment",  # 有意义的经历
        "decision_made",  # 重要决策
        "reflection_added",  # 对话洞察、自我反思
        "contradiction_noted",  # 说 X 但做 Y 的观察
        "relationship_noted",  # 重要的人
    }
)

# ── L0 固定块（Profile 子集，不含 emotional_pattern）──
L0_FIXED_BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "profile_updated",
        "interest_observed",
        "value_surfaced",
        "preference_learned",
    }
)

PipelineName = Literal["profile", "narrative"]


def classify(event_type: str) -> PipelineName:
    """返回事件类型所属管线。未知类型默认归入 narrative。"""
    if event_type in PROFILE_EVENT_TYPES:
        return "profile"
    if event_type in NARRATIVE_EVENT_TYPES:
        return "narrative"
    logger.warning("Unknown event_type %r, defaulting to narrative", event_type)
    return "narrative"


def is_l0_fixed(event_type: str) -> bool:
    """该事件类型是否参与 L0 固定块画像聚合。"""
    return event_type in L0_FIXED_BLOCK_TYPES


def is_profile(event_type: str) -> bool:
    """该事件类型是否属于 Profile 管线。"""
    return event_type in PROFILE_EVENT_TYPES


__all__ = [
    "L0_FIXED_BLOCK_TYPES",
    "NARRATIVE_EVENT_TYPES",
    "PROFILE_EVENT_TYPES",
    "PipelineName",
    "classify",
    "is_l0_fixed",
    "is_profile",
]
