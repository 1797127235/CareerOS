# Lumen 记忆层 Roadmap / 待办清单

> 生成日期：2026-05-15
> 适用范围：记忆层（`backend/modules/memory/` + `backend/modules/data_sources/ingestion/`）
> 状态：持续更新

---

## 一、高优先级修补（建议一个月内完成）

### 0. 画像字段体系与 AI 伴侣定位脱节 ⚠️

| 属性 | 说明 |
|------|------|
| **问题** | `ProfilePayload` 和 Agent 的 `update_profile` 工具仍在使用旧版求职字段集（`school_name`、`gpa`、`target_direction`、`expected_salary`...）。Agent 在对话中向用户询问"你学校是什么"、"期望薪资多少"，与"AI 伴侣"产品定位产生严重角色认知偏差 |
| **影响** | 每次 Agent 调用画像更新工具，都在强化"职业规划助手"而非"越聊越懂你的 AI 伴侣"的角色形象 |
| **修复文件** | `backend/modules/profile/schemas.py`（`ProfilePayload`）、`backend/modules/agent/tools/builtin/profile.py`（`handle_update_profile`）、`backend/modules/agent/pydantic_agent.py`（系统提示词中的画像字段引用） |
| **工作量** | 半天 |
| **实现思路** | 将 `ProfilePayload` 迁移到通用伴侣画像维度：`personality`（性格倾向）、`communication_style`（沟通风格）、`attachment_pattern`（依恋模式）、`stress_response`（压力反应）等。同步修改 Agent 工具的字段列表和提示词文案 |

---

### 0b. 模式洞察（patterns）核心功能空缺 ⚠️

| 属性 | 说明 |
|------|------|
| **问题** | `understanding.py` 第 209 行 `patterns: [],  # 模式洞察待实现`。Profile 页面的"AI 注意到的"区块永远是空的 |
| **影响** | "越聊越懂你"最直观的体现缺失。用户看不到 AI 从对话中提炼出的模式（如"你每次做决定前都会焦虑 2-3 天"），画像只是事件罗列 |
| **修复文件** | `backend/modules/memory/understanding.py`（`_generate_understanding` LLM 调用）、`backend/modules/profile/models.py`（`profile_data` JSON 结构） |
| **工作量** | 1 天 |
| **实现思路** | 在 `update_ai_understanding()` 的 LLM prompt 中要求 AI 同时生成 3-5 条模式洞察，每条包含 `insight`、`category`、`evidence_count`。将 patterns 持久化到 `UserProfile.profile_data["patterns"]` |

---

### 0c. Profile 页面失去主动塑造画像能力 ⚠️

| 属性 | 说明 |
|------|------|
| **问题** | Workstream C 删除简历编辑后，`src/pages/Profile.tsx` 变成了纯只读展示。用户无法主动告诉 AI"我是谁" |
| **影响** | 新用户冷启动困难——聊得少时 AI 完全不了解他；老用户想修正理解时只能等 AI 主动发现 |
| **修复文件** | `src/pages/Profile.tsx`、`src/lib/api/memory.ts`、`backend/modules/memory/router.py` |
| **工作量** | 1-2 天 |
| **实现思路** | 在 Profile 页面增加轻量化的"告诉 AI"入口：兴趣、价值观、重要的人。用户输入后，前端直接调用 `/api/memory/profile-update`（或新建 `/api/memory/tell`）写入对应 event type（`interest_observed`、`value_surfaced`、`relationship_noted`），不走旧版的结构化 CRUD |

---

### 1. search_all 三路搜索串行 → 并行化

| 属性 | 说明 |
|------|------|
| **问题** | Provider、FTS5 narrative、FTS5 external 顺序执行，延迟叠加（~300ms） |
| **影响** | 每次 Agent 触发 `build_context()` 时搜索卡顿，对话响应慢 |
| **修复文件** | `backend/modules/memory/search.py` |
| **工作量** | 1 小时 |
| **实现思路** | `asyncio.gather()` 并行执行三路搜索，各自维护 `seen` set，最后统一去重 |
| **代码片段** | 见下方 "参考实现" |

**参考实现：**
```python
# search.py
provider_results, fts5_results, ext_results = await asyncio.gather(
    _search_provider(query, limit),
    _search_fts5(user_id, query, limit, set()),
    _search_external_fts5(query, limit, set(), user_id),
)
seen: set[str] = set()
results: list[MemoryItem] = []
for batch in (provider_results, fts5_results, ext_results):
    for item in batch:
        if item.id not in seen:
            seen.add(item.id)
            results.append(item)
return results[:limit]
```

