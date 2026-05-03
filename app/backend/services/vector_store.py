"""向量存储服务 — Chroma 封装接口

职责：
- 连接 Chroma 向量库
- 文本向量化（调用 llm_router.embed）
- 索引增删改查
- 语义检索

不依赖：
- SQLAlchemy
- Document/Chunk 模型
- 数据库会话

设计原则：
- 提供抽象接口，方便后续替换为 Milvus/Weaviate
- 所有操作通过 chunk_id（字符串）与 DB 层关联
"""

from typing import Protocol

import chromadb
from chromadb.api.types import EmbeddingFunction

from app.backend.agent.llm_router import embed

# Chroma 持久化目录
CHROMA_PERSIST_DIR = "./chroma_db"

# Collection 名称
COLLECTION_NAME = "career_os_knowledge"


class VectorStore(Protocol):
    """向量存储抽象接口"""

    async def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> None: ...

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]: ...

    async def delete(self, ids: list[str]) -> None: ...

    async def clear(self) -> None: ...


class ChromaVectorStore:
    """Chroma 向量存储实现"""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_EmbeddingFn(),
        )

    async def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """批量添加文本块到向量库"""
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        """语义检索

        Returns:
            [{"id": str, "text": str, "metadata": dict, "distance": float}]
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filters,
        )

        # 解析结果
        hits = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            hits.append(
                {
                    "id": ids[i],
                    "text": documents[i],
                    "metadata": metadatas[i] or {},
                    "distance": distances[i],
                }
            )

        return hits

    async def delete(self, ids: list[str]) -> None:
        """批量删除"""
        self.collection.delete(ids=ids)

    async def clear(self) -> None:
        """清空 collection"""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_EmbeddingFn(),
        )


class _EmbeddingFn(EmbeddingFunction):
    """Chroma 嵌入函数适配器 — 调用 llm_router.embed"""

    def __call__(self, texts: list[str]) -> list[list[float]]:
        # chromadb 的 EmbeddingFunction 是同步接口
        # 这里需要把 async embed() 转成同步调用
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            # 在已有事件循环中：使用 run_coroutine_threadpool 或 nest_asyncio
            import nest_asyncio

            nest_asyncio.apply()
            return asyncio.run(self._embed_async(texts))
        else:
            return asyncio.run(self._embed_async(texts))

    async def _embed_async(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            emb = await embed(text)
            embeddings.append(emb)
        return embeddings


# 全局单例（懒加载）
_chroma_store: ChromaVectorStore | None = None


def get_vector_store() -> ChromaVectorStore:
    """获取向量存储实例（单例）"""
    global _chroma_store
    if _chroma_store is None:
        _chroma_store = ChromaVectorStore()
    return _chroma_store
