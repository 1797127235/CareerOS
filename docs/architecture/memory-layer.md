# Lumen 记忆层架构文档

> 版本：当前代码状态（截至 2026-05-15）
> 状态：已落地
> 适用：单用户本地部署

---

## 1. 设计目标

Lumen 记忆层的核心目标不是"存储所有对话"，而是**让 Agent 真正认识用户**——知道用户是谁、经历过什么、关心什么，并在每次对话时把最相关的背景注入 system prompt。

为此，记忆层需要同时解决三个问题：

1. **画像固定注入**：用户的基本信息、技能、目标必须**每次对话都出现**（L0）
2. **近期上下文**：最近聊了什么，避免 Agent"失忆"（L1）
3. **语义召回**：从海量历史中提取与当前话题相关的内容（L2）

---

## 2. 核心概念

### 2.1 双管线架构（Profile vs Narrative）

记忆层将所有事件分为两类，走完全不同的处理路径：

| 维度 | Profile 管线 | Narrative 管线 |
|------|-------------|----------------|
| **语义** | 用户「是谁」— 身份、技能、目标、偏好 | 用户「经历了什么」— 经历、决策、笔记 |
| **事件类型** | `profile_updated`, `skill_added`, `skill_level_changed`, `goal_updated`, `preference_learned`, `status_changed` | `experience_added`, `decision_made`, `note_added` |
| **去向** | `.md` 投影 → L0 固定注入 | FTS5 + LanceDB → L2 按需召回 |
| **搜索** | ❌ 不走搜索索引 | ✅ 全文 + 语义搜索 |
| **去重** | `dedupe_key` (SHA256) | 同左 |

**为什么分两路？** Profile 是状态型数据（"用户在学 Rust"），需要聚合去重后呈现，逐条搜索无意义；Narrative 是时间线型数据（"用户上周做了一个决定"），需要语义召回支持时间线查询。

### 2.2 GrowthEvent — 统一事件模型

所有记忆都以 `GrowthEvent` 形式存储，核心字段：

```python
class GrowthEvent(Base):
    id: str           # UUID
    user_id: str      # 用户标识（单用户场景下固定为 demo_user）
    event_type: str   # 事件类型，决定走 Profile 还是 Narrative 管线
    entity_type: str | None   # 实体类型（如 skill, experience, goal）
    entity_id: str | None     # 实体标识（如技能名、经历ID）
    payload_json: str | None  # JSON 载荷，存储具体内容
    source: str       # 来源（system / user_upload / 用户主动）
    created_at: datetime
    dedupe_key: str   # SHA256(user_id|type|entity|payload) 去重键
    payload_hash: str # SHA256(payload_json)
    projected_md_at: datetime | None       # .md 投影时间戳
    projected_provider_at: datetime | None # Provider 语义索引时间戳
```

`projected_md_at` 和 `projected_provider_at` 是两个游标，支持断点续传式的增量同步。

### 2.3 L0/L1/L2 分层注入

Agent 的 system prompt 中，记忆上下文按三层注入：

```
<memory-context>
[System note: ...]

## AI 对你的理解        ← L0: 固定块（about_you.md / memory.md）
...

## 近期对话              ← L1: 最近 7 天、最多 5 个对话的摘要
...

【相关记忆】             ← L2: 按 user_input 语义召回的 8 条记忆
- ...

【对话摘要】             ← 当前对话的 running summary（可选）
...
</memory-context>
```

| 层级 | 数据源 | 更新频率 | 缓存策略 |
|------|--------|---------|---------|
| L0 | `about_you.md` → `memory.md` | 每次写入后重建 | 5min TTL |
| L1 | `Conversation` + `Message` 表 | 每次对话前查询 | 5min TTL |
| L2 | `GrowthEvent`(narrative) + `external_items` | 实时查询 | 无缓存 |

---

## 3. 架构总览

