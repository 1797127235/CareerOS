"""SQLAlchemy ORM 模型: User, UserProfile, Conversation, Message, GrowthEvent, AgentTrace"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(100), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    user_type: Mapped[str] = mapped_column(String(30), default="student")
    privacy_level: Mapped[str] = mapped_column(String(10), default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[UserProfile | None] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    profile_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), unique=True)
    school_name: Mapped[str | None] = mapped_column(String(100))
    school_level: Mapped[str | None] = mapped_column(String(30))
    major: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[str | None] = mapped_column(String(20))
    graduation_year: Mapped[int | None] = mapped_column()
    target_direction: Mapped[str | None] = mapped_column(String(50))
    target_company_level: Mapped[str | None] = mapped_column(String(20))
    current_skills: Mapped[list | None] = mapped_column(JSON)
    profile_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    available_time_daily: Mapped[int | None] = mapped_column()
    personality_tags: Mapped[dict | None] = mapped_column(JSON)
    learning_style: Mapped[str | None] = mapped_column(String(20))
    anxiety_level: Mapped[int | None] = mapped_column()
    preferred_interaction: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    topic_type: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="active")
    context_snapshot: Mapped[dict | None] = mapped_column(JSON)
    message_count: Mapped[int] = mapped_column(default=0)
    is_pinned: Mapped[bool] = mapped_column(default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    pydantic_messages: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list[Message]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.conversation_id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(20), default="text")
    card_type: Mapped[str | None] = mapped_column(String(50))
    card_payload: Mapped[dict | None] = mapped_column(JSON)
    intent: Mapped[str | None] = mapped_column(String(50))
    sentiment: Mapped[float | None] = mapped_column(Float)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(String(50))
    feedback_rating: Mapped[int | None] = mapped_column(Integer)
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class GrowthEvent(Base):
    __tablename__ = "growth_events"
    __table_args__ = (
        Index("ix_growth_events_user_event", "user_id", "event_type"),
        Index("ix_growth_events_user_entity", "user_id", "entity_type", "entity_id"),
        Index("ix_growth_events_dedupe", "user_id", "dedupe_key"),
        Index("ix_growth_events_unprojected_md", "user_id", "projected_md_at"),
        Index("ix_growth_events_unprojected_cognee", "user_id", "projected_cognee_at"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_growth_events_user_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="user主动")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    projected_md_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    projected_cognee_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<GrowthEvent {self.event_type} user={self.user_id} at {self.created_at}>"


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(20))
    tool_name: Mapped[str | None] = mapped_column(String(50))
    tool_args: Mapped[dict | None] = mapped_column(JSON)
    tool_result: Mapped[str | None] = mapped_column(String(5000))
    content: Mapped[str] = mapped_column(String(5000))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AgentTrace {self.id} step={self.step_number} type={self.step_type}>"


__all__ = [
    "AgentTrace",
    "Conversation",
    "GrowthEvent",
    "Message",
    "User",
    "UserProfile",
]
