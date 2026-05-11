"""memory_save 工具 — Agent 主动保存记忆（统一 Tool 接口版）。"""

from __future__ import annotations

from pydantic_ai import RunContext

from backend.agent.deps import LumenDeps
from backend.agent.tools.base import Tool, ToolResult
from backend.domain.schemas import DecisionPayload, ExperiencePayload, KeyValuePayload, SkillPayload
from backend.logging_config import get_logger
from backend.memory import get_memory

logger = get_logger(__name__)

_EVENT_TYPE_MAP: dict[str, str] = {
    "skills": "skill_added",
    "experiences": "experience_added",
    "preferences": "preference_learned",
    "goals": "goal_updated",
    "decisions": "decision_made",
    "status": "status_changed",
}


class MemorySaveTool(Tool):
    """保存记忆。Agent 主动调用，不要等用户要求。"""

    name = "memory_save"
    is_read_only = False
    description = (
        "保存记忆。主动调用！不要等用户要求！"
        "entity_type: skills / experiences / preferences / goals / decisions / status"
    )

    async def call(
        self,
        ctx: RunContext[LumenDeps],
        entity_type: str,
        section: str,
        content: str,
    ) -> ToolResult:
        logger.info("Tool call: memory_save", entity_type=entity_type, section=section)

        if entity_type not in _EVENT_TYPE_MAP:
            return ToolResult.fail(
                f"未知的类型 {entity_type}。支持: {', '.join(_EVENT_TYPE_MAP.keys())}",
                error_code="INVALID_ENTITY_TYPE",
            )

        if entity_type == "skills":
            payload = SkillPayload(name=section, level="familiar", context=content, source="Agent工具").model_dump()
        elif entity_type == "experiences":
            payload = ExperiencePayload(title=section, description=content, source="Agent工具").model_dump()
        elif entity_type == "decisions":
            payload = DecisionPayload(title=section, content=content).model_dump()
        elif entity_type in ("preferences", "goals", "status"):
            payload = KeyValuePayload(key=section, value=content).model_dump()
        else:
            return ToolResult.fail(
                f"不支持的类型 {entity_type}",
                error_code="UNSUPPORTED_TYPE",
            )

        memory = get_memory()
        event = await memory.remember(
            user_id=ctx.deps.user_id,
            event_type=_EVENT_TYPE_MAP[entity_type],
            entity_type=entity_type,
            entity_id=section,
            payload=payload,
            source="Agent工具",
            db=ctx.deps.db,
        )
        if event and event.id is not None:
            ctx.deps.pending_event_ids.append(str(event.id))
            ctx.deps.build_context_cache = ""
            return ToolResult.ok(f"已保存 {entity_type}/{section}", event_id=str(event.id))

        return ToolResult.ok(f"{entity_type}/{section} 内容未变化，跳过")
