"""Agent 编排引擎 — Skill 自发现 + 意图分类 + Prompt 组装"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import yaml

from app.backend.agent.llm_router import get_model, _get_client, TaskType

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent / "skills"


@dataclass(frozen=True, slots=True)
class SkillMeta:
    intent: str
    name: str
    description: str
    task_type: str
    body: str


_skills_cache: dict[str, SkillMeta] | None = None


def discover_skills() -> dict[str, SkillMeta]:
    """扫描 skills/ 目录，解析 SKILL.md frontmatter，返回 intent → SkillMeta 映射。"""
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache

    skills: dict[str, SkillMeta] = {}
    if not _SKILLS_DIR.exists():
        _skills_cache = skills
        return skills

    for subdir in sorted(_SKILLS_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        md_path = subdir / "SKILL.md"
        if not md_path.exists():
            continue

        try:
            content = md_path.read_text(encoding="utf-8")
            meta, body = _parse_skill_md(content)
        except Exception as e:
            logger.warning("解析 SKILL.md 失败: %s — %s", md_path, e)
            continue

        intent = subdir.name
        skills[intent] = SkillMeta(
            intent=intent,
            name=meta.get("name", intent),
            description=meta.get("description", ""),
            task_type=meta.get("task_type", "general_chat"),
            body=body,
        )

    _skills_cache = skills
    return skills


def _parse_skill_md(text: str) -> tuple[dict, str]:
    """提取 YAML frontmatter + 正文。"""
    if not text.startswith("---"):
        return {}, text.strip()

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}

    body = parts[2].strip()
    return meta, body


def _sanitize_summary(text: str) -> str:
    """清洗摘要中的文件引用，防止 LLM 误认为需要读取文件。"""
    # 去掉 PDF/DOCX 文件名引用
    text = re.sub(r'[\[【].*?\.(?:pdf|docx?|png|jpg|txt)[\]】]', '', text, flags=re.IGNORECASE)
    # 去掉 "[PDF N]" 格式的引用标记
    text = re.sub(r'\[PDF\s*\d+\]', '', text, flags=re.IGNORECASE)
    return text


# ── 意图分类 ──
def _validate_task_type(raw: str) -> TaskType:
    """确保 task_type 是 TaskType 字面量，否则回退到 general_chat。"""
    valid = TaskType.__args__  # type: ignore[attr-defined]
    return cast(TaskType, raw if raw in valid else "general_chat")


async def classify(user_input: str) -> tuple[str, TaskType]:
    """输入文本 → 返回 (intent, task_type)。"""
    skills = discover_skills()
    if not skills:
        return "consultation", _validate_task_type("general_chat")

    intent = await _classify_llm(user_input, skills)
    skill = skills.get(intent)
    if skill is None:
        # fallback：前缀匹配
        for key in skills:
            if key in intent or intent in key:
                skill = skills[key]
                break
        if skill is None:
            skill = skills.get("consultation") or next(iter(skills.values()))
    return skill.intent, _validate_task_type(skill.task_type)


async def _classify_llm(user_input: str, skills: dict[str, SkillMeta]) -> str:
    client = _get_client()

    lines = [
        "你是一个意图分类器。根据用户输入，从以下意图中选一个，只输出意图名称（英文），不要解释。\n",
        "意图类型：",
    ]
    for intent, skill in skills.items():
        lines.append(f"- {intent}：{skill.description}")
    lines.append(f"\n用户输入：{user_input}")
    lines.append("输出（只输出一个词）：")

    response = await client.chat.completions.create(
        model=get_model("general_chat"),
        messages=[{"role": "user", "content": "\n".join(lines)}],
        temperature=0.0,
        max_tokens=20,
    )

    content = response.choices[0].message.content if response.choices else None
    if content is None:
        return "consultation"
    return content.strip().lower().replace("-", "_")


# ── Prompt 组装 ──


def build_system_prompt(
    user_profile: dict | None,
    intent: str,
    conversation_summary: str | None = None,
) -> str:
    """组装系统提示词。"""
    skills = discover_skills()
    skill = skills.get(intent)

    parts = [
        "你是「码路领航」职业规划学长 Agent，一名研二计算机学长，在大厂实习过。",
        f"今天是 {date.today().isoformat()}。涉及市场行情、薪资、技术栈热度时，请基于这个时间点判断。",
        "风格：亲切、有干货、用大白话讲技术、不装腔作势。",
        "回答格式：【一句话总结】→ 详细解释 → 个性化建议 → 下一步行动。",
    ]

    if user_profile:
        p = user_profile
        nickname = p.get("nickname") or "同学"
        grade = p.get("grade") or ""
        school = p.get("school_name") or ""
        major = p.get("major") or ""
        target = p.get("target_direction") or "未设定"

        bg_parts = []
        if grade:
            bg_parts.append(grade)
        if school:
            bg_parts.append(school)
        if major:
            bg_parts.append(major)

        bg_line = f"【用户背景】{nickname}"
        if bg_parts:
            bg_line += f"，{'、'.join(bg_parts)}"
        bg_line += f"\n目标方向：{target}"
        parts.append(bg_line)

        skills_data = p.get("current_skills")
        if skills_data and isinstance(skills_data, list):
            names = [
                s.get("skill", "")
                for s in skills_data
                if isinstance(s, dict) and s.get("skill")
            ]
            if names:
                parts.append(f"已掌握技能：{'、'.join(names)}")

        # ⚠️ 画像仅供参考，不要强行关联
        parts.append(
            "以上是用户画像。如果用户当前问题与画像内容无关（例如换了话题、"
            "问的是行业趋势而非个人情况），不要强行关联画像，直接回答问题。"
        )

    if conversation_summary:
        summary = _sanitize_summary(conversation_summary[:500])
        parts.append(f"【对话摘要】{summary}")

    if skill and skill.body:
        parts.append(f"\n{skill.body}")
    elif skill and skill.description:
        parts.append(f"\n当前任务：{skill.description}")

    return "\n".join(parts)


# ── 统一入口 ──


async def run_orchestrator(
    user_input: str,
    user_profile: dict | None,
    conversation_summary: str | None = None,
) -> tuple[str, TaskType, str]:
    """
    一次调用完成：分类 + 加载 skill + 组装 prompt。
    返回: (intent, task_type, system_prompt)
    """
    intent, task_type = await classify(user_input)
    system = build_system_prompt(user_profile, intent, conversation_summary)
    return intent, task_type, system
