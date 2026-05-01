"""简历"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class Resume(Base):
    __tablename__ = "resumes"

    resume_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    resume_name: Mapped[str | None] = mapped_column(String(100))
    raw_file_url: Mapped[str | None] = mapped_column(String(500))
    raw_file_type: Mapped[str | None] = mapped_column(String(10))  # pdf | doc | docx | image
    parsed_content: Mapped[dict | None] = mapped_column(JSON)
    optimized_content: Mapped[dict | None] = mapped_column(JSON)
    target_direction: Mapped[str | None] = mapped_column(String(50))
    ats_score: Mapped[int | None] = mapped_column(Integer)
    match_jd_id: Mapped[str | None] = mapped_column(String(36))
    match_score: Mapped[int | None] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
