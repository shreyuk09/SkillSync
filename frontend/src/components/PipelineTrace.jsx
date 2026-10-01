/**
 * Shows what the RAG pipeline actually did to a document.
 *
 * This exists because the whole point of the project is that RAG is a real
 * process, not a black box. After an upload the user sees each stage, in order,
 * with the real numbers it produced.
 */
import { cx } from './ui'

const STAGE_ICONS = {
  Extraction: 'M7 3h7l4 4v14H7z M14 3v4h4',
  Cleaning: 'M4 12h16 M8 6h8 M8 18h8',
  Sectioning: 'M4 5h16 M4 10h10 M4 15h16 M4 20h7',
  Chunking: 'M4 5h7v6H4z M13 5h7v6h-7z M4 13h7v6H4z M13 13h7v6h-7z',
  Embedding: 'M12 3v18 M3 12h18 M6 6l12 12 M18 6L6 18',
  Indexing: 'M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7',
}

export function PipelineTrace({ stages, dense = false }) {
  if (!stages?.length) return null

  return (
    <ol className={cx('relative', dense ? 'space-y-2.5' : 'space-y-3.5')}>
      {/* The connecting rail */}
      <span
        aria-hidden="true"
        className="absolute left-[15px] top-3 bottom-3 w-px bg-line"
      />
      {stages.map((stage, index) => (
        <li key={stage.stage} className="relative flex gap-3">
          <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-brand">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
              <path d={STAGE_ICONS[stage.stage] || 'M12 3v18'} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="min-w-0 flex-1 pt-1">
            <p className="text-[13px] font-semibold text-ink">
              <span className="mr-1.5 font-mono text-[11px] text-subtle">{index + 1}</span>
              {stage.stage}
            </p>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">{stage.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
