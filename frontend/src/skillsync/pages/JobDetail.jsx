import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteJob, invalidate, paths } from '../api'
import { ApplyLink, Bar, Card, CompanyMark, ErrorState, LoadingSkeleton, MatchScore, NoResume, SkillBadge, Tabs, UploadedBadge } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

function Section({ title, icon, tone, children }) {
  return (
    <section className="mt-5">
      <h3 className="flex items-center gap-2 font-semibold">
        {icon && <Icon name={icon} size={17} className={tone} />}
        {title}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  )
}

/** The job detail body, used in the Job Matches side panel and on its own page. */
export function JobDetailBody({ jobId, panel = false }) {
  const { resumeId, isSaved, toggleSaved } = useSkillSync()
  const { data: job, error, loading, retry } = useQuery(resumeId ? paths.job(jobId, resumeId) : null)
  const [tab, setTab] = useState('overview')
  const [confirm, setConfirm] = useState(false)
  const [showText, setShowText] = useState(false)
  const navigate = useNavigate()

  if (error) return <ErrorState error={error} onRetry={retry} message="We couldn't load this job." />
  if (loading || !job) return <LoadingSkeleton message="Comparing your skills…" rows={3} />

  const saved = isSaved(job.id)
  return (
    <div className={panel ? '' : 'p-5 sm:p-6'}>
      <div className="flex items-start gap-3">
        <CompanyMark company={job.company} size={52} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h2 className="text-xl font-semibold leading-snug">{job.title}</h2>
            <MatchScore value={job.match} size="lg" />
          </div>
          <p className="flex flex-wrap items-center gap-2 text-ss-sub">
            {job.company}
            {job.uploaded && <UploadedBadge />}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-ss-sub">
        <span className="inline-flex items-center gap-1.5">
          <Icon name="pin" size={16} /> {job.location}
        </span>
        <span className="rounded-lg bg-ss-soft px-2.5 py-1">{job.work_type}</span>
        <span className="rounded-lg bg-ss-soft px-2.5 py-1">{job.level}</span>
        <span className="rounded-lg bg-ss-soft px-2.5 py-1">{job.experience}</span>
      </div>

      <div className="mt-5 border-b border-ss-line pb-2">
        <Tabs
          label="Job details"
          value={tab}
          onChange={setTab}
          tabs={[
            { id: 'overview', label: 'Overview' },
            { id: 'requirements', label: 'Requirements' },
            { id: 'why', label: 'Why it Matches' },
          ]}
        />
      </div>

      {tab === 'overview' && (
        <>
          <p className="mt-4 text-[15px] leading-relaxed text-ss-sub">{job.summary}</p>
          <Section title="Skills you have" icon="check" tone="text-ss-g-ink">
            <div className="flex flex-wrap gap-1.5">
              {job.skills_you_have.length ? (
                job.skills_you_have.map((s) => (
                  <SkillBadge key={s.skill} tone="green" icon="check">
                    {s.skill}
                    {s.via ? ` (via ${s.via})` : ''}
                  </SkillBadge>
                ))
              ) : (
                <p className="text-sm text-ss-sub">None of the listed skills yet.</p>
              )}
              {job.skills_partial.map((s) => (
                <SkillBadge key={s.skill} tone="amber" icon="tri">
                  {s.skill} (related: {s.related})
                </SkillBadge>
              ))}
            </div>
          </Section>
          <Section title="Missing Skills" icon="x" tone="text-ss-r-ink">
            <div className="flex flex-wrap gap-1.5">
              {job.skills_missing.length ? (
                job.skills_missing.map((s) => (
                  <SkillBadge key={s.skill} tone={s.required ? 'red' : 'neutral'}>
                    {s.skill}
                    {!s.required && ' · nice to have'}
                  </SkillBadge>
                ))
              ) : (
                <p className="text-sm text-ss-sub">You cover every listed skill.</p>
              )}
            </div>
          </Section>
          <Section title="Why You Match">
            <p className="text-sm leading-relaxed text-ss-sub">{job.explanation}</p>
          </Section>
        </>
      )}

      {tab === 'requirements' && (
        <>
          <Section title="Responsibilities">
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-ss-sub">
              {job.responsibilities.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Section>
          <Section title="Requirements">
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-ss-sub">
              {job.requirements.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Section>
          {job.full_text && (
            <Section title="Your full job description">
              <button type="button" className="text-sm font-medium text-ss-b-ink hover:underline" onClick={() => setShowText((v) => !v)} aria-expanded={showText}>
                {showText ? 'Hide full text' : 'Show full text'}
              </button>
              {showText && <pre className="ss-scroll mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-ss-soft/70 p-4 font-ss text-sm text-ss-sub">{job.full_text}</pre>}
            </Section>
          )}
          <Section title="Skills listed">
            <div className="flex flex-wrap gap-1.5">
              {job.required_skills.map((s) => (
                <SkillBadge key={s} tone="blue">
                  {s}
                </SkillBadge>
              ))}
              {job.preferred_skills.map((s) => (
                <SkillBadge key={s} tone="neutral">
                  {s} · preferred
                </SkillBadge>
              ))}
            </div>
          </Section>
        </>
      )}

      {tab === 'why' && (
        <>
          <Section title="Why you match">
            <ul className="space-y-2">
              {job.why_you_match.map((w) => (
                <li key={w} className="flex gap-2 text-sm text-ss-sub">
                  <Icon name="check" size={16} strokeWidth={2.4} className="mt-0.5 text-ss-g-ink" />
                  {w}
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Score breakdown">
            <dl className="space-y-2.5">
              {[
                ['Required skills', job.breakdown.required_skills, '55%'],
                ['Preferred skills', job.breakdown.preferred_skills, '15%'],
                ['Role focus', job.breakdown.role_fit, '15%'],
                ['Experience level', job.breakdown.experience_fit, '15%'],
              ].map(([label, v, w]) => (
                <div key={label} className="grid grid-cols-[130px_1fr_40px] items-center gap-3 text-sm">
                  <dt className="text-ss-sub">
                    {label} <span className="text-xs text-ss-mute">({w})</span>
                  </dt>
                  <Bar value={v} tone={v >= 75 ? 'green' : v >= 45 ? 'amber' : 'red'} />
                  <dd className="text-right font-semibold">{v}%</dd>
                </div>
              ))}
            </dl>
          </Section>
          <Section title="Resume evidence">
            <ul className="space-y-2">
              {job.skills_you_have
                .filter((s) => s.evidence.length)
                .slice(0, 4)
                .map((s) => (
                  <li key={s.skill} className="rounded-xl bg-ss-soft/70 p-3 text-sm">
                    <p className="font-semibold">{s.skill}</p>
                    <p className="mt-0.5 text-ss-sub">
                      “{s.evidence[0].text}” <span className="text-ss-mute">— {s.evidence[0].where}</span>
                    </p>
                  </li>
                ))}
            </ul>
          </Section>
          {job.recommended_improvements.length > 0 && (
            <Section title="Recommended improvements">
              <ul className="space-y-2">
                {job.recommended_improvements.map((b) => (
                  <li key={b.skill} className="flex gap-3 rounded-xl border border-ss-line p-3 text-sm">
                    <span className="shrink-0 rounded-lg bg-ss-g-bg px-2 py-0.5 text-xs font-bold text-ss-g-ink">+{b.gain}</span>
                    <span>
                      <strong className="font-semibold">{b.skill}:</strong> <span className="text-ss-sub">{b.how_to_learn}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      )}

      <p className="mt-6 rounded-xl bg-ss-b-bg/60 p-3 text-xs text-ss-b-ink">
        <Icon name="info" size={13} className="-mt-0.5 mr-1 inline" />
        {job.uploaded ? (
          <>
            Added on {job.retrieved_at}. {job.source_note}
          </>
        ) : (
          <>
            Summarised from{' '}
            <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="font-semibold underline">
              {job.source_name}
            </a>{' '}
            on {job.retrieved_at}. {job.source_note}
          </>
        )}
      </p>

      <div className="mt-5 grid grid-cols-2 gap-2 sm:flex">
        <button type="button" className="ss-btn2 sm:flex-1" onClick={() => toggleSaved(job)} aria-pressed={saved}>
          <Icon name="bookmark" size={16} className={saved ? 'fill-current text-ss-green' : ''} />
          {saved ? 'Saved' : 'Save Job'}
        </button>
        <ApplyLink job={job} className="ss-btn sm:flex-1" label="Apply Now" />
        <button type="button" className={`ss-btn2 border-ss-p-ink/30 text-ss-p-ink ${job.uploaded ? '' : 'col-span-2 sm:flex-none'}`} onClick={() => navigate(`/app/assistant?job=${job.id}`)}>
          <Icon name="ai" size={16} /> Ask AI about this job
        </button>
      </div>
      {job.uploaded && (
        <div className="mt-3 text-right">
          {confirm ? (
            <span className="inline-flex flex-wrap items-center justify-end gap-2 text-sm text-ss-sub">
              Remove this job description?
              <button
                type="button"
                className="ss-btn2 h-8 border-ss-r-ink/40 px-3 text-[13px] text-ss-r-ink"
                onClick={async () => {
                  await deleteJob(job.id).catch(() => {})
                  invalidate()
                  navigate('/app/jobs')
                }}
              >
                Remove
              </button>
              <button type="button" className="ss-btn2 h-8 px-3 text-[13px]" onClick={() => setConfirm(false)}>
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" className="inline-flex items-center gap-1.5 text-sm text-ss-mute hover:text-ss-r-ink" onClick={() => setConfirm(true)}>
              <Icon name="trash" size={15} /> Remove this job description
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function JobDetail() {
  const { jobId } = useParams()
  const { resumeId } = useSkillSync()
  if (!resumeId) return <NoResume />
  return (
    <>
      <Link to="/app/jobs" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ss-sub hover:text-ss-ink">
        <Icon name="back" size={16} /> Job Matches
      </Link>
      <Card className="mx-auto max-w-3xl">
        <JobDetailBody jobId={jobId} />
      </Card>
    </>
  )
}
