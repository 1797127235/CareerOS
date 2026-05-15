"""记忆写入层 — 事件写入、单条/批量记录。"""

from __future__ import annotations

from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.memory.models import GrowthEvent
from backend.modules.memory.relational_store import GrowthEventRepository


class EventSpec(TypedDict, total=False):
    event_type: str
    entity_type: str | None
    entity_id: str | None
    payload: dict | None
    source: str


class MemoryWriter:
    """事件写入职责 — 纯写入，无 session 管理，无投影触发。

    db 必须显式传入。commit 和投影同步由 LumenMemory 编排。
    可独立实例化测试写入逻辑。
    """

    async def _write_events(
        self,
        user_id: str,
        events: list[dict] | list[EventSpec],
        db: AsyncSession,
    ) -> list[GrowthEvent]:
        """通用事件写入，仅 flush，不 commit。调用方负责 commit + projections。"""
        repo = GrowthEventRepository(db)
        created: list[GrowthEvent] = []
        for spec in events:
            spec = spec  # type: ignore[assignment]
            event = await repo.create_with_dedup(
                user_id=user_id,
                event_type=spec["event_type"],  # type: ignore[typeddict-item]
                entity_type=spec.get("entity_type"),
                entity_id=spec.get("entity_id"),
                payload=spec.get("payload"),
                source=spec.get("source", "system"),
            )
            if event:
                created.append(event)
        if created:
            await db.flush()
        return created

    async def remember(
        self,
        user_id: str,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: dict | None = None,
        source: str = "system",
        *,
        db: AsyncSession,
    ) -> GrowthEvent | None:
        """写入一条记忆事件（db 必须传入，仅 flush）。"""
        spec: EventSpec = {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "source": source,
        }
        created = await self._write_events(user_id, [spec], db)
        return created[0] if created else None

    async def remember_batch(
        self,
        user_id: str,
        events: list[EventSpec],
        *,
        db: AsyncSession,
    ) -> list[GrowthEvent]:
        """批量写入（db 必须传入，仅 flush）。"""
        specs: list[dict] = [dict(e) for e in events]
        return await self._write_events(user_id, specs, db)
