"""技能成长记录模型"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class SkillRecord(Base):
    """技能成长记录 — 从对话中识别或表单填写，用户确认后入库"""

    __tablename__ = "skill_records"
    __table_args__ = (Index("ix_skill_records_user_skill", "user_id", "skill_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(100))  # 技能名称，如 "Python"、"React"
    proficiency: Mapped[str | None] = mapped_column(String(20))  # 掌握程度：beginner/intermediate/advanced/expert
    context: Mapped[str | None] = mapped_column(Text)  # 来源上下文，如 "课程项目"、"实习经历"
    source: Mapped[str] = mapped_column(String(20), default="form")  # 来源：form（表单）/conversation（对话识别）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
