import { useState } from 'react'
import { Link } from 'react-router-dom'
import { paths } from '../api'
import { Card, CardHeader, ErrorState, LoadingSkeleton, NoResume, PageHeader, ScoreRing } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

const HELP = {
  ats: 'Can an applicant tracking system find the standard sections: contact, summary, experience, education, skills and dates?',
  skills: 'Average share of required skills you cover across postings for your target role.',
  projects: 'Number of projects, and whether each lists its tech, explains what it does and shows an outcome or link.',
  experience: 'Share of bullets that start with an action and avoid vague phrasing, plus how many include numbers.',
  keywords: 'Share of the core keywords for your target role that appear in your resume.',
  structure: 'Summary length, bullets per role, vague bullets, number of projects, and certifications or achievements.',
}

function Column({ title, icon, tone, items, empty }) {
  const t = { green: ['bg-ss-g-bg/60', 'text-ss-g-ink'], red: ['bg-ss-r-bg/60', 'text-ss-r-ink'], blue: ['bg-ss-b-bg/60', 'text-ss-b-ink'] }[tone]
  return (
    <section className={`rounded-[18px] border border-ss-line p-5 ${t[0]}`}>
      <h2 className={`flex items-center gap-2 font-semibold ${t[1]}`}>
        <Icon name={icon} size={18} />
        <span className="text-ss-ink">{title}</span>
      </h2>
      {items.length ? (
        <ul className="mt-4 space-y-3">
          {items.map((text) => (
            <li key={text} className="flex gap-2.5 text-sm text-ss-ink">
              <Icon name={tone === 'red' ? 'x' : 'check'} size={16} strokeWidth={2.4} className={`mt-0.5 ${t[1]}`} />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-ss-sub">{empty}</p>
      )}
    </section>
  )
}

export default function ResumeAnalysis() {
  const { resumeId } = useSkillSync()
  const { data, error, loading, retry } = useQuery(resumeId ? paths.analysis(resumeId) : null)
  const [full, setFull] = useState(false)
  if (!resumeId) return <NoResume />
  if (error) return <ErrorState error={error} onRetry={retry} />
  if (loading) return <LoadingSkeleton message="Analyzing your resume…" rows={3} />

  const message =
    data.overall >= 85
      ? 'Your resume is strong! A few improvements can make it even better.'
      : data.overall >= 70
        ? 'Your resume is in good shape. The changes below will make it stand out.'
        : 'Your resume has a solid base. Work through the changes below to raise your score.'

  return (
    <>
      <PageHeader title="Resume Analysis" subtitle="Detailed analysis of your resume with AI insights." />
      <Card className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:p-6">
        <ScoreRing value={data.overall} size={104} stroke={9} big label="Overall resume score" />
        <div className="flex-1">
          <h2 className="text-xl font-semibold">Overall Resume Score</h2>
          <p className="mt-1 text-ss-sub">{message}</p>
          <p className="mt-1 text-sm text-ss-mute">
            Measured against <strong className="font-semibold text-ss-sub">{data.target_role_title}</strong> roles · {data.grade}
          </p>
        </div>
        <button type="button" className="ss-btn self-start sm:self-center" onClick={() => setFull((f) => !f)} aria-expanded={full}>
          {full ? 'Hide Details' : 'View Full Analysis'}
        </button>
      </Card>

      <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {data.scores.map((s) => (
          <li key={s.key} className="ss-card flex flex-col items-center p-4 text-center" title={HELP[s.key]}>
            <p className="text-[13px] font-semibold text-ss-sub">{s.label}</p>
            <div className="mt-3">
              <ScoreRing value={s.value} size={62} label={s.label} />
            </div>
          </li>
        ))}
      </ul>

      {full && (
        <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title="What each score measures" />
            <dl className="divide-y divide-ss-line">
              {data.scores.map((s) => (
                <div key={s.key} className="px-5 py-3 text-sm">
                  <dt className="font-semibold">
                    {s.label} · {s.value}
                  </dt>
                  <dd className="mt-0.5 text-ss-sub">{HELP[s.key]}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card>
            <CardHeader title="ATS checks" />
            <ul className="divide-y divide-ss-line">
              {data.ats_checks.map((c) => (
                <li key={c.label} className="flex items-center justify-between px-5 py-3 text-sm">
                  {c.label}
                  <span className={`inline-flex items-center gap-1 font-semibold ${c.ok ? 'text-ss-g-ink' : 'text-ss-r-ink'}`}>
                    <Icon name={c.ok ? 'check' : 'x'} size={15} strokeWidth={2.5} />
                    {c.ok ? 'Found' : 'Missing'}
                  </span>
                </li>
              ))}
            </ul>
            <p className="border-t border-ss-line px-5 py-3 text-xs text-ss-mute">
              {data.bullet_stats.total} experience bullets · {data.bullet_stats.with_metrics} with numbers · {data.bullet_stats.vague} vague
            </p>
          </Card>
        </div>
      )}

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Column title="What’s Working" icon="check" tone="green" items={data.whats_working} empty="Add measurable results and role skills to build strengths here." />
        <Column title="Needs Improvement" icon="alert" tone="red" items={data.needs_improvement} empty="Nothing major — nice work." />
        <Column title="Recommended Changes" icon="improve" tone="blue" items={data.recommended_changes} empty="Your profile is looking strong. We'll show new recommendations when we find opportunities to improve." />
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        <Link to="/app/improvements" className="ss-btn">
          See step-by-step improvements <Icon name="arrow" size={16} />
        </Link>
        <Link to="/app/skills" className="ss-btn2">
          Compare skills
        </Link>
      </div>
    </>
  )
}
