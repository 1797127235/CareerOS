# Requirements Document

## Introduction

重构 DocumentIndexProvider（语义搜索 Provider）层。砍掉无用实现（Cognee、HRR），只保留 LanceDB + Null；修复 LanceDB 已知安全/性能问题；增强 ABC 接口（健康检查、生命周期钩子）；加入用户可配置能力（Settings 页面选择 Provider）；改造工厂逻辑；暴露 Provider 状态到 API 实现可观测性。

## Glossary

- **Provider**: DocumentIndexProvider 的具体实现，负责语义搜索的后端存储与召回
- **LanceDB_Provider**: 基于 LanceDB 向量数据库 + sentence-transformers embedding 的语义搜索实现
- **Null_Provider**: 空实现，所有操作为 no-op，用于降级或用户关闭语义搜索时
- **Provider_Factory**: 根据用户配置创建 Provider 实例的工厂模块
- **Provider_ABC**: DocumentIndexProvider 抽象基类，定义所有 Provider 必须实现的接口
- **Settings_Page**: 前端设置页面，用户在此选择 LLM Provider、Embedding Provider 及 Document Index Provider
- **Health_Status**: Provider 运行时健康状态，包含 ready、degraded、error、not_initialized 四种状态
- **Lifecycle_Hook**: Provider 生命周期钩子方法，在特定时机（对话结束、应用关闭）被调用
- **Config_JSON**: 用户运行时配置文件（~/.lumen/config.json），存储用户选择的 Provider 等配置

## Requirements

### Requirement 1: 删除 Cognee 实现

**User Story:** As a 开发者, I want to 移除 CogneeProvider 及其所有关联代码, so that 代码库不再包含已知有缺陷且不再维护的实现。

#### Acceptance Criteria

1. WHEN the application starts, THE Provider_Factory SHALL NOT import or reference CogneeProvider
2. THE codebase SHALL NOT contain the file `providers/cognee.py`
3. THE codebase SHALL NOT contain the file `memory/cognify_loop.py`
4. THE codebase SHALL NOT contain the file `memory/datasets.py`
5. WHEN any module references `cognee_status` or `projected_cognee_at`, THE codebase SHALL replace these references with provider-agnostic equivalents
6. THE Provider_Factory SHALL NOT include "cognee" in its provider registry or auto-detection sequence

### Requirement 2: 删除 HRR 实现

**User Story:** As a 开发者, I want to 移除 HRRProvider 及其所有关联代码, so that 代码库不再包含与 FTS5 功能重叠的低质量实现。

#### Acceptance Criteria

1. WHEN the application starts, THE Provider_Factory SHALL NOT import or reference HRRProvider
2. THE codebase SHALL NOT contain the file `providers/hrr.py`
3. THE Provider_Factory SHALL NOT include "hrr" in its provider registry or auto-detection sequence

### Requirement 3: 修复 LanceDB SQL 注入漏洞

**User Story:** As a 开发者, I want to 修复 LanceDB_Provider 中 delete 操作的 SQL 注入风险, so that 恶意 doc_id 无法注入任意 LanceDB 过滤表达式。

#### Acceptance Criteria

1. WHEN LanceDB_Provider executes a delete operation, THE LanceDB_Provider SHALL sanitize the doc_id parameter by escaping single quotes before constructing the filter expression
2. WHEN a doc_id contains single quote characters, THE LanceDB_Provider SHALL escape each single quote as two consecutive single quotes in the filter expression
3. WHEN a doc_id contains other special characters, THE LanceDB_Provider SHALL process the delete operation without error

### Requirement 4: 修复 LanceDB 初始化阻塞事件循环

**User Story:** As a 开发者, I want to 将 LanceDB_Provider 的 initialize 方法改为异步执行, so that embedding 模型加载不阻塞主事件循环。

#### Acceptance Criteria

1. WHEN LanceDB_Provider initializes, THE LanceDB_Provider SHALL execute the embedding model loading in a separate thread via asyncio.to_thread
2. WHEN LanceDB_Provider initializes, THE LanceDB_Provider SHALL execute the LanceDB connection and table creation in a separate thread via asyncio.to_thread
3. WHILE LanceDB_Provider is initializing, THE application event loop SHALL remain responsive to other coroutines
4. IF LanceDB_Provider initialization fails, THEN THE LanceDB_Provider SHALL set its health status to error and log the failure details

### Requirement 5: Provider ABC 接口增加健康检查

**User Story:** As a 开发者, I want to Provider_ABC 提供标准化的健康状态查询接口, so that 调用方可以在运行时判断 Provider 是否正常工作。

#### Acceptance Criteria

1. THE Provider_ABC SHALL define an abstract method `health_check` that returns a Health_Status value
2. THE Health_Status SHALL be one of: "ready", "degraded", "error", "not_initialized"
3. WHEN LanceDB_Provider is successfully initialized and operational, THE LanceDB_Provider health_check SHALL return "ready"
4. WHEN LanceDB_Provider encounters a recoverable issue, THE LanceDB_Provider health_check SHALL return "degraded"
5. WHEN LanceDB_Provider initialization has failed, THE LanceDB_Provider health_check SHALL return "error"
6. WHEN Null_Provider health_check is called, THE Null_Provider SHALL return "ready"

### Requirement 6: Provider ABC 接口增加生命周期钩子

**User Story:** As a 开发者, I want to Provider_ABC 提供生命周期钩子方法, so that Provider 可以在对话结束或应用关闭时执行清理和 flush 操作。

#### Acceptance Criteria

