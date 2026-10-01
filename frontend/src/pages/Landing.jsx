import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { HowItWorksContent } from './HowItWorks'
import heroArt from '../assets/hero-art.webp'
import logoMark from '../assets/logo-mark.webp'
import iconMatching from '../assets/icon-matching.webp'
import iconGap from '../assets/icon-gap.webp'
import iconSuggest from '../assets/icon-suggest.webp'

/**
 * The landing page, built to match the supplied design comp.
 *
 * Desktop geometry is written in `u`, a unit equal to 1px when the viewport is
 * 1584px wide -- the width the comp was drawn at -- and shrinking in
 * proportion below that. Every position and size below was measured off the
 * comp in pixels, so at 1584px the page lines up with it exactly and at
 * smaller desktop widths it scales rather than reflowing into something else.
 * Under 1024px it drops to an ordinary stacked layout.
 *
 * The palette is scoped to `.sync` on purpose: the application's own blue is a
 * data colour its charts are calibrated against, and must not be touched by a
 * marketing page.
 */
const STYLES = `
.sync {
  --u: min(1px, calc(100vw / 1584));

  --s-page: #fdfaf3;
  --s-ink: #041024;
  --s-green: #046834;
  --s-green-top: #298655;
  --s-green-bottom: #086030;
  --s-on-green: #ffffff;
  --s-pill: #e4f0e0;
  --s-pill-ink: #045c24;
  --s-link: #747478;
  --s-sub: #5c6064;
  --s-line: #ebe4d8;
  --s-btn: #fdf9f3;
  --s-card1: #fef8ef;
  --s-card2: #f8f3fd;
  --s-card3: #edf6fd;
  --s-card-body: #747478;

  background: var(--s-page);
  color: var(--s-ink);
  min-height: 100vh;
}
.dark .sync {
  --s-page: #121210;
  --s-ink: #f5f2eb;
  --s-green: #5fae7d;
  --s-green-top: #74c191;
  --s-green-bottom: #4f9d6c;
  --s-on-green: #0f140f;
  --s-pill: #1d2a22;
  --s-pill-ink: #7cc496;
  --s-link: #b3afa5;
  --s-sub: #b3afa5;
  --s-line: #2e2e28;
  --s-btn: #1d1d1a;
  --s-card1: #2a2117;
  --s-card2: #231f2e;
  --s-card3: #17232e;
  --s-card-body: #b3afa5;
}

.sx-green { background: linear-gradient(180deg, var(--s-green-top), var(--s-green-bottom)); color: var(--s-on-green); }
.sx-arrow { display: block; flex-shrink: 0; }

/* ---------------------------------------------------------- mobile first */
.sx-frame   { padding: 16px 20px 40px; }
.sx-header  { display: flex; align-items: center; gap: 12px; }
.sx-logo    { display: flex; align-items: center; gap: 10px; }
.sx-logo img { width: 38px; height: 38px; }
.sx-word    { font: 800 24px/1 "Instrument Sans", Inter, system-ui, sans-serif; letter-spacing: -0.02em; }
.sx-links   { display: none; }
.sx-right   { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.sx-search, .sx-login { display: none; }
.sx-cta     { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; white-space: nowrap;
              padding: 11px 16px; font: 600 15px/1 "Instrument Sans", Inter, system-ui, sans-serif; }
.sx-h1      { margin-top: 36px; font: 400 48px/1 "DM Serif Display", Georgia, serif; letter-spacing: -0.025em; }
.sx-h1 .g   { color: var(--s-green); }
.sx-btns    { margin-top: 28px; display: flex; flex-wrap: wrap; gap: 12px; }
.sx-btn1, .sx-btn2 { display: inline-flex; align-items: center; justify-content: center; gap: 12px;
              height: 56px; padding: 0 24px; border-radius: 14px; font: 600 17px/1 "Instrument Sans", Inter, system-ui, sans-serif; }
.sx-btn2    { background: var(--s-btn); border: 1px solid var(--s-line); color: var(--s-ink); padding-left: 10px; }
.sx-play    { width: 34px; height: 34px; border-radius: 999px; background: var(--s-ink);
              display: flex; align-items: center; justify-content: center; }
.sx-sub     { margin-top: 22px; font: 400 18px/1.4 "Instrument Sans", Inter, system-ui, sans-serif; color: var(--s-sub); }
.sx-art     { display: block; width: 100%; height: auto; margin-top: 28px; }
.sx-cards   { margin-top: 24px; display: grid; gap: 14px; }
.sx-card    { display: flex; align-items: center; gap: 18px; border-radius: 18px; padding: 18px 22px;
              text-align: left; transition: transform .15s; }
.sx-card:hover { transform: translateY(-2px); }
.sx-card img { width: 64px; height: 64px; border-radius: 999px; flex-shrink: 0; }
.sx-card-t  { display: block; font: 600 19px/1.2 "Instrument Sans", Inter, system-ui, sans-serif; letter-spacing: -0.01em; }
.sx-card-b  { display: block; margin-top: 6px; font: 400 15px/1.3 "Instrument Sans", Inter, system-ui, sans-serif; color: var(--s-card-body); }
.sx-card .sx-arrow { margin-left: auto; }

.sx-theme   { display: flex; align-items: center; justify-content: center; border-radius: 999px;
              width: 42px; height: 42px; background: var(--s-btn); color: var(--s-ink);
              border: 1px solid var(--s-line); flex-shrink: 0; }
.sx-h1      { -webkit-text-stroke: 0.7px currentColor; }

/* The comp's backdrop is a warm ivory. On the dark page the art sits in a
   rounded panel instead: feathering an ivory image into black would leave a
   foggy halo, while a crisp panel reads as deliberate. */
.sx-art { border-radius: 24px; }
:root:not(.dark) .sx-art { border-radius: 0; }

/* the narrowest phones: tighten the header so nothing pushes the page sideways */
@media (max-width: 374px) {
  .sx-frame   { padding-left: 16px; padding-right: 16px; }
  .sx-logo    { gap: 8px; }
  .sx-logo img { width: 32px; height: 32px; }
  .sx-word    { font-size: 20px; }
  .sx-right   { gap: 8px; }
  .sx-theme   { width: 38px; height: 38px; }
  .sx-cta     { padding: 10px 13px; font-size: 14px; }
  .sx-cta .sx-arrow { display: none; }
  .sx-h1      { font-size: 42px; }
}

/* ------------------------------------------------ desktop: the comp's grid */
@media (min-width: 1024px) {
  .sx-frame   { position: relative; width: calc(1584 * var(--u)); height: calc(993 * var(--u));
                margin: 0 auto; padding: 0; }
  .sx-header  { position: absolute; inset: 0 0 auto 0; height: calc(110 * var(--u)); display: block; }
  .sx-logo    { position: absolute; left: calc(72 * var(--u)); top: calc(22 * var(--u)); gap: calc(21 * var(--u)); }
  .sx-logo img { width: calc(60 * var(--u)); height: calc(60 * var(--u)); }
  .sx-word    { font-size: calc(36 * var(--u)); font-weight: 700; position: relative; top: calc(2 * var(--u)); }

  .sx-links   { display: block; position: absolute; left: 0; top: calc(34 * var(--u)); }
  .sx-link    { display: block; position: absolute; left: calc(var(--x) * var(--u)); height: calc(42 * var(--u));
                padding: 0 calc(18 * var(--u)); white-space: nowrap;
                border-radius: 999px; font: 500 calc(16 * var(--u)) / calc(42 * var(--u)) "Instrument Sans", Inter, system-ui, sans-serif;
                color: var(--s-link); }
  .sx-link.on { width: calc(80 * var(--u)); }
  .sx-link.on { background: var(--s-pill); color: var(--s-pill-ink); }

  .sx-right   { position: absolute; right: calc(61 * var(--u)); top: calc(25 * var(--u)); margin: 0;
                gap: calc(15 * var(--u)); }
  .sx-search  { display: block; width: calc(22 * var(--u)); height: calc(22 * var(--u)); margin-right: calc(6 * var(--u)); color: var(--s-ink); }
  .sx-login   { display: flex; align-items: center; justify-content: center;
                width: calc(121 * var(--u)); height: calc(59 * var(--u)); border-radius: 999px;
                border: 1px solid var(--s-line); background: var(--s-btn); color: var(--s-ink);
                font: 600 calc(17.1 * var(--u)) / 1 "Instrument Sans", Inter, system-ui, sans-serif; }
  .sx-cta     { justify-content: center; width: calc(200 * var(--u)); height: calc(57 * var(--u)); padding: 0;
                gap: calc(15 * var(--u)); font-size: calc(17.6 * var(--u)); }

  .sx-h1      { position: absolute; margin: 0; left: calc(81 * var(--u)); top: calc(196 * var(--u));
                font-size: calc(90 * var(--u)); line-height: calc(89.5 * var(--u)); letter-spacing: 0;
                -webkit-text-stroke: calc(1.4 * var(--u)) currentColor; }
  .sx-btns    { position: absolute; margin: 0; left: calc(86 * var(--u)); top: calc(509 * var(--u)); gap: calc(23 * var(--u)); flex-wrap: nowrap; }
  .sx-btn1    { width: calc(278 * var(--u)); height: calc(73 * var(--u)); padding: 0; gap: calc(18 * var(--u));
                border-radius: calc(16 * var(--u)); font-size: calc(20.2 * var(--u)); }
  .sx-btn2    { width: calc(273 * var(--u)); height: calc(73 * var(--u)); padding: 0 0 0 calc(32 * var(--u));
                justify-content: flex-start; gap: calc(22 * var(--u));
                border-radius: calc(16 * var(--u)); font-size: calc(18.6 * var(--u)); }
  .sx-play    { width: calc(33 * var(--u)); height: calc(33 * var(--u)); }
  .sx-sub     { position: absolute; margin: 0; left: calc(88 * var(--u)); top: calc(598 * var(--u));
                width: calc(510 * var(--u)); font-size: calc(24.2 * var(--u)); line-height: calc(33 * var(--u)); }

  /* light/dark switch, between search and Get Started */
  .sx-theme   { width: calc(42 * var(--u)); height: calc(42 * var(--u)); }
  .sx-theme svg { width: calc(20 * var(--u)); height: calc(20 * var(--u)); }

  .sx-art     { position: absolute; margin: 0; left: calc(660 * var(--u)); top: calc(100 * var(--u));
                width: calc(924 * var(--u)); height: calc(670 * var(--u)); }
  :root:not(.dark) .sx-art {
    /* feather every edge so the art melts into the ivory page, as in the comp */
    -webkit-mask-image: linear-gradient(90deg, transparent, #000 5%, #000 97%, transparent),
                        linear-gradient(180deg, transparent, #000 6%, #000 94%, transparent);
    -webkit-mask-composite: source-in;
            mask-image: linear-gradient(90deg, transparent, #000 5%, #000 97%, transparent),
                        linear-gradient(180deg, transparent, #000 6%, #000 94%, transparent);
            mask-composite: intersect;
  }
  /* On the dark page the panel's edge would sit hard against the end of
     "Opportunities." and against the viewport's right edge. The art has only
     empty ivory in those margins, so trim them and round what remains. */
  .dark .sx-art { border-radius: 0; clip-path: inset(0 calc(16 * var(--u)) 0 calc(22 * var(--u)) round calc(28 * var(--u))); }

  .sx-cards   { position: absolute; margin: 0; left: calc(61 * var(--u)); top: calc(789 * var(--u));
                width: calc(1464 * var(--u)); grid-template-columns: 481fr 464fr 481fr; gap: calc(19 * var(--u)); }
  .sx-card    { height: calc(140 * var(--u)); padding: 0 calc(28.5 * var(--u)) 0 calc(27 * var(--u));
                gap: calc(26 * var(--u)); border-radius: calc(18 * var(--u)); }
  .sx-card img { width: calc(90 * var(--u)); height: calc(90 * var(--u)); }
  .sx-card > span { padding-top: calc(14 * var(--u)); }
  .sx-card .sx-arrow { width: calc(24 * var(--u)) !important; height: calc(24 * var(--u)) !important; }
  .sx-card-t  { font-size: calc(21.2 * var(--u)); font-weight: 700; }
  .sx-card-b  { margin-top: calc(10 * var(--u)); font-size: calc(17.5 * var(--u)); }
}
`

