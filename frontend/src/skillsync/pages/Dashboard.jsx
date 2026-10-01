import { Link, useNavigate } from 'react-router-dom'
import { paths, prefetch } from '../api'
import { Card, CardHeader, CompanyMark, DashboardCard, ErrorState, LoadingSkeleton, MatchScore, PageHeader, ResumeSummary, SkillBadge, StatusBadge } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'
import { SampleGrid } from './MyResume'

const greeting = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export default function Dashboard() {
  const { resumeId, openJd } = useSkillSync()
  const { data, error, loading, retry } = useQuery(resumeId ? paths.dashboard(resumeId) : null)
  const navigate = useNavigate()

  if (!resumeId)
    return (
      <>
        <PageHeader title={`${greeting()} 👋`} subtitle="Pick a sample resume or upload your own to see what SkillSync finds." />
        <Card className="mb-6 flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center">
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-ss-g-bg text-ss-g-ink">
            <Icon name="upload" size={26} />
          </span>
          <div className="flex-1">
            <h2 className="text-lg font-semibold">Upload a resume to unlock your personalized matches.</h2>
            <p className="mt-1 text-sm text-ss-sub">PDF, DOCX or TXT. Or try the demo with one of the 10 sample resumes below.</p>
          </div>
          <Link to="/app/resume" className="ss-btn">
            Upload Resume <Icon name="arrow" size={16} />
          </Link>
        </Card>
        <h2 className="mb-3 text-lg font-semibold">Choose Sample Resume</h2>
        <SampleGrid onPicked={() => navigate('/app')} />
      </>
    )
  if (error) return <ErrorState error={error} onRetry={retry} />
  if (loading || !data) return <LoadingSkeleton message="Analyzing your resume…" cards={4} rows={2} />

  const { profile, cards } = data
  const first = profile.name?.split(' ')[0] || 'there'
  return (
    <>
      <PageHeader title={`${greeting()}, ${first} 👋`} subtitle="Here’s what SkillSync found from your resume." />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <DashboardCard label="Resume Score" value={cards.resume_score} suffix="/100" icon="target" tone="green" to="/app/analysis" />
        <DashboardCard label="Job Matches" value={cards.job_matches} icon="jobs" tone="purple" to="/app/jobs" hint={`of ${cards.total_jobs} roles in the dataset`} />
        <DashboardCard label="Strong Matches" value={cards.strong_matches} icon="star" tone="blue" to="/app/jobs" hint="75% match or higher" />
        <DashboardCard label="Skills to Improve" value={cards.skills_to_improve} icon="skills" tone="red" to="/app/skills" hint={`for ${data.analysis.target_role_title} roles`} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Your Resume Profile"
            action={
              <Link to="/app/resume" className="text-sm font-medium text-ss-sub hover:text-ss-ink">
                View / Change
              </Link>
            }
          />
          <ResumeSummary profile={profile} />
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Top Job Matches"
              action={
                <Link to="/app/jobs" className="text-sm font-medium text-ss-sub hover:text-ss-ink">
                  View All
                </Link>
              }
            />
            <ul>
              {data.top_matches.map((job) => (
                <li key={job.id} className="border-b border-ss-line last:border-0">
                  <Link to={`/app/jobs/${job.id}`} onMouseEnter={() => prefetch(paths.job(job.id, resumeId))} className="flex gap-3 px-5 py-4 hover:bg-ss-soft/60">
                    <CompanyMark company={job.company} size={42} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-semibold leading-snug">{job.title}</p>
                        <MatchScore value={job.match} />
                      </div>
                      <p className="text-[13px] text-ss-sub">
                        {job.company} · {job.location}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {job.matched_skills.slice(0, 3).map((s) => (
                          <SkillBadge key={s} tone="green">
                            {s}
                          </SkillBadge>
                        ))}
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader
              title="Skills to work on"
              action={
                <Link to="/app/skills" className="text-sm font-medium text-ss-sub hover:text-ss-ink">
                  Skill Analysis
                </Link>
              }
            />
            <ul className="divide-y divide-ss-line">
              {data.top_gaps.map((g) => (
                <li key={g.skill} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">{g.skill}</p>
                    <p className="truncate text-xs text-ss-mute">{g.gap}</p>
                  </div>
                  <StatusBadge status={g.status} />
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Top improvements"
          action={
            <Link to="/app/improvements" className="text-sm font-medium text-ss-sub hover:text-ss-ink">
              See all
            </Link>
          }
        />
        <ul className="grid grid-cols-1 divide-y divide-ss-line md:grid-cols-3 md:divide-x md:divide-y-0">
          {data.top_improvements.map((i) => (
            <li key={i.id} className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ss-mute">
                {i.category} · <span className={i.priority === 'High' ? 'text-ss-r-ink' : 'text-ss-a-ink'}>{i.priority}</span>
              </p>
              <p className="mt-1 font-semibold">{i.title}</p>
              <p className="mt-1 line-clamp-3 text-sm text-ss-sub">{i.action}</p>
            </li>
          ))}
        </ul>
      </Card>

      <button type="button" onClick={openJd} className="mt-6 flex w-full items-center gap-4 rounded-[18px] border-2 border-dashed border-ss-b-ink/30 bg-ss-b-bg/50 p-5 text-left transition hover:bg-ss-b-bg/80">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-ss-card text-ss-b-ink">
          <Icon name="upload" size={22} />
        </span>
        <span className="flex-1">
          <span className="block font-semibold">Have a specific job in mind?</span>
          <span className="block text-sm text-ss-sub">Upload its job description (PDF or text) to see your match, skill gaps and what to improve.</span>
        </span>
        <span className="ss-btn hidden sm:inline-flex">Upload Job Description</span>
      </button>

      <Link to="/app/assistant" className="mt-6 flex items-center gap-4 rounded-[18px] border border-ss-line bg-ss-p-bg/70 p-5 transition hover:shadow-md">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-ss-card text-ss-p-ink">
          <Icon name="ai" size={24} />
        </span>
        <div className="flex-1">
          <p className="font-semibold">Ask the AI Career Assistant</p>
          <p className="text-sm text-ss-sub">Answers come only from your resume and the SkillSync job data, with sources.</p>
        </div>
        <Icon name="chevron" size={20} className="text-ss-p-ink" />
      </Link>
    </>
  )
}
