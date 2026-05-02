# 对话摘要缓冲方案

## 背景

`chat_service.py::stream_chat()` 加载历史消息时硬编码 `LIMIT 20`，超过 20 条消息后早期上下文丢失，AI "失忆"。

## 目标

用滚动摘要替代硬截断：最近 20 条完整保留，更早的消息压缩为一段摘要文本拼接在 system prompt 中。

## 业界参考

- **LangChain ConversationSummaryBufferMemory**：滑动窗口 + 摘要，生产标准
- **ChatGPT 内存系统**：逆向工程确认底层也是"近期对话摘要 + 当前会话完整保留"
- **Deep Agents SDK**：70-85% 窗口触发摘要 + 文件系统保留原始历史

---

## 设计

### 数据模型

`Conversation` 表加一个字段，`Message` 表不改：

```python
# models/conversation.py — Conversation 类新增
summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
```

#### 加列方式

SQLite 的 `Base.metadata.create_all()` 只建表不 ALTER 已有表。MVP 阶段选择方案 A：

| 方案 | 做法 | 适合 |
|------|------|------|
| **A** | 删旧 `career_os.db`，重启后 `create_all` 自动建含新列的表 | MVP，无生产数据 |
| B | `lifespan` 中检测列不存在则 `ALTER TABLE ADD COLUMN` | 生产环境 |
| C | Alembic 迁移 | 正式发布后 |

当前选 A，后续切 B 只需在 lifespan 加 5 行。

### 触发时机

`message_count` 计 user + assistant 总和，每轮 +2，始终为偶数。

```
第 1-10 轮：message_count = 2, 4, ..., 20（≤20，不触发）
第 11-14 轮：message_count = 22, 24, 26, 28（>20 但未到阈值，不触发）
第 15 轮：message_count = 30（≥30 且 %10==0 → 触发！）
第 20 轮：message_count = 40（触发）
第 25 轮：message_count = 50（触发）
```

```python
# stream_chat() 末尾、AI 回复 commit 后
if conv.message_count >= 30 and conv.message_count % 10 == 0:
    await _summarize_and_persist(db, conv)
```

### 被摘要的消息范围

保留窗口 20 条（与当前 `LIMIT 20` 一致）。窗口外的消息**全部重新摘要**（非增量追加）：

- message_count=30 → 窗口外 10 条 → 摘要
- message_count=40 → 窗口外 20 条 → 全部重新摘要（覆盖旧摘要）
- message_count=50 → 窗口外 30 条 → 全部重新摘要

每次传入"旧摘要 + 全部窗口外消息"，让 LLM 自己决定保留什么。避免增量摘要累积误差（"摘要漂移"）。

### 查询窗口外消息

```python
limit = conv.message_count - 20
result = await db.execute(
    select(Message)
    .where(Message.conversation_id == conv.conversation_id)
    .order_by(Message.created_at.asc())  # 从最早开始
    .limit(limit)
)
```

按 `created_at ASC` 取前 N 条，不依赖 message_count 做偏移，不受消息删除影响。

### 摘要 Prompt

```python
_SUMMARIZE_PROMPT = """根据以下对话记录更新摘要。只保留：用户背景变化、重要结论和决策、未完成的待办。丢弃闲聊和中间推理。100 字以内，中文。无关紧要则输出"（无重要内容）"

{previous_summary}

{old_messages}"""
```

`previous_summary` 为空时显示 `（新对话）`。

`old_messages` 格式化：
```
user: 你好学长
assistant: 你好呀，新宇学弟！
user: 我想了解一下测试方向
assistant: 【一句话总结】软件测试不是点点点...
```

### 竞争条件

同一会话快速连续发消息时，两条请求可能同时触发摘要。

```python
# 模块级轻量锁，按 conversation_id 隔离
_summary_locks: dict[str, asyncio.Lock] = {}

async def _summarize_and_persist(db, conv):
    lock = _summary_locks.setdefault(conv.conversation_id, asyncio.Lock())
    async with lock:
        await db.refresh(conv)
        # 获取锁后可能已被其他请求更新过
        if conv.summary:
            return
        # ... 执行摘要
```

锁字典只增不减，MVP 阶段对话量小（<100 把锁），可接受。

### System Prompt 拼接

`build_system_prompt()` 加 `conversation_summary` 参数，摘要插入用户背景后、Skill 正文前：

```python
def build_system_prompt(user_profile, intent, conversation_summary=None):
    parts = [
        "你是「码路领航」职业规划学长 Agent...",
        "风格：亲切、有干货...",
    ]
    if user_profile:
        parts.append(...)
    if conversation_summary:
        parts.append(f"\n【对话摘要】{conversation_summary}")
    # ... Skill 正文
```

`stream_chat()` 传入 `conv.summary`。

### LLM 调用规格

| 参数 | 值 | 理由 |
|------|-----|------|
| 模型 | `qwen-plus` | 复用现有路由 |
| task_type | `memory_summarize` | `llm_router.py` 已定义 |
| temperature | 0.3 | 摘要不需创造力 |
| max_tokens | 256 | 100 字内摘要足够 |
| 失败处理 | 保留旧摘要，log 警告 | 降级不崩溃 |

### 摘要失败不阻塞

```python
try:
    result = await llm_chat("memory_summarize", [{"role": "user", "content": prompt}])
    conv.summary = result if result else None
    await db.commit()
except Exception:
    logger.warning("摘要生成失败, 保留旧摘要")
```

---

## 完整调用链

```
stream_chat(db, user_id, user_input, conversation_id):
  ├─ 创建/获取会话
  ├─ 加载历史消息（LIMIT 20，不变）
  ├─ classify → commit 用户消息（带 intent）
  ├─ build_system_prompt(profile, intent, conv.summary)  ← 拼摘要
  ├─ chat_stream() 流式生成
  ├─ commit AI 回复
  └─ if message_count>=30 and message_count%10==0:
       _summarize_and_persist(db, conv)
         ├─ 查最早 N 条消息（N = message_count - 20）
         ├─ llm_chat(memory_summarize, prompt)
         └─ conv.summary = result → commit
```

---

## 涉及文件与改动量

| 文件 | 改动 | 行数 |
|------|------|------|
| `models/conversation.py` | 加 `summary` 字段 | +3 |
| `services/chat_service.py` | 触发逻辑 + `_summarize_and_persist()` + 锁 | +55 |
| `agent/orchestrator.py` | `build_system_prompt()` 加参数 + 拼接 | +10 |
| **合计** | | **~70 行** |

不引入新依赖。不修改前端。

---

## 效果示例

**触发前**（message_count=28，第 14 轮）：
```
context = [sys + 用户背景] + [msg9...msg28] + [输入]
        = 20 条完整历史
```

**首次触发**（message_count=30，第 15 轮）：
```
context = [sys + 用户背景]
        + [摘要: "讨论了测试方向，用户掌握Selenium/Pytest，建议学Playwright..."]
        + [msg11...msg30]
        + [输入]
        = 摘要 + 20 条最近消息
```

**第二次触发**（message_count=40，第 20 轮）：
```
context = [sys + 用户背景]
        + [摘要: "讨论过测试方向→Playwright学习→字节面试准备常见问题..."]
        + [msg21...msg40]
        + [输入]
        = 摘要（稍长）+ 20 条最近消息
```

context 长度随对话增长而稳定。摘要缓慢增长但远小于保留 40 条原始消息。
