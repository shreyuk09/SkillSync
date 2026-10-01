import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { paths, prefetch } from '../api'
import { Card, EmptyState, ErrorState, JobCard, LoadingSkeleton, MatchScore, NoResume, PageHeader, UploadedBadge } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useDebounced, useQuery } from '../useQuery'
import { JobDetailBody } from './JobDetail'

const MIN = [
  { id: 0, label: 'Any match' },
  { id: 45, label: '45%+' },
  { id: 60, label: '60%+' },
  { id: 75, label: 'Strong (75%+)' },
]

function useIsWide() {
  const q = '(min-width: 1024px)'
  const [wide, setWide] = useState(() => window.matchMedia(q).matches)
  useEffect(() => {
    const m = window.matchMedia(q)
    const on = () => setWide(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return wide
}

export default function JobMatches() {
  const { resumeId, isSaved, toggleSaved, openJd } = useSkillSync()
  const { data, error, loading, retry } = useQuery(resumeId ? paths.matches(resumeId) : null)
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const [role, setRole] = useState(params.get('role') || 'all')
  const [min, setMin] = useState(0)
  const [work, setWork] = useState('all')
  const [showFilters, setShowFilters] = useState(false)
  const [selected, setSelected] = useState(null)
  const q = useDebounced(query.trim().toLowerCase(), 180)
  const wide = useIsWide()
  const navigate = useNavigate()

  useEffect(() => setQuery(params.get('q') || ''), [params])

  const roles = useMemo(() => {
    const seen = new Map()
    data?.matches.forEach((j) => seen.set(j.role, j.role_title))
    return [...seen]
  }, [data])

  const list = useMemo(() => {
    if (!data) return []
    const filtered = data.matches.filter((j) => {
      if (role === 'uploaded') return j.uploaded
      if (role !== 'all' && j.role !== role) return false
      if (j.match < min) return false
      if (work !== 'all' && j.work_type !== work) return false
      if (!q) return true
      return [j.title, j.company, j.location, j.role_title, ...j.required_skills, ...j.preferred_skills].join(' ').toLowerCase().includes(q)
    })
    // Your own job descriptions stay pinned to the top.
    return [...filtered.filter((j) => j.uploaded), ...filtered.filter((j) => !j.uploaded)]
  }, [data, role, min, work, q])
  const uploadedCount = data?.matches.filter((j) => j.uploaded).length || 0

  const active = list.find((j) => j.id === selected) ? selected : list[0]?.id

  if (!resumeId) return <NoResume />
  if (error) return <ErrorState error={error} onRetry={retry} />

  const open = (job) => (wide ? setSelected(job.id) : navigate(`/app/jobs/${job.id}`))

  return (
    <>
      <PageHeader
        title="Job Matches"
        subtitle="Discover opportunities that match your skills and experience."
        actions={
          <button type="button" className="ss-btn" onClick={openJd}>
            <Icon name="upload" size={16} /> Upload Job Description
          </button>
        }
      />
      {data && uploadedCount === 0 && (
        <button type="button" onClick={openJd} className="mb-5 flex w-full items-center gap-4 rounded-[18px] border-2 border-dashed border-ss-p-ink/30 bg-ss-p-bg/40 p-4 text-left transition hover:bg-ss-p-bg/70 sm:p-5">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-ss-card text-ss-p-ink">
            <Icon name="upload" size={22} />
          </span>
          <span className="flex-1">
            <span className="block font-semibold text-ss-ink">Found a job you like? Upload its job description.</span>
            <span className="block text-sm text-ss-sub">Upload a PDF or paste the text and SkillSync compares it with your resume.</span>
          </span>
          <Icon name="chevron" size={20} className="hidden text-ss-p-ink sm:block" />
        </button>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-xl border border-ss-line bg-ss-card px-3.5 py-2.5 focus-within:border-ss-green/50 sm:max-w-[440px]">
          <Icon name="search" size={17} className="text-ss-mute" />
          <label htmlFor="jm-q" className="sr-only">
            Search job titles, companies or skills
          </label>
          <input
            id="jm-q"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })
            }}
            placeholder="Search job titles, companies or skills…"
            className="min-w-0 flex-1 bg-transparent text-sm text-ss-ink placeholder:text-ss-mute focus:outline-none"
          />
        </div>
        <button type="button" className="ss-btn2 ml-auto" onClick={() => setShowFilters((f) => !f)} aria-expanded={showFilters}>
          <Icon name="filter" size={16} /> Filters
        </button>
      </div>

      <div className="ss-scroll -mx-1 mb-4 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Role">
        {[['all', 'All roles'], ...(uploadedCount ? [['uploaded', `Your JDs (${uploadedCount})`]] : []), ...roles].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setRole(id)} aria-pressed={role === id} className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-medium transition ${role === id ? 'border-ss-green bg-ss-green text-ss-on-green' : 'border-ss-line bg-ss-card text-ss-sub hover:text-ss-ink'}`}>
            {label}
          </button>
        ))}
      </div>

      {showFilters && (
        <Card className="mb-4 flex flex-wrap gap-6 p-4">
          <fieldset>
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-ss-mute">Minimum match</legend>
            <div className="flex flex-wrap gap-2">
              {MIN.map((m) => (
                <button key={m.id} type="button" aria-pressed={min === m.id} onClick={() => setMin(m.id)} className={`rounded-lg px-3 py-1.5 text-sm ${min === m.id ? 'bg-ss-pill font-semibold text-ss-pill-ink' : 'bg-ss-soft text-ss-sub'}`}>
                  {m.label}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-ss-mute">Work type</legend>
            <div className="flex flex-wrap gap-2">
              {['all', 'Remote', 'Hybrid', 'Not specified'].map((w) => (
                <button key={w} type="button" aria-pressed={work === w} onClick={() => setWork(w)} className={`rounded-lg px-3 py-1.5 text-sm ${work === w ? 'bg-ss-pill font-semibold text-ss-pill-ink' : 'bg-ss-soft text-ss-sub'}`}>
                  {w === 'all' ? 'Any' : w}
                </button>
              ))}
            </div>
          </fieldset>
        </Card>
      )}

      {loading ? (
        <LoadingSkeleton message="Finding relevant opportunities…" rows={4} />
      ) : list.length === 0 ? (
        <EmptyState
          icon="search"
          title="No matches for these filters"
          message="We couldn't find a strong match yet. Try another role or update your skills."
          action={
            <button
              type="button"
              className="ss-btn2"
              onClick={() => {
                setRole('all')
                setMin(0)
                setWork('all')
                setQuery('')
                setParams({}, { replace: true })
              }}
            >
              Clear filters
            </button>
          }
        />
      ) : wide ? (
        <div className="grid grid-cols-[minmax(300px,380px)_minmax(0,1fr)] gap-5">
          <Card className="ss-scroll max-h-[calc(100vh-250px)] self-start overflow-y-auto">
            <p className="border-b border-ss-line px-4 py-2.5 text-xs text-ss-mute">
              {list.length} role{list.length === 1 ? '' : 's'} · {uploadedCount ? 'your JDs first, then ' : ''}sorted by match
            </p>
            <ul>
              {list.map((job) => (
                <li key={job.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(job.id)}
                    onMouseEnter={() => prefetch(paths.job(job.id, resumeId))}
                    aria-current={job.id === active}
                    className={`flex w-full items-start justify-between gap-3 border-b border-l-[3px] border-b-ss-line px-4 py-3 text-left transition last:border-b-0 ${job.id === active ? 'border-l-ss-green bg-ss-g-bg/50' : 'border-l-transparent hover:bg-ss-soft/60'}`}
                  >
                    <span className="min-w-0">
                      <span className="block font-semibold leading-snug text-ss-ink">{job.title}</span>
                      {job.uploaded && (
                        <span className="my-0.5 block">
                          <UploadedBadge />
                        </span>
                      )}
                      <span className="block truncate text-[13px] text-ss-sub">
                        {job.company} · {job.location}
                      </span>
                      <span className="block text-xs text-ss-mute">
                        {job.role_title} · {job.work_type}
                      </span>
                    </span>
                    <MatchScore value={job.match} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="self-start p-6">{active && <JobDetailBody key={active} jobId={active} panel />}</Card>
        </div>
      ) : (
        <ul className="space-y-3">
          {list.map((job) => (
            <li key={job.id}>
              <JobCard job={job} onSelect={() => open(job)} saved={isSaved(job.id)} onSave={toggleSaved} />
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
