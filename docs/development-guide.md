# CareerOS 开发指南

**项目**: CareerOS（码路领航）
**最后更新**: 2026-05-06

---

## 1. 环境要求

### 必需

- **Python**: 3.11+
- **Node.js**: 22+
- **Git**: 任意版本

### 可选

- **Docker**: 20.10+ (容器化部署)
- **VS Code**: 推荐编辑器

---

## 2. 本地开发设置

### 2.1 克隆仓库

```bash
git clone https://github.com/1797127235/CareerOS.git
cd CareerOS
```

### 2.2 后端设置

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

### 2.3 前端设置

```bash
cd app/frontend
npm install
cd ../..
```

### 2.4 启动开发服务器

**方式一：使用脚本（推荐）**

```bash
# Windows
run.bat

# PowerShell
.\run.ps1
```

**方式二：手动启动**

```bash
# 终端 1：后端
uvicorn app.backend.main:app --reload --port 3000

# 终端 2：前端
cd app/frontend
npm run dev
```

**访问地址**:
- 前端: http://localhost:5173
- 后端 API: http://localhost:3000
- API 文档: http://localhost:3000/docs

---

## 3. 项目配置

### 3.1 环境变量 (.env)

```bash
# LLM Provider
DASHSCOPE_API_KEY=sk-xxx        # DashScope API Key
LLM_PROVIDER=dashscope          # 可选: dashscope/openai/deepseek/anthropic
LLM_MODEL=qwen-plus             # 模型名称

# 数据库
DATABASE_URL=sqlite+aiosqlite:///~/.careeros/career_os.db

# 调试
DEBUG=true
```

### 3.2 用户配置 (config.json)

运行时配置，通过 Settings 页面或 API 修改：

```json
{
  "llm_provider": "dashscope",
  "llm_model": "qwen-plus",
  "llm_api_key": "",
  "llm_base_url": "",
  "embedding_provider": "dashscope",
  "embedding_model": "text-embedding-v3",
  "embedding_api_key": "",
  "embedding_base_url": ""
}
```

配置文件位置：`~/.careeros/config.json`

---

## 4. 代码规范

### 4.1 Python

- **Linter**: ruff
- **Formatter**: ruff format
- **类型提示**: 必须（`from __future__ import annotations`）
- **异步风格**: SQLAlchemy 2.0 async

```bash
# 检查
ruff check app/

# 格式化
ruff format app/

# 同时检查 + 格式化
ruff check app/ && ruff format app/
```

### 4.2 TypeScript

- **Linter**: ESLint
- **Formatter**: Prettier (通过 ESLint)
- **类型检查**: TypeScript strict mode

```bash
cd app/frontend
npm run lint
```

### 4.3 提交规范

```bash
# 格式
<type>: <description>

# 示例
feat: 添加技能管理功能
fix: 修复对话历史加载失败
refactor: 重构记忆投影器
docs: 更新 API 文档
test: 添加 profile API 测试
```

---

## 5. 测试

### 5.1 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_api_health.py

# 运行并显示覆盖率
pytest --cov=app/backend
```

### 5.2 测试结构

```
tests/
├── conftest.py             # 测试 fixtures
├── test_agent_loop.py      # Agent 测试
├── test_api_health.py      # API 测试
└── test_chat_api.py        # Chat 测试
```

### 5.3 编写测试

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_example(client: AsyncClient):
    """测试示例"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
```

---

## 6. 数据库

### 6.1 本地数据库

位置：`~/.careeros/career_os.db`

### 6.2 重置数据库

```bash
# 删除数据库文件
rm ~/.careeros/career_os.db

# 重启应用会自动重建
```

### 6.3 查看数据库

```bash
# 使用 sqlite3 CLI
sqlite3 ~/.careeros/career_os.db

# 查看表
.tables

# 查看表结构
.schema growth_events

# 查询数据
SELECT * FROM growth_events LIMIT 10;
```

---

## 7. Docker 开发

### 7.1 构建镜像

```bash
docker build -t career-os .
```

### 7.2 运行容器

```bash
docker compose up -d
```

### 7.3 查看日志

```bash
docker compose logs -f career-os
```

### 7.4 进入容器

```bash
docker exec -it career-os /bin/bash
```

---

## 8. 调试

### 8.1 后端调试

```bash
# 启用调试日志
DEBUG=true uvicorn app.backend.main:app --reload

# 在代码中添加
import logging
logger = logging.getLogger(__name__)
logger.debug("调试信息")
```

### 8.2 前端调试

- 打开浏览器 DevTools (F12)
- Network 面板查看 API 请求
- Console 面板查看错误
- React DevTools 扩展

### 8.3 Agent 调试

查看 `agent_traces` 表：

```sql
SELECT * FROM agent_traces 
WHERE conversation_id = 'xxx' 
ORDER BY step_number;
```

---

## 9. 常见问题

### 9.1 API Key 未配置

**错误**: `未配置 LLM API Key`

**解决**: 在 Settings 页面配置 API Key，或在 `.env` 中设置 `DASHSCOPE_API_KEY`

### 9.2 数据库锁定

**错误**: `database is locked`

**解决**: 确保没有多个进程同时写入 SQLite

### 9.3 前端构建失败

**错误**: TypeScript 编译错误

**解决**: 
```bash
cd app/frontend
npm run build
# 查看具体错误
```

### 9.4 Cognee 初始化失败

**错误**: `Cognee not installed`

**解决**: Cognee 是可选依赖，不影响核心功能。如需使用：
```bash
pip install cognee==1.0.5
```

---

## 10. 贡献流程

1. Fork 仓库
2. 创建功能分支：`git checkout -b feat/your-feature`
3. 提交更改：`git commit -m "feat: your feature"`
4. 推送分支：`git push origin feat/your-feature`
5. 创建 Pull Request

### PR 检查清单

- [ ] 代码通过 `ruff check`
- [ ] 代码通过 `ruff format --check`
- [ ] 测试通过 `pytest`
- [ ] 前端构建通过 `npm run build`
- [ ] 添加必要的测试
- [ ] 更新相关文档
