# Story：目录重组 — 照抄 openhanako 架构

## 目标

把 Lumen 后端从 `backend/modules/` 的技术层切割风格，重组为 openhanako 的业务域平铺风格：

```
career-os/
├── core/           # 原 backend/core/（零依赖基础设施）
├── lib/            # 原 backend/modules/ 中的业务逻辑
│   ├── agent/
│   ├── chat/
│   ├── config/
│   ├── data_sources/
│   ├── memory/
│   ├── profile/
│   ├── tools/      # 原 backend/modules/agent/tools/（提升一层）
│   └── model_registry.py
├── server/
│   └── routes/     # 原各 modules/*/router.py（集中放路由）
│       ├── chat.py
│       ├── config.py
│       ├── health.py
│       ├── memory.py
│       ├── mcp.py
│       └── notes.py
├── shared/         # 原 backend/shared/
├── main.py         # 原 backend/main.py（提升到根级）
├── src/            # 前端，不动
└── src-tauri/      # 不动
```

**这是纯搬移重命名，不写任何新逻辑。**

---

## 第一步：建目录骨架

```bash
mkdir -p core lib/tools lib/agent lib/chat lib/config lib/data_sources lib/memory lib/profile server/routes shared
```

---

## 第二步：移动文件（全部用 git mv，保留历史）

### 2.1 core/ — 直接搬

```bash
git mv backend/core/__init__.py     core/__init__.py
git mv backend/core/config.py       core/config.py
git mv backend/core/db.py           core/db.py
git mv backend/core/logging.py      core/logging.py
git mv backend/core/migrations.py   core/migrations.py
git mv backend/core/startup.py      core/startup.py
git mv backend/core/vector_store.py core/vector_store.py
```

### 2.2 shared/ — 直接搬

```bash
git mv backend/shared/__init__.py      shared/__init__.py
git mv backend/shared/path_utils.py   shared/path_utils.py
```

### 2.3 lib/model_registry.py

```bash
git mv backend/model_registry.py lib/model_registry.py
```

### 2.4 lib/memory/ — 搬非路由文件

```bash
git mv backend/modules/memory/__init__.py      lib/memory/__init__.py
git mv backend/modules/memory/classifier.py    lib/memory/classifier.py
git mv backend/modules/memory/events_merger.py lib/memory/events_merger.py
git mv backend/modules/memory/facade.py        lib/memory/facade.py
git mv backend/modules/memory/markdown.py      lib/memory/markdown.py
git mv backend/modules/memory/models.py        lib/memory/models.py
git mv backend/modules/memory/observations.py  lib/memory/observations.py
git mv backend/modules/memory/projection.py    lib/memory/projection.py
git mv backend/modules/memory/relational_store.py lib/memory/relational_store.py
git mv backend/modules/memory/review_service.py lib/memory/review_service.py
git mv backend/modules/memory/search.py        lib/memory/search.py
git mv backend/modules/memory/searcher.py      lib/memory/searcher.py
git mv backend/modules/memory/snapshot.py      lib/memory/snapshot.py
git mv backend/modules/memory/understanding.py lib/memory/understanding.py
git mv backend/modules/memory/writer.py        lib/memory/writer.py
```

### 2.5 lib/agent/ — 搬非路由文件

```bash
git mv backend/modules/agent/__init__.py       lib/agent/__init__.py
git mv backend/modules/agent/deps.py           lib/agent/deps.py
git mv backend/modules/agent/event_handlers.py lib/agent/event_handlers.py
git mv backend/modules/agent/models.py         lib/agent/models.py
git mv backend/modules/agent/pydantic_agent.py lib/agent/pydantic_agent.py
```

### 2.6 lib/tools/ — 将 agent/tools/ 提升为独立 lib

