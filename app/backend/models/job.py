"""求职记录与面试记录"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class JobApplication(Base):
    __tablename__ = "job_applications"

    application_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    company_name: Mapped[str] = mapped_column(String(100))
    company_type: Mapped[str | None] = mapped_column(
        String(20)
    )  # top | major | medium | state_owned | startup
    position_name: Mapped[str] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    jd_text: Mapped[str | None] = mapped_column(Text)
    jd_parsed: Mapped[dict | None] = mapped_column(JSON)
    channel: Mapped[str | None] = mapped_column(
        String(20)
    )  # official | referral | boss | zhaopin | others
    referrer_name: Mapped[str | None] = mapped_column(String(50))
    resume_id: Mapped[str | None] = mapped_column(String(36))
    current_stage: Mapped[str] = mapped_column(
        String(20), default="applied"
    )
    # applied | screening | written_test | 1st_interview | 2nd_interview
    # | 3rd_interview | hr_interview | oc | rejected | withdrew | accepted
    stage_history: Mapped[dict | None] = mapped_column(JSON)
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # high | medium | low
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_event_type: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InterviewRecord(Base):
    __tablename__ = "interview_records"

    record_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    round_number: Mapped[int] = mapped_column(default=1)
    round_type: Mapped[str | None] = mapped_column(
        String(20)
    )  # phone | online_1st | online_2nd | online_3rd | onsite | hr
    interview_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    questions_asked: Mapped[dict | None] = mapped_column(JSON)
    performance_rating: Mapped[int | None] = mapped_column(Integer)
    difficulty_rating: Mapped[int | None] = mapped_column(Integer)
    key_takeaways: Mapped[str | None] = mapped_column(Text)
    weaknesses_found: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[str | None] = mapped_column(
        String(20)
    )  # pending | passed | rejected | no_show
    feedback_from_company: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
