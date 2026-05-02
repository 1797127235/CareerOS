# 对话流程 Bug 记录

## 背景

`services/chat_service.py::stream_chat()` 是用户发消息 → AI 回复的核心链路。审查发现 8 个问题，按严重程度分级。

---

## 🔴 P0 — 数据缺失 / 不一致

### 1. intent 字段写不进 DB

**位置**：`services/chat_service.py` L71-84

**流程**：
```
L71  db.add(user_message)
L74  await db.commit()           ← 用户消息已提交,对象 expired
L83  intent = await classify()
L84  user_message.intent = intent  ← 修改已 detached 的对象
```

`user_message` 在 L74 commit 后进入 expired 状态，L84 的赋值不保证写回 DB。结果：DB 中 `user_message.intent` 恒为 NULL。

**影响**：用户消息的意图标签丢失，无法按意图统计对话分布、无法分析用户意图变化趋势。

**修复思路**：将 `classify()` 移到 commit 之前，在第一次 commit 时就带着 intent。

---

### 2. 用户消息已 commit 后失败 → 孤儿消息

**位置**：`services/chat_service.py` L70-110

**流程**：
```
L71-74  db.add + db.commit(用户消息)    ← 已写库
L83    classify(user_input)             ← 可能 LLM 超时
L93    chat_stream(task_type, messages) ← 可能 API 报错
```

L74 之后任何异常，用户消息已在 DB 中，但 AI 回复未生成。用户看到「生成回复失败」但消息已保存。

**影响**：每次失败的 LLM 调用都产生一条无回复的孤儿消息。DB 中出现 `role="user"` 但没有对应 `role="assistant"` 的悬挂记录。

**修复思路**：
- 方案 A：classify + 生成先执行，成功后再 commit（风险：LLM 生成到一半崩溃，消息全丢）
- 方案 B：用户消息先 commit，但标记 `status="pending"`，AI 回复完成后改为 `status="completed"`，失败则改为 `status="failed"`（推荐）
- 方案 C：将 classify 和 LLM 生成分开，classify 成功后才 commit 用户消息

---

## 🟡 P1 — 功能缺陷 / 安全

### 3. 历史只保留 20 条，长对话失忆

**位置**：`services/chat_service.py` L50-61

```python
.limit(20)  # ← 硬编码 20 条
```

超过 20 条消息后，早期的内容被截断。LLM 看不到前面讨论的背景（用户学校、目标、之前聊过的方向等）。

**影响**：30+ 轮对话中，AI 会「忘记」早前讨论的内容。没有滑动窗口或摘要机制来补偿。

**修复思路**：
- 短期内：增大 limit（如 50），配合 `max_tokens` 控制上下文长度
- 长期：实现滑动窗口 + 历史摘要压缩（将旧消息摘要为一段话拼接在 system prompt 中）

---

### 4. stream_chat 未校验会话归属

**位置**：`services/chat_service.py` L36-39

```python
if conversation_id:
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        yield _sse_error("会话不存在")
        return
    # ← 缺少 conv.user_id != user_id 检查
```

未校验 `conv.user_id` 是否匹配当前 `user_id`。传他人的 `conversation_id` 可向他人会话发消息。

**位置**：`routers/chat.py` L90-92

```python
conv = await db.get(Conversation, conversation_id)
if not conv or conv.user_id != user_id:
    return []  # ← 应该返回 403
```

归属校验用返回空列表代替 403，REST 风格不一致。

**影响**：
- `POST /api/chat`：会话劫持（AGENTS.md 已标注为已知 limitation）
- `GET /api/chat/{id}`：越权时返回空列表而非 403，前端无法区分「无权访问」和「空会话」

**修复思路**：
- `POST` 侧补 `conv.user_id != user_id` 检查
- `GET` 侧改为 HTTP 403

---

## 🟡 P2 — 性能 / 体验

### 5. 每条消息都查两次用户画像

**位置**：`services/chat_service.py` L115-135

每次 `stream_chat` 执行两次 SELECT：
```python
await db.execute(select(User).where(User.user_id == user_id))
await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
```

单条消息影响不大，但一次 50 轮对话 = 100 次冗余查询。

**影响**：无用 IO。用户画像在一次对话中几乎不变，每次查库没有意义。

**修复思路**：按 `conversation_id` 缓存 profile 引用，首次加载后复用。或由调用方传入（`chat_service` 只负责对话，不负责查 profile）。

---

### 6. 流式生成不支持客户端取消

**位置**：`services/chat_service.py` L92-95

```python
async for token in chat_stream(task_type, messages):
    full_content += token
    yield _sse_token(token, conv.conversation_id)
```

用户关掉页面或点了「停止生成」后，服务端继续跑完 LLM 流。没有检测客户端断开连接的机制。

**影响**：用户取消后，API 额度继续消耗，`full_content` 继续累加。一个 500 字的回答如果用户在第 100 字时取消，仍有 400 字被白白生成。

**修复思路**：
- 通过 `StreamingResponse` 的 `asend()` / `aclose()` 机制检测断开
- 或在 `chat_stream` 中定期 yield 空 token 以检测生成器是否已关闭

---

## 🟢 P3 — 轻微 / 边界

### 7. commit 成功后 rollback 无意义

**位置**：`services/chat_service.py` L70-79

```python
try:
    db.add(user_message)
    ...
    await db.commit()
except Exception:
    await db.rollback()  # ← commit 成功后无事务可回滚
```

如果 commit 成功，rollback 是空操作。如果 commit 前出错，rollback 合理。但当前 try 块包含 `yield` 之前的同步操作，若 `yield` 触发异常（类 Starlette 内部错误），此时事务可能已提交。

**影响**：无实际运行时危害，但代码意图不清晰，后续维护者可能误读。

---

### 8. 流中断时前端无法判断回复完整性

**位置**：`services/chat_service.py` L106-110

如果 LLM 生成途中崩溃（如在 300 token 时 API 断开），`chat_stream` 抛出异常，进入 except 块：
```python
except Exception:
    await db.rollback()
    yield _sse_error("生成回复失败，请稍后重试")
```

前端已通过 SSE 收到 300 token + `_sse_error`。但当前 schema 没有标记消息状态，前端无法判断这条回复是完整的还是残缺的。

**影响**：前端可能展示残缺的 AI 回复，用户以为这是完整回答。

**修复思路**：`Message` 模型加 `status` 字段（`streaming | completed | failed`），流开始时设为 `streaming`，完成设为 `completed`，失败设为 `failed`。

---

## 汇总

| # | 严重度 | 问题 | 文件位置 | 推荐优先级 |
|---|--------|------|----------|-----------|
| 1 | 🔴 P0 | intent 写不进 DB | chat_service.py:84 | 最高 |
| 2 | 🔴 P0 | 孤儿消息 | chat_service.py:70-110 | 最高 |
| 3 | 🟡 P1 | 20 条截断失忆 | chat_service.py:55 | 高 |
| 4 | 🟡 P1 | 会话归属无校验 | chat_service.py:36 / chat.py:90 | 高 |
| 5 | 🟡 P2 | 重复查用户画像 | chat_service.py:115-135 | 中 |
| 6 | 🟡 P2 | 流式不支持取消 | chat_service.py:92-95 | 中 |
| 7 | 🟢 P3 | commit 后 rollback | chat_service.py:77 | 低 |
| 8 | 🟢 P3 | 残缺回复标识缺失 | chat_service.py:106-110 | 低 |
