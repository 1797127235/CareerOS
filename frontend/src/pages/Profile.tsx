import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import {
  getProfile,
  patchProfile,
  uploadResume,
  type Profile,
  type SkillItem,
} from '../lib/api'

const SCHOOL_LEVEL: Array<[string, string]> = [
  ['985', '985'],
  ['211', '211'],
  ['double_first_class', '双一流'],
  ['normal', '普通本科'],
]

const GRADE: Array<[string, string]> = [
  ['freshman', '大一'],
  ['sophomore', '大二'],
  ['junior', '大三'],
  ['senior', '大四'],
  ['graduate1', '研一'],
  ['graduate2', '研二'],
  ['graduate3', '研三'],
]

const COMPANY_LEVEL: Array<[string, string]> = [
  ['top', '大厂'],
  ['major', '一线'],
  ['medium', '中厂'],
  ['state_owned', '国企'],
]

const SKILL_LEVEL: Array<[string, string]> = [
  ['beginner', '入门'],
  ['familiar', '熟练'],
  ['intermediate', '一般'],
  ['advanced', '精通'],
]

const ACCEPT_EXT = ['.pdf', '.docx', '.txt', '.md']

function labelOf(table: Array<[string, string]>, key: string | null | undefined): string {
  if (!key) return ''
  return table.find(([k]) => k === key)?.[1] ?? key
}

function isFilled(p: Profile | null): boolean {
  if (!p) return false
  return Boolean(
    p.school_name ||
      p.major ||
      p.target_direction ||
      (p.current_skills && p.current_skills.length > 0),
  )
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProfile()
      .then((p) => setProfile(p))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }, [])

  async function handleUpload(file: File) {
    const res = await uploadResume(file)
    setProfile(res.profile)
  }

  async function handlePatch(patch: Partial<Profile>) {
    const next = await patchProfile(patch)
    setProfile(next)
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[720px] px-md py-2xl">
        <div className="ink-progress mt-2xl" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[720px] px-md py-2xl">
      {isFilled(profile) ? (
        <FilledProfile
          profile={profile!}
          onPatch={handlePatch}
          onReupload={handleUpload}
        />
      ) : (
        <EmptyState onUpload={handleUpload} />
      )}
    </div>
  )
}

function EmptyState({ onUpload }: { onUpload: (f: File) => Promise<void> }) {
  return (
    <div className="flex flex-col gap-xl ink-fade-in">
      <header>
        <h2 className="text-2xl">先扔一份简历给我.</h2>
        <p className="text-text-muted text-base mt-xs">我看看你现在在哪一格.</p>
      </header>
      <UploadZone mode="full" onUpload={onUpload} />
    </div>
  )
}

function FilledProfile({
  profile,
  onPatch,
  onReupload,
}: {
  profile: Profile
  onPatch: (p: Partial<Profile>) => Promise<void>
  onReupload: (f: File) => Promise<void>
}) {
  return (
    <div className="flex flex-col gap-xl ink-fade-in">
      <header>
        <h2 className="text-2xl">这是你现在的样子.</h2>
        <p className="text-text-muted text-base mt-xs">从你上传的简历里读出来的.</p>
      </header>

      <Divider />

      <Section caption="学校 / 专业">
        <EditableLine
          value={profile.school_name}
          display={profile.school_name || '学校 —'}
          onSave={(v) => onPatch({ school_name: v || null })}
          renderInput={(v, set) => (
            <input
              autoFocus
              value={v}
              onChange={(e) => set(e.target.value)}
              className="w-full text-lg border-b border-border-soft focus:border-ink py-2xs"
              placeholder="学校"
            />
          )}
        />
        <EditableLine
          value={profile.major}
          display={profile.major || '专业 —'}
          onSave={(v) => onPatch({ major: v || null })}
          renderInput={(v, set) => (
            <input
              autoFocus
              value={v}
              onChange={(e) => set(e.target.value)}
              className="w-full text-lg border-b border-border-soft focus:border-ink py-2xs"
              placeholder="专业"
            />
          )}
        />
        <EditableLine
          muted
          value={profile.school_level}
          display={
            profile.school_level
              ? labelOf(SCHOOL_LEVEL, profile.school_level)
              : '学校层级 —'
          }
          onSave={(v) => onPatch({ school_level: v || null })}
          renderInput={(v, set) => (
            <SelectInput value={v} onChange={set} options={SCHOOL_LEVEL} />
          )}
        />
        <EditableLine
          muted
          value={profile.grade}
          display={profile.grade ? labelOf(GRADE, profile.grade) : '年级 —'}
          onSave={(v) => onPatch({ grade: v || null })}
          renderInput={(v, set) => (
            <SelectInput value={v} onChange={set} options={GRADE} />
          )}
        />
        <EditableLine
          muted
          value={profile.graduation_year ? String(profile.graduation_year) : ''}
          display={
            profile.graduation_year ? `${profile.graduation_year} 毕业` : '毕业年份 —'
          }
          onSave={(v) => {
            const n = Number.parseInt(v, 10)
            return onPatch({ graduation_year: Number.isFinite(n) ? n : null })
          }}
          renderInput={(v, set) => (
            <input
              autoFocus
              type="number"
              min={2020}
              max={2035}
              value={v}
              onChange={(e) => set(e.target.value)}
              className="w-32 text-base border-b border-border-soft focus:border-ink py-2xs"
            />
          )}
        />
      </Section>

      <Section caption="目标方向">
        <EditableLine
          value={profile.target_direction}
          display={profile.target_direction || '方向 —'}
          onSave={(v) => onPatch({ target_direction: v || null })}
          renderInput={(v, set) => (
            <input
              autoFocus
              value={v}
              onChange={(e) => set(e.target.value)}
              className="w-full text-lg border-b border-border-soft focus:border-ink py-2xs"
              placeholder="后端 / 前端 / 算法 / AI ..."
            />
          )}
        />
        <EditableLine
          muted
          value={profile.target_company_level}
          display={
            profile.target_company_level
              ? `目标公司层级:${labelOf(COMPANY_LEVEL, profile.target_company_level)}`
              : '目标公司层级 —'
          }
          onSave={(v) => onPatch({ target_company_level: v || null })}
          renderInput={(v, set) => (
            <SelectInput value={v} onChange={set} options={COMPANY_LEVEL} />
          )}
        />
      </Section>

      <Section caption="现有技能">
        <SkillList
          skills={profile.current_skills ?? []}
          onChange={(skills) => onPatch({ current_skills: skills })}
        />
      </Section>

      <Divider />

      <UploadZone mode="compact" onUpload={onReupload} />
    </div>
  )
}

