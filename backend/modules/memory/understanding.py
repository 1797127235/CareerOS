"""AI 综合画像生成器。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.core.db import get_async_session_maker
from backend.core.logging import get_logger
from backend.modules.memory.models import GrowthEvent

logger = get_logger(__name__)

# ── 防抖：同一 user_id 5 分钟内、或已有进行中的任务时不重复触发 ──
_PENDING_TASKS: dict[str, asyncio.Task] = {}
_LAST_UPDATE: dict[str, datetime] = {}
_DEBOUNCE_SECONDS = 300
_PENDING_LOCK = asyncio.Lock()


@dataclass
class AboutYouData:
    about_you: str = ""
    updated_at: str = ""
    patterns: list[dict] = field(default_factory=list)
    now_status: dict = field(default_factory=dict)
    journey: list[dict] = field(default_factory=list)


async def _get_profile_text(user_id: str) -> tuple[str, int, int]:
    """读取 memory.md 作为 LLM 画像生成的输入。

    替代原来的 _get_all_events_summary（逐事件读取），改为读取已合并的 memory.md。
    memory.md 是 project_user_to_md 的产出，包含去重、合并后的结构化画像数据。

    Returns:
        (memory_md_content, char_count, event_count)
    """
    from sqlalchemy import func as _func

    from backend.modules.memory.markdown import read_memory

    content = read_memory(user_id)
    if not content.strip():
        return "", 0, 0

    async with get_async_session_maker()() as db:
        result = await db.execute(select(_func.count(GrowthEvent.id)).where(GrowthEvent.user_id == user_id))
        count = result.scalar() or 0

    return content, len(content), count


def _is_debounced(user_id: str) -> bool:
    """检查是否应该跳过本次触发（并发防抖 + 时间窗口防抖）。"""
    existing_task = _PENDING_TASKS.get(user_id)
    if existing_task is not None and not existing_task.done():
        logger.debug("AI understanding already in progress", user_id=user_id)
        return True

    now = datetime.now(UTC)
    last = _LAST_UPDATE.get(user_id)
    if last and (now - last) < timedelta(seconds=_DEBOUNCE_SECONDS):
        logger.debug("AI understanding debounced", user_id=user_id, last=last.isoformat())
        return True

    return False


async def update_ai_understanding(user_id: str) -> str:
    """生成/更新 AI 综合画像。返回画像文本。

    防抖：同一 user_id 已有进行中的任务或最近更新过时不重复触发。
    成功后记录时间戳，失败不留时间戳（允许立即重试）。
    """
    from backend.modules.memory.markdown import read_about_you

    if _is_debounced(user_id):
        return read_about_you(user_id)

    # 创建 protected task 并在完成后自动清理
    async with _PENDING_LOCK:
        # 双重检查：获取锁后可能已有新任务注册
        if _is_debounced(user_id):
            return read_about_you(user_id)
        task = asyncio.create_task(_do_update_understanding(user_id))
        _PENDING_TASKS[user_id] = task

    try:
        return await task
    except asyncio.CancelledError:
        logger.debug("AI understanding cancelled", user_id=user_id)
        return read_about_you(user_id)
    finally:
        async with _PENDING_LOCK:
            if _PENDING_TASKS.get(user_id) is task:
                del _PENDING_TASKS[user_id]


async def _do_update_understanding(user_id: str) -> str:
    """执行实际的 LLM 画像生成（由 update_ai_understanding 的 protected task 调用）。"""
    from backend.modules.memory.markdown import read_about_you, write_about_you

    content, _, event_count = await _get_profile_text(user_id)
    existing = read_about_you(user_id)

    if not content.strip():
        return existing

    try:
        new_text = await _generate_understanding(content, existing)
    except Exception as exc:
        logger.warning("AI understanding generation failed", user_id=user_id, error=str(exc))
        return existing

    write_about_you(user_id, new_text, event_count=event_count)
    await _update_profile_data(user_id, new_text)

    # 只在成功后才写入时间戳（允许失败立即重试）
    _LAST_UPDATE[user_id] = datetime.now(UTC)

    logger.info("AI understanding updated", user_id=user_id, chars=len(new_text))
    return new_text


async def _generate_understanding(profile_text: str, existing: str) -> str:
    """调用 LLM 基于 memory.md 结构化画像生成 about_you 自然语言文本。

    输入从原始事件列表改为 memory.md（project_user_to_md 的产出），
    与结构化投影形成上下游关系，消除独立读取事件的重复开销。
    """
    from pydantic_ai import Agent

    from backend.modules.agent.pydantic_agent import _create_model

    model = _create_model()

    system_prompt = """你是一个 AI 伴侣的用户画像专家。基于用户的画像数据（Markdown 格式），生成一段关于用户的综合画像。

## 规则
1. 用第二人称（"你"），像向用户本人介绍他们自己
2. 写 2-3 段自然语言，总长 300-500 字
3. 只包含有证据支撑的观察，不编造
4. 使用"缺席成本测试"：6个月后全新对话中缺少此信息是否导致方向性失误？是→必须包含
5. 优先包含：用户事实（身份背景）、用户偏好（思维方式/价值取向）、关键决策
6. 忽略标记为"（待填写）"的字段——那是占位符，不是真实数据
7. 忽略纯技术操作细节（如技能的具体等级分数），保留有意义的上下文
8. 直接输出画像文本，不要加标题或分隔线"""

    existing_section = ""
    if existing and len(existing) > 20:
        existing_section = f"\n## 现有画像（需要在此基础上更新，保持连续性）\n{existing}"

    prompt = f"""## 用户画像数据（来自 memory.md）
{profile_text}
{existing_section}

