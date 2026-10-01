/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Surfaces and ink are driven by CSS custom properties (see index.css)
        // so light and dark are two selected palettes, not one auto-inverted.
        canvas: 'rgb(var(--canvas) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        raised: 'rgb(var(--raised) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        subtle: 'rgb(var(--subtle) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        brand: 'rgb(var(--brand) / <alpha-value>)',
        'brand-soft': 'rgb(var(--brand-soft) / <alpha-value>)',
        good: 'rgb(var(--good) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        serious: 'rgb(var(--serious) / <alpha-value>)',
        critical: 'rgb(var(--critical) / <alpha-value>)',
        // SkillSync dashboard palette (tokens in src/skillsync/ss.css)
        ss: {
          'page': 'rgb(var(--ss-page) / <alpha-value>)',
          'side': 'rgb(var(--ss-side) / <alpha-value>)',
          'card': 'rgb(var(--ss-card) / <alpha-value>)',
          'soft': 'rgb(var(--ss-soft) / <alpha-value>)',
          'ink': 'rgb(var(--ss-ink) / <alpha-value>)',
          'sub': 'rgb(var(--ss-sub) / <alpha-value>)',
          'mute': 'rgb(var(--ss-mute) / <alpha-value>)',
          'line': 'rgb(var(--ss-line) / <alpha-value>)',
          'green': 'rgb(var(--ss-green) / <alpha-value>)',
          'green2': 'rgb(var(--ss-green2) / <alpha-value>)',
          'on-green': 'rgb(var(--ss-on-green) / <alpha-value>)',
          'pill': 'rgb(var(--ss-pill) / <alpha-value>)',
          'pill-ink': 'rgb(var(--ss-pill-ink) / <alpha-value>)',
          'g-bg': 'rgb(var(--ss-g-bg) / <alpha-value>)',
          'g-ink': 'rgb(var(--ss-g-ink) / <alpha-value>)',
          'a-bg': 'rgb(var(--ss-a-bg) / <alpha-value>)',
          'a-ink': 'rgb(var(--ss-a-ink) / <alpha-value>)',
          'r-bg': 'rgb(var(--ss-r-bg) / <alpha-value>)',
          'r-ink': 'rgb(var(--ss-r-ink) / <alpha-value>)',
          'b-bg': 'rgb(var(--ss-b-bg) / <alpha-value>)',
          'b-ink': 'rgb(var(--ss-b-ink) / <alpha-value>)',
          'p-bg': 'rgb(var(--ss-p-bg) / <alpha-value>)',
          'p-ink': 'rgb(var(--ss-p-ink) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        ss: ['"Instrument Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        // Display serif for landing headlines. DM Serif Display is loaded in
        // index.html; the system serifs behind it only show if that fails.
        display: ['"DM Serif Display"', 'Iowan Old Style', 'Palatino', 'Georgia', 'serif'],
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
      },
      boxShadow: {
        card: '0 1px 2px rgb(0 0 0 / 0.04), 0 8px 24px -12px rgb(0 0 0 / 0.12)',
        lift: '0 2px 4px rgb(0 0 0 / 0.06), 0 20px 40px -20px rgb(0 0 0 / 0.24)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(12px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-in': 'slide-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
    },
  },
  plugins: [],
}
