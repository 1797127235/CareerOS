# CareerOS 源码结构分析

**项目**: CareerOS（码路领航）
**最后更新**: 2026-05-06

---

## 顶层结构

```
career-os/
├── app/                    # 应用代码
│   ├── backend/            # Python 后端
│   └── frontend/           # React 前端
├── docs/                   # 项目文档
├── tests/                  # 测试用例
├── _bmad/                  # BMad 工作流配置
├── .github/                # GitHub Actions CI/CD
├── Dockerfile              # Docker 多阶段构建
├── docker-compose.yml      # Docker Compose 配置
├── pyproject.toml          # Python 项目配置
├── requirements.txt        # Python 依赖
├── run.bat                 # Windows 启动脚本
├── run.ps1                 # PowerShell 启动脚本
└── .env.example            # 环境变量模板
```

---

## 后端结构 (app/backend/)

```
app/backend/
├── main.py                 # FastAPI 入口，lifespan 管理
├── config.py               # pydantic-settings 配置
│
├── db/                     # 数据库层
│   ├── base.py             # SQLAlchemy AsyncEngine + Base
│   └── session.py          # get_db 依赖注入
│
├── models/                 # SQLAlchemy 模型
│   ├── user.py             # User + UserProfile
│   ├── conversation.py     # Conversation + Message
│   ├── growth_event.py     # GrowthEvent（真相源）
│   ├── skill_record.py     # SkillRecord
│   └── agent_trace.py      # AgentTrace 可观测性
│
├── routers/                # API 路由
│   ├── health.py           # GET /api/health
│   ├── chat.py             # POST /api/chat (SSE)
│   ├── profile.py          # /api/profile/*
│   ├── memory.py           # /api/memory/*
│   ├── skills.py           # /api/skills/*
│   └── config_router.py    # /api/config/*
│
├── schemas/                # Pydantic 模型
│   └── profile.py          # Profile 请求/响应模型
│
├── services/               # 业务逻辑层
│   ├── chat_service.py     # SSE 流式对话
│   ├── profile_service.py  # 简历解析
│   ├── memory_service.py   # .md 文件操作
│   ├── growth_event_service.py  # GrowthEvent CRUD
│   ├── cognee_service.py   # Cognee 封装
│   ├── cognee_projector.py # SQLite → Cognee 投影
│   ├── md_projector.py     # SQLite → .md 投影
│   └── memory_extractor.py # 对话后记忆提取
│
└── agent/                  # AI Agent 层
    ├── pydantic_agent.py   # PydanticAI Agent 定义
    ├── pydantic_tools.py   # Agent 工具注册
    ├── llm_router.py       # LiteLLM 多 Provider 路由
    ├── deps.py             # CareerOSDeps 依赖注入
    ├── cognee_client.py    # Cognee 单例管理
    └── tools.py            # 旧版工具文档
```

### 关键文件说明

| 文件 | 行数 | 职责 |
|------|------|------|
| `main.py` | ~80 | FastAPI 入口，lifespan 中自动 create_all |
| `config.py` | ~100 | pydantic-settings，从 .env + config.json 加载 |
| `pydantic_agent.py` | ~200 | Agent 定义 + 动态 system prompt |
| `pydantic_tools.py` | ~280 | memory_search/update/add 工具 |
| `chat_service.py` | ~300 | SSE 流式输出 + 对话管理 |
| `md_projector.py` | ~620 | 事件 → .md 投影（核心复杂点） |
| `growth_event_service.py` | ~380 | GrowthEvent CRUD + 去重 |

---

## 前端结构 (app/frontend/)