function Divider() {
  return <div className="h-px w-full bg-border-soft" />
}

function Section({
  caption,
  children,
}: {
  caption: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-sm">
      <div className="text-xs text-text-subtle uppercase tracking-wider font-latin">
        {caption}
      </div>
      <div className="flex flex-col gap-xs">{children}</div>
    </section>
  )
}

function EditableLine({
  value,
  display,
  onSave,
  renderInput,
  muted,
}: {
  value: string | null | undefined
  display: string
  onSave: (v: string) => Promise<void> | void
  renderInput: (v: string, set: (s: string) => void) => React.ReactNode
  muted?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [savedFlash, setSavedFlash] = useState(false)

  function start() {
    setDraft(value ?? '')
    setEditing(true)
  }
  function cancel() {
    setEditing(false)
    setDraft('')
  }
  async function commit() {
    if (busy) return
    setBusy(true)
    try {
      await onSave(draft.trim())
      setEditing(false)
      setDraft('')
      setSavedFlash(true)
      setTimeout(() => setSavedFlash(false), 1500)
    } finally {
      setBusy(false)
    }
  }
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      commit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      cancel()
    }
  }

  if (editing) {
    return (
      <div className="flex flex-col gap-2xs" onKeyDown={onKeyDown}>
        {renderInput(draft, setDraft)}
        <p className="text-xs text-text-subtle">
          Enter 记下来 · Esc 再想想{busy ? ' · 记中' : ''}
        </p>
      </div>
    )
  }

  return (
    <div className="group flex items-baseline gap-md">
      <div
        className={
          (muted ? 'text-sm text-text-muted' : 'text-lg text-text') +
          ' border-b border-dashed border-border-soft/40 group-hover:border-border-soft transition-colors'
        }
      >
        {display}
      </div>
      {savedFlash ? (
        <span className="text-xs text-success ink-fade-in">✓ 记下来了</span>
      ) : (
        <button
          onClick={start}
          className="text-xs text-text-subtle opacity-0 group-hover:opacity-100 transition-opacity hover:text-ink"
          aria-label="修改这一行"
        >
          修改
        </button>
      )}
    </div>
  )
}

function SelectInput({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: Array<[string, string]>
}) {
  return (
    <select
      autoFocus
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="text-base bg-bg border-b border-border-soft focus:border-ink py-2xs pr-md"
    >
      <option value="">—</option>
      {options.map(([k, label]) => (
        <option key={k} value={k}>
          {label}
        </option>
      ))}
    </select>
  )
}

