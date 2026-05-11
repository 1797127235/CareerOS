"""AST 工具集扫描器 — 零副作用发现 FunctionToolset。

设计原则：
1. 只解析 AST，不 import 模块 → 避免副作用
2. 扫描 toolsets/*.py 找 FunctionToolset 赋值
3. 返回 (module_path, variable_name, metadata) 元组列表
4. 按需 import：过滤后再真正加载模块

类似 Hermes 的 AST 扫描，但找的是 FunctionToolset 实例而非 registry.register()。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolsetRef:
    """AST 扫描发现的工具集引用（尚未 import）。"""

    module_path: str
    """Python 模块路径，如 backend.agent.tools.toolsets.chat"""

    variable_name: str
    """模块内变量名，如 chat_toolset"""

    file_path: Path
    """源文件绝对路径"""

    def __repr__(self) -> str:
        return f"ToolsetRef({self.module_path}.{self.variable_name})"


def scan_toolset_refs(package_path: Path) -> list[ToolsetRef]:
    """扫描目录下所有 .py 文件，找 FunctionToolset 赋值。

    扫描规则：
    1. 只处理 *.py 文件（跳过 __init__.py）
    2. 找顶层赋值：xxx_toolset = FunctionToolset(...)
    3. 变量名以 _toolset 结尾
    4. 不 import 模块，零副作用

    Args:
        package_path: toolsets/ 目录路径

    Returns:
        ToolsetRef 列表（可能为空）
    """
    refs: list[ToolsetRef] = []

    if not package_path.exists():
        logger.debug("Toolset package not found", path=package_path)
        return refs

    # 从包路径推导模块前缀
    # e.g. backend/agent/tools/toolsets -> backend.agent.tools.toolsets
    module_prefix = _path_to_module(package_path)

    for py_file in sorted(package_path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.warning("Syntax error in toolset file", file=py_file.name, error=str(exc))
            continue
        except Exception as exc:
            logger.warning("Failed to read toolset file", file=py_file.name, error=str(exc))
            continue

        module_name = py_file.stem
        full_module = f"{module_prefix}.{module_name}"

        # 找顶层 FunctionToolset 赋值
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if not target.id.endswith("_toolset"):
                    continue

                # 确认右侧是 FunctionToolset(...) 调用
                if _is_function_toolset_call(node.value):
                    refs.append(
                        ToolsetRef(
                            module_path=full_module,
                            variable_name=target.id,
                            file_path=py_file,
                        )
                    )
                    logger.debug(
                        "Toolset discovered via AST",
                        module=full_module,
                        variable=target.id,
                    )

    logger.info("AST scan complete", found=len(refs), directory=str(package_path))
    return refs


def _is_function_toolset_call(node: ast.expr) -> bool:
    """检查 AST 节点是否为 FunctionToolset(...) 调用。"""
    # 处理 FunctionToolset(...)
    if isinstance(node, ast.Call):
        func = node.func
        # 直接调用：FunctionToolset(...)
        if isinstance(func, ast.Name) and func.id == "FunctionToolset":
            return True
        # 属性访问：pydantic_ai.FunctionToolset(...) 或 toolsets.FunctionToolset(...)
        if isinstance(func, ast.Attribute) and func.attr == "FunctionToolset":
            return True
    return False


def _path_to_module(path: Path) -> str:
    """把文件路径转成 Python 模块路径。

    e.g. E:/MyHub/career-os/backend/agent/tools/toolsets
         -> backend.agent.tools.toolsets
    """
    # 找到项目根目录（包含 backend/ 的目录）
    parts: list[str] = []
    for part in path.parts:
        if part == "backend":
            parts = ["backend"]
        elif parts:
            parts.append(part)

    if not parts:
        # fallback：用最后两级
        parts = list(path.parts[-2:])

    return ".".join(parts)


def load_toolset(ref: ToolsetRef) -> Any:
    """按需 import 模块并获取 FunctionToolset 实例。

    Args:
        ref: AST 扫描发现的引用

    Returns:
        FunctionToolset 实例

    Raises:
        ImportError: 模块导入失败
        AttributeError: 变量不存在
    """
    logger.debug("Loading toolset", module=ref.module_path, variable=ref.variable_name)

    import importlib

    module = importlib.import_module(ref.module_path)
    toolset = getattr(module, ref.variable_name)

    return toolset
