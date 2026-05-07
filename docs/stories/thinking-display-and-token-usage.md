# Story: 思考过程展示 + Token 用量显示

## 背景

DeepSeek V4 Flash 在流式响应里直接输出 `<think>...</think>` 标签包裹的推理过程。
Lumen 后端的 `stream_text(delta=True)` 已经把这些 token 原样传给前端，但前端把它们当普通文本显示了。

目标：
1. 解析 `<think>` 块 → 可折叠"思考过程"卡片
2. 后端在 `done` 事件里带上 token 用量 → 前端每条 AI 回复底部显示"输入 xxx · 输出 xxx"

---

## 变更范围（5 个文件）

---

### 1. `app/backend/services/chat_service.py`

**改动：** 在 `async with agent.run_stream(...)` 内部，`async for` 循环结束后捕获 `response.usage()`；更新 `_sse_done()` 函数签名，将 usage 带入 done 事件。

**精确修改位置与内容：**

```python
# ① 在 async with 块内，async for 循环之后，紧接着加：
        usage_data: dict | None = None
        try:
            u = response.usage()
            usage_data = {
                "input": u.request_tokens or 0,
                "output": u.response_tokens or 0,
            }
        except Exception:
            pass
```

```python
# ② 函数末尾的 yield _sse_done 改为传入 usage_data：
    yield _sse_done(conv.conversation_id, usage_data)
```

```python
# ③ _sse_done 函数改为：
def _sse_done(conversation_id: str, usage: dict | None = None) -> str:
    payload: dict = {"type": "done", "conversation_id": conversation_id}
    if usage:
        payload["usage"] = usage
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

**注意**：`usage_data` 变量需要在 `async with` 块之前初始化为 `None`，以防 stream 提前中断时 finally 块访问不到该变量。完整 try/finally 结构保持不变，只在 `async for` 循环结束后、`finally` 之前插入 usage 捕获逻辑。

---

### 2. `app/frontend/src/lib/api.ts`

**改动①**：`SSEEvent` 的 `done` 类型加 `usage` 字段：

```ts
export type SSEEvent =
  | { type: 'token'; content: string; conversation_id: string }
  | { type: 'done'; conversation_id: string; usage?: { input: number; output: number } }
  | { type: 'error'; message: string }
```

**改动②**：`ChatStreamHandlers.onDone` 回调加 `usage` 参数：

```ts
export type ChatStreamHandlers = {
  onToken: (delta: string, conversationId: string) => void
  onDone: (conversationId: string, usage?: { input: number; output: number }) => void
  onError: (message: string) => void
  signal?: AbortSignal
}
```

**改动③**：`chatStream` 函数内 `done` 分支传入 usage：

```ts
} else if (evt.type === 'done') {
  h.onDone(evt.conversation_id, evt.usage)
}
```

---

### 3. `app/frontend/src/lib/chatSession.tsx`

**改动①**：`ChatMessage` 类型加可选 `usage` 字段：

```ts
export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  usage?: { input: number; output: number }
}
```

**改动②**：`onDone` 回调接收 usage，附加到最后一条 assistant 消息：

```ts
onDone: (cid, usage) => {
  if (completed) return
  completed = true
  setConversationId(cid)
  setStreaming(false)
  abortRef.current = null
  if (usage) {
    setMessages((prev) => {
      const next = prev.slice()
      const last = next[next.length - 1]
      if (last && last.role === 'assistant') {
        next[next.length - 1] = { ...last, usage }
      }
      return next
    })
  }
},
```

**不改动**：`ChatSessionValue` 类型、context、其他方法。

---

### 4. `app/frontend/src/lib/thinkSegments.ts`（新建）

精简版解析器，只处理原始 `<think>...</think>` 形式（Lumen 不需要 DeepTutor 的反引号包裹兼容）：

```ts
export interface TextSegment { kind: 'text'; content: string }
export interface ThinkSegment { kind: 'think'; content: string; closed: boolean }
export type ContentSegment = TextSegment | ThinkSegment

const OPEN_RE = /<think(?:ing)?\b[^>]*>/i
const CLOSE_RE = /<\/think(?:ing)?>/i

function trim(s: string): string {
  return s.replace(/^\s+/, '').replace(/\s+$/, '')
}

