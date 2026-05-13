# Data Source Connections 方案

## 目标

Lumen 要做的不是一个单独的“外部数据导入脚本”，而是一个用户可管理的数据源连接系统。

用户应该可以主动建立连接：

- 本地文件夹 / Obsidian
- 单个网页 / 网站
- GitHub 仓库
- Notion / Google Drive / 其他远程服务

系统负责把这些连接里的内容同步到本地索引中，再通过 Agent 工具安全、可追溯地使用。

最小闭环：

```text
用户添加本地文件夹
  -> 系统扫描 Markdown / 文本文件
  -> 文件新增、修改、删除能同步
  -> Agent 能搜索数据源
  -> 回答时带标题、路径、来源和片段
```

## 核心边界

```text
data_sources
  用户建立了哪些连接，以及连接状态。

ingestion
  如何扫描、监听、同步这些连接里的内容。

external_items
  已同步进系统的文档索引。

memory/search
  如何搜索 external_items，并返回可引用结果。

agent/tools
  Agent 被允许如何使用这些数据源。

frontend
  用户如何添加、暂停、重扫、删除数据源连接。
```

关键原则：

- `data_sources` 是产品主模块。
- `ingestion` 只是同步执行层。
- `agent/tools` 是 Agent 使用数据源的权限边界，不是最后随便接一个函数。
- 本地数据源和远程数据源都走同一套 `DataSource` 模型。

## 当前代码基础

当前已经具备的基础：

- `backend/ingestion/connector.py` 有 `DataSourceConnector` 抽象。
- `backend/ingestion/pipeline.py` 已经能写入 `external_items`。
- `backend/ingestion/connectors/filesystem.py` 已经能扫描和监听本地 Markdown / 文本文件。
- `backend/memory/search.py` 已经能搜索 `external_items`。
- `backend/agent/tools/core/*` 已经有工具注册、调度、toolset、策略和 PydanticAI adapter。
- `backend/agent/tools/builtin/external.py` 已经有 `search_external_docs` 雏形。

当前主要缺口：

- 没有 `data_sources` 配置表，数据源还依赖 `.env`。
- `source_id = filesystem` 表示连接器类型，不表示用户建立的某一个连接。
- Agent 工具只叫 `search_external_docs`，语义偏窄，返回来源信息也不够完整。
- 前端没有数据源管理页面。
- `main.py` 里启动逻辑偏重，后续应拆到 startup 模块。

## 数据模型

### data_sources

新增表：`data_sources`

```sql
CREATE TABLE data_sources (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    config_json TEXT NOT NULL DEFAULT '{}',
    credential_ref TEXT,
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    last_sync_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

字段说明：

- `id`: 用户建立的某一个连接，例如 `ds_xxx`。
- `user_id`: 当前先保留 `demo_user`，后续多用户时直接可用。
- `name`: 用户可读名称，例如“我的 Obsidian 工作库”。
- `type`: 连接器类型，例如 `local_folder`、`web_url`、`github_repo`。
- `status`: `active`、`paused`、`error`。
- `config_json`: 非敏感配置，例如本地路径、URL、repo 名称。
- `credential_ref`: 凭据引用。第一阶段可以为空，后续接 OAuth/token。
- `capabilities_json`: 该数据源能力，例如 `scan`、`watch`、`incremental`。
- `last_sync_at`: 最近同步时间。
- `last_error`: 最近同步错误。

### external_items

当前表可以继续叫 `external_items`，但字段要从“按连接器类型”升级成“按用户连接”。

建议目标字段：

```sql
external_items
- id
- user_id
- data_source_id
- connector_type
- external_id
- uri
- title
- content
- content_hash
- metadata_json
- indexed_at
- updated_at
- deleted_at
```

关键点：

- `data_source_id` 是必须字段，用于区分用户添加的不同连接。
- `connector_type` 表示连接器类型。
- `external_id` 表示源系统内的唯一 ID，例如文件绝对路径、URL、GitHub file path。
- `uri` 用于展示和引用，例如 `file:///...`、`https://...`。
- `title` 用于 Agent 和前端展示。
- `deleted_at` 用于软删除。第一阶段也可以物理删除，但最终建议保留软删除能力。

