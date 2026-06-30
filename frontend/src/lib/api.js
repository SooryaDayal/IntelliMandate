import axios from 'axios'

export const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    'ngrok-skip-browser-warning': 'true',
  },
})

// Unwraps {maps: [...]}, {mandates: [...]}, {audit: [...]} or plain arrays
function unwrapList(data, ...keys) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    for (const k of keys) {
      if (Array.isArray(data[k])) return data[k]
    }
  }
  return []
}

export async function fetchMaps() {
  const { data } = await client.get('/maps')
  return unwrapList(data, 'maps')
}

export async function fetchStats() {
  const { data } = await client.get('/stats')
  return data || {}
}

export async function fetchMapDetail(mapId) {
  const { data } = await client.get(`/maps/${mapId}`)
  return data
}

export async function fetchAssignments(mapId) {
  const { data } = await client.get(`/maps/${mapId}/assignments`)
  return unwrapList(data, 'assignments')
}

export async function fetchGraphImpact(mandateId) {
  const { data } = await client.get(`/graph/impact/${mandateId}`)
  return unwrapList(data, 'maps', 'affected_maps')
}

export async function fetchHistory() {
  const { data } = await client.get('/scrape/history')
  return unwrapList(data, 'mandates')
}

export async function fetchScrapeStatus() {
  const { data } = await client.get('/scrape/status')
  return data
}

export async function triggerOnlineScrape(maxCirculars = 10) {
  const { data } = await client.post(`/scrape/rbi?max_circulars=${maxCirculars}`)
  return data
}

export async function triggerOfflineLoad() {
  const { data } = await client.post('/scrape/offline')
  return data
}

export async function triggerOrchestrate(mandateId) {
  const { data } = await client.post(`/agents/orchestrate/${mandateId}`)
  return data
}

export async function uploadCircular({ file, title, source }) {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title || '')
  form.append('source', source)
  const { data } = await client.post('/scrape/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  return data
}

export async function uploadEvidence(mapId, { file, fileHash }) {
  const form = new FormData()
  form.append('file', file)
  form.append('file_hash', fileHash)
  const { data } = await client.post(`/maps/${mapId}/evidence`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  return data
}

export async function validateEvidence(evidenceId) {
  try {
    const { data } = await client.post(`/agents/validate/${evidenceId}`)
    return data
  } catch {
    const { data } = await client.get(`/agents/validate/${evidenceId}`)
    return data
  }
}

export async function fetchAudit() {
  const { data } = await client.get('/audit')
  return unwrapList(data, 'audit', 'certificates', 'records')
}

export async function sha256Hex(arrayBuffer) {
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

export async function clearAllData() {
  const res = await fetch(`${API_BASE}/admin/clear-all`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export default client