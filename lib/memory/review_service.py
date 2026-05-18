"""后台记忆审查服务。

当 Agent 在对话中未主动保存记忆时，后台 fork Agent 审查本轮对话，
判断是否有值得保存的用户信息。
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)

_REVIEW_PROMPT = (
    "审查上一轮对话，判断是否包含值得保存的用户信息。\n\n"
    "重点关注：\n"
    "1. 用户是否透露了关于自己的新信息（目标、技能、经历、偏好、状态、决策）？\n"
    "2. 用户是否纠正了你、表达了偏好、或做出了决策？\n"
    "3. 对话中是否有值得记录的洞察、反思或笔记？如有，用 entity_type='note' 保存。\n\n"
    "如果有值得保存的信息，调用 memory_save 或 update_profile 保存。\n"
    "如果没有任何新信息，回复「无需保存」。\n\n"
    "【对话】\n"
    "用户：{user_message}\n\n"
    "助手：{assistant_response}"
)


async def background_memory_review(
    user_id: str,
    user_message: str,
    assistant_response: str,
    conversation_id: str,
) -> None:
    """后台审查本轮对话，判断是否有值得保存的记忆。

    审查 Agent 写入的事件只触发 .md 投影 + 缓存失效，不触发
    _update_understanding（主对话的 persist_turn 已处理），避免递归链。
    """
    try:
        from core.db import get_async_session_maker
        from lib.agent.deps import LumenDeps
        from lib.agent.pydantic_agent import get_agent

        async with get_async_session_maker()() as db:
            agent = get_agent()
            deps = LumenDeps(
                user_id=user_id,
                db=db,
                conversation_id=conversation_id,
                current_user_input=user_message,
            )

            prompt = _REVIEW_PROMPT.format(
                user_message=user_message,
                assistant_response=assistant_response,
            )

            await agent.run(prompt, deps=deps)

            await db.commit()

            if deps.pending_event_ids:
                from lib.memory.markdown import sync_user_md_projection
                from lib.memory.snapshot import invalidate_cache

                await sync_user_md_projection(user_id)
                await invalidate_cache(user_id)
                logger.info(
                    "后台审查已保存 %d 条记忆",
                    len(deps.pending_event_ids),
                    conversation_id=conversation_id,
                )
    except Exception:
        logger.exception("后台记忆审查失败", conversation_id=conversation_id)
