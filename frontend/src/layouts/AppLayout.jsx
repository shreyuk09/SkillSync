import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { Badge, Button, cx } from '../components/ui'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: 'M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-4H4zM14 8h6V4h-6z', needs: 'both' },
  { to: '/resume', label: 'Resume', icon: 'M7 3h7l4 4v14H7zM14 3v4h4M10 13h6M10 17h4', needs: 'resume' },
  { to: '/job', label: 'Job Description', icon: 'M4 8h16v12H4zM9 8V5h6v3M4 13h16', needs: 'jd' },
  { to: '/match', label: 'Match Analysis', icon: 'M12 3v18M5 8l7-5 7 5M5 16l7 5 7-5', needs: 'both' },
  { to: '/assistant', label: 'AI Assistant', icon: 'M4 5h16v11H9l-5 4z', needs: 'both', badge: 'RAG' },
  { to: '/improvements', label: 'Improvements', icon: 'M4 20l5-1 10-10-4-4L5 15zM14 6l4 4', needs: 'both' },
  { to: '/interview', label: 'Interview Prep', icon: 'M12 3a4 4 0 110 8 4 4 0 010-8zM4 21c0-4 3.6-7 8-7s8 3 8 7', needs: 'both' },
  { to: '/roadmap', label: 'Learning Roadmap', icon: 'M4 6h10M4 12h16M4 18h8M18 3l3 3-3 3', needs: 'both' },
]

function Logo({ className }) {
  return (
    <span className={cx('flex items-center gap-2.5', className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand text-[13px] font-bold text-white">
        R
      </span>
      <span className="text-[15px] font-bold tracking-tight text-ink">
        Resume<span className="text-brand">RAG</span>
      </span>
    </span>
  )
}

function NavItem({ item, disabled, onNavigate }) {
  return (
    <NavLink
      to={item.to}
      onClick={(event) => {
        if (disabled) event.preventDefault()
        else onNavigate?.()
      }}
      aria-disabled={disabled}
      title={disabled ? 'Upload your resume and a job description first' : undefined}
      className={({ isActive }) =>
        cx(
          'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition-all duration-150',
          disabled
            ? 'cursor-not-allowed text-subtle opacity-55'
            : isActive
              ? 'bg-brand/10 text-brand'
              : 'text-muted hover:bg-raised hover:text-ink'
        )
      }
    >
      {({ isActive }) => (
        <>
          <svg
            className={cx('h-[17px] w-[17px] shrink-0', isActive && 'text-brand')}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
          >
            <path d={item.icon} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge && (
            <span className="rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-brand ring-1 ring-inset ring-brand/30">
              {item.badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

export function AppLayout() {
  const { status, health, hasResume, hasJd, ready, resetSession, theme, toggleTheme } = useApp()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  const isDisabled = (needs) => {
    if (needs === 'resume') return !hasResume
    if (needs === 'jd') return !hasJd
    if (needs === 'any') return !hasResume && !hasJd
    return !ready
  }

  const sidebar = (
    <>
      <div className="px-3 pb-4 pt-1">
        <StepTracker hasResume={hasResume} hasJd={hasJd} />
      </div>
      <nav className="flex-1 space-y-0.5 px-3">
        {NAV.map((item) => (
          <NavItem
            key={item.to}
            item={item}
            disabled={isDisabled(item.needs)}
            onNavigate={() => setMenuOpen(false)}
          />
        ))}
      </nav>
      <div className="space-y-3 px-3 pb-4 pt-4">
        {health?.rag && (
          <div className="rounded-xl border border-line bg-raised/50 p-3">
            <p className="text-[10.5px] font-semibold uppercase tracking-wider text-subtle">
              RAG stack
            </p>
            <dl className="mt-2 space-y-1 text-[11.5px]">
              <div className="flex justify-between gap-2">
                <dt className="text-subtle">Embeddings</dt>
                <dd className="truncate font-medium text-muted" title={health.rag.embedding_model}>
                  {health.rag.semantic_embeddings ? 'MiniLM' : 'Hashing'}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-subtle">Vector DB</dt>
                <dd className="font-medium text-muted">{health.rag.vector_store}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-subtle">Provider</dt>
                <dd className="truncate font-medium text-muted">{health.rag.llm_provider}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-subtle">Model</dt>
                <dd className="truncate font-medium text-muted" title={health.rag.llm_model}>
                  {String(health.rag.llm_model).split('/').pop()}
                </dd>
              </div>
              {status?.chunk_count > 0 && (
                <div className="flex justify-between gap-2">
                  <dt className="text-subtle">Indexed</dt>
                  <dd className="font-medium text-muted">{status.chunk_count} chunks</dd>
                </div>
              )}
            </dl>
          </div>
        )}
        <button
          onClick={resetSession}
          className="w-full rounded-lg px-3 py-2 text-left text-[12.5px] font-medium text-subtle transition-colors hover:bg-raised hover:text-critical"
        >
          Clear session &amp; delete my data
        </button>
      </div>
    </>
  )

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-surface lg:flex">
        <div className="px-5 py-5">
          <NavLink to="/">
            <Logo />
          </NavLink>
        </div>
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/45" onClick={() => setMenuOpen(false)} />
          <aside className="relative flex h-full w-72 flex-col border-r border-line bg-surface">
            <div className="flex items-center justify-between px-5 py-5">
              <Logo />
              <button
                onClick={() => setMenuOpen(false)}
                aria-label="Close menu"
                className="rounded-lg p-1.5 text-muted hover:bg-raised"
              >
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur-md sm:px-6">
          <button
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 text-muted transition-colors hover:bg-raised lg:hidden"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
            </svg>
          </button>

          <div className="min-w-0 flex-1">
            <p className="truncate text-[13.5px] font-semibold text-ink">
              {NAV.find((item) => location.pathname.startsWith(item.to))?.label || 'Upload'}
            </p>
          </div>

          {health && !health.rag.llm_configured && (
            <Badge tone="warn" icon={<span aria-hidden="true">!</span>}>
              <span className="hidden sm:inline">No API key configured</span>
              <span className="sm:hidden">No key</span>
            </Badge>
          )}

          <NavLink to="/upload">
            <Button size="sm" variant="secondary">
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 16V4m0 0L8 8m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
              </svg>
              <span className="hidden sm:inline">Documents</span>
            </Button>
          </NavLink>

          <button
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-pressed={theme === 'dark'}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            className="rounded-lg p-2 text-muted transition-colors hover:bg-raised hover:text-ink"
          >
            {theme === 'dark' ? (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" strokeLinecap="round" />
              </svg>
            ) : (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </header>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function StepTracker({ hasResume, hasJd }) {
  const steps = [
    { label: 'Resume', done: hasResume },
    { label: 'Job description', done: hasJd },
    { label: 'Analysis ready', done: hasResume && hasJd },
  ]
  return (
    <ol className="space-y-1.5">
      {steps.map((step) => (
        <li key={step.label} className="flex items-center gap-2.5 text-[12px]">
          <span
            aria-hidden="true"
            className={cx(
              'flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold',
              step.done ? 'bg-good/20 text-good' : 'border border-line text-subtle'
            )}
          >
            {step.done ? '✓' : ''}
          </span>
          <span className={step.done ? 'font-medium text-muted' : 'text-subtle'}>{step.label}</span>
        </li>
      ))}
    </ol>
  )
}
