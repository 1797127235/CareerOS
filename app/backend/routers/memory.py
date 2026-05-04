"""记忆管理路由 — Mem0 状态查询与重置"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.backend.agent.mem0_client import get_mem0, get_mem0_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryStats(BaseModel):
    status: str  # ready / no_api_key / error / not_initialized
    count: int


class MemoryResetResponse(BaseModel):
    deleted: int


class MemoryItem(BaseModel):
    id: str
    memory: str
    created_at: str | None = None
    categories: list[str] = []


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(user_id: str = Query("demo_user")) -> MemoryStats:
    """查询当前记忆状态和条数"""
    mem0 = get_mem0()
    status = get_mem0_status()

    if mem0 is None:
        return MemoryStats(status=status, count=0)

    try:
        results = await asyncio.to_thread(mem0.get_all, user_id=user_id)
        items = results.get("results", results) if isinstance(results, dict) else results
        return MemoryStats(status=status, count=len(items))
    except Exception as e:
        logger.error("记忆条数查询失败: %s", e)
        return MemoryStats(status=status, count=0)


@router.post("/reset", response_model=MemoryResetResponse)
async def reset_memory(user_id: str = Query("demo_user")) -> MemoryResetResponse:
    """清空指定用户的所有 Mem0 记忆"""
    mem0 = get_mem0()
    if mem0 is None:
        raise HTTPException(status_code=503, detail="记忆服务未就绪")

    try:
        # 先查条数（用于返回 deleted 数量）
        results = await asyncio.to_thread(mem0.get_all, user_id=user_id)
        items = results.get("results", results) if isinstance(results, dict) else results
        count = len(items)

        # 尝试 delete_all（新版 mem0ai），失败则逐条删除（兼容旧版）
        try:
            await asyncio.to_thread(mem0.delete_all, user_id=user_id)
        except AttributeError:
            for item in items:
                if item_id := item.get("id"):
                    await asyncio.to_thread(mem0.delete, item_id)

        logger.info("记忆已重置: user_id=%s, deleted=%d", user_id, count)
        return MemoryResetResponse(deleted=count)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("记忆重置失败: %s", e)
        raise HTTPException(status_code=500, detail="清空失败，请查看日志")


@router.get("/list", response_model=list[MemoryItem])
async def list_memories(user_id: str = Query("demo_user")) -> list[MemoryItem]:
    """返回用户所有记忆条目，按 created_at 倒序"""
    mem0 = get_mem0()
    if mem0 is None:
        return []

    try:
        results = await asyncio.to_thread(mem0.get_all, user_id=user_id)
        items = results.get("results", results) if isinstance(results, dict) else results

        memories: list[MemoryItem] = []
        for item in items:
            memories.append(
                MemoryItem(
                    id=str(item.get("id", "")),
                    memory=item.get("memory", ""),
                    created_at=item.get("created_at"),
                    categories=item.get("categories", []) or [],
                )
            )

        # 按 created_at 倒序（None 排最后）
        memories.sort(key=lambda m: m.created_at or "", reverse=True)
        return memories
    except Exception as e:
        logger.error("记忆列表查询失败: %s", e)
        return []