export function parseThinkSegments(input: string): ContentSegment[] {
  if (!input) return []
  if (!OPEN_RE.test(input)) return [{ kind: 'text', content: input }]

  const segments: ContentSegment[] = []
  let cursor = 0

  while (cursor < input.length) {
    const tail = input.slice(cursor)
    const open = OPEN_RE.exec(tail)
    if (!open) {
      if (tail) segments.push({ kind: 'text', content: tail })
      break
    }
    if (open.index > 0) {
      segments.push({ kind: 'text', content: tail.slice(0, open.index) })
    }
    const afterOpen = tail.slice(open.index + open[0].length)
    const close = CLOSE_RE.exec(afterOpen)
    if (!close) {
      segments.push({ kind: 'think', content: trim(afterOpen), closed: false })
      break
    }
    segments.push({
      kind: 'think',
      content: trim(afterOpen.slice(0, close.index)),
      closed: true,
    })
    cursor += open.index + open[0].length + close.index + close[0].length
  }

  return segments
}
```

---

### 5. `app/frontend/src/pages/Chat.tsx`

#### 5a. 新增 `ThinkingCard` 组件

放在文件末尾（`InputBox` 之后）：

```tsx
function ThinkingCard({ content, closed }: { content: string; closed: boolean }) {
  const [userToggled, setUserToggled] = useState<boolean | null>(null)
  const detailsRef = useRef<HTMLDetailsElement>(null)

  const open = userToggled !== null ? userToggled : !closed

  useEffect(() => {
    const el = detailsRef.current
    if (el && el.open !== open) el.open = open
  }, [open])

  return (
    <details
      ref={detailsRef}
      onToggle={(e) => {
        const next = e.currentTarget.open
        if (next !== open) setUserToggled(next)
      }}
      className="group/think my-sm overflow-hidden rounded-lg border border-border-soft bg-surface/50"
    >
      <summary className="flex cursor-pointer list-none items-center gap-xs px-sm py-xs text-xs text-text-subtle transition-colors hover:text-text-muted [&::-webkit-details-marker]:hidden">
        <svg
          className="h-3 w-3 shrink-0 transition-transform group-open/think:rotate-180"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        <span>思考过程</span>
        {!closed && (
          <span className="ml-xs animate-pulse text-text-subtle">·</span>
        )}
      </summary>
      <div className="border-t border-border-soft px-sm py-xs">
        <pre className="whitespace-pre-wrap font-mono text-xs text-text-subtle leading-relaxed">
          {content || '思考中…'}
        </pre>
      </div>
    </details>
  )
}
```

#### 5b. 更新 `AssistantBubble`

**import 改动**：在文件顶部加：

```ts
import { parseThinkSegments } from '../lib/thinkSegments'
```

**组件改动**：`AssistantBubble` 接收可选的 `usage` prop，内部解析 segments：

```tsx
function AssistantBubble({
  text,
  streaming,
  usage,
}: {
  text: string
  streaming: boolean
  usage?: { input: number; output: number }
}) {
  const segments = parseThinkSegments(text)

  return (
    <div className="ink-fade-in">
      <div className="mb-2xs text-xs text-text-subtle">学长</div>
      <div className="mb-sm h-px w-12 bg-border" />

      {segments.map((seg, i) =>
        seg.kind === 'think' ? (
          <ThinkingCard key={i} content={seg.content} closed={seg.closed} />
        ) : (
          <div key={i} className="prose prose-sm max-w-none text-base">
            <ReactMarkdown>{seg.content}</ReactMarkdown>
            {streaming && i === segments.length - 1 && seg.content ? (
              <span className="ink-cursor" />
            ) : null}
          </div>
        ),
      )}

      {streaming && !text ? (
        <span className="text-text-muted ink-cursor">正在写...</span>
      ) : null}

      {usage && !streaming ? (
        <div className="mt-xs flex gap-xs text-[11px] text-text-subtle/50">
          <span>输入 {usage.input}</span>
          <span>·</span>
          <span>输出 {usage.output}</span>
          <span>token</span>
        </div>
      ) : null}
    </div>
  )
}
```

#### 5c. 传入 `usage` prop

在 `Chat.tsx` 的消息渲染循环里，给最后一条 assistant 消息传入 `usage`：

```tsx
{messages.map((message, index) =>
  message.role === 'assistant' ? (
    <AssistantBubble
      key={index}
      text={message.content}
      streaming={streaming && index === messages.length - 1}
      usage={message.usage}
    />
  ) : (
    <UserBubble key={index} text={message.content} />
  ),
)}
```

`ChatMessage.usage` 只在流结束时由 `onDone` 写入，历史消息加载时该字段为 `undefined`，所以历史消息不会显示 token 数——这是预期行为。

---

## 不改动的内容

- `chatStream()` 的 SSE 读取循环结构不变
- `ChatSessionProvider` 的其他 state（messages、streaming、conversationId、error）不变
- `UserBubble`、`InputBox` 不变
- 后端摘要逻辑、记忆审查逻辑不变

---

## 验收标准

1. 发一条消息给 DeepSeek V4 Flash，AI 回复中的 `<think>...</think>` 内容渲染为可折叠卡片，不作为正文 Markdown 显示
2. 卡片在思考流式中保持展开 + 动态省略号，收到 `</think>` 后自动折叠
3. 用户手动展开/折叠后，自动行为不再干预
4. 流结束后，AssistantBubble 底部显示"输入 xxx · 输出 xxx token"（仅当前会话，加载历史时不显示）
5. 无思考块的模型（如 qwen-plus）响应正常渲染，无异常
6. `thinkSegments.ts` 的 `parseThinkSegments('')` 和 `parseThinkSegments('普通文本')` 返回单个 TextSegment，不崩溃
