/**
 * Charts.
 *
 * Design rules applied here (they are not arbitrary):
 *
 * - The component scores are ONE measure across five categories, so they get
 *   ONE hue. Identity is carried by the row label, never by colour. Giving each
 *   component its own colour would imply a relationship between them that
 *   doesn't exist.
 * - Bars are thin, anchored to a baseline at 0, with a rounded data-end and a
 *   2px gap between adjacent fills.
 * - Values are direct-labelled at the end of each bar, so no legend is needed
 *   and no one has to read a value off an axis.
 * - Every mark has a hover tooltip that explains how that number was produced.
 * - Text always wears text tokens; the coloured mark beside it carries meaning.
 * - A table view of the same numbers is always one click away.
 */
import { useState } from 'react'
import { cx } from './ui'

/* ------------------------------------------------------------- Score ring */
export function ScoreRing({ value, size = 168, label = 'Overall match', band }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  const stroke = size >= 140 ? 12 : 9
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - pct / 100)

  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`${label}: ${pct} percent`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--raised))"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--brand))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 900ms cubic-bezier(0.16, 1, 0.3, 1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-bold leading-none tracking-tight text-ink"
          style={{ fontSize: size * 0.28 }}
        >
          {pct}
          <span className="text-[0.5em] font-semibold text-muted">%</span>
        </span>
        {band && (
          <span className="mt-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
            {band}
          </span>
        )}
      </div>
    </div>
  )
}

