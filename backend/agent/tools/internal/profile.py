"""画像工具 — get_profile + update_profile（统一 Tool 接口版）。"""

from __future__ import annotations

import re
from typing import Any

from pydantic_ai import RunContext

from backend.agent.deps import LumenDeps
from backend.agent.tools.base import Tool, ToolResult
from backend.domain.schemas import ProfilePayload
from backend.logging_config import get_logger
from backend.memory import get_memory

logger = get_logger(__name__)


class GetProfileTool(Tool):
    """获取用户画像。通常无需主动调用，画像已在 system prompt 中。"""

    name = "get_profile"
    is_read_only = True
    description = "获取用户完整画像。通常无需主动调用，画像已在 system prompt 中。"

    async def call(self, ctx: RunContext[LumenDeps]) -> ToolResult:
        logger.info("Tool call: get_profile", user_id=ctx.deps.user_id)

        if ctx.deps.build_context_cache.strip():
            return ToolResult.ok(_strip_context_tags(ctx.deps.build_context_cache))

        memory_instance = get_memory()
        context = await memory_instance.build_context(ctx.deps.user_id)
        if context.strip():
            return ToolResult.ok(_strip_context_tags(context))

        return ToolResult.ok("用户画像为空，请先上传简历或手动填写画像。")


class UpdateProfileTool(Tool):
    """更新用户画像。只传有值的字段，传 None 的会被忽略。"""

    name = "update_profile"
    is_read_only = False
    description = (
        "更新用户画像。只传有值的字段。"
        "可用字段: school_name, major, grade, graduation_year, school_level, "
        "target_direction, target_company_level, city, gpa, ranking, awards, bio, "
        "english_level, expected_salary"
    )

    async def call(
        self,
        ctx: RunContext[LumenDeps],
        school_name: str | None = None,
        major: str | None = None,
        grade: str | None = None,
        graduation_year: str | None = None,
        school_level: str | None = None,
        target_direction: str | None = None,
        target_company_level: str | None = None,
        city: str | None = None,
        gpa: str | None = None,
        ranking: str | None = None,
        awards: list[str] | None = None,
        bio: str | None = None,
        english_level: str | None = None,
        expected_salary: str | None = None,
    ) -> ToolResult:
        fields: dict[str, Any] = {}
        for name, val in [
            ("school_name", school_name),
            ("major", major),
            ("grade", grade),
            ("graduation_year", graduation_year),
            ("school_level", school_level),
            ("target_direction", target_direction),
            ("target_company_level", target_company_level),
            ("city", city),
            ("gpa", gpa),
            ("ranking", ranking),
            ("awards", awards),
            ("bio", bio),
            ("english_level", english_level),
            ("expected_salary", expected_salary),
        ]:
            if val is not None:
                fields[name] = val

        if not fields:
            return ToolResult.ok("没有需要更新的字段。")

        allowed_keys = set(ProfilePayload.model_fields.keys())
        known = {k: v for k, v in fields.items() if k in allowed_keys}
        discarded = [k for k in fields if k not in allowed_keys]
        if discarded:
            logger.warning("update_profile discarded unknown keys", discarded=discarded)

        try:
            validated = ProfilePayload.model_validate(known)
        except Exception as e:
            return ToolResult.fail(f"画像字段校验失败：{e}", error_code="VALIDATION_ERROR")

        memory = get_memory()
        event = await memory.remember(
            user_id=ctx.deps.user_id,
            event_type="profile_updated",
            entity_type="profile",
            entity_id="profile_fields",
            payload=validated.model_dump(exclude_none=True),
            source="Agent工具",
            db=ctx.deps.db,
        )
        if event and event.id is not None:
            ctx.deps.pending_event_ids.append(str(event.id))
            ctx.deps.build_context_cache = ""
            updated_keys = ", ".join(validated.model_dump(exclude_none=True).keys())
            return ToolResult.ok(f"画像已更新：{updated_keys}", event_id=str(event.id))

        return ToolResult.ok("画像内容没有变化，跳过更新。")


def _strip_context_tags(text: str) -> str:
    """去除 <memory-context> 包裹标签。"""
    text = re.sub(r"^<memory-context>\n\[System note:[^\]]*\]\n", "", text)
    return text.removesuffix("\n</memory-context>")
