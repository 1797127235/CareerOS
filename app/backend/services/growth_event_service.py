"""SQLite 事实源的 GrowthEvent 辅助方法。"""

from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models.growth_event import GrowthEvent

logger = logging.getLogger(__name__)


def _make_payload_hash(payload: dict | None) -> str | None:
    if not payload:
        return None
    content = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _make_dedupe_key(
    event_type: str,
    entity_type: str | None,
    entity_id: str | None,
    payload_hash: str | None,
) -> str:
    raw_key = "|".join(
        [
            event_type or "",
            entity_type or "",
            entity_id or "",
            payload_hash or "",
        ]
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def create_growth_event_with_dedup(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
    source: str = "system",
) -> GrowthEvent | None:
    """创建 GrowthEvent，带 payload 去重。重复则返回 None。"""
    payload_hash = _make_payload_hash(payload)
    dedupe_key = _make_dedupe_key(event_type, entity_type, entity_id, payload_hash)
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None

    event = GrowthEvent(
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
        source=source,
        dedupe_key=dedupe_key,
        payload_hash=payload_hash,
    )

    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
        return event
    except IntegrityError as exc:
        # 只处理 dedupe_key 唯一约束冲突，其它 IntegrityError 不吞掉
        if "dedupe_key" in str(exc.orig) or "uq_growth_events_user_dedupe" in str(exc.orig):
            logger.debug("Skipped duplicate event: user_id=%s, dedupe_key=%s", user_id, dedupe_key)
            return None
        raise
