import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { getProfile, patchProfile, resetProfile, uploadResume } from '../lib/api'

// ── 常量 ──

const ACCEPT_EXT = ['.pdf', '.docx', '.txt', '.md']

const GRADE_OPTIONS = [
  ['freshman', '大一'],
  ['sophomore', '大二'],
  ['junior', '大三'],
  ['senior', '大四'],
  ['graduate1', '研一'],
  ['graduate2', '研二'],
  ['graduate3', '研三'],
]

// ── 类型 ──

interface ProfileData {
  content: string
}

// ── 主组件 ──

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 加载画像
  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p)
        setDraft(p.content || '')
      })
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }, [])

  // 上传简历
  async function handleUpload(file: File) {
    setError(null)
    setBusy(true)
    try {
      const res = await uploadResume(file)
      // 后端返回 { success, message, preview, content_length }
      // 上传成功后重新加载画像
      const profileData = await getProfile()
      setProfile(profileData)
      setDraft(profileData.content || '')
    } catch (e) {
      setError((e as Error).message || '上传失败')
    } finally {
      setBusy(false)
    }
  }

  // 保存画像
  async function handleSave() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const next = await patchProfile({ content: draft })
      setProfile(next)
      setEditing(false)
    } catch (e) {
      setError((e as Error).message || '保存失败')
    } finally {
      setBusy(false)
    }
  }

  // 重置画像
  async function handleReset() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const next = await resetProfile()
      setProfile(next)
      setDraft(next.content || '')
      setEditing(false)
    } catch (e) {
      setError((e as Error).message || '重置失败')
    } finally {
      setBusy(false)
    }
  }

  // 加载中
  if (loading) {
    return (
      <div className="mx-auto max-w-[720px] px-md py-2xl">
        <div className="ink-progress mt-2xl" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[720px] px-md py-2xl ink-fade-in">
      {/* 标题 */}
      <header className="mb-lg">
        <h1 className="text-2xl font-han text-ink">画像</h1>
        <p className="text-text-muted text-base mt-xs">
          你的核心信息，AI 每次对话都会参考
        </p>
      </header>

      {/* 上传简历 — 有内容后隐藏 */}
      {!profile?.content && (
        <UploadZone onUpload={handleUpload} busy={busy} />
      )}

      {/* 错误提示 */}
      {error && (
        <p className="mt-md text-sm text-danger">{error}</p>
      )}

      {/* 画像内容 */}
      <div className="mt-lg">
        <div className="flex items-center justify-between mb-sm">
          <h2 className="text-lg text-ink">核心记忆</h2>
          <div className="flex gap-sm">
            {editing ? (
              <>
                <button
                  onClick={handleSave}
                  disabled={busy}
                  className="text-sm text-ink hover:text-ink-deep disabled:opacity-50"
                >
                  {busy ? '保存中...' : '保存'}
                </button>
                <button
                  onClick={() => {
                    setEditing(false)
                    setDraft(profile?.content || '')
                  }}
                  disabled={busy}
                  className="text-sm text-text-muted hover:text-text disabled:opacity-50"
                >
                  取消
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setEditing(true)}
                  className="text-sm text-text-muted hover:text-text"
                >
                  编辑
                </button>
                <button
                  onClick={handleReset}
                  disabled={busy}
                  className="text-sm text-text-subtle hover:text-danger disabled:opacity-50"
                >
                  重置
                </button>
              </>
            )}
          </div>
        </div>

        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full h-[500px] p-md font-mono text-sm border border-border rounded-lg bg-bg resize-y"
            placeholder="在这里编辑你的核心记忆..."
          />
        ) : (
          <div className="p-md border border-border rounded-lg bg-surface min-h-[200px]">
            {profile?.content ? (
              <article className="prose">
                <Markdown>{profile.content}</Markdown>
              </article>
            ) : (
              <p className="text-text-muted text-sm">
                还没有画像信息，上传简历或手动编辑
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 上传组件 ──

function UploadZone({
  onUpload,
  busy,
}: {
  onUpload: (f: File) => Promise<void>
  busy: boolean
}) {
  const [drag, setDrag] = useState(false)

  function handleFile(file: File) {
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
    if (!ACCEPT_EXT.includes(ext)) {
      alert('这种文件我读不来.要 PDF / DOCX / TXT / MD.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('文件有点大,精简到 10MB 以内?')
      return
    }
    onUpload(file)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleFile(f)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = ACCEPT_EXT.join(',')
        input.onchange = (e) => {
          const f = (e.target as HTMLInputElement).files?.[0]
          if (f) handleFile(f)
        }
        input.click()
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          e.currentTarget.click()
        }
      }}
      onDrop={onDrop}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      className={[
        'flex flex-col items-center justify-center gap-2xs px-md py-lg',
        'min-h-[120px]',
        'border border-dashed cursor-pointer transition-colors rounded-lg',
        drag ? 'border-ink bg-surface' : 'border-border-soft hover:border-border',
        busy ? 'opacity-60 pointer-events-none' : '',
      ].join(' ')}
    >
      <p className="text-base text-text">
        拖一份简历过来
      </p>
      <p className="text-sm text-text-muted">或点击选个文件</p>
      <p className="text-xs text-text-subtle font-latin tracking-wide">
        PDF · DOCX · TXT · MD
      </p>
    </div>
  )
}
