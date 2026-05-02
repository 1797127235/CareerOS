# 对话流程 Bug 记录

> 最后更新：2026-05-03
> 
> 状态标注：✅ 已修复 | 🔄 部分修复 | ❌ 未修复

## 背景

`services/chat_service.py::stream_chat()` 是用户发消息 → AI 回复的核心链路。审查发现 8 个问题，按严重程度分级。

---

## 🔴 P0 — 数据缺失 / 不一致

### 1. ✅ intent 字段写不进 DB — 已修复

**位置**：`services/chat_service.py` L71-84

**原流程**：
```
L71  db.add(user_message)
L74  await db.commit()           ← 用户消息已提交,对象 expired
L83  intent = await classify()
L84  user_message.intent = intent  ← 修改已 detached 的对象
```

**修复方式**：`run_orchestrator()` 在 commit 之前执行，用户消息带着 intent 一起提交。

---

### 2. ✅ 孤儿消息 — 已修复

**位置**：`services/chat_service.py` L70-110

**原流程**：用户消息 commit 后，LLM 调用失败导致无回复的孤儿消息。

**修复方式**：用 `try/finally` 保存已生成的内容，客户端断开也能保存部分回复。

---

## 🟡 P1 — 功能缺陷 / 安全

### 3. 🔄 20 条截断失忆 — 部分修复

**位置**：`services/chat_service.py` L50-61

```python
.limit(20)  # ← 硬编码 20 条
```

**现状**：已实现滚动摘要机制（`_summarize_and_persist`），超过 30 条消息后自动压缩旧消息为摘要。但最近 20 条之外的原始消息仍被截断。

**仍需改进**：摘要质量依赖 LLM，可能丢失关键信息。

---

### 4. ✅ 会话归属无校验 — 已修复

**位置**：`services/chat_service.py` L63

```python
if not conv or conv.user_id != user_id:
    yield _sse_error("会话不存在")
    return
```

**现状**：`chat_service.py` 和 `routers/chat.py` 都已添加归属校验。

---

## 🟡 P2 — 性能 / 体验

### 5. ❌ 每条消息都查两次用户画像 — 未修复

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

### 6. ❌ 流式生成不支持客户端取消 — 未修复

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

### 7. ✅ commit 成功后 rollback 无意义 — 已修复

**位置**：`services/chat_service.py`

**现状**：代码结构已重构，commit/rollback 逻辑更清晰。

---

### 8. ❌ 流中断时前端无法判断回复完整性 — 未修复

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

| # | 严重度 | 状态 | 问题 | 文件位置 |
|---|--------|------|------|----------|
| 1 | 🔴 P0 | ✅ 已修复 | intent 写不进 DB | chat_service.py |
| 2 | 🔴 P0 | ✅ 已修复 | 孤儿消息 | chat_service.py |
| 3 | 🟡 P1 | 🔄 部分修复 | 20 条截断失忆 | chat_service.py |
| 4 | 🟡 P1 | ✅ 已修复 | 会话归属无校验 | chat_service.py |
| 5 | 🟡 P2 | ❌ 未修复 | 重复查用户画像 | chat_service.py |
| 6 | 🟡 P2 | ❌ 未修复 | 流式不支持取消 | chat_service.py |
| 7 | 🟢 P3 | ✅ 已修复 | commit 后 rollback | chat_service.py |
| 8 | 🟢 P3 | ❌ 未修复 | 残缺回复标识缺失 | chat_service.py |

**统计**：✅ 已修复 4 个 | 🔄 部分修复 1 个 | ❌ 未修复 3 个