```bash
git mv backend/modules/agent/tools/__init__.py lib/tools/__init__.py

# core/
git mv backend/modules/agent/tools/core/__init__.py  lib/tools/core/__init__.py
git mv backend/modules/agent/tools/core/context.py   lib/tools/core/context.py
git mv backend/modules/agent/tools/core/definitions.py lib/tools/core/definitions.py
git mv backend/modules/agent/tools/core/dispatcher.py lib/tools/core/dispatcher.py
git mv backend/modules/agent/tools/core/factory.py   lib/tools/core/factory.py
git mv backend/modules/agent/tools/core/policies.py  lib/tools/core/policies.py
git mv backend/modules/agent/tools/core/registry.py  lib/tools/core/registry.py
git mv backend/modules/agent/tools/core/toolsets.py  lib/tools/core/toolsets.py

# builtin/
git mv backend/modules/agent/tools/builtin/__init__.py lib/tools/builtin/__init__.py
git mv backend/modules/agent/tools/builtin/external.py lib/tools/builtin/external.py
git mv backend/modules/agent/tools/builtin/memory.py   lib/tools/builtin/memory.py
git mv backend/modules/agent/tools/builtin/profile.py  lib/tools/builtin/profile.py
git mv backend/modules/agent/tools/builtin/schemas.py  lib/tools/builtin/schemas.py

# adapters/
git mv backend/modules/agent/tools/adapters/__init__.py  lib/tools/adapters/__init__.py
git mv backend/modules/agent/tools/adapters/pydanticai.py lib/tools/adapters/pydanticai.py

# mcp/（非路由文件）
git mv backend/modules/agent/tools/mcp/__init__.py      lib/tools/mcp/__init__.py
git mv backend/modules/agent/tools/mcp/client_manager.py lib/tools/mcp/client_manager.py
git mv backend/modules/agent/tools/mcp/config_store.py  lib/tools/mcp/config_store.py
git mv backend/modules/agent/tools/mcp/models.py        lib/tools/mcp/models.py
git mv backend/modules/agent/tools/mcp/tool_bridge.py   lib/tools/mcp/tool_bridge.py
git mv backend/modules/agent/tools/mcp/transport.py     lib/tools/mcp/transport.py
```

### 2.7 lib/chat/ — 搬非路由文件

```bash
git mv backend/modules/chat/__init__.py    lib/chat/__init__.py
git mv backend/modules/chat/lock.py        lib/chat/lock.py
git mv backend/modules/chat/models.py      lib/chat/models.py
git mv backend/modules/chat/persistence.py lib/chat/persistence.py
git mv backend/modules/chat/service.py     lib/chat/service.py
git mv backend/modules/chat/session.py     lib/chat/session.py
git mv backend/modules/chat/summary.py     lib/chat/summary.py
```

### 2.8 lib/data_sources/

```bash
git mv backend/modules/data_sources/__init__.py          lib/data_sources/__init__.py
git mv backend/modules/data_sources/models.py            lib/data_sources/models.py
git mv backend/modules/data_sources/registry.py          lib/data_sources/registry.py
git mv backend/modules/data_sources/service.py           lib/data_sources/service.py
git mv backend/modules/data_sources/ingestion            lib/data_sources/ingestion
```

### 2.9 lib/profile/

```bash
git mv backend/modules/profile/__init__.py lib/profile/__init__.py
git mv backend/modules/profile/models.py   lib/profile/models.py
git mv backend/modules/profile/schemas.py  lib/profile/schemas.py
```

### 2.10 lib/config/

```bash
git mv backend/modules/config/__init__.py lib/config/__init__.py
git mv backend/modules/config/service.py  lib/config/service.py
```

### 2.11 server/routes/ — 集中所有路由

```bash
touch server/__init__.py
touch server/routes/__init__.py

git mv backend/modules/chat/router.py              server/routes/chat.py
git mv backend/modules/memory/router.py            server/routes/memory.py
git mv backend/modules/config/router.py            server/routes/config.py
git mv backend/modules/health/router.py            server/routes/health.py
git mv backend/modules/notes/router.py             server/routes/notes.py
git mv backend/modules/agent/tools/mcp/router.py   server/routes/mcp.py
```

### 2.12 main.py — 提升到根级

```bash
git mv backend/main.py main.py
```

---

## 第三步：全局替换 import 路径

用 sed 批量替换所有 `.py` 文件中的 import。**顺序很重要，长路径先替换。**

```bash
# 找出所有需要处理的 py 文件
FILES=$(find core lib server shared main.py -name "*.py" 2>/dev/null)

# 替换顺序：最长路径前面，避免部分匹配污染
sed -i \
  -e 's/from backend\.modules\.agent\.tools\.mcp\./from lib.tools.mcp./g' \
  -e 's/from backend\.modules\.agent\.tools\.builtin\./from lib.tools.builtin./g' \
  -e 's/from backend\.modules\.agent\.tools\.core\./from lib.tools.core./g' \
  -e 's/from backend\.modules\.agent\.tools\.adapters\./from lib.tools.adapters./g' \
  -e 's/from backend\.modules\.agent\.tools\./from lib.tools./g' \
  -e 's/from backend\.modules\.agent\./from lib.agent./g' \
  -e 's/from backend\.modules\.chat\./from lib.chat./g' \
  -e 's/from backend\.modules\.memory\./from lib.memory./g' \
  -e 's/from backend\.modules\.profile\./from lib.profile./g' \
  -e 's/from backend\.modules\.config\./from lib.config./g' \
  -e 's/from backend\.modules\.data_sources\./from lib.data_sources./g' \
  -e 's/from backend\.modules\.health\./from server.routes./g' \
  -e 's/from backend\.core\./from core./g' \
  -e 's/from backend\.shared\./from shared./g' \
  -e 's/from backend\.model_registry/from lib.model_registry/g' \
  -e 's/from backend\.main/from main/g' \
  -e 's/import backend\.core\./import core./g' \
  $FILES
```

