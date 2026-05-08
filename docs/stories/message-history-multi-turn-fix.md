# Story: PydanticAI message_history 多轮对话修复

## 背景

Lumen 后端使用 PydanticAI Agent，但每次调用 `agent.run_stream()` / `agent.run_stream_events()` 都没有传入 `message_history`，导致每轮对话对模型来说都是全新的无状态请求。

当前对历史的处理方式是：从 DB 读最近 10 条消息，截断到每条 150 字，拼成文本塞进 `@agent.system_prompt`。这有两个问题：

1. **多轮结构丢失**：模型在 `role: user / assistant` 格式上训练，把历史拍平成文本会降低理解质量
2. **工具调用历史丢失**：PydanticAI 的 `message_history` 可以携带上轮的工具调用和结果，当前每轮都是 stateless 调用，模型看不到自己上轮用了什么工具

修复方法：将历史消息存储为 PydanticAI 原生的 `ModelMessage` 格式，每轮通过 `message_history=` 传入，流结束后调用 `result.new_messages()` 追加并持久化。

---

## 变更范围（3 个文件）

---

### 1. `app/backend/models/conversation.py`

**改动：** 在 `Conversation` 类中新增一列：

```python
pydantic_messages: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
```

完整的 `Conversation` 类（只加这一行，其他不变）：

```python
class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    topic_type: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="active")
    context_snapshot: Mapped[dict | None] = mapped_column(JSON)
    message_count: Mapped[int] = mapped_column(default=0)
    is_pinned: Mapped[bool] = mapped_column(default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    pydantic_messages: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)  # ← 新增
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
```

---

### 2. `app/backend/main.py`

**改动：** 在 `_migrate_sqlite()` 的 SQL 列表中追加一行：

```python
"ALTER TABLE conversations ADD COLUMN pydantic_messages TEXT",
```

加在现有的 `"ALTER TABLE conversations ADD COLUMN summary TEXT"` 之后即可。函数本身有 `try/except` 忽略 "duplicate column" 错误，新列幂等安全。

---

### 3. `app/backend/agent/pydantic_agent.py`

**改动：** 删除 `dynamic_prompt` 中的"近期对话历史"段落。

**删除以下代码（`pydantic_agent.py:149-165`）：**

```python
        # ── 近期对话历史（最近 10 条）──
        try:
            history_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == ctx.deps.conversation_id)
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            history = list(history_result.scalars().all())
            history.reverse()
            if history:
                lines = ["【近期对话】"]
                for msg in history:
                    tag = "用户" if msg.role == "user" else "助手"
                    lines.append(f"{tag}: {(msg.content or '')[:150]}")
                parts.append("\n".join(lines))
        except Exception:
            pass
```

删掉之后还需要删除文件顶部对应的 `from app.backend.models.conversation import Conversation, Message` 中的 `Message` 引用——如果 `Message` 只在这段代码里用到，则把 `Message` 从 import 里去掉：

```python
# 改前
from app.backend.models.conversation import Conversation, Message

# 改后（只有 dynamic_prompt 里用到 Conversation，Message 不再用）
from app.backend.models.conversation import Conversation
```

`dynamic_prompt` 改完后只保留两段：记忆上下文 + 对话摘要。

---

### 4. `app/backend/services/chat_service.py`

这是改动最大的文件，SSE 路径（`stream_chat`）和 WS 路径（`stream_chat_ws`）都要改，逻辑相同但结构不同。

#### 4.1 新增辅助函数（放在文件顶层，两个函数之前）

```python
def _load_pydantic_history(conv) -> list:
    """反序列化 conversation.pydantic_messages → list[ModelMessage]。"""
    from pydantic_ai import ModelMessagesTypeAdapter

    if not conv.pydantic_messages:
        return []
    try:
        return ModelMessagesTypeAdapter.validate_json(conv.pydantic_messages.encode())
    except Exception:
        return []


def _save_pydantic_history(conv, new_msgs: list) -> None:
    """追加 new_msgs 并序列化写回 conv.pydantic_messages，保留最近 30 条。"""
    from pydantic_ai import ModelMessagesTypeAdapter
    from pydantic_core import to_json

    if not new_msgs:
        return
    existing = _load_pydantic_history(conv)
    updated = (existing + new_msgs)[-30:]
    conv.pydantic_messages = to_json(updated).decode()
```

**为什么保留 30 条：** `ModelMessage` 不等于一轮对话——Agent 调用 2 个工具时，一轮会产生 3–5 个 `ModelMessage`（request + 多个 response）。保留 30 条大约覆盖最近 8–10 轮对话，与之前的 10 条文本历史覆盖范围相当，但保留了完整结构。

---

#### 4.2 `stream_chat()`（SSE 路径）改动

**改动位置：** `stream_chat()` 函数内部，"PydanticAI Agent 流式处理"注释之后。

在 `deps = LumenDeps(...)` 声明之前，加载历史：

