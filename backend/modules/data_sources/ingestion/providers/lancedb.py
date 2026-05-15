"""LanceDBProvider — DocumentIndexProvider 的 LanceDB 实现。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.core.config import USER_DATA_DIR
from backend.core.logging import get_logger
from backend.modules.data_sources.ingestion.document_index_provider import (
    DocumentIndexProvider,
    HealthStatus,
    ProviderHit,
)

logger = get_logger(__name__)

DEFAULT_TABLE = "lumen_documents"


class LanceDBProvider(DocumentIndexProvider):
    """LanceDB 实现。使用向量索引做语义搜索。

    分块策略：简单 overlap 分块（chunk_size=512, overlap=50）。
    Embedding：使用 sentence-transformers 的 all-MiniLM-L6-v2。
    """

    @classmethod
    def provider_name(cls) -> str:
        return "lancedb"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import lancedb  # noqa: F401
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def __init__(self, db_path: Path | None = None, table_name: str = DEFAULT_TABLE) -> None:
        self._db_path = db_path or (USER_DATA_DIR / "lancedb")
        self._table_name = table_name
        self._db: Any = None
        self._table: Any = None
        self._embedder: Any = None
        self._health: HealthStatus = HealthStatus.NOT_INITIALIZED
        self._error_msg: str = ""

    async def initialize(self) -> None:
        """异步初始化：模型加载和 DB 连接在线程池中执行。"""
        try:
            await asyncio.to_thread(self._blocking_initialize)
            self._health = HealthStatus.READY
        except Exception as exc:
            self._health = HealthStatus.ERROR
            self._error_msg = str(exc)
            logger.error("lancedb.init_failed", error=str(exc))

    def _blocking_initialize(self) -> None:
        """阻塞初始化逻辑（在线程池中执行）。"""
        import lancedb
        from sentence_transformers import SentenceTransformer

        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))
        logger.info("lancedb.loading_embedding_model", model="all-MiniLM-L6-v2")
        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")

        # 创建或打开表
        try:
            self._table = self._db.open_table(self._table_name)
        except Exception:
            # 表不存在，创建（需要至少一条数据定义 schema）
            import pyarrow as pa

            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("doc_id", pa.string()),
                    pa.field("chunk_text", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), 384)),  # MiniLM-L6 输出 384 维
                    pa.field("metadata", pa.string()),
                ]
            )
            self._table = self._db.create_table(self._table_name, schema=schema)
            logger.info("lancedb.table_created", table=self._table_name)

        logger.info("lancedb.initialized", db_path=str(self._db_path))

    async def prefetch(self, query: str) -> list[ProviderHit]:
        """向量召回：query → embedding → ANN search → 结构化结果。

        运行时异常会降级健康状态并返回空列表，避免单次故障拖垮上层搜索。
        """
        if self._table is None or self._embedder is None:
            return []

        try:
            query_vec = (await asyncio.to_thread(self._embedder.encode, query)).tolist()
            results = self._table.search(query_vec).metric("cosine").limit(10).to_list()
            if not results:
                if self._health != HealthStatus.READY:
                    self._health = HealthStatus.READY
                    self._error_msg = ""
                return []

            hits: list[ProviderHit] = []
            for row in results:
                hits.append(
                    ProviderHit(
                        doc_id=row.get("doc_id", "unknown"),
                        content=row.get("chunk_text", "")[:500],
                        score=float(1.0 - row.get("_distance", 1.0)),  # cosine distance → similarity
                        metadata=json.loads(row.get("metadata", "{}")),
                    )
                )
            if self._health != HealthStatus.READY:
                self._health = HealthStatus.READY
                self._error_msg = ""
            return hits
        except Exception as exc:
            self._health = HealthStatus.DEGRADED
            self._error_msg = str(exc)
            logger.error("lancedb.prefetch_failed", error=str(exc))
            return []

    async def sync_document(
        self,
        content: str,
        doc_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """保存文档：分块 → embedding → 写入 LanceDB。

        运行时异常会降级健康状态并重新抛出，供调用方（projection.py）决定重试策略。
        """
        if self._table is None:
            return

        try:
            chunks = self._chunk_text(content)
            if not chunks:
                return

            embeddings = (await asyncio.to_thread(self._embedder.encode, chunks)).tolist()

            rows = []
            for idx, (chunk, vec) in enumerate(zip(chunks, embeddings, strict=False)):
                chunk_id = hashlib.sha256(f"{doc_id}:{idx}:{chunk}".encode()).hexdigest()
                rows.append(
                    {
                        "id": chunk_id,
                        "doc_id": doc_id,
                        "chunk_text": chunk,
                        "vector": vec,
                        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                    }
                )

            # 使用转义的 doc_id 删除旧版本
            safe_id = doc_id.replace("'", "''")
            with contextlib.suppress(Exception):
                self._table.delete(f"doc_id = '{safe_id}'")

            self._table.add(rows)
            if self._health != HealthStatus.READY:
                self._health = HealthStatus.READY
                self._error_msg = ""
            logger.info("lancedb.document_synced", doc_id=doc_id, chunks=len(rows))
        except Exception as exc:
            self._health = HealthStatus.DEGRADED
            self._error_msg = str(exc)
            logger.error("lancedb.sync_failed", doc_id=doc_id, error=str(exc))
            raise

    async def clear(self) -> bool:
        """清空 LanceDB 表。"""
        try:
            if self._table is not None:
                self._db.drop_table(self._table_name, ignore_missing=True)
                self._table = None
            logger.info("lancedb.index_cleared", table=self._table_name)
            return True
        except Exception as exc:
            logger.error("lancedb.clear_failed", error=str(exc))
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """删除指定 doc_id 的所有 chunks。

        单引号转义防止 filter 注入。
        """
        if self._table is None:
            return False
        try:
            safe_id = doc_id.replace("'", "''")
            self._table.delete(f"doc_id = '{safe_id}'")
            if self._health != HealthStatus.READY:
                self._health = HealthStatus.READY
                self._error_msg = ""
            logger.info("lancedb.document_deleted", doc_id=doc_id)
            return True
        except Exception as exc:
            self._health = HealthStatus.DEGRADED
            self._error_msg = str(exc)
            logger.error("lancedb.delete_failed", doc_id=doc_id, error=str(exc))
            return False

    def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
        """语义分块：优先按段落切分，超长段落按句子切分，最后硬截断兜底。

        与简单硬截断不同，语义分块在段落/句子边界处自然保持上下文完整性，
        只在超长句子无法避免时才使用硬截断 + overlap。
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        # 步骤1：按段落切分
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        # 步骤2：段落合并成 chunk（不超过 chunk_size）
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            # 超长段落：先 flush 当前 buffer，然后按句子切分
            if len(para) > chunk_size:
                if current:
                    chunks.append(current)
                    current = ""

                sentences = self._split_sentences(para)
                for sent in sentences:
                    if len(current) + len(sent) < chunk_size:
                        current += " " + sent if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
                continue

            # 正常段落：尝试合并到当前 chunk
            if len(current) + len(para) + 2 < chunk_size:
                current += "\n\n" + para if current else para
            else:
                if current:
                    chunks.append(current)
                current = para

        if current:
            chunks.append(current)

        # 步骤3：任何超过 chunk_size 的 chunk 硬截断兜底（带 overlap）
        final_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) <= chunk_size:
                final_chunks.append(chunk)
            else:
                for i in range(0, len(chunk), chunk_size - overlap):
                    final_chunks.append(chunk[i : i + chunk_size])

        return [c.strip() for c in final_chunks if c.strip()]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """按句子切分，支持中英文标点。"""
        import re

        parts = re.split(r"(?<=[。！？.!?])\s*", text)
        return [p.strip() for p in parts if p.strip()]

    def get_tool_schemas(self) -> list[dict]:
        return [
            {
                "name": "data_source_search",
                "description": "搜索外部数据源中的相关文档（语义搜索）",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            }
        ]

    async def handle_tool_call(self, name: str, args: dict) -> str:
        if name == "data_source_search":
            hits = await self.prefetch(args["query"])
            if not hits:
                return "未找到相关内容。"
            return "\n\n".join(f"[来源: {h.doc_id}]\n{h.content}" for h in hits)
        raise NotImplementedError(f"Tool {name} not supported")

    def health_check(self) -> HealthStatus:
        return self._health

    async def on_session_end(self) -> None:
        """LanceDB 无需 session 级别操作。"""
        pass

    async def shutdown(self) -> None:
        """释放资源。"""
        self._embedder = None
        self._table = None
        self._db = None
        self._health = HealthStatus.NOT_INITIALIZED
        logger.info("lancedb.shutdown")
