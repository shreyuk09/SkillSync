import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../context/AppContext'

/**
 * Fetch one analysis endpoint, with loading / error / refresh handled once.
 *
 * Analysis calls can take several seconds (they run retrieval and then a
 * Claude call), so every page that uses this gets a proper loading state
 * rather than a frozen screen.
 *
 * Identical in-flight requests are shared rather than duplicated. Two things
 * would otherwise fire the same expensive call twice: React StrictMode
 * double-invokes effects in development, and separate pages legitimately want
 * the same report (Dashboard and MatchAnalysis both read `match`). Each
 * duplicate costs a full LLM round-trip, and on a rate-limited key that is the
 * difference between one call and two against a per-minute token budget.
 *
 * The entry is dropped as soon as the request settles, so this only collapses
 * concurrent callers -- it is not a result cache. The backend already caches
 * analysis per session, which makes the later calls cheap anyway.
 */
const inFlight = new Map()

function shared(fetcher, key, sessionId, refresh) {
  // A refresh must always reach the server -- never join an in-flight read.
  if (refresh) return fetcher(sessionId, true)

  let byKey = inFlight.get(fetcher)
  if (!byKey) {
    byKey = new Map()
    inFlight.set(fetcher, byKey)
  }

  const pending = byKey.get(key)
  if (pending) return pending

  const promise = fetcher(sessionId, false).finally(() => {
    byKey.delete(key)
    if (byKey.size === 0) inFlight.delete(fetcher)
  })
  byKey.set(key, promise)
  return promise
}
export function useAnalysis(fetcher, { auto = true, deps = [] } = {}) {
  const { sessionId, ready, analysisVersion } = useApp()
  // Requests from before a document swap must never satisfy one from after it,
  // so the version is part of the key as well as of the dependencies.
  const key = `${sessionId}::${analysisVersion}`
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(
    async (refresh = false) => {
      if (!sessionId) return
      setLoading(true)
      setError(null)
      try {
        const result = await shared(fetcher, key, sessionId, refresh)
        if (mounted.current) setData(result)
      } catch (caught) {
        if (mounted.current) setError(caught)
      } finally {
        if (mounted.current) setLoading(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, key, ...deps]
  )

  // Drop the previous run's data the moment the documents change, so a stale
  // report is never left on screen while the new one is still being written.
  useEffect(() => {
    setData(null)
    setError(null)
  }, [key])

  useEffect(() => {
    if (auto && sessionId && ready) run(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, key, ready, auto, ...deps])

  return { data, loading, error, run, refresh: () => run(true) }
}
