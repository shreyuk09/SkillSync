/**
 * Source citation UI -- the visible proof that an answer is grounded.
 *
 * The backend returns, for every claim, the chunk it came from: document,
 * section, page, similarity score and the exact text. Clicking a citation opens
 * that text verbatim. If an answer has no sources, that is shown too, because
 * "the model didn't cite anything" is information the user deserves.
 */
import { useState } from 'react'
import { Badge, Modal, cx } from './ui'

const DOC_LABEL = { resume: 'Resume', jd: 'Job Description' }

function docTone(docType) {
  return docType === 'resume'
    ? 'border-brand/30 bg-brand/[0.08] text-brand'
    : 'border-line bg-raised text-muted'
}

/** A single clickable citation chip. */
export function SourceChip({ source, onClick, index }) {
  return (
    <button
      onClick={() => onClick(source)}
      className={cx(
        'inline-flex max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 text-left text-[11.5px] font-medium transition-all hover:shadow-sm',
        docTone(source.doc_type)
      )}
      title={`${source.citation} — open the exact text`}
    >
      {index !== undefined && (
        <span className="shrink-0 font-mono font-bold opacity-70">S{index}</span>
      )}
      <span className="truncate">
        {DOC_LABEL[source.doc_type] || source.doc_type} → {source.section} → p.{source.page}
      </span>
    </button>
  )
}

/** The row of chips under an answer, plus the modal that shows the passage. */
export function SourceList({ sources, title = 'Sources', emptyNote, compact = false }) {
  const [active, setActive] = useState(null)

  if (!sources?.length) {
    return emptyNote ? (
      <p className="mt-2 text-[12px] italic text-subtle">{emptyNote}</p>
    ) : null
  }

  return (
    <div className={compact ? 'mt-2.5' : 'mt-4'}>
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
        {title} · {sources.length} passage{sources.length === 1 ? '' : 's'} retrieved
      </p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, position) => (
          <SourceChip
            key={source.chunk_id + position}
            source={source}
            index={position + 1}
            onClick={setActive}
          />
        ))}
      </div>

      <Modal
        open={Boolean(active)}
        onClose={() => setActive(null)}
        title={active?.citation || 'Source passage'}
        subtitle={
          active
            ? `${active.doc_name} · chunk ${active.chunk_id} · similarity ${(active.score * 100).toFixed(0)}%`
            : ''
        }
      >
        {active && (
          <>
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge tone={active.doc_type === 'resume' ? 'brand' : 'neutral'}>
                {DOC_LABEL[active.doc_type] || active.doc_type}
              </Badge>
              <Badge>{active.section}</Badge>
              <Badge>Page {active.page}</Badge>
              <Badge>Similarity {(active.score * 100).toFixed(0)}%</Badge>
            </div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
              Exact text retrieved from your document
            </p>
            <pre className="whitespace-pre-wrap rounded-xl border border-line bg-raised/60 p-4 font-sans text-[13.5px] leading-relaxed text-ink">
              {active.text}
            </pre>
            <p className="mt-4 text-[12px] leading-relaxed text-subtle">
              This is the unedited text the AI was given. It cannot see anything
              outside the passages retrieved for your question.
            </p>
          </>
        )}
      </Modal>
    </div>
  )
}

/** The retrieval trace: what the vector search returned, in rank order. */
export function RetrievalTrace({ retrieval }) {
  const [open, setOpen] = useState(false)
  if (!retrieval?.length) return null

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 text-[12px] font-medium text-subtle transition-colors hover:text-brand"
      >
        <svg
          className={cx('h-3 w-3 transition-transform', open && 'rotate-90')}
          viewBox="0 0 12 12"
          fill="currentColor"
        >
          <path d="M4 2l5 4-5 4z" />
        </svg>
        How this answer was retrieved
      </button>
      {open && (
        <ol className="mt-2 space-y-1 rounded-xl border border-line bg-raised/40 p-3">
          {retrieval.map((step) => (
            <li key={step.chunk_id} className="flex items-center gap-2 text-[12px]">
              <span className="w-7 shrink-0 font-mono font-bold text-subtle">{step.ref}</span>
              <span className="flex-1 truncate text-muted">{step.citation}</span>
              <span className="shrink-0 tabular-nums text-subtle">
                {(step.score * 100).toFixed(0)}%
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