function SkillList({
  skills,
  onChange,
}: {
  skills: SkillItem[]
  onChange: (s: SkillItem[]) => Promise<void> | void
}) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [level, setLevel] = useState('familiar')

  async function remove(idx: number) {
    const next = skills.filter((_, i) => i !== idx)
    await onChange(next)
  }
  async function add() {
    const trimmed = name.trim()
    if (!trimmed) return
    await onChange([...skills, { name: trimmed, level }])
    setName('')
    setLevel('familiar')
    setAdding(false)
  }
  async function changeLevel(idx: number, lv: string) {
    const next = skills.map((s, i) => (i === idx ? { ...s, level: lv } : s))
    await onChange(next)
  }
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      add()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setAdding(false)
      setName('')
    }
  }

  return (
    <div className="flex flex-col gap-2xs">
      {skills.map((s, i) => (
        <SkillRow
          key={`${s.name}-${i}`}
          skill={s}
          onLevel={(lv) => changeLevel(i, lv)}
          onRemove={() => remove(i)}
        />
      ))}
      {adding ? (
        <div className="flex flex-col gap-2xs mt-xs" onKeyDown={onKeyDown}>
          <div className="flex items-center gap-md">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="技能名"
              className="flex-1 text-base border-b border-border-soft focus:border-ink py-2xs"
            />
            <span className="text-text-subtle">·</span>
            <SelectInput value={level} onChange={setLevel} options={SKILL_LEVEL} />
          </div>
          <p className="text-xs text-text-subtle">Enter 记下来 · Esc 再想想</p>
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="text-base text-ink hover:text-ink-deep self-start mt-xs"
        >
          + 添加一项
        </button>
      )}
    </div>
  )
}

function SkillRow({
  skill,
  onLevel,
  onRemove,
}: {
  skill: SkillItem
  onLevel: (lv: string) => void
  onRemove: () => void
}) {
  const [editing, setEditing] = useState(false)
  if (editing) {
    return (
      <div className="flex items-center gap-md">
        <span className="text-base">{skill.name}</span>
        <span className="text-text-subtle">·</span>
        <SelectInput
          value={skill.level}
          onChange={(lv) => {
            onLevel(lv)
            setEditing(false)
          }}
          options={SKILL_LEVEL}
        />
        <button
          onClick={() => setEditing(false)}
          className="text-xs text-text-subtle hover:text-text"
        >
          再想想
        </button>
      </div>
    )
  }
  return (
    <div className="group flex items-baseline gap-md">
      <div className="text-base border-b border-dashed border-border-soft/40 group-hover:border-border-soft transition-colors">
        {skill.name} <span className="text-text-subtle">·</span>{' '}
        <span className="text-text-muted">{labelOf(SKILL_LEVEL, skill.level)}</span>
      </div>
      <button
        onClick={() => setEditing(true)}
        className="text-xs text-text-subtle opacity-0 group-hover:opacity-100 transition-opacity hover:text-ink"
      >
        改一改
      </button>
      <button
        onClick={onRemove}
        className="text-xs text-text-subtle opacity-0 group-hover:opacity-100 transition-opacity hover:text-danger"
      >
        划掉这条
      </button>
    </div>
  )
}

function UploadZone({
  mode,
  onUpload,
}: {
  mode: 'full' | 'compact'
  onUpload: (f: File) => Promise<void>
}) {
  const ref = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  function pick() {
    ref.current?.click()
  }

  async function handleFile(file: File) {
    setError(null)
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
    if (!ACCEPT_EXT.includes(ext)) {
      setError('这种文件我读不来.要 PDF / DOCX / TXT / MD.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('文件有点大,精简到 10MB 以内?')
      return
    }
    setBusy(true)
    try {
      await onUpload(file)
    } catch (e) {
      setError((e as Error).message || '我刚才走神了,你再传一遍.')
    } finally {
      setBusy(false)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleFile(f)
  }

  const minH = mode === 'full' ? 'min-h-[180px]' : 'min-h-[120px]'

  return (
    <div className="flex flex-col gap-sm">
      <div
        role="button"
        tabIndex={0}
        onClick={pick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            pick()
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
          minH,
          'border border-dashed cursor-pointer transition-colors',
          drag ? 'border-ink bg-surface' : 'border-border-soft hover:border-border',
          busy ? 'opacity-60 pointer-events-none' : '',
        ].join(' ')}
      >
        <p className="text-base text-text">
          {mode === 'full' ? '拖一份简历过来' : '拖一份新简历过来,我重新读一遍'}
        </p>
        <p className="text-sm text-text-muted">或点击选个文件</p>
        <p className="text-xs text-text-subtle font-latin tracking-wide">
          PDF · DOCX · TXT · MD
        </p>
        <input
          ref={ref}
          type="file"
          accept={ACCEPT_EXT.join(',')}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) handleFile(f)
            e.target.value = ''
          }}
        />
      </div>
      {busy ? (
        <div className="flex flex-col gap-xs">
          <p className="text-text-muted text-sm">我在读...</p>
          <div className="ink-progress" />
        </div>
      ) : null}
      {error ? <p className="text-danger text-sm">{error}</p> : null}
    </div>
  )
}
