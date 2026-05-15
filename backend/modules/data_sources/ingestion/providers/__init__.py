"""DocumentIndexProvider 内置实现。"""

from __future__ import annotations

from backend.modules.data_sources.ingestion.providers.lancedb import LanceDBProvider
from backend.modules.data_sources.ingestion.providers.null import NullProvider

__all__ = ["LanceDBProvider", "NullProvider"]
