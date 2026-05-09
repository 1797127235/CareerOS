"""API 请求/响应模型 & 记忆事件 Payload 类型定义"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════
#  画像 API schemas
# ═══════════════════════════════════════════


class SkillItem(BaseModel):
    name: str
    level: str = "familiar"  # beginner | familiar | intermediate | advanced
    context: str | None = None


class WorkExperienceItem(BaseModel):
    company: str
    role: str
    period: str
    description: str


class ProjectItem(BaseModel):
    title: str
    tech_stack: str | None = None
    role: str | None = None
    period: str
    description: str


class PortfolioLink(BaseModel):
    label: str
    url: str


class ProfileResponse(BaseModel):
    nickname: str | None = None
    school_name: str | None = None
    school_level: str | None = None
    major: str | None = None
    grade: str | None = None
    graduation_year: int | None = None
    target_direction: str | None = None
    target_company_level: str | None = None
    current_skills: list[SkillItem] | None = None
    gpa: str | None = None
    ranking: str | None = None
    awards: list[str] | None = None
    bio: str | None = None
    city: str | None = None
    english_level: str | None = None
    expected_salary: str | None = None
    portfolio_links: list[PortfolioLink] | None = None
    projects: list[ProjectItem] | None = None
    work_experience: list[WorkExperienceItem] | None = None


class ResumeUploadResponse(BaseModel):
    profile: ProfileResponse
    raw_text_preview: str = ""


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
    gpa: str | None = None
    ranking: str | None = None
    awards: list[str] | None = None
    bio: str | None = None
    city: str | None = None
    english_level: str | None = None
    expected_salary: str | None = None
    portfolio_links: list[PortfolioLink] | None = None
    projects: list[ProjectItem] | None = None
    work_experience: list[WorkExperienceItem] | None = None


# ═══════════════════════════════════════════
#  记忆事件 Payload 类型
# ═══════════════════════════════════════════

EventType = Literal[
    "profile_updated",
    "skill_added",
    "skill_level_changed",
    "experience_added",
    "preference_learned",
    "goal_updated",
    "status_changed",
    "decision_made",
]

ENTITY_TYPE_MAP: dict[str, str] = {
    "profile_updated": "profile",
    "skill_added": "skill",
    "skill_level_changed": "skill",
    "experience_added": "experience",
    "preference_learned": "preference",
    "goal_updated": "goal",
    "status_changed": "status",
    "decision_made": "decision",
}


class ProfilePayload(BaseModel):
    school_name: str | None = None
    major: str | None = None
    grade: str | None = None
    graduation_year: str | None = None
    school_level: str | None = None
    target_direction: str | None = None
    target_company_level: str | None = None
    city: str | None = None
    gpa: str | None = None
    ranking: str | None = None
    awards: list[str] | None = None
    bio: str | None = None
    english_level: str | None = None
    expected_salary: str | None = None


class SkillPayload(BaseModel):
    name: str = Field(min_length=1)
    level: Literal["familiar", "proficient", "expert"] = "familiar"
    context: str = ""
    source: str = ""


class ExperiencePayload(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    period: str = ""
    tech_stack: str = ""
    role: str = ""
    source: str = ""


class KeyValuePayload(BaseModel):
    key: str = Field(min_length=1)
    value: str


class DecisionPayload(BaseModel):
    title: str = Field(min_length=1)
    content: str


class FilePayload(BaseModel):
    filename: str
    file_type: Literal["resume", "project", "notes", "generic"]
    file_hash: str = ""
    size_bytes: int = 0
    metadata: dict = Field(default_factory=dict)


EVENT_PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    "profile_updated": ProfilePayload,
    "skill_added": SkillPayload,
    "skill_level_changed": SkillPayload,
    "experience_added": ExperiencePayload,
    "preference_learned": KeyValuePayload,
    "goal_updated": KeyValuePayload,
    "status_changed": KeyValuePayload,
    "decision_made": DecisionPayload,
}
