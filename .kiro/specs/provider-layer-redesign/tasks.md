# Implementation Plan: Provider 层清理与重构

## Overview

分 6 个阶段实施：先删除无效实现并清理引用，再修复 LanceDB 问题，然后增强 ABC 接口，接着改造工厂和配置层，最后实现前端 UI 和 Health API。每个阶段结束有 checkpoint 确保增量可验证。

## Tasks

- [ ] 1. 删除无效 Provider 实现并清理引用
  - [ ] 1.1 删除 Cognee 和 HRR 相关文件
    - 删除 `backend/modules/data_sources/ingestion/providers/cognee.py`
    - 删除 `backend/modules/data_sources/ingestion/providers/hrr.py`
    - 删除 `backend/modules/memory/cognify_loop.py`
    - 删除 `backend/modules/memory/datasets.py`
    - _Requirements: 1.2, 1.3, 1.4, 2.2_

  - [ ] 1.2 清理 projection.py 中的 Cognee 引用
    - 移除 `cognee_status()` 静态方法
    - 将 `projected_cognee_at` 字段引用改为 `projected_provider_at`
    - 移除 `from backend.modules.data_sources.ingestion.providers.cognee import CogneeProvider` 导入
    - 更新 `_sync_narrative_to_provider` 中的 projection_field 参数
    - _Requirements: 12.1, 12.2, 12.5_

  - [ ] 1.3 清理 search.py 中的 Cognee/HRR 注释
    - 更新模块顶部注释，移除 "Cognee/LanceDB/HRR" 改为 "LanceDB"
    - 更新 `_search_provider` 函数注释
    - _Requirements: 12.3_

  - [ ] 1.4 清理 startup.py 中的 Cognee 引用
    - 移除模块顶部关于 Cognee 的注释
    - _Requirements: 12.4_

  - [ ] 1.5 清理 health/router.py 中的 cognee_status 调用
    - 移除 `get_memory().cognee_status()` 调用（后续步骤会重新实现 provider 状态）
    - _Requirements: 12.1_

  - [ ] 1.6 添加 SQLite 迁移：重命名 projected_cognee_at 列
    - 在 `core/migrations.py` 中添加 `ALTER TABLE growth_events RENAME COLUMN projected_cognee_at TO projected_provider_at`
    - 更新 GrowthEvent ORM 模型中的字段名
    - _Requirements: 12.2_

  - [ ] 1.7 清理 memory/__init__.py 和 facade.py 中的 Cognee 引用
    - 移除 `cancel_background_tasks` 中对 cognify_loop 的引用（如有）
    - 移除 facade.py 中的 `cognee_status` 方法或委托
    - _Requirements: 1.5, 12.1_

- [ ] 2. Checkpoint — 确保删除后项目可运行
  - 确保所有测试通过（排除 Cognee/HRR 相关测试），ask the user if questions arise.

- [ ] 3. 增强 Provider ABC 接口
  - [ ] 3.1 修改 document_index_provider.py — 新增 HealthStatus 枚举和 ABC 方法
    - 添加 `HealthStatus` 枚举（ready/degraded/error/not_initialized）
    - 将 `initialize` 签名改为 `async def initialize(self) -> None`
    - 新增 `health_check(self) -> HealthStatus` 方法（默认返回 READY）
    - 新增 `async def on_session_end(self) -> None` 方法（默认空操作）
    - 新增 `async def shutdown(self) -> None` 方法（默认空操作）
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 7.1_

  - [ ] 3.2 更新 NullProvider — 实现新增 ABC 方法
    - `initialize` 改为 async（内容不变）
    - `health_check` 返回 `HealthStatus.READY`
    - `on_session_end` 和 `shutdown` 为空操作
    - _Requirements: 5.6, 6.4, 6.5, 7.3_

  - [ ] 3.3 更新 LanceDBProvider — 实现异步初始化、健康检查、生命周期钩子
    - 添加 `_health` 状态字段和 `_error_msg` 字段
    - 将 `initialize` 改为 async，内部用 `asyncio.to_thread` 包装阻塞操作
    - 提取 `_blocking_initialize` 方法
    - 实现 `health_check` 返回 `self._health`
    - 实现 `shutdown` 释放 `_embedder`、`_table`、`_db` 引用
    - 修复 `delete_document` 中的单引号转义（`doc_id.replace("'", "''")`）
    - 同步修复 `sync_document` 中的 delete 调用也使用转义
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 5.3, 5.4, 5.5, 6.3_

  - [ ]* 3.4 编写 Property Test — 单引号转义正确性
    - **Property 1: 单引号转义正确性**
    - 使用 hypothesis 生成含单引号的随机字符串
    - 验证转义后无裸单引号（所有单引号都成对出现）
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 3.5 编写 Property Test — 特殊字符 doc_id 不导致删除异常
    - **Property 2: 特殊字符 doc_id 不导致删除异常**
    - 使用 hypothesis 生成任意 Unicode 字符串
    - 验证 delete_document 不抛出未捕获异常
    - **Validates: Requirements 3.3**

