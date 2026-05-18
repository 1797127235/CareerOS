"""应用配置 — 环境变量 + config.json 双层配置

优先级: config.json > 环境变量 (.env) > 默认值
USER_DATA_DIR: ~/.lumen/（用户运行时数据，跨版本持久化）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Provider 目录 — 照抄 openhanako lib/providers/*.js + lib/default-models.json ──
# api 字段 = openhanako defaultApi：openai-completions / anthropic-messages / google-generative-ai
# chat_models = openhanako default-models.json 对应列表（无固定列表的留空，由用户 fetch 或手填）
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "api": "anthropic-messages",
        "chat_models": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
            "claude-opus-4-1",
            "claude-haiku-4-5",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-7-sonnet",
            "claude-3-5-sonnet",
            "claude-3-5-haiku",
            "claude-haiku-3-5-20241022",
        ],
        "embedding_models": [],
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api": "openai-completions",
        "chat_models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini", "o4-mini", "o3", "o3-mini"],
        "embedding_models": ["text-embedding-3-small", "text-embedding-3-large"],
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api": "google-generative-ai",
        "chat_models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
        "embedding_models": ["models/text-embedding-004"],
    },
    "xai": {
        "label": "xAI (Grok)",
        "base_url": "https://api.x.ai/v1",
        "api": "openai-completions",
        "chat_models": ["grok-4-1-fast-reasoning", "grok-4-1-fast-non-reasoning", "grok-3-beta", "grok-3-mini-beta"],
        "embedding_models": [],
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "api": "openai-completions",
        "chat_models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
        "embedding_models": ["mistral-embed"],
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api": "openai-completions",
        "chat_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "embedding_models": [],
    },
    "perplexity": {
        "label": "Perplexity",
        "base_url": "https://api.perplexity.ai",
        "api": "openai-completions",
        "chat_models": ["sonar-pro", "sonar"],
        "embedding_models": [],
    },
    "fireworks": {
        "label": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "api": "openai-completions",
        "chat_models": [
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/deepseek-r1",
        ],
        "embedding_models": [],
    },
    "together": {
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "api": "openai-completions",
        "chat_models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-R1"],
        "embedding_models": [],
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api": "openai-completions",
        "chat_models": [],  # 无固定列表，用户 fetch 或手填
        "embedding_models": [],
    },
    "dashscope": {
        "label": "阿里云百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api": "openai-completions",
        "chat_models": [
            "qwen3.6-plus",
            "qwen3.6-flash",
            "qwen3.6-max-preview",
            "qwen3-vl-plus",
            "qwen3.5-plus",
            "qwen3.5-max",
            "qwen3.5-flash",
            "qwen3-plus",
            "qwen3-max",
            "qwen3-mini",
            "qwen-plus",
            "qwen-turbo",
            "qwen-max",
            "qwen-long",
            "qwen-vl-plus",
            "qwen-vl-max",
        ],
        "embedding_models": ["text-embedding-v4", "text-embedding-v3"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "api": "openai-completions",
        "chat_models": ["deepseek-v4-pro", "deepseek-v4-flash"],
        "embedding_models": [],
    },
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "api": "openai-completions",
        "chat_models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
        "embedding_models": [],
    },
    "zhipu": {
        "label": "智谱 AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api": "openai-completions",
        "chat_models": ["glm-5", "glm-4-plus", "glm-4-flash", "glm-4-air"],
        "embedding_models": [],
    },
    "volcengine": {
        "label": "火山引擎 (豆包)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api": "openai-completions",
        "chat_models": [],  # 无固定列表，用户 fetch 或手填
        "embedding_models": [],
    },
    "siliconflow": {
        "label": "SiliconFlow (硅基流动)",
        "base_url": "https://api.siliconflow.cn/v1",
        "api": "openai-completions",
        "chat_models": [
            "deepseek-ai/DeepSeek-V3-0324",
            "Qwen/Qwen3-8B",
            "THUDM/GLM-4-9B-0414",
            "Pro/deepseek-ai/DeepSeek-R1",
        ],
        "embedding_models": ["BAAI/bge-m3"],
    },
    "baichuan": {
        "label": "百川智能",
        "base_url": "https://api.baichuan-ai.com/v1",
        "api": "openai-completions",
        "chat_models": ["Baichuan4-Turbo", "Baichuan4-Air"],
        "embedding_models": [],
    },
    "hunyuan": {
        "label": "腾讯混元",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "api": "openai-completions",
        "chat_models": ["hunyuan-turbos-latest", "hunyuan-large-latest"],
        "embedding_models": [],
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimaxi.com/anthropic",
        "api": "anthropic-messages",
        "chat_models": [
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5",
            "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1",
            "MiniMax-M2",
        ],
        "embedding_models": [],
    },
    "baidu-cloud": {
        "label": "百度智能云 (文心)",
        "base_url": "https://qianfan.baidubce.com/v2",
        "api": "openai-completions",
        "chat_models": ["ernie-4.5-turbo-vl-32k", "ernie-4.0-turbo-128k"],
        "embedding_models": [],
    },
    "stepfun": {
        "label": "阶跃星辰 (StepFun)",
        "base_url": "https://api.stepfun.com/v1",
        "api": "openai-completions",
        "chat_models": ["step-2-16k", "step-1-flash"],
        "embedding_models": [],
    },
    "modelscope": {
        "label": "魔搭 (ModelScope)",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api": "openai-completions",
        "chat_models": ["Qwen/Qwen3-235B-A22B"],
        "embedding_models": [],
    },
    "infini": {
        "label": "无问芯穹 (Infini)",
        "base_url": "https://cloud.infini-ai.com/maas/v1",
        "api": "openai-completions",
        "chat_models": ["deepseek-r1", "deepseek-v3-0324"],
        "embedding_models": [],
    },
    "mimo": {
        "label": "Xiaomi (MiMo)",
        "base_url": "https://api.xiaomimimo.com/v1",
        "api": "openai-completions",
        "chat_models": [
            "mimo-v2.5-pro",
            "mimo-v2.5",
            "mimo-v2-pro",
            "mimo-v2-flash",
            "mimo-v2-omni",
        ],
        "embedding_models": [],
    },
    "ollama": {
        "label": "Ollama（本地）",
        "base_url": "http://localhost:11434/v1",
        "api": "openai-completions",
        "chat_models": [],  # 无固定列表，由用户 fetch 发现
        "embedding_models": ["nomic-embed-text", "mxbai-embed-large"],
    },
    "custom": {
        "label": "自定义（OpenAI-Compatible）",
        "base_url": "",
        "chat_models": [],
        "embedding_models": [],
    },
}


# ── 目录常量 ────────────────────────────────────────

# 用户运行时数据目录（SQLite / Chroma / config.json）
USER_DATA_DIR = Path.home() / ".lumen"


def _ensure_user_data_dir() -> None:
    """确保用户数据目录存在"""
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Settings ─────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Provider ──
    llm_provider: str = "dashscope"
    llm_model: str = "qwen-plus"
    llm_api_key: str = ""
    llm_base_url: str = ""

    # 旧字段兼容（迁移后仅读取）
    dashscope_api_key: str = ""

    # ── Embedding Provider ──
    embedding_provider: str = "dashscope"
    embedding_model: str = "text-embedding-v4"
    embedding_api_key: str = ""  # 空 = 使用 llm_api_key
    embedding_base_url: str = ""

    # ── 数据库 ──
    database_url: str = ""

    # ── Agent 工作目录 ──
    # Agent 文件工具可访问的根目录（用于开发时访问项目文件）
    # 默认使用用户主目录（最安全），可配置为项目根目录以方便开发
    # 示例：AGENT_WORKSPACE_DIR=E:\\MyHub\\career-os
    agent_workspace_dir: str = ""

    # ── 外部数据接入 ──
    external_data_enabled: bool = False
    external_data_dirs: str = ""
    # 格式：逗号分隔的目录路径，如 "C:\\Obsidian,C:\\Notes"

    @property
    def external_data_dir_list(self) -> list[str]:
        """解析逗号分隔的目录路径为列表。"""
        if not self.external_data_dirs:
            return []
        return [d.strip() for d in self.external_data_dirs.split(",") if d.strip()]

    # ── 应用 ──
    debug: bool = True
    # ── 语义去重 ──
    semantic_dedup_enabled: bool = False
    semantic_dedup_default_threshold: float = 0.85
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # 数据库默认路径：用户数据目录
        if not self.database_url:
            _ensure_user_data_dir()
            self.database_url = f"sqlite+aiosqlite:///{USER_DATA_DIR}/lumen.db"
        # 修复 Windows .env 中文编码问题：直接读取 .env 文件覆盖
        env_path = Path(__file__).parents[1] / ".env"
        if env_path.exists():
            raw = env_path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                if line.startswith("EXTERNAL_DATA_DIRS="):
                    val = line[len("EXTERNAL_DATA_DIRS=") :].strip()
                    if val:
                        self.external_data_dirs = val
                    break


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# ── config.json 双层配置 ──────────────────────────────


def load_user_config() -> dict[str, Any]:
    """读取用户运行时配置（~/.lumen/config.json）

    由 lifespan 或 config API 调用，叠加在 env/default 之上。
    Returns 空 dict 表示文件不存在或解析失败。
    """
    config_path = USER_DATA_DIR / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_config(data: dict[str, Any]) -> dict[str, Any]:
    """写入用户运行时配置，返回合并后的配置"""
    _ensure_user_data_dir()
    config_path = USER_DATA_DIR / "config.json"
    existing = load_user_config()
    # 过滤空值，不保存空字符串覆盖（含纯空格）
    data = {k: v for k, v in data.items() if v not in (None, "") and not (isinstance(v, str) and not v.strip())}
    existing.update(data)
    config_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return existing


def apply_user_config(settings: Settings, user_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """将 config.json 中的值覆盖到 Settings 实例

    Returns 实际应用的配置项（供调试/日志使用）
    """
    cfg = load_user_config() if user_config is None else user_config
    applied: dict[str, Any] = {}

    # 新字段
    _CONFIG_KEYS = (
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
        "embedding_provider",
        "embedding_model",
        "embedding_api_key",
        "embedding_base_url",
    )

    for key in _CONFIG_KEYS:
        val = cfg.get(key)
        if val is not None and val != "" and getattr(settings, key, None) != val:
            setattr(settings, key, val)
            # key 字段脱敏
            if "key" in key.lower():
                applied[key] = "***"
            else:
                applied[key] = val

    # 一次性迁移：旧用户 dashscope_api_key → llm_api_key
    # 条件：llm_provider 是 dashscope（或未设置）且 llm_api_key 为空且 dashscope_api_key 非空
    if settings.llm_provider in ("dashscope", "") and not settings.llm_api_key and settings.dashscope_api_key:
        settings.llm_api_key = settings.dashscope_api_key
        # 同步写入 config.json，避免下次重启重复迁移
        save_user_config({"llm_api_key": settings.dashscope_api_key})
        applied["llm_api_key"] = "***（从 dashscope_api_key 迁移）"

    return applied


def build_llm_call_params(
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, str]:
    """构建 LLM 调用参数（model_id, api_key, base_url）

    统一 model_id 构建规则（provider != openai 时加前缀）和认证参数获取逻辑，
    避免 summary.py、test_config 等处重复实现。
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    model = model or settings.llm_model
    model_id = model if provider == "openai" else f"{provider}/{model}"
    return {
        "model": model_id,
        "api_key": api_key or settings.llm_api_key or settings.dashscope_api_key or "",
        "base_url": base_url or settings.llm_base_url,
    }


def get_provider_catalog_frontend() -> dict[str, dict]:
    """返回前端所需的 Provider 配置格式

    将后端 PROVIDER_CATALOG 转换为前端 Settings.tsx 所需的字段名，
    避免前后端维护两份重复数据。
    """
    return {
        key: {
            "name": val["label"],
            "baseUrl": val["base_url"],
            "models": val["chat_models"],
            "embeddingModels": val["embedding_models"],
        }
        for key, val in PROVIDER_CATALOG.items()
    }
