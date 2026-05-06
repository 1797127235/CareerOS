import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { getMemoryContent, resetMemory } from '../lib/api'

export default function ProfilePage() {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getMemoryContent()
      .then((p) => setContent(p.content || ''))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleReset() {
    if (busy) return
    if (!confirm('确定要重置所有记忆吗？这会清空你的画像、技能和经历。')) return
    setBusy(true)
    setError(null)
    try {
      await resetMemory()
      const p = await getMemoryContent()
      setContent(p.content || '')
    } catch (e) {
      setError((e as Error).message || '重置失败')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[720px] px-md py-2xl">
        <div className="ink-progress mt-2xl" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[720px] px-md py-2xl ink-fade-in">
      <header className="mb-lg">
        <h1 className="text-2xl font-han text-ink">画像</h1>
        <p className="text-text-muted text-base mt-xs">
          AI 从对话中自动学习你的信息
        </p>
      </header>

      {error && (
        <p className="mt-md text-sm text-danger">{error}</p>
      )}

      <div className="mt-lg">
        <div className="flex items-center justify-between mb-sm">
          <h2 className="text-lg text-ink">核心记忆</h2>
          <button
            onClick={handleReset}
            disabled={busy}
            className="text-sm text-text-subtle hover:text-danger disabled:opacity-50"
          >
            {busy ? '重置中...' : '重置'}
          </button>
        </div>

        <div className="p-md border border-border rounded-lg bg-surface min-h-[200px]">
          {content ? (
            <article className="prose">
              <Markdown>{content}</Markdown>
            </article>
          ) : (
            <p className="text-text-muted text-sm">
              还没有画像信息，在对话中告诉 AI 你的信息
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
