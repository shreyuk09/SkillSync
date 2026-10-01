import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { Button, EmptyState, ErrorState, SkeletonCard } from './ui'

/**
 * Wraps a page in the four states every analysis page needs:
 * not-ready, loading, error, and content. Doing it once here keeps each page
 * focused on what it actually displays.
 */
export function PageState({ needs = 'both', loading, error, onRetry, data, skeleton, children }) {
  const navigate = useNavigate()
  const { hasResume, hasJd, health } = useApp()

  const missing =
    needs === 'resume' ? !hasResume : needs === 'jd' ? !hasJd : !hasResume || !hasJd

  if (missing) {
    return (
      <EmptyState
        icon={
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d="M7 3h7l4 4v14H7zM14 3v4h4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
        title={
          needs === 'resume'
            ? 'No resume uploaded yet'
            : needs === 'jd'
              ? 'No job description yet'
              : 'Two documents needed'
        }
        description={
          needs === 'both'
            ? 'This page compares your resume against a job description, so it needs both before it can show anything.'
            : 'Upload the document to see the extracted information.'
        }
        action={<Button onClick={() => navigate('/upload')}>Go to documents</Button>}
      />
    )
  }

  if (error) {
    const noKey = error.code === 'llm_not_configured'
    const noCredits = error.code === 'llm_out_of_credits'
    return (
      <div className="space-y-4">
        <ErrorState error={error} onRetry={onRetry} />

        {noCredits && (
          <div className="rounded-2xl border border-line bg-raised/50 p-5 text-[13px] leading-relaxed text-muted">
            <p className="mb-2 font-semibold text-ink">What still works right now</p>
            <ul className="ml-4 list-disc space-y-1.5">
              <li>Uploading documents, and the whole extract → chunk → embed → index pipeline</li>
              <li>Semantic search over your indexed chunks, with live similarity scores</li>
              <li>Browsing every chunk the pipeline produced</li>
            </ul>
            <p className="mt-3 text-[12.5px] text-subtle">
              Only the pages that generate written text need credits. Retrieval runs entirely on
              your own machine and costs nothing.
            </p>
          </div>
        )}

        {noKey && (
          <div className="rounded-2xl border border-line bg-raised/50 p-5 text-[13px] leading-relaxed text-muted">
            <p className="mb-2 font-semibold text-ink">How to fix this</p>
            <ol className="ml-4 list-decimal space-y-1.5">
              <li>
                Open <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[12px]">backend/.env</code>
              </li>
              <li>
                Add <strong>either</strong>{' '}
                <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[12px]">GROQ_API_KEY=gsk_...</code>{' '}
                (free tier, console.groq.com) <strong>or</strong>{' '}
                <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[12px]">ANTHROPIC_API_KEY=sk-ant-...</code>
              </li>
              <li>Restart the backend, then reload this page.</li>
            </ol>
            <p className="mt-3 text-[12.5px] text-subtle">
              Document upload, chunking, embedding and vector search all work without a key —
              only the pages that generate text need one.
            </p>
          </div>
        )}
      </div>
    )
  }

  if (loading && !data) {
    return (
      skeleton ?? (
        <div className="space-y-4">
          <SkeletonCard lines={3} />
          <div className="grid gap-4 sm:grid-cols-2">
            <SkeletonCard lines={4} />
            <SkeletonCard lines={4} />
          </div>
        </div>
      )
    )
  }

  if (!data) return null

  return children
}

/** Consistent page title block. */
export function PageHeader({ title, subtitle, action, children }) {
  return (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[24px] font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-muted">{subtitle}</p>}
        {children}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}

/** "Analysing..." overlay for a slow LLM call on an already-populated page. */
export function RefreshingBar({ show, label = 'Re-running the analysis...' }) {
  if (!show) return null
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-brand/25 bg-brand/[0.06] px-4 py-2.5">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      <span className="text-[13px] font-medium text-ink">{label}</span>
    </div>
  )
}
