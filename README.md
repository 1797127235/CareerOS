# Lumen

<p align="center">
  <b>一个真正认识你的 AI 伴侣</b><br>
  <i>伴你从学生到未来，深谋远虑，始终平易近人</i>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#功能特性">功能</a> ·
  <a href="#项目结构">结构</a> ·
  <a href="#文档">文档</a> ·
  <a href="#参与贡献">贡献</a>
</p>

---

## 这是什么

一个单用户 AI 伴侣系统，持续积累对你的了解——你的经历、目标、困惑、决定——随时间真正认识你这个人。

**目标用户**：处于学生到职场初期，面对方向选择、个人成长、人生规划的人。

**核心价值**：你不需要每次重新解释自己。数据在本地，不依赖云端，越用越懂你。

**技术栈**：FastAPI + SQLAlchemy + PydanticAI + LiteLLM + React + Vite + Tailwind

---


## 快速开始

### 方式一：Docker（推荐）

```bash
git clone https://github.com/1797127235/Lumen.git
cd Lumen
docker compose up -d
```

打开 `http://localhost:3000`，在设置页选择 LLM Provider 并填入 API Key，开始使用。

### 方式二：本地开发

```bash
# 后端
pip install -r requirements.txt

# 前端
cd app/frontend && npm install && cd ../..

# 配置
cp .env.example .env
# 编辑 .env，配置 API Key（或在浏览器设置页填写）

# 启动
# Windows: 双击 run.bat
# PowerShell: .\run.ps1
```

打开 `http://localhost:5173`，开始使用。

---



## 数据架构

Lumen 使用**事件驱动的记忆系统**：

```
写入路径:
Agent 工具（memory_save / update_profile）
    |
    ├─ 对话中主动调用 → growth_events
    |                       ↓
    |                   sync_projections → .md（投影）
    |
    └─ Agent 没调 → 后台审查（asyncio.create_task）
                         ↓
                    独立 Agent + review prompt
                         ↓
                    有信息→growth_events→.md
                    无信息→跳过
```

**两层记忆模型**:

| 层级 | 存储 | 用途 |
|------|------|------|
| L1 | conversation messages | 短期上下文（最近 20 条 + 滚动摘要） |
| L2 | growth_events → .md | 结构化画像 + FTS5 全文搜索 |

所有数据存储在 `~/.lumen/`：
```
~/.lumen/
├── lumen.db      # SQLite（事件、对话、技能、FTS5 索引）
├── memory/           # .md 记忆文件
│   ├── memory.md     # 核心画像
│   ├── skills.md     # 技能
│   └── experiences.md # 经历
├── kuzu/             # Cognee 图谱数据（可选，待调通）
├── lancedb/          # Cognee 向量数据（可选，待调通）
└── config.json       # 用户设置（API Key 等）
```

---

## 技术选型

| 层级 | 选型 | 说明 |
|------|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 | async，类型安全 |
| 数据库 | SQLite（单文件） | 自托管首选，零运维 |
| LLM | LiteLLM（DashScope / OpenAI / DeepSeek / Anthropic / Gemini / Ollama / OpenRouter）| 多 Provider 统一路由，用户自选 |
| Agent | PydanticAI + ReAct Loop | 流式推理，工具调用，可观测性 |
| 记忆层 | growth_events → .md（FTS5 全文搜索 + Cognee 语义） | 事件溯源 + 投影架构 |
| 前端 | React 19 + Vite + Tailwind CSS 4 | OKLCH 配色，响应式 |
| 部署 | Docker Compose | 单容器，单端口，持久化 volume |

---

## Agent 系统

Lumen 使用 PydanticAI 实现的 Agent ReAct Loop：

```
用户消息 → POST /api/chat
    ↓
chat_service.py
    ├─ 创建/获取 Conversation
    ├─ 保存用户消息
    ↓
@agent.system_prompt 注入：memory.md + 摘要 + 历史
    ↓
PydanticAI Agent (ReAct Loop)
    ├─ 工具调用（memory_save / update_profile / memory_search）
    └─ 流式输出（SSE）
    ↓
Agent 调了工具？ → sync_projections → .md
    ↓ 没调？
后台审查兜底（fork Agent + review prompt）
```

