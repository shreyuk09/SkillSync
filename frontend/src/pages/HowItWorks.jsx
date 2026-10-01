import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import backdrop from '../assets/hiw-bg.webp'
import backdropDark from '../assets/hiw-bg-dark.webp'
import logoMark from '../assets/hiw-logo.webp'
import card1 from '../assets/hiw-card1.webp'
import card2 from '../assets/hiw-card2.webp'
import card3 from '../assets/hiw-card3.webp'
import card4 from '../assets/hiw-card4.webp'
import card1Dark from '../assets/hiw-card1-dark.webp'
import card2Dark from '../assets/hiw-card2-dark.webp'
import card3Dark from '../assets/hiw-card3-dark.webp'
import card4Dark from '../assets/hiw-card4-dark.webp'
import ben1 from '../assets/hiw-ben1.webp'
import ben2 from '../assets/hiw-ben2.webp'
import ben3 from '../assets/hiw-ben3.webp'
import ben4 from '../assets/hiw-ben4.webp'

/**
 * "How It Works", built to match the supplied design comp.
 *
 * On desktop the comp itself is the backdrop -- its illustrations, hand-drawn
 * notes, leaves and hills exactly as drawn -- with every piece of text removed
 * from it, and real text set back on top at the positions measured off the
 * comp. That keeps the artwork pixel-exact while the words stay selectable,
 * translatable and readable by screen readers.
 *
 * Geometry is in `u`: 1px at 1536px wide (the comp's width), scaling in
 * proportion up to 1920px. Below 1024px the page drops to a stacked layout
 * built from crops of the same artwork.
 *
 * Dark mode swaps in a dark rendering of the same artwork, built from the
 * comp: plain paper tones (background, card fills, the benefits bar, the
 * handwriting) are inverted, while the illustrations, badges and icons are kept
 * exactly as drawn and sit on the darkened cards.
 */
const u = (n) => `calc(${n} * var(--u))`