### 3.1 组件拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent / API                               │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────────┐
        │  remember │   │  recall  │   │ build_context │
        │   写入    │   │   搜索   │   │  构建 prompt │
        └────┬─────┘   └────┬─────┘   └──────┬───────┘
             │              │                │
             ▼              ▼                ▼
    ┌─────────────────────────────────────────────────────┐
    │                  LumenMemory (门面)                  │
    │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │ MemoryWriter│  │MemorySearcher│  │ProjectionManager│
    │  └─────────────┘  └──────────────┘  └────────────┘  │
    └─────────────────────────────────────────────────────┘
             │              │                │
             ▼              ▼                ▼
    ┌─────────────────────────────────────────────────────┐
    │                   SQLite (lumen.db)                  │
    │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │growth_events│  │external_items│  │ingestion_state│ │
    │  │  + FTS5     │  │   + FTS5     │  │            │  │
    │  │  触发器     │  │   触发器     │  │            │  │
    │  └─────────────┘  └──────────────┘  └────────────┘  │
    └─────────────────────────────────────────────────────┘
             │              ▲                │
             ▼              │                ▼
    ┌─────────────────┐    │         ┌──────────────┐
    │  ~/.lumen/memory│    │         │  LanceDB     │
    │  /{user_id}/    │    │         │  (向量搜索)   │
    │                 │    │         │              │
    │  memory.md      │────┘         │  all-MiniLM  │
    │  about_you.md   │              │  384dim      │
    │  patterns.md    │              └──────────────┘
    └─────────────────┘
```

### 3.2 统一门面 — LumenMemory

`LumenMemory` 通过多重继承组合三个职责：

```python
class LumenMemory(MemoryWriter, MemorySearcher, ProjectionManager):
    async def remember(self, ...):
        # db=None → 自开 session → 写入 → 投影 → commit
        # db=传入 → 仅 flush，调用方负责 commit + 投影
```

**设计意图**：
- `MemoryWriter`：纯写入逻辑，不感知 session 生命周期
- `MemorySearcher`：搜索召回，不感知写入
- `ProjectionManager`：投影同步，可独立调用
- `LumenMemory`：编排事务边界，保证"写入 + .md 投影"原子提交

---

## 4. 写入流程

### 4.1 单条写入

```
Agent 调用 remember(user_id, event_type, payload)
        │
        ▼
┌─────────────────┐
│ MemoryWriter    │
│ _write_events() │────▶ GrowthEventRepository.create_with_dedup()
└─────────────────┘              │
                                 ▼
                    ┌────────────────────────┐
                    │ 1. 计算 payload_hash   │
                    │ 2. 计算 dedupe_key     │
                    │ 3. 查询是否已存在      │
                    │ 4. 存在 → 返回 None    │
                    │ 5. 不存在 → flush      │
                    └────────────────────────┘
                                 │
        ┌────────────────────────┘
        ▼
┌─────────────────┐
│ ProjectionManager│
│ sync_projections()│
└─────────────────┘
        │
        ├──► Phase 1: sync_user_md_projection()
        │         ├── dirty_count == 0 → 跳过
        │         └── dirty_count > 0  → 全量重建 memory.md
        │
        ├──► Phase 2: invalidate_cache() + 后台 update_ai_understanding()
        │         └── 生成 about_you.md（LLM 驱动，5min 防抖）
        │
        └──► Phase 3: _sync_narrative_to_provider()
                  └── 未同步的 Narrative 事件 → LanceDB.sync_document()
```

### 4.2 事务边界

```python
# facade.py
async with get_async_session_maker()() as session:
    event = await MemoryWriter.remember(..., db=session)      # flush
    await ProjectionManager.sync_projections(..., db=session)  # flush（同 session）
    await session.commit()                                      # 原子提交
```

- Phase 1（.md 投影）参与主事务：失败则写入回滚
- Phase 2/3 在 commit 后执行：失败不影响已提交的数据

### 4.3 去重机制

```python
# relational_store.py
payload_hash = SHA256(payload_json)
dedupe_key = SHA256(f"{user_id}|{event_type}|{entity_type}|{entity_id}|{payload_hash}")
```

DB 层有唯一约束 `uq_growth_events_user_dedupe`，重复事件静默跳过。

---

## 5. 读取流程 — build_context

### 5.1 分层构建

```python
# searcher.py
async def build_context(user_id, user_input, *, conversation_summary=None):
    static_ctx = await build_snapshot(user_id)   # L0 + L1
    # L2 语义召回
    items = await self.recall(user_id, user_input, limit=8)
    ...