```
app/frontend/
├── package.json            # npm 依赖
├── tsconfig.json           # TypeScript 配置
├── vite.config.ts          # Vite 配置
│
└── src/
    ├── main.tsx            # 路由定义
    ├── App.tsx             # 布局 + 导航
    ├── index.css           # Tailwind v4 主题
    │
    ├── pages/              # 页面组件
    │   ├── Chat.tsx        # 流式对话 + 历史抽屉
    │   ├── Profile.tsx     # 画像管理 + 简历上传
    │   ├── Memories.tsx    # 记忆状态 + 列表
    │   └── Settings.tsx    # Provider 配置
    │
    └── lib/                # 工具函数
        ├── api.ts          # API 调用 + SSE 解析
        ├── chatSession.tsx # 聊天状态 Context
        └── userId.ts       # 用户 ID 管理
```

### 关键文件说明

| 文件 | 行数 | 职责 |
|------|------|------|
| `api.ts` | ~400 | 所有 API 调用 + TypeScript 类型 |
| `chatSession.tsx` | ~180 | 全局聊天状态 Context |
| `Chat.tsx` | ~430 | 流式对话 + 历史抽屉 |
| `Profile.tsx` | ~270 | 画像管理 + 简历上传 |
| `Settings.tsx` | ~400 | Provider 配置表单 |
| `Memories.tsx` | ~130 | 记忆状态展示 |

---

## 测试结构 (tests/)

```
tests/
├── conftest.py             # 测试 fixtures
├── test_agent_loop.py      # Agent 创建和工具注册
├── test_api_health.py      # Health/Profile/Chat API
└── test_chat_api.py        # Chat 历史和简历上传
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| test_agent_loop.py | 6 | Agent 创建、工具注册、system prompt |
| test_api_health.py | 3 | Health、Profile、Chat history |
| test_chat_api.py | 2 | Chat history、简历上传 |
| **总计** | **11** | 核心功能 |

---

## 文档结构 (docs/)

```
docs/
├── project-overview.md     # 项目概览（本文档）
├── architecture.md         # 系统架构
├── source-tree-analysis.md # 源码结构（本文档）
├── api-contracts.md        # API 契约
├── data-models.md          # 数据模型
├── development-guide.md    # 开发指南
│
├── 需求/                   # 需求文档
│   ├── 用户画像与场景.md
│   └── 功能需求清单.md
│
├── 架构/                   # 架构文档
│   ├── 系统整体架构.md
│   └── 安全合规与运维部署.md
│
├── 功能设计/               # 功能设计
│   ├── 智能对话咨询.md
│   ├── 简历优化.md
│   ├── 学习路径与能力分析.md
│   └── 交互与数据模型.md
│
├── 记忆系统产品与架构计划.md
├── 记忆层架构变更.md
├── 记忆架构方案分析.md
├── 长期记忆模块实现规划.md
└── frontend-design.md
```

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python 项目元数据 + ruff/pytest 配置 |
| `requirements.txt` | Python 依赖 |
| `package.json` | Node.js 依赖 |
| `tsconfig.json` | TypeScript 配置 |
| `vite.config.ts` | Vite 构建配置 |
| `Dockerfile` | Docker 多阶段构建 |
| `docker-compose.yml` | Docker Compose 编排 |
| `.env.example` | 环境变量模板 |
| `.pre-commit-config.yaml` | Pre-commit hooks |

---

## 入口点

| 入口 | 文件 | 说明 |
|------|------|------|
| 后端 API | `app/backend/main.py` | FastAPI application |
| 前端开发 | `app/frontend/src/main.tsx` | React 入口 |
| 前端构建 | `app/frontend/vite.config.ts` | Vite 构建 |
| Docker | `Dockerfile` | 多阶段构建 |
| 测试 | `tests/conftest.py` | pytest fixtures |

---

## 依赖关系

### 后端核心依赖

```
fastapi + uvicorn          → Web 框架
sqlalchemy + aiosqlite     → 数据库 ORM
pydantic-ai                → AI Agent 框架
litellm                    → LLM 多 Provider 路由
cognee + kuzu + lancedb    → 记忆层（图 + 向量）
markitdown                 → 简历文本提取
```

### 前端核心依赖

```
react + react-dom          → UI 框架
react-router-dom           → 路由
tailwindcss                → 样式
@radix-ui/react-dialog     → UI 组件
react-markdown             → Markdown 渲染
```