const STYLES = `
.hiw {
  --u: min(1.25px, calc(100vw / 1536));
  --hw-ink: #020713;
  --hw-green: #055439;
  --hw-sub: #5b646e;
  --hw-nav: #525c64;
  --hw-nav-on: #0a4e2b;
  --hw-label: #104832;
  --hw-bd: #56606a;
  --hw-ctl-bg: #ffffff;
  --hw-ctl-line: #e8e1d3;
  background: #fcf9f4;
  color: var(--hw-ink);
  min-height: 100vh;
  font-family: "Instrument Sans", Inter, system-ui, sans-serif;
  overflow-x: clip;
}
.hiw .serif { font-family: "DM Serif Display", Georgia, serif; font-weight: 400; }
.dark .hiw {
  /* ink for the dark rendering of the artwork */
  --hw-ink: #f5f2eb;
  --hw-green: #74c191;
  --hw-sub: #b9b4a9;
  --hw-nav: #b3afa5;
  --hw-nav-on: #7cc496;
  --hw-label: #7cc496;
  --hw-bd: #b3afa5;
  --hw-ctl-bg: #24221d;
  --hw-ctl-line: #3a3730;
  background: #1d1a16;
  color-scheme: dark;
}
.hw-desc    { color: var(--desc-ink); }
.dark .hw-desc { color: #bcb7ac; }
.hw-step    { background: var(--fill); }
.dark .hw-step { background: var(--fill-dark); }
.hw-search  { display: none; }
.hw-theme   { display: flex; align-items: center; justify-content: center; flex-shrink: 0; border-radius: 999px;
              width: 40px; height: 40px; background: var(--hw-ctl-bg); color: var(--hw-ink);
              border: 1px solid var(--hw-ctl-line); }
.hw-theme svg { width: 19px; height: 19px; }

/* ------------------------------------------------------------ phone first */
.hw-frame   { padding: 16px 20px 48px; }
.hw-header  { display: flex; align-items: center; gap: 10px; }
.hw-header .hw-theme { margin-left: auto; }
.hw-logo    { display: flex; align-items: center; gap: 9px; }
.hw-logo img { width: 36px; height: 36px; }
.hw-word    { font-weight: 700; font-size: 23px; letter-spacing: -0.02em; line-height: 1; }
.hw-nav, .hw-login { display: none; }
.hw-cta     { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
              border-radius: 999px; padding: 11px 16px; background: linear-gradient(180deg, #0f6a40, #065530);
              color: #fcfffd; font-weight: 600; font-size: 15px; line-height: 1; }
.hw-cta svg { width: 14px; height: 14px; }
.dark .hw-label { background: #1d2a22; }
.hw-label   { margin: 34px auto 0; width: max-content; border-radius: 999px; background: #eef4ea;
              padding: 7px 16px; color: var(--hw-label); font-weight: 600; font-size: 12px; letter-spacing: 0.2em; }
.hw-title   { margin-top: 14px; text-align: center; color: var(--hw-ink); font-size: min(34px, 9.2vw); line-height: 1.08; -webkit-text-stroke: 0.5px currentColor; }
.hw-title .hw-ln { display: block; }
.hw-title .hw-ln + .hw-ln::before { content: none; }
.hw-title .g { color: var(--hw-green); }
.hw-sub     { margin-top: 14px; text-align: center; color: var(--hw-sub); font-size: 16px; line-height: 1.45; }
.hw-steps   { margin-top: 28px; display: grid; gap: 14px; }
.hw-step    { position: relative; overflow: hidden; border-radius: 22px; padding: 20px 20px 0; }
.hw-badge   { display: flex; align-items: center; justify-content: center; width: 46px; height: 46px;
              border-radius: 999px; font-weight: 600; font-size: 19px; line-height: 1; }
.hw-head    { margin-top: 14px; font-size: 24px; line-height: 1.15; color: var(--hw-ink); }
.hw-desc    { margin-top: 6px; font-size: 16px; line-height: 1.35; }
.hw-illo    { display: block; width: calc(100% + 40px); max-width: none; margin: 10px -20px 0; height: auto; }
.hw-benefits { margin-top: 18px; display: grid; gap: 4px; border-radius: 22px; background: #fefefd;
              --bar-dark: #242424;
              padding: 10px 14px; box-shadow: 0 10px 30px -18px rgb(20 35 59 / .35); }
.hw-benefit { display: flex; align-items: center; gap: 14px; padding: 8px 0; }
.hw-benefit img { width: 56px; height: 56px; flex-shrink: 0; border-radius: 999px; }
.dark .hw-benefits { background: var(--bar-dark); }
.hw-bt      { display: block; font-size: 17px; line-height: 1.2; color: var(--hw-ink); }
.hw-bd      { display: block; margin-top: 3px; font-size: 14px; line-height: 1.3; color: var(--hw-bd); }
.hw-ln + .hw-ln::before { content: ' '; }

/* Embedded in another page (the home page): no header of its own. */
.hiw.hw-embedded { min-height: 0; }
.hw-embedded .hw-frame { padding-top: 0; }

/* ----------------------------------------------------- desktop: the comp */
@media (min-width: 1024px) {
  /* the artwork's top 90u is its navbar; embedded, that strip is clipped away */
  .hiw.hw-embedded { overflow: hidden; }
  .hw-embedded .hw-frame { margin-top: ${u(-90)}; padding-top: 0; }
  .hw-frame   { position: relative; width: ${u(1536)}; height: ${u(1024)}; margin: 0 auto; padding: 0;
                background: url(${backdrop}) 0 0 / 100% 100% no-repeat; }
  .dark .hw-frame { background-image: url(${backdropDark}); }
  /* everything below is placed absolutely at its measured position */
  .hw-frame * { box-sizing: border-box; }
  .hw-ln      { display: block; }
  .hw-ln + .hw-ln::before { content: none; }
  /* the artwork carries these on desktop */
  .hw-logo img, .hw-illo, .hw-benefit img { display: none; }

  .hw-header  { display: block; }
  .hw-logo    { position: absolute; left: ${u(80)}; top: ${u(20)}; width: ${u(215)}; height: ${u(56)}; }
  .hw-word    { position: absolute; left: ${u(153.2 - 80)}; top: ${u(31.5 - 20)}; font-size: ${u(31.3)}; letter-spacing: 0; }

  .hw-nav     { display: block; }
  .hw-link    { position: absolute; top: ${u(39.2)}; font-size: ${u(14.6)}; line-height: 1; font-weight: 500;
                color: var(--hw-nav); padding: ${u(10)} ${u(12)}; margin: ${u(-10)} ${u(-12)}; border-radius: 999px; }
  .hw-link:hover { color: var(--hw-nav-on); }
  .hw-link[aria-current="page"] { color: var(--hw-nav-on); }

  .hw-login, .hw-cta { position: absolute; display: flex; align-items: center; justify-content: center;
                border-radius: 999px; padding: 0; margin: 0; background: transparent; }
  .hw-login   { left: ${u(1154)}; top: ${u(23)}; width: ${u(111)}; height: ${u(48)};
                color: var(--hw-ink); font-weight: 600; font-size: ${u(15.5)}; line-height: 1; }
  .hw-cta     { left: ${u(1285)}; top: ${u(23)}; width: ${u(174)}; height: ${u(48)};
                gap: ${u(11)}; font-size: ${u(15.5)}; }
  .hw-login:hover { background: rgb(128 128 128 / .08); }
  /* search and the light/dark switch, between the nav and Get Started. The comp's
     painted search icon was removed from the artwork so the two could be spaced */
  .hw-search  { display: block; position: absolute; left: ${u(1194)}; top: ${u(36)}; width: ${u(22)}; height: ${u(22)};
                color: var(--hw-ink); }
  .hw-header .hw-theme { position: absolute; left: ${u(1235)}; top: ${u(27.5)}; margin: 0;
                width: ${u(38)}; height: ${u(38)}; }
  .hw-header .hw-theme svg { width: ${u(18)}; height: ${u(18)}; }
  .hw-cta:hover   { background: rgb(255 255 255 / .08); }
  .hw-cta svg { width: ${u(14)}; height: ${u(14)}; }

  .hw-label   { position: absolute; left: 0; top: ${u(112.2)}; width: ${u(1536)}; margin: 0; padding: 0 0 0 ${u(3.6)};
                background: none; text-align: center; font-size: ${u(13.89)}; letter-spacing: ${u(1.8)}; line-height: 1; }
  .hw-title   { position: absolute; left: ${u(2)}; top: ${u(144.6)}; width: ${u(1536)}; margin: 0;
                font-size: ${u(57)}; line-height: ${u(56)}; -webkit-text-stroke: ${u(0.9)} currentColor; }
  .hw-sub     { position: absolute; left: ${u(2)}; top: ${u(278.6)}; width: ${u(1536)}; margin: 0;
                font-size: ${u(17)}; line-height: ${u(24)}; }

  .hw-steps   { display: block; margin: 0; }
  .hw-step    { position: static; overflow: visible; border-radius: 0; padding: 0; background: none !important; }
  .hw-badge   { position: absolute; top: ${u(392.3)}; width: ${u(60)}; height: auto; margin-left: ${u(-30)};
                background: none !important; border-radius: 0; font-size: ${u(21)}; }
  .hw-head    { position: absolute; top: ${u(438.3)}; margin: 0; font-size: ${u(23.7)}; line-height: 1; white-space: nowrap;
                -webkit-text-stroke: ${u(0.2)} currentColor; }
  .hw-desc    { position: absolute; top: ${u(471.5)}; margin: 0; font-size: ${u(16.4)}; line-height: ${u(21)}; white-space: nowrap; }

  .hw-benefits { display: block; margin: 0; padding: 0; background: none; box-shadow: none; border-radius: 0; }
  .hw-benefit { display: block; padding: 0; }
  .hw-bt      { position: absolute; top: ${u(800.3)}; margin: 0; font-size: ${u(16.3)}; line-height: 1; white-space: nowrap;
                -webkit-text-stroke: ${u(0.24)} currentColor; }
  .hw-bd      { position: absolute; top: ${u(825)}; margin: 0; font-size: ${u(14)}; line-height: 1; white-space: nowrap; }
}
`

