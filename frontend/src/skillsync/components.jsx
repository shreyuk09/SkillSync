import { memo, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Icon, ROLE_ICON } from './icons'
import { REPO_URL, STATIC_NOTICE } from '../staticMode'

/* ---------------------------------------------------------------------------
   Meaning colours: green = matched/strong, amber = improve, red = missing,
   blue = info, purple = AI. Status is never colour-only: every badge also
   carries an icon or a word.
--------------------------------------------------------------------------- */
export const TONE = {
  green: 'bg-ss-g-bg text-ss-g-ink',
  amber: 'bg-ss-a-bg text-ss-a-ink',
  red: 'bg-ss-r-bg text-ss-r-ink',
  blue: 'bg-ss-b-bg text-ss-b-ink',
  purple: 'bg-ss-p-bg text-ss-p-ink',
  neutral: 'bg-ss-soft text-ss-sub',
}

export const matchTone = (score) => (score >= 75 ? 'green' : score >= 60 ? 'blue' : score >= 45 ? 'amber' : 'neutral')
export const statusTone = { strong: 'green', improve: 'amber', missing: 'red' }
export const priorityTone = { High: 'red', Medium: 'amber', Low: 'blue' }

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] text-ss-ink sm:text-[30px]">{title}</h1>
        {subtitle && <p className="mt-1.5 text-[15px] text-ss-sub">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Card({ className = '', children, as: As = 'section', ...rest }) {
  return (
    <As className={`ss-card ${className}`} {...rest}>
      {children}
    </As>
  )
}

export function CardHeader({ title, action, icon, className = '' }) {
  return (
    <div className={`flex items-center justify-between gap-3 border-b border-ss-line px-5 py-4 ${className}`}>
      <h2 className="flex items-center gap-2 text-[17px] font-semibold text-ss-ink">
        {icon}
        {title}
      </h2>
      {action}
    </div>
  )
}

/* ---- Dashboard stat card -------------------------------------------------- */
const CARD_TONE = {
  green: 'bg-ss-g-bg/80 text-ss-g-ink',
  purple: 'bg-ss-p-bg/80 text-ss-p-ink',
  blue: 'bg-ss-b-bg/80 text-ss-b-ink',
  red: 'bg-ss-r-bg/80 text-ss-r-ink',
}
export function DashboardCard({ label, value, suffix, icon, tone = 'green', to, hint }) {
  const body = (
    <div className={`group h-full rounded-[18px] border border-ss-line/60 p-4 transition hover:-translate-y-0.5 hover:shadow-md sm:p-5 ${CARD_TONE[tone]}`}>
      <div className="flex items-center gap-2 text-[13px] font-semibold sm:text-sm">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-ss-card/80">
          <Icon name={icon} size={17} />
        </span>
        {label}
      </div>
      <div className="mt-3 flex items-baseline gap-1 text-ss-ink">
        <span className="text-[30px] font-bold leading-none tracking-tight sm:text-[34px]">{value}</span>
        {suffix && <span className="text-[15px] font-medium text-ss-sub">{suffix}</span>}
      </div>
      {hint && <p className="mt-2 text-xs text-ss-sub">{hint}</p>}
    </div>
  )
  return to ? (
    <Link to={to} className="block h-full rounded-[18px]">
      {body}
    </Link>
  ) : (
    body
  )
}

/* ---- Badges ---------------------------------------------------------------- */
export const SkillBadge = memo(function SkillBadge({ children, tone = 'blue', icon, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[12.5px] font-medium ${TONE[tone]} ${className}`}>
      {icon && <Icon name={icon} size={13} strokeWidth={2.2} />}
      {children}
    </span>
  )
})

export function MatchScore({ value, size = 'md' }) {
  const tone = matchTone(value)
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full font-semibold ${TONE[tone]} ${size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'}`}
      title="How closely your resume covers this role's skills, level and focus"
    >
      {value}% Match
    </span>
  )
}

export function PriorityBadge({ priority }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${TONE[priorityTone[priority]]}`}>
      <Icon name={priority === 'High' ? 'alert' : priority === 'Medium' ? 'info' : 'check'} size={13} strokeWidth={2.2} />
      {priority === 'Medium' ? 'Medium' : `${priority} Priority`}
    </span>
  )
}

const STATUS_LABEL = { strong: 'Strong', improve: 'Improve', missing: 'Missing' }
const STATUS_ICON = { strong: 'check', improve: 'tri', missing: 'x' }
export function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE[statusTone[status]]}`}>
      <Icon name={STATUS_ICON[status]} size={12} strokeWidth={2.6} />
      {STATUS_LABEL[status]}
    </span>
  )
}

