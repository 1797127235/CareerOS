# Lumen

<p align="center">
  <b>一个真正认识你的 AI 伴侣</b><br>
  <i>本地运行 · 原生桌面 · 隐私优先</i>
</p>

---

## 这是什么

单用户 AI 伴侣桌面应用（Tauri v2）。所有数据存本地，不依赖云端，越用越懂你。

**技术栈**：Tauri v2 (Rust) + FastAPI (Python sidecar) + React 19 + Vite + Tailwind CSS 4 + SQLite + PydanticAI

---

## 快速开始

### 前提

- **Rust**（1.80+）：`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Python**（3.11+）
- **Node.js**（20+）

### 启动

```bash
# 安装前端依赖
npm install

# 安装 Python 依赖
pip install -r requirements.txt

# 配置 API Key（二选一）
# 方式一：编辑 .env
#   LLM_PROVIDER=deepseek
#   LLM_API_KEY=your-key
# 方式二：启动后在设置页填写

# 启动桌面应用（自动启动 Python 后端 + Vite 前端 + Tauri 窗口）
cargo tauri dev
```

一行命令，全部自动拉起。Python 后端作为 sidecar 子进程由 Rust 管理生命周期，关闭窗口自动结束。

---

## 项目结构

```
career-os/
├── src/                  # React 前端
│   ├── pages/            # Chat / Profile / Memories / Settings
│   └── lib/              # API 调用 / 状态管理
├── src-tauri/            # Tauri v2 壳 (Rust)
│   ├── src/
│   │   ├── main.rs       # 桌面入口
│   │   └── lib.rs        # Python sidecar 管理 + Tauri commands
│   ├── tauri.conf.json   # 窗口 / 打包配置
│   └── capabilities/     # 权限声明
├── backend/              # Python FastAPI 后端 (sidecar)
│   ├── main.py           # 入口 + lifespan
│   ├── config.py         # 环境变量 + 用户配置
│   ├── db.py             # SQLAlchemy 引擎与会话
│   ├── models.py         # ORM 模型
│   ├── schemas.py        # Pydantic 请求/响应模型
│   ├── agent/            # PydanticAI Agent + 工具
│   │   ├── pydantic_agent.py
│   │   ├── tools.py          # 工具注册
│   │   └── tool_*.py         # memory_save / memory_search / profile
│   ├── memory/           # 记忆层（事件驱动 + .md 投影 + Cognee 语义索引）
│   │   ├── facade.py         # 统一入口
│   │   ├── snapshot.py       # 分层注入（L0 固定块 + L1 近期块）
│   │   ├── events_merger.py  # 事件合并纯函数
│   │   ├── markdown.py       # .md 文件投影
│   │   ├── relational_store.py  # SQLite + FTS5
│   │   ├── semantic_store.py    # Cognee 封装
│   │   ├── cognify_loop.py      # 后台索引循环
│   │   └── datasets.py          # Dataset 常量
│   ├── services/         # API 路由 + 业务逻辑
│   │   ├── chat.py       # SSE 流式对话 + Agent Loop
│   │   ├── memory.py     # 记忆管理 API
│   │   ├── config.py     # LLM Provider 配置
│   │   ├── health.py     # 健康检查
│   │   ├── summary.py    # 对话摘要
│   │   └── review.py     # 后台记忆审查
│   └── utils/            # json_utils / date_utils
├── public/               # 静态资源
├── docs/                 # 设计文档
├── tests/                # pytest
└── .env                  # API Key 等配置
```

---

## 架构

```
┌──────────────────────────────────────────┐
│  Tauri v2 窗口（React 前端）              │
│  http://localhost:5173 (Vite dev)        │
│           │                              │
│  Vite proxy: /api → 127.0.0.1:8000      │
└───────────┼──────────────────────────────┘
            │ HTTP
┌───────────┼──────────────────────────────┐
│  Rust lib.rs                             │
│  ├─ start_backend()  ← Command::new()    │
│  ├─ stop_backend()   ← kill + wait      │
│  ├─ Tauri commands   ← IPC              │
│  └─ 文件夹监听       ← notify crate      │
└───────────┼──────────────────────────────┘
            │ spawn subprocess
┌───────────┼──────────────────────────────┐
│  Python FastAPI (127.0.0.1:8000)         │
│  ├─ SSE 流式对话 (PydanticAI Agent)      │
│  ├─ 记忆系统 (growth_events → .md → Cognee) │
│  └─ SQLite (单文件，~/.lumen/lumen.db)   │
└──────────────────────────────────────────┘
```

---

## 记忆系统

三层记忆注入 Agent system prompt：

| 层级 | 内容 | 策略 |
|------|------|------|
| L0 固定块 | 身份、目标、技能、偏好 | 全量事件，800 字预算，动态分配 |
| L1 近期块 | 最近动态 | 30 天内，类型衰减过滤，5 分钟 TTL |
| L2 语义召回 | 历史记忆 | Cognee 语义 → FTS5 全文 → .md 兜底 |

数据全部在本地 `~/.lumen/`：
- `lumen.db` — SQLite（事件、对话、FTS5）
- `memory/*.md` — 可读的记忆快照
- `kuzu/` + `lancedb/` — Cognee 图谱与向量
- `config.json` — 用户设置

---

## API 端点

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/chat` | SSE 流式对话 |
| `GET` | `/api/chat/history` | 对话历史 |
| `GET` | `/api/chat/{id}` | 单条会话消息 |
| `DELETE` | `/api/chat/{id}` | 删除对话 |
| `GET` | `/api/memory/me` | 读取画像 |
| `GET` | `/api/memory/stats` | 记忆统计 |
| `GET` | `/api/memory/list` | 事件列表 |
| `GET` | `/api/memory/search` | 多源搜索 |
| `POST` | `/api/memory/reset` | 重置记忆 |
| `POST` | `/api/memory/rebuild` | 重建投影 |
| `DELETE` | `/api/memory/{id}` | 删除事件 |
| `GET` | `/api/config` | 读取配置 |
| `POST` | `/api/config` | 更新配置 |
| `POST` | `/api/config/test` | 测试 LLM 连接 |

---

## 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 桌面壳 | Tauri v2 (Rust) | 体积小（~5MB），原生系统 API，不与 Node 绑定 |
| 后端 | FastAPI (Python sidecar) | 保持现有 Python AI 生态不变 |
| 通信 | HTTP localhost:8000 | 前后端解耦，Vite proxy 同端口无需 CORS |
| Agent | PydanticAI + ReAct Loop | 流式推理，4 个工具，可观测 |
| 数据库 | SQLite (aiosqlite) | 单文件零运维，FTS5 全文搜索 |
| 前端 | React 19 + Tailwind CSS 4 | 现代 UI，OKLCH 配色 |
| 记忆 | growth_events → .md + Cognee | 事件溯源 + 语义索引 |

---

## 开发

```bash
# 仅后端
python -m uvicorn backend.main:app --reload

# 仅前端
npm run dev

# 完整桌面（推荐）
cargo tauri dev

# 测试
pytest

# 打包
cargo tauri build
```

---

## License

[MIT](LICENSE)