// `x`: where each link's text starts in the comp.
const NAV = [
  { label: 'Home', to: '/', x: 424.9 },
  { label: 'Jobs', to: '/app/jobs', x: 501.8 },
  { label: 'Resume Tools', to: '/app/resume', x: 568.9 },
  { label: 'Career Resources', to: '/app/improvements', x: 694.4 },
  { label: 'How It Works', to: '/how-it-works', x: 847.9, current: true },
]

// Per step: text colours sampled from the comp, the badge's centre and the
// text's left edge in the comp, and the phone layout's fill and illustration.
const STEPS = [
  { n: '01', head: 'Upload Resume', desc: ['Share your resume and let us', 'understand your background.'],
    badgeInk: '#022b1d', badgeFill: '#ceeacf', descInk: '#525e64', fill: '#f0f8ec', illo: card1, illoDark: card1Dark, fillDark: '#1c2718',
    badgeX: 149, textX: 127.4, alt: 'A resume document with an upload arrow' },
  { n: '02', head: 'AI Analysis', desc: ['Our AI analyzes your skills,', 'experience, and interests.'],
    badgeInk: '#03063a', badgeFill: '#d9cdfc', descInk: '#50586b', fill: '#f4effe', illo: card2, illoDark: card2Dark, fillDark: '#282535',
    badgeX: 498, textX: 476, alt: 'A friendly robot examining charts with a magnifying glass' },
  { n: '03', head: 'Job Matching', desc: ['We find the most relevant', 'opportunities for you.'],
    badgeInk: '#853b05', badgeFill: '#fedcb6', descInk: '#565f66', fill: '#fef4ea', illo: card3, illoDark: card3Dark, fillDark: '#2c2217',
    badgeX: 846, textX: 823.5, alt: 'Job matches: Software Engineer 95%, Frontend Developer 89%, Full Stack Developer 82%' },
  // the comp sets this card's second line a touch tighter than the others
  { n: '04', head: 'Get Personalized Insights', desc: ['Receive skill gap analysis,', 'recommendations, and career guidance.'],
    tightLine: 1,
    badgeInk: '#001249', badgeFill: '#badefd', descInk: '#4c5b6b', fill: '#ebf5fe', illo: card4, illoDark: card4Dark, fillDark: '#172830',
    badgeX: 1203, textX: 1181, alt: 'A rising career chart with skills to improve, a learning path and career guidance' },
]

