import { useCallback, useEffect, useState } from 'react'
import { cached, invalidate, peek } from './api'

/**
 * Fetch a cached API path. Renders cached data on the very first frame (no
 * skeleton flash when revisiting a page) and only shows loading otherwise.
 */
export function useQuery(path) {
  const [state, setState] = useState(() => ({ data: path ? peek(path) : undefined, error: null }))
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) {
      setState({ data: undefined, error: null })
      return
    }
    let alive = true
    const hit = peek(path)
    setState({ data: hit, error: null })
    if (!hit) {
      cached(path).then(
        (data) => alive && setState({ data, error: null }),
        (error) => alive && setState({ data: undefined, error })
      )
    }
    return () => {
      alive = false
    }
  }, [path, nonce])

  const retry = useCallback(() => {
    if (path) invalidate(path)
    setNonce((n) => n + 1)
  }, [path])

  return { data: state.data, error: state.error, loading: Boolean(path) && !state.data && !state.error, retry }
}

export function useDebounced(value, delay = 200) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}