唯一约束：

```sql
UNIQUE(data_source_id, external_id)
```

## 后端目录

新增：

```text
backend/data_sources/
├── __init__.py
├── models.py
├── schemas.py
├── service.py
├── registry.py
└── routes.py
```

职责：

- `models.py`: `DataSource` ORM model。
- `schemas.py`: API 请求/响应模型。
- `service.py`: 新增、暂停、删除、测试连接、触发同步。
- `registry.py`: 注册 `local_folder`、`web_url`、`github_repo` 等 connector。
- `routes.py`: `/api/data-sources` 路由。

保留并改造：

```text
backend/ingestion/
├── connector.py
├── pipeline.py
├── store.py
└── connectors/
    ├── filesystem.py      # 后续可改名 local_folder.py
    ├── web.py             # Phase 2
    └── github.py          # Phase 3
```

## Connector 抽象

当前 `DataSourceConnector` 构造函数里直接带目录配置，适合 demo，不适合用户动态添加连接。

目标接口：

```python
class DataSourceConnector(ABC):
    type: str

    def capabilities(self) -> set[str]:
        return {"scan"}

    async def test_connection(self, source: DataSource) -> ConnectionTestResult:
        ...

    async def scan(self, source: DataSource) -> AsyncIterator[RawDocument]:
        ...

    def start_watching(
        self,
        source: DataSource,
        on_change: Callable[[RawDocument], Coroutine],
        on_delete: Callable[[str, str], Coroutine],
    ) -> WatchHandle | None:
        return None
```

`RawDocument` 目标结构：

```python
@dataclass
class RawDocument:
    user_id: str
    data_source_id: str
    connector_type: str
    external_id: str
    uri: str
    title: str
    content: str
    metadata: dict[str, Any]
```

说明：

- 本地目录支持 `scan` 和 `watch`。
- 远程数据源通常只支持 `scan` 或 `incremental`。
- 不要强迫所有 connector 都实现 watch。

## Ingestion Pipeline

目标职责：

```text
读取 active data_sources
  -> 找到对应 connector
  -> test_connection
  -> scan 或 incremental sync
  -> 计算 content_hash
  -> UPSERT external_items
  -> 更新 data_sources.last_sync_at / last_error
```

第一阶段只做：

- `run_full_scan(data_source_id)`
- `start_watching(data_source_id)`
- `handle_change(raw_document)`
- `handle_delete(data_source_id, external_id)`

删除策略：

- 文件删除后必须让 `external_items` 搜不到。
- 第一阶段可以物理删除。
- 后续建议软删除并记录 `deleted_at`。

## API 设计

新增路由：

```text
GET    /api/data-sources
POST   /api/data-sources
GET    /api/data-sources/{id}
PATCH  /api/data-sources/{id}
DELETE /api/data-sources/{id}
POST   /api/data-sources/{id}/test
POST   /api/data-sources/{id}/sync
POST   /api/data-sources/{id}/pause
POST   /api/data-sources/{id}/resume
```

第一阶段请求示例：

```json
{
  "name": "我的 Obsidian",
  "type": "local_folder",
  "config": {
    "path": "E:/Notes/Obsidian"
  }
}
```

响应示例：

```json
{
  "id": "ds_abc",
  "name": "我的 Obsidian",
  "type": "local_folder",
  "status": "active",
  "capabilities": ["scan", "watch"],
  "last_sync_at": null,
  "last_error": null
}
```

## Agent 工具层

当前工具层已经有：

```text
ToolDefinition
ToolRegistry
ToolDispatcher
ToolsetResolver
ToolRuntimeContext
PydanticAIToolAdapter
PathPolicy
BudgetPolicy
LoopGuardPolicy
ApprovalPolicy
ResultPolicy
```