const BENEFITS = [
  { title: 'Better Job Matches', body: 'Find roles that fit your skills.', icon: ben1, x: 226.6, bodyX: 226.8 },
  { title: 'Clear Skill Insights', body: 'Know what to learn next.', icon: ben2, x: 574.7, bodyX: 574.8 },
  { title: 'Personalized Guidance', body: 'Get tailored career advice.', icon: ben3, x: 893.6, bodyX: 894.3 },
  { title: 'Faster Career Growth', body: 'Move closer to your goals.', icon: ben4, x: 1230.6, bodyX: 1230.8 },
]

/**
 * The "How It Works" screen's content. Rendered as a page it brings the
 * comp's own header; `embedded` drops that header, clips the artwork's navbar
 * strip, and steps the headings down a level so a host page's own h1 stays
 * the only one.
 */
export function HowItWorksContent({ header = null, embedded = false, id }) {
  const { theme } = useApp()
  const isDark = theme === 'dark'
  const Wrap = embedded ? 'section' : 'main'
  const Title = embedded ? 'h2' : 'h1'
  const StepHead = embedded ? 'h3' : 'h2'

  return (
    <div className={`hiw${embedded ? ' hw-embedded' : ''}`} id={id}>
      <style>{STYLES}</style>

      <div className="hw-frame">
        {header}

        <Wrap aria-labelledby={embedded ? 'hw-title' : undefined}>
          {/* ------------------------------------------------------- heading */}
          <p className="hw-label">HOW IT WORKS</p>
          <Title className="hw-title serif" id="hw-title">
            <span className="hw-ln">From Your Resume to</span>
            <span className="hw-ln g">Real Opportunities</span>
          </Title>
          <p className="hw-sub">
            <span className="hw-ln">A simple 4-step process that uses AI to understand your skills, analyze your</span>
            <span className="hw-ln">profile, and find the best opportunities for you.</span>
          </p>

          {/* --------------------------------------------------- the 4 steps */}
          <ol className="hw-steps">
            {STEPS.map((step) => (
              <li key={step.n} className="hw-step" style={{ '--fill': step.fill, '--fill-dark': step.fillDark }}>
                <span
                  className="hw-badge"
                  style={{ left: u(step.badgeX), color: step.badgeInk, background: step.badgeFill }}
                  aria-hidden="true"
                >
                  {step.n}
                </span>
                <StepHead className="hw-head serif" style={{ left: u(step.textX) }}>
                  <span className="sr-only">Step {Number(step.n)}: </span>
                  {step.head}
                </StepHead>
                <p className="hw-desc" style={{ left: u(step.textX), '--desc-ink': step.descInk }}>
                  {step.desc.map((line, i) => (
                    <span
                      key={line}
                      className="hw-ln"
                      style={i === step.tightLine ? { letterSpacing: '-0.03em' } : undefined}
                    >
                      {line}
                    </span>
                  ))}
                </p>
                <img className="hw-illo" src={isDark ? step.illoDark : step.illo} alt={step.alt} />
              </li>
            ))}
          </ol>

          {/* ------------------------------------------------------ benefits */}
          <ul className="hw-benefits">
            {BENEFITS.map((item) => (
              <li key={item.title} className="hw-benefit">
                <img src={item.icon} alt="" />
                <span>
                  <strong className="hw-bt serif" style={{ left: u(item.x) }}>{item.title}</strong>
                  <span className="hw-bd" style={{ left: u(item.bodyX) }}>{item.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </Wrap>
      </div>
    </div>
  )
}

export default function HowItWorks() {
  const navigate = useNavigate()
  const { theme, toggleTheme } = useApp()
  const isDark = theme === 'dark'

  // Straight into the SkillSync dashboard; it asks for a resume if none is picked.
  const start = () => navigate('/app')

  return (
    <HowItWorksContent
      header={
        <header className="hw-header">
          <Link to="/" className="hw-logo" aria-label="SkillSync home">
            <img src={logoMark} alt="" />
            <span className="hw-word">SkillSync</span>
          </Link>

          <nav className="hw-nav" aria-label="Primary">
            {NAV.map((item) => (
              <Link
                key={item.label}
                to={item.to}
                className="hw-link"
                style={{ left: u(item.x) }}
                aria-current={item.current ? 'page' : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <svg className="hw-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
            aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="7.2" />
            <path d="M16 16l5.5 5.5" strokeLinecap="round" />
          </svg>
          <button
            onClick={toggleTheme}
            className="hw-theme"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-pressed={isDark}
            title={isDark ? 'Light mode' : 'Dark mode'}
          >
            {isDark ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="4.2" />
                <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"
                  strokeLinecap="round" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.8 8.8 0 1 0 11.1 11.1Z" />
              </svg>
            )}
          </button>
          <button onClick={start} className="hw-cta">
            Get Started
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"
              style={{ flexShrink: 0 }}>
              <path d="M1.5 7h10.5M7.8 2.8L12 7l-4.2 4.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </header>
      }
    />
  )
}
