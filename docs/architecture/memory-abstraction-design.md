# Memory Abstraction Layer Design

## 问题

当前 5 个写入入口各自手动编排三层后端（SQLite → .md → Cognee），四段重复代码。Agent 工具漏投 Cognee 的根本原因：没有任何机制强制调用方走完整流程。11 个读取入口各自实现搜索逻辑，无统一入口。`cognee_service.recall()` 语义搜索完全断连。

## 目标

一个门面类 `CareerOSMemory`，对外两个方法：

| 方法 | 语义 | 调用方 |
|------|------|--------|
| `remember(user_id, event_type, payload, source)` | 写一条记忆事件 → 扇出到全部后端 | 5 个写入入口 |
| `recall(user_id, query, limit)` | 语义优先 → 子串 fallback | Agent 工具 + API |
| `build_context(user_id, user_input?)` | 结构化画像 + 相关记忆 | system prompt |

此后任何入口加记忆，一行业务代码不碰后端编排。

## 架构

```
                    CareerOSMemory (facade)
                    ├── remember()  → SQLite → .md → Cognee (fire-and-forget)
                    ├── recall()    → Cognee.search → SQLite LIKE → .md 子串
                    └── build_context() → .md 全量 + Cognee 召回

    内部不新建类，直接调用已有模块:

    app/backend/services/
    ├── careeros_memory.py       ← NEW: 门面类
    ├── growth_event_service.py  ← 已有: SQLite CRUD + dedup
    ├── md_projector.py          ← 已有: .md 投影
    ├── memory_service.py        ← 已有: .md 读写 + 子串搜索
    ├── cognee_projector.py      ← 已有: Cognee 投影
    └── cognee_service.py        ← 已有: Cognee 语义搜索
```

## API 设计

### 事务模型

```
remember(db=None)                remember(db=external_session)
────────────────────            ──────────────────────────────
1. 开 own session               1. 写入 external session (flush)
2. create_growth_event          2. 不 commit
3. db.commit()                  3. 不 sync .md / Cognee
4. sync_user_md_projection          (调用方自己决定何时投影)
5. project_event_ids (bg)
────────────────────            ──────────────────────────────
适用: resume上传、extractor     适用: Agent 工具 (chat_service
     (独立操作)                      的 get_db 统一 commit)
```

### `CareerOSMemory`

```python
class CareerOSMemory:
    """记忆层统一门面。单例，无状态。"""

    async def remember(
        self,
        user_id: str,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: dict | None = None,
        source: str = "system",
        *,
        db: AsyncSession | None = None,   # ← Agent 工具传入 ctx.deps.db
    ) -> GrowthEvent | None:
        """写入一条记忆事件。

        - db 传了:  只写 SQLite (flush, 不 commit)，调用方管理事务
        - db 未传:  自己开 session，一次 commit，同步 .md + Cognee

        1. SQLite: create_growth_event_with_dedup (真相源，去重)
        2. .md:    sync_user_md_projection (db=None 时同步，失败抛)
        3. Cognee: project_event_ids (fire-and-forget，失败只 log)

        返回创建的 GrowthEvent 或 None（去重跳过）。
        """

    async def remember_batch(
        self,
        user_id: str,
        events: list[EventSpec],
        *,
        db: AsyncSession | None = None,
    ) -> list[GrowthEvent]:
        """批量写入——保证同一事务。

        Resume 上传一次产生 N 个事件，走 remember_batch 而非 N 次 remember。
        db 传了就在调用方事务里 flush；db=None 自己开事务、一次 commit。
        """

    async def recall(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """语义搜索记忆，三源合并 + event_id 去重。

        1. Cognee cognee_service.recall() — 语义向量搜索，带 event_id 元数据
        2. SQLite search (LIKE on payload_json + event_type)
        3. .md search_memory() — 子串匹配

        三源按 event_id 去重：Cognee 优先（语义），SQLite 补充，.md 兜底。
        """

    async def build_context(
        self,
        user_id: str,
        user_input: str | None = None,
    ) -> str:
        """构建注入 system prompt 的记忆上下文。

        1. 结构化画像: read_memory + read_skills + read_experiences (全量)
        2. 相关记忆: 如果提供 user_input，Cognee recall 注入相关片段
        返回格式化文本。
        """


class EventSpec(TypedDict, total=False):
    event_type: str
    entity_type: str | None
    entity_id: str | None
    payload: dict | None
    source: str


class MemoryItem(BaseModel):
    id: str                        # event_id (Cognee+SQLite) 或 "md:{file}" (.md)
    content: str
    created_at: str | None = None
    categories: list[str] = Field(default_factory=list)
    source: str = "unknown"        # "cognee" | "sqlite" | "md"
```

### 前置依赖：`cognee_service.recall()` 返回结构化结果

**改前** (line 46):
```python
user_results.append(getattr(result, "text", str(result)))
```

**改后**:
```python
user_results.append({
    "text": getattr(result, "text", str(result)),
    "event_id": metadata.get("event_id"),
    "event_type": metadata.get("event_type"),
    "created_at": metadata.get("created_at"),
})
```

