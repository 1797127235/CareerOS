"""RAG 知识库检索 — 基于 LlamaIndex + Chroma + DashScope

架构：
- 向量化：DashScopeEmbedding (text-embedding-v4)
- 向量库：ChromaVectorStore (PersistentClient)
- 切割：SentenceSplitter
- 索引：VectorStoreIndex
- 检索：as_retriever()
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import chromadb
from llama_index.core import Document as LlamaDocument
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.backend.config import get_settings

# 配置
DATA_DIR = Path(__file__).parents[3] / "data"
CHROMA_DIR = "./chroma_db"
COLLECTION = "career_os_knowledge"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 50

# 全局单例（懒加载）
_retriever = None
_vector_store = None
_settings_done = False


def _ensure_settings() -> None:
    """配置 LlamaIndex 全局设置（仅首次调用）"""
    global _settings_done
    if _settings_done:
        return
    cfg = get_settings()
    Settings.embed_model = DashScopeEmbedding(
        model_name="text-embedding-v4",
        api_key=cfg.dashscope_api_key,
    )
    _settings_done = True


def _get_vector_store() -> ChromaVectorStore:
    """获取或创建 Chroma vector store"""
    global _vector_store
    if _vector_store is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_or_create_collection(COLLECTION)
        _vector_store = ChromaVectorStore(chroma_collection=collection)
    return _vector_store


def _get_retriever():
    """获取检索器（懒加载）"""
    global _retriever
    _ensure_settings()
    if _retriever is None:
        vs = _get_vector_store()
        index = VectorStoreIndex.from_vector_store(vs)
        _retriever = index.as_retriever(similarity_top_k=5)
    return _retriever


# ─── 公开 API ─────────────────────────────────────────────


def ingest_knowledge_base(data_dir: Path = DATA_DIR) -> int:
    """一键导入：加载 data/*.json → Chunking → 向量化 → Chroma

    Returns: 导入的文档数
    """
    global _retriever
    _ensure_settings()

    # 1. 加载 JSON → LlamaIndex Document
    ldocs = []
    for fp in sorted(data_dir.glob("*.json")):
        items = json.loads(fp.read_text(encoding="utf-8"))
        for item in items:
            ldocs.append(
                LlamaDocument(
                    text=item.get("content", ""),
                    metadata={
                        "title": item.get("title", ""),
                        "category": item.get("category", ""),
                        "subcategory": item.get("subcategory", ""),
                        "source_file": fp.name,
                    },
                )
            )

    # 2. Chunking + 向量化 + 写入 Chroma
    vs = _get_vector_store()
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP),
        ],
        vector_store=vs,
    )
    pipeline.run(documents=ldocs)

    # 3. 刷新 retriever
    index = VectorStoreIndex.from_vector_store(vs)
    _retriever = index.as_retriever(similarity_top_k=5)

    return len(ldocs)


async def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """语义检索 — 返回 top_k 条匹配的文本块"""
    retriever = _get_retriever()
    retriever.similarity_top_k = top_k
    nodes = retriever.retrieve(query)

    return [
        {
            "content": node.text,
            "title": node.metadata.get("title", ""),
            "category": node.metadata.get("category", ""),
            "score": round(node.score or 0, 4),
        }
        for node in nodes
    ]


def reset_index() -> None:
    """清空向量库并重置 retriever"""
    global _retriever, _vector_store
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    with contextlib.suppress(Exception):
        client.delete_collection(COLLECTION)
    _vector_store = None
    _retriever = None


# ─── 向后兼容别名 ─────────────────────────────────────────


class SimpleRAG:
    """向后兼容适配器：对外暴露与旧版一致的 search() 接口"""

    def __init__(self) -> None:
        _ensure_settings()

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return await search(query, top_k)


def get_rag() -> SimpleRAG:
    return SimpleRAG()


def init_rag(kb_path: str | None = None) -> None:
    """初始化 RAG（首次调用时加载 data/ 目录）"""
    global _retriever
    if kb_path:
        data_dir = Path(kb_path) if Path(kb_path).is_dir() else Path(kb_path).parent
    else:
        data_dir = DATA_DIR
    # 如果 Chroma 为空，执行首次导入
    _ensure_settings()
    vs = _get_vector_store()
    if vs._collection.count() == 0:
        ingest_knowledge_base(data_dir)
    else:
        _get_retriever()  # 加载已有索引
