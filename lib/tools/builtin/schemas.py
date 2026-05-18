"""Builtin 工具 Handler 的输入类型定义 — TypedDict。"""

from __future__ import annotations

from typing import NotRequired, TypedDict


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


class GetProfileArgs(TypedDict):
    """get_profile 工具的输入参数（无参数）。"""


class UpdateProfileArgs(TypedDict):
    """update_profile 工具的输入参数 — 只收集最基础的身份名片。"""

    nickname: NotRequired[str]
    bio: NotRequired[str]
