"""对话 API 测试"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_history(client: AsyncClient):
    """对话历史接口"""
    r = await client.get("/api/chat/history", params={"user_id": "test_user", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