数据源能力必须正式进入这套工具运行时。

### 工具命名

将 `search_external_docs` 升级为：

```text
data_source_search
data_source_list
data_source_get_item
data_source_status
```

第一阶段必须实现：

```text
data_source_search
```

第二阶段再补：

```text
data_source_list
data_source_get_item
data_source_status
```

### data_source_search

只读工具。

用途：

```text
搜索用户已连接的数据源，返回可引用结果。
```

输入：

```json
{
  "query": "搜索关键词",
  "limit": 5,
  "source_ids": ["ds_xxx"]
}
```

`source_ids` 可选。不传则搜索当前用户全部 active 数据源。

输出必须包含：

```text
title
source_name
uri
snippet
updated_at
item_id
```

示例输出：

```text
找到 2 条数据源结果：

1. Python 项目复盘
来源：我的 Obsidian
路径：file:///E:/Notes/Python项目复盘.md
片段：这里记录了我对 FastAPI 和 SQLite 的实践...
item_id: ext_xxx
```

### data_source_get_item

只读工具。

用途：

```text
按 item_id 读取更完整内容，用于用户追问某一条资料。
```

输入：

```json
{
  "item_id": "ext_xxx",
  "max_chars": 4000
}
```

### data_source_list

只读工具。

用途：

```text
让 Agent 知道当前用户连接了哪些数据源。
```

输出：

```text
- 我的 Obsidian: active, local_folder, last_sync_at=...
- 我的 GitHub: paused, github_repo, last_sync_at=...
```

### data_source_status

只读工具。

用途：

```text
诊断为什么搜不到资料，展示同步状态和错误。
```

### 管理类工具暂不默认开放

不要第一阶段就让 Agent 新增、暂停、删除数据源。

如果后续要做，必须独立 toolset：

```text
data-source-admin
- data_source_create
- data_source_pause
- data_source_resync
- data_source_delete
```

并且这些工具必须：

```python
read_only=False
requires_approval=True
```

默认 `default-chat` 不包含 `data-source-admin`。

## Toolset 设计

目标 toolset：

```text
chat-core
  memory_search
  memory_save
  get_profile
  update_profile

data-source-read
  data_source_search
  data_source_list
  data_source_get_item
  data_source_status

file
  file_read
  file_write
  file_list
  file_search

default-chat
  includes: chat-core, data-source-read
```

注意：

- `file` 工具是项目文件操作工具，不等于用户数据源工具。
- 用户笔记不要通过 `file_read` 让 Agent 随意读。
- 用户笔记应该通过 `data_source_search` 和 `data_source_get_item` 访问，这样才能走权限、索引、引用和审计。

## 工具策略扩展

现有策略还不够，需要补数据源相关策略。

### DataSourcePolicy

职责：

- 检查 `data_source_id` 是否属于当前 `user_id`。
- 检查数据源是否 `active`。
- 检查工具是否允许访问该类型数据源。
- 限制单次返回内容长度。

### SecretPolicy

职责：

- 禁止工具输出 token、credential、完整 `config_json` 中的敏感字段。
- 敏感字段包括 `token`、`api_key`、`password`、`secret`、`authorization`。

### CitationPolicy

职责：

- 强制数据源搜索结果包含 `title`、`source_name`、`uri`、`snippet`。
- Agent 回答外部资料时，应优先基于这些来源组织答案。

第一阶段可以不单独建类，但实现时必须遵守这些规则。

## 前端页面

新增：

```text
src/pages/DataSources.tsx
src/lib/api/dataSources.ts
```

侧边栏新增：

```text
数据源
```

第一版页面功能：

- 添加本地目录。
- 查看数据源列表。
- 查看状态：active / paused / error。
- 查看最近同步时间。
- 手动重新扫描。
- 暂停 / 恢复。
- 删除连接。

第一版不要做：

