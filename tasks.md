# Lumen 开发任务追踪

> 本文档用于日常任务追踪，详细设计见 `docs/todo/roadmap.md` 和 `.sisyphus/plans/`

---

## ✅ 已完成（2026-05-15）

### 文档整理
- [x] 更新 `AGENTS.md` — 同步代码实际状态（删除 Cognee/HRR 引用、更新 Provider 描述等）
- [x] 更新 `docs/architecture/ingestion-refactor-design.md` — 添加实现状态说明
- [x] 更新 `docs/architecture/external-data-mcp-design.md` — 添加实现偏差说明
- [x] 更新 `docs/architecture/external-data-mcp-design-supplement.md` — 修正 Cognee → LanceDB 引用
- [x] 更新 `docs/memory-structure/memory.md` — 同步代码模板
- [x] 更新 `docs/stories/file-upload-ingestion.md` — 标注未实现 + 架构漂移
- [x] 更新 `docs/stories/file-extraction.md` — 标注未实现 + 架构漂移
- [x] 创建 `docs/architecture/memory-layer.md` — 完整记忆层架构文档
- [x] 创建 `docs/todo/roadmap.md` — 后续开发路线图

### Bug 修复
- [x] **P0-1**: `searcher.py` 删除无效去重判断（`item.id in recent_ids` 永不为真）
- [x] **P0-2**: `projection.py` Provider 同步容错（失败事件不更新时间戳，下次重试）
- [x] **P0-3**: `search.py` 三路搜索并行化（`asyncio.gather` + 职责归一）

---

## 🚧 进行中

*暂无*

---

## 📋 待办（按优先级）

### 🔴 高优先级（本月）

- [x] **并行搜索** — `search.py` 三路搜索改为 `asyncio.gather` 并行，`_search_fts5` / `_search_external_fts5` / `_search_external_like` 职责归一（不再接收 `seen` 参数） ✅ 2026-05-15
- [x] **LanceDB 分块策略改进** — `_chunk_text` 改为语义分块：段落 → 句子 → 硬截断兜底，新增 `_split_sentences` 支持中英文标点 ✅ 2026-05-15
- [x] **.md 投影增量更新** — dirty < 5 时增量更新，避免全量重建（`markdown.py`） ✅ 2026-05-15
- [x] **Provider 健康检测** — `prefetch()`/`sync_document()`/`delete_document()` 运行时异常更新 `_health`，成功恢复 READY（`lancedb.py`） ✅ 2026-05-15
- [x] **语义索引补偿机制** — 后台定时扫描未同步事件并补偿（`projection.py` + `startup.py`） ✅ 2026-05-15

### 🟡 中优先级（三个月内）

- [x] **snapshot.py 解耦 chat 模块** — 定义 `ConversationContext` + `ConversationFetcher` 协议，移除顶部 chat 模型导入，延迟导入兜底 + `set_conversation_fetcher` 注入点 ✅ 2026-05-15
- [x] **搜索时间范围过滤** — `recall()` keyword 模式支持 `time_filter`；FTS5/Provider/External 三路搜索均在各自层面过滤时间（SQL 层 + metadata 解析层） ✅ 2026-05-15
- [ ] **GrowthEvent 软删除** — 增加 `deleted_at` 字段 + 回收站 API

### 🟢 新功能（未来）

- [ ] **记忆版本控制** — `about_you.md` 保留历史版本 + 回滚
- [ ] **Agent 主动洞察** — 外部数据变化后主动提醒用户
- [ ] **对话级记忆开关** — `Conversation.memory_enabled` 字段
- [ ] **GitHub 数据源连接器** — 自动提取项目经历和技术栈
- [ ] **语义去重** — embedding similarity > 0.85 时合并旧事件

---

## 🗂️ 外部计划文档

| 文件 | 内容 |
|------|------|
| `docs/todo/roadmap.md` | 完整路线图（含工作量估算、实现思路、代码片段） |
| `.sisyphus/plans/background-memory-review.md` | 后台记忆审查（Agent fork 审查对话） |
| `.sisyphus/plans/external-data-phase2a.md` | Phase 2a 外部数据接入（本地文件系统 + FTS5） |
| `.sisyphus/plans/resume-upload.md` | 简历上传到画像层 |

---

## 如何更新本文档

- 完成某项：`[ ]` → `[x]`，并在末尾加完成日期
- 新增任务：按优先级插入到对应分区
- 任务变更：同步修改 `docs/todo/roadmap.md` 中的详细设计
