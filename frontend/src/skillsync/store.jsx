import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { invalidate } from './api'

/**
 * Which resume is selected, saved jobs and chat history.
 * Saved jobs and the selected resume persist per browser; chat lives for the
 * tab (sessionStorage) and is kept per resume.
 */
const Ctx = createContext(null)

const read = (store, key, fallback) => {
  try {
    const raw = store.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}
const write = (store, key, value) => {
  try {
    store.setItem(key, JSON.stringify(value))
  } catch {
    /* private mode / quota: the app still works, it just won't remember */
  }
}

export function SkillSyncProvider({ children }) {
  const [resumeId, setResumeIdState] = useState(() => read(localStorage, 'skillsync.resume', null))
  const [saved, setSaved] = useState(() => read(localStorage, 'skillsync.saved', []))
  const [chats, setChats] = useState(() => read(sessionStorage, 'skillsync.chats', {}))
  const [jdOpen, setJdOpen] = useState(false)

  useEffect(() => write(localStorage, 'skillsync.resume', resumeId), [resumeId])
  useEffect(() => write(localStorage, 'skillsync.saved', saved), [saved])
  useEffect(() => write(sessionStorage, 'skillsync.chats', chats), [chats])

  const setResumeId = useCallback((id) => {
    invalidate('/dashboard')
    setResumeIdState(id)
  }, [])

  const toggleSaved = useCallback((job) => {
    setSaved((list) =>
      list.some((j) => j.id === job.id)
        ? list.filter((j) => j.id !== job.id)
        : [{ id: job.id, title: job.title, company: job.company, location: job.location, work_type: job.work_type, role_title: job.role_title, saved_at: new Date().toISOString() }, ...list]
    )
  }, [])

  const setChat = useCallback((id, updater) => {
    setChats((all) => ({ ...all, [id]: typeof updater === 'function' ? updater(all[id] || []) : updater }))
  }, [])

  const value = useMemo(
    () => ({
      resumeId, setResumeId, saved, isSaved: (id) => saved.some((j) => j.id === id), toggleSaved, clearSaved: () => setSaved([]), chats, setChat,
      jdOpen, openJd: () => setJdOpen(true), closeJd: () => setJdOpen(false),
    }),
    [resumeId, setResumeId, saved, toggleSaved, chats, setChat, jdOpen]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useSkillSync = () => useContext(Ctx)
