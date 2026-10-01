/**
 * SkillSync API client with a small in-memory cache.
 *
 * Everything except chat is deterministic on the server, so a GET result is
 * reused until the selected resume changes or `invalidate()` is called.
 * Identical in-flight requests share one promise (StrictMode double effects,
 * two components asking for the same thing).
 */
import { ApiError } from '../services/api'

const cache = new Map() // url -> { data } | { promise }

async function request(path, { method = 'GET', body, form } = {}) {
  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: form || (body ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new ApiError({ code: 'network_error', message: "Couldn't reach the SkillSync server.", hint: 'Make sure the backend is running, then try again.', status: 0 })
  }
  const payload = await res.json().catch(() => null)
  if (!res.ok) {
    const e = payload?.error ?? {}
    throw new ApiError({ code: e.code ?? `http_${res.status}`, message: e.message ?? 'Something went wrong.', hint: e.hint, status: res.status })
  }
  return payload
}

export function cached(path) {
  const hit = cache.get(path)
  if (hit?.data) return Promise.resolve(hit.data)
  if (hit?.promise) return hit.promise
  const promise = request(path)
    .then((data) => {
      cache.set(path, { data })
      return data
    })
    .catch((err) => {
      cache.delete(path)
      throw err
    })
  cache.set(path, { promise })
  return promise
}

/** Synchronous peek so a page can render cached data on the first frame. */
export const peek = (path) => cache.get(path)?.data

/** Warm the cache without caring about the result (hover prefetch). */
export const prefetch = (path) => {
  if (path) cached(path).catch(() => {})
}

export const invalidate = (prefix = '') => {
  for (const key of cache.keys()) if (key.startsWith(prefix)) cache.delete(key)
}

export const paths = {
  resumes: () => '/resumes',
  resume: (id) => `/resumes/${id}`,
  jobs: () => '/jobs',
  job: (id, resumeId) => `/jobs/${id}${resumeId ? `?resume_id=${resumeId}` : ''}`,
  matches: (id) => `/matches/${id}`,
  analysis: (id) => `/analysis/${id}`,
  skills: (id, { role, jobId } = {}) =>
    `/skills/${id}${role ? `?role=${role}` : jobId ? `?job_id=${jobId}` : ''}`,
  improvements: (id) => `/improvements/${id}`,
  dashboard: (id) => `/dashboard/${id}`,
}

export function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/resume/upload', { method: 'POST', form })
}

export function uploadJob(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/jobs/upload', { method: 'POST', form })
}

export const uploadJobText = (text) => request('/jobs/upload-text', { method: 'POST', body: { text } })
export const deleteJob = (id) => request(`/jobs/${id}`, { method: 'DELETE' })

export const chat = (body) => request('/chat', { method: 'POST', body })
