/**
 * The single place the frontend talks to the backend.
 *
 * There is no API key here and there never should be -- every LLM call
 * and every embedding computation happens on the server. The browser only ever
 * sees results.
 */

const BASE = '/api'

/** An error carrying the backend's structured {code, message, hint}. */
export class ApiError extends Error {
  constructor({ code, message, hint, status }) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.hint = hint
    this.status = status
  }
}

async function request(path, { method = 'GET', body, signal, isForm = false } = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: isForm || !body ? undefined : { 'Content-Type': 'application/json' },
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError({
      code: 'network_error',
      message: "Couldn't reach the server.",
      hint: 'Make sure the backend is running on http://localhost:8000.',
      status: 0,
    })
  }

  if (response.status === 204) return null

  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const detail = payload?.error ?? {}
    throw new ApiError({
      code: detail.code ?? `http_${response.status}`,
      message: detail.message ?? 'Something went wrong.',
      hint: detail.hint,
      status: response.status,
    })
  }

  return payload
}

// -- system -----------------------------------------------------------------
export const getHealth = () => request('/health')
export const getSamples = () => request('/samples')

// -- sessions ---------------------------------------------------------------
export const createSession = () => request('/sessions', { method: 'POST' })
export const getSession = (id) => request(`/sessions/${id}`)
export const deleteSession = (id) => request(`/sessions/${id}`, { method: 'DELETE' })

// -- documents --------------------------------------------------------------
export function uploadDocument(sessionId, docType, file) {
  const form = new FormData()
  form.append('file', file)
  return request(`/sessions/${sessionId}/documents/${docType}/upload`, {
    method: 'POST',
    body: form,
    isForm: true,
  })
}

export const pasteDocument = (sessionId, docType, text, name) =>
  request(`/sessions/${sessionId}/documents/${docType}/text`, {
    method: 'POST',
    body: { text, name },
  })

export const getDocument = (sessionId, docType) =>
  request(`/sessions/${sessionId}/documents/${docType}`)

export const loadSamples = (sessionId, { resumeId, jdId }) =>
  request(`/sessions/${sessionId}/samples/load`, {
    method: 'POST',
    body: { resume_id: resumeId ?? null, jd_id: jdId ?? null },
  })

// -- analysis ---------------------------------------------------------------
const analysis = (sessionId, name, refresh) =>
  request(`/sessions/${sessionId}/analysis/${name}${refresh ? '?refresh=true' : ''}`)

export const getResumeProfile = (id, refresh) => analysis(id, 'resume', refresh)
export const getJobProfile = (id, refresh) => analysis(id, 'job', refresh)
export const getMatch = (id, refresh) => analysis(id, 'match', refresh)
export const getSkills = (id, refresh) => analysis(id, 'skills', refresh)
export const getAts = (id, refresh) => analysis(id, 'ats', refresh)
export const getProjects = (id, refresh) => analysis(id, 'projects', refresh)
export const getImprovements = (id, refresh) => analysis(id, 'improvements', refresh)
export const getPriorities = (id, refresh) => analysis(id, 'priorities', refresh)
export const getDashboard = (id, refresh) => analysis(id, 'dashboard', refresh)

export const setImprovementDecision = (sessionId, suggestionId, decision) =>
  request(`/sessions/${sessionId}/analysis/improvements/decision`, {
    method: 'POST',
    body: { suggestion_id: suggestionId, decision },
  })

// -- chat -------------------------------------------------------------------
export const askQuestion = (sessionId, question, signal) =>
  request(`/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: { question, remember: true },
    signal,
  })

export const getChatHistory = (sessionId) => request(`/sessions/${sessionId}/chat`)
export const clearChat = (sessionId) =>
  request(`/sessions/${sessionId}/chat`, { method: 'DELETE' })

// -- preparation ------------------------------------------------------------
export const getInterview = (id, refresh) =>
  request(`/sessions/${id}/interview${refresh ? '?refresh=true' : ''}`)

export const regenerateInterview = (id, { focus, refresh = true }) =>
  request(`/sessions/${id}/interview`, { method: 'POST', body: { focus, refresh } })

export const getRoadmap = (id, refresh) =>
  request(`/sessions/${id}/roadmap${refresh ? '?refresh=true' : ''}`)

export const regenerateRoadmap = (id, { weeks = 0, refresh = true }) =>
  request(`/sessions/${id}/roadmap`, { method: 'POST', body: { weeks, refresh } })