**工具列表**：
- `memory_search(query, files?)` — 搜索记忆（FTS5 全文搜索）
- `memory_save(entity_type, section, content)` — 保存记忆（目标/技能/经历/偏好/决策/状态）
- `update_profile(school_name, major, grade, ...)` — 更新结构化画像（14 个显式参数）
- `get_profile()` — 获取画像（很少需要，已在 system prompt）

**可观测性**：每个 Agent 运行记录在 `agent_traces` 表，包含推理步骤、工具调用、耗时。

---

## API 端点

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/health` | 健康检查 |
| `POST` | `/api/chat` | SSE 流式对话（Agent Loop） |
| `GET`  | `/api/chat/history` | 对话历史列表 |
| `GET`  | `/api/chat/{id}` | 单条会话消息 |
| `DELETE` | `/api/chat/{id}` | 删除对话 |
| `POST` | `/api/profile/resume` | 上传简历，LLM 自动提取画像 |
| `GET`  | `/api/profile/me` | 获取用户画像 |
| `PATCH` | `/api/profile/me` | 更新画像 |
| `DELETE` | `/api/profile/me` | 重置画像 |
| `GET`  | `/api/memory/me` | 读取 `.md` 画像内容 |
| `GET`  | `/api/memory/stats` | 记忆统计 |
| `GET`  | `/api/memory/list` | 记忆列表 |
| `POST` | `/api/memory/reset` | 重置记忆（SQLite + .md + Cognee） |
| `POST` | `/api/memory/rebuild` | 重建记忆投影 |
| `DELETE` | `/api/memory/{id}` | 删除单条事件记忆 |
| `GET`  | `/api/memory/search` | 搜索记忆（FTS5 + Cognee） |
| `GET/POST/PATCH/DELETE` | `/api/skills` | 技能记录 CRUD |
| `GET/POST` | `/api/config` | 用户配置 |

---

## 设计理念

- **自托管优先**：数据在本地，不依赖外部服务，用户自己掌控
- **事件驱动**：所有写入走 growth_events，通过投影器同步到 .md
- **Agent 工具驱动**：Agent 在对话中主动调用工具保存记忆，而非后台自动提取
- **后台审查兜底**：Agent 未主动保存时，后台 fork Agent 审查 → 决定是否保存
- **Agent 而非问答**：ReAct Loop + 工具调用，真正的 Agent 系统

---

## 文档

- [产品简介](docs/product-brief.md) — 产品定位和价值主张
- [系统架构](docs/architecture/) — 架构设计和核心决策
- [记忆结构](docs/memory-structure/) — 记忆数据模型和实体定义
- [Project Context](docs/project-context.md) — AI Agent 编码规则
- [Stories](docs/stories/) — 功能实现记录

---

## 开发规范

### 代码质量

```bash
# Lint + 格式化
ruff check . && ruff format --check .

# 测试
pytest

# 提交前自动检查（已配置 pre-commit hook）
```

CI 会在每次 push 时自动运行：ruff check → ruff format → pytest → frontend build。

### 分支与提交

```bash
git checkout -b feat/your-feature
git commit -m "feat: add something"
git push origin feat/your-feature
# 然后在 GitHub 上创建 PR
```

- Python 3.11+，类型提示
- SQLAlchemy 2.0 async 风格
- PydanticAI 1.89.1
- 中文 commit message

---

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | ✅ | LLM API Key（也可在设置页填写） |
| `LLM_PROVIDER` | ❌ | 默认 `dashscope`（可选 openai/deepseek 等） |
| `LLM_MODEL` | ❌ | 默认 `qwen-plus` |
| `DATABASE_URL` | ❌ | 默认 `~/.lumen/lumen.db` |
| `DEBUG` | ❌ | `true`（开发）/ `false`（Docker 生产） |

完整配置见 `.env.example`。

---

## License

[MIT](LICENSE)
