import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { chat, paths } from '../api'
import { ChatInput, ChatMessage, DemoNotice, NoResume, PageHeader } from '../components'
import { STATIC } from '../../staticMode'
import { Icon } from '../icons'
import { useSkillSync } from '../store'
import { useQuery } from '../useQuery'

const SUGGESTED = [
  'What jobs match my resume?',
  'What skills am I missing?',
  'How can I improve my resume?',
  'Why is this job a good match?',
  'What should I learn next?',
  'Which projects should I add?',
]

export default function Assistant() {
  const { resumeId, chats, setChat } = useSkillSync()
  const [params, setParams] = useSearchParams()
  const jobId = params.get('job')
  const { data: job } = useQuery(jobId && resumeId ? paths.job(jobId, resumeId) : null)
  const { data: matches } = useQuery(resumeId ? paths.matches(resumeId) : null)
  const [pending, setPending] = useState(false)
  const endRef = useRef(null)
  const asked = useRef(false)
  const uploaded = (matches?.matches || []).filter((j) => j.uploaded)
  const others = (matches?.matches || []).filter((j) => !j.uploaded)
  const key = resumeId || 'none'
  const messages = chats[key] || []

  const send = useCallback(
    async (question) => {
      if (!resumeId || pending) return
      // With no job chosen, the server works out which job is meant (a job or
      // company named in the question, or "this job" -> your latest uploaded JD).
      const focus = jobId
      const history = (chats[key] || []).slice(-4).map((m) => ({ role: m.role, content: m.content || '' }))
      setChat(key, (list) => [...list, { role: 'user', content: question, id: Date.now() }])
      setPending(true)
      try {
        const result = await chat({ question, resume_id: resumeId, job_id: focus || null, history })
        setChat(key, (list) => [...list, { role: 'assistant', content: result.answer || '', result, id: Date.now() + 1 }])
      } catch (e) {
        setChat(key, (list) => [...list, { role: 'assistant', content: '', error: `${e.message} ${e.hint || ''}`.trim(), id: Date.now() + 1 }])
      } finally {
        setPending(false)
      }
    },
    [resumeId, pending, jobId, chats, key, setChat]
  )

  // A question handed over from another page (?q=...) is asked once.
  useEffect(() => {
    const q = params.get('q')
    if (q && resumeId && !asked.current) {
      asked.current = true
      const next = new URLSearchParams(params)
      next.delete('q')
      setParams(next, { replace: true })
      send(q)
    }
  }, [params, resumeId, send, setParams])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, pending])

  if (!resumeId) return <NoResume />
  if (STATIC)
    return (
      <>
        <PageHeader title="AI Career Assistant" subtitle="Ask questions about your resume, skills, and matched opportunities." />
        <div className="ss-card p-6">
          <DemoNotice title="The AI Career Assistant runs in the full app" />
          <p className="mt-6 text-sm font-semibold text-ss-sub">Questions it answers, with sources from your resume and job descriptions</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {SUGGESTED.map((q) => (
              <li key={q} className="rounded-xl border border-ss-line bg-ss-soft/50 px-4 py-3 text-sm font-medium text-ss-ink">
                {q}
              </li>
            ))}
          </ul>
        </div>
      </>
    )

  return (
    <div className="flex min-h-[calc(100vh-150px)] flex-col">
      <PageHeader
        title="AI Career Assistant"
        subtitle="Ask questions about your resume, skills, and matched opportunities."
        actions={
          messages.length > 0 && (
            <button type="button" className="ss-btn2 h-9 text-[13px]" onClick={() => setChat(key, [])}>
              <Icon name="refresh" size={15} /> New chat
            </button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label htmlFor="ss-focus" className="text-sm font-medium text-ss-sub">
          Answer about
        </label>
        <select
          id="ss-focus"
          value={jobId || ''}
          onChange={(e) => {
            const next = new URLSearchParams(params)
            if (e.target.value) next.set('job', e.target.value)
            else next.delete('job')
            setParams(next, { replace: true })
          }}
          className="h-9 max-w-full rounded-xl border border-ss-line bg-ss-card px-3 text-sm font-medium text-ss-ink focus:border-ss-green/50 focus:outline-none"
        >
          <option value="">My resume (detect the job from my question)</option>
          {uploaded.length > 0 && (
            <optgroup label="Your job descriptions">
              {uploaded.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} · {j.company}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label="Top matches">
            {others.slice(0, 8).map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} · {j.company} ({j.match}%)
              </option>
            ))}
          </optgroup>
        </select>
        {jobId && job && <span className="text-xs text-ss-mute">Answers use your full resume, this job description and your match facts.</span>}
      </div>

      <div className="flex-1 space-y-5" aria-live="polite">
        {messages.length === 0 && (
          <div className="ss-card p-6">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-ss-p-bg text-ss-p-ink">
                <Icon name="ai" size={22} />
              </span>
              <div>
                <p className="font-semibold">Hi! I answer from your resume and the SkillSync job data.</p>
                <p className="text-sm text-ss-sub">Every answer shows the sources it used. If something isn't in the data, I'll say so.</p>
              </div>
            </div>
            <p className="mt-6 text-sm font-semibold text-ss-sub">Try asking</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {SUGGESTED.map((q) => (
                <button key={q} type="button" onClick={() => send(q)} className="rounded-xl border border-ss-line bg-ss-soft/50 px-4 py-3 text-left text-sm font-medium text-ss-ink transition hover:border-ss-p-ink/40 hover:bg-ss-p-bg/50">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {pending && (
          <div className="flex gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ss-p-bg text-ss-p-ink">
              <Icon name="ai" size={18} />
            </span>
            <div className="rounded-2xl rounded-tl-md border border-ss-line bg-ss-card px-4 py-3 text-sm text-ss-sub">
              <span className="inline-flex items-center gap-2">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ss-p-ink [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ss-p-ink [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ss-p-ink" />
                </span>
                Searching your resume and job data…
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {messages.length > 0 && !pending && (
        <div className="ss-scroll mt-5 flex gap-2 overflow-x-auto pb-1">
          {SUGGESTED.map((q) => (
            <button key={q} type="button" onClick={() => send(q)} className="shrink-0 rounded-full border border-ss-line bg-ss-card px-3 py-1.5 text-xs font-medium text-ss-sub hover:text-ss-ink">
              {q}
            </button>
          ))}
        </div>
      )}
      <div className="sticky bottom-[76px] mt-3 bg-ss-page pb-2 pt-1 md:bottom-0 md:pb-4">
        <ChatInput onSend={send} disabled={pending} />
        <p className="mt-2 text-center text-[11px] text-ss-mute">AI Match answers use retrieved sources only. Job postings are summaries of public listings and may have closed.</p>
      </div>
    </div>
  )
}
