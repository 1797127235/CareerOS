# Story：架构重构 — 将 vector store 访问层提取到 core

## 背景与目的

当前 `backend/modules/memory/`、`agent/`、`config/`、`health/` 等模块直接
import `backend.modules.data_sources.ingestion` 来访问 vector store。
这造成基础设施层（memory）反向依赖领域模块（data_sources），架构方向错误：

```
现在（错误）：
  memory/writer.py ──▶ data_sources/ingestion ──▶ LanceDB

目标（正确）：
  data_sources/ingestion ──▶ core/vector_store ──▶ LanceDB
  memory/writer.py       ──▶ core/vector_store ──▶ LanceDB
```

**实现方式：创建 `backend/core/vector_store.py` 统一出口，改所有 import 路径，
代码文件本身不移动。** 这是"改门牌号"而不是"搬家"，风险最低。

---

## 任务清单

- [ ] 1. 创建 `backend/core/vector_store.py`
- [ ] 2. 更新 `backend/modules/memory/writer.py`
- [ ] 3. 更新 `backend/modules/memory/search.py`
- [ ] 4. 更新 `backend/modules/memory/projection.py`
- [ ] 5. 更新 `backend/modules/config/router.py`
- [ ] 6. 更新 `backend/modules/health/router.py`
- [ ] 7. 更新 `backend/modules/agent/tools/core/factory.py`
- [ ] 8. 更新 `backend/core/startup.py`
- [ ] 9. 验证启动无报错

---

## 任务 1 — 创建 `backend/core/vector_store.py`

新建文件，内容如下：

```python
"""Vector store 基础设施出口。

所有需要访问 DocumentIndexProvider 的模块应从此处 import，
而不是直接引用 backend.modules.data_sources.ingestion。

具体实现仍住在 data_sources/ingestion/，此文件只做统一出口。
"""

from backend.modules.data_sources.ingestion.document_index_provider import (
    DocumentIndexProvider,
    HealthStatus,
    ProviderHit,
)
from backend.modules.data_sources.ingestion.pipeline import get_document_index_provider
from backend.modules.data_sources.ingestion.providers.null import NullProvider

__all__ = [
    "DocumentIndexProvider",
    "HealthStatus",
    "ProviderHit",
    "get_document_index_provider",
    "NullProvider",
]
```

---

## 任务 2 — `backend/modules/memory/writer.py`

第 99–100 行（lazy import 块内），将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
from backend.modules.data_sources.ingestion.providers.null import NullProvider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider, NullProvider
```

---

## 任务 3 — `backend/modules/memory/search.py`

第 381–382 行（lazy import 块内），将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
from backend.modules.data_sources.ingestion.providers.null import NullProvider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider, NullProvider
```

---

## 任务 4 — `backend/modules/memory/projection.py`

共 4 处，全部替换：

| 行号 | 原内容 | 改为 |
|------|--------|------|
| 94 | `from backend.modules.data_sources.ingestion import get_document_index_provider` | `from backend.core.vector_store import get_document_index_provider` |
| 95 | `from backend.modules.data_sources.ingestion.providers.null import NullProvider` | `from backend.core.vector_store import NullProvider` |
| 274 | `from backend.modules.data_sources.ingestion import get_document_index_provider` | `from backend.core.vector_store import get_document_index_provider` |
| 288 | `from backend.modules.data_sources.ingestion import get_document_index_provider` | `from backend.core.vector_store import get_document_index_provider` |
| 289 | `from backend.modules.data_sources.ingestion.providers.null import NullProvider` | `from backend.core.vector_store import NullProvider` |

---

## 任务 5 — `backend/modules/config/router.py`

第 82 行，将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider
```

---

## 任务 6 — `backend/modules/health/router.py`

第 13 行，将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider
```

---

## 任务 7 — `backend/modules/agent/tools/core/factory.py`

第 228 行，将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider
```

---

## 任务 8 — `backend/core/startup.py`

第 16 行，将：

```python
from backend.modules.data_sources.ingestion import get_pipeline, init_pipeline_async
```

保持不变（`get_pipeline`、`init_pipeline_async` 属于 ingestion pipeline 领域，不移动）。

第 92 行，将：

```python
from backend.modules.data_sources.ingestion import get_document_index_provider
```

改为：

```python
from backend.core.vector_store import get_document_index_provider
```

---

## 任务 9 — 验证

```bash
# 启动后端，无 ImportError
cd backend && python -m uvicorn main:app --reload

# 确认无残留的旧 import
grep -rn "from backend.modules.data_sources.ingestion import get_document_index_provider" backend/ --include="*.py"
grep -rn "from backend.modules.data_sources.ingestion.providers.null import NullProvider" backend/ --include="*.py"
# 以上两条应无输出
```

---

## 不要做的事

- **不要移动任何 `.py` 文件**，只改 import 路径
- **不要修改** `backend/core/startup.py` 第 16 行（`get_pipeline`、`init_pipeline_async` 留在原处）
- **不要修改** `data_sources/ingestion/` 内部任何逻辑
- **不要在此 Story 里实现随记功能**，这是独立的下一步
