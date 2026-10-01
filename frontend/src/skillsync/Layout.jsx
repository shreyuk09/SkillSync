import { Suspense, useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import logoMark from '../assets/logo-mark.webp'
import { paths, prefetch } from './api'
import { Avatar, LoadingSkeleton } from './components'
import { Icon } from './icons'
import JdUpload from './JdUpload'
import { loaders } from './routes'
import { SkillSyncProvider, useSkillSync } from './store'
import { useQuery } from './useQuery'
import './ss.css'

const NAV = [
  { to: '/app', label: 'Dashboard', icon: 'home', end: true, page: 'dashboard', data: paths.dashboard },
  { to: '/app/resume', label: 'My Resume', icon: 'resume', page: 'resume' },
  { to: '/app/analysis', label: 'Resume Analysis', icon: 'analysis', page: 'analysis', data: paths.analysis },
  { to: '/app/jobs', label: 'Job Matches', icon: 'jobs', page: 'jobs', data: paths.matches },
  { to: '/app/skills', label: 'Skill Analysis', icon: 'skills', page: 'skills', data: (id) => paths.skills(id) },
  { to: '/app/improvements', label: 'Improvements', icon: 'improve', page: 'improvements', data: paths.improvements },
  { to: '/app/assistant', label: 'AI Career Assistant', icon: 'ai', page: 'assistant' },
  { to: '/app/saved', label: 'Saved Jobs', icon: 'bookmark', page: 'saved' },
  { to: '/app/settings', label: 'Settings', icon: 'settings', page: 'settings' },
]
const MOBILE = ['/app', '/app/resume', '/app/jobs', '/app/skills', '/app/assistant']

function useWarm(resumeId) {
  return (item) => {
    loaders[item.page]?.()
    if (resumeId && item.data) prefetch(item.data(resumeId))
  }
}

function Brand({ compact }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg" aria-label="SkillSync home">
      <img src={logoMark} alt="" width="34" height="34" className="h-[34px] w-[34px]" />
      {!compact && <span className="text-[22px] font-bold tracking-[-0.02em] text-ss-ink">SkillSync</span>}
    </Link>
  )
}

function ProfileFooter({ compact }) {
  const { resumeId } = useSkillSync()
  const { data } = useQuery(resumeId ? paths.resume(resumeId) : null)
  if (!resumeId)
    return (
      <Link to="/app/resume" className={`block rounded-xl border border-dashed border-ss-line p-3 text-sm text-ss-sub hover:bg-ss-soft ${compact ? 'hidden' : ''}`}>
        No resume selected. <span className="font-semibold text-ss-green">Choose one →</span>
      </Link>
    )
  if (!data) return <div className="ss-skel h-[54px]" />
  return (
    <Link to="/app/resume" className="block rounded-xl p-2 hover:bg-ss-soft" title={data.name}>
      <div className={`flex items-center gap-3 ${compact ? 'justify-center' : ''}`}>
        <Avatar name={data.name} size={38} />
        {!compact && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ss-ink">{data.name}</p>
            <p className="truncate text-xs text-ss-mute">{data.email || data.headline}</p>
          </div>
        )}
      </div>
    </Link>
  )
}