```python
        # 加载 PydanticAI 消息历史
        history = _load_pydantic_history(conv)
```

在 `full_content = ""` 和 `usage_data: dict | None = None` 之后，`try:` 之前，声明：

```python
        new_msgs: list = []
```

`agent.run_stream()` 调用加上 `message_history=history`：

```python
            async with agent.run_stream(
                user_input,
                message_history=history,      # ← 新增
                deps=deps,
                model_settings=ModelSettings(max_tokens=4096),
            ) as response:
                async for text in response.stream_text(delta=True):
                    full_content += text
                    yield _sse_token(text, conv.conversation_id)

                try:
                    u = response.usage()
                    usage_data = {
                        "input": u.request_tokens or 0,
                        "output": u.response_tokens or 0,
                    }
                except Exception:
                    pass

                new_msgs = response.new_messages()  # ← 新增：在 async with 内部取
```

在 `finally` 块内，`await db.commit()` 之前，追加：

```python
                    _save_pydantic_history(conv, new_msgs)  # ← 新增
```

完整的 `finally` 块应该是：

```python
        finally:
            if full_content:
                db.add(
                    Message(
                        conversation_id=conv.conversation_id,
                        role="assistant",
                        content=full_content,
                        intent="consultation",
                    )
                )
                conv.message_count = (conv.message_count or 0) + 1
                conv.last_message_at = datetime.now(UTC)
                _save_pydantic_history(conv, new_msgs)  # ← 新增
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.warning("保存 AI 回复失败 (可能为部分)", conversation_id=conv.conversation_id)

                # Agent 工具创建了事件 → commit 后触发投影（不变）
                ...
                # 后台记忆审查（不变）
                ...
```

---

#### 4.3 `stream_chat_ws()`（WS 路径）改动

同样在 `deps = LumenDeps(...)` 之前加载历史：

```python
        # 加载 PydanticAI 消息历史
        history = _load_pydantic_history(conv)
```

在 `full_content = ""` 等变量声明之后加：

```python
        new_msgs: list = []
```

`agent.run_stream_events()` 加上 `message_history=history`：

```python
            async for event in agent.run_stream_events(
                user_input,
                message_history=history,      # ← 新增
                deps=deps,
                model_settings=ModelSettings(max_tokens=4096),
            ):
```

在 `elif ek == "agent_run_result":` 分支里取本轮消息：

```python
                elif ek == "agent_run_result":
                    new_msgs = event.result.new_messages()  # ← 新增
                    if not cancelled:
                        try:
                            u = event.result.usage()
                            usage_data = {
                                "input": u.request_tokens or 0,
                                "output": u.response_tokens or 0,
                            }
                        except Exception:
                            pass
```

`finally` 块同 SSE 路径，在 `db.commit()` 之前加：

```python
                _save_pydantic_history(conv, new_msgs)  # ← 新增
```

注意：`cancelled` 为 True 时也保存（截断的对话历史也有意义），但可以选择只在 `not cancelled` 时保存，两种都可以接受。

---

## 验收标准

1. **多轮记忆**：第一轮告诉 AI "我叫李明"，第二轮问"我叫什么"，AI 能回答（不借助 memory_search，从 message_history 里直接知道）
2. **工具调用历史保留**：第一轮 memory_save 保存了某个技能，第二轮问"你刚才保存了什么"，AI 能回忆起工具调用
3. **DB 列存在**：`conversations` 表有 `pydantic_messages` TEXT 列，启动时不报错
4. **无回归**：SSE 和 WebSocket 路径都正常流式输出，token 用量显示正常，trace 面板正常
5. **长对话稳定**：发送超过 30 条消息后，`pydantic_messages` 列始终只保留最近 30 条 `ModelMessage`（可以用 SQLite 工具直接查列内容验证）

---

## 不改动的内容

- `stream_chat()` 和 `stream_chat_ws()` 的 `finally` 块中，DB 保存、投影触发、后台记忆审查逻辑完全不变
- 滚动摘要逻辑（`_summarize_bg`）不变，`pydantic_messages` 和 `summary` 两套机制共存互补
- `deps.py`、`LumenDeps` 不变
- 前端不涉及任何改动
- `_background_memory_review()` 不变

---

## 注意事项

1. `response.new_messages()` 必须在 `async with agent.run_stream(...) as response:` 代码块**内部**调用，离开 `async with` 后 `response` 不可用
2. `event.result.new_messages()` 在 `run_stream_events` 的 `agent_run_result` 事件里调用，这是流的最后一个事件
3. `_load_pydantic_history` 内部有 try/except 兜底，旧 DB 里 `pydantic_messages` 为 NULL 时返回空列表，不报错
4. `pydantic_core.to_json()` 返回 `bytes`，需要 `.decode()` 才能存 Text 列
5. 两个辅助函数中的 import 放在函数内部（lazy import），避免影响模块加载顺序