```

### 5.2 L0 固定块 — 用户画像

```python
# snapshot.py
def _build_fixed_block(user_id):
    about_you = read_about_you(user_id)     # AI 综合画像
    if _has_substantive_content(about_you):
        return f"## AI 对你的理解\n{about_you}"

    memory = read_memory(user_id)           # 结构化画像
    if _has_substantive_content(memory):
        return f"## 用户画像\n{memory}"

    return ""
```

**可用性判断**：排除模板占位符（`（待填写）`、`_暂无记录_`），低于 30 字符视为无效。

### 5.3 L1 近期对话

```python
# snapshot.py
async def _fetch_recent_conversations(user_id, db):
    # 最近 7 天、状态 active、最多 5 个对话
    # 每个对话最多 3 条最新消息
    # 总字符上限 600
```

**关键隔离**：L1 数据源是 `Conversation + Message` 表，与 L0（`.md` 文件）和 L2（`GrowthEvent`）物理隔离，天然不重复。

### 5.4 L2 语义召回 — search_all

```python
# search.py
async def search_all(user_id, query, limit=10):
    seen = set()
    results = []

    # 1. Provider 语义搜索
    provider_results = await _search_provider(query, limit)
    ...

    # 2. FTS5 关键词 — narrative 事件
    fts5_results = await _search_fts5(user_id, query, limit, seen)
    ...

    # 3. FTS5 关键词 — 外部文档
    ext_results = await _search_external_fts5(query, limit, seen, user_id)
    ...

    return results[:limit]
```

**三路召回策略**：

| 管线 | 后端 | 覆盖数据 | ID 格式 |
|------|------|---------|---------|
| Provider | LanceDB | narrative 事件 + 外部文档 | `narrative:{uuid}` / 原始 doc_id |
| FTS5 narrative | SQLite FTS5 | `growth_events_fts` | 裸 UUID |
| FTS5 external | SQLite FTS5 | `external_items_fts` | `ext:{id}` |

**去重**：`seen: set[str]` 按 `id` 去重。Provider 返回的 narrative 事件去除 `narrative:` 前缀后与 FTS5 的 UUID 一致，自然去重。

**FTS5 查询安全**：
```python
_FTS5_SPECIAL_RE = re.compile(r'[+\-*"()^@]')
# 移除所有操作符，保留中英文和数字
```

**CJK 支持**：
- 3 字符以上 CJK 走 `trigram` tokenizer
- 1-2 字符 CJK 降级为 `LIKE '%query%'` fallback

---

## 6. 投影机制

### 6.1 .md 投影 — 结构化画像

`project_user_to_md()` 全量重建 `memory.md`：

```python
# markdown.py
events_by_type = groupby(event_type)
profile = merge_profile_events(events_by_type["profile_updated"])
skills = merge_skill_events(events_by_type["skill_added"] + events_by_type["skill_level_changed"])
experiences = merge_experience_events(events_by_type["experience_added"])
...

core = generate_memory_md(profile, preferences, status, goals, decisions)
skills_section = _build_skills_section(skills)
exp_section = _build_experiences_section(experiences)

combined = core + "\n\n" + skills_section + "\n\n" + exp_section
_write_md_file_safe(memory.md, combined, max_chars=14000)
```

**原子写**：`NamedTemporaryFile` → `os.replace()`，避免写一半崩溃导致文件损坏。

**字符限制**：
- `memory.md` 上限 8000 字符
- `about_you.md` 上限 2000 字符
- 合计约 14000 字符

### 6.2 FTS5 索引 — 自动维护

SQLite 触发器自动同步：

```sql
-- 插入 growth_events 后，自动写入 growth_events_fts
CREATE TRIGGER IF NOT EXISTS trg_growth_events_fts_insert
AFTER INSERT ON growth_events
BEGIN
    INSERT INTO growth_events_fts(rowid, content)
    VALUES (NEW.rowid, NEW.payload_json || ' ' || COALESCE(NEW.entity_type, ''));
END;

-- 删除后自动清理
CREATE TRIGGER IF NOT EXISTS trg_growth_events_fts_delete
AFTER DELETE ON growth_events
BEGIN
    DELETE FROM growth_events_fts WHERE rowid = OLD.rowid;