/* ---- Score ring ------------------------------------------------------------- */
export function ScoreRing({ value, size = 64, stroke = 6, label, big = false }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const color = value >= 75 ? 'rgb(var(--ss-green))' : value >= 55 ? 'rgb(var(--ss-a-ink))' : 'rgb(var(--ss-r-ink))'
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={`${label || 'Score'}: ${value} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--ss-soft))" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / 100)}
          style={{ transition: 'stroke-dashoffset .8s cubic-bezier(.16,1,.3,1)' }}
        />
      </svg>
      <span className="absolute font-bold text-ss-ink" style={{ fontSize: big ? size * 0.3 : size * 0.26 }}>
        {value}
        {big ? <span className="text-[0.45em] font-medium text-ss-sub">/100</span> : <span className="text-[0.55em]">%</span>}
      </span>
    </div>
  )
}

export function Bar({ value, tone = 'green', className = '' }) {
  const fill = { green: 'bg-ss-green', amber: 'bg-ss-a-ink', red: 'bg-ss-r-ink', blue: 'bg-ss-b-ink', neutral: 'bg-ss-mute' }[tone]
  return (
    <div className={`h-2 overflow-hidden rounded-full bg-ss-soft ${className}`}>
      <div className={`h-full rounded-full ${fill}`} style={{ width: `${Math.max(3, Math.min(100, value))}%`, transition: 'width .6s cubic-bezier(.16,1,.3,1)' }} />
    </div>
  )
}

/* ---- Avatars / logos -------------------------------------------------------- */
const initials = (name = '') =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() || 'SS'

export function Avatar({ name, size = 40 }) {
  return (
    <span
      className="inline-grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-ss-green2 to-ss-green font-semibold text-ss-on-green"
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}

/** Company tile: a monogram, not the company's logo (no trademarked marks). */
const LOGO_TONES = ['bg-ss-b-bg text-ss-b-ink', 'bg-ss-p-bg text-ss-p-ink', 'bg-ss-g-bg text-ss-g-ink', 'bg-ss-a-bg text-ss-a-ink', 'bg-ss-r-bg text-ss-r-ink']
export function CompanyMark({ company = '', size = 44 }) {
  const tone = LOGO_TONES[[...company].reduce((a, ch) => a + ch.charCodeAt(0), 0) % LOGO_TONES.length]
  return (
    <span className={`inline-grid shrink-0 place-items-center rounded-xl border border-ss-line font-bold ${tone}`} style={{ width: size, height: size, fontSize: size * 0.42 }} aria-hidden="true">
      {company[0] || '?'}
    </span>
  )
}

export function RoleIcon({ role, size = 40, tone = 'green' }) {
  return (
    <span className={`inline-grid shrink-0 place-items-center rounded-xl ${TONE[tone]}`} style={{ width: size, height: size }} aria-hidden="true">
      <Icon name={ROLE_ICON[role] || 'resume'} size={size * 0.5} />
    </span>
  )
}

/* ---- Job card -------------------------------------------------------------- */
export const JobCard = memo(function JobCard({ job, active, onSelect, compact, saved, onSave, onPrefetch }) {
  return (
    <article
      className={`group relative rounded-2xl border p-4 transition ${active ? 'border-ss-green/50 bg-ss-g-bg/40 ring-1 ring-ss-green/30' : 'border-ss-line bg-ss-card hover:border-ss-green/30 hover:shadow-md'}`}
      onMouseEnter={onPrefetch}
      onFocus={onPrefetch}
    >
      <div className="flex items-start gap-3">
        <CompanyMark company={job.company} size={compact ? 38 : 44} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold leading-snug text-ss-ink">
              <button type="button" onClick={onSelect} className="text-left after:absolute after:inset-0 after:content-[''] focus-visible:outline-none">
                {job.title}
              </button>
            </h3>
            <MatchScore value={job.match} />
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[13px] text-ss-sub">
            {job.company} · {job.location}
            {job.uploaded && <UploadedBadge />}
          </p>
          <p className="text-[13px] text-ss-mute">
            {job.work_type} · {job.level}
          </p>
          {!compact && (
            <>
              <p className="mt-3 text-sm leading-relaxed text-ss-sub">{job.explanation}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {job.matched_skills.slice(0, 4).map((s) => (
                  <SkillBadge key={s} tone="green" icon="check">
                    {s}
                  </SkillBadge>
                ))}
                {job.missing_skills.slice(0, 3).map((s) => (
                  <SkillBadge key={s} tone="red" icon="x">
                    {s}
                  </SkillBadge>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      {!compact && onSave && (
        <div className="relative z-10 mt-4 flex flex-wrap gap-2 pl-[56px]">
          <button type="button" className="ss-btn2 h-9 px-3 text-[13px]" onClick={onSelect}>
            View Details
          </button>
          <button type="button" className="ss-btn2 h-9 px-3 text-[13px]" onClick={() => onSave(job)} aria-pressed={saved}>
            <Icon name="bookmark" size={15} className={saved ? 'fill-current text-ss-green' : ''} />
            {saved ? 'Saved' : 'Save Job'}
          </button>
          <ApplyLink job={job} className="ss-btn h-9 px-3 text-[13px]" />
        </div>
      )}
    </article>
  )
})

export function UploadedBadge() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-ss-p-bg px-2 py-0.5 text-[11px] font-semibold text-ss-p-ink">
      <Icon name="upload" size={11} strokeWidth={2.4} />
      Your JD
    </span>
  )
}

export function ApplyLink({ job, className = 'ss-btn', label = 'Apply' }) {
  if (!job.source_url) return null
  return (
    <a
      href={job.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      title={`Opens the original listing on ${job.source_name}. Captured ${job.retrieved_at}; it may have closed since.`}
    >
      {label}
      <Icon name="external" size={15} />
    </a>
  )
}

/* ---- Skill gap row ----------------------------------------------------------- */
const LEVEL = { strong: 90, improve: 50, missing: 8 }
export const SkillGap = memo(function SkillGap({ row }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="border-b border-ss-line last:border-0">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-5 py-3 text-left hover:bg-ss-soft/60 sm:grid-cols-[150px_minmax(0,1fr)_92px_18px]">
        <span className="truncate font-medium text-ss-ink">{row.skill}</span>
        <span className="order-3 col-span-2 flex items-center gap-2 sm:order-none sm:col-span-1">
          <Bar value={LEVEL[row.status]} tone={statusTone[row.status]} className="flex-1" />
          <span className="hidden w-[84px] text-[11px] text-ss-mute md:inline">{row.required_level}</span>
        </span>
        <span className="justify-self-end">
          <StatusBadge status={row.status} />
        </span>
        <Icon name="down" size={16} className={`hidden text-ss-mute transition sm:block ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <dl className="grid gap-3 bg-ss-soft/50 px-5 py-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ss-mute">Current skill</dt>
            <dd className="mt-0.5 text-ss-ink">{row.current || 'Not in your resume'}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ss-mute">Required skill</dt>
            <dd className="mt-0.5 text-ss-ink">
              {row.skill} · {row.required_level}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ss-mute">Gap</dt>
            <dd className="mt-0.5 text-ss-ink">{row.gap}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ss-mute">Recommendation</dt>
            <dd className="mt-0.5 text-ss-ink">{row.recommendation}</dd>
          </div>
          {row.evidence?.[0] && (
            <div className="sm:col-span-2">
              <dt className="text-xs font-semibold uppercase tracking-wide text-ss-mute">Resume evidence</dt>
              <dd className="mt-0.5 text-ss-sub">
                “{row.evidence[0].text}” <span className="text-ss-mute">— {row.evidence[0].where}</span>
              </dd>
            </div>
          )}
        </dl>
      )}
    </li>
  )
})

