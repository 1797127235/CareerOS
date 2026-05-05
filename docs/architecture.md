# CareerOS 系统架构

**项目**: CareerOS（码路领航）
**架构模式**: 分层架构 + 事件驱动记忆系统
**最后更新**: 2026-05-06

---

## 1. 架构概览

CareerOS 采用前后端分离的分层架构，后端使用 FastAPI + SQLAlchemy，前端使用 React + Vite。核心创新在于事件驱动的记忆系统，实现了"越用越懂你"的个性化体验。

### 1.1 系统层次

```
┌──────────────────────────────────────────────────────────────┐
│                      Presentation Layer                       │
│                    React 19 + TypeScript                      │
│         Chat / Profile / Memories / Settings                 │
└──────────────────────────────────────────────────────────────┘
                              │
                         REST + SSE
                              │
┌──────────────────────────────────────────────────────────────┐
│                       API Layer (FastAPI)                     │
│    health / chat / profile / memory / skills / config        │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│   chat_service / profile_service / memory_service            │
│   growth_event_service / cognee_service / md_projector       │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                      Agent Layer                             │
│         PydanticAI Agent + Tools + LLM Router                │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│   SQLite (truth) → .md files (projection) → Cognee (index)  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 核心架构决策

### 2.1 事件驱动记忆系统

**决策**: 使用 growth_events 表作为唯一真相源，通过投影器同步到 .md 文件和 Cognee。

**理由**:
- 事件溯源支持时间旅行和审计
- 投影器可以重建任意时间点的状态
- 去重机制防止重复事件
- 支持多层记忆（L1/L2/L3）

**实现**:
```
写入路径: Agent 工具 / 对话提取 / 简历上传
    ↓
growth_events (SQLite)
    ↓
┌─────────┴─────────┐
↓                   ↓
.md 投影器      Cognee 投影器
↓                   ↓
memory.md         Cognee 索引
entities/*.md     (Kuzu + LanceDB)
```

### 2.2 单用户模式

**决策**: 当前实现为单用户模式，user_id 由客户端 localStorage 控制。

**理由**:
- 简化初始实现
- 避免认证复杂性
- 适合自托管场景

**未来**: 生产环境需加 JWT 认证。

### 2.3 SQLite 作为主数据库

**决策**: 使用 SQLite + aiosqlite 作为主数据库。

**理由**:
- 零运维，单文件部署
- 适合自托管场景
- 支持 JSON 字段（profile_data）
- 足够单用户性能

---

## 3. 记忆系统架构

### 3.1 三层记忆模型

| 层级 | 存储 | 用途 | 注入时机 |
|------|------|------|---------|
| L1 | conversation messages | 短期上下文 | 最近 20 条消息 |
| L2 | .md 文件 | 结构化画像 | system prompt |
| L3 | Cognee | 语义检索 | 按相关性召回 |

### 3.2 事件类型

| 事件类型 | 实体类型 | 合并规则 |
|---------|---------|---------|
| profile_updated | profile | 递归深合并 |
| skill_added | skill | 按技能名覆盖 |
| skill_level_changed | skill | 按技能名覆盖 |
| experience_added | experience | 追加 |
| preference_learned | preference | 覆盖 |
| decision_made | decision | 追加 |
| status_changed | status | 覆盖 |
| goal_updated | goal | 覆盖 |
| resume_uploaded | profile | 触发全量重建 |

### 3.3 去重机制

- **UNIQUE 约束**: (user_id, dedupe_key)
- **dedupe_key 格式**: `{event_type}:{entity_type}:{entity_id}`
- **冲突处理**: IntegrityError → 跳过创建

### 3.4 投影追踪

- `projected_md_at`: 最后投影到 .md 的时间
- `projected_cognee_at`: 最后投影到 Cognee 的时间
- 增量投影查询: `WHERE projected_md_at IS NULL`

---

## 4. Agent 系统架构

### 4.1 PydanticAI Agent

```python
Agent(
    model=OpenAIChatModel,  # LiteLLM 路由
    deps_type=CareerOSDeps,
    output_type=str,
    system_prompt="...",  # 静态提示词
)

@agent.system_prompt
async def dynamic_prompt(ctx):  # 动态提示词
    # 注入: memory.md + Cognee recall + 历史消息
```

### 4.2 工具注册

| 工具 | 功能 | 写入路径 |
|------|------|---------|
| memory_search | 搜索记忆 | 只读 |
| memory_update | 更新记忆 | growth_events → .md |
| memory_add | 添加记忆 | growth_events → .md |

### 4.3 LLM 路由

- **统一层**: LiteLLM
- **Provider**: DashScope / OpenAI / DeepSeek / Anthropic / Gemini / Ollama / OpenRouter
- **任务路由**: 不同任务使用不同模型

---

## 5. 数据流

### 5.1 对话流程

```
用户消息 → POST /api/chat
    ↓
chat_service.py
    ↓
PydanticAI Agent (ReAct Loop)
    ↓
┌─────────┴─────────┐
↓                   ↓
工具调用          直接回复
↓                   ↓
growth_events     SSE 流式输出
↓
memory_extractor (fire-and-forget)
↓
growth_events
```

### 5.2 简历上传流程

```
上传文件 → POST /api/profile/resume
    ↓
profile_service.py
    ↓
markitdown (文本提取)
    ↓
LLM 解析 (结构化)
    ↓
growth_events (resume_uploaded + profile_updated)
    ↓
.md 投影器 (同步)
    ↓
memory.md + entities/*.md
```

---

## 6. 部署架构

### 6.1 Docker 部署

```yaml
services:
  career-os:
    image: ghcr.io/1797127235/career-os:latest
    ports:
      - "3000:3000"
    volumes:
      - career-data:/root/.careeros
```

### 6.2 数据持久化

```
~/.careeros/
├── career_os.db      # SQLite 数据库
├── memory/           # .md 记忆文件
│   ├── memory.md     # 核心记忆
│   └── entities/     # 实体记忆
├── config.json       # 用户配置
└── cognee_data/      # Cognee 索引
```

---

## 7. 安全考虑

### 7.1 当前状态

- ❌ 无认证（user_id 由客户端控制）
- ❌ 无 HTTPS（需反向代理）
- ❌ 无输入验证（LLM 提示词注入风险）

### 7.2 生产环境建议

- ✅ 添加 JWT 认证
- ✅ 使用 HTTPS
- ✅ 输入验证和净化
- ✅ API 限流
- ✅ 日志脱敏

---

## 8. 性能考虑

### 8.1 当前优化

- SQLite WAL 模式（并发读）
- 异步 IO（aiosqlite）
- SSE 流式输出（避免长等待）
- Fire-and-forget 事件创建

### 8.2 潜在瓶颈

- .md 投影器全量重建（大量事件时）
- Cognee 语义搜索延迟
- LLM 调用延迟

---

## 9. 扩展性

### 9.1 水平扩展

- 当前为单实例部署
- SQLite 不支持多实例写入
- 未来可迁移到 PostgreSQL

### 9.2 功能扩展

- 多用户支持（加认证）
- 团队协作（共享记忆）
- 插件系统（自定义工具）
