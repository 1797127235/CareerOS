"""记忆管理 API — 路由 + 业务逻辑合一"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_user_id(user_id: str) -> str:
    if not _USER_ID_PATTERN.match(user_id):
        raise HTTPException(status_code=400, detail="user_id 格式无效，只允许字母、数字、下划线和连字符，长度 1-64")
    return user_id


def _get_memory():
    from backend.memory.facade import get_memory

    return get_memory()


# ── 响应模型 ──


class MemoryContent(BaseModel):
    content: str


class MemoryStats(BaseModel):
    status: str
    count: int


class MemoryResetResponse(BaseModel):
    deleted: int
    index_cleared: bool = False


class MemoryItemOut(BaseModel):
    id: str
    memory: str
    created_at: str | None = None
    categories: list[str] = Field(default_factory=list)


# ── 路由 ──


@router.get("/me", response_model=MemoryContent)
async def get_my_memory(user_id: str = Query("demo_user")) -> MemoryContent:
    _validate_user_id(user_id)
    try:
        content = await _get_memory().get_memory_content(user_id)
        return MemoryContent(content=content)
    except Exception:
        logger.exception("Read memory failed: user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="读取画像失败") from None


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(user_id: str = Query("demo_user")) -> MemoryStats:
    _validate_user_id(user_id)
    memory = _get_memory()
    status = memory.cognee_status()
    try:
        count = await memory.count_events(user_id)
    except Exception as exc:
        logger.error("Memory stats count failed: %s", exc)
        count = 0
    return MemoryStats(status=status, count=count)


@router.post("/reset", response_model=MemoryResetResponse)
async def reset_memory(user_id: str = Query("demo_user")) -> MemoryResetResponse:
    _validate_user_id(user_id)
    try:
        result = await _get_memory().reset(user_id)
        return MemoryResetResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory reset failed: %s", exc)
        raise HTTPException(status_code=500, detail="清空失败，请查看日志")


@router.get("/list", response_model=list[MemoryItemOut])
async def list_memories(user_id: str = Query("demo_user")) -> list[MemoryItemOut]:
    _validate_user_id(user_id)
    try:
        items = await _get_memory().list_events(user_id)
    except Exception as exc:
        logger.error("Memory list failed: %s", exc)
        return []
    return [MemoryItemOut(**item) for item in items]


@router.post("/rebuild")
async def rebuild_memory(user_id: str = Query("demo_user")) -> dict:
    _validate_user_id(user_id)
    try:
        result = await _get_memory().rebuild(user_id)
        md_ok = result.get("md_success", False)
        cognee_ok = result.get("cognee_success")
        msg = "重建成功"
        if not md_ok:
            msg = ".md 重建失败"
        elif cognee_ok is False:
            msg = ".md 已重建，但 Cognee 重建失败"
        return {"message": msg, "user_id": user_id, **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory rebuild failed: %s", exc)
        raise HTTPException(status_code=500, detail="重建失败，请查看日志")


@router.get("/search")
async def search_memories(
    user_id: str = Query("demo_user"),
    query: str = Query(...),
    limit: int = Query(10),
) -> list[MemoryItemOut]:
    _validate_user_id(user_id)
    try:
        memory = _get_memory()
        items = await memory.recall(user_id, query, limit=limit)
        return [
            MemoryItemOut(id=item.id, memory=item.content, created_at=item.created_at, categories=item.categories)
            for item in items
        ]
    except Exception as exc:
        logger.error("Memory search failed: %s", exc)
        return []


@router.post("/compensate")
async def compensate_cognee(user_id: str = Query("demo_user")) -> dict:
    _validate_user_id(user_id)
    try:
        fixed = await _get_memory().compensate_cognee(user_id)
        return {"user_id": user_id, "compensated": fixed}
    except Exception as exc:
        logger.error("Cognee compensate failed: %s", exc)
        raise HTTPException(status_code=500, detail="补偿失败")


@router.delete("/{event_id}")
async def delete_memory(event_id: str, user_id: str = Query("demo_user")) -> dict:
    _validate_user_id(user_id)
    try:
        success, error = await _get_memory().delete_event(user_id, event_id)
        if not success:
            status_code = 403 if error and "无权" in error else 404
            raise HTTPException(status_code=status_code, detail=error or "删除失败")
        logger.info("Memory deleted: id=%s, user_id=%s", event_id, user_id)
        return {"deleted": event_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="删除失败")
