import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  diagnoseJD,
  getProfile,
  type GapSkill,
  type JDDiagnoseResponse,
  type Profile,
} from '../lib/api'

const PRIORITY_HINT: Record<string, string> = {
  high: '先补这个',
  medium: '可以补',
  low: '再说',
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

export default function JDPage() {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<JDDiagnoseResponse | null>(null)
  const [profileFilled, setProfileFilled] = useState<boolean | null>(null)

  useEffect(() => {
    getProfile()
      .then((p) => setProfileFilled(isFilled(p)))
      .catch(() => setProfileFilled(false))
  }, [])

  async function submit() {
    const trimmed = text.trim()
    if (trimmed.length < 10) {
      setError('再多贴点,这样我看不出来.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await diagnoseJD(trimmed)
      setResult(res)
    } catch (e) {
      setError((e as Error).message || '我刚才走神了,你再问我一遍.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[820px] px-md py-2xl flex flex-col gap-2xl">
      <header className="ink-fade-in">
        <h2 className="text-2xl">把你看上的 JD 贴进来,</h2>
        <h2 className="text-2xl">我帮你看看够不够格.</h2>
      </header>

      {profileFilled === false ? (
        <p className="text-text-muted text-sm ink-fade-in">
          你还没填画像, 我只能笼统说说.{' '}
          <Link to="/profile" className="text-ink hover:text-ink-deep">
            先去画像页?
          </Link>
        </p>
      ) : null}

      <div className="flex flex-col gap-md">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="把你看上的那段贴上来,我们对一对."
          rows={10}
          className="w-full min-h-[240px] resize-y border-y border-border-soft py-md text-base leading-relaxed placeholder:text-text-subtle focus:border-ink"
        />
        <div className="flex justify-center">
          <button
            onClick={submit}
            disabled={busy || text.trim().length === 0}
            className="text-ink hover:text-ink-deep text-lg disabled:text-text-subtle disabled:cursor-not-allowed"
            aria-label="提交 JD 让学长看看"
          >
            {busy ? '…' : '让学长看看'}
          </button>
        </div>
      </div>

      {busy ? (
        <div className="flex flex-col gap-xs">
          <p className="text-text-muted text-sm">我在比对...</p>
          <div className="ink-progress" />
        </div>
      ) : null}

      {error ? <p className="text-danger text-sm">{error}</p> : null}

      {result ? <Result data={result} profileFilled={profileFilled} /> : null}
    </div>
  )
}

function Result({
  data,
  profileFilled,
}: {
  data: JDDiagnoseResponse
  profileFilled: boolean | null
}) {
  const have = [...data.matched_skills, ...data.strengths]

  return (
    <div className="flex flex-col gap-2xl ink-fade-in">
      <div className="h-px w-full bg-border-soft" />

      <div className="flex flex-col gap-xs">
        {data.jd_title ? (
          <p className="text-text-subtle text-sm">{data.jd_title}</p>
        ) : null}
        <div className="font-mono text-3xl text-ink leading-none">
          {data.overall_score}
        </div>
        <p className="text-sm text-text-muted">
          / 100{data.summary ? ` · ${data.summary}` : ''}
        </p>
      </div>

      {have.length > 0 ? (
        <Section caption="你已经具备的">
          <BulletList items={have} />
        </Section>
      ) : null}

      {data.skill_gaps.length > 0 ? (
        <Section caption="你还缺的">
          <ul className="flex flex-col gap-xs">
            {data.skill_gaps.map((g, i) => (
              <GapItem key={i} g={g} />
            ))}
          </ul>
        </Section>
      ) : null}

      {data.risks.length > 0 ? (
        <Section caption="提个醒">
          <BulletList items={data.risks} />
        </Section>
      ) : null}

      {data.action_plan.length > 0 ? (
        <Section caption="下一步建议">
          <ol className="flex flex-col gap-sm">
            {data.action_plan.map((a, i) => (
              <li key={i} className="flex gap-md text-base text-text">
                <span className="font-mono text-text-subtle min-w-[1.5rem]">
                  {i + 1}.
                </span>
                <span className="flex-1">{a}</span>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}

      {data.resume_tips.length > 0 ? (
        <Section caption="改简历的话">
          <BulletList items={data.resume_tips} />
        </Section>
      ) : null}

      {profileFilled === false ? (
        <p className="text-text-muted text-sm">
          想更准确?{' '}
          <Link to="/profile" className="text-ink hover:text-ink-deep">
            去补全画像 →
          </Link>
        </p>
      ) : null}
    </div>
  )
}

function Section({
  caption,
  children,
}: {
  caption: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-md">
      <h3 className="text-lg">{caption}</h3>
      {children}
    </section>
  )
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-2xs">
      {items.map((s, i) => (
        <li key={i} className="flex items-baseline gap-sm text-base text-text">
          <span className="text-text-subtle">·</span>
          <span className="flex-1">{s}</span>
        </li>
      ))}
    </ul>
  )
}

function GapItem({ g }: { g: GapSkill }) {
  const right = g.suggested_hours
    ? `约 ${g.suggested_hours} 小时`
    : (PRIORITY_HINT[g.priority] ?? g.priority)
  return (
    <li className="flex items-baseline gap-sm text-base text-text">
      <span className="text-text-subtle">·</span>
      <span className="flex-1">{g.skill}</span>
      <span className="text-text-muted text-sm shrink-0">{right}</span>
    </li>
  )
}
