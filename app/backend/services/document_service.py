"""知识库文档服务 — 纯数据库操作，无 Chunking 逻辑

职责：
- Document / Chunk 的增删改查
- 状态管理
- 分类查询

不依赖：
- 向量库
- 文本切割逻辑（由 chunk_service 提供）
"""

from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.backend.models.document import Chunk, Document


def _map_category(raw_category: str) -> str:
    """映射原始 category 到 Document.category 枚举值"""
    mapping = {
        "职位数据": "career_path",
        "面试题库": "interview",
        "技能图谱": "skill",
        "行业报告": "industry",
        "用户案例": "resume",
    }
    return mapping.get(raw_category, "knowledge_base")


def _extract_metadata(item: dict) -> dict:
    """从原始 JSON item 提取 metadata"""
    return {
        "subcategory": item.get("subcategory"),
        "original_title": item.get("title"),
    }


async def create_document(
    db: AsyncSession,
    title: str,
    category: str | None = None,
    source_type: str = "knowledge_base",
    source_path: str | None = None,
    file_type: str = "json",
    metadata: dict | None = None,
) -> Document:
    """创建 Document 记录（不含 chunks）"""
    doc = Document(
        title=title,
        source_type=source_type,
        source_path=source_path,
        category=category,
        file_type=file_type,
        status="processing",
        metadata_json=metadata or {},
    )
    db.add(doc)
    await db.flush()
    return doc


async def create_chunk(
    db: AsyncSession,
    document_id: str,
    content: str,
    chunk_index: int,
    token_count: int | None = None,
    metadata: dict | None = None,
) -> Chunk:
    """创建 Chunk 记录"""
    chunk = Chunk(
        document_id=document_id,
        content=content,
        chunk_index=chunk_index,
        token_count=token_count,
        metadata_json=metadata or {},
    )
    db.add(chunk)
    await db.flush()
    return chunk


async def update_document_status(
    db: AsyncSession,
    document_id: str,
    status: str,
    chunk_count: int | None = None,
    error_message: str | None = None,
) -> None:
    """更新文档状态和元数据"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return

    doc.status = status
    if chunk_count is not None:
        doc.chunk_count = chunk_count
    if error_message is not None:
        doc.error_message = error_message
        from datetime import datetime

        doc.last_error_at = datetime.now(UTC)

    await db.flush()


async def get_document_chunks(
    db: AsyncSession,
    document_id: str,
) -> list[Chunk]:
    """获取指定文档的所有文本块（按 chunk_index 排序）"""
    result = await db.execute(select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index))
    return list(result.scalars().all())


async def get_documents_by_category(
    db: AsyncSession,
    category: str,
) -> list[Document]:
    """按分类获取文档列表"""
    result = await db.execute(
        select(Document).where(Document.category == category).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document_by_id(
    db: AsyncSession,
    document_id: str,
) -> Document | None:
    """根据 ID 获取文档"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def delete_document(
    db: AsyncSession,
    document_id: str,
) -> bool:
    """删除文档（级联删除 chunks）"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return False
    await db.delete(doc)
    await db.flush()
    return True
