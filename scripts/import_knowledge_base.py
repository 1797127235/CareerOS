#!/usr/bin/env python3
"""数据导入脚本 — 一键将 data/ 目录下所有 JSON 文件灌入 Chroma 向量库 + Document/Chunk 表

用法:
    python scripts/import_knowledge_base.py

环境:
    需要 DATABASE_URL 环境变量（或 .env 文件）
"""

import asyncio
import json
import sys
from pathlib import Path

# 将项目根目录加入路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.backend.agent.rag import ingest_knowledge_base
from app.backend.config import get_settings
from app.backend.db.base import Base
from app.backend.services.chunk_service import estimate_token_count, split_text
from app.backend.services.document_service import (
    _extract_metadata,
    _map_category,
    create_chunk,
    create_document,
    update_document_status,
)

DATA_DIR = project_root / "data"


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Phase 1: Chroma 向量库（LlamaIndex 自动处理 chunking + embedding）
    doc_count = ingest_knowledge_base(DATA_DIR)

    # Phase 2: SQL 审计库（Document + Chunk 元数据）
    async with async_session() as db:
        for fp in sorted(DATA_DIR.glob("*.json")):
            items = json.loads(fp.read_text(encoding="utf-8"))
            for item in items:
                doc = await create_document(
                    db=db,
                    title=item.get("title", "Untitled"),
                    category=_map_category(item.get("category", "")),
                    source_type="knowledge_base",
                    source_path=str(fp.relative_to(project_root)),
                    file_type="json",
                    metadata=_extract_metadata(item),
                )
                chunks_text = split_text(item.get("content", ""))
                for idx, ct in enumerate(chunks_text):
                    await create_chunk(
                        db=db,
                        document_id=doc.id,
                        content=ct,
                        chunk_index=idx,
                        token_count=estimate_token_count(ct),
                    )
                await update_document_status(db, doc.id, status="indexed", chunk_count=len(chunks_text))
        await db.commit()

    print(f"{doc_count} 文档导入完成（Chroma 向量库 + SQL 审计库）")


if __name__ == "__main__":
    asyncio.run(main())
