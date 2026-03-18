const BASE = import.meta.env.VITE_API_URL
const KEY = import.meta.env.VITE_API_KEY

const headers = () => ({
  'Content-Type': 'application/json',
  'X-Chimera-API-Key': KEY,
})

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // System
  health: () => fetch(`${BASE}/health`).then(r => r.json()),
  status: () => req('/status'),
  version: () => req('/version'),

  // Registry
  getRegistry: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return req(`/v1/registry${q ? '?' + q : ''}`, { headers: headers() })
  },
  getRecord: (id) => req(`/v1/registry/${id}`, { headers: headers() }),
  getMetrics: () => req('/v1/registry/metrics', { headers: headers() }),
  agentQuery: (query) => req('/v1/registry/agent/query', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ query }),
  }),

  // Sources
  getSources: () => req('/v1/sources', { headers: headers() }),
  createSource: (data) => req('/v1/sources', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  }),
  deleteSource: (id) => req(`/v1/sources/${id}`, {
    method: 'DELETE',
    headers: headers(),
  }),

  // Config
  getConfig: () => req('/v1/config', { headers: headers() }),
  updateConfig: (data) => req('/v1/config', {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  }),

  // Ingest
  manualIngest: (message_id) => req('/v1/ingest/manual', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ message_id }),
  }),
}
