"""Vector store 基础设施出口。

所有需要访问 DocumentIndexProvider 的模块应从此处 import，
而不是直接引用 lib.data_sources.ingestion。

具体实现仍住在 data_sources/ingestion/，此文件只做统一出口。
"""

from lib.data_sources.ingestion.document_index_provider import (
    DocumentIndexProvider,
    HealthStatus,
    ProviderHit,
)
from lib.data_sources.ingestion.pipeline import get_document_index_provider
from lib.data_sources.ingestion.providers.null import NullProvider

__all__ = [
    "DocumentIndexProvider",
    "HealthStatus",
    "NullProvider",
    "ProviderHit",
    "get_document_index_provider",
]
