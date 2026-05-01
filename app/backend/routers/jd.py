"""JD 诊断 API — 岗位描述匹配度诊断"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db.session import get_db
from app.backend.schemas.jd import JDDiagnoseRequest, JDDiagnoseResponse
from app.backend.services.jd_service import diagnose_jd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jd", tags=["jd"])


@router.post("/diagnose", response_model=JDDiagnoseResponse)
async def diagnose(
    req: JDDiagnoseRequest,
    user_id: str = Query("demo_user"),
    db: AsyncSession = Depends(get_db),
):
    """提交一段 JD 文本，返回岗位匹配度诊断报告"""
    try:
        return await diagnose_jd(db, user_id, req.jd_text)
    except Exception:
        logger.exception("JD 诊断失败: user_id=%s", user_id)
        raise
