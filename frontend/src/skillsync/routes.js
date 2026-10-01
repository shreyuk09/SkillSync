/** Lazy page loaders. Shared by the router and by hover-prefetch in the nav. */
export const loaders = {
  dashboard: () => import('./pages/Dashboard'),
  resume: () => import('./pages/MyResume'),
  analysis: () => import('./pages/ResumeAnalysis'),
  jobs: () => import('./pages/JobMatches'),
  job: () => import('./pages/JobDetail'),
  skills: () => import('./pages/SkillAnalysis'),
  improvements: () => import('./pages/Improvements'),
  assistant: () => import('./pages/Assistant'),
  saved: () => import('./pages/SavedJobs'),
  settings: () => import('./pages/Settings'),
}