END;
```

**双表策略**：
- `growth_events_fts` — 默认 tokenizer（适合英文词干）
- `growth_events_fts_trigram` — `tokenize='trigram'`（适合 CJK 子串搜索）

查询时动态选择：
```python
fts_table = "growth_events_fts_trigram" if _CJK_RE.search(query) else "growth_events_fts"
```

### 6.3 Provider 语义索引 — LanceDB

```python
# lancedb.py
class LanceDBProvider(DocumentIndexProvider):
    def _blocking_initialize(self):
        self._db = lancedb.connect(str(self._db_path))
        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        # schema: id, doc_id, chunk_text, vector(384d), metadata

    async def prefetch(self, query: str) -> list[ProviderHit]:
        query_vec = self._embedder.encode(query).tolist()
        results = self._table.search(query_vec).metric("cosine").limit(10).to_list()
        # score = 1.0 - _distance

    async def sync_document(self, content: str, doc_id: str, metadata: dict):
        chunks = self._chunk_text(content)  # 512/50 overlap
        embeddings = self._embedder.encode(chunks).tolist()
        # 先 delete(doc_id) 再 add()，保证幂等
```

**同步策略**：`ProjectionManager._sync_narrative_to_provider()` 查询 `projected_provider_at IS NULL` 的事件，逐条写入 LanceDB。成功则更新时间戳，失败（try/except 保护）留待下次重试。

### 6.4 AI 综合画像 — about_you.md

```python
# understanding.py
async def update_ai_understanding(user_id):
    # 1. 防抖：5 分钟窗口，同一用户并发任务去重
    # 2. 读取 memory.md 作为输入（而非原始事件列表，消除重复开销）
    # 3. 调用 PydanticAI Agent 生成 300-500 字自然语言画像
    # 4. 写入 about_you.md（带元数据注释）
```

---

## 7. 外部数据接入

### 7.1 IngestionPipeline

```
FilesystemConnector.scan()
        │
        ▼
   RawBytes → parse_raw_bytes() → StructuredDocument
        │
   ┌────┴────┐
   ▼         ▼
[dedup]  [batch buffer]
IngestionStore  _flush_batch()
is_indexed()    │
                ▼
           SQLite UPSERT
           external_items
           + FTS5 触发器自动索引
                │
                ▼
           memory_queue
           (asyncio.Queue, maxsize=1000)
                │
                ▼
           LanceDB.sync_document()
           （语义索引，最终一致性）
