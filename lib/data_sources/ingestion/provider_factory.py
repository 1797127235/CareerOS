"""DocumentIndexProvider 工厂 — 根据用户配置创建 Provider 实例。"""

from __future__ import annotations

from core.config import load_user_config
from lib.data_sources.ingestion.document_index_provider import DocumentIndexProvider
from lib.data_sources.ingestion.providers.null import NullProvider
from shared.logging import get_logger

logger = get_logger(__name__)

_PROVIDER_REGISTRY: dict[str, type[DocumentIndexProvider]] = {}


def _register_providers() -> None:
    """注册内置 Provider（仅 LanceDB + Null）。"""
    from lib.data_sources.ingestion.providers.lancedb import LanceDBProvider

    _PROVIDER_REGISTRY["lancedb"] = LanceDBProvider
    _PROVIDER_REGISTRY["null"] = NullProvider


async def create_document_index_provider(config: dict | None = None) -> DocumentIndexProvider:
    """根据用户配置创建 DocumentIndexProvider 实例。

    从 config.json 读取 document_index_provider 字段决定创建哪种 Provider。
    降级逻辑：无效值 / LanceDB 依赖不可用 → NullProvider。
    """
    if not _PROVIDER_REGISTRY:
        _register_providers()

    user_config = config or load_user_config()
    backend = user_config.get("document_index_provider", "lancedb")

    if backend == "disabled":
        backend = "null"

    provider_cls = _PROVIDER_REGISTRY.get(backend)
    if not provider_cls:
        logger.warning(f"Unknown provider '{backend}', falling back to null")
        provider_cls = NullProvider

    # LanceDB 依赖不可用时降级
    if backend == "lancedb" and not provider_cls.is_available():
        logger.warning("LanceDB dependencies not available, falling back to null")
        provider_cls = NullProvider

    provider = provider_cls()
    await provider.initialize()
    logger.info("document_index_provider.initialized", provider=provider.name)
    return provider
