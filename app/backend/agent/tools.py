"""Agent 工具注册中心 — ReAct Loop 可调用的工具

工具列表：
- get_profile: 读取用户画像
- update_profile: 从对话中增量更新画像
- diagnose_jd: JD 对比分析
- web_search: 搜索网页获取实时信息（暂未实现，未注册）
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Awaitable[str]]
    requires_db: bool = False


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("工具已注册: %s", tool.name)

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict[str, Any]]:
        """返回 OpenAI function calling 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        db: Any = None,
        user_id: str | None = None,
    ) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具 '{name}'"

        try:
            # 复制参数，避免修改原始 tool_args（会污染 AgentTrace 记录）
            kwargs = dict(arguments)
            if tool.requires_db and db is not None:
                kwargs["db"] = db
            if user_id is not None:
                kwargs["user_id"] = user_id

            result = await tool.handler(**kwargs)
            return str(result)
        except Exception as e:
            logger.error("工具执行失败: %s - %s", name, e, exc_info=True)
            return f"工具执行失败：{e}"


tool_registry = ToolRegistry()


async def _get_profile(user_id: str, db: Any = None) -> str:
    """读取用户画像"""
    if db is None:
        return "错误：数据库未初始化"

    from sqlalchemy import select

    from app.backend.models.user import User, UserProfile

    # 查询画像
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        return "用户画像为空，请先上传简历或手动填写画像。"

    # 查询昵称
    user = await db.get(User, user_id)
    nickname = user.nickname if user else None

    # 组装画像摘要
    parts = []
    if nickname:
        parts.append(f"姓名：{nickname}")
    if profile.school_name:
        parts.append(f"学校：{profile.school_name}（{profile.school_level or '未知'}）")
    if profile.major:
        parts.append(f"专业：{profile.major}")
    if profile.grade:
        grade_map = {
            "freshman": "大一",
            "sophomore": "大二",
            "junior": "大三",
            "senior": "大四",
            "graduate1": "研一",
            "graduate2": "研二",
            "graduate3": "研三",
        }
        parts.append(f"年级：{grade_map.get(profile.grade, profile.grade)}")
    if profile.target_direction:
        parts.append(f"目标方向：{profile.target_direction}")
    if profile.target_company_level:
        level_map = {"top": "大厂", "major": "中厂", "medium": "小厂", "state_owned": "国企"}
        parts.append(f"目标公司：{level_map.get(profile.target_company_level, profile.target_company_level)}")

    skills = profile.current_skills
    if skills and isinstance(skills, list):
        skill_names = [s.get("skill", s.get("name", "")) for s in skills if isinstance(s, dict)]
        if skill_names:
            parts.append(f"技能：{', '.join(skill_names)}")

    # 扩展字段
    pdata = profile.profile_data or {}
    if pdata.get("bio"):
        parts.append(f"简介：{pdata['bio']}")
    if pdata.get("education"):
        edu = pdata["education"]
        if edu.get("gpa"):
            parts.append(f"GPA：{edu['gpa']}")
        if edu.get("awards"):
            parts.append(f"获奖：{', '.join(edu['awards'])}")

    return "\n".join(parts) if parts else "画像数据不完整，请补充信息。"


async def _update_profile(fields: dict[str, Any], user_id: str, db: Any = None) -> str:
    """从对话中增量更新画像

    参数：
        fields: 要更新的字段字典，支持的字段：
            - target_direction: 目标方向（后端/前端/算法/AI等）
            - target_company_level: 目标公司（top/major/medium/state_owned）
            - bio: 个人简介
            - city: 城市
            - expected_salary: 期望薪资
            - english_level: 英语水平
    """
    if db is None:
        return "错误：数据库未初始化"

    from sqlalchemy import select

    from app.backend.models.user import UserProfile
    from app.backend.services.profile_service import _map_direction

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.flush()

    pdata = dict(profile.profile_data or {})
    updated_fields = []

    # target_direction 需要校验合法值
    if "target_direction" in fields and fields["target_direction"] is not None:
        mapped = _map_direction(fields["target_direction"])
        if mapped:
            profile.target_direction = mapped
            updated_fields.append("target_direction")
        else:
            logger.warning("无效的 target_direction: %s", fields["target_direction"])

    # target_company_level 直接写入（枚举值已在 Schema 层校验）
    if "target_company_level" in fields and fields["target_company_level"] is not None:
        profile.target_company_level = fields["target_company_level"]
        updated_fields.append("target_company_level")

    # 扩展字段存入 profile_data
    ext_fields = {"bio", "city", "expected_salary", "english_level"}
    for key in ext_fields:
        if key in fields and fields[key] is not None:
            pdata[key] = fields[key]
            updated_fields.append(key)

    profile.profile_data = pdata
    await db.flush()

    if updated_fields:
        return f"画像已更新：{', '.join(updated_fields)}"
    else:
        return "没有需要更新的字段。"


