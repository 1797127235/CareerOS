"""聊天工具集 — FunctionToolset 试点。

用 PydanticAI 的 FunctionToolset 包装现有 Tool 实例，
保留完整参数签名（LLM 可见具体参数类型），
并附带使用说明（instructions）。
"""

from __future__ import annotations

from pydantic_ai import FunctionToolset, RunContext  # pyright: ignore[reportMissingImports]

from backend.agent.deps import LumenDeps
from backend.agent.tools.executor import ToolExecutor
from backend.agent.tools.internal.memory_search import MemorySearchTool
from backend.agent.tools.internal.memory_save import MemorySaveTool
from backend.agent.tools.internal.profile import GetProfileTool, UpdateProfileTool

_executor = ToolExecutor()

chat_toolset = FunctionToolset(
    instructions=(
        "核心记忆与画像工具集。\n"
        "- memory_search: 用户询问过去信息、技能、经历时使用\n"
        "- memory_save: 用户透露新信息时主动保存，不要等用户要求\n"
        "- get_profile: 获取用户完整画像（通常已在 system prompt 中）\n"
        "- update_profile: 用户提到学校、专业、目标等画像字段时更新"
    ),
    timeout=10,
)


@chat_toolset.tool
async def memory_search(
    ctx: RunContext[LumenDeps],
    query: str,
    scope: str | None = None,
    search_mode: str = "keyword",
    time_filter: str | None = None,
) -> str:
    """搜索用户记忆。支持 keyword（关键词）和 grep（时间范围）两种模式。

    Args:
        query: 搜索关键词或时间描述
        scope: 搜索范围 — profile / emotions / reference / chat
        search_mode: "keyword"（默认）或 "grep"
        time_filter: 时间过滤 — today / yesterday / recent_7d 等（仅 grep 模式）
    """
    return await _executor.execute(
        MemorySearchTool(),
        ctx,
        query=query,
        scope=scope,
        search_mode=search_mode,
        time_filter=time_filter,
    )


@chat_toolset.tool
async def memory_save(
    ctx: RunContext[LumenDeps],
    entity_type: str,
    section: str,
    content: str,
) -> str:
    """保存记忆。主动调用！不要等用户要求！

    Args:
        entity_type: 类型 — skills / experiences / preferences / goals / decisions / status
        section: 标题/名称
        content: 具体内容
    """
    return await _executor.execute(
        MemorySaveTool(),
        ctx,
        entity_type=entity_type,
        section=section,
        content=content,
    )


@chat_toolset.tool
async def get_profile(ctx: RunContext[LumenDeps]) -> str:
    """获取用户完整画像。通常无需主动调用，画像已在 system prompt 中。"""
    return await _executor.execute(GetProfileTool(), ctx)


@chat_toolset.tool
async def update_profile(
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
) -> str:
    """更新用户画像。只传有值的字段，传 None 的会被忽略。

    Args:
        school_name: 学校名称
        major: 专业
        grade: 年级（大一/大二/大三/大四/研一/研二/研三）
        graduation_year: 毕业年份
        school_level: 学校层次（985/211/双一流/普通本科/专科）
        target_direction: 职业目标方向（如：后端开发/AI算法/前端开发/产品经理）
        target_company_level: 目标公司层次（大厂/中厂/小厂/创业公司/无所谓）
        city: 意向城市
        gpa: GPA
        ranking: 排名
        awards: 获奖列表
        bio: 个人简介
        english_level: 英语水平（CET4/CET6/雅思/托福/无）
        expected_salary: 期望薪资
    """
    return await _executor.execute(
        UpdateProfileTool(),
        ctx,
        school_name=school_name,
        major=major,
        grade=grade,
        graduation_year=graduation_year,
        school_level=school_level,
        target_direction=target_direction,
        target_company_level=target_company_level,
        city=city,
        gpa=gpa,
        ranking=ranking,
        awards=awards,
        bio=bio,
        english_level=english_level,
        expected_salary=expected_salary,
    )
