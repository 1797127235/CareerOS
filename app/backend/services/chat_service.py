"""对话服务 — SSE 流式对话 + 历史存 DB + 滚动摘要"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.agent.agent_loop import AgentResult, agent_loop
from app.backend.agent.llm_router import TaskType
from app.backend.agent.llm_router import chat as llm_chat
from app.backend.agent.orchestrator import run_orchestrator
from app.backend.agent.tools import tool_registry
from app.backend.models.agent_trace import AgentTrace
from app.backend.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

# ── 摘要 ──

# 每次触发生成摘要时，上下文窗口保留最近 20 条，更早的压缩为摘要
_SUMMARY_WINDOW = 20

# 按 conversation_id 隔离的轻量锁，防止并发触发摘要时数据竞争
# MVP: 只增不减，生产环境需加 LRU 或 TTL 清理（<100 对话无影响）
_summary_locks: dict[str, asyncio.Lock] = {}

_SUMMARIZE_PROMPT = """根据以下对话记录更新摘要。只保留：用户背景变化、重要结论和决策、未完成的待办。丢弃闲聊和中间推理。100 字以内，中文。无关紧要则输出"（无重要内容）"

【上次摘要】
{PREV}

【对话记录】
{MSGS}"""

_MAX_MSG_CHARS = 200  # 单条消息送入摘要前的截断长度


def _log_task_error(task: asyncio.Task) -> None:
    """asyncio.Task 的 done_callback：未取消且抛异常时记录日志。"""
    if not task.cancelled() and (exc := task.exception()):
        logger.error("摘要任务异常", exc_info=exc)


async def stream_chat(
    db: AsyncSession,
    user_id: str,
    user_input: str,
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    """
    SSE 流式对话：
    1. 获取/创建会话
    2. 加载历史上下文
    3. run_orchestrator：画像加载 + 意图分类 + 系统提示词组装
    4. agent_loop：ReAct 循环（支持工具调用）
    5. 存 DB + 滚动摘要
    """
    # 获取或创建会话
    if conversation_id:
        conv = await db.get(Conversation, conversation_id)
        if not conv or conv.user_id != user_id:
            yield _sse_error("会话不存在")
            return
    else:
        conv = Conversation(
            user_id=user_id,
            title=user_input[:30] + "..." if len(user_input) > 30 else user_input,
        )
        db.add(conv)
        await db.flush()

    yield _sse_token("", conv.conversation_id)  # 初始事件（返回 conversation_id）

    # 加载历史消息
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.conversation_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent = history_result.scalars().all()
    history_messages = [{"role": msg.role, "content": msg.content or ""} for msg in reversed(recent)]

    # 1. 加载画像 + 意图分类 + 组装 prompt（失败不落库，无孤儿消息）
    try:
        user_profile = await _load_user_profile(db, user_id)
        intent, task_type, system = await run_orchestrator(user_input, user_profile, conv.summary, user_id=user_id)
    except Exception:
        logger.exception("编排失败: conversation_id=%s", conv.conversation_id)
        yield _sse_error("服务暂不可用，请稍后重试")
        return

    user_message = Message(
        conversation_id=conv.conversation_id,
        role="user",
        content=user_input,
        intent=intent,
    )
    db.add(user_message)
    conv.message_count = (conv.message_count or 0) + 1
    conv.last_message_at = datetime.now(UTC)
    try:
        await db.commit()
    except Exception:
        logger.exception("保存用户消息失败: conversation_id=%s", conv.conversation_id)
        await db.rollback()
        yield _sse_error("消息保存失败，请稍后重试")
        return

    # 2. Agent Loop 生成 + 保存 AI 回复
    try:
        full_content = ""
        try:
            # agent_loop 现在是异步生成器，yield 流式 token 和最终结果
            async for item in agent_loop(
                user_input=user_input,
                system_prompt=system,
                history_messages=history_messages,
                task_type=cast(TaskType, task_type),
                db=db,
                user_id=user_id,
                registry=tool_registry,
            ):
                if isinstance(item, str):
                    # 流式 token，直接 yield 给前端
                    full_content += item
                    yield _sse_token(item, conv.conversation_id)
                elif isinstance(item, AgentResult):
                    # 最终结果
                    result = item
                    # 如果有工具调用，输出提示
                    for step in result.steps:
                        if step.step_type == "tool_call" and step.tool_name:
                            yield _sse_token(f"\n[调用工具: {step.tool_name}]\n", conv.conversation_id)
                    # 保存追踪记录
                    await _save_agent_traces(db, conv.conversation_id, user_id, result.steps)

        finally:
            # 无论正常完成还是客户端断开，都保存已生成的内容
            if full_content:
                db.add(
                    Message(
                        conversation_id=conv.conversation_id,
                        role="assistant",
                        content=full_content,
                        intent=intent,
                    )
                )
                conv.message_count = (conv.message_count or 0) + 1
                conv.last_message_at = datetime.now(UTC)
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.warning("保存 AI 回复失败 (可能为部分): conversation_id=%s", conv.conversation_id)
    except Exception:
        logger.exception("生成 AI 回复失败: conversation_id=%s", conv.conversation_id)
        await db.rollback()
        yield _sse_error("生成回复失败，请稍后重试")
        return

    # 3. 滚动摘要：fire-and-forget，不阻塞 SSE
    if conv.message_count >= 30 and conv.message_count % 10 == 0:
        task = asyncio.create_task(_summarize_bg(conv.conversation_id))
        task.add_done_callback(_log_task_error)

    # 4. Cognee 记忆提取已移除：事件驱动写入，不逐对话提取
    # 成长事件通过 growth_events 表和 cognee_projector 投影到 Cognee

    yield _sse_done(conv.conversation_id)


async def _load_user_profile(db: AsyncSession, user_id: str) -> dict | None:
    """从 DB 加载用户画像（含 nickname）"""
    from app.backend.models.user import User, UserProfile

    user_result = await db.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    return {
        "nickname": user.nickname if user else None,
        "grade": profile.grade,
        "school_name": profile.school_name,
        "major": profile.major,
        "target_direction": profile.target_direction,
        "current_skills": profile.current_skills,
    }


async def _summarize_bg(conversation_id: str) -> None:
    """后台摘要：独立 db session，内部重判触发条件防并发重复触发。"""
    from app.backend.db.base import get_async_session_maker

    async with get_async_session_maker()() as db:
        try:
            conv = await db.get(Conversation, conversation_id)
            if conv is None or conv.message_count < 30 or conv.message_count % 10 != 0:
                return
            await _summarize_and_persist(db, conv)
        except Exception:
            logger.exception("后台摘要失败: conversation_id=%s", conversation_id)


async def _fetch_old_messages(db: AsyncSession, conv: Conversation) -> list[Message]:
    """取窗口外最早 N 条消息（N = 总消息数 - 窗口大小）。"""
    limit = conv.message_count - _SUMMARY_WINDOW
    if limit <= 0:
        return []
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _format_messages(messages: list[Message]) -> str:
    """消息列表 → user: xxx\nassistant: xxx，清洗文件名引用防止 LLM 误读。"""
    import re

    def _clean(content: str) -> str:
        content = re.sub(r"[\[【].*?\.(?:pdf|docx?|png|jpg|txt)[\]】]", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\[PDF\s*\d+\]", "", content, flags=re.IGNORECASE)
        return content

    return "\n".join(
        f"{'user' if msg.role == 'user' else 'assistant'}: {_clean((msg.content or '')[:_MAX_MSG_CHARS])}"
        for msg in messages
    )


def _build_summary_prompt(previous: str, old_text: str) -> str:
    """拼接摘要 prompt；用 replace() 避免用户消息含 { } 时与 format() 冲突。"""
    return _SUMMARIZE_PROMPT.replace("{PREV}", previous or "（新对话）").replace("{MSGS}", old_text)


async def _summarize_and_persist(db: AsyncSession, conv: Conversation) -> None:
    """将窗口外的旧消息压缩为摘要，写入 Conversation.summary。"""
    lock = _summary_locks.setdefault(conv.conversation_id, asyncio.Lock())
    async with lock:
        await db.refresh(conv)
        old_messages = await _fetch_old_messages(db, conv)
        if not old_messages:
            return

        prompt = _build_summary_prompt(conv.summary or "", _format_messages(old_messages))

        try:
            result = await llm_chat(
                task_type="memory_summarize",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=256,
            )
            # llm_chat 可能返回 str 或 dict（如果有 tool_calls），确保处理两种情况
            summary = result if isinstance(result, str) else str(result)
            conv.summary = summary.strip() if summary else None
            await db.commit()
            logger.info("摘要已更新: conversation_id=%s, len=%d", conv.conversation_id, len(summary) if summary else 0)
        except asyncio.CancelledError:
            raise
        except Exception:
            await db.rollback()
            logger.warning("摘要生成失败，保留旧摘要: conversation_id=%s", conv.conversation_id)
        finally:
            # 释放锁引用，防止无限增长
            _summary_locks.pop(conv.conversation_id, None)


def _sse_token(content: str, conversation_id: str) -> str:
    return f"data: {json.dumps({'type': 'token', 'content': content, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"


def _sse_error(message: str) -> str:
    return f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"


def _sse_done(conversation_id: str) -> str:
    return f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"


async def _save_agent_traces(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    steps: list,
) -> None:
    """保存 Agent 执行追踪记录"""
    try:
        for step in steps:
            trace = AgentTrace(
                conversation_id=conversation_id,
                user_id=user_id,
                step_number=step.step_number,
                step_type=step.step_type,
                tool_name=step.tool_name,
                tool_args=step.tool_args,
                content=step.content[:5000],  # 截断过长内容
                duration_ms=step.duration_ms,
                success=step.success,
                error_message=step.error,
            )
            db.add(trace)
        await db.flush()
        logger.debug("Agent 追踪记录已保存: conversation_id=%s, steps=%d", conversation_id, len(steps))
    except Exception:
        logger.warning("保存 Agent 追踪记录失败: conversation_id=%s", conversation_id, exc_info=True)
