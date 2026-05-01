"""JD 诊断历史"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, JSON, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.db.base import Base


class JDDiagnosis(Base):
    __tablename__ = "jd_diagnoses"

    diagnosis_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), index=True)
    jd_text: Mapped[str] = mapped_column(Text)  # 原始 JD 文本，支持重诊断
    jd_title: Mapped[str | None] = mapped_column(String(200))  # 兜底 "未命名 JD"
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