/* ---- Improvement card ----------------------------------------------------------- */
const CAT_ICON = { Resume: 'resume', Skills: 'skills', Projects: 'layers', Experience: 'jobs', Keywords: 'key', 'Job Match': 'target', 'Interview Preparation': 'mic' }
const CAT_TONE = { Resume: 'red', Skills: 'purple', Projects: 'blue', Experience: 'amber', Keywords: 'green', 'Job Match': 'blue', 'Interview Preparation': 'purple' }
export const ImprovementCard = memo(function ImprovementCard({ item }) {
  return (
    <Card as="article" className="p-4 sm:p-5">
      <div className="flex gap-4">
        <span className={`hidden h-14 w-14 shrink-0 place-items-center rounded-2xl sm:grid ${TONE[CAT_TONE[item.category]]}`}>
          <Icon name={CAT_ICON[item.category]} size={26} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-ss-ink">{item.title}</h3>
              <span className="rounded-md bg-ss-soft px-2 py-0.5 text-xs text-ss-sub">{item.category}</span>
            </div>
            <PriorityBadge priority={item.priority} />
          </div>
          <dl className="mt-2 space-y-1.5 text-sm">
            <div>
              <dt className="inline font-semibold text-ss-ink">Problem: </dt>
              <dd className="inline text-ss-sub">{item.problem}</dd>
            </div>
            <div>
              <dt className="inline font-semibold text-ss-ink">Why it matters: </dt>
              <dd className="inline text-ss-sub">{item.why}</dd>
            </div>
            <div>
              <dt className="inline font-semibold text-ss-ink">Suggested action: </dt>
              <dd className="inline text-ss-sub">{item.action}</dd>
            </div>
          </dl>
          {item.example && (
            <div className="mt-3 grid gap-2 rounded-xl bg-ss-soft/70 p-3 text-sm sm:grid-cols-2">
              <p>
                <span className="font-semibold text-ss-r-ink">Before: </span>
                <span className="text-ss-sub">“{item.example.before}”</span>
              </p>
              <p>
                <span className="font-semibold text-ss-g-ink">After: </span>
                <span className="text-ss-sub">{item.example.after}</span>
              </p>
            </div>
          )}
          {item.keywords?.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-xs font-semibold text-ss-sub">Keywords:</span>
              {item.keywords.map((k) => (
                <SkillBadge key={k} tone="blue">
                  {k}
                </SkillBadge>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  )
})

/* ---- Resume summary ---------------------------------------------------------- */
export function ResumeSummary({ profile }) {
  const edu = profile.education?.[0]
  const latest = profile.experience?.[0]
  return (
    <div className="p-5">
      <div className="flex items-center gap-3">
        <Avatar name={profile.name} size={52} />
        <div className="min-w-0">
          <p className="text-lg font-semibold text-ss-ink">{profile.name}</p>
          <p className="text-sm text-ss-sub">
            {profile.headline}
            {profile.location ? ` · ${profile.location}` : ''}
          </p>
        </div>
      </div>
      {profile.summary && <p className="mt-4 text-sm leading-relaxed text-ss-sub">{profile.summary}</p>}
      <div className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <p className="font-semibold text-ss-ink">Education</p>
          {edu ? (
            <p className="mt-1 text-ss-sub">
              {edu.degree}
              <br />
              {edu.institution}
              {edu.end ? ` · ${edu.start ? `${edu.start}–` : ''}${edu.end}` : ''}
            </p>
          ) : (
            <p className="mt-1 text-ss-mute">Not listed</p>
          )}
        </div>
        <div>
          <p className="font-semibold text-ss-ink">Experience</p>
          <p className="mt-1 text-ss-sub">
            {profile.years_experience > 0 ? `${profile.years_experience} year${profile.years_experience === 1 ? '' : 's'}` : 'Fresher'}
            {latest && (
              <>
                <br />
                {latest.title}
              </>
            )}
          </p>
        </div>
        <div>
          <p className="font-semibold text-ss-ink">Projects</p>
          <p className="mt-1 text-ss-sub">
            {profile.projects?.length || 0} project{profile.projects?.length === 1 ? '' : 's'}
            <br />
            {profile.projects
              ?.slice(0, 2)
              .map((p) => p.name)
              .join(', ')}
          </p>
        </div>
      </div>
      <div className="mt-5">
        <p className="text-sm font-semibold text-ss-ink">Certifications</p>
        <p className="mt-1 text-sm text-ss-sub">{profile.certifications?.length ? profile.certifications.join(' · ') : 'None listed'}</p>
      </div>
      <div className="mt-5">
        <p className="text-sm font-semibold text-ss-ink">Technical Skills</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {profile.technical_skills.map((s) => (
            <SkillBadge key={s} tone="blue">
              {s}
            </SkillBadge>
          ))}
        </div>
      </div>
      <div className="mt-4">
        <p className="text-sm font-semibold text-ss-ink">Soft Skills</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {profile.soft_skills.map((s) => (
            <SkillBadge key={s} tone="purple">
              {s}
            </SkillBadge>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ---- Citations ---------------------------------------------------------------- */
export function SourceCitation({ sources = [], used = [] }) {
  const [open, setOpen] = useState(false)
  const shown = used.length ? sources.filter((s) => used.includes(s.ref_id)) : sources
  if (!shown.length) return null
  return (
    <div className="mt-3 border-t border-ss-line pt-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-semibold text-ss-sub">Sources used ({shown.length})</span>
        {shown.map((s) => (
          <span key={s.id} className="rounded-md bg-ss-b-bg px-2 py-0.5 text-[11.5px] font-medium text-ss-b-ink" title={s.title}>
            {s.label}
          </span>
        ))}
      </div>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-ss-sub hover:text-ss-ink">
        <Icon name="down" size={14} className={`transition ${open ? 'rotate-180' : ''}`} />
        Information used for this answer
      </button>
      {open && (
        <ol className="mt-2 space-y-2">
          {sources.map((s) => (
            <li key={s.id} className={`rounded-lg border border-ss-line p-2.5 text-xs ${used.includes(s.ref_id) ? 'bg-ss-card' : 'bg-ss-soft/50 opacity-80'}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-ss-ink">
                  [{s.ref_id}] {s.label} · {s.title}
                </span>
                <span className="shrink-0 text-ss-mute" title={s.core ? 'Always included in full' : 'Relevance to your question'}>
                  {s.core ? 'Full document' : `${Math.round(s.similarity * 100)}% relevant`}
                </span>
              </div>
              <p className="mt-1 line-clamp-3 text-ss-sub">{s.text}</p>
              {s.url && (
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-ss-b-ink hover:underline">
                  Original listing <Icon name="external" size={12} />
                </a>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/* ---- Chat --------------------------------------------------------------------- */
function renderAnswer(text) {
  // Minimal, safe formatting: paragraphs, bullet / numbered lines, **bold**, [S#] chips.
  const lines = text.split('\n').filter((l, i, a) => l.trim() || (i > 0 && a[i - 1].trim()))
  const inline = (t, key) =>
    t.split(/(\*\*[^*]+\*\*|\[S\d+\])/g).map((part, i) =>
      part.startsWith('**') ? (
        <strong key={`${key}-${i}`} className="font-semibold text-ss-ink">
          {part.slice(2, -2)}
        </strong>
      ) : /^\[S\d+\]$/.test(part) ? (
        <sup key={`${key}-${i}`} className="mx-0.5 rounded bg-ss-b-bg px-1 text-[10px] font-semibold text-ss-b-ink">
          {part.slice(1, -1)}
        </sup>
      ) : (
        part
      )
    )
  return lines.map((line, i) => {
    const m = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/)
    if (m)
      return (
        <p key={i} className="relative pl-4 before:absolute before:left-0 before:top-[0.6em] before:h-1.5 before:w-1.5 before:rounded-full before:bg-ss-green/70">
          {inline(m[1], i)}
        </p>
      )
    return line.trim() ? <p key={i}>{inline(line, i)}</p> : <div key={i} className="h-1" />
  })
}

export const ChatMessage = memo(function ChatMessage({ message }) {
  if (message.role === 'user')
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-ss-green px-4 py-2.5 text-[15px] text-ss-on-green shadow-sm">{message.content}</div>
      </div>
    )
  const r = message.result || {}
  const about = r.job_id && r.sources?.find((s) => s.kind === 'job' && s.ref === r.job_id)
  return (
    <div className="flex gap-3">
      <span className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ss-p-bg text-ss-p-ink" aria-hidden="true">
        <Icon name="ai" size={18} />
      </span>
      <div className="min-w-0 max-w-[92%] flex-1 rounded-2xl rounded-tl-md border border-ss-line bg-ss-card px-4 py-3 text-[15px] leading-relaxed text-ss-sub shadow-sm">
        {r.mode === 'retrieval_only' && (
          <p className="mb-2 flex items-start gap-2 rounded-lg bg-ss-a-bg px-3 py-2 text-sm text-ss-a-ink">
            <Icon name="info" size={16} className="mt-0.5" />
            {r.notice}
          </p>
        )}
        {message.error && <p className="text-ss-r-ink">{message.error}</p>}
        {about && (
          <p className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-ss-p-bg px-2.5 py-0.5 text-[11.5px] font-medium text-ss-p-ink">
            <Icon name="jobs" size={12} /> About: {about.title}
          </p>
        )}
        {message.content && <div className="space-y-1.5">{renderAnswer(message.content)}</div>}
        {r.mode === 'retrieval_only' && (
          <ul className="space-y-2">
            {r.sources.slice(0, 3).map((s) => (
              <li key={s.id} className="text-sm">
                <span className="font-semibold text-ss-ink">{s.label}:</span> {s.text}
              </li>
            ))}
          </ul>
        )}
        {r.sources && r.mode !== 'refused' && <SourceCitation sources={r.sources} used={r.used_sources} />}
      </div>
    </div>
  )
})

export function ChatInput({ onSend, disabled, placeholder = 'Ask a question about your resume, jobs, or career…' }) {
  const [text, setText] = useState('')
  const ref = useRef(null)
  useEffect(() => {
    if (!disabled) ref.current?.focus()
  }, [disabled])
  const submit = (e) => {
    e.preventDefault()
    const q = text.trim()
    if (!q || disabled) return
    onSend(q)
    setText('')
  }
  return (
    <form onSubmit={submit} className="flex items-center gap-2 rounded-2xl border border-ss-line bg-ss-card p-1.5 pl-4 shadow-sm focus-within:border-ss-green/50">
      <label htmlFor="ss-chat" className="sr-only">
        Ask the AI Career Assistant
      </label>
      <input
        id="ss-chat"
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        maxLength={600}
        className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-ss-ink placeholder:text-ss-mute focus:outline-none"
        autoComplete="off"
      />
      <button type="submit" disabled={disabled || !text.trim()} className="grid h-10 w-10 place-items-center rounded-full bg-ss-green text-ss-on-green transition hover:brightness-110 disabled:opacity-40" aria-label="Send">
        <Icon name="send" size={17} />
      </button>
    </form>
  )
}

/* ---- Loading / empty / error ------------------------------------------------ */
export function LoadingSkeleton({ message, rows = 3, cards = 0 }) {
  return (
    <div aria-busy="true" aria-live="polite">
      {message && (
        <p className="mb-4 flex items-center gap-2 text-sm text-ss-sub">
          <span className="h-2 w-2 animate-pulse rounded-full bg-ss-green" />
          {message}
        </p>
      )}
      {cards > 0 && (
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: cards }).map((_, i) => (
            <div key={i} className="ss-skel h-[108px] rounded-[18px]" />
          ))}
        </div>
      )}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="ss-skel h-24 rounded-[18px]" style={{ opacity: 1 - i * 0.18 }} />
        ))}
      </div>
    </div>
  )
}

export function EmptyState({ icon = 'resume', title, message, action }) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid h-16 w-16 place-items-center rounded-2xl bg-ss-g-bg text-ss-g-ink">
        <Icon name={icon} size={30} />
      </span>
      {title && <h2 className="mt-5 text-lg font-semibold text-ss-ink">{title}</h2>}
      <p className="mt-2 max-w-md text-ss-sub">{message}</p>
      {action && <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>}
    </Card>
  )
}

export function ErrorState({ error, onRetry, message = 'Something went wrong while analyzing your resume.' }) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center" role="alert">
      <span className="grid h-16 w-16 place-items-center rounded-2xl bg-ss-r-bg text-ss-r-ink">
        <Icon name="alert" size={30} />
      </span>
      <h2 className="mt-5 text-lg font-semibold text-ss-ink">{message}</h2>
      {error?.message && <p className="mt-2 max-w-md text-sm text-ss-sub">{error.message}{error.hint ? ` ${error.hint}` : ''}</p>}
      <div className="mt-6 flex gap-2">
        {onRetry && (
          <button type="button" className="ss-btn" onClick={onRetry}>
            <Icon name="refresh" size={16} /> Try Again
          </button>
        )}
        <button type="button" className="ss-btn2" onClick={() => window.history.back()}>
          <Icon name="back" size={16} /> Go Back
        </button>
      </div>
    </Card>
  )
}

export function NoResume() {
  return (
    <EmptyState
      icon="upload"
      title="No resume selected yet"
      message="Upload a resume to unlock your personalized matches."
      action={
        <>
          <Link to="/app/resume" className="ss-btn">
            <Icon name="upload" size={16} /> Upload Resume
          </Link>
          <Link to="/app/resume?tab=samples" className="ss-btn2">
            Choose Sample Resume
          </Link>
        </>
      }
    />
  )
}

/** Shown in the online (GitHub Pages) demo where a feature needs the server. */
export function DemoNotice({ title = 'Available in the full app' }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border-2 border-dashed border-ss-b-ink/30 bg-ss-b-bg/40 px-6 py-10 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full bg-ss-card text-ss-b-ink">
        <Icon name="info" size={24} />
      </span>
      <p className="mt-4 font-semibold text-ss-ink">{title}</p>
      <p className="mt-1 max-w-md text-sm text-ss-sub">{STATIC_NOTICE}</p>
      <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="ss-btn mt-5">
        View on GitHub <Icon name="external" size={15} />
      </a>
    </div>
  )
}

export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div role="tablist" aria-label={label} className="ss-scroll -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
      {tabs.map((t) => {
        const id = t.id ?? t
        const active = id === value
        return (
          <button
            key={id}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(id)}
            className={`shrink-0 whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-medium transition ${active ? 'bg-ss-pill text-ss-pill-ink shadow-sm' : 'text-ss-sub hover:bg-ss-soft hover:text-ss-ink'}`}
          >
            {t.label ?? t}
            {t.count != null && <span className="ml-1.5 text-xs opacity-70">{t.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
