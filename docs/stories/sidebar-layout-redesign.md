# Story: 侧边栏布局重构

## 背景与目标

当前 Lumen 用顶部横向导航（header 64px）+ 对话历史抽屉（翻翻之前 → Dialog）。
随着功能增长，顶部导航扩展性差，对话历史需要点击才能看到。

**目标**：改为左侧固定侧边栏，对话历史内联显示，与 DeepTutor 布局模式对齐，但保留 Lumen 深色主题和排版风格。

---

## 变更范围（3 个文件）

### 1. `app/frontend/src/App.tsx`（重写）

**删除**：`<header>` 顶部导航栏整块
**删除**：`NavItem` 组件
**新增**：整体改为左右分栏布局，左侧 `<Sidebar />`，右侧 `<Outlet />`

```tsx
import { Outlet } from 'react-router-dom'
import { ChatSessionProvider } from './lib/chatSession'
import Sidebar from './components/Sidebar'

function App() {
  return (
    <ChatSessionProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </ChatSessionProvider>
  )
}

export default App
```

---

### 2. `app/frontend/src/components/Sidebar.tsx`（新建）

侧边栏宽度固定 `220px`，深色风格与现有 design token 一致。

**布局结构（从上到下）：**

```
┌────────────────────┐
│  Lumen             │  ← NavLink to="/" , font-han text-ink text-xl
├────────────────────┤
│  ＋ 新对话          │  ← button, onClick: startNew()
├────────────────────┤
│  TODAY             │  ← 分组标题 text-xs text-text-subtle
│    · 你好世界       │  ← 对话 item，active 时高亮
│    · 求职方向探讨   │
│  昨天              │
│    · 面试复盘       │
│  更早              │
│    · OCBC 评估     │
├────────────────────┤  ← 弹性占位 flex-1
│  画像              │  ← NavLink to="/profile"
│  记忆              │  ← NavLink to="/memories"
│  设置              │  ← NavLink to="/settings"
├────────────────────┤
│  反馈              │  ← <a> 外链 GitHub Issues，text-xs text-text-subtle
└────────────────────┘
```

**数据来源：**
- `useChatSession()` 取 `conversationId`、`loadConversation`、`startNew`
- `getChatHistory(30)` 获取对话列表
- 当 `conversationId` 变化时重新 fetch（用 `useEffect([conversationId])`）

**对话分组规则（客户端计算）：**
```
今天 → TODAY
昨天 → 昨天
2天前~6天前 → 本周
7天以上 → 更早
```

**对话 item 交互：**
- 点击 → `loadConversation(id)`
- hover 显示删除按钮（text-text-subtle opacity-0 → opacity-100）
- 第一次点删除 → 变为"确定？"文字（text-danger），3s 后自动重置
- 第二次点 → `deleteConversation(id)`，从列表移除
- 删除当前对话 → `startNew()`
- 当前对话高亮：`bg-surface-elevated/50`

**完整代码：**

