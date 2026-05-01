"""画像 API 请求/响应模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── 技能条目 ──

class SkillItem(BaseModel):
    name: str
    level: str = "familiar"  # beginner | familiar | intermediate | advanced
    context: str | None = None  # 使用场景，如"课程项目用过"、"竞赛主力语言"


# ── 画像响应 ──

class ProfileResponse(BaseModel):
    nickname: str | None = None
    school_name: str | None = None
    school_level: str | None = None  # 985 | 211 | double_first_class | normal
    major: str | None = None
    grade: str | None = None  # freshman | sophomore | junior | senior | graduate1-3
    graduation_year: int | None = None
    target_direction: str | None = None  # 后端 | 前端 | 算法 | AI | 测试 | 运维 | ...
    target_company_level: str | None = None  # top | major | medium | state_owned
    current_skills: list[SkillItem] | None = None
    # 教育详情（从 profile_data["education"] 合并而来）
    gpa: str | None = None  # 如 "3.8/4.0"
    ranking: str | None = None  # 如 "前10%"
    awards: list[str] | None = None  # 获奖列表


# ── 简历上传响应 ──

class ResumeUploadResponse(BaseModel):
    profile: ProfileResponse
    raw_text_preview: str = ""  # 简历文本前 500 字符，供前端展示确认


# ── 画像局部更新 ──

class ProfileUpdate(BaseModel):
    nickname: str | None = None
    school_name: str | None = None
    school_level: str | None = None
    major: str | None = None
    grade: str | None = None
    graduation_year: int | None = None
    target_direction: str | None = None
    target_company_level: str | None = None
    current_skills: list[SkillItem] | None = None
    # 教育详情（写入 profile_data["education"]）
    gpa: str | None = None
    ranking: str | None = None
    awards: list[str] | None = None
