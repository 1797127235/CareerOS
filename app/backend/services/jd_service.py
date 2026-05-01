"""JD 诊断服务 — 画像 + JD → LLM → 结构化诊断"""
from __future__ import annotations
import json
import re
import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.backend.agent.llm_router import chat as llm_chat
from app.backend.models.user import UserProfile
from app.backend.schemas.jd import JDDiagnoseResponse, GapSkill

logger = logging.getLogger(__name__)

_JD_DIAGNOSE_PROMPT = """你是一个技术岗位匹配诊断专家。请根据用户画像和岗位描述(JD)，输出诊断报告。

【用户画像】
{profile_summary}

【岗位描述】
{jd_text}

请返回 JSON，字段如下：
- jd_title: 岗位名称（从JD首行提取，简短）
- overall_score: 综合匹配度 (0-100)
- summary: 一句话总结
- matched_skills: 用户已匹配的技能列表
- skill_gaps: 缺口技能列表，每个含 skill(技能名)、priority(high/medium/low)、suggested_hours(建议学习小时数，可null)
- strengths: 用户优势列表（字符串数组）
- risks: 风险项列表
- resume_tips: 简历改写建议列表
- action_plan: 下一步行动计划列表

评分标准：
- 技能匹配度占 60%
- 项目经验匹配度占 25%
- 学历/背景占 15%
- 如果用户画像为空，评分默认50，gap为空

只输出 JSON，不要解释。"""


async def diagnose_jd(
    db: AsyncSession, user_id: str, jd_text: str
) -> JDDiagnoseResponse:
    """诊断岗位匹配度"""

    # 1. 加载画像
    profile_summary = await _load_profile_summary(db, user_id)

    # 2. LLM 诊断
    prompt = _JD_DIAGNOSE_PROMPT.format(
        profile_summary=profile_summary,
        jd_text=jd_text[:5000],
    )

    try:
        result = await llm_chat(
            task_type="skill_analysis",  # 低温度
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as e:
        logger.exception("LLM 调用失败")
        raise HTTPException(status_code=502, detail=f"AI 诊断失败: {e}")

    # 3. 解析 JSON
    data = _parse_json(result)
    if not data:
        raise HTTPException(status_code=422, detail="LLM 未返回有效诊断结果")

    # 4. 组装响应
    return JDDiagnoseResponse(
        jd_title=data.get("jd_title", ""),
        overall_score=data.get("overall_score", 0),
        summary=data.get("summary", ""),
        matched_skills=data.get("matched_skills", []),
        skill_gaps=[GapSkill(**g) for g in data.get("skill_gaps", []) if isinstance(g, dict)],
        strengths=data.get("strengths", []),
        risks=data.get("risks", []),
        resume_tips=data.get("resume_tips", []),
        action_plan=data.get("action_plan", []),
    )


async def _load_profile_summary(db: AsyncSession, user_id: str) -> str:
    """加载用户画像摘要，供 prompt 使用"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return "（暂无画像数据，请先上传简历建立画像）"

    parts = []
    if profile.school_name:
        parts.append(f"学校：{profile.school_name}（{profile.school_level or '未知'}）")
    if profile.major:
        parts.append(f"专业：{profile.major}")
    if profile.grade:
        grade_map = {
            "freshman": "大一", "sophomore": "大二", "junior": "大三", "senior": "大四",
            "graduate1": "研一", "graduate2": "研二", "graduate3": "研三",
        }
        parts.append(f"年级：{grade_map.get(profile.grade, profile.grade)}")
    if profile.target_direction:
        parts.append(f"目标方向：{profile.target_direction}")
    if profile.target_company_level:
        level_map = {"top": "大厂", "major": "中厂", "medium": "小厂", "state_owned": "国企"}
        parts.append(f"目标公司：{level_map.get(profile.target_company_level, profile.target_company_level)}")

    skills = profile.current_skills
    if skills and isinstance(skills, list):
        skill_names = [
            s.get("skill", s.get("name", "")) for s in skills
            if isinstance(s, dict)
        ]
        if skill_names:
            parts.append(f"技能：{', '.join(skill_names)}")

    return "\n".join(parts)


def _parse_json(text: str) -> dict:
    """鲁棒 JSON 解析"""
    if not text:
        return {}

    # 去除 think/thinking/reasoning tag
    text = re.sub(r"<(think|thinking|reasoning)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 提取 markdown fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    candidate = fence_match.group(1).strip() if fence_match else text.strip()

    # 定位首尾花括号
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        logger.warning("JSON 解析失败，原始输出: %.200s", text)
        return {}
