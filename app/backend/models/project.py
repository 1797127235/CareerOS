"""项目经历模型"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class Project(Base):
    """项目经历 — 从对话中识别或表单填写，用户确认后入库"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))  # 项目名称
    tech_stack: Mapped[str | None] = mapped_column(Text)  # 技术栈，逗号分隔，如 "Python,FastAPI,React"
    role: Mapped[str | None] = mapped_column(String(100))  # 角色，如 "后端开发"、"全栈"
    period: Mapped[str | None] = mapped_column(String(50))  # 时间段，如 "2024.09 - 2024.12"
    description: Mapped[str | None] = mapped_column(Text)  # 项目描述
    source: Mapped[str] = mapped_column(String(20), default="form")  # 来源：form（表单）/conversation（对话识别）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