---

### 2. LanceDB 分块策略改进 — 硬截断改按语义切分

| 属性 | 说明 |
|------|------|
| **问题** | `LanceDBProvider._chunk_text()` 是 `[text[i:i+512] for i in ...]`，在句子中间切断 |
| **影响** | 中文语义搜索质量差。搜"北京大学"时，"北"和"京大学"被切成两块，完全匹配不到 |
| **修复文件** | `backend/modules/data_sources/ingestion/providers/lancedb.py` |
| **工作量** | 4 小时（含测试） |
| **实现思路** | 优先按段落 `\n\n` 切分，超长段落再按句子 `。！？` 切分，最后才用硬截断兜底 |
| **备注** | 外部文档的 IngestionPipeline 分块（`MAX_CONTENT_CHARS=150000`）不受影响，这是 Provider 内部分块 |

**参考实现：**
```python
def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) < chunk_size:
            current += "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks if chunks else [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - overlap)]
```

---

### 3. .md 投影从「全量重建」改为「阈值触发」

| 属性 | 说明 |
|------|------|
| **问题** | `project_user_to_md()` 每次 dirty > 0 就全量重建。长期使用后事件数增长，响应越来越慢 |
| **影响** | 对话中调用 `remember()` 后，用户感知到明显卡顿（全量重建 + LLM 生成 about_you） |
| **修复文件** | `backend/modules/memory/markdown.py`、`backend/modules/memory/projection.py` |
| **工作量** | 1-2 天 |
| **实现思路** | dirty < 5 时增量更新（只追加/修改对应章节）；dirty >= 5 时保持全量重建 |
| **备注** | 增量更新需处理章节定位（如"技能"章节追加新技能），逻辑比全量重建复杂 |

**参考实现：**
```python
_INCREMENTAL_THRESHOLD = 5

async def sync_user_md_projection(user_id, *, db=None):
    dirty_count = ...  # 现有逻辑
    dirty_events = ... # 查询具体 dirty 事件
    if dirty_count <= _INCREMENTAL_THRESHOLD:
        return await _incremental_update_md(db, user_id, dirty_events)
    return await project_user_to_md(db, user_id)
```

---

### 4. Provider 运行时健康检测

| 属性 | 说明 |
|------|------|
| **问题** | `LanceDBProvider.health_check()` 只返回初始化时的状态，运行时故障完全感知不到 |
| **影响** | LanceDB 挂了（磁盘满、文件损坏）后，`prefetch` 抛异常被 `search.py` 静默吞掉，用户以为语义搜索正常，实际已降级到 FTS5 |
| **修复文件** | `backend/modules/data_sources/ingestion/providers/lancedb.py` |
| **工作量** | 2 小时 |
| **实现思路** | `prefetch()` 捕获异常后更新 `self._health = HealthStatus.ERROR`，让 `/api/health` 能反映问题 |

**参考实现：**
```python
async def prefetch(self, query: str) -> list[ProviderHit]:
    try:
        query_vec = (await asyncio.to_thread(self._embedder.encode, query)).tolist()
        results = self._table.search(query_vec).metric("cosine").limit(10).to_list()
        self._health = HealthStatus.READY
        return [...]
    except Exception as exc:
        self._health = HealthStatus.ERROR
        self._error_msg = str(exc)
        raise  # search.py 会捕获并记录，但 health_check 能反映问题
```

---

### 5. 语义索引失败补偿机制

| 属性 | 说明 |
|------|------|
| **问题** | `pipeline.py` 的 `_memory_worker` 重试 3 次后永久丢弃；`projection.py` 失败事件虽会重试，但如果 LanceDB 长期不可用，恢复后会一次性涌入大量事件 |
| **影响** | 部分文档/事件语义搜不到，用户感知为"AI 失忆" |
| **修复文件** | `backend/modules/memory/projection.py`、`backend/modules/data_sources/ingestion/pipeline.py`、`backend/core/startup.py` |
| **工作量** | 4 小时 |
| **实现思路** | 增加后台定时任务（每 5 分钟），扫描 `projected_provider_at IS NULL` 的事件，分批补偿同步 |

**参考实现：**
```python
# projection.py 中新增
async def _compensation_sync(self, user_id: str) -> None:
    """后台补偿：定期扫描未同步的 narrative 事件。"""
    await self._sync_narrative_to_provider(user_id)

# startup.py lifespan 中注册
async def _start_compensation_loop():
    while True:
        await asyncio.sleep(300)
        await memory._compensation_sync("demo_user")
```

### 6. AGENTS.md 文档与代码不同步

