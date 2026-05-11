"""工具注册表 — AST 扫描 + FunctionToolset 管理。

重构后架构：
1. AST 扫描发现 toolsets/*.py 中的 FunctionToolset（零副作用）
2. 条件过滤：按 enabled_toolsets / settings.mcp_*_enabled 筛选
3. 按需 import：只加载需要的模块
4. 返回 FunctionToolset 列表给 Agent

设计原则：
- 注册层：FunctionToolset（PydanticAI 原生，保留签名）
- 业务层：Tool ABC（不变，call() 写业务逻辑）
- 执行层：ToolExecutor（不变，统一流水线）
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.config import get_settings
from backend.logging_config import get_logger

if TYPE_CHECKING:
    from pydantic_ai import FunctionToolset

logger = get_logger(__name__)

# 缓存扫描结果（进程生命周期内有效）
_scanned_refs: list | None = None


def discover_toolsets(
    *,
    enabled: list[str] | None = None,
    disabled: list[str] | None = None,
) -> list[FunctionToolset]:
    """发现并加载工具集。

    流程：
    1. AST 扫描 toolsets/ 目录 → ToolsetRef 列表
    2. 条件过滤（enabled / disabled / mcp config）
    3. 按需 import 并返回 FunctionToolset 实例

    Args:
        enabled: 白名单 — 只加载这些 toolset（如 ["chat", "mcp-filesystem"]）
               None 表示加载所有
        disabled: 黑名单 — 排除这些 toolset（如 ["terminal"]）

    Returns:
        FunctionToolset 实例列表（可直接传给 Agent(toolsets=...)）
    """
    from backend.agent.tools.ast_scanner import load_toolset, scan_toolset_refs

    global _scanned_refs

    # 1. AST 扫描（缓存）
    if _scanned_refs is None:
        toolsets_dir = Path(__file__).parent / "toolsets"
        _scanned_refs = scan_toolset_refs(toolsets_dir)

    refs = _scanned_refs
    if not refs:
        logger.warning("No toolsets discovered")
        return []

    # 2. 条件过滤
    filtered = _filter_refs(refs, enabled=enabled, disabled=disabled)

    # 3. 按需加载
    toolsets: list[FunctionToolset] = []
    for ref in filtered:
        try:
            toolset = load_toolset(ref)
            toolsets.append(toolset)
            logger.debug("Toolset loaded", name=ref.variable_name, module=ref.module_path)
        except Exception as exc:
            logger.error(
                "Failed to load toolset",
                module=ref.module_path,
                variable=ref.variable_name,
                error=str(exc),
            )

    logger.info(
        "Toolsets ready",
        total=len(toolsets),
        names=[ref.variable_name for ref in filtered],
    )
    return toolsets


def _filter_refs(refs, *, enabled: list[str] | None, disabled: list[str] | None) -> list:
    """按条件过滤 ToolsetRef。"""
    settings = get_settings()
    result = list(refs)

    # MCP 条件过滤：检查 settings.mcp_*_enabled
    # 变量名如 mcp_filesystem_toolset → 需要 mcp_filesystem_enabled=True
    mcp_filtered = []
    for ref in result:
        var_name = ref.variable_name
        if var_name.startswith("mcp_"):
            # mcp_filesystem_toolset → mcp_filesystem_enabled
            config_key = var_name.replace("_toolset", "_enabled")
            if not getattr(settings, config_key, False):
                logger.debug("MCP toolset disabled", toolset=var_name, config_key=config_key)
                continue
        mcp_filtered.append(ref)
    result = mcp_filtered

    # enabled 白名单
    if enabled is not None:
        # 从变量名提取 toolset 名：chat_toolset → chat
        enabled_names = set(enabled)
        result = [ref for ref in result if _toolset_name(ref.variable_name) in enabled_names]

    # disabled 黑名单
    if disabled is not None:
        disabled_names = set(disabled)
        result = [ref for ref in result if _toolset_name(ref.variable_name) not in disabled_names]

    return result


def _toolset_name(variable_name: str) -> str:
    """从变量名提取 toolset 标识。

    e.g. chat_toolset → chat
         mcp_filesystem_toolset → mcp-filesystem
    """
    name = variable_name.replace("_toolset", "").replace("_", "-")
    return name


def invalidate_scan_cache() -> None:
    """使扫描缓存失效（用于热重载场景）。"""
    global _scanned_refs
    _scanned_refs = None
    logger.info("Toolset scan cache invalidated")
