"""Lumen 日志配置 — structlog + stdlib 混合方案

设计原则：
1. 开发环境：彩色控制台输出，易读
2. 生产环境：JSON 格式，便于日志收集
3. SQLAlchemy 噪音过滤：只显示 WARNING 以上
4. 结构化上下文：自动注入 request_id, user_id, conversation_id
5. 日志轮转：生产环境写入文件，自动轮转
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

# ── 上下文变量 ──────────────────────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
conversation_id_var: ContextVar[str] = ContextVar("conversation_id", default="")

REQUEST_ID_HEADER = "X-Request-ID"


# ── structlog 配置 ──────────────────────────────────────────


def setup_logging(json_logs: bool = False, log_level: str = "INFO") -> None:
    """配置 structlog + stdlib 混合日志。

    Args:
        json_logs: True=JSON 格式（生产），False=彩色控制台（开发）
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
    """
    shared_processors: list[structlog.types.Processor] = [
        merge_contextvars,  # 合并上下文变量到每条日志
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
    ]

    # 选择渲染器
    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # 配置 structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置 stdlib handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
    )

    # 过滤噪音日志
    _suppress_noisy_loggers()

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def _suppress_noisy_loggers() -> None:
    """抑制过于详细的日志源。"""
    noisy_loggers = [
        "sqlalchemy.engine",  # SQL 查询日志
        "sqlalchemy.pool",  # 连接池日志
        "sqlalchemy.dialects",
        "uvicorn.access",  # HTTP 访问日志（由我们自己的 middleware 替代）
        "watchfiles",  # 文件监听日志
        "httpx",  # HTTP 客户端日志
        "httpcore",  # HTTP 核心日志
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# ── 请求日志中间件 ──────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI 请求日志中间件 — 自动绑定 request_id, user_id, conversation_id。"""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 生成或提取 request_id
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4())[:8])
        request_id_var.set(request_id)

        # 清空并绑定上下文
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            client_host=request.client.host if request.client else None,
        )

        log = structlog.get_logger()
        log.info("request_started")

        try:
            response = await call_next(request)
            log.info("request_completed", status_code=response.status_code)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception as exc:
            log.error("request_failed", error=str(exc))
            raise


# ── 上下文绑定工具 ──────────────────────────────────────────


def bind_user_context(user_id: str) -> None:
    """绑定用户 ID 到当前上下文。"""
    user_id_var.set(user_id)
    bind_contextvars(user_id=user_id)


def bind_conversation_context(conversation_id: str) -> None:
    """绑定会话 ID 到当前上下文。"""
    conversation_id_var.set(conversation_id)
    bind_contextvars(conversation_id=conversation_id)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取带上下文的 logger。"""
    return structlog.get_logger(name)