| 属性 | 说明 |
|------|------|
| **问题** | `AGENTS.md` 中仍记载 `/api/memory/profile-structured`、`/api/memory/profile-update`、`/api/memory/upload-resume` 等端点，但这些端点已在 Workstream C 中被删除 |
| **影响** | 新加入的开发者（或 Agent）会按错误文档调用不存在的 API |
| **修复文件** | `AGENTS.md` |
| **工作量** | 30 分钟 |
| **实现思路** | 删除已移除端点的 API 说明；更新"涉及文件"列表；确认前端调用链路无残留 |

---

### 7. Journey 与"此刻"数据重叠

| 属性 | 说明 |
|------|------|
| **问题** | `_get_journey()` 查询"除 `profile_updated` 外的所有事件"，而 `_get_current_status()` 查询 `emotional_pattern` + `value_surfaced`。两者数据范围重叠——`emotional_pattern`/`value_surfaced` 既出现在"此刻"又出现在"你走过的路" |
| **影响** | Journey 时间线和"此刻"状态显示重复信息，用户困惑 |
| **修复文件** | `backend/modules/memory/understanding.py` |
| **工作量** | 1 小时 |
| **实现思路** | `_get_journey()` 改为仅查询 Narrative 管线事件（`significant_moment`、`decision_made`、`reflection_added`、`contradiction_noted`、`relationship_noted`），排除 Profile 管线事件 |

---

### 8. 前端缺少 searchMemory / rebuildMemory API 封装

| 属性 | 说明 |
|------|------|
| **问题** | `memory/router.py` 中有 `/search` 和 `/rebuild` 端点，但 `src/lib/api/memory.ts` 没有对应的 `searchMemory()` 和 `rebuildMemory()` 函数 |
| **影响** | 前端无法调用这两个后端能力（搜索记忆、重建画像） |
| **修复文件** | `src/lib/api/memory.ts`、`src/lib/api.ts` |
| **工作量** | 30 分钟 |

---

## 二、中优先级优化（建议三个月内完成）

### 6. snapshot.py 解耦 chat 模块

| 属性 | 说明 |
|------|------|
| **问题** | `_fetch_recent_conversations` 直接 `from backend.modules.chat.models import Conversation, Message`，memory 模块强依赖 chat 模块 |
| **影响** | 架构耦合，无法独立测试 memory 模块；未来如果 chat 模块重构，snapshot.py 必须同步改 |
| **修复文件** | `backend/modules/memory/snapshot.py`、`backend/modules/chat/service.py` |
| **工作量** | 半天 |
| **实现思路** | `build_snapshot` 接收 `fetch_conversations_fn: Callable` 参数，由调用方注入 |

---

### 7. 搜索支持时间范围过滤

| 属性 | 说明 |
|------|------|
| **问题** | `recall(search_mode="keyword")` 不支持时间过滤。用户说"上周我说的那件事"时，会搜到所有时间的结果 |
| **影响** | 语义召回结果包含过旧信息，干扰 Agent 判断 |
| **修复文件** | `backend/modules/memory/searcher.py`、`backend/modules/memory/search.py` |
| **工作量** | 3 小时 |
| **实现思路** | `recall()` 增加 `time_start`/`time_end` 参数，传递给 `_search_fts5` 和 `_search_provider`（LanceDB 支持 where 过滤） |

---

### 8. GrowthEvent 支持软删除 + 回收站

| 属性 | 说明 |
|------|------|
| **问题** | `delete_event()` 是物理删除（`await db.delete(event)`），误删后无法恢复 |
| **影响** | 用户或 Agent 误删重要记忆后，永久丢失 |
| **修复文件** | `backend/modules/memory/models.py`、`relational_store.py`、`projection.py`、`router.py` |
| **工作量** | 1 天 |
| **实现思路** | 增加 `deleted_at` 字段；删除改为更新 `deleted_at`；查询默认过滤 `IS NULL`；新增 `list_deleted` + `restore` API |

---

## 三、新功能开发

### 9. 记忆版本控制（about_you.md 历史）

| 属性 | 说明 |
|------|------|
| **价值** | 用户可以看到 AI 对自己的理解如何演变，发现偏差时可回滚 |
| **实现文件** | `backend/modules/memory/understanding.py`、`markdown.py`、`router.py` |
| **工作量** | 1 天 |
| **实现思路** | `about_you.md` 更新时复制旧版本到 `about_you.md.{timestamp}.bak`；保留最近 10 个版本；API 增加 history + rollback |

---

### 10. Agent 主动洞察（Proactive Insight）

