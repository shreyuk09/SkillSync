import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { invalidate, paths, prefetch, uploadResume } from '../api'
import { Avatar, Card, CardHeader, ErrorState, LoadingSkeleton, PageHeader, ResumeSummary, RoleIcon, SkillBadge, Tabs } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

const TONES = ['green', 'blue', 'purple', 'amber', 'red']
const STEPS = ['Analyzing your resume…', 'Finding relevant opportunities…', 'Comparing your skills…', 'Preparing your recommendations…']

export function SampleGrid({ onPicked }) {
  const { data, error, loading, retry } = useQuery(paths.resumes())
  const { resumeId, setResumeId } = useSkillSync()
  if (error) return <ErrorState error={error} onRetry={retry} message="We couldn't load the sample resumes." />
  if (loading) return <LoadingSkeleton rows={2} />
  const pick = (id) => {
    setResumeId(id)
    onPicked?.(id)
  }
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {data.samples.map((r, i) => {
        const active = r.id === resumeId
        return (
          <li key={r.id}>
            <Card className={`flex h-full flex-col p-5 transition hover:-translate-y-0.5 hover:shadow-md ${active ? 'ring-2 ring-ss-green/50' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <RoleIcon role={r.target_role} tone={TONES[i % TONES.length]} />
                {active && (
                  <span className="rounded-full bg-ss-g-bg px-2 py-0.5 text-xs font-semibold text-ss-g-ink">
                    <Icon name="check" size={12} strokeWidth={2.6} className="-mt-0.5 mr-0.5 inline" />
                    In use
                  </span>
                )}
              </div>
              <h3 className="mt-3 font-semibold">{r.headline}</h3>
              <p className="text-sm text-ss-sub">
                Sample Resume · {r.name}
              </p>
              <p className="mt-0.5 text-xs text-ss-mute">
                {r.years_experience > 0 ? `${r.years_experience} yrs` : 'Fresher'} · {r.location}
              </p>
              <div className="mt-3 flex flex-wrap gap-1">
                {r.top_skills.slice(0, 4).map((s) => (
                  <SkillBadge key={s} tone="neutral" className="!px-2 !py-0.5 !text-[11.5px]">
                    {s}
                  </SkillBadge>
                ))}
              </div>
              <div className="mt-auto pt-4">
                <button
                  type="button"
                  onClick={() => pick(r.id)}
                  onMouseEnter={() => prefetch(paths.dashboard(r.id))}
                  className={active ? 'ss-btn2 w-full' : 'ss-btn w-full'}
                >
                  {active ? 'Open Dashboard' : 'View & Use'}
                </button>
              </div>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}

function Uploader() {
  const { setResumeId } = useSkillSync()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState(null)
  const [drag, setDrag] = useState(false)
  const input = useRef(null)

  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900)
    return () => clearInterval(t)
  }, [busy])

  const handle = async (file) => {
    if (!file) return
    setError(null)
    setBusy(true)
    setStep(0)
    try {
      const res = await uploadResume(file)
      invalidate('/resumes')
      setResumeId(res.id)
      navigate('/app')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5 sm:p-6">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          handle(e.dataTransfer.files?.[0])
        }}
        className={`flex flex-col items-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition ${drag ? 'border-ss-green bg-ss-g-bg/50' : 'border-ss-line bg-ss-soft/40'}`}
      >
        {busy ? (
          <div aria-live="polite" className="flex flex-col items-center">
            <span className="h-10 w-10 animate-spin rounded-full border-[3px] border-ss-line border-t-ss-green" />
            <p className="mt-4 font-semibold">{STEPS[step]}</p>
            <p className="mt-1 text-sm text-ss-sub">This usually takes a few seconds.</p>
          </div>
        ) : (
          <>
            <span className="grid h-14 w-14 place-items-center rounded-full bg-ss-green text-ss-on-green">
              <Icon name="upload" size={24} />
            </span>
            <p className="mt-4 text-lg font-semibold">Drop your resume here</p>
            <p className="mt-1 text-sm text-ss-sub">PDF, DOCX, TXT or an image · up to 8 MB</p>
            <button type="button" className="ss-btn mt-5" onClick={() => input.current?.click()}>
              Browse files
            </button>
            <input ref={input} type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp" className="sr-only" onChange={(e) => handle(e.target.files?.[0])} aria-label="Upload resume file" />
          </>
        )}
      </div>
      {error && (
        <div role="alert" className="mt-4 flex items-start gap-3 rounded-xl bg-ss-r-bg p-4 text-sm text-ss-r-ink">
          <Icon name="alert" size={18} className="mt-0.5" />
          <div>
            <p className="font-semibold">Something went wrong while analyzing your resume.</p>
            <p className="mt-0.5">{error.message} {error.hint}</p>
            <button type="button" className="mt-2 font-semibold underline" onClick={() => input.current?.click()}>
              Try Again
            </button>
          </div>
        </div>
      )}
      <p className="mt-4 flex items-start gap-2 text-xs text-ss-mute">
        <Icon name="shield" size={14} className="mt-0.5" />
        Your file is parsed on this server and stored only in this project's local data folder. It is never sent to the AI model except as short excerpts when you ask the assistant a question.
      </p>
    </Card>
  )
}

function Uploads() {
  const { data } = useQuery(paths.resumes())
  const { resumeId, setResumeId } = useSkillSync()
  if (!data?.uploads?.length) return null
  return (
    <Card className="mt-6">
      <CardHeader title="Your uploads" />
      <ul className="divide-y divide-ss-line">
        {data.uploads.map((r) => (
          <li key={r.id} className="flex items-center gap-3 px-5 py-3">
            <Avatar name={r.name} size={36} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{r.name}</p>
              <p className="truncate text-xs text-ss-mute">{r.source?.note}</p>
            </div>
            {r.id === resumeId ? (
              <span className="text-sm font-semibold text-ss-g-ink">In use</span>
            ) : (
              <button type="button" className="ss-btn2 h-9 text-[13px]" onClick={() => setResumeId(r.id)}>
                Use
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Current() {
  const { resumeId } = useSkillSync()
  const { data, loading } = useQuery(resumeId ? paths.resume(resumeId) : null)
  if (!resumeId) return null
  if (loading || !data) return <div className="ss-skel mb-6 h-40 rounded-[18px]" />
  return (
    <Card className="mb-6">
      <CardHeader
        title="Resume in use"
        action={
          <Link to="/app/analysis" className="ss-btn h-9 px-3 text-[13px]">
            View Analysis
          </Link>
        }
      />
      <ResumeSummary profile={data} />
      <div className="border-t border-ss-line px-5 py-3 text-xs text-ss-mute">
        <Icon name="info" size={13} className="-mt-0.5 mr-1 inline" />
        {data.source?.type === 'synthetic' ? `Synthetic sample · ${data.source.license}. ${data.source.note}` : data.source?.license}
      </div>
    </Card>
  )
}

export default function MyResume() {
  const [params, setParams] = useSearchParams()
  const { resumeId } = useSkillSync()
  const tab = params.get('tab') === 'samples' ? 'samples' : params.get('tab') === 'upload' ? 'upload' : resumeId ? 'samples' : 'upload'
  const navigate = useNavigate()
  return (
    <>
      <PageHeader title="My Resume" subtitle="Upload your resume or choose a sample resume to get started." />
      <Current />
      <div className="mb-5">
        <Tabs
          label="Resume source"
          value={tab}
          onChange={(t) => setParams({ tab: t }, { replace: true })}
          tabs={[
            { id: 'upload', label: 'Upload Resume' },
            { id: 'samples', label: 'Select Sample Resume' },
          ]}
        />
      </div>
      {tab === 'upload' ? (
        <>
          <Uploader />
          <Uploads />
        </>
      ) : (
        <>
          <p className="mb-4 text-sm text-ss-sub">Demo mode: 10 synthetic resumes (fictional people, no real personal data) covering common tech roles.</p>
          <SampleGrid onPicked={() => navigate('/app')} />
        </>
      )}
    </>
  )
}
