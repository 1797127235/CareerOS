"""[已废弃] RAG 记忆检索 — LlamaIndex 实现已被 Mem0 替代 (Story 1.1)

此模块保留为空存根，防止旧引用产生 ImportError。
实际记忆功能见 agent/mem0_client.py
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── 向后兼容存根 ──────────────────────────────────────────


class SimpleRAG:
    """已废弃存根：接口保留，操作为空"""

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        logger.warning("SimpleRAG.search() 已废弃，请使用 Mem0 (Story 1.3)")
        return []


def get_rag() -> SimpleRAG:
    return SimpleRAG()


async def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    logger.warning("rag.search() 已废弃，请使用 Mem0 (Story 1.3)")
    return []


def reset_index() -> None:
    logger.warning("rag.reset_index() 已废弃，请使用 POST /api/memory/reset (Story 2.x)")