| 属性 | 说明 |
|------|------|
| **价值** | 不是等用户问，而是 AI 看到外部数据变化后主动提醒 |
| **场景示例** | 用户 Obsidian 新增 3 篇 Rust 笔记 → Agent 主动说："你在学 Rust？需要我更新技能画像吗？" |
| **实现文件** | `backend/modules/data_sources/ingestion/pipeline.py`、`backend/modules/memory/projection.py`、`chat/service.py` |
| **工作量** | 3-5 天 |
| **实现思路** | `IngestionPipeline` 检测到高价值变更（如新技能关键词出现）→ 生成 `insight_suggested` 事件 → 下次 `build_snapshot` 注入提示语 → 或 push 到前端 toast |

---

### 11. 对话级记忆开关

| 属性 | 说明 |
|------|------|
| **价值** | 聊敏感话题时，用户可临时禁用记忆 |
| **实现文件** | `backend/modules/chat/models.py`、`chat/service.py`、`chat/router.py`、前端 `Chat.tsx` |
| **工作量** | 半天 |
| **实现思路** | `Conversation` 表增加 `memory_enabled: bool = True`；`chat/service.py` 调用 `remember()` 前检查该字段；前端增加 🔒 按钮 |

---

### 12. GitHub 数据源连接器

| 属性 | 说明 |
|------|------|
| **价值** | 自动提取用户的项目经历和技术栈，无需手动输入 |
| **实现文件** | `backend/modules/data_sources/ingestion/connectors/github.py`、`data_sources/service.py` |
| **工作量** | 2-3 天（含前端配置界面） |
| **实现思路** | 实现 `DataSourceConnector` 接口；`scan()` 遍历 repo 的 README 和主要代码文件；`start_watching()` 用 webhook 或轮询 |

---

### 13. 语义去重（高级）

| 属性 | 说明 |
|------|------|
| **价值** | 当前 `dedupe_key` 是精确匹配。"我在学 Rust"和"我开始学 Rust 了"语义相同但会被存成两条 |
| **实现文件** | `backend/modules/memory/relational_store.py` 或 `writer.py` |
| **工作量** | 2 天 |
| **实现思路** | 写入前用 embedding 计算新事件与最近 10 条事件的 cosine similarity；similarity > 0.85 时更新旧事件而非插入新事件 |
| **备注** | 需要 embedding 计算，可能增加写入延迟。可作为可选开关 |

---

## 四、建议实施顺序

| 周 | 任务 | 优先级 | 工作量 | 原因 |
|----|------|--------|--------|------|
| W1 | **画像字段 AI 伴侣化** | P0 | 0.5d | 地基问题。Agent 每次更新画像都在问 GPA 和目标公司，所有其他工作都会被这个错误信号拉偏 |
| W1 | **模式洞察实现** | P0 | 1d | "越聊越懂你"最直观的体现。与字段改造并行（一个改写入侧，一个改消费侧） |
| W1 | **并行搜索** | P0 | 1h | 搜索延迟直接影响对话体验，改动极小 |
| W1 | **Provider 健康检测** | P0 | 2h | 诊断能力，改完马上能知道 LanceDB 是否健康 |
| W1-W2 | **LanceDB 分块改进** | P0 | 4h | 语义搜索质量提升，用户感知明显 |
| W2 | **语义索引补偿** | P0 | 4h | 修复"AI 失忆"问题 |
| W2-W3 | **.md 增量更新** | P0 | 1-2d | 解决长期性能衰退 |
| W3 | **软删除 + 回收站** | P1 | 1d | 数据安全基础功能 |
| W3 | **snapshot.py 解耦** | P1 | 0.5d | 架构清理，降低未来重构成本 |
| W4 | **搜索时间过滤** | P1 | 3h | 用户体验提升 |
| W4 | **记忆版本控制** | P2 | 1d | 用户可控性 |
| W4 | **对话级记忆开关** | P2 | 0.5d | 快速实现，价值明确 |
| W5+ | **Agent 主动洞察** | P2 | 3-5d | 差异化功能，需产品设计 |
| W6+ | **GitHub 连接器** | P2 | 2-3d | 外部数据扩展 |
| 未来 | **语义去重** | P3 | 2d | 高级功能，可作为实验开关 |

---

## 五、如何更新本文档

1. 完成某项后，在对应条目末尾添加 `✅ 完成于 YYYY-MM-DD`
2. 新增需求时，按优先级插入到对应分区
3. 如果某项设计变更，同步修改"实现思路"和"修复文件"

---

*本文档与代码同步维护。*
