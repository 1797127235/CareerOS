# Story：Provider Catalog 拆分 — 照抄 openhanako 结构

## 目标

把 `core/config.py` 里的 `PROVIDER_CATALOG` 大 dict 拆成 openhanako 的三层结构：

```
lib/
├── default-models.json  ← 只放模型列表（照抄 openhanako lib/default-models.json，放 lib/ 根）
└── providers/
    ├── __init__.py      ← 注册表：合并所有 provider 文件 + ../default-models.json
    ├── anthropic.py
├── openai.py
├── gemini.py
├── xai.py
├── mistral.py
├── groq.py
├── perplexity.py
├── fireworks.py
├── together.py
├── openrouter.py
├── dashscope.py
├── deepseek.py
├── moonshot.py
├── zhipu.py
├── volcengine.py
├── siliconflow.py
├── baichuan.py
├── hunyuan.py
├── minimax.py
├── baidu_cloud.py       ← baidu-cloud（Python 文件名不能含连字符）
├── stepfun.py
├── modelscope.py
├── infini.py
├── mimo.py
├── ollama.py
└── custom.py            ← Lumen 特有，openhanako 无此文件
```

完成后 `core/config.py` 里的 `PROVIDER_CATALOG` 改为从 `lib.providers` 导入。

---

## 参考文件（先读）

```
E:\OpenHub\openhanako\lib\providers\anthropic.js   ← 看 provider 文件格式
E:\OpenHub\openhanako\lib\providers\ollama.js      ← auth_type: none 的例子
E:\OpenHub\openhanako\lib\default-models.json      ← 模型列表来源
E:\MyHub\career-os\core\config.py                  ← 现有 PROVIDER_CATALOG（数据来源）
```

---

## 每个 provider 文件的格式

openhanako 用 JS，Lumen 用 Python dict，字段对应：

| openhanako JS | Lumen Python |
|---------------|-------------|
| `id` | `"id"` |
| `displayName` | `"label"` |
| `defaultBaseUrl` | `"base_url"` |
| `defaultApi` | `"api"` |
| `authType: "api-key"` | `"auth_type": "api-key"` |
| `authType: "none"` | `"auth_type": "none"` |

每个文件只有一个变量 `PROVIDER`：

```python
# lib/providers/anthropic.py
PROVIDER = {
    "id": "anthropic",
    "label": "Anthropic",
    "base_url": "https://api.anthropic.com",
    "api": "anthropic-messages",
    "auth_type": "api-key",
}
```

```python
# lib/providers/ollama.py
PROVIDER = {
    "id": "ollama",
    "label": "Ollama（本地）",
    "base_url": "http://localhost:11434/v1",
    "api": "openai-completions",
    "auth_type": "none",
}
```

```python
# lib/providers/custom.py（Lumen 特有）
PROVIDER = {
    "id": "custom",
    "label": "自定义（OpenAI-Compatible）",
    "base_url": "",
    "api": "openai-completions",
    "auth_type": "api-key",
}
```

所有 provider 的数据从现有 `core/config.py` 的 `PROVIDER_CATALOG` 照抄，不要自己发明。

---

## default-models.json

位置：`lib/default-models.json`（与 openhanako 一致，放在 `lib/` 根目录，不在 `providers/` 里）。

照抄 `E:\OpenHub\openhanako\lib\default-models.json`，但只保留 Lumen 现有的供应商。

Lumen 现有供应商：anthropic, openai, gemini, xai, mistral, groq, perplexity, fireworks, together, openrouter, dashscope, deepseek, moonshot, zhipu, volcengine, siliconflow, baichuan, hunyuan, minimax, baidu-cloud, stepfun, modelscope, infini, mimo, ollama, custom。

openhanako `default-models.json` 没有的供应商（volcengine、mimo、custom 等），从 `core/config.py` 现有的 `chat_models` 列表补充。

ollama 和 custom 无固定模型列表，写空数组 `[]`（或不写该 key）。

---

## lib/providers/__init__.py（注册表）

