"""Mem0 记忆客户端 — 单例初始化与全局访问

Story 1.1: 初始化基础设施
Story 1.2: 使用 get_mem0().add() 提取记忆
Story 1.3: 使用 get_mem0().get_all() 检索记忆
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_mem0: Any | None = None  # mem0.Memory 单例
_mem0_status: str = "not_initialized"


def get_mem0() -> Any | None:
    """返回已初始化的 Memory 实例，未初始化时返回 None"""
    return _mem0


def get_mem0_status() -> str:
    """返回当前状态：ready / no_api_key / error / not_initialized"""
    return _mem0_status


def init_mem0() -> str:
    """初始化 Mem0 Memory 客户端，返回状态字符串。

    在 lifespan 启动时调用。不抛出异常，错误仅记录日志。
    状态说明：
      - "ready": 初始化成功
      - "no_api_key": 未配置 API Key，跳过初始化
      - "error": 初始化异常
    """
    global _mem0, _mem0_status

    from mem0 import Memory

    from app.backend.config import USER_DATA_DIR, get_settings

    settings = get_settings()

    # API Key 检查：优先用新字段，回退旧字段
    api_key = settings.llm_api_key or settings.dashscope_api_key
    if not api_key:
        logger.warning("Mem0 初始化跳过：未配置任何 LLM API Key")
        _mem0_status = "no_api_key"
        return _mem0_status

    # LiteLLM model identifier，与 llm_router._get_model_identifier 逻辑一致
    # OpenAI 不需要 provider 前缀；其他 provider 使用 "provider/model" 格式
    provider = settings.llm_provider or "dashscope"
    model_name = settings.llm_model or "qwen-plus"
    chat_model = model_name if provider == "openai" else f"{provider}/{model_name}"

    embed_provider = settings.embedding_provider or provider
    embed_name = settings.embedding_model or "text-embedding-v4"
    embed_model = embed_name if embed_provider == "openai" else f"{embed_provider}/{embed_name}"
    embed_key = settings.embedding_api_key or api_key

    config: dict = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "career_os_memory",
                "path": str(USER_DATA_DIR / "chroma_db"),
            },
        },
        "llm": {
            "provider": "litellm",
            "config": {
                "model": chat_model,
                "api_key": api_key,
            },
        },
        "embedder": {
            "provider": "litellm",
            "config": {
                "model": embed_model,
                "api_key": embed_key,
            },
        },
    }

    # 自定义 base_url（用于自托管 Provider 或 OpenAI-compatible 接口）
    if settings.llm_base_url:
        config["llm"]["config"]["api_base"] = settings.llm_base_url
    if settings.embedding_base_url:
        config["embedder"]["config"]["api_base"] = settings.embedding_base_url

    try:
        _mem0 = Memory.from_config(config)
        _mem0_status = "ready"
        logger.info("Mem0 初始化成功，Chroma 路径: %s/chroma_db", USER_DATA_DIR)
    except Exception as e:
        logger.error("Mem0 初始化失败: %s", e)
        _mem0_status = "error"

    return _mem0_status
