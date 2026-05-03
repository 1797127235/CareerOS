"""知识库导入流水线 — 编排层

职责：
- 协调 Chunking → DB 写入 → 向量索引
- 事务控制（DB commit + vector index 一致性）
- 错误处理和状态更新

依赖：
- chunk_service（文本切割）
- document_service（DB 操作）
- vector_store（向量索引）

设计原则：
- 唯一连接 DB 和向量库的地方
- 支持重试、幂等、断点续传
"""

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.services.chunk_service import estimate_token_count, split_text
from app.backend.services.document_service import (
    _extract_metadata,
    _map_category,
    create_chunk,
    create_document,
    update_document_status,
)
from app.backend.services.vector_store import get_vector_store

# 数据文件目录
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


async def ingest_document(
    db: AsyncSession,
    title: str,
    content: str,
    category: str | None = None,
    source_type: str = "knowledge_base",
    source_path: str | None = None,
    file_type: str = "json",
    metadata: dict | None = None,
) -> dict:
    """单条文档完整入库：DB + 向量库

    Returns:
        {"document_id": str, "chunk_count": int, "chunk_ids": list[str]}
    """
    # 1. 创建 Document（DB）
    doc = await create_document(
        db=db,
        title=title,
        category=category,
        source_type=source_type,
        source_path=source_path,
        file_type=file_type,
        metadata=metadata,
    )

    try:
        # 2. Chunking（纯函数）
        chunks_text = split_text(content)

        # 3. 创建 Chunk（DB）
        chunk_ids = []
        for idx, chunk_text in enumerate(chunks_text):
            chunk = await create_chunk(
                db=db,
                document_id=doc.id,
                content=chunk_text,
                chunk_index=idx,
                token_count=estimate_token_count(chunk_text),
                metadata={"overlap": 50 if idx > 0 else 0},
            )
            chunk_ids.append(chunk.id)

        # 4. 提交 DB（确保 chunks 先落库）
        await db.commit()

        # 5. 索引到向量库（DB 提交后再索引，避免向量库有数据但 DB 回滚）
        vector_store = get_vector_store()
        metadatas = [
            {
                "document_id": doc.id,
                "chunk_index": idx,
                "category": category,
            }
            for idx in range(len(chunks_text))
        ]
        await vector_store.add(
            ids=chunk_ids,
            texts=chunks_text,
            metadatas=metadatas,
        )

        # 6. 更新文档状态为 indexed
        await update_document_status(db, doc.id, status="indexed", chunk_count=len(chunks_text))
        await db.commit()

        return {
            "document_id": doc.id,
            "chunk_count": len(chunks_text),
            "chunk_ids": chunk_ids,
        }

    except Exception as e:
        # 出错：标记文档状态为 error
        await update_document_status(db, doc.id, status="error", error_message=str(e))
        await db.commit()
        raise


async def ingest_json_file(
    db: AsyncSession,
    file_path: Path,
    source_type: str = "knowledge_base",
) -> list[dict]:
    """批量导入单个 JSON 文件"""
    with open(file_path, encoding="utf-8") as f:
        items = json.load(f)

    results = []
    for item in items:
        result = await ingest_document(
            db=db,
            title=item.get("title", "Untitled"),
            content=item.get("content", ""),
            category=_map_category(item.get("category", "")),
            source_type=source_type,
            source_path=str(file_path.relative_to(DATA_DIR.parent)),
            file_type="json",
            metadata=_extract_metadata(item),
        )
        results.append(result)

    return results


async def ingest_all_data_files(db: AsyncSession) -> dict[str, list[dict]]:
    """一键导入 data/ 目录下所有 JSON 文件

    Returns:
        {文件名: [ingest_document 结果列表]}
    """
    json_files = sorted(DATA_DIR.glob("*.json"))
    results = {}

    for file_path in json_files:
        docs = await ingest_json_file(db, file_path)
        results[file_path.name] = docs

    return results


async def delete_document_with_vectors(
    db: AsyncSession,
    document_id: str,
) -> bool:
    """删除文档及其向量索引"""
    from app.backend.services.document_service import delete_document, get_document_chunks

    # 1. 获取 chunk IDs
    chunks = await get_document_chunks(db, document_id)
    chunk_ids = [c.id for c in chunks]

    # 2. 删除向量索引
    if chunk_ids:
        vector_store = get_vector_store()
        await vector_store.delete(chunk_ids)

    # 3. 删除 DB 记录（级联删除 chunks）
    return await delete_document(db, document_id)