function Sidebar() {
  const { resumeId } = useSkillSync()
  const warm = useWarm(resumeId)
  return (
    <aside className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-ss-line bg-ss-side md:flex md:w-[84px] lg:w-[248px]">
      <div className="flex h-[72px] items-center px-6 md:justify-center lg:justify-start">
        <span className="lg:hidden">
          <Brand compact />
        </span>
        <span className="hidden lg:block">
          <Brand />
        </span>
      </div>
      <nav aria-label="Main" className="ss-scroll flex-1 overflow-y-auto px-3 py-3 lg:px-4">
        <ul className="space-y-1">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                onMouseEnter={() => warm(item)}
                onFocus={() => warm(item)}
                title={item.label}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14.5px] font-medium transition md:justify-center lg:justify-start ${isActive ? 'bg-ss-pill text-ss-pill-ink shadow-sm' : 'text-ss-sub hover:bg-ss-soft hover:text-ss-ink'}`
                }
              >
                <Icon name={item.icon} size={20} />
                <span className="md:sr-only lg:not-sr-only">{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-ss-line p-3 lg:p-4">
        <span className="lg:hidden">
          <ProfileFooter compact />
        </span>
        <span className="hidden lg:block">
          <ProfileFooter />
        </span>
      </div>
    </aside>
  )
}

function ThemeButton() {
  const { theme, toggleTheme } = useApp()
  const dark = theme === 'dark'
  return (
    <button type="button" onClick={toggleTheme} aria-pressed={dark} title={dark ? 'Switch to light mode' : 'Switch to dark mode'} className="grid h-10 w-10 place-items-center rounded-full text-ss-sub hover:bg-ss-soft hover:text-ss-ink">
      <Icon name={dark ? 'sun' : 'moon'} size={19} />
      <span className="sr-only">{dark ? 'Light mode' : 'Dark mode'}</span>
    </button>
  )
}

function Bell() {
  const { resumeId } = useSkillSync()
  const { data } = useQuery(resumeId ? paths.dashboard(resumeId) : null)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const close = (e) => !ref.current?.contains(e.target) && setOpen(false)
    const esc = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])
  const items = data
    ? [
        data.cards.strong_matches > 0 && { to: '/app/jobs', text: `${data.cards.strong_matches} strong job match${data.cards.strong_matches > 1 ? 'es' : ''} for your resume` },
        data.top_improvements[0] && { to: '/app/improvements', text: `Top improvement: ${data.top_improvements[0].title}` },
        data.top_gaps[0] && { to: '/app/skills', text: `Skill to work on: ${data.top_gaps[0].skill}` },
      ].filter(Boolean)
    : []
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="true" className="relative grid h-10 w-10 place-items-center rounded-full text-ss-sub hover:bg-ss-soft hover:text-ss-ink" title="Notifications">
        <Icon name="bell" size={19} />
        {items.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-ss-r-ink ring-2 ring-ss-page" />}
        <span className="sr-only">Notifications</span>
      </button>
      {open && (
        <div className="ss-card absolute right-0 top-12 z-40 w-[300px] p-2">
          {items.length ? (
            items.map((it) => (
              <Link key={it.text} to={it.to} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2.5 text-sm text-ss-sub hover:bg-ss-soft hover:text-ss-ink">
                {it.text}
              </Link>
            ))
          ) : (
            <p className="px-3 py-2.5 text-sm text-ss-sub">You're all caught up.</p>
          )}
        </div>
      )}
    </div>
  )
}

function TopNavbar({ onMenu }) {
  const navigate = useNavigate()
  const { resumeId, openJd } = useSkillSync()
  const { data } = useQuery(resumeId ? paths.resume(resumeId) : null)
  const [q, setQ] = useState('')
  const submit = (e) => {
    e.preventDefault()
    navigate(`/app/jobs${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`)
  }
  return (
    <header className="sticky top-0 z-30 flex h-[64px] items-center gap-3 border-b border-ss-line bg-ss-page/85 px-4 backdrop-blur md:h-[72px] md:border-0 md:bg-transparent md:px-8 md:backdrop-blur-0">
      <button type="button" onClick={onMenu} className="grid h-10 w-10 place-items-center rounded-full text-ss-sub hover:bg-ss-soft md:hidden" aria-label="Open menu">
        <Icon name="menu" size={21} />
      </button>
      <span className="md:hidden">
        <Brand />
      </span>
      <form onSubmit={submit} role="search" className="hidden max-w-[420px] flex-1 items-center gap-2 rounded-xl border border-ss-line bg-ss-card px-3.5 py-2.5 focus-within:border-ss-green/50 md:flex">
        <Icon name="search" size={17} className="text-ss-mute" />
        <label htmlFor="ss-search" className="sr-only">
          Search jobs and skills
        </label>
        <input id="ss-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search jobs, skills or companies…" className="min-w-0 flex-1 bg-transparent text-sm text-ss-ink placeholder:text-ss-mute focus:outline-none" />
      </form>
      <div className="ml-auto flex items-center gap-1">
        <button type="button" onClick={openJd} className="ss-btn mr-1 h-10 px-3 text-[13px] sm:px-4 sm:text-sm" title="Upload your own job description and see your match">
          <Icon name="upload" size={16} />
          <span className="hidden sm:inline">Upload Job Description</span>
          <span className="sm:hidden">JD</span>
        </button>
        <ThemeButton />
        <Bell />
        <Link to="/app/resume" className="ml-1 hidden rounded-full sm:block" title="My Resume">
          <Avatar name={data?.name || 'Sk Sy'} size={38} />
        </Link>
      </div>
    </header>
  )
}

function MobileNav() {
  return (
    <nav aria-label="Quick" className="fixed inset-x-0 bottom-0 z-30 border-t border-ss-line bg-ss-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
      <ul className="grid grid-cols-5">
        {NAV.filter((n) => MOBILE.includes(n.to)).map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} end={item.end} className={({ isActive }) => `flex flex-col items-center gap-1 py-2 text-[11px] font-medium ${isActive ? 'text-ss-green' : 'text-ss-mute'}`}>
              <Icon name={item.icon} size={21} />
              {item.label.replace('AI Career Assistant', 'AI Assistant').replace('Skill Analysis', 'Skills').replace('Job Matches', 'Jobs')}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Drawer({ open, onClose }) {
  const location = useLocation()
  useEffect(onClose, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
      <button type="button" className="absolute inset-0 bg-black/30" onClick={onClose} aria-label="Close menu" />
      <div className="absolute inset-y-0 left-0 flex w-[280px] flex-col bg-ss-side shadow-xl">
        <div className="flex h-16 items-center justify-between px-5">
          <Brand />
          <button type="button" onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full text-ss-sub hover:bg-ss-soft" aria-label="Close menu">
            <Icon name="x" size={20} />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `mb-1 flex items-center gap-3 rounded-xl px-3 py-3 font-medium ${isActive ? 'bg-ss-pill text-ss-pill-ink' : 'text-ss-sub'}`}>
              <Icon name={item.icon} size={20} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-ss-line p-4">
          <ProfileFooter />
        </div>
      </div>
    </div>
  )
}

function Shell() {
  const [menu, setMenu] = useState(false)
  const { jdOpen, closeJd } = useSkillSync()
  const location = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])
  return (
    <div className="ss flex min-h-screen">
      <a href="#ss-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ss-card focus:px-4 focus:py-2">
        Skip to content
      </a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNavbar onMenu={() => setMenu(true)} />
        <main id="ss-main" className="mx-auto w-full max-w-[1280px] flex-1 px-4 pb-28 pt-4 sm:px-6 md:px-8 md:pb-12 md:pt-2">
          <Suspense fallback={<LoadingSkeleton rows={3} cards={4} />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <MobileNav />
      <Drawer open={menu} onClose={() => setMenu(false)} />
      <JdUpload open={jdOpen} onClose={closeJd} />
    </div>
  )
}

export default function SkillSyncLayout() {
  return (
    <SkillSyncProvider>
      <Shell />
    </SkillSyncProvider>
  )
}
