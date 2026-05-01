# CodePilot · 码路领航

<p align="center">
  <b>面向计算机专业学生的 AI 职业规划智能体</b><br>
  <i>An AI Career Planning Agent for Computer Science Students</i>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> |
  <a href="#功能特性">功能特性</a> |
  <a href="#api-文档">API 文档</a> |
  <a href="#技术栈">技术栈</a> |
  <a href="#开发路线图">路线图</a> |
  <a href="#贡献指南">贡献</a>
</p>

---

## 简介

CodePilot（码路领航）是一位 **24 小时在线、懂计算机行业、陪你从大一走到毕业的 AI 学长**。基于 Multi-Agent 架构，通过自然语言对话为计算机专业在校生提供全周期职业规划服务：

- **方向迷茫** → AI 对话咨询 + 行业全景导览 + 智能方向测评
- **路径不清** → 个性化学习路径生成 + 岗位能力差距分析
- **求职焦虑** → 简历智能解析优化 + 模拟面试 + 求职进度管理

> 一句话：从"方向选择"到"拿到 Offer"的全程 AI 陪伴。

---

## 功能特性

### MVP 阶段（当前）

| 功能 | 状态 | 说明 |
|------|------|------|
| 智能对话式职业咨询 | ✅ | SSE 流式对话，7 大意图分类（方向咨询 / 路径规划 / 简历 / 面试 / 能力分析 / 技术问答 / 情感疏导） |
| 用户画像管理 | ✅ | 简历上传（PDF/DOCX/TXT）→ LLM 自动提取画像 → 手动修正 |
| 学习路径生成 | 🚧 | 根据目标岗位生成结构化学习路线 |
| 能力差距分析 | 🚧 | 技能雷达图对比 + 补全建议 |
| 简历解析优化 | 🚧 | STAR 法则优化、JD 匹配度分析 |
| 模拟面试 | 🚧 | 八股/算法/系统设计/行为面试 |

### 增强版（规划中）

- 项目实践指导与代码 Review
- 求职进度管理看板
- 行业岗位实时数据看板
- 综合测评系统（霍兰德 + 技术偏好）
- Offer 决策分析器
- 学习进度追踪与动态路径调优

---

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| **后端框架** | FastAPI + Uvicorn |
| **ORM** | SQLAlchemy 2.0 (async) |
| **数据库** | SQLite (开发) / PostgreSQL (生产) |
| **LLM 路由** | DashScope (qwen-plus / qwen-max) |
| **Agent 编排** | LangGraph StateGraph（意图分类） |
| **配置管理** | Pydantic Settings v2 |
| **认证** | JWT (python-jose) |
| **文档解析** | pdfplumber + python-docx |

---

## 快速开始

### 环境要求

