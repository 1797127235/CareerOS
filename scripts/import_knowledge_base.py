#!/usr/bin/env python3
"""数据导入脚本 — 一键将 data/ 目录下所有 JSON 文件灌入 Document/Chunk 表 + Chroma 向量库

用法:
    python scripts/import_knowledge_base.py

环境:
    需要 DATABASE_URL 环境变量（或 .env 文件）
"""

import asyncio
import sys
from pathlib import Path

# 将项目根目录加入路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.backend.config import get_settings
from app.backend.db.base import Base
from app.backend.services.ingestion_pipeline import ingest_all_data_files


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 确保表已创建
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        results = await ingest_all_data_files(session)

        total_docs = sum(len(docs) for docs in results.values())
        total_chunks = sum(sum(d["chunk_count"] for d in docs) for docs in results.values())

        print("=" * 50)
        print("知识库导入完成")
        print("=" * 50)
        for filename, docs in results.items():
            chunk_count = sum(d["chunk_count"] for d in docs)
            print(f"  {filename:20s} → {len(docs):3d} 文档, {chunk_count:4d} 块")
        print("-" * 50)
        print(f"  总计: {total_docs} 文档, {total_chunks} 块")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
