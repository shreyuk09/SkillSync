import { Link } from 'react-router-dom'
import { paths, prefetch } from '../api'
import { Card, CompanyMark, EmptyState, MatchScore, PageHeader } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

export default function SavedJobs() {
  const { saved, toggleSaved, resumeId } = useSkillSync()
  const { data } = useQuery(resumeId ? paths.matches(resumeId) : null)
  const score = Object.fromEntries((data?.matches || []).map((j) => [j.id, j.match]))
  return (
    <>
      <PageHeader title="Saved Jobs" subtitle="Roles you bookmarked. Saved in this browser only." />
      {saved.length === 0 ? (
        <EmptyState
          icon="bookmark"
          title="No saved jobs yet"
          message="Save roles from Job Matches to compare them later."
          action={
            <Link to="/app/jobs" className="ss-btn">
              Browse Job Matches
            </Link>
          }
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {saved.map((job) => (
            <li key={job.id}>
              <Card className="flex h-full gap-3 p-5">
                <CompanyMark company={job.company} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold leading-snug">{job.title}</p>
                    {score[job.id] != null && <MatchScore value={score[job.id]} />}
                  </div>
                  <p className="text-sm text-ss-sub">
                    {job.company} · {job.location}
                  </p>
                  <p className="text-xs text-ss-mute">Saved {new Date(job.saved_at).toLocaleDateString()}</p>
                  <div className="mt-4 flex gap-2">
                    <Link to={`/app/jobs/${job.id}`} onMouseEnter={() => resumeId && prefetch(paths.job(job.id, resumeId))} className="ss-btn h-9 px-3 text-[13px]">
                      View Details
                    </Link>
                    <button type="button" className="ss-btn2 h-9 px-3 text-[13px]" onClick={() => toggleSaved(job)}>
                      <Icon name="trash" size={15} /> Remove
                    </button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
