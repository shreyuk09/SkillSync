import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { invalidate, paths } from '../api'
import { Card, CardHeader, PageHeader } from '../components'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

function Row({ title, detail, children }) {
  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-medium">{title}</p>
        {detail && <p className="text-sm text-ss-sub">{detail}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

export default function Settings() {
  const { theme, toggleTheme } = useApp()
  const { saved, clearSaved, setResumeId, resumeId, setChat } = useSkillSync()
  const { data: resumes } = useQuery(paths.resumes())
  const { data: jobs } = useQuery(paths.jobs())
  const [rag, setRag] = useState(null)
  useEffect(() => {
    fetch('/api/rag/status')
      .then((r) => r.json())
      .then(setRag)
      .catch(() => setRag(null))
  }, [])

  return (
    <>
      <PageHeader title="Settings" subtitle="Appearance, your data in this browser, and where SkillSync's data comes from." />
      <div className="space-y-6">
        <Card>
          <CardHeader title="Appearance" />
          <Row title="Dark mode" detail="Applies to the whole site.">
            <button type="button" role="switch" aria-checked={theme === 'dark'} onClick={toggleTheme} className={`relative h-7 w-12 rounded-full transition ${theme === 'dark' ? 'bg-ss-green' : 'bg-ss-line'}`}>
              <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${theme === 'dark' ? 'left-6' : 'left-1'}`} />
              <span className="sr-only">Dark mode</span>
            </button>
          </Row>
        </Card>

        <Card>
          <CardHeader title="Your data in this browser" />
          <div className="divide-y divide-ss-line">
            <Row title="Selected resume" detail={resumeId || 'None'}>
              <button type="button" className="ss-btn2 h-9 text-[13px]" disabled={!resumeId} onClick={() => setResumeId(null)}>
                Clear selection
              </button>
            </Row>
            <Row title="Saved jobs" detail={`${saved.length} saved`}>
              <button type="button" className="ss-btn2 h-9 text-[13px]" disabled={!saved.length} onClick={clearSaved}>
                <Icon name="trash" size={15} /> Clear saved jobs
              </button>
            </Row>
            <Row title="Chat history" detail="Kept for this tab only.">
              <button type="button" className="ss-btn2 h-9 text-[13px]" disabled={!resumeId} onClick={() => setChat(resumeId, [])}>
                Clear chat
              </button>
            </Row>
            <Row title="Refresh data" detail="Reload results after editing the JSON files in /data.">
              <button
                type="button"
                className="ss-btn2 h-9 text-[13px]"
                onClick={() => {
                  invalidate()
                  window.location.reload()
                }}
              >
                <Icon name="refresh" size={15} /> Refresh
              </button>
            </Row>
          </div>
        </Card>

        <Card>
          <CardHeader title="About the data" icon={<Icon name="database" size={18} className="text-ss-b-ink" />} />
          <div className="space-y-3 p-5 text-sm text-ss-sub">
            <p>
              <strong className="text-ss-ink">{resumes?.samples.length ?? '…'} sample resumes</strong> are synthetic: invented people, employers and contact details (CC0). They contain no real personal data.
            </p>
            <p>
              <strong className="text-ss-ink">{jobs?.jobs.length ?? '…'} job postings across {jobs?.roles.length ?? '…'} roles</strong> are short summaries, written in our own words, of public listings on company job boards. Each keeps its source link and retrieval date. They are not the original text, and a role may have closed since it was captured.
            </p>
            <p>
              <strong className="text-ss-ink">Matching, scores, gaps and improvements</strong> are calculated from these files, so every number can be explained. The <strong className="text-ss-ink">AI Career Assistant</strong> retrieves the most relevant pieces from a vector index of this data and answers only from them, showing its sources.
            </p>
            <p className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${rag?.ready ? 'bg-ss-green' : 'bg-ss-a-ink'}`} />
              Knowledge index: {rag == null ? 'checking…' : rag.ready ? 'ready' : 'warming up'}
            </p>
            <p>
              <Link to="/how-it-works" className="font-semibold text-ss-green hover:underline">
                How SkillSync works →
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </>
  )
}
