// Thin fetch wrapper. The token lives in sessionStorage (cleared when the browser tab closes).
const KEY = 'nirikshan.session'

export function getSession() {
  try { return JSON.parse(sessionStorage.getItem(KEY) || 'null') } catch { return null }
}
export function setSession(s) {
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY) } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const s = getSession()
  const headers = {}
  if (s?.token) headers.Authorization = `Bearer ${s.token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) })
  if (res.status === 401 && s) { setSession(null); window.location.assign('/login') }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try { const j = await res.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* not json */ }
    throw new ApiError(res.status, msg)
  }
  if (raw) return res
  return res.status === 204 ? null : res.json()
}

// Page images need the auth header, so fetch them as blobs.
export async function pageImage(docId, page) {
  const res = await api(`/api/documents/${docId}/page/${page}`, { raw: true })
  const blob = await res.blob()
  return { url: URL.createObjectURL(blob), w: Number(res.headers.get('X-Page-Width')), h: Number(res.headers.get('X-Page-Height')) }
}

export async function openAuthed(path) {
  const res = await api(path, { raw: true })
  const blob = await res.blob()
  window.open(URL.createObjectURL(blob), '_blank', 'noopener')
}
