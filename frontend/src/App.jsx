import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useApp } from './context/AppContext'
import { ToastStack } from './components/ui'

import Landing from './pages/Landing'
import { loaders } from './skillsync/routes'

// Everything except the landing page is split into its own chunk, so the
// homepage paints without downloading the dashboard.
const HowItWorks = lazy(() => import('./pages/HowItWorks'))
const SkillSyncLayout = lazy(() => import('./skillsync/Layout'))
const P = Object.fromEntries(Object.entries(loaders).map(([k, load]) => [k, lazy(load)]))

// The earlier single-session analyzer stays available at its old URLs.
const AppLayout = lazy(() => import('./layouts/AppLayout').then((m) => ({ default: m.AppLayout })))
const Upload = lazy(() => import('./pages/Upload'))
const LegacyDashboard = lazy(() => import('./pages/Dashboard'))
const ResumePage = lazy(() => import('./pages/ResumePage'))
const JobPage = lazy(() => import('./pages/JobPage'))
const MatchAnalysis = lazy(() => import('./pages/MatchAnalysis'))
const LegacyAssistant = lazy(() => import('./pages/Assistant'))
const LegacyImprovements = lazy(() => import('./pages/Improvements'))
const InterviewPrep = lazy(() => import('./pages/InterviewPrep'))
const Roadmap = lazy(() => import('./pages/Roadmap'))

function Blank() {
  return <div className="min-h-screen bg-[#fdfaf3] dark:bg-[#121210]" />
}

export default function App() {
  const { toasts, dismissToast } = useApp()

  return (
    <>
      <Suspense fallback={<Blank />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/how-it-works" element={<HowItWorks />} />

          <Route path="/app" element={<SkillSyncLayout />}>
            <Route index element={<P.dashboard />} />
            <Route path="resume" element={<P.resume />} />
            <Route path="analysis" element={<P.analysis />} />
            <Route path="jobs" element={<P.jobs />} />
            <Route path="jobs/:jobId" element={<P.job />} />
            <Route path="skills" element={<P.skills />} />
            <Route path="improvements" element={<P.improvements />} />
            <Route path="assistant" element={<P.assistant />} />
            <Route path="saved" element={<P.saved />} />
            <Route path="settings" element={<P.settings />} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Route>

          <Route element={<AppLayout />}>
            <Route path="/upload" element={<Upload />} />
            <Route path="/dashboard" element={<LegacyDashboard />} />
            <Route path="/resume" element={<ResumePage />} />
            <Route path="/job" element={<JobPage />} />
            <Route path="/match" element={<MatchAnalysis />} />
            <Route path="/assistant" element={<LegacyAssistant />} />
            <Route path="/improvements" element={<LegacyImprovements />} />
            <Route path="/interview" element={<InterviewPrep />} />
            <Route path="/roadmap" element={<Roadmap />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  )
}
