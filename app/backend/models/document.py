"""知识库文档与文本块模型"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.db.base import Base


class DocumentSourceType(StrEnum):
    """文档来源（写入 DB 的取值须与成员值一致）"""

    KNOWLEDGE_BASE = "knowledge_base"
    FILE_UPLOAD = "file_upload"
    EXTERNAL_URL = "external_url"


class DocumentStatus(StrEnum):
    """文档处理状态机"""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    ERROR = "error"


class Document(Base):
    """知识库文档 — 存储原始文档/文件的元数据"""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_user_status", "user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(30), default=DocumentSourceType.KNOWLEDGE_BASE)
    source_path: Mapped[str | None] = mapped_column(String(500))  # 文件路径或 URL，可为空（如纯文本录入）
    category: Mapped[str | None] = mapped_column(
        String(30)
    )  # career_path | skill | learning | interview | industry | resume
    file_type: Mapped[str | None] = mapped_column(String(10))  # pdf | docx | txt | md | json
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 服务层与 chunks 行数保持一致
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    """文档文本块 — 切割后的检索单元"""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")
