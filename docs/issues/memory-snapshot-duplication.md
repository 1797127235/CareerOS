# Memory Snapshot 数据流问题清单

> 仅记录问题现象与根因，不附修改建议。
> ✅ = 已修复 | ⚠️ = 需要架构决策 | ❌ = 未修复

## 1. L0 与 L1 消费同一数据源，无互斥边界 ✅ 已修复

- **现象**：`build_snapshot()` 内，L0 固定块（`_build_fixed_block_v2`）和 L1 近期块（`_build_recent_block`）都从 `GrowthEvent` 全表读取并合并。
- **根因**：没有机制标记哪些事件已被 L0 "消费"。
- **修复**：L0 改为仅读取 `about_you.md`（AI 综合画像），L1 改为读取 `Conversation` + `Message`（近期对话摘要），数据源完全分离。

## 2. about_you.md 生成与 snapshot 构建存在竞态 ✅ 已修复

- **现象**：`flush_projections()` 里 `asyncio.create_task` 后台写 about_you.md，`build_snapshot()` 同步读取同一个文件。
- **根因**：`invalidate_cache` 在后台任务完成前就被调用，snapshot 读到旧版 about_you.md。
- **修复**：移除 `sync_projections` 中过早的 `invalidate_cache` 调用，仅保留 `_update_understanding` 完成后的那次。缓存只在 about_you.md 落盘后才失效。

## 3. L0→L1 去重完全缺失 ✅ 已不再适用

- **现象**：`facade.py` 的 `build_context()` 只做了 L1→L2 去重。
- **根因**：架构设计时只考虑了 L2 与 L1 的重复。
- **修复**：L0（about_you.md 聚合态）和 L1（Conversation/Message 摘要态）数据源已分离，不存在语义重复风险。

## 4. _build_fixed_block_v2 的降级逻辑不解决重复问题 ✅ 已不再适用

- **现象**：`about_you.md` 为空时降级到直接读取 GrowthEvent。
- **根因**：降级只是换了一种渲染格式。
- **修复**：`_build_fixed_block_v2` 不再有降级分支，仅返回 about_you.md 或空字符串。

## 5. _static_cache 只缓存字符串，丢失结构化元数据 ✅ 已修复

- **现象**：缓存只有最终 markdown 字符串，无事件覆盖信息。
- **根因**：缓存设计只考虑了"加速读取"。
- **修复**：`CacheEntry` 新增 `about_you_event_count` 和 `about_you_generated_at` 字段，从 about_you.md 元数据行解析填入。缓存操作加 `asyncio.Lock` 防并发。

## 6. _build_fixed_block_v2 返回类型不透明 ⚠️ 已缓解

- **现象**：返回 `str`，调用方无法判断数据源。
- **根因**：返回类型未携带元信息。
- **缓解**：about_you.md 文件内嵌 HTML 注释元数据，缓存条目存储解析后的元数据。

## 7. about_you.md 的 50 字符阈值缺乏语义 ✅ 已修复

- **现象**：`len(about_you.strip()) > 50` 作为唯一判断标准。
- **根因**：50 是任意魔法数字。
- **修复**：替换为命名常量 `_MIN_ABOUT_YOU_CHARS = 30`，更准确地对应"有意义的最小画像长度"。

## 8. project_user_to_md 与 about_you.md 的生成链路独立 ✅ 已修复

- **现象**：`project_user_to_md()` 和 `update_ai_understanding()` 独立生成，彼此不知道对方存在。
- **根因**：两个投影任务是平行演进的关系，没有统一协调点。
- **修复**：`update_ai_understanding()` 不再直接查询 GrowthEvent，改为读取 `memory.md`（`project_user_to_md` 的产出）作为 LLM 输入。数据流变为：`Events → memory.md → about_you.md`，形成单一管道。

## 9. about_you.md 不包含时间戳元数据 ✅ 已修复

- **现象**：文件里没有记录覆盖的时间窗口。
- **根因**：纯文本 markdown，无 front matter。
- **修复**：`write_about_you()` 在文件首行写入 `<!-- lumen-meta: events=N generated_at=ISO8601 -->` 元数据注释。`build_snapshot()` 解析此元数据存入缓存。`_build_fixed_block_v2` 用 `_strip_meta()` 剥离后返回纯内容。

## 10. _build_recent_block 的过滤条件不包含"已被聚合"检查 ✅ 已不再适用

- **现象**：`_build_recent_block` 只按 `age_days` 和 `score` 过滤。
- **根因**：函数签名没有预留排除已聚合事件的扩展点。
- **修复**：L1 已重构为 `_build_context_block`，数据源切换为 Conversation/Message，不再消费 GrowthEvent。