```

**批量**：`batch_size=100` 或 `flush_interval=5s`。

**背压**：`asyncio.Queue(maxsize=1000)`，队列满时 `put()` 挂起，对上游产生背压。

**异步语义索引**：`_memory_worker()` 后台消费队列，重试 3 次后放弃（不影响 DB 状态）。

### 7.2 文件监听

`FilesystemConnector` 基于 `watchdog`：
- `on_modified/on_created` → 1.5 秒防抖（应对 Obsidian 自动保存的连续触发）
- `on_deleted/on_moved` → 立即回调，从 DB + Store + LanceDB 中清理

### 7.3 清理

`cleanup_deleted()` 全量扫描后对比 `indexed_ids` 与 `existing_ids`，删除已不存在的条目。

---

## 8. 缓存策略

### 8.1 快照缓存

```python
# snapshot.py
_static_cache: dict[str, _CacheEntry] = {}
_CACHE_TTL_MINUTES = 5
_MAX_CACHE_SIZE = 100
```

- 5 分钟 TTL，过期后重新查询
- LRU 驱逐（最多 100 用户）
- 缓存内容：L0 固定块 + L1 近期对话的拼接结果

### 8.2 缓存失效时机

- 每次 `remember()` 写入后：`invalidate_cache(user_id)`
- `.md` 重建后：`invalidate_cache(user_id)`
- `about_you.md` 生成后：`invalidate_cache(user_id)`

---

## 9. 降级设计

| 场景 | 降级路径 | 影响 |
|------|---------|------|
| LanceDB 未安装 | `NullProvider` → 语义搜索返回空列表 | FTS5 仍可用 |
| `about_you.md` 缺失 | 降级到 `memory.md` | L0 内容变为结构化表格 |
| `memory.md` 空 | 返回「用户画像为空」 | Agent 无背景知识 |
| CJK 短查询（1-2 字）| `LIKE` fallback | 性能略差，结果正确 |
| Provider 同步失败 | 不更新时间戳，下次重试 | 该事件语义搜不到，关键词仍可搜 |
| AI 画像生成失败 | log warning，不影响主流程 | about_you.md 不更新 |

---

## 10. 关键设计决策

### D1：为什么 Profile 不进搜索索引？

Profile 事件（技能、目标、偏好）是**状态型**数据。用户"会 Rust"这个信息不会随时间线变化，需要的是**聚合后的当前状态**（如技能列表），而非"用户分别在 2025-01 和 2025-03 各添加了一次 Rust"这种逐条记录。因此 Profile 事件聚合为 `.md` 后走 L0 固定注入，不走搜索。

### D2：为什么 .md 投影用全量重建而非增量？

单用户场景下，GrowthEvent 数量级可控（长期使用 < 1 万条）。全量重建的优势：
- 逻辑简单，无状态漂移
- 天然支持事件删除后的"回退"（比如用户删了一条经历，增量更新需要处理删除逻辑）
- `.md` 生成是纯函数（输入全部事件 → 输出固定 markdown），可测试、可预测

代价：dirty > 0 时重建全部。当前通过 dirty_count 检查避免无变化时的重建。

### D3：为什么 Provider 语义索引不参与主事务？

LanceDB 是外部 IO，可能因磁盘满、模型异常、进程重启等原因失败。如果参与主事务，会导致**写入失败**——用户说一句"我在学 Rust"，因为 LanceDB 挂了，这句记忆就存不进去。

解耦后：SQLite 写入成功即向用户返回成功，LanceDB 异步同步，失败留待重试。语义搜索临时降级到 FTS5，用户体验不受损。

### D4：为什么用 SQLite FTS5 而非独立搜索引擎？

单用户、本地部署场景下：
- SQLite FTS5 零额外依赖
- 触发器自动维护，应用层零干预
- 与主数据同事务，一致性简单

语义搜索（LanceDB）作为增强层，而非替代层。FTS5 是永久兜底。

### D5：为什么快照缓存 5 分钟？

- 太短：每次对话都重建快照，浪费 IO
- 太长：用户刚更新了画像，Agent 还在用旧版本
- 5 分钟是平衡：对话通常持续 < 5 分钟，一次对话内画像稳定；跨对话时用户修改画像后最多等 5 分钟生效

---

## 11. 文件职责索引

| 文件 | 职责 | 关键类/函数 |
|------|------|-----------|
| `facade.py` | 统一门面，编排事务 | `LumenMemory`, `get_memory()` |
| `writer.py` | 事件写入（仅 flush） | `MemoryWriter`, `EventSpec` |
| `searcher.py` | 搜索召回，构建 system prompt | `MemorySearcher`, `build_context()` |
| `search.py` | 统一搜索（三路召回合并） | `search_all()`, `MemoryItem` |
| `projection.py` | 投影同步与后台任务 | `ProjectionManager`, `sync_projections()` |
| `snapshot.py` | L0/L1 快照构建与缓存 | `build_snapshot()`, `_CacheEntry` |
| `classifier.py` | 双管线路由 | `classify()`, `PROFILE_EVENT_TYPES` |
| `relational_store.py` | 去重写入与 FTS 管理 | `GrowthEventRepository` |
| `markdown.py` | .md 原子读写与投影生成 | `project_user_to_md()`, `sync_user_md_projection()` |
| `events_merger.py` | 事件合并纯函数 | `merge_profile_events()`, `generate_memory_md()` |
| `understanding.py` | AI 综合画像生成 | `update_ai_understanding()` |
| `models.py` | GrowthEvent ORM | `GrowthEvent` |
| `pipeline.py` | 外部数据摄入协调器 | `IngestionPipeline` |
| `document_index_provider.py` | Provider 抽象基类 | `DocumentIndexProvider`, `ProviderHit` |
| `lancedb.py` | LanceDB 向量搜索实现 | `LanceDBProvider` |
| `null.py` | 空实现（降级） | `NullProvider` |
| `provider_factory.py` | Provider 工厂 | `create_document_index_provider()` |
| `local_folder.py` | 本地文件系统连接器 | `LocalFolderConnector` |
| `store.py` | 摄入状态追踪 | `IngestionStore` |
| `connector.py` | Connector ABC | `DataSourceConnector`, `RawBytes` |
| `parser.py` | 文档解析 | `parse_raw_bytes()` |
| `retry.py` | 重试工具 | `jittered_sleep()` |

---

*本文档与代码同步维护。如修改记忆层架构，请同步更新本文档。*