```python
"""Provider 注册表 — 照抄 openhanako core/provider-registry.js 的合并逻辑。

每个 provider 文件声明静态元数据，default-models.json 声明默认模型列表，
此模块在启动时合并两者，构建出 PROVIDER_CATALOG。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── 导入所有 provider 声明 ──
from lib.providers.anthropic import PROVIDER as _anthropic
from lib.providers.openai import PROVIDER as _openai
from lib.providers.gemini import PROVIDER as _gemini
from lib.providers.xai import PROVIDER as _xai
from lib.providers.mistral import PROVIDER as _mistral
from lib.providers.groq import PROVIDER as _groq
from lib.providers.perplexity import PROVIDER as _perplexity
from lib.providers.fireworks import PROVIDER as _fireworks
from lib.providers.together import PROVIDER as _together
from lib.providers.openrouter import PROVIDER as _openrouter
from lib.providers.dashscope import PROVIDER as _dashscope
from lib.providers.deepseek import PROVIDER as _deepseek
from lib.providers.moonshot import PROVIDER as _moonshot
from lib.providers.zhipu import PROVIDER as _zhipu
from lib.providers.volcengine import PROVIDER as _volcengine
from lib.providers.siliconflow import PROVIDER as _siliconflow
from lib.providers.baichuan import PROVIDER as _baichuan
from lib.providers.hunyuan import PROVIDER as _hunyuan
from lib.providers.minimax import PROVIDER as _minimax
from lib.providers.baidu_cloud import PROVIDER as _baidu_cloud
from lib.providers.stepfun import PROVIDER as _stepfun
from lib.providers.modelscope import PROVIDER as _modelscope
from lib.providers.infini import PROVIDER as _infini
from lib.providers.mimo import PROVIDER as _mimo
from lib.providers.ollama import PROVIDER as _ollama
from lib.providers.custom import PROVIDER as _custom

_ALL_PROVIDERS = [
    _anthropic, _openai, _gemini, _xai, _mistral, _groq, _perplexity,
    _fireworks, _together, _openrouter, _dashscope, _deepseek, _moonshot,
    _zhipu, _volcengine, _siliconflow, _baichuan, _hunyuan, _minimax,
    _baidu_cloud, _stepfun, _modelscope, _infini, _mimo, _ollama, _custom,
]

_DEFAULT_MODELS: dict[str, list] = json.loads(
    (Path(__file__).parent.parent / "default-models.json").read_text(encoding="utf-8")
)


def _build_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for p in _ALL_PROVIDERS:
        pid = p["id"]
        catalog[pid] = {
            "label": p["label"],
            "base_url": p["base_url"],
            "api": p.get("api", "openai-completions"),
            "auth_type": p.get("auth_type", "api-key"),
            "chat_models": _DEFAULT_MODELS.get(pid, []),
            "embedding_models": [],
        }
    return catalog


PROVIDER_CATALOG: dict[str, dict[str, Any]] = _build_catalog()
```

---

## core/config.py 修改

找到现有的 `PROVIDER_CATALOG` 大 dict（约第 18–223 行），整块替换为：

```python
from lib.providers import PROVIDER_CATALOG as PROVIDER_CATALOG  # noqa: PLC0414
```

同时删掉文件顶部的注释块（`# ── Provider 目录…` 那几行）。

`get_provider_catalog_frontend()` 函数保留不动，它读 `PROVIDER_CATALOG` 变量，不需要改。

---

## embedding_models 处理

现有 `PROVIDER_CATALOG` 里有些供应商有 `embedding_models`（openai、gemini、dashscope 等）。

在对应的 provider 文件里加一个可选字段：

```python
# lib/providers/openai.py
PROVIDER = {
    "id": "openai",
    "label": "OpenAI",
    "base_url": "https://api.openai.com/v1",
    "api": "openai-completions",
    "auth_type": "api-key",
    "embedding_models": ["text-embedding-3-small", "text-embedding-3-large"],
}
```

注册表的 `_build_catalog()` 里读取：

```python
"embedding_models": p.get("embedding_models", []),
```

---

## 验证

```bash
python -c "from lib.providers import PROVIDER_CATALOG; print(len(PROVIDER_CATALOG), 'providers')"
python -c "from core.config import PROVIDER_CATALOG; print('ok')"
python -c "from main import app; print('OK:', app.title)"
```

期望输出：`26 providers`、`ok`、`OK: Lumen`。

---

## 不要做的事

- 不要修改 provider 的数据（label、base_url、api、模型列表），只改结构
- 不要改 `core/config.py` 里 `PROVIDER_CATALOG` 以外的任何内容
- 不要改 `get_provider_catalog_frontend()`
- 不要改 `build_llm_call_params()`
