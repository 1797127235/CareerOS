# AGENTS.md

## What This Is

Lumen — 一个真正认识你的 AI 伴侣。FastAPI + SQLAlchemy + PydanticAI + LiteLLM + SQLite。前端 React 19 + Vite + Tailwind CSS 4。

## How to Run

```bash
# 方式一：Docker（推荐）
docker compose up -d
# 打开 http://localhost:3000

# 方式二：本地开发
pip install -r requirements.txt
cd app/frontend && npm install && cd ../..
# Windows: 双击 run.bat
# PowerShell: .\run.ps1
# 打开 http://localhost:5173
```

启动后自动建表（SQLite），无需手动迁移。首次启动自动初始化记忆目录（`~/.lumen/memory/`）。

## Project Structure

```
career-os/
├── app/backend/
│   ├── main.py              # FastAPI 入口，lifespan 中自动 create_all
│   ├── config.py            # pydantic-settings，从根目录 .env 加载
│   ├── db/
│   │   ├── base.py          # SQLAlchemy AsyncEngine + Base 声明
│   │   └── session.py       # get_db 依赖注入（yield + commit/rollback）
│   ├── models/
│   │   ├── user.py           # User + UserProfile（含 profile_data JSON）
│   │   ├── conversation.py   # Conversation + Message
│   │   ├── growth_event.py   # GrowthEvent 事件溯源
│   │   └── agent_trace.py    # AgentTrace 可观测性
│   ├── agent/
│   │   ├── pydantic_agent.py  # PydanticAI Agent 定义 + 动态系统提示词
│   │   ├── tools/             # Agent 工具（memory_search, memory_save, profile）
│   │   ├── llm_router.py     # LLM 路由（多 Provider），流式+非流式
│   │   └── deps.py           # Agent 依赖注入（LumenDeps）
│   ├── routers/
│   │   ├── health.py         # GET /api/health
│   │   ├── chat.py           # POST /api/chat (SSE), GET /api/chat/history, DELETE /api/chat/{id}
│   │   ├── memory.py         # GET /api/memory/stats, /api/memory/list, POST /api/memory/reset
│   │   └── config_router.py  # GET/POST /api/config
│   ├── schemas/
│   │   └── profile.py        # ProfileResponse, ProfileUpdate, SkillItem（含 context）
│   └── services/
│       ├── chat_service.py   # 对话业务：Agent Loop 集成 + SSE 流式输出
│       ├── memory_service.py  # 记忆投影（growth_events → .md）
│       ├── review_service.py  # 后台记忆审查兜底
│       └── summary_service.py # 对话摘要生成
├── app/frontend/
│   └── src/
│       ├── pages/
│       │   ├── Chat.tsx      # SSE 流式对话 + 历史抽屉 + 空态示例
│       │   ├── Profile.tsx   # 画像页：教育详情/技能/获奖 + inline 编辑
│       │   ├── Memories.tsx  # 记忆管理页
│       │   └── Settings.tsx  # 设置页：Provider 选择 + API Key
│       └── lib/
│           ├── api.ts        # 后端 API 调用 + SSE 解析
│           ├── chatSession.tsx # 全局聊天状态管理（Context Provider）
│           └── userId.ts     # 用户 ID 管理
├── tests/                    # pytest 测试用例
├── docs/                     # 设计文档
│   ├── 需求/                 # 用户画像 + 功能需求清单
│   ├── 架构/                 # 系统架构、安全合规
│   └── 功能设计/             # 各核心功能详细设计
├── .github/workflows/        # CI/CD（lint + test + build）
├── Dockerfile                # 多阶段构建（node + python）
├── docker-compose.yml        # 单服务 + 持久化 volume
├── pyproject.toml            # ruff + pytest 配置
└── run.ps1 / run.bat         # 本地开发启动脚本
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/health` | 健康检查 |
| `POST` | `/api/chat` | SSE 流式对话（Agent Loop），body: `{ message, conversation_id?, user_id? }` |
| `GET`  | `/api/chat/history?user_id=&limit=` | 对话历史列表 |
| `GET`  | `/api/chat/{conversation_id}` | 单条会话消息详情 |
| `DELETE` | `/api/chat/{conversation_id}` | 删除对话及其消息 |
| `GET`  | `/api/memory/stats?user_id=` | 记忆统计（状态、数量） |
| `GET`  | `/api/memory/list?user_id=` | 记忆列表 |
| `POST` | `/api/memory/reset?user_id=` | 重置记忆 |
| `GET`  | `/api/config` | 获取当前用户配置 |
| `POST` | `/api/config` | 更新用户配置（API Key 等） |

## Key Architecture Decisions

- **Agent 系统**：PydanticAI 实现（`pydantic_agent.py`），支持工具调用、动态系统提示词、流式输出
- **工具注册**：`@agent.tool` 装饰器注册工具，3 个核心工具：`memory_search`、`memory_save`、`update_profile`
- **LLM 路由**：`llm_router.py` 支持多 Provider（DashScope/OpenAI/DeepSeek 等），通过 LiteLLM 统一调用
- **记忆层**：growth_events → .md 投影（`memory_service.py`），`memory.md` 存核心画像，`entities/*.md` 存技能/经历/偏好等
- **数据库**：SQLite（`lumen.db`），`lifespan` 中 `Base.metadata.create_all` 自动建表
- **画像数据模型**：扩展字段存入 `profile_data` JSON 列，零 ORM 列新增
- **聊天状态**：`chatSession.tsx` 全局 Context Provider，跨页面保持对话状态
- **可观测性**：`agent_traces` 表记录 Agent 推理步骤、工具调用、耗时

## .env

根目录有 `.env` 文件，包含 DashScope API Key 等。**不要提交到 git**。

关键配置：
- `LLM_API_KEY` / `DASHSCOPE_API_KEY` — LLM 调用
- `DATABASE_URL` — 默认 `~/.lumen/lumen.db`
- `DEBUG` — `true`（开发）/ `false`（生产）

## Code Style

- Python 3.11+，类型提示（`from __future__ import annotations`）
- SQLAlchemy 2.0 async（`Mapped[...]`, `mapped_column()`）
- Pydantic v2（`BaseSettings`, `BaseModel`）
- 前端 React 19 + TypeScript + Tailwind CSS 4
- ruff 做 lint + format（`pyproject.toml` 配置）
- pytest + pytest-asyncio（16 条测试，`pytest` 运行）

## Gotchas

- `chat_service.py` 流式对话使用 `db.commit()` 而非 `flush()`，确保用户消息立即落库，流中断不丢失
- `update_profile` 中 `null` 可以清空字段（通过 `model_fields_set` 区分"未传"和"传 null"）
- `chatSession.tsx` 使用 `sessionStorage` 持久化 conversationId，刷新页面不丢失对话

## Known Limitations

- **无认证**：`user_id` 由客户端 localStorage 控制，无 JWT 鉴权。生产环境需加认证
- **单用户模式**：demo_user 硬编码，多用户需改造

## docs/

设计文档在 `docs/` 下：
- `docs/architecture/` — 系统架构设计与核心决策
- `docs/memory-structure/` — 记忆结构（memory.md + entities/*.md）
- `docs/stories/` — 功能实现 story 记录
- `docs/product-brief.md` — 产品简介
- `docs/project-context.md` — AI Agent 编码规则
