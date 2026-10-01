import { useMemo, useState } from 'react'
import { paths } from '../api'
import { Card, CardHeader, EmptyState, ErrorState, ImprovementCard, LoadingSkeleton, NoResume, PageHeader, SkillBadge, Tabs } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

function Keywords({ kw }) {
  const groups = [
    { title: 'Strong keywords', tone: 'green', icon: 'check', items: kw.strong, note: 'Already in your resume and asked for by the role.' },
    { title: 'Missing keywords', tone: 'red', icon: 'x', items: kw.missing, note: 'Required by the role and not found in your resume.' },
    { title: 'Recommended keywords', tone: 'blue', icon: 'info', items: kw.recommended, note: 'Nice to have, or close to something you already know.' },
  ]
  return (
    <Card>
      <CardHeader title="Keyword analysis" icon={<Icon name="key" size={18} className="text-ss-g-ink" />} />
      <div className="grid gap-5 p-5 md:grid-cols-3">
        {groups.map((g) => (
          <section key={g.title}>
            <h3 className="font-semibold">{g.title}</h3>
            <p className="mt-0.5 text-xs text-ss-mute">{g.note}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {g.items.length ? (
                g.items.map((k) => (
                  <SkillBadge key={k.keyword} tone={g.tone} icon={g.icon}>
                    {k.keyword}
                    {g.tone === 'green' && !k.shown ? ' · list only' : ''}
                  </SkillBadge>
                ))
              ) : (
                <span className="text-sm text-ss-sub">None</span>
              )}
            </div>
          </section>
        ))}
      </div>
      <p className="flex items-start gap-2 border-t border-ss-line px-5 py-3 text-sm text-ss-sub">
        <Icon name="alert" size={16} className="mt-0.5 text-ss-a-ink" />
        {kw.note}
      </p>
    </Card>
  )
}

export default function Improvements() {
  const { resumeId } = useSkillSync()
  const { data, error, loading, retry } = useQuery(resumeId ? paths.improvements(resumeId) : null)
  const [cat, setCat] = useState('All')
  const [prio, setPrio] = useState('all')

  const items = useMemo(() => (data ? data.items.filter((i) => (cat === 'All' || i.category === cat) && (prio === 'all' || i.priority === prio)) : []), [data, cat, prio])

  if (!resumeId) return <NoResume />
  if (error) return <ErrorState error={error} onRetry={retry} />
  if (loading) return <LoadingSkeleton message="Preparing your recommendations…" rows={4} />

  const count = (c) => data.items.filter((i) => c === 'All' || i.category === c).length
  return (
    <>
      <PageHeader
        title="Improvements"
        subtitle="Actionable recommendations to make your profile stronger."
        actions={
          <label className="flex items-center gap-2 text-sm text-ss-sub">
            Priority
            <select value={prio} onChange={(e) => setPrio(e.target.value)} className="h-10 rounded-xl border border-ss-line bg-ss-card px-3 text-sm font-medium text-ss-ink focus:outline-none">
              <option value="all">All</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </label>
        }
      />
      <div className="mb-5">
        <Tabs label="Category" value={cat} onChange={setCat} tabs={['All', ...data.categories].map((c) => ({ id: c, label: c, count: count(c) }))} />
      </div>

      {cat === 'Keywords' && (
        <div className="mb-5">
          <Keywords kw={data.keywords} />
        </div>
      )}

      {items.length ? (
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.id}>
              <ImprovementCard item={item} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon="star" message="Your profile is looking strong. We'll show new recommendations when we find opportunities to improve." />
      )}

      {cat === 'All' && (
        <div className="mt-6">
          <Keywords kw={data.keywords} />
        </div>
      )}
    </>
  )
}
