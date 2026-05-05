"""GrowthEvent — 成长事件表，SQLite 真相层的核心表"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class GrowthEvent(Base):
    """成长事件：记录用户的所有成长轨迹

    这是 SQLite 真相层的核心表，所有成长轨迹都从这里投影到 Cognee。
    事件驱动写入，不是逐对话提取。
    """

    __tablename__ = "growth_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        # "profile_updated" | "skill_added" | "skill_level_changed" |
        # "target_created" | "target_status_changed" |
        # "reflection_added" | "project_added" | "resume_uploaded"
    )
    entity_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        # "profile" | "skill" | "target" | "reflection" | "project"
    )
    entity_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        # 关联实体的 ID
    )
    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # 事件详情的 JSON 字符串
    )
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="user主动",
        # "user主动" | "对话识别" | "简历提取" | "系统产出"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<GrowthEvent {self.event_type} user={self.user_id} at {self.created_at}>"
