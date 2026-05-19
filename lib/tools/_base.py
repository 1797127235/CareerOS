"""工具基础类型 — ToolDef 定义 + 结果构造器。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.agent import LumenDeps


@dataclass
class ToolDef:
    """单个工具的完整描述。"""

    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Callable[[dict[str, Any], LumenDeps], Awaitable[str]]
    read_only: bool = True
    category: str = "builtin"  # builtin / mcp / plugin


def tool_ok(text: str) -> str:
    return text


def tool_error(message: str, code: str = "") -> str:
    if code:
        return f"[错误/{code}] {message}"
    return f"[错误] {message}"