// `x` is where each link's box starts in the comp, in u. The comp's links
// are not evenly spaced, so they are placed individually rather than by gap.
const NAV = [
  { label: 'Home', href: '#top', active: true, x: 414 },
  { label: 'Jobs', href: '/app/jobs', x: 509, route: true },
  { label: 'Resume Tools', href: '/app/resume', x: 583, route: true },
  { label: 'Career Resources', href: '/app/improvements', x: 723, route: true },
  { label: 'How It Works', href: '/how-it-works', x: 893, route: true },
]

const CARDS = [
  { title: 'AI Job Matching', body: 'Find the roles that fit your skills.', icon: iconMatching, bg: 'var(--s-card1)' },
  { title: 'Skill Gap Analysis', body: 'Know what to learn next.', icon: iconGap, bg: 'var(--s-card2)' },
  { title: 'Personalized Suggestions', body: 'Get tailored career guidance.', icon: iconSuggest, bg: 'var(--s-card3)' },
]

function Arrow({ size = '1em' }) {
  return (
    <svg className="sx-arrow" style={{ width: size, height: size }} viewBox="0 0 20 20" fill="none"
      stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3.5 10h12.5M11 4.8l5.2 5.2-5.2 5.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ThemeToggle({ isDark, onToggle, className }) {
  return (
    <button
      onClick={onToggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={isDark}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`sx-theme ${className}`}
    >
      {isDark ? (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"
            strokeLinecap="round" />
        </svg>
      ) : (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.8 8.8 0 1 0 11.1 11.1Z" />
        </svg>
      )}
    </button>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const { theme, toggleTheme, ready } = useApp()
  const isDark = theme === 'dark'

  // Straight into the SkillSync dashboard; it asks for a resume if none is picked.
  const start = () => navigate('/app')

  return (
    <div className="sync">
      <style>{STYLES}</style>
      <span id="top" />

      <div className="sx-frame">
        {/* ---------------------------------------------------------- header */}
        <header className="sx-header">
          <a href="#top" className="sx-logo">
            <img src={logoMark} alt="" />
            <span className="sx-word">SkillSync</span>
          </a>

          <nav className="sx-links" aria-label="Primary">
            {NAV.map((item) => (
              item.route ? (
                <Link key={item.label} to={item.href} className="sx-link" style={{ '--x': item.x }}>
                  {item.label}
                </Link>
              ) : (
                <a
                  key={item.label}
                  href={item.href}
                  className={`sx-link${item.active ? ' on' : ''}`}
                  style={{ '--x': item.x }}
                >
                  {item.label}
                </a>
              )
            ))}
          </nav>

          <div className="sx-right">
            <svg className="sx-search" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="7.2" />
              <path d="M16 16l5.5 5.5" strokeLinecap="round" />
            </svg>
            <ThemeToggle isDark={isDark} onToggle={toggleTheme} className="sx-theme-head" />
            <button onClick={start} className="sx-cta sx-green">
              {ready ? 'Open dashboard' : 'Get Started'}
              <Arrow size="1.24em" />
            </button>
          </div>
        </header>

        {/* ------------------------------------------------------------ hero */}
        <h1 className="sx-h1">
          {/* the comp sets this line tighter than DM Serif's default spacing;
              the other two lines already match it untouched */}
          <span style={{ letterSpacing: '-0.012em' }}>Your Skills.</span>
          <br />
          The Right
          <br />
          <span className="g">Opportunities.</span>
        </h1>

        <div className="sx-btns">
          <button onClick={start} className="sx-btn1 sx-green">
            {ready ? 'Open dashboard' : 'Get Started'}
            <Arrow size="1.15em" />
          </button>
          <Link to="/how-it-works" className="sx-btn2">
            <span className="sx-play">
              <svg width="46%" height="46%" viewBox="0 0 12 12" fill="var(--s-page)" aria-hidden="true">
                <path d="M3 1.6v8.8L10.2 6Z" />
              </svg>
            </span>
            See How It Works
          </Link>
        </div>

        <p className="sx-sub">Connect your skills with opportunities that move your career forward.</p>

        <img
          className="sx-art"
          src={heroArt}
          alt="A woman working on a laptop, surrounded by cards showing her resume skills, job matches, AI matching, skill insights and better opportunities"
          width="924"
          height="670"
        />

        {/* ------------------------------------------------------ feature cards */}
        <div className="sx-cards">
          {CARDS.map((card) => (
            <button key={card.title} onClick={start} className="sx-card" style={{ background: card.bg }}>
              <img src={card.icon} alt="" />
              <span>
                <span className="sx-card-t">{card.title}</span>
                <span className="sx-card-b">{card.body}</span>
              </span>
              <Arrow size="1.15em" />
            </button>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------ how it works */}
      <HowItWorksContent embedded id="how" />

      <footer className="px-5 py-10" style={{ borderTop: '1px solid var(--s-line)' }}>
        <p className="text-center text-[12.5px]" style={{ color: 'var(--s-sub)' }}>
          SkillSync · A retrieval-augmented generation project built with FastAPI and React.
        </p>
      </footer>

    </div>
  )
}
