import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { paths } from '../api'
import { Card, CardHeader, EmptyState, ErrorState, LoadingSkeleton, NoResume, PageHeader, PriorityBadge, SkillGap, TONE } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'strong', label: '✓ Strong' },
  { id: 'improve', label: '△ Improve' },
  { id: 'missing', label: '✕ Missing' },
]

export default function SkillAnalysis() {
  const { resumeId } = useSkillSync()
  const [draft, setDraft] = useState('')
  const [target, setTarget] = useState('')
  const [filter, setFilter] = useState('all')
  const opts = target.startsWith('job:') ? { jobId: target.slice(4) } : target ? { role: target } : {}
  const { data, error, loading, retry } = useQuery(resumeId ? paths.skills(resumeId, opts) : null)
  const { data: jobs } = useQuery(resumeId ? paths.matches(resumeId) : null)

  const rows = useMemo(() => (data ? data.skills.filter((r) => filter === 'all' || r.status === filter) : []), [data, filter])
  const recommended = useMemo(() => (data ? data.skills.filter((r) => r.status !== 'strong').slice(0, 6) : []), [data])

  if (!resumeId) return <NoResume />
  if (error) return <ErrorState error={error} onRetry={retry} />

  const current = target || (data ? (data.target.type === 'job' ? `job:${data.target.id}` : data.target.id) : '')

  return (
    <>
      <PageHeader
        title="Skill Gap Analysis"
        subtitle="Compare your skills with job requirements and find what to learn next."
        actions={
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              setTarget(draft || current)
            }}
          >
            <label className="text-xs font-semibold text-ss-sub">
              Target Role
              <select value={draft || current} onChange={(e) => setDraft(e.target.value)} className="mt-1 block h-10 w-[250px] max-w-full rounded-xl border border-ss-line bg-ss-card px-3 text-sm font-medium text-ss-ink focus:border-ss-green/50 focus:outline-none">
                <optgroup label="Roles">
                  {data?.roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Specific jobs">
                  {jobs?.matches.map((j) => (
                    <option key={j.id} value={`job:${j.id}`}>
                      {j.title} · {j.company}
                    </option>
                  ))}
                </optgroup>
              </select>
            </label>
            <button type="submit" className="ss-btn">
              Compare
            </button>
          </form>
        }
      />

      {loading || !data ? (
        <LoadingSkeleton message="Comparing your skills…" rows={4} />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-3 gap-3">
            {[
              ['strong', 'Strong', 'check', 'green'],
              ['improve', 'Improve', 'tri', 'amber'],
              ['missing', 'Missing', 'x', 'red'],
            ].map(([k, label, icon, tone]) => (
              <button key={k} type="button" onClick={() => setFilter(filter === k ? 'all' : k)} aria-pressed={filter === k} className={`rounded-[18px] border p-4 text-left transition ${TONE[tone]} ${filter === k ? 'border-current' : 'border-transparent'}`}>
                <span className="flex items-center gap-1.5 text-sm font-semibold">
                  <Icon name={icon} size={16} strokeWidth={2.4} /> {label}
                </span>
                <span className="mt-1 block text-[28px] font-bold leading-none text-ss-ink">{data.summary[k]}</span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <Card>
              <CardHeader
                title="Skills Comparison"
                action={<span className="hidden text-xs text-ss-mute sm:inline">vs {data.target.title}</span>}
              />
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ss-line px-5 py-2.5">
                <div className="flex gap-1" role="group" aria-label="Filter by status">
                  {FILTERS.map((f) => (
                    <button key={f.id} type="button" onClick={() => setFilter(f.id)} aria-pressed={filter === f.id} className={`rounded-lg px-2.5 py-1 text-xs font-medium ${filter === f.id ? 'bg-ss-pill text-ss-pill-ink' : 'text-ss-sub hover:bg-ss-soft'}`}>
                      {f.label}
                    </button>
                  ))}
                </div>
                <span className="text-xs text-ss-mute">Tap a skill for details</span>
              </div>
              {rows.length ? (
                <ul>
                  {rows.map((row) => (
                    <SkillGap key={row.skill} row={row} />
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-8 text-center text-sm text-ss-sub">No skills in this group.</p>
              )}
            </Card>

            <Card className="self-start">
              <CardHeader title="Recommended Skills" />
              {recommended.length ? (
                <ul className="divide-y divide-ss-line">
                  {recommended.map((r) => (
                    <li key={r.skill} className="flex gap-3 px-5 py-4">
                      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${r.status === 'missing' ? TONE.red : TONE.amber}`}>
                        <Icon name={r.status === 'missing' ? 'book' : 'improve'} size={19} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className="font-semibold">{r.skill}</p>
                          <PriorityBadge priority={r.priority} />
                        </div>
                        <p className="mt-1 text-sm text-ss-sub">{r.recommendation}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-5">
                  <EmptyState icon="star" message="Your profile is looking strong. We'll show new recommendations when we find opportunities to improve." />
                </div>
              )}
              <div className="border-t border-ss-line p-4">
                <Link to={`/app/assistant?q=${encodeURIComponent('What should I learn next?')}`} className="ss-btn2 w-full">
                  <Icon name="ai" size={16} /> Ask AI what to learn next
                </Link>
              </div>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
