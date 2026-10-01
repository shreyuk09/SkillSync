import { useCallback, useRef, useState } from 'react'
import { Button, Spinner, cx } from './ui'

const ACCEPT = '.pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.heic,.tiff'
const MAX_MB = 8
const FORMAT_HINT = 'PDF, DOCX, TXT, MD or an image'

/**
 * Drag-and-drop file input with client-side pre-validation.
 *
 * The server validates again (and is the real gate -- client checks are only a
 * courtesy so the user gets an instant answer instead of a round trip).
 */
export function Dropzone({ onFile, loading, label, hint, compact = false }) {
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState('')
  const inputRef = useRef(null)

  const validate = useCallback((file) => {
    const extension = '.' + (file.name.split('.').pop() || '').toLowerCase()
    if (!ACCEPT.split(',').includes(extension)) {
      return `"${file.name}" isn't a supported format. Use ${FORMAT_HINT}.`
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `"${file.name}" is ${(file.size / 1024 / 1024).toFixed(1)} MB, over the ${MAX_MB} MB limit.`
    }
    if (file.size === 0) return `"${file.name}" is empty.`
    return ''
  }, [])

  const handle = useCallback(
    (file) => {
      if (!file) return
      const problem = validate(file)
      setLocalError(problem)
      if (!problem) onFile(file)
    },
    [onFile, validate]
  )

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          handle(event.dataTransfer.files?.[0])
        }}
        onClick={() => !loading && inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            inputRef.current?.click()
          }
        }}
        role="button"
        tabIndex={0}
        aria-label={label}
        className={cx(
          'group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition-all duration-200',
          compact ? 'px-4 py-6' : 'px-6 py-10',
          dragging
            ? 'border-brand bg-brand/[0.07]'
            : 'border-line bg-surface hover:border-brand/50 hover:bg-raised/50',
          loading && 'pointer-events-none opacity-60'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => {
            handle(event.target.files?.[0])
            event.target.value = ''
          }}
        />

        <div
          className={cx(
            'mb-3 flex items-center justify-center rounded-2xl transition-colors',
            compact ? 'h-9 w-9' : 'h-11 w-11',
            dragging ? 'bg-brand/15 text-brand' : 'bg-raised text-muted group-hover:text-brand'
          )}
        >
          {loading ? (
            <Spinner className="h-5 w-5" />
          ) : (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 16V4m0 0L8 8m4-4l4 4" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
            </svg>
          )}
        </div>

        <p className={cx('font-semibold text-ink', compact ? 'text-[13.5px]' : 'text-sm')}>
          {loading ? 'Processing...' : label}
        </p>
        <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
          {hint || 'Drag a file here, or click to browse'}
        </p>
        {!compact && (
          <p className="mt-2 text-[11.5px] text-subtle">
            {FORMAT_HINT} · up to {MAX_MB} MB
          </p>
        )}
      </div>

      {localError && (
        <p className="mt-2 flex items-start gap-1.5 text-[12.5px] leading-relaxed text-critical">
          <span aria-hidden="true" className="font-bold">!</span>
          {localError}
        </p>
      )}
    </div>
  )
}

/** Paste-text alternative, used for job descriptions copied off a careers page. */
export function PasteBox({ onSubmit, loading, placeholder, minLength = 40 }) {
  const [text, setText] = useState('')
  const tooShort = text.trim().length > 0 && text.trim().length < minLength

  return (
    <div>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={placeholder}
        rows={9}
        className="w-full resize-y rounded-xl border border-line bg-surface px-3.5 py-3 text-[13.5px] leading-relaxed text-ink placeholder:text-subtle focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/25"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className={cx('text-[12px]', tooShort ? 'text-critical' : 'text-subtle')}>
          {tooShort
            ? `Needs at least ${minLength} characters (${text.trim().length} so far)`
            : `${text.trim().length.toLocaleString()} characters`}
        </span>
        <Button
          size="sm"
          loading={loading}
          disabled={text.trim().length < minLength}
          onClick={() => onSubmit(text)}
        >
          Analyse this text
        </Button>
      </div>
    </div>
  )
}
