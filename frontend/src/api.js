async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return data
}

export const api = {
  me: () => request('/api/auth/me'),
  login: (username, password) => request('/api/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  overview: () => request('/api/overview'),
  documents: (q = '') => request(`/api/documents?q=${encodeURIComponent(q)}`),
  document: (id) => request(`/api/documents/${id}`),
  acknowledge: (id, payload) => request(`/api/documents/${id}/acknowledge`, {
    method: 'POST', body: JSON.stringify(payload),
  }),
  team: () => request('/api/team'),
  audit: () => request('/api/audit'),
}
