"""Builtin 工具 Handler 的输入类型定义 — TypedDict。"""

from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict

# ── 文件工具 ──


class FileReadArgs(TypedDict):
    """file_read 工具的输入参数。"""

    _resolved_path: Path
    """Dispatcher 解析后的绝对路径。"""

    offset: NotRequired[int]
    """起始行号（默认 1）。"""

    limit: NotRequired[int]
    """最大行数（默认 500，最大 2000）。"""


class FileWriteArgs(TypedDict):
    """file_write 工具的输入参数。"""

    _resolved_path: Path
    """Dispatcher 解析后的绝对路径。"""

    content: str
    """文件内容。"""


class FileListArgs(TypedDict):
    """file_list 工具的输入参数。"""

    path: NotRequired[str]
    """原始路径参数（可选）。"""

    _resolved_path: NotRequired[Path]
    """Dispatcher 解析后的绝对路径（path 为空时为 None）。"""


class FileSearchArgs(TypedDict):
    """file_search 工具的输入参数。"""

    pattern: str
    """正则表达式模式。"""

    path: NotRequired[str]
    """原始路径参数（可选）。"""

    _resolved_path: NotRequired[Path]
    """Dispatcher 解析后的绝对路径（path 为空时为 None）。"""


# ── 记忆工具 ──


class MemorySearchArgs(TypedDict):
    """memory_search 工具的输入参数。"""

    query: str
    """搜索关键词或时间描述。"""

    scope: NotRequired[str]
    """搜索范围 — profile / emotions / reference / chat / knowledge。"""

    search_mode: NotRequired[str]
    """keyword（默认）或 grep。"""

    time_filter: NotRequired[str]
    """时间过滤 — today / yesterday / recent_7d 等（仅 grep 模式）。"""


class MemorySaveArgs(TypedDict):
    """memory_save 工具的输入参数。"""

    entity_type: str
    """类型 — skills / experiences / preferences / goals / decisions / status / note。"""

    section: str
    """标题/名称。"""

    content: str
    """具体内容。"""


# ── 画像工具 ──


class GetProfileArgs(TypedDict):
    """get_profile 工具的输入参数（无参数）。"""


class UpdateProfileArgs(TypedDict):
    """update_profile 工具的输入参数 — 只收集最基础的身份名片。"""

    nickname: NotRequired[str]
    bio: NotRequired[str]