- Python >= 3.11
- [DashScope API Key](https://dashscope.aliyun.com/)

### 安装

```bash
# 克隆仓库
git clone https://github.com/1797127235/CareerOS.git
cd CareerOS

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DASHSCOPE_API_KEY
```

### 启动

```bash
# 开发模式（含热重载）
python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload

# 访问文档
open http://localhost:8000/docs
```

启动后自动建表（SQLite `career_os.db`），无需手动迁移。

---

## API 文档

### 对话 API

| Method | Path | 描述 |
|--------|------|------|
| `POST` | `/api/chat` | SSE 流式对话 |
| `GET` | `/api/chat/history` | 对话历史列表 |
| `GET` | `/api/chat/{id}` | 单条会话详情 |

### 画像 API

| Method | Path | 描述 |
|--------|------|------|
| `POST` | `/api/profile/resume` | 上传简历，LLM 解析提取画像 |
| `GET` | `/api/profile/me` | 查看当前画像 |
| `PATCH` | `/api/profile/me` | 手动修正画像（局部更新） |

### JD 诊断 API

| Method | Path | 描述 |
|--------|------|------|
| `POST` | `/api/jd/diagnose` | 提交 JD 文本，LLM 对比画像输出匹配评分+技能缺口+优化建议 |

### 健康检查

| Method | Path | 描述 |
|--------|------|------|
| `GET` | `/api/health` | 服务状态 |

交互式 API 文档：`http://localhost:8000/docs`

---

## 项目结构

```
career-os/
├── app/
│   └── backend/
│       ├── main.py              # FastAPI 入口
│       ├── config.py            # 配置管理（Pydantic Settings）
│       ├── db/
│       │   ├── base.py          # SQLAlchemy AsyncEngine + Base
│       │   └── session.py       # get_db 依赖注入
│       ├── models/              # ORM 模型
│       │   ├── user.py          # User + UserProfile
│       │   ├── conversation.py  # Conversation + Message
│       │   ├── learning.py      # LearningPath + PathNode
│       │   ├── resume.py        # Resume
│       │   ├── job.py           # JobApplication + InterviewRecord
│       │   └── ...
│       ├── agent/
│       │   ├── llm_router.py    # LLM 路由（按 task_type 选模型）
│       │   ├── orchestrator.py  # LangGraph 意图分类 + 系统提示词
│       │   ├── rag.py           # 简化版 RAG（MVP）
│       │   └── tools.py         # 工具注册中心
│       ├── routers/
│       │   ├── chat.py          # 对话路由
│       │   ├── profile.py       # 画像路由
│       │   ├── jd.py            # JD 诊断路由
│       │   └── health.py        # 健康检查
│       ├── services/
│       │   ├── chat_service.py  # 对话业务逻辑
│       │   ├── profile_service.py # 画像业务逻辑
│       │   └── jd_service.py    # JD 诊断业务逻辑
│       └── schemas/
│           ├── profile.py       # Pydantic 请求/响应模型
│           └── jd.py            # JD 诊断模型
├── docs/                        # 产品设计文档
│   ├── 需求/                    # 用户画像 + 功能需求清单
│   ├── 架构/                    # 系统架构、技术栈、安全合规
│   └── 功能设计/                # 模块总览、各功能详细设计
├── .env                         # 环境变量（不提交到 git）
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 架构设计

```
用户请求
  → FastAPI Router
    → Service 层（业务逻辑）
      → LangGraph 意图分类（classify）
        → LLM Router（按 task_type 选 qwen-plus/qwen-max）
          → 真流式生成（chat_stream）
      → SQLAlchemy AsyncSession（读写 DB）
    → SSE 响应
```

**关键设计决策**：

- **LangGraph 只做意图分类**：流式生成绕开 StateGraph 直接走 `chat_stream`，兼顾架构清晰度与用户体验
- **LLM 路由硬编码**：`_ROUTE_MAP` 按任务类型选模型，不依赖 `LLM_MODEL` 环境变量
- **上下文窗口**：加载最近 20 条消息，无滑动窗口或摘要（后续迭代）
- **数据库**：开发阶段 SQLite，生产切 PostgreSQL（改 `.env` 中 `DATABASE_URL` 即可）

---

## 开发路线图

| 阶段 | 时间 | 目标 | 核心功能 |
|------|------|------|----------|
| **MVP** | 0-3 个月 | 验证核心价值 | 智能对话、学习路径、简历优化、模拟面试 |
| **增强版** | 4-6 个月 | 完善场景闭环 | 进度管理、Offer 决策、动态调优、成就体系 |
| **生态版** | 7-12 个月 | 构建用户生态 | 社区、导师对接、高校 SaaS、多模态 |

---

## 贡献指南

我们欢迎所有形式的贡献：代码、文档、Issue、建议。

### 开发流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/your-feature`
3. 提交代码：`git commit -m "feat: add something"`
4. 推送到远程：`git push origin feat/your-feature`
5. 创建 Pull Request

### 代码规范

- Python 3.11+，使用类型提示（`from __future__ import annotations`）
- SQLAlchemy 2.0 async 风格（`Mapped[...]`, `mapped_column()`）
- Pydantic v2（`BaseSettings`, `BaseModel`）
- 如无必要，勿增注释；注释只解释 WHY，不解释 WHAT

---

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DASHSCOPE_API_KEY` | ✅ | DashScope API Key（LLM 调用） |
| `DATABASE_URL` | ❌ | 数据库连接串，默认 SQLite |
| `FRONTEND_URL` | ❌ | CORS 白名单，默认 `http://localhost:5173` |

完整配置见 `.env.example`。

---

## 许可证

[MIT License](LICENSE)

---

<p align="center">
  Made with ❤️ for CS students everywhere.
</p>
