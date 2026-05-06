"""Cognee client singleton management — Kuzu + LanceDB 配置"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_cognee_status: str = "not_initialized"

# 显式配置 Cognee 存储路径到 ~/.lumen/
USER_DATA_DIR = Path.home() / ".lumen"


def _configure_cognee_paths():
    """配置 Cognee 存储路径到 ~/.lumen/"""
    os.environ["GRAPH_DATABASE_PROVIDER"] = "kuzu"
    os.environ["GRAPH_DATABASE_PATH"] = str(USER_DATA_DIR / "kuzu")
    os.environ["VECTOR_DATABASE_PROVIDER"] = "lancedb"
    os.environ["VECTOR_DATABASE_PATH"] = str(USER_DATA_DIR / "lancedb")
    logger.info(
        "Cognee paths configured: kuzu=%s, lancedb=%s",
        USER_DATA_DIR / "kuzu",
        USER_DATA_DIR / "lancedb",
    )


def get_cognee_status() -> str:
    """返回当前 Cognee 初始化状态"""
    return _cognee_status


def init_cognee() -> str:
    """Initialize Cognee and return status."""
    global _cognee_status

    try:
        import cognee  # noqa: F401

        _configure_cognee_paths()
        _cognee_status = "ready"
        logger.info("Cognee initialized with Kuzu + LanceDB")
        return _cognee_status
    except ImportError:
        logger.warning("Cognee not installed")
        _cognee_status = "not_installed"
        return _cognee_status
    except Exception as exc:
        logger.error("Cognee init failed: %s", exc)
        _cognee_status = "error"
        return _cognee_status
