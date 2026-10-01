/**
 * The small component kit the whole app is built from.
 *
 * Kept in one file on purpose: it is ~15 primitives, and having them side by
 * side makes the visual language easy to see and keep consistent.
 */
import { createContext, useContext, useEffect, useId, useRef, useState } from 'react'

export const cx = (...parts) => parts.filter(Boolean).join(' ')

/* ------------------------------------------------------------------ Card */
export function Card({ className, children, as: Tag = 'div', ...rest }) {
  return (
    <Tag className={cx('card', className)} {...rest}>
      {children}
    </Tag>
  )
}

export function CardHeader({ title, subtitle, action, icon, className }) {
  return (
    <div className={cx('flex items-start justify-between gap-4 px-5 pt-5 sm:px-6 sm:pt-6', className)}>
      <div className="min-w-0">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-ink">
          {icon}
          <span className="truncate">{title}</span>
        </h3>
        {subtitle && <p className="mt-1 text-[13px] leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function CardBody({ className, children }) {
  return <div className={cx('px-5 pb-5 pt-4 sm:px-6 sm:pb-6', className)}>{children}</div>
}

/* ---------------------------------------------------------------- Button */
const BUTTON_VARIANTS = {
  primary:
    'bg-brand text-white hover:brightness-110 active:brightness-95 shadow-sm disabled:hover:brightness-100',
  secondary:
    'bg-surface text-ink border border-line hover:bg-raised active:bg-raised',
  ghost: 'text-muted hover:text-ink hover:bg-raised',
  danger: 'bg-critical text-white hover:brightness-110',
  soft: 'bg-brand/10 text-brand hover:bg-brand/[0.18] border border-brand/20',
}

const BUTTON_SIZES = {
  sm: 'h-8 px-3 text-[13px] gap-1.5 rounded-lg',
  md: 'h-10 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-12 px-6 text-[15px] gap-2 rounded-xl',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  children,
  disabled,
  ...rest
}) {
  return (
    <button
      className={cx(
        'inline-flex select-none items-center justify-center font-medium transition-all duration-150',
        'disabled:cursor-not-allowed disabled:opacity-50',
        BUTTON_SIZES[size],
        BUTTON_VARIANTS[variant],
        className
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  )
}

export function Spinner({ className }) {
  return (
    <svg className={cx('animate-spin', className || 'h-4 w-4')} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

/* ----------------------------------------------------------------- Badge */
const BADGE_TONES = {
  neutral: 'bg-raised text-muted border-line',
  brand: 'bg-brand/10 text-brand border-brand/25',
  good: 'bg-good/10 text-ink border-good/30',
  warn: 'bg-warn/15 text-ink border-warn/40',
  critical: 'bg-critical/10 text-ink border-critical/30',
}

export function Badge({ tone = 'neutral', icon, className, children }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium leading-none',
        BADGE_TONES[tone],
        className
      )}
    >
      {icon}
      {children}
    </span>
  )
}

/**
 * Status is never carried by colour alone: every pill has an icon and a word.
 * That is what makes it readable for colour-blind users and in print.
 */
const STATUS_META = {
  matched: { tone: 'good', glyph: '✓', label: 'Present' },
  partial: { tone: 'warn', glyph: '!', label: 'Partial' },
  missing: { tone: 'critical', glyph: '✗', label: 'Missing' },
}

export function StatusPill({ status, children, showLabel = false }) {
  const meta = STATUS_META[status] ?? STATUS_META.missing
  const dot =
    status === 'matched' ? 'text-good' : status === 'partial' ? 'text-warn' : 'text-critical'
  return (
    <Badge tone={meta.tone}>
      <span className={cx('font-bold', dot)} aria-hidden="true">
        {meta.glyph}
      </span>
      <span>{children ?? meta.label}</span>
      {showLabel && <span className="text-subtle">· {meta.label}</span>}
      <span className="sr-only"> ({meta.label})</span>
    </Badge>
  )
}

/* -------------------------------------------------------------- Progress */
export function Progress({ value, tone = 'brand', className, showValue = false, label }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  const fill =
    tone === 'good' ? 'bg-good' : tone === 'warn' ? 'bg-warn' : tone === 'critical' ? 'bg-critical' : 'bg-brand'
  return (
    <div className={cx('flex items-center gap-3', className)}>
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-raised"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        {/* Rounded data-end only; the origin stays square on the baseline. */}
        <div
          className={cx('h-full rounded-r-full transition-[width] duration-700 ease-out', fill)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showValue && (
        <span className="w-10 shrink-0 text-right text-[13px] font-semibold tabular-nums text-ink">
          {pct}%
        </span>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ Tabs */
const TabsContext = createContext(null)

export function Tabs({ value, onChange, children, className }) {
  return (
    <TabsContext.Provider value={{ value, onChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabList({ children, className }) {
  return (
    <div
      role="tablist"
      className={cx(
        'scroll-x -mx-1 flex gap-1 border-b border-line px-1 pb-px',
        className
      )}
    >
      {children}
    </div>
  )
}

export function Tab({ id, children, count }) {
  const { value, onChange } = useContext(TabsContext)
  const active = value === id
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={() => onChange(id)}
      className={cx(
        'relative whitespace-nowrap rounded-t-lg px-3.5 py-2.5 text-[13.5px] font-medium transition-colors',
        active ? 'text-ink' : 'text-muted hover:text-ink'
      )}
    >
      <span className="flex items-center gap-2">
        {children}
        {count !== undefined && (
          <span
            className={cx(
              'rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums',
              active ? 'bg-brand/15 text-brand' : 'bg-raised text-subtle'
            )}
          >
            {count}
          </span>
        )}
      </span>
      {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand" />}
    </button>
  )
}

export function TabPanel({ id, children }) {
  const { value } = useContext(TabsContext)
  if (value !== id) return null
  return <div className="animate-fade-up pt-5">{children}</div>
}

/* ------------------------------------------------------------- Skeletons */
export function Skeleton({ className }) {
  return <div className={cx('shimmer rounded-lg bg-raised', className)} />
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <Card className="card-pad">
      <Skeleton className="h-4 w-1/3" />
      <div className="mt-4 space-y-2.5">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className={cx('h-3', index === lines - 1 ? 'w-2/3' : 'w-full')} />
        ))}
      </div>
    </Card>
  )
}

/* ------------------------------------------------------------ Empty/Error */
export function EmptyState({ icon, title, description, action, className }) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-6 py-14 text-center', className)}>
      {icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-raised text-muted">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry, className }) {
  return (
    <div className={cx('rounded-2xl border border-critical/30 bg-critical/[0.06] p-5', className)}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-critical/15 text-[13px] font-bold text-critical">
          !
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink">
            {error?.message || 'Something went wrong.'}
          </p>
          {error?.hint && <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{error.hint}</p>}
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-3.5" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- Modal */
export function Modal({ open, onClose, title, subtitle, children, width = 'max-w-2xl' }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6">
      <div
        className="absolute inset-0 bg-black/45 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx(
          'relative z-10 max-h-[88vh] w-full overflow-hidden rounded-t-2xl border border-line bg-surface shadow-lift sm:rounded-2xl',
          width
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 truncate text-[13px] text-muted">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 rounded-lg p-1.5 text-muted transition-colors hover:bg-raised hover:text-ink"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="max-h-[calc(88vh-64px)] overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- Tooltip */
export function InfoTip({ text, className }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className={cx('relative inline-flex', className)}>
      <button
        type="button"
        aria-label="More information"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
        className="flex h-4 w-4 items-center justify-center rounded-full border border-line text-[10px] font-bold text-subtle transition-colors hover:border-brand hover:text-brand"
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-30 mb-2 w-64 -translate-x-1/2 rounded-xl border border-line bg-surface p-3 text-[12.5px] leading-relaxed text-muted shadow-lift"
        >
          {text}
        </span>
      )}
    </span>
  )
}

/* ----------------------------------------------------------------- Toast */
export function ToastStack({ toasts, onDismiss }) {
  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cx(
            'pointer-events-auto animate-slide-in rounded-xl border bg-surface p-3.5 shadow-lift',
            toast.type === 'error'
              ? 'border-critical/40'
              : toast.type === 'success'
                ? 'border-good/40'
                : 'border-line'
          )}
        >
          <div className="flex items-start gap-2.5">
            <span
              aria-hidden="true"
              className={cx(
                'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                toast.type === 'error'
                  ? 'bg-critical/15 text-critical'
                  : toast.type === 'success'
                    ? 'bg-good/15 text-good'
                    : 'bg-brand/15 text-brand'
              )}
            >
              {toast.type === 'error' ? '!' : toast.type === 'success' ? '✓' : 'i'}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-medium leading-snug text-ink">{toast.message}</p>
              {toast.hint && <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{toast.hint}</p>}
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              aria-label="Dismiss"
              className="-mr-1 -mt-1 rounded p-1 text-subtle transition-colors hover:text-ink"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