async def _diagnose_jd(jd_text: str, user_id: str, db: Any = None) -> str:
    """JD 对比分析

    参数：
        jd_text: JD 岗位描述文本
    """
    if db is None:
        return "错误：数据库未初始化"

    from app.backend.services.jd_service import diagnose_jd

    try:
        result = await diagnose_jd(db, user_id, jd_text)

        # 格式化输出
        parts = [
            "【JD 诊断结果】",
            f"岗位：{result.jd_title}",
            f"匹配度：{result.overall_score}/100",
            f"总结：{result.summary}",
        ]

        if result.matched_skills:
            parts.append(f"匹配技能：{', '.join(result.matched_skills)}")

        if result.skill_gaps:
            gaps = [f"{g.skill}（{g.priority}）" for g in result.skill_gaps]
            parts.append(f"技能缺口：{', '.join(gaps)}")

        if result.strengths:
            parts.append(f"优势：{', '.join(result.strengths)}")

        if result.risks:
            parts.append(f"风险：{', '.join(result.risks)}")

        if result.action_plan:
            parts.append("行动计划：")
            for i, plan in enumerate(result.action_plan, 1):
                parts.append(f"  {i}. {plan}")

        return "\n".join(parts)
    except Exception as e:
        logger.error("JD 诊断失败: %s", e)
        return f"JD 诊断失败：{e}"


# TODO: 接入真实的搜索 API（如 DashScope 联网搜索插件、SerpAPI 等）
# def _web_search(query: str) -> str: ...


# 注册工具

tool_registry.register(
    Tool(
        name="get_profile",
        description="读取用户画像，包括学校、专业、技能、目标方向等信息。当需要了解用户背景时调用。",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_get_profile,
        requires_db=True,
    )
)

tool_registry.register(
    Tool(
        name="update_profile",
        description="从对话中增量更新用户画像。当用户提到目标方向、目标公司、个人偏好等信息时调用。",
        parameters={
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": "要更新的字段",
                    "properties": {
                        "target_direction": {
                            "type": "string",
                            "description": "目标方向：后端/前端/算法/AI/测试/运维/安全/客户端/数据/嵌入式/其他",
                        },
                        "target_company_level": {
                            "type": "string",
                            "description": "目标公司：top(大厂)/major(中厂)/medium(小厂)/state_owned(国企)",
                        },
                        "bio": {"type": "string", "description": "个人简介"},
                        "city": {"type": "string", "description": "意向城市"},
                        "expected_salary": {"type": "string", "description": "期望薪资"},
                        "english_level": {"type": "string", "description": "英语水平"},
                    },
                },
            },
            "required": ["fields"],
        },
        handler=_update_profile,
        requires_db=True,
    )
)

tool_registry.register(
    Tool(
        name="diagnose_jd",
        description="诊断用户与 JD 的匹配度。当用户粘贴 JD 或询问岗位匹配情况时调用。",
        parameters={
            "type": "object",
            "properties": {
                "jd_text": {
                    "type": "string",
                    "description": "JD 岗位描述文本",
                },
            },
            "required": ["jd_text"],
        },
        handler=_diagnose_jd,
        requires_db=True,
    )
)

# web_search 工具暂不注册，等接入真实搜索 API 后再启用