/* --------------------------------------------------- Component bar chart */
export function ComponentBars({ components, onSelect }) {
  const [hovered, setHovered] = useState(null)
  const [showTable, setShowTable] = useState(false)

  if (!components?.length) return null

  return (
    <div>
      <div className="flex items-center justify-between pb-1">
        <p className="text-[12px] font-medium uppercase tracking-wider text-subtle">
          Score by component
        </p>
        <button
          onClick={() => setShowTable((v) => !v)}
          className="text-[12px] font-medium text-muted underline-offset-2 transition-colors hover:text-brand hover:underline"
        >
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </div>

      {showTable ? (
        <div className="scroll-x mt-3">
          <table className="w-full min-w-[420px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[12px] uppercase tracking-wide text-subtle">
                <th className="py-2 pr-4 font-medium">Component</th>
                <th className="py-2 pr-4 text-right font-medium">Score</th>
                <th className="py-2 pr-4 text-right font-medium">Weight</th>
                <th className="py-2 text-right font-medium">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {components.map((component) => (
                <tr key={component.key} className="border-b border-line/60 last:border-0">
                  <td className="py-2.5 pr-4 text-ink">{component.label}</td>
                  <td className="py-2.5 pr-4 text-right font-semibold tabular-nums text-ink">
                    {component.score}%
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-muted">
                    {component.weight_percent}%
                  </td>
                  <td className="py-2.5 text-right tabular-nums text-muted">
                    {component.contribution}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        // 2px gap between adjacent bars: space-y-[9px] on 8px-tall rows.
        <ul className="mt-3 space-y-3.5">
          {components.map((component) => {
            const active = hovered === component.key
            return (
              <li
                key={component.key}
                onMouseEnter={() => setHovered(component.key)}
                onMouseLeave={() => setHovered(null)}
                className="group relative"
              >
                <button
                  type="button"
                  onClick={() => onSelect?.(component)}
                  className="block w-full text-left"
                >
                  <div className="flex items-baseline justify-between gap-3 pb-1.5">
                    <span className="truncate text-[13.5px] font-medium text-ink">
                      {component.label}
                      <span className="ml-2 text-[12px] font-normal text-subtle">
                        {component.weight_percent}% of total
                      </span>
                    </span>
                    {/* Direct label -- no axis to read against. */}
                    <span className="shrink-0 text-[13.5px] font-semibold tabular-nums text-ink">
                      {component.score}%
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-[4px] bg-raised">
                    <div
                      className="h-full rounded-r-[4px] bg-brand transition-[width,filter] duration-700 ease-out group-hover:brightness-110"
                      style={{ width: `${component.score}%` }}
                    />
                  </div>
                </button>

                {active && component.calculation && (
                  <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-full max-w-md rounded-xl border border-line bg-surface p-3 text-[12.5px] leading-relaxed text-muted shadow-lift">
                    {component.calculation}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- Stat tile */
export function StatTile({ label, value, suffix, caption, tone = 'neutral', icon }) {
  const accent =
    tone === 'good' ? 'text-good' : tone === 'warn' ? 'text-warn' : tone === 'critical' ? 'text-critical' : 'text-brand'
  return (
    <div className="card card-pad">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-medium uppercase tracking-wider text-subtle">{label}</p>
        {icon && <span className={cx('shrink-0', accent)}>{icon}</span>}
      </div>
      <p className="mt-2.5 text-[30px] font-bold leading-none tracking-tight text-ink">
        {value}
        {suffix && <span className="ml-0.5 text-[18px] font-semibold text-muted">{suffix}</span>}
      </p>
      {caption && <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{caption}</p>}
    </div>
  )
}

/* ------------------------------------------------------- Relevance bar row */
export function RelevanceRow({ name, value, detail, rank }) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-baseline justify-between gap-3 pb-1.5">
        <span className="flex min-w-0 items-baseline gap-2">
          {rank !== undefined && (
            <span className="shrink-0 text-[12px] font-semibold tabular-nums text-subtle">{rank}.</span>
          )}
          <span className="truncate text-[13.5px] font-medium text-ink">{name}</span>
        </span>
        <span className="shrink-0 text-[13.5px] font-semibold tabular-nums text-ink">{value}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-[4px] bg-raised">
        <div
          className="h-full rounded-r-[4px] bg-brand transition-[width] duration-700 ease-out"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
      {hovered && detail && (
        <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-full rounded-xl border border-line bg-surface p-3 text-[12.5px] leading-relaxed text-muted shadow-lift">
          {detail}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ Keyword grid */
export function KeywordGrid({ keywords }) {
  const [hovered, setHovered] = useState(null)
  if (!keywords?.length) return null

  return (
    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
      {keywords.map((row) => (
        <div
          key={row.keyword}
          onMouseEnter={() => setHovered(row.keyword)}
          onMouseLeave={() => setHovered(null)}
          className={cx(
            'relative flex items-center justify-between gap-2 rounded-lg border px-3 py-2 transition-colors',
            row.present
              ? 'border-good/25 bg-good/[0.06]'
              : 'border-critical/25 bg-critical/[0.05]'
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden="true"
              className={cx(
                'flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
                row.present ? 'bg-good/20 text-good' : 'bg-critical/20 text-critical'
              )}
            >
              {row.present ? '✓' : '✗'}
            </span>
            <span className="truncate text-[13px] font-medium text-ink">{row.keyword}</span>
          </span>
          <span className="flex shrink-0 items-center gap-2">
            {row.present && row.count > 1 && (
              <span className="text-[11px] font-semibold tabular-nums text-subtle">×{row.count}</span>
            )}
            <span
              className={cx(
                'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                row.importance === 'high'
                  ? 'bg-raised text-ink'
                  : 'bg-raised/60 text-subtle'
              )}
            >
              {row.importance}
            </span>
          </span>
          <span className="sr-only">{row.present ? 'present in resume' : 'missing from resume'}</span>

          {hovered === row.keyword && (
            <div className="pointer-events-none absolute bottom-full left-0 z-20 mb-1.5 w-64 rounded-xl border border-line bg-surface p-3 text-[12.5px] leading-relaxed text-muted shadow-lift">
              {row.present ? (
                <>
                  Found {row.count} time{row.count === 1 ? '' : 's'}
                  {row.sections?.length ? ` in: ${row.sections.join(', ')}` : ''}.
                </>
              ) : (
                <>Not found anywhere in your resume. Importance to this posting: {row.importance}.</>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
