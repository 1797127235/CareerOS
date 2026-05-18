"""随记路由 — 基于 GrowthEvent (event_type='quick_note') 实现。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.db import get_async_session_maker
from backend.core.logging import get_logger
from backend.modules.memory.facade import get_memory
from backend.modules.memory.models import GrowthEvent

logger = get_logger(__name__)
router = APIRouter(prefix="/notes", tags=["notes"])


class NoteOut(BaseModel):
    id: str
    content: str
    created_at: datetime
    updated_at: datetime | None


class NoteCreate(BaseModel):
    content: str


class NoteUpdate(BaseModel):
    content: str


def _event_to_note(ev: GrowthEvent) -> NoteOut:
    payload = {}
    if ev.payload_json:
        try:
            payload = json.loads(ev.payload_json)
        except json.JSONDecodeError:
            payload = {}
    content = payload.get("content", "")
    return NoteOut(
        id=ev.id,
        content=content,
        created_at=ev.created_at,
        updated_at=ev.reviewed_at,  # update_event 会更新 reviewed_at
    )


@router.get("", response_model=list[NoteOut])
async def list_notes(user_id: str = Query("demo_user")) -> list[NoteOut]:
    """列出所有随记，按创建时间倒序。"""
    async with get_async_session_maker()() as db:
        stmt = (
            select(GrowthEvent)
            .where(GrowthEvent.user_id == user_id)
            .where(GrowthEvent.event_type == "quick_note")
            .order_by(GrowthEvent.created_at.desc())
        )
        result = await db.execute(stmt)
        events = list(result.scalars().all())
    return [_event_to_note(e) for e in events]


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(body: NoteCreate, user_id: str = Query("demo_user")) -> NoteOut:
    """新建随记。"""
    memory = get_memory()
    async with get_async_session_maker()() as db:
        event = await memory.remember(
            user_id,
            event_type="quick_note",
            payload={"content": body.content},
            source="user",
            db=db,
        )
        await db.commit()
        if event is None:
            # 内容重复（dedup）：查出已有的返回
            stmt = (
                select(GrowthEvent)
                .where(GrowthEvent.user_id == user_id)
                .where(GrowthEvent.event_type == "quick_note")
                .order_by(GrowthEvent.created_at.desc())
                .limit(1)
            )
            result = await db.execute(stmt)
            event = result.scalar_one()
    return _event_to_note(event)


@router.patch("/{note_id}", response_model=NoteOut)
async def update_note(note_id: str, body: NoteUpdate, user_id: str = Query("demo_user")) -> Any:
    """编辑随记内容。"""
    memory = get_memory()
    ok, error = await memory.update_event(user_id, note_id, payload={"content": body.content})
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=error or "随记不存在")

    async with get_async_session_maker()() as db:
        event = await db.get(GrowthEvent, note_id)
    if event is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="随记不存在")
    return _event_to_note(event)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: str, user_id: str = Query("demo_user")) -> None:
    """删除随记。"""
    memory = get_memory()
    success, error = await memory.delete_event(user_id, note_id)
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=error or "随记不存在")
