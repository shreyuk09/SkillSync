import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../services/api'
import { STATIC } from '../staticMode'

const AppContext = createContext(null)
const SESSION_KEY = 'resumerag.session'

export function AppProvider({ children }) {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null)
  const [status, setStatus] = useState(null) // { has_resume, has_jd, ready, ... }
  // Bumped whenever the resume or job description is swapped. Every analysis
  // hook watches it, drops what it is holding and refetches -- which is what
  // keeps one run from ever showing alongside the documents of another.
  const [analysisVersion, setAnalysisVersion] = useState(0)
  const [health, setHealth] = useState(null)
  const [booting, setBooting] = useState(true)
  const [toasts, setToasts] = useState([])
  const [theme, setTheme] = useState(
    () => localStorage.getItem('theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  )
  const toastId = useRef(0)

  // -- theme ---------------------------------------------------------------
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  // -- toasts --------------------------------------------------------------
  const dismissToast = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const toast = useCallback(
    (message, { type = 'info', hint = '', duration = 5000 } = {}) => {
      const id = ++toastId.current
      setToasts((current) => [...current, { id, message, type, hint }])
      if (duration) setTimeout(() => dismissToast(id), duration)
      return id
    },
    [dismissToast]
  )

  const toastError = useCallback(
    (error) => {
      const message = error?.message || 'Something went wrong.'
      toast(message, { type: 'error', hint: error?.hint, duration: 8000 })
    },
    [toast]
  )

  // -- session -------------------------------------------------------------
  const refreshStatus = useCallback(async (id = sessionId) => {
    if (!id) return null
    try {
      const next = await api.getSession(id)
      setStatus(next)
      return next
    } catch (error) {
      if (error.status === 404) {
        // The session expired server-side; start clean rather than looping.
        localStorage.removeItem(SESSION_KEY)
        setSessionId(null)
        setStatus(null)
      }
      return null
    }
  }, [sessionId])

  const ensureSession = useCallback(async () => {
    if (sessionId) {
      const existing = await api.getSession(sessionId).catch(() => null)
      if (existing) {
        setStatus(existing)
        return sessionId
      }
    }
    const created = await api.createSession()
    localStorage.setItem(SESSION_KEY, created.session_id)
    setSessionId(created.session_id)
    setStatus(null)
    return created.session_id
  }, [sessionId])

  /**
   * Call after a document has been swapped.
   *
   * The server has already discarded the cached analysis for this session, so
   * the only thing left is to make every mounted page throw away its copy.
   */
  const documentsChanged = useCallback(async () => {
    setAnalysisVersion((version) => version + 1)
    return refreshStatus()
  }, [refreshStatus])

  const resetSession = useCallback(async () => {
    if (sessionId) await api.deleteSession(sessionId).catch(() => {})
    localStorage.removeItem(SESSION_KEY)
    setSessionId(null)
    setStatus(null)
  }, [sessionId])

  // -- boot ----------------------------------------------------------------
  useEffect(() => {
    if (STATIC) {
      setBooting(false)
      return undefined
    }
    let cancelled = false
    ;(async () => {
      try {
        const info = await api.getHealth()
        if (!cancelled) setHealth(info)
      } catch (error) {
        if (!cancelled) toastError(error)
      }
      if (sessionId) await refreshStatus(sessionId)
      if (!cancelled) setBooting(false)
    })()
    return () => {
      cancelled = true
    }
    // Boot once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value = useMemo(
    () => ({
      sessionId, status, health, booting, theme,
      toasts, toast, toastError, dismissToast,
      toggleTheme, ensureSession, refreshStatus, resetSession,
      analysisVersion, documentsChanged,
      ready: Boolean(status?.ready),
      hasResume: Boolean(status?.has_resume),
      hasJd: Boolean(status?.has_jd),
    }),
    [sessionId, status, health, booting, theme, toasts, toast, toastError,
     dismissToast, toggleTheme, ensureSession, refreshStatus, resetSession,
     analysisVersion, documentsChanged]
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp must be used inside <AppProvider>')
  return context
}