> **Windows 注意**：Git Bash 的 sed -i 可能需要 `sed -i ''`，或者用 Python 脚本替代：
>
> ```python
> # scripts/fix_imports.py
> import re, pathlib
>
> RULES = [
>     (r'from backend\.modules\.agent\.tools\.mcp\.', 'from lib.tools.mcp.'),
>     (r'from backend\.modules\.agent\.tools\.builtin\.', 'from lib.tools.builtin.'),
>     (r'from backend\.modules\.agent\.tools\.core\.', 'from lib.tools.core.'),
>     (r'from backend\.modules\.agent\.tools\.adapters\.', 'from lib.tools.adapters.'),
>     (r'from backend\.modules\.agent\.tools\.', 'from lib.tools.'),
>     (r'from backend\.modules\.agent\.', 'from lib.agent.'),
>     (r'from backend\.modules\.chat\.', 'from lib.chat.'),
>     (r'from backend\.modules\.memory\.', 'from lib.memory.'),
>     (r'from backend\.modules\.profile\.', 'from lib.profile.'),
>     (r'from backend\.modules\.config\.', 'from lib.config.'),
>     (r'from backend\.modules\.data_sources\.', 'from lib.data_sources.'),
>     (r'from backend\.core\.', 'from core.'),
>     (r'from backend\.shared\.', 'from shared.'),
>     (r'from backend\.model_registry', 'from lib.model_registry'),
>     (r'from backend\.main', 'from main'),
>     (r'import backend\.core\.', 'import core.'),
> ]
>
> roots = ['core', 'lib', 'server', 'shared', 'main.py', 'tests', 'scripts']
> for root in roots:
>     for p in pathlib.Path(root).rglob('*.py') if pathlib.Path(root).is_dir() else [pathlib.Path(root)]:
>         txt = p.read_text(encoding='utf-8')
>         new = txt
>         for pattern, repl in RULES:
>             new = re.sub(pattern, repl, new)
>         if new != txt:
>             p.write_text(new, encoding='utf-8')
>             print(f'fixed: {p}')
> ```
>
> 运行：`python scripts/fix_imports.py`

---

## 第四步：修改 main.py

`main.py` 现在在根级，更新所有路由 import：

```python
# main.py 的 router import 从这里：
from backend.modules.agent.tools.mcp.router import router as mcp_router
from backend.modules.chat.router import router as chat_router
from backend.modules.config.router import router as config_router
from backend.modules.health.router import router as health_router
from backend.modules.memory.router import router as memory_router
from backend.modules.notes.router import router as notes_router

# 改为：
from server.routes.mcp import router as mcp_router
from server.routes.chat import router as chat_router
from server.routes.config import router as config_router
from server.routes.health import router as health_router
from server.routes.memory import router as memory_router
from server.routes.notes import router as notes_router
```

（第三步的脚本不会处理这些，需要手动改或单独 sed。）

---

## 第五步：修改 pyproject.toml

```toml
# 原来：
[tool.ruff.lint.isort]
known-first-party = ["backend"]

# 改为：
[tool.ruff.lint.isort]
known-first-party = ["core", "lib", "server", "shared"]
```

---

## 第六步：修改 .github/workflows/ci.yml

找到所有引用 `backend/` 的行，替换：

```yaml
# 原：
- name: Ruff lint
  run: ruff check backend/

- name: Ruff format
  run: ruff format backend/

- name: Ruff format check
  run: ruff format --check backend/

- name: Byte-compile backend
  run: python -m compileall -q backend/

- name: Smoke import app
  run: python -c "from backend.main import app; assert app.title"

# 改为：
- name: Ruff lint
  run: ruff check core/ lib/ server/ shared/ main.py

- name: Ruff format
  run: ruff format core/ lib/ server/ shared/ main.py

- name: Ruff format check
  run: ruff format --check core/ lib/ server/ shared/ main.py

- name: Byte-compile
  run: python -m compileall -q core/ lib/ server/ shared/

- name: Smoke import app
  run: python -c "from main import app; assert app.title"
```

---

## 第七步：清理空目录

```bash
# 删除已经清空的旧目录（确认全部文件已移走再执行）
rm -rf backend/
```

---

## 第八步：验证

```bash
# 1. 没有残留的 backend. import
grep -r "from backend\." core/ lib/ server/ shared/ main.py

# 2. 应用可以启动
python -c "from main import app; print('OK:', app.title)"

# 3. ruff 不报错
ruff check core/ lib/ server/ shared/ main.py

# 4. 跑测试
pytest
```

全部通过则完成。

---

## 不要做的事

- 不要修改任何业务逻辑
- 不要改 `src/`（前端）
- 不要改 `src-tauri/`
- 不要改 `tests/`（除非 import 报错才修）
- 不要新增功能
