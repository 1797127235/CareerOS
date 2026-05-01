"""学习路径、路径节点、能力评估"""

import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, func, JSON, Text, Integer, Date, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class LearningPath(Base):
    __tablename__ = "learning_paths"

    path_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_id: Mapped[str | None] = mapped_column(String(36))
    path_name: Mapped[str | None] = mapped_column(String(100))
    target_role: Mapped[str | None] = mapped_column(String(100))
    target_company: Mapped[str | None] = mapped_column(String(100))
    current_level: Mapped[str | None] = mapped_column(String(50))
    total_duration_days: Mapped[int | None] = mapped_column(Integer)
    daily_time_hours: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft | active | paused | completed | abandoned
    progress_percent: Mapped[int] = mapped_column(default=0)
    completed_nodes: Mapped[int] = mapped_column(default=0)
    total_nodes: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    is_auto_adjusted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PathNode(Base):
    __tablename__ = "path_nodes"

    node_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    path_id: Mapped[str] = mapped_column(String(36), index=True)
    node_name: Mapped[str] = mapped_column(String(200))
    node_type: Mapped[str] = mapped_column(
        String(20)
    )  # knowledge | practice | project | quiz | milestone
    stage_number: Mapped[int | None] = mapped_column(Integer)
    stage_name: Mapped[str | None] = mapped_column(String(100))
    sequence_order: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    estimated_hours: Mapped[int | None] = mapped_column(Integer)
    resource_refs: Mapped[dict | None] = mapped_column(JSON)
    prerequisite_nodes: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(20), default="locked"
    )  # locked | unlocked | in_progress | completed | skipped
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_notes: Mapped[str | None] = mapped_column(Text)
    quiz_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SkillAssessment(Base):
    __tablename__ = "skill_assessments"

    assessment_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_id: Mapped[str | None] = mapped_column(String(36))
    target_role: Mapped[str | None] = mapped_column(String(100))
    target_jd_text: Mapped[str | None] = mapped_column(Text)
    assessment_type: Mapped[str] = mapped_column(
        String(20), default="self_rating"
    )  # self_rating | quiz | comprehensive
    dimension_scores: Mapped[dict | None] = mapped_column(JSON)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    match_percentage: Mapped[int | None] = mapped_column(Integer)
    gap_analysis: Mapped[dict | None] = mapped_column(JSON)
    radar_chart_data: Mapped[dict | None] = mapped_column(JSON)
    generated_path_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