```tsx
import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { deleteConversation, getChatHistory, type ConversationSummary } from '../lib/api'
import { useChatSession } from '../lib/chatSession'

const FEEDBACK_URL = 'https://github.com/1797127235/Lumen/issues'

function groupByDate(items: ConversationSummary[]): { label: string; items: ConversationSummary[] }[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 6 * 86400000)

  const groups: Record<string, ConversationSummary[]> = {
    TODAY: [],
    昨天: [],
    本周: [],
    更早: [],
  }

  for (const item of items) {
    if (!item.last_message_at) { groups['更早'].push(item); continue }
    const d = new Date(item.last_message_at)
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    if (day >= today) groups['TODAY'].push(item)
    else if (day >= yesterday) groups['昨天'].push(item)
    else if (day >= weekAgo) groups['本周'].push(item)
    else groups['更早'].push(item)
  }

  return Object.entries(groups)
    .filter(([, list]) => list.length > 0)
    .map(([label, list]) => ({ label, items: list }))
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) {
    const h = date.getHours()
    const m = date.getMinutes()
    return `${h < 10 ? '0' + h : h}:${m < 10 ? '0' + m : m}`
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

export default function Sidebar() {
  const { conversationId, loadConversation, startNew } = useChatSession()
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    getChatHistory(30)
      .then(setItems)
      .catch(() => {})
  }, [conversationId])

  async function handleDelete(id: string, event: React.MouseEvent) {
    event.stopPropagation()
    if (deleteId !== id) {
      setDeleteId(id)
      setTimeout(() => setDeleteId(prev => prev === id ? null : prev), 3000)
      return
    }
    try {
      await deleteConversation(id)
      setItems(prev => prev.filter(i => i.conversation_id !== id))
      setDeleteId(null)
      if (id === conversationId) {
        startNew()
        navigate('/', { replace: true })
      }
    } catch {
      alert('删除失败，请重试')
    }
  }

  const groups = groupByDate(items)

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-sm px-sm py-xs rounded-md text-sm transition-colors ${
      isActive
        ? 'bg-surface-elevated text-text'
        : 'text-text-muted hover:bg-surface hover:text-text'
    }`

  return (
    <aside className="flex w-[220px] flex-shrink-0 flex-col border-r border-border-soft bg-surface px-xs py-md gap-xs">
      {/* Logo */}
      <NavLink
        to="/"
        end
        className="px-sm py-xs text-xl font-han text-ink hover:opacity-80 mb-xs"
      >
        Lumen
      </NavLink>

      {/* 新对话 */}
      <button
        onClick={() => { startNew(); navigate('/', { replace: true }) }}
        className="flex items-center gap-xs px-sm py-xs rounded-md text-sm text-text-muted hover:bg-surface-elevated hover:text-text transition-colors"
      >
        <span className="text-base leading-none">＋</span>
        新对话
      </button>

      {/* 对话历史 */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-xs mt-xs">
        {groups.map(group => (
          <div key={group.label}>
            <div className="px-sm py-xs text-xs text-text-subtle">{group.label}</div>
            {group.items.map(item => (
              <div
                key={item.conversation_id}
                onClick={() => { void loadConversation(item.conversation_id); navigate('/', { replace: true }) }}
                className={`group relative flex items-center rounded-md px-sm py-[6px] cursor-pointer transition-colors ${
                  conversationId === item.conversation_id
                    ? 'bg-surface-elevated/50'
                    : 'hover:bg-surface-elevated/30'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm text-text group-hover:text-ink transition-colors">
                    {item.title || '未命名'}
                  </div>
                  <div className="text-xs text-text-subtle">{formatTime(item.last_message_at)}</div>
                </div>
                <button
                  onClick={(e) => void handleDelete(item.conversation_id, e)}
                  className={`ml-xs flex-shrink-0 text-xs transition-all ${
                    deleteId === item.conversation_id
                      ? 'text-danger opacity-100'
                      : 'text-text-subtle opacity-0 group-hover:opacity-100 hover:text-danger'
                  }`}
                >
                  {deleteId === item.conversation_id ? '确定？' : '删'}
                </button>
              </div>
            ))}
          </div>
        ))}
        {items.length === 0 && (
          <p className="px-sm text-xs text-text-subtle">还没有聊过。</p>
        )}
      </div>

      {/* 页面导航 */}
      <div className="flex flex-col gap-2xs border-t border-border-soft pt-xs mt-xs">
        <NavLink to="/profile" className={navLinkClass}>画像</NavLink>
        <NavLink to="/memories" className={navLinkClass}>记忆</NavLink>
        <NavLink to="/settings" className={navLinkClass}>设置</NavLink>
      </div>

      {/* 反馈 */}
      <a
        href={FEEDBACK_URL}
        target="_blank"
        rel="noreferrer noopener"
        className="px-sm text-xs text-text-subtle hover:text-text-muted transition-colors"
      >
        反馈
      </a>
    </aside>
  )
}
```

---

### 3. `app/frontend/src/pages/Chat.tsx`（删除 sticky sub-header + HistoryDrawer）

**删除以下内容：**

1. sticky sub-header 整块（含"+ 重新开始"和"翻翻之前"两个按钮）：
   ```tsx
   // 删除这个 div 及其所有子节点
   <div className="sticky top-[64px] z-40 -mx-md mb-lg flex justify-end gap-md ...">
     <button onClick={startNew} ...>+ 重新开始</button>
     <HistoryDrawer ... />
   </div>
   ```

2. `HistoryDrawer` 组件函数（整个函数体，约 90 行）
3. `formatTime` 函数（移到 Sidebar.tsx，Chat.tsx 不再需要）
4. `pad` 函数（同上）
5. import 中的 `deleteConversation`、`getChatHistory`、`type ConversationSummary`（不再用）
6. import 中的 `* as Dialog from '@radix-ui/react-dialog'`（不再用）
7. `useChatSession` 解构中的 `startNew`（不再用）

**保留（不变）：**
- `messages`、`streaming`、`conversationId`、`error`、`sendMessage`、`loadConversation` 从 `useChatSession`
- `useEffect` 监听 URL `?c=` 参数的逻辑
- `useEffect` 同步 `conversationId` 到 URL 的逻辑
- `useEffect` 自动滚动到底部
- 消息列表渲染（`AssistantBubble`、`UserBubble`）
- `InputBox` 组件
- 整体 `mx-auto max-w-[680px]` 内容居中布局

**Chat.tsx 顶层 `div` 的 `pt-xl` 保留，但去掉原来为 sticky header 留的 `top-[64px]` offset（因为 header 已删）：**
Chat 页面的顶层 padding 保持不变：`min-h-[calc(100vh-64px)]` 改为 `min-h-screen`（因为不再有 64px header）。

---

## 不改动的内容

- `index.css`（design tokens 不变）
- `main.tsx`（路由不变）
- `Profile.tsx`、`Memories.tsx`、`Settings.tsx`（页面内容不变）
- `chatSession.tsx`、`api.ts`（逻辑层不变）
- `Chat.tsx` 的消息渲染、InputBox、AssistantBubble、UserBubble
- Lumen 深色主题和 font-han 排版

---

## 补充说明（给 Kimi）

### 1. `gap-2xs` 是有效的 class

`index.css` 中已定义 `--spacing-2xs: 4px`，Tailwind v4 的 `@theme` 会自动生成所有 spacing utilities。
现有代码中 `mb-2xs`、`mt-2xs` 已在 Chat.tsx 和 Memories.tsx 中使用，`gap-2xs` 同理有效，无需替换。

### 2. 对话列表不显示 message_count — 有意设计

原 HistoryDrawer 在宽 380px 的抽屉里显示"14 条消息"，空间充裕。
侧边栏只有 220px，item 行已有标题 + 时间，加 message_count 会挤压截断标题。
**有意去掉**，侧边栏只保留标题和时间。

### 3. 移动端 — 本 Story 不处理

Lumen 是本地单用户桌面应用，运行在 localhost。移动端不是当前目标。
本 Story 只需保证 ≥ 1024px 宽度下布局正确。移动适配作为独立 Story 后续处理。

---

## 验收标准

1. 页面左侧显示 220px 固定侧边栏，顶部无 header
2. 侧边栏显示 Lumen wordmark（可点击回首页）
3. "＋ 新对话" 按钮调用 `startNew()` 并跳转 `/?` 清空对话
4. 对话历史按 TODAY / 昨天 / 本周 / 更早 分组，最多显示 30 条
5. 当前对话在列表中有高亮
6. 新发一条消息后，侧边栏列表刷新显示最新对话
7. 删除交互：hover 显示"删"，第一次点变"确定？"，3s 无操作自动重置，再点则删除
8. 画像 / 记忆 / 设置 NavLink 激活时有高亮样式
9. Chat 页面不再有 sticky sub-header，无"翻翻之前"按钮
10. Profile、Memories、Settings 页面正常渲染，无布局错位