`CareerOSMemory.recall()` 收到结构化结果后，按 `event_id` 去重——三层共用一个 ID 空间。

## 调用方改造

### 写入方 — Agent 工具 (传入 ctx.deps.db)

**改前**（pydantic_tools.py memory_save）:
```python
event = await create_event_and_project_md(
    db=ctx.deps.db,
    user_id=ctx.deps.user_id,
    event_type=_EVENT_TYPE_MAP[entity_type],
    entity_type=entity_type, entity_id=section,
    payload=payload, source="Agent工具",
)
```

**改后**:
```python
memory = CareerOSMemory()
event = await memory.remember(
    user_id=ctx.deps.user_id,
    event_type=_EVENT_TYPE_MAP[entity_type],
    entity_type=entity_type,
    entity_id=section,
    payload=payload,
    source="Agent工具",
    db=ctx.deps.db,      # ← 复用 Agent 的 session
)
```

**注意**: Agent 工具调用后不 commit——由 chat_service.py 的 get_db 依赖注入在请求结束时统一 commit/rollback。`remember()` 只 flush。

### 写入方 — Resume 上传 (批量，外部 session)

**改前**（profile_service.py）:
```python
async with get_async_session_maker()() as db:
    for skill in decomp.skills:
        skill_event = await create_growth_event_with_dedup(db, ...)
    for exp in decomp.experiences:
        exp_event = await create_growth_event_with_dedup(db, ...)
    await db.commit()
await sync_user_md_projection(user_id)
await project_event_ids(event_ids)
```

**改后**:
```python
memory = CareerOSMemory()
events = await memory.remember_batch(
    user_id=user_id,
    events=[
        EventSpec(event_type="skill_added", entity_type="skill",
                  entity_id=s.name, payload=SkillPayload(...).model_dump(),
                  source="简历提取")
        for s in decomp.skills
    ] + [
        EventSpec(event_type="experience_added", entity_type="experience",
                  entity_id=e.title, payload=ExperiencePayload(...).model_dump(),
                  source="简历提取")
        for e in decomp.experiences
    ],
    # db=None → 内部开事务、commit、同步 .md + Cognee
)
```

### 写入方 — 对话后提取 (memory_extractor)

**改前**:
```python
for event in events:
    created = await create_growth_event_with_dedup(db, user_id, ...)
    if created: success_count += 1
await db.commit()
await sync_user_md_projection(user_id)
await project_event_ids(event_ids)
```

**改后**:
```python
memory = CareerOSMemory()
events = await memory.remember_batch(user_id, events=event_specs)
success_count = len(events)
```

### 读取方 — System prompt

**改前**（pydantic_agent.py dynamic_prompt）:
```python
memory_content = read_memory(uid)
skills_content = read_skills(uid)
exp_content = read_experiences(uid)
# 全量 dump
```

**改后**:
```python
memory = CareerOSMemory()
context = await memory.build_context(
    uid,
    user_input=ctx.deps.current_user_input,
)
```

### 读取方 — Agent 工具

**改前**（memory_search）:
```python
results = search_memory(uid, query)
```

**改后**:
```python
memory = CareerOSMemory()
items = await memory.recall(uid, query)
```

### 读取方 — API endpoint

**改前**（memory.py /search）:
```python
# SQLite LIKE
# search_memory() 子串
```

**改后**:
```python
memory = CareerOSMemory()
items = await memory.recall(user_id, query, limit=limit)
```

## 不变的部分

- `schemas/memory_events.py` — 数据契约不变（已有统一入口）
- `growth_event_service.py` — SQLite CRUD 作为内部实现
- `md_projector.py` — .md 投影作为内部实现，`create_event_and_project_md` 标记 @deprecated
- `cognee_projector.py` + `cognee_service.py` — 作为内部实现
- `memory_limits.py` + `memory_templates.py` — 不变
- `memory_extractor.py` — 改为调用 `CareerOSMemory.remember()`
- `chat_service.py` — 启动 Cognee log 调用不变

## 实现步骤

0. **前置**: `cognee_service.recall()` 返回结构化 dict 而非裸字符串（带 event_id 元数据）
1. 新增 `app/backend/services/careeros_memory.py` — CareerOSMemory 类 + EventSpec + MemoryItem
2. Agent 工具改造: `pydantic_tools.py` memory_save / update_profile / memory_search / get_profile
3. Resume 改造: `profile_service.py` → `remember_batch()`
4. Extractor 改造: `memory_extractor.py` → `remember_batch()`
5. System prompt 改造: `pydantic_agent.py` dynamic_prompt → `build_context()`
6. Router 改造: `profile.py` / `memory.py` → `recall()` / `remember()`
7. 清理: `create_event_and_project_md` 标记 deprecated（内部保留，不删）
8. 验证: 工具写 → Cognee 可召回；API 搜索 → Cognee 语义结果

## 不做的

- 不引入插件系统（三层固定，不需要 Hermes 的 Provider 注册）
- 不拆分 backend 子模块（三个后端各已有独立文件）
- 不改 `memory_limits` / `memory_templates`
- 不迁移现有数据
- 不删 `create_event_and_project_md`（标记 deprecated，向后兼容）