1. THE Provider_ABC SHALL define a method `on_session_end` that is called when a chat session ends
2. THE Provider_ABC SHALL define a method `shutdown` that is called when the application is shutting down
3. WHEN `shutdown` is called on LanceDB_Provider, THE LanceDB_Provider SHALL release database connections and embedding model resources
4. WHEN `on_session_end` is called on Null_Provider, THE Null_Provider SHALL return immediately without performing any operation
5. WHEN `shutdown` is called on Null_Provider, THE Null_Provider SHALL return immediately without performing any operation

### Requirement 7: Provider ABC 接口增加 initialize 异步化

**User Story:** As a 开发者, I want to 将 Provider_ABC 的 initialize 方法签名改为 async, so that 所有 Provider 实现可以在初始化时执行异步 IO 操作而不阻塞事件循环。

#### Acceptance Criteria

1. THE Provider_ABC SHALL define `initialize` as an async method with signature `async def initialize(self) -> None`
2. WHEN Provider_Factory creates a Provider instance, THE Provider_Factory SHALL await the initialize method
3. WHEN Null_Provider initialize is called, THE Null_Provider SHALL complete without performing any blocking operation

### Requirement 8: 用户可配置 Document Index Provider

**User Story:** As a 用户, I want to 在 Settings 页面选择语义搜索 Provider（LanceDB 或关闭）, so that 我可以根据自己的硬件条件决定是否启用语义搜索。

#### Acceptance Criteria

1. THE Config_JSON SHALL support a `document_index_provider` field with allowed values: "lancedb" and "disabled"
2. WHEN the user selects "LanceDB" on the Settings_Page, THE system SHALL save `"document_index_provider": "lancedb"` to Config_JSON
3. WHEN the user selects "关闭" on the Settings_Page, THE system SHALL save `"document_index_provider": "disabled"` to Config_JSON
4. WHEN `document_index_provider` is "disabled", THE Provider_Factory SHALL create a Null_Provider instance
5. WHEN `document_index_provider` is "lancedb", THE Provider_Factory SHALL create a LanceDB_Provider instance
6. IF `document_index_provider` is "lancedb" and LanceDB dependencies are not installed, THEN THE Provider_Factory SHALL fall back to Null_Provider and log a warning
7. WHEN `document_index_provider` is not set in Config_JSON, THE Provider_Factory SHALL default to "lancedb" if dependencies are available, otherwise fall back to Null_Provider

### Requirement 9: Settings 页面展示 Provider 选择 UI

**User Story:** As a 用户, I want to 在 Settings 页面看到语义搜索 Provider 的选择控件, so that 我可以直观地切换或关闭语义搜索功能。

#### Acceptance Criteria

1. THE Settings_Page SHALL display a "语义搜索" section with a provider selector
2. THE provider selector SHALL offer two options: "LanceDB（向量搜索）" and "关闭（仅关键词搜索）"
3. WHEN the user changes the provider selection, THE Settings_Page SHALL call the config update API to persist the choice
4. THE Settings_Page SHALL display the current Provider health status next to the selector
5. WHEN the Provider health status is "ready", THE Settings_Page SHALL display a green indicator
6. WHEN the Provider health status is "error" or "not_initialized", THE Settings_Page SHALL display a red indicator with error description

### Requirement 10: 工厂改造 — 读取用户配置

**User Story:** As a 开发者, I want to Provider_Factory 从 Config_JSON 读取用户选择的 Provider, so that 工厂逻辑与用户配置联动。

#### Acceptance Criteria

1. WHEN Provider_Factory creates a provider, THE Provider_Factory SHALL read the `document_index_provider` field from Config_JSON
2. THE Provider_Factory SHALL only maintain a registry containing LanceDB_Provider and Null_Provider
3. WHEN the configured provider is not recognized, THE Provider_Factory SHALL fall back to Null_Provider and log a warning
4. THE Provider_Factory SHALL NOT use a priority-based auto-detection sequence involving multiple providers

### Requirement 11: Provider 状态暴露到 Health API

**User Story:** As a 开发者, I want to 通过 Health API 暴露当前 Provider 的运行状态, so that 前端和运维可以监控语义搜索后端的健康状况。

#### Acceptance Criteria

1. WHEN the health API endpoint is called, THE health API SHALL include a `document_index_provider` field in the response
2. THE `document_index_provider` field SHALL contain: provider name, health status, and provider type
3. WHEN Provider is LanceDB_Provider and status is "ready", THE health API SHALL return `{"name": "lancedb", "status": "ready", "type": "vector"}`
4. WHEN Provider is Null_Provider, THE health API SHALL return `{"name": "null", "status": "ready", "type": "disabled"}`
5. WHEN Provider health_check returns "error", THE health API SHALL include an `error` field with a human-readable description

### Requirement 12: 清理遗留引用

**User Story:** As a 开发者, I want to 移除代码库中所有对已删除 Provider 的遗留引用, so that 代码库保持一致性且不存在死代码。

#### Acceptance Criteria

1. THE `projection.py` SHALL NOT reference `CogneeProvider` or call `cognee_status()`
2. THE `projection.py` SHALL rename the `projected_cognee_at` tracking field to a provider-agnostic name such as `projected_provider_at`
3. THE `search.py` comment block SHALL NOT reference "Cognee" or "HRR" as available providers
4. THE `startup.py` SHALL NOT import or reference Cognee-related modules
5. WHEN the `reset` method clears provider index, THE `projection.py` SHALL use the generic Provider interface without referencing specific provider names in comments or variable names