请生成/更新用户画像。"""

    agent = Agent(model=model, output_type=str, system_prompt=system_prompt, retries=1)
    result = await agent.run(prompt)
    return result.output


async def _update_profile_data(user_id: str, about_you: str) -> None:
    """更新 UserProfile.profile_data 中的 ai_understanding 字段。"""
    from backend.modules.profile.models import UserProfile

    async with get_async_session_maker()() as db:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            data = dict(profile.profile_data or {})
            data["ai_understanding"] = about_you
            data["ai_understanding_updated_at"] = datetime.now(UTC).isoformat()
            profile.profile_data = data
            await db.commit()


async def get_about_you_data(user_id: str) -> AboutYouData:
    """读取完整的画像数据（关于你 + 模式 + 此刻 + 时间线）。

    updated_at 从 about_you.md 元数据注释中解析，不再依赖 DB 双写。
    """
    import re as _re

    from backend.modules.memory.markdown import read_about_you

    about_you_text = read_about_you(user_id)

    # 从 about_you.md 的 meta 注释中提取 generated_at 时间戳
    updated_at = ""
    if about_you_text:
        meta_match = _re.match(r"<!-- lumen-meta:.*?generated_at=([^\s>]+)", about_you_text)
        if meta_match:
            updated_at = meta_match.group(1)

    now_status = await _get_current_status(user_id)
    journey = await _get_journey(user_id)

    return AboutYouData(
        about_you=about_you_text,
        updated_at=updated_at,
        patterns=[],  # 模式洞察待实现
        now_status=now_status,
        journey=journey,
    )


async def _get_current_status(user_id: str) -> dict:
    """读取最新状态（status_changed + goal_updated 最近各 3 条）。"""
    from backend.modules.memory.events_merger import merge_dict_events

    async with get_async_session_maker()() as db:
        stmt = (
            select(GrowthEvent)
            .where(
                GrowthEvent.user_id == user_id,
                GrowthEvent.event_type.in_(["status_changed", "goal_updated"]),
            )
            .order_by(GrowthEvent.created_at.desc())
            .limit(10)
        )
        result = await db.execute(stmt)
        events = list(result.scalars().all())

    return merge_dict_events(events)


async def _get_journey(user_id: str) -> list[dict]:
    """构建成长时间线——聚合原始事件为有意义的时间节点。"""

    _TYPE_LABELS: dict[str, str] = {
        "skill_added": "技能成长",
        "skill_level_changed": "技能提升",
        "experience_added": "经历更新",
        "preference_learned": "新发现",
        "goal_updated": "目标调整",
        "status_changed": "状态变化",
        "decision_made": "关键决策",
    }

    async with get_async_session_maker()() as db:
        stmt = (
            select(GrowthEvent)
            .where(
                GrowthEvent.user_id == user_id,
                GrowthEvent.event_type.notin_(["profile_updated"]),
            )
            .order_by(GrowthEvent.created_at.asc())
            .limit(50)
        )
        result = await db.execute(stmt)
        events = list(result.scalars().all())

    def _extract_content(event: GrowthEvent) -> str:
        if not event.payload_json:
            return ""
        try:
            p = json.loads(event.payload_json)
            if not isinstance(p, dict):
                return ""
            return (
                p.get("content")
                or p.get("value")
                or p.get("memory_md")
                or p.get("description")
                or p.get("title")
                or p.get("name")  # SkillPayload / ExperiencePayload
                or ""
            )
        except json.JSONDecodeError:
            return ""

    # 按类型+时间窗口聚合（1小时内同类型合并）
    aggregated: list[dict] = []
    AGGREGATION_WINDOW_SEC = 3600

    for event in events:
        label = _TYPE_LABELS.get(event.event_type, event.event_type.replace("_", " ").title())
        content = _extract_content(event)

        # 尝试聚合到上一个同类型条目
        if aggregated:
            last = aggregated[-1]
            time_diff = (
                (event.created_at - last["_latest_date"]).total_seconds()
                if event.created_at and last["_latest_date"]
                else float("inf")
            )
            if last["type"] == label and time_diff < AGGREGATION_WINDOW_SEC:
                last["count"] += 1
                if content and content not in last.get("_contents", []):
                    last["_contents"].append(content)
                last["_latest_date"] = event.created_at
                continue

        # 新开一条
        entry: dict = {
            "id": str(event.id),
            "type": label,
            "content": content[:120] if content else f"新的{label}",
            "date": event.created_at.isoformat() if event.created_at else None,
            "_latest_date": event.created_at,
            "count": 1,
            "_contents": [content] if content else [],
        }
        aggregated.append(entry)

    # 清理内部字段 + 聚合文案
    for item in aggregated:
        item.pop("_latest_date", None)
        item.pop("_contents", None)
        count = item.pop("count", 1)
        if count > 1:
            item["content"] = f"新增了 {count} 项{item['type']}"

    return aggregated[:12]
