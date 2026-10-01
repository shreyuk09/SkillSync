/**
 * The GitHub Pages build has no backend. It is made with VITE_STATIC=1 and
 * reads pre-computed results instead (see backend/scripts/export_static.py).
 * In normal development this is false and nothing below changes behaviour.
 */
export const STATIC = import.meta.env.VITE_STATIC === '1'

export const REPO_URL = 'https://github.com/shreyuk09/SkillSync'

export const STATIC_NOTICE =
  'This is the online demo, which runs without a server. Uploading your own resume or job description and the AI Career Assistant work in the full app — see the README on GitHub to run it locally.'
