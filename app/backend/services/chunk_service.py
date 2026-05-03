"""文本分块服务 — 纯函数，零外部依赖

职责：
- 文本切分为语义块
- 段落边界检测
- 句子边界检测
- 块间重叠处理

不依赖：
- 数据库
- 向量库
- 任何第三方服务
"""

import re

# 默认分块配置
DEFAULT_MAX_CHARS = 600
DEFAULT_OVERLAP = 50


def split_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """将文本切分为语义块

    策略：
    1. 优先按段落切分（保留空行边界）
    2. 段落过长时按句子切分（保留句号/问号/感叹号边界）
    3. 最终合并相邻段落/句子，确保每块不超过 max_chars
    4. 添加块间重叠

    Args:
        text: 原始文本
        max_chars: 每块最大字符数
        overlap: 块间重叠字符数

    Returns:
        文本块列表
    """
    if len(text) <= max_chars:
        return [text]

    # 第一步：按段落拆分
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # 段落本身超过限制：按句子切分
            sentences = _split_sentences(para)
            for sent in sentences:
                if len(current_chunk) + len(sent) + 1 <= max_chars:
                    current_chunk = f"{current_chunk}\n{sent}".strip() if current_chunk else sent
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sent
        else:
            # 正常段落，尝试合并
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk = f"{current_chunk}\n\n{para}".strip() if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    # 添加重叠
    if overlap > 0 and len(chunks) > 1:
        chunks = _apply_overlap(chunks, overlap)

    return chunks


def _split_sentences(text: str) -> list[str]:
    """按中文/英文句子边界切分文本"""
    # 匹配句号、问号、感叹号、换行（保留分隔符）
    parts = re.split(r"([。！？\n])", text)
    sentences = []
    buf = ""
    for part in parts:
        buf += part
        if part in ("\u3002", "\uff01", "\uff1f", "\n") and buf.strip():
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """为每个块（除第一个）添加前一块末尾的重叠内容"""
    result = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            prev_tail = chunks[i - 1][-overlap:]
            chunk = prev_tail + chunk
        result.append(chunk)
    return result


def estimate_token_count(text: str) -> int:
    """粗略估计中文字符对应的 token 数量

    经验值：中文字符 ≈ 0.6-0.8 token/字，保守估计按 1:1
    """
    return len(text)
