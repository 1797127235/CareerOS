"""记忆事件 Payload 类型 — 供 events_merger.py 和 agent/tools 使用。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfilePayload(BaseModel):
    nickname: str | None = None
    bio: str | None = None


class KeyValuePayload(BaseModel):
    key: str = Field(min_length=1)
    value: str


class DecisionPayload(BaseModel):
    title: str = Field(min_length=1)
    content: str