- [ ] 4. 改造 Provider Factory 和配置层
  - [ ] 4.1 重写 provider_factory.py
    - 移除 Cognee/HRR 注册
    - 只注册 LanceDB + Null
    - 从 `load_user_config()` 读取 `document_index_provider` 字段
    - 将 `create_document_index_provider` 改为 async
    - 处理 "disabled" → NullProvider 映射
    - 处理无效值 → NullProvider 降级 + warning
    - 处理 LanceDB 依赖不可用 → NullProvider 降级
    - _Requirements: 1.1, 1.6, 2.1, 2.3, 8.4, 8.5, 8.6, 8.7, 10.1, 10.2, 10.3, 10.4_

  - [ ] 4.2 更新 pipeline.py 中的 init_pipeline — 适配 async factory
    - `init_pipeline` 改为 async 或在内部 await factory
    - 更新 `_bootstrap_ingestion` 中的调用
    - _Requirements: 7.2_

  - [ ] 4.3 更新 config.py — 支持 document_index_provider 字段
    - `apply_user_config` 中添加 `document_index_provider` 到 `_CONFIG_KEYS`
    - _Requirements: 8.1_

  - [ ] 4.4 更新 config/router.py — ConfigResponse 和 ConfigUpdate 新增字段
    - `ConfigResponse` 新增 `document_index_provider: str` 和 `document_index_provider_status: str`
    - `ConfigUpdate` 新增 `document_index_provider: str | None`
    - GET /api/config 返回当前 provider 配置和状态
    - POST /api/config 支持更新 document_index_provider
    - _Requirements: 8.2, 8.3_

  - [ ]* 4.5 编写 Property Test — 无效 Provider 名称始终降级为 NullProvider
    - **Property 3: 无效 Provider 名称始终降级为 NullProvider**
    - 使用 hypothesis 生成不在 {"lancedb", "disabled"} 中的随机字符串
    - 验证 factory 返回 NullProvider 实例
    - **Validates: Requirements 8.1, 10.3**

- [ ] 5. Checkpoint — 确保后端重构完成
  - 确保所有测试通过，ask the user if questions arise.

- [ ] 6. 实现 Health API 和前端 UI
  - [ ] 6.1 更新 health/router.py — 返回 Provider 状态
    - 移除旧的 `cognee` 字段
    - 新增 `document_index_provider` 字段，包含 name/status/type
    - 当 status 为 error 时包含 error 描述
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ] 6.2 更新 startup.py — shutdown 时调用 provider.shutdown()
    - 在 `_shutdown` 函数中获取 provider 并调用 `await provider.shutdown()`
    - _Requirements: 6.3_

  - [ ] 6.3 更新前端 API 类型定义
    - `Config` 接口新增 `document_index_provider` 和 `document_index_provider_status` 字段
    - 新增 health API 响应类型
    - _Requirements: 9.1_

  - [ ] 6.4 更新 Settings.tsx — 记忆 Tab 新增语义搜索区块
    - 在"记忆"Tab 中添加"语义搜索"section
    - 添加 Provider 下拉选择器（LanceDB / 关闭）
    - 显示当前 Provider 健康状态指示器（绿色/红色圆点）
    - 选择变更时调用 config update API
    - 显示"切换后需重启应用生效"提示
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 6.5 编写单元测试 — Health API 和 Config API
    - 测试 GET /api/health 返回正确的 provider 状态结构
    - 测试 POST /api/config 更新 document_index_provider
    - 测试无效 provider 值的错误处理
    - _Requirements: 11.1, 11.2, 8.2, 8.3_

- [ ] 7. Final checkpoint — 确保全部测试通过
  - 确保所有测试通过，ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 删除文件操作（步骤 1）应在 git 中一次性提交，方便回滚
- `projected_cognee_at` → `projected_provider_at` 的迁移需要在 `core/migrations.py` 中添加，lifespan 启动时自动执行
- Property tests 使用 hypothesis 库，需确认 requirements.txt 中已包含
- 前端改动集中在 Settings.tsx 的"记忆"Tab，不影响其他页面
