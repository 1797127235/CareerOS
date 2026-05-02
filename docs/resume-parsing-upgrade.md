# 简历解析升级计划 — 借鉴 Resume-Matcher

> 状态：待审核

---

## 1. 背景

CareerOS 当前简历解析存在多个短板，导致解析质量不稳定：

| 问题 | 影响 |
|------|------|
| 无日期修复 | LLM 把 "Jun 2020 - Aug 2021" 变成 "2020 - 2021" |
| 无截断检测 | LLM 返回空 workExperience 不会重试 |
| Prompt 太简单 | 没有 schema 示例，LLM 容易格式错误 |
| 无真实性规则 | LLM 可能添加不存在的技能 |
| JSON 提取脆弱 | 简单 `json.loads`，无容错 |

[Resume-Matcher](https://github.com/srbhr/Resume-Matcher) 是一个 14k+ stars 的开源项目，已经解决了上述所有问题。

---

## 2. Resume-Matcher 核心优势

### 2.1 文档解析：markitdown

```python
# Resume-Matcher: 一行代码解析多种格式
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert(file_path)  # PDF/DOCX/HTML/CSV/JSON 都支持
markdown_text = result.text_content
```

**优势**：
- 微软维护，质量有保证
- 支持 10+ 文件格式
- 输出 Markdown，方便后续处理
- 比 pdfplumber 更稳定（处理扫描件、加密文件等边缘情况）

### 2.2 日期修复

```python
# 从原始 Markdown 提取完整日期，修复 LLM 丢失的月份
def restore_dates_from_markdown(parsed_data, markdown):
    # 正则提取: "Jan 2020 - Dec 2023", "May 2021 - Present"
    md_dates = _extract_markdown_dates(markdown)
    
    # 构建映射: "2020 - 2021" → "Jun 2020 - Aug 2021"
    year_to_full = {}
    for md_date in md_dates:
        years = year_only_re.findall(md_date)
        year_key = " - ".join(years)
        if year_key not in year_to_full:
            year_to_full[year_key] = md_date
    
    # 修复 parsed_data 中的年份
    for section in ("workExperience", "education", "personalProjects"):
        for entry in parsed_data.get(section, []):
            years = entry.get("years", "")
            if years in year_to_full:
                entry["years"] = year_to_full[years]
    
    return parsed_data
```

### 2.3 JSON 安全提取

```python
def _extract_json(content):
    # 1. 处理 thinking tags (deepseek-r1, qwq 等)
    if "<think>" in content:
        content = _strip_thinking_tags(content)
    
    # 2. 处理 markdown code blocks
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    
    # 3. 检测截断（unbalanced braces）
    if end_idx == -1 and depth != 0:
        logging.warning("JSON extraction found unbalanced braces")
    
    # 4. 大小限制（1MB）
    if len(content) > MAX_JSON_CONTENT_SIZE:
        raise ValueError("Content too large")
    
    # 5. 递归深度限制
    if _depth > MAX_JSON_EXTRACTION_RECURSION:
        raise ValueError("Exceeded max recursion depth")
```

### 2.4 真实性规则

```
CRITICAL TRUTHFULNESS RULES - NEVER VIOLATE:
1. DO NOT add any skill, tool, technology, or certification that is not explicitly mentioned in the original resume
2. DO NOT invent numeric achievements (e.g., "increased by 30%") unless they exist in original
3. DO NOT add company names, product names, or technical terms not in the original
4. DO NOT upgrade experience level (e.g., "Junior" -> "Senior")
5. DO NOT add languages, frameworks, or platforms the candidate hasn't used
6. DO NOT extend employment dates or change timelines
7. Preserve factual accuracy - only use information provided by the candidate
8. NEVER remove existing skills, certifications, languages, or awards
```

### 2.5 截断检测 + 重试

```python
async def complete_json(prompt, retries=2):
    for attempt in range(retries + 1):
        result = await llm_call(prompt)
        
        # 检测截断
        if _appears_truncated(result):
            if attempt < retries:
                prompt += "\n\nIMPORTANT: Output the COMPLETE JSON object"
                continue
            logging.warning("Truncated on final attempt")
        
        return result
```

---

## 3. 借鉴方案

### 3.1 引入清单

| 模块 | 决策 | 来源 | 理由 |
|------|------|------|------|
| `markitdown` | ✅ 引入 | Resume-Matcher | 替换 pdfplumber，更稳定 |
| 日期修复 | ✅ 复制 | Resume-Matcher | 核心逻辑，直接复用 |
| JSON 提取 | ✅ 复制 | Resume-Matcher | 截断检测 + 重试 |
| 真实性规则 | ✅ 复制 | Resume-Matcher | Prompt 工程 |
| 截断检测 | ✅ 复制 | Resume-Matcher | 自动重试机制 |
| LiteLLM | ✅ 引入 | Resume-Matcher | 统一 LLM 抽象层 |
| TinyDB | ❌ 不用 | - | SQLAlchemy 更适合 |
| Pydantic 模型 | ✅ 参考 | Resume-Matcher | 结构设计 |

### 3.2 LiteLLM 集成

**为什么要引入 LiteLLM**：

| 维度 | DashScope 直调 | LiteLLM |
|------|----------------|---------|
| Provider 切换 | 改代码 | 改配置 |
| 重试机制 | 手写 | 内置（429/500/timeout） |
| JSON Mode | 手写检测 | 自动检测 + fallback |
| 多模型支持 | 只有通义千问 | 100+ 模型 |
| 错误处理 | 基础 | 分类（Auth/Rate/Timeout/Content） |

**LiteLLM 支持 DashScope**：

```python
import litellm

# 直接调用 DashScope
response = await litellm.acompletion(
    model="dashscope/qwen-plus",
    messages=[...],
    api_key="your-dashscope-key",
)
```

### 3.3 不复用的部分

| 模块 | 不复用理由 |
|------|-----------|
| TinyDB | CareerOS 定位是可部署服务，需要 SQLAlchemy + SQLite/PostgreSQL |
| 前端 | CareerOS 有自己的 UI 设计 |
| 数据库迁移 | CareerOS 用 ORM create_all，不用 Alembic |

---

## 4. 技术实现

### 4.1 新增依赖

```txt
# requirements.txt 新增
markitdown>=0.0.1
litellm>=1.30.0
```

### 4.2 文件结构

```
app/backend/
├── agent/
│   ├── llm_router.py      # 重构：使用 LiteLLM
│   ├── resume_parser.py   # 新增：简历解析核心逻辑
│   └── ...
├── services/
│   ├── profile_service.py # 重构：使用新解析器
│   └── ...
└── utils/
    ├── json_utils.py      # 新增：JSON 安全提取
    └── date_utils.py      # 新增：日期修复
```

### 4.3 核心模块设计

**1. resume_parser.py**（新增）

```python
"""简历解析器 — 借鉴 Resume-Matcher"""

from markitdown import MarkItDown
from app.backend.agent.llm_router import chat as llm_chat
from app.backend.utils.json_utils import extract_json
from app.backend.utils.date_utils import restore_dates

# 真实性规则
TRUTHFULNESS_RULES = """
CRITICAL TRUTHFULNESS RULES:
1. DO NOT add any skill not explicitly mentioned in original
2. DO NOT invent numeric achievements
3. DO NOT add company names not in original
4. DO NOT upgrade experience level
5. DO NOT add languages/frameworks candidate hasn't used
6. DO NOT extend employment dates
"""

# 解析 Prompt
PARSE_RESUME_PROMPT = """Parse this resume into JSON. Output ONLY the JSON object.

{truthfulness_rules}

Schema:
{schema}

Resume:
{resume_text}"""


async def parse_resume(file_content: bytes, filename: str) -> dict:
    """完整解析流程：文件 → Markdown → JSON → 修复"""
    
    # 1. 转换为 Markdown
    markdown = await convert_to_markdown(file_content, filename)
    
    # 2. LLM 解析
    prompt = PARSE_RESUME_PROMPT.format(
        truthfulness_rules=TRUTHFULNESS_RULES,
        schema=RESUME_SCHEMA,
        resume_text=markdown[:5000],
    )
    result = await llm_chat(
        task_type="resume_optimize",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    
    # 3. JSON 安全提取
    data = extract_json(result)
    
    # 4. 日期修复
    data = restore_dates(data, markdown)
    
    return data


async def convert_to_markdown(content: bytes, filename: str) -> str:
    """使用 markitdown 转换为 Markdown"""
    import tempfile
    from pathlib import Path
    
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        return result.text_content
    finally:
        tmp_path.unlink(missing_ok=True)
```

**2. json_utils.py**（升级现有文件）

**当前实现问题**：

```python
# 现有实现（rfind 边界问题）
start = candidate.find("{")
end = candidate.rfind("}")  # ❌ 如果 JSON 字符串内含 }，会截断错误
if start != -1 and end != -1 and end > start:
    candidate = candidate[start : end + 1]
```

**问题示例**：
```json
{"description": "使用正则 } 匹配", "skills": ["Python"]}
```
`rfind("}")` 会匹配到字符串内的 `}`，导致 JSON 解析失败。

**升级方案**：

```python
"""JSON 安全提取 — 升级自 Resume-Matcher"""

import json
import re
import logging

MAX_JSON_SIZE = 1024 * 1024  # 1MB
MAX_RECURSION_DEPTH = 10


def extract_json(content: str) -> dict:
    """从 LLM 响应提取 JSON，处理各种格式"""
    
    if not content:
        return {}
    
    # 1. 处理 thinking tags（保留现有逻辑）
    cleaned = _THINKING_RE.sub("", content)
    
    # 2. 处理 markdown code blocks（保留现有逻辑）
    fence_match = _FENCE_RE.search(cleaned)
    candidate = fence_match.group(1).strip() if fence_match else cleaned.strip()
    
    # 3. 提取 JSON（升级：括号匹配而非 rfind）
    json_str = _extract_json_object(candidate)
    
    # 4. 解析
    result = json.loads(json_str)
    
    # 5. 检测截断
    if _appears_truncated(result):
        logging.warning("JSON appears truncated")
    
    return result


def _extract_json_object(content: str, _depth: int = 0) -> str:
    """提取完整的 JSON 对象 — 括号匹配算法"""
    
    if _depth > MAX_RECURSION_DEPTH:
        raise ValueError("Exceeded max recursion depth")
    
    if len(content) > MAX_JSON_SIZE:
        raise ValueError("Content too large")
    
    # 找到第一个 {
    start_idx = content.find("{")
    if start_idx == -1:
        raise ValueError("No JSON found")
    
    # 括号匹配：正确处理字符串内的 }
    depth = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(content[start_idx:], start=start_idx):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start_idx:i + 1]
    
    raise ValueError("Unbalanced braces")


def _appears_truncated(data: dict) -> bool:
    """检测 JSON 是否被截断"""
    suspicious_empty = ["workExperience", "education", "skills"]
    for key in suspicious_empty:
        if key in data and data[key] == []:
            return True
    return False
```

**3. date_utils.py**（新增）

```python
"""日期修复 — 借鉴 Resume-Matcher"""

import re

# 匹配日期范围: "Jan 2020 - Dec 2023", "May 2021 - Present"
_DATE_RE = re.compile(
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)"
    r"\.?\s+\d{4})"
    r"(?:\s*[-–—]\s*"
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)"
    r"\.?\s+\d{4}"
    r"|Present|Current|Now|Ongoing))?",
    re.IGNORECASE,
)


def restore_dates(parsed_data: dict, markdown: str) -> dict:
    """修复 LLM 丢失的月份信息"""
    
    # 从 Markdown 提取完整日期
    md_dates = _DATE_RE.findall(markdown)
    if not md_dates:
        return parsed_data
    
    # 构建映射: "2020 - 2021" → "Jun 2020 - Aug 2021"
    year_to_full = {}
    year_only_re = re.compile(r"\d{4}")
    
    for md_date in md_dates:
        years = year_only_re.findall(md_date)
        if years:
            year_key = " - ".join(years)
            if year_key not in year_to_full:
                year_to_full[year_key] = md_date
    
    if not year_to_full:
        return parsed_data
    
    # 修复 workExperience, education, personalProjects
    patched = 0
    for section in ("workExperience", "education", "personalProjects"):
        for entry in parsed_data.get(section, []):
            if not isinstance(entry, dict):
                continue
            years = entry.get("years", "")
            if not isinstance(years, str) or not years:
                continue
            # 跳过已有月份的
            if re.search(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", years, re.IGNORECASE):
                continue
            # 修复
            if years in year_to_full:
                entry["years"] = year_to_full[years]
                patched += 1
    
    if patched:
        logging.info("Restored months in %d date fields", patched)
    
    return parsed_data
```

**4. llm_router.py**（重构）

```python
"""LLM 路由 — 使用 LiteLLM 统一抽象"""

import litellm
from functools import lru_cache
from app.backend.config import get_settings

# LiteLLM 配置
litellm.drop_params = True  # 丢弃不支持的参数
litellm.modify_params = True  # 自动修改参数

# 模型映射
_MODEL_MAP = {
    "qwen-plus": "dashscope/qwen-plus",
    "qwen-max": "dashscope/qwen-max",
    "text-embedding-v4": "dashscope/text-embedding-v4",
}


async def chat(
    task_type: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    retries: int = 2,
) -> str:
    """统一 LLM 调用，内置重试"""
    
    settings = get_settings()
    model = _MODEL_MAP.get("qwen-plus", "dashscope/qwen-plus")
    
    for attempt in range(retries + 1):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=settings.dashscope_api_key,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt < retries:
                logging.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
                continue
            raise


async def chat_json(
    task_type: str,
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 2048,
    retries: int = 2,
) -> dict:
    """JSON 模式调用，自动检测支持"""
    
    settings = get_settings()
    model = _MODEL_MAP.get("qwen-plus", "dashscope/qwen-plus")
    
    # 检测是否支持 JSON mode
    supports_json = _supports_json_mode(model)
    
    for attempt in range(retries + 1):
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": settings.dashscope_api_key,
            }
            if supports_json:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            
            return extract_json(content)
        except Exception as e:
            if attempt < retries:
                logging.warning("JSON call failed (attempt %d): %s", attempt + 1, e)
                continue
            raise


def _supports_json_mode(model: str) -> bool:
    """检测模型是否支持 JSON mode"""
    try:
        info = litellm.get_model_info(model=model)
        supported_params = info.get("supported_openai_params", [])
        return "response_format" in supported_params
    except Exception:
        return False
```

---

## 5. 实施计划

### Phase 1：依赖引入（0.5 天）

- [ ] `requirements.txt` 新增 `markitdown` 和 `litellm`
- [ ] 测试 markitdown 是否正常工作
- [ ] 测试 LiteLLM 是否支持 DashScope

### Phase 2：核心模块（1.5 天）

- [ ] 创建 `app/backend/utils/json_utils.py`
- [ ] 创建 `app/backend/utils/date_utils.py`
- [ ] 创建 `app/backend/agent/resume_parser.py`
- [ ] 单元测试各模块

### Phase 3：LLM 路由重构（1 天）

- [ ] 重构 `llm_router.py` 使用 LiteLLM
- [ ] 添加 `chat_json()` 函数
- [ ] 测试 JSON mode 支持
- [ ] 保持向后兼容

### Phase 4：集成测试（1 天）

- [ ] 重构 `profile_service.py` 使用新解析器
- [ ] 测试完整流程：上传 → 解析 → 存储
- [ ] 测试边缘情况（扫描件、格式混乱）
- [ ] 测试日期修复是否生效

### Phase 5：Prompt 优化（1 天）

- [ ] 添加真实性规则到 Prompt
- [ ] 添加 schema 示例到 Prompt
- [ ] 测试解析质量提升

**总计：5 天**

---

## 6. 验收标准

- [ ] 上传 PDF/DOCX，解析成功率 > 95%
- [ ] 日期字段保留月份信息（不丢失）
- [ ] JSON 解析失败时自动重试（最多 3 次）
- [ ] LLM 不添加简历中不存在的技能
- [ ] 空 workExperience/education 触发重试
- [ ] 现有功能不受影响（向后兼容）

---

## 7. 风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| markitdown 不支持某些 PDF | 中 | 回退到 pdfplumber |
| LiteLLM 不支持 DashScope | 低 | 已验证支持 |
| JSON mode 不生效 | 中 | 回退到 prompt-only |
| 日期修复误判 | 低 | 只修复明确的年份映射 |
| 性能下降 | 低 | LiteLLM 有连接池 |

---

## 8. 参考资料

- [Resume-Matcher GitHub](https://github.com/srbhr/Resume-Matcher)
- [markitdown 文档](https://github.com/microsoft/markitdown)
- [LiteLLM 文档](https://docs.litellm.ai/)
- [DashScope LiteLLM 集成](https://docs.litellm.ai/docs/providers/dashscope)
