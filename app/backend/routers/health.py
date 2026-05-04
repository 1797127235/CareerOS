"""健康检查"""

from fastapi import APIRouter

from app.backend.agent.mem0_client import get_mem0_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0", "mem0": get_mem0_status()}
