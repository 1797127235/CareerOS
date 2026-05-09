"""文件系统存储 — 原始档案的真相源。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.config import USER_DATA_DIR
from backend.logging_config import get_logger

logger = get_logger(__name__)


class DocumentStore:
    def __init__(self) -> None:
        self._base_dir = USER_DATA_DIR / "files"

    def _ensure_dir(self, user_id: str, doc_type: str) -> Path:
        path = self._base_dir / user_id / doc_type
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, user_id: str, doc_type: str, filename: str, content: bytes) -> str:
        dir_path = self._ensure_dir(user_id, doc_type)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{ts}_{filename}"
        file_path = dir_path / safe_name
        file_path.write_bytes(content)
        rel = str(file_path.relative_to(self._base_dir))
        logger.debug("Document saved", rel_path=rel, size=len(content))
        return rel

    def read(self, rel_path: str) -> bytes:
        full_path = self._base_dir / rel_path
        if not full_path.exists():
            raise FileNotFoundError(f"Document not found: {rel_path}")
        return full_path.read_bytes()

    def delete(self, rel_path: str) -> bool:
        full_path = self._base_dir / rel_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def get_absolute_path(self, rel_path: str) -> Path:
        return self._base_dir / rel_path