- OAuth
- Notion
- Google Drive
- 自动网页爬虫
- 插件市场

## 本地与远程的差异

本地数据源：

```text
local_folder / obsidian
  config: path
  capabilities: scan, watch
  sync: 文件系统扫描 + watchdog
```

远程数据源：

```text
web_url
  config: url
  capabilities: scan
  sync: 手动抓取或定时抓取

github_repo
  config: owner, repo, branch, paths
  capabilities: scan, incremental
  sync: GitHub API 或 git clone/pull

notion / drive
  config: workspace/page/folder
  capabilities: scan, incremental, oauth
  sync: API + token + rate limit
```

因此 connector 不应该强制都有 watch。

## 阶段计划

### Phase 1: 本地数据源产品化

目标：

```text
用户能在 UI 添加本地目录，系统能扫描、监听、删除同步，Agent 能搜索并引用。
```

任务：

- 新增 `data_sources` 表。
- 新增 `backend/data_sources` 模块。
- 本地目录从 `.env EXTERNAL_DATA_DIRS` 迁移到数据库配置。
- `external_items` 增加 `data_source_id`、`user_id`、`title`、`uri`。
- `FilesystemConnector` 改为基于 `DataSource` 扫描。
- `search_external_docs` 改为 `data_source_search`。
- 前端新增数据源页面。
- 补测试：新增、扫描、修改、删除、搜索。

### Phase 2: 搜索引用和诊断

目标：

```text
Agent 不只是搜到，还能说明来源；用户也能知道为什么搜不到。
```

任务：

- 增加 `data_source_list`。
- 增加 `data_source_get_item`。
- 增加 `data_source_status`。
- 搜索结果统一返回 `title/source_name/uri/snippet/item_id`。
- 数据源页面展示文件数、最近错误、最近同步时间。

### Phase 3: Web URL

目标：

```text
支持用户添加一个网页 URL，系统抓取正文并进入同一套搜索。
```

任务：

- 新增 `web_url` connector。
- 支持 `POST /api/data-sources` 创建 `web_url`。
- 支持手动重扫。
- 限制抓取大小和超时。
- 记录来源 URL。

### Phase 4: GitHub Repo

目标：

```text
支持连接 GitHub 仓库中的文档和代码说明文件。
```

任务：

- 新增 `github_repo` connector。
- 支持 public repo。
- 后续再支持 token/private repo。
- 默认只索引 `.md`、`.txt`、`README`、`docs/`。

### Phase 5: OAuth 数据源

目标：

```text
Notion / Google Drive / 远程服务通过 OAuth 或 token 连接。
```

任务：

- 设计 credential 存储。
- 增加 token 刷新。
- 增加 rate limit。
- 增加同步 cursor。

## 不做什么

当前阶段不做：

- 不做插件市场。
- 不做多 Agent Hub。
- 不做完整 MCP 平台。
- 不做复杂向量库优先架构。
- 不让 Agent 默认管理数据源连接。
- 不让 Agent 通过 `file_read` 直接读用户笔记目录。

## 成功标准

Phase 1 完成时必须满足：

- 用户能添加一个本地 Markdown 目录。
- 首次扫描能把内容写入 `external_items`。
- 修改文件后搜索结果更新。
- 删除文件后旧内容搜不到。
- 中文关键词能搜到结果。
- Agent 调用 `data_source_search` 能返回标题、来源、路径、片段。
- 前端能看到数据源状态和最近同步时间。
- 测试覆盖扫描、修改、删除、搜索。

## 推荐实施顺序

```text
1. 新增 data_sources 表和 service
2. 改 ingestion pipeline 接收 DataSource
3. 改 external_items 写入字段
4. 实现 data_source_search 工具
5. 加 /api/data-sources 路由
6. 加前端 DataSources 页面
7. 补测试
8. 再拆 main.py startup
```

不要先大重构目录。先把“数据源连接”这条产品链路打通。
