import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { invalidate, uploadJob, uploadJobText } from './api'
import { DemoNotice, Tabs } from './components'
import { STATIC } from '../staticMode'
import { Icon } from './icons'

const STEPS = ['Reading the job description…', 'Extracting required skills…', 'Comparing your skills…', 'Preparing your match…']

/** Dialog for uploading your own job description (file or pasted text). */
export default function JdUpload({ open, onClose }) {
  const [mode, setMode] = useState('file')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState(null)
  const [drag, setDrag] = useState(false)
  const input = useRef(null)
  const dialog = useRef(null)
  const navigate = useNavigate()

  // Fresh state each time the dialog opens (not on every re-render while open,
  // which would wipe an error the moment it is shown).
  useEffect(() => {
    if (open) setError(null)
  }, [open])

  useEffect(() => {
    if (!open) return
    const esc = (e) => e.key === 'Escape' && !busy && onClose()
    document.addEventListener('keydown', esc)
    dialog.current?.focus()
    return () => document.removeEventListener('keydown', esc)
  }, [open, busy, onClose])

  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 700)
    return () => clearInterval(t)
  }, [busy])

  if (!open) return null

  const run = async (promise) => {
    setError(null)
    setBusy(true)
    setStep(0)
    try {
      const res = await promise
      invalidate() // matches, gaps and improvements all include the new job
      setText('')
      onClose()
      navigate(`/app/jobs/${res.id}`)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-labelledby="jd-title">
      <button type="button" className="absolute inset-0 bg-black/40" onClick={() => !busy && onClose()} aria-label="Close" tabIndex={-1} />
      <div ref={dialog} tabIndex={-1} className="ss-card relative w-full max-w-xl p-5 focus:outline-none sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="jd-title" className="text-xl font-semibold text-ss-ink">
              Upload a Job Description
            </h2>
            <p className="mt-1 text-sm text-ss-sub">See how well your resume matches a job you found yourself.</p>
          </div>
          <button type="button" onClick={onClose} disabled={busy} className="grid h-9 w-9 place-items-center rounded-full text-ss-sub hover:bg-ss-soft" aria-label="Close">
            <Icon name="x" size={19} />
          </button>
        </div>

        {STATIC ? (
          <div className="mt-4">
            <DemoNotice title="Uploading a job description works in the full app" />
          </div>
        ) : (
        <>
        <div className="mt-4">
          <Tabs
            label="How to add the job description"
            value={mode}
            onChange={setMode}
            tabs={[
              { id: 'file', label: 'Upload PDF / file' },
              { id: 'text', label: 'Paste text' },
            ]}
          />
        </div>

        <div className="mt-4">
          {busy ? (
            <div aria-live="polite" className="flex flex-col items-center rounded-2xl bg-ss-soft/50 px-6 py-12 text-center">
              <span className="h-10 w-10 animate-spin rounded-full border-[3px] border-ss-line border-t-ss-green" />
              <p className="mt-4 font-semibold text-ss-ink">{STEPS[step]}</p>
            </div>
          ) : mode === 'file' ? (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDrag(true)
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDrag(false)
                const f = e.dataTransfer.files?.[0]
                if (f) run(uploadJob(f))
              }}
              className={`flex flex-col items-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${drag ? 'border-ss-green bg-ss-g-bg/50' : 'border-ss-line bg-ss-soft/40'}`}
            >
              <span className="grid h-14 w-14 place-items-center rounded-full bg-ss-b-bg text-ss-b-ink">
                <Icon name="jobs" size={24} />
              </span>
              <p className="mt-4 font-semibold text-ss-ink">Drop the job description here</p>
              <p className="mt-1 text-sm text-ss-sub">PDF, DOCX, TXT or a screenshot · up to 8 MB</p>
              <button type="button" className="ss-btn mt-5" onClick={() => input.current?.click()}>
                <Icon name="upload" size={16} /> Choose file
              </button>
              <input
                ref={input}
                type="file"
                accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp"
                className="sr-only"
                aria-label="Job description file"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  e.target.value = ''
                  if (f) run(uploadJob(f))
                }}
              />
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (text.trim().length >= 60) run(uploadJobText(text))
              }}
            >
              <label htmlFor="jd-text" className="sr-only">
                Job description text
              </label>
              <textarea
                id="jd-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={9}
                maxLength={40000}
                placeholder="Paste the full job description: title, company, responsibilities, requirements…"
                className="ss-scroll w-full resize-y rounded-2xl border border-ss-line bg-ss-card p-4 text-sm text-ss-ink placeholder:text-ss-mute focus:border-ss-green/50 focus:outline-none"
              />
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="text-xs text-ss-mute">{text.trim().length < 60 ? 'At least a few sentences' : `${text.length.toLocaleString()} characters`}</span>
                <button type="submit" className="ss-btn" disabled={text.trim().length < 60}>
                  Analyze match
                </button>
              </div>
            </form>
          )}
        </div>

        {error && (
          <div role="alert" className="mt-4 flex items-start gap-3 rounded-xl bg-ss-r-bg p-4 text-sm text-ss-r-ink">
            <Icon name="alert" size={18} className="mt-0.5" />
            <div>
              <p className="font-semibold">{error.message}</p>
              {error.hint && <p className="mt-0.5">{error.hint}</p>}
            </div>
          </div>
        )}
        </>
        )}
        <p className="mt-4 flex items-start gap-2 text-xs text-ss-mute">
          <Icon name="shield" size={14} className="mt-0.5" />
          Stored only in this project's local data folder. You can remove it any time from the job's page.
        </p>
      </div>
    </div>
  )
}
